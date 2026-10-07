"""The Warder and the session log for Hermes, Cursor and pi (hooks/warder.py, hooks/install.py,
hooks/pi_extension.py): each tool's payload is judged as the Claude Code tool it is, and each hears
the verdict its way."""
from __future__ import annotations

import io
import json
import sys
from pathlib import Path

import pytest

from orkcraft.hooks import install, pi_extension, warder


def _warder(monkeypatch, capsys, harness: str, payload: dict) -> str:
    monkeypatch.setattr(sys, "argv", ["warder", harness])
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
    monkeypatch.setattr(warder, "log", lambda *a, **k: None)
    assert warder.main() == 0
    return capsys.readouterr().out.strip()


@pytest.mark.parametrize("harness, payload", [
    ("hermes", {"tool_name": "terminal", "tool_input": {"command": "rm -rf /"}, "cwd": "/tmp"}),
    ("cursor", {"hook_event_name": "preToolUse", "tool_name": "Shell", "tool_input": {"command": "rm -rf /"},
                "workspace_roots": ["/tmp"]}),
    ("cursor", {"hook_event_name": "beforeShellExecution", "command": "rm -rf /", "cwd": "/tmp"}),
    ("pi", {"tool_name": "bash", "tool_input": {"command": "rm -rf /"}, "cwd": "/tmp"}),
])
def test_each_tool_hears_a_deny_its_way(monkeypatch, capsys, harness, payload):
    said = json.loads(_warder(monkeypatch, capsys, harness, payload))
    if harness == "hermes":
        assert said["decision"] == "block" and "Warder" in said["reason"]
    elif harness == "cursor":
        assert said["permission"] == "deny" and "Warder" in said["agent_message"]
    else:
        assert said["decision"] == "deny"


def test_a_secret_file_is_kept_from_every_tool(monkeypatch, capsys):
    for harness, name, args in (("hermes", "read_file", {"path": ".env"}), ("cursor", "Read", {"path": ".env"}),
                                ("pi", "read", {"path": ".env"})):
        out = _warder(monkeypatch, capsys, harness, {"tool_name": name, "tool_input": args, "cwd": "/tmp"})
        assert "deny" in out or "block" in out


def test_an_ask_goes_to_hermes_own_gate_and_nothing_said_is_nothing(monkeypatch, capsys):
    said = json.loads(_warder(monkeypatch, capsys, "hermes",
                              {"tool_name": "terminal", "tool_input": {"command": "git reset --hard"}, "cwd": "/tmp"}))
    assert said["action"] == "approve"
    assert _warder(monkeypatch, capsys, "hermes", {"tool_name": "terminal", "tool_input": {"command": "ls"}}) == ""
    assert _warder(monkeypatch, capsys, "cursor", {"tool_name": "Shell", "tool_input": {"command": "ls"}}) == "{}"


def test_cursor_hooks_merge_and_go_again(tmp_path: Path):
    (tmp_path / ".cursor").mkdir()
    (tmp_path / ".cursor" / "hooks.json").write_text(json.dumps(
        {"version": 1, "hooks": {"preToolUse": [{"command": "./mine.sh"}]}}), encoding="utf-8")
    install.install_cursor(tmp_path)
    install.install_cursor(tmp_path)                                         # replaced, not doubled
    data = json.loads((tmp_path / ".cursor" / "hooks.json").read_text())
    assert [e["command"] for e in data["hooks"]["preToolUse"]][0] == "./mine.sh"
    assert len(data["hooks"]["preToolUse"]) == 2 and "warder cursor" in data["hooks"]["preToolUse"][1]["command"]
    assert install.uninstall_cursor(tmp_path)
    data = json.loads((tmp_path / ".cursor" / "hooks.json").read_text())
    assert data["hooks"] == {"preToolUse": [{"command": "./mine.sh"}]}


def test_hermes_gets_a_marked_block_and_never_a_second_hooks_key(tmp_path: Path):
    cfg = tmp_path / "config.yaml"
    cfg.write_text("model:\n  default: x\n", encoding="utf-8")
    install.install_hermes_global(cfg)
    install.install_hermes_global(cfg)
    text = cfg.read_text()
    assert text.startswith("model:\n  default: x\n") and text.count(install.HERMES_BEGIN) == 1
    assert "pre_tool_call" in text and "warder hermes" in text
    assert install.uninstall_hermes_global(cfg) == cfg and cfg.read_text() == "model:\n  default: x\n"
    cfg.write_text("hooks:\n  pre_tool_call: []\n", encoding="utf-8")
    with pytest.raises(ValueError, match="by hand"):
        install.install_hermes_global(cfg)


def test_pi_extension_carries_this_python_and_is_written_once(tmp_path: Path):
    path = pi_extension.write(tmp_path / "x.ts")
    text = path.read_text()
    assert json.dumps(sys.executable) in text and 'pi.on("tool_call"' in text and "block: true" in text
    mtime = path.stat().st_mtime_ns
    assert pi_extension.write(tmp_path / "x.ts") == path and path.stat().st_mtime_ns == mtime
