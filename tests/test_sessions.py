"""Sessions: the hook recorder, the merged session sources, the terminal and the Chat window."""
from __future__ import annotations

import importlib.util
import json
import os
import stat
import subprocess
from pathlib import Path

import pytest

from orkcraft.app import OrkcraftApp
from orkcraft.sources import sessions as ss
from orkcraft.widgets.terminal import Terminal

REAL_REPO = Path(__file__).resolve().parent.parent.parent


def _hook_module(repo: Path):
    """Load orkcraft/hooks/session.py with its log redirected into `repo`."""
    spec = importlib.util.spec_from_file_location("session_hook", Path(__file__).resolve().parents[1] / "orkcraft" / "hooks" / "session.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.LOG = repo / ".orkcraft" / "sessions.jsonl"
    return mod


def test_hook_records_claude_and_agy_payloads(tmp_path: Path):
    hook = _hook_module(tmp_path)
    e = hook.record("claude", {"session_id": "s1", "hook_event_name": "UserPromptSubmit",
                               "prompt": "fix [[T1092]] then T1090 and T1092"}, env={"ORKCRAFT_TICKET": "T1089"})
    assert e["tickets"] == ["T1089", "T1092", "T1090"]
    e = hook.record("agy", {"conversationId": "c9", "workspacePaths": ["/w"], "transcriptPath": "/t"}, env={})
    assert e["session"] == "c9" and e["cwd"] == "/w" and e["transcript"] == "/t"
    assert hook.record("claude", {"no": "id"}, env={}) is None
    lines = hook.LOG.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2


def test_hook_script_never_fails_and_prints_only_for_agy(tmp_path: Path):
    script = Path(__file__).resolve().parents[1] / "orkcraft" / "hooks" / "session.py"
    for harness, expected in (("agy", "{}"), ("claude", "")):
        out = subprocess.run(["python3", str(script), harness], input="not json", capture_output=True, text=True)
        assert out.returncode == 0 and out.stdout.strip() == expected


def _claude_transcript(folder: Path, sid: str, prompt: str) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    rows = [
        {"type": "queue-operation", "sessionId": sid},
        {"type": "user", "message": {"role": "user", "content": prompt}, "sessionId": sid},
        {"type": "user", "message": {"role": "user", "content": [{"type": "tool_result", "content": "T9999"}]}},
    ]
    (folder / f"{sid}.jsonl").write_text("\n".join(json.dumps(r, separators=(",", ":")) for r in rows), encoding="utf-8")


def test_sessions_merge_log_transcripts_agy_and_git(fake_repo: Path, tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ORKCRAFT_CLAUDE_HOME", str(tmp_path / "claude"))
    monkeypatch.setenv("ORKCRAFT_AGY_HOME", str(tmp_path / "agy"))
    _claude_transcript(ss.claude_projects_dir(fake_repo), "loc-1", "поработай над [[T1001]]")
    (tmp_path / "agy" / "brain" / "conv-7").mkdir(parents=True)
    hook = _hook_module(fake_repo)
    hook.record("agy", {"conversationId": "conv-7"}, env={"ORKCRAFT_TICKET": "T1002"})
    subprocess.run(["git", "commit", "-q", "--allow-empty", "-m",
                    "task(T1003): x\n\nClaude-Session: https://claude.ai/code/session_ABC123"], cwd=fake_repo, check=True)

    found = {s.key: s for s in ss.collect_sessions(fake_repo, max_age=0)}
    local = found["claude:loc-1"]
    assert local.tickets == {"T1001"} and local.title.startswith("поработай")  # tool results ignored
    assert found["agy:conv-7"].tickets == {"T1002"}
    web = found["claude-web:session_ABC123"]
    assert web.tickets == {"T1003"} and web.url.endswith("session_ABC123") and not web.resumable

    assert ss.resume_command(local)[-2:] == ["--resume", "loc-1"]
    assert ss.resume_command(found["agy:conv-7"])[-2:] == ["--conversation", "conv-7"]
    assert ss.resume_command(web) is None
    assert [s.key for s in ss.sessions_for(list(found.values()), "T1002")] == ["agy:conv-7"]


@pytest.fixture
def fake_cli(tmp_path: Path, monkeypatch) -> Path:
    """A stand-in for `claude`: prints its args and ticket, echoes one line back."""
    script = tmp_path / "fake-claude"
    script.write_text("#!/bin/bash\necho \"args:$* ticket:$ORKCRAFT_TICKET\"\nread line\necho \"you said:$line\"\nsleep 5\n")
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("ORKCRAFT_CLAUDE_BIN", str(script))
    monkeypatch.setenv("ORKCRAFT_CLAUDE_HOME", str(tmp_path / "claude"))
    monkeypatch.setenv("ORKCRAFT_AGY_HOME", str(tmp_path / "agy"))
    return script


async def _wait_for(pilot, predicate, tries: int = 40):
    for _ in range(tries):
        if predicate():
            return True
        await pilot.pause(0.05)
    return predicate()


@pytest.mark.asyncio
async def test_chat_new_session_runs_cli_with_ticket_and_owns_keys(fake_repo: Path, fake_cli: Path):
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=(160, 50)) as pilot:
        await pilot.pause()
        app.open_chat("T1001")
        await pilot.pause()
        term = app.screen.query_one(Terminal)
        assert await _wait_for(pilot, lambda: any("args:" in l for l in term.text_lines()))
        assert "ticket:T1001" in term.text_lines()[0]
        assert app.focused is term
        # q and digits reach the CLI instead of quitting orkcraft or switching windows.
        await pilot.press("q", "1", "enter")
        assert await _wait_for(pilot, lambda: any("you said:q1" in l for l in term.text_lines()))
        assert app.is_running
        await pilot.press("f12")
        await pilot.pause()
        assert app.focused.id == "chat-sessions"
        term.stop()


@pytest.mark.asyncio
async def test_chat_resumes_recorded_session(fake_repo: Path, fake_cli: Path):
    _hook_module(fake_repo).record("claude", {"session_id": "sess-42"}, env={"ORKCRAFT_TICKET": "T1001"})
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=(160, 50)) as pilot:
        await pilot.pause()
        app.open_chat("T1001")
        await pilot.pause()
        term = app.screen.query_one(Terminal)
        assert await _wait_for(pilot, lambda: any("args:" in l for l in term.text_lines()))
        assert "args:--resume sess-42" in term.text_lines()[0]
        term.stop()


def test_deploy_command_passes_orders_as_one_safe_argument(monkeypatch):
    from orkcraft.sources.sessions import deploy_command

    monkeypatch.setenv("ORKCRAFT_CLAUDE_BIN", "claude")
    assert deploy_command("claude", "") == ["claude"]
    assert deploy_command("claude", "You are Coder. Orders: take T1001; rm -rf nothing") == \
        ["claude", "You are Coder. Orders: take T1001; rm -rf nothing"]
    assert deploy_command("claude", "--dangerously-skip-permissions") == \
        ["claude", "Orders: --dangerously-skip-permissions"]
    assert deploy_command("agy", "anything") is None


def test_hook_records_a_deployed_orc_and_rejects_junk(tmp_path, monkeypatch):
    import importlib.util, sys
    spec = importlib.util.spec_from_file_location(
        "session_hook", Path(__file__).resolve().parents[1] / "orkcraft" / "hooks" / "session.py")
    hook = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(hook)
    monkeypatch.setattr(hook, "LOG", tmp_path / "sessions.jsonl")
    e = hook.record("claude", {"session_id": "s1"}, env={"ORKCRAFT_ORC": "forge/coder"})
    assert e["orc"] == "forge/coder"
    e = hook.record("claude", {"session_id": "s2"}, env={"ORKCRAFT_ORC": "../../x; rm"})
    assert "orc" not in e
