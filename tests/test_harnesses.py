"""The registry of AI tools (realm/harnesses.py): every tool answers, reads and works through it, and
its output is read the same way whatever the tool."""
from __future__ import annotations

import json

import pytest

from orkcraft.realm import builders, harnesses, roads


def _lines(*events: dict) -> str:
    return "\n".join(json.dumps(e) for e in events)


def test_every_tool_is_registered_once_in_order():
    assert harnesses.ids() == ("claude", "agy", "codex", "hermes", "pi", "cursor")
    assert all(len(h.mark) == 1 for h in harnesses.REGISTRY.values())


@pytest.mark.parametrize("tool", harnesses.ids())
def test_a_prompt_never_reads_as_a_flag(tool, tmp_path):
    h = harnesses.need(tool)
    for cmd in (h.ask("-rm everything", tmp_path), h.read("-x", tmp_path), h.work("-x", tmp_path)):
        if h.stdin_prompt:
            assert "-rm everything" not in cmd and "-x" not in cmd
        else:
            i = cmd.index("-rm everything") if "-rm everything" in cmd else cmd.index("-x")
            assert cmd[i - 1] in ("-p", "--print", "--")                    # it is a flag's value or after --
    assert h.interactive("-x") in (None, [*h.interactive(), *h.deploy_args, "Orders: -x"])


def test_hermes_reads_its_stream():
    out = _lines({"type": "system", "subtype": "init", "model": "m", "session_id": "20261007_120000_abcdef"},
                 {"type": "text", "text": "par"}, {"type": "text", "text": "tial"},
                 {"type": "result", "session_id": "20261007_120000_abcdef", "exit_code": 0, "text": "the answer",
                  "tokens": {"input": 10, "output": 5, "total": 15}})
    assert harnesses.hermes_result(out) == ("the answer", None, 15, "20261007_120000_abcdef")
    assert harnesses.hermes_error(_lines({"type": "result", "error": "no provider"})) == "no provider"
    h = harnesses.need("hermes")
    assert "--toolsets" in h.read("x", "/r") and "write" not in " ".join(h.read("x", "/r"))
    assert h.env("read", "/r")["HERMES_WRITE_SAFE_ROOT"] == harnesses.NOWHERE           # reading writes nowhere
    assert h.env("work", "/w")["HERMES_WRITE_SAFE_ROOT"] == "/w"                        # working: its worktree


def test_pi_sums_its_messages_and_their_price():
    usage = lambda n, usd: {"totalTokens": n, "cost": {"total": usd}}                  # noqa: E731
    out = _lines({"type": "session", "version": 3, "id": "u-1", "cwd": "/r"},
                 {"type": "message_end", "message": {"role": "assistant", "content": [{"type": "text", "text": "a"}],
                                                     "usage": usage(100, 0.01)}},
                 {"type": "message_end", "message": {"role": "toolResult", "content": []}},
                 {"type": "message_end", "message": {"role": "assistant", "content": [{"type": "text", "text": "done"}],
                                                     "usage": usage(50, 0.02)}})
    text, cost, tokens, session = harnesses.pi_result(out)
    assert (text, round(cost, 4), tokens, session) == ("done", 0.03, 150, "u-1")
    h = harnesses.need("pi")
    read = h.read("x", "/r")
    assert "--no-tools" in h.ask("x", "/f") and read[read.index("--tools") + 1] == "read,grep,find,ls"
    assert read[read.index("-e") + 1].endswith("orkcraft.ts")                         # the Warder rides along


def test_cursor_reads_its_result_line():
    out = _lines({"type": "system", "subtype": "init", "session_id": "c-1", "model": "Auto"},
                 {"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": "hi"}]},
                  "session_id": "c-1"},
                 {"type": "result", "subtype": "success", "is_error": False, "result": "hi", "session_id": "c-1",
                  "usage": {"inputTokens": 7, "outputTokens": 3, "cacheReadTokens": 0, "cacheWriteTokens": 0}})
    assert harnesses.cursor_result(out) == ("hi", None, 10, "c-1")
    assert harnesses.cursor_error(_lines({"type": "result", "subtype": "error", "is_error": True, "result": "bad model"})) \
        == "bad model"
    assert "--mode" in harnesses.need("cursor").read("x", "/r")                         # ask: never edits


def test_a_model_moves_between_tools_by_its_tier():
    assert harnesses.model_on("codex", "haiku") == "gpt-6-luna"
    assert harnesses.model_on("claude", "elder") == "opus"
    assert harnesses.model_on("agy", "my-own-model") == "my-own-model"
    assert harnesses.model_on("pi", "opus") == ""                       # no tiers: its own default


@pytest.mark.parametrize("tool, answer, expect", [
    ("hermes", _lines({"type": "result", "session_id": "s", "text": "{}", "tokens": {"total": 3}}), ("{}", None)),
    ("pi", _lines({"type": "session", "id": "s"}, {"type": "message_end", "message": {
        "role": "assistant", "content": [{"type": "text", "text": "{}"}], "usage": {"totalTokens": 3, "cost": {"total": 0.5}}}}),
     ("{}", 0.5)),
    ("cursor", _lines({"type": "result", "result": "{}", "session_id": "s"}), ("{}", None)),
])
def test_a_decision_runs_on_any_tool(tool, answer, expect, tmp_path, monkeypatch):
    fake, record = tmp_path / f"fake-{tool}", tmp_path / "argv.json"
    fake.write_text("#!/usr/bin/env python3\nimport json, os, sys\n"
                    "stdin = '' if sys.stdin is None or sys.stdin.isatty() else sys.stdin.read()\n"
                    f"json.dump({{'argv': sys.argv[1:], 'stdin': stdin, 'env': dict(os.environ)}}, open({str(record)!r}, 'w'))\n"
                    f"sys.stdout.write({answer!r})\n", encoding="utf-8")
    fake.chmod(0o755)
    monkeypatch.setenv(f"ORKCRAFT_{tool.upper()}_BIN", str(fake))
    assert builders.ask(tool, "plan it") == expect
    rec = json.loads(record.read_text())
    assert ("plan it" in rec["argv"]) != (rec["stdin"] == "plan it")
    assert not any(k.startswith("ORKCRAFT_") for k in rec["env"])
    assert roads.resolve("main") in harnesses.ids()


def test_logins_of_the_new_tools_are_told_from_disk(tmp_path):
    from orkcraft import tools
    home = tmp_path
    assert tools._hermes_login({}, home) == (None, "subscription")
    (home / ".hermes").mkdir()
    (home / ".hermes" / ".env").write_text("OPENROUTER_API_KEY=sk-x\n", encoding="utf-8")
    assert tools._hermes_login({}, home) == (True, "api")
    (home / ".hermes" / "auth.json").write_text('{"providers": {"nous": {}}}', encoding="utf-8")
    assert tools._hermes_login({}, home) == (True, "subscription")
    (home / ".pi" / "agent").mkdir(parents=True)
    (home / ".pi" / "agent" / "auth.json").write_text('{"anthropic": {"type": "oauth"}}', encoding="utf-8")
    assert tools._pi_login({}, home) == (True, "subscription")
    assert tools._cursor_login({"CURSOR_API_KEY": "k"}, home) == (True, "subscription")
    assert tools._cursor_login({}, home) == (None, "subscription")
    found = tools.detect(which=lambda b: f"/bin/{b}" if b in ("pi", "cursor-agent") else None,
                         run=lambda *a, **k: type("P", (), {"stdout": "1.0.4", "stderr": "", "returncode": 0})(),
                         env={}, home=home)
    assert [s.id for s in found if s.found] == ["pi", "cursor"] and found[4].logged_in


def test_autonomy_says_what_each_new_tool_changes():
    from orkcraft import autonomy
    free = autonomy.guide(autonomy.FREE, ("hermes", "pi", "cursor"))
    assert "hermes --yolo" in free and "cursor-agent --force" in free and "never asks" in free
    chains = autonomy.guide(0, ("hermes", "cursor"))
    assert "--yolo" not in chains and "--force" not in chains


def test_mcp_servers_of_hermes_pi_and_cursor_are_named_never_read(tmp_path):
    from orkcraft.realm import mcp
    (tmp_path / ".hermes").mkdir()
    (tmp_path / ".hermes" / "config.yaml").write_text(
        "model:\n  default: x\nmcp_servers:\n  github:\n    command: npx\n    env:\n      TOKEN: secret\n"
        "  linear:\n    url: https://x\nhooks: {}\n", encoding="utf-8")
    (tmp_path / ".cursor").mkdir()
    (tmp_path / ".cursor" / "mcp.json").write_text('{"mcpServers": {"github": {}, "figma": {}}}', encoding="utf-8")
    (tmp_path / ".pi" / "agent").mkdir(parents=True)
    (tmp_path / ".pi" / "agent" / "mcp.json").write_text('{"mcpServers": {"sentry": {}}}', encoding="utf-8")
    got = {s.id: s.tools for s in mcp.found(home=tmp_path)}
    assert got == {"github": ("hermes", "cursor"), "linear": ("hermes",), "figma": ("cursor",), "sentry": ("pi",)}
