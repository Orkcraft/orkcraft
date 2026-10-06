"""Codex: a harness without a terminal (`codex exec`, its JSONL events) and a War Tent session."""
from __future__ import annotations

import json
import sys
import threading
from pathlib import Path

import pytest

from orkcraft import scroll as ts
from orkcraft.app import OrkcraftApp
from orkcraft.realm import barracks as bk
from orkcraft.realm import jobs, looks, orcs, roads, roster, team, tiers
from orkcraft.sources import sessions as ss

FIXTURE = Path(__file__).parent / "fixtures" / "codex_exec.jsonl"
TRUST_SCREEN = Path(__file__).parent / "fixtures" / "codex_trust_screen.txt"


def fake_codex(tmp_path: Path, monkeypatch, *, exit_code: int = 0, noise: int = 0) -> Path:
    """A `codex` on ORKCRAFT_CODEX_BIN that answers with where it ran, its argv and its stdin."""
    script = tmp_path / "codex"
    script.write_text(f"""#!{sys.executable}
import json, os, sys
prompt = sys.stdin.read()
print(json.dumps({{"type": "thread.started", "thread_id": "th-1"}}))
print(json.dumps({{"type": "item.completed", "item": {{"type": "command_execution", "aggregated_output": "x" * {noise}}}}}))
if {exit_code}:
    print(json.dumps({{"type": "turn.failed", "error": {{"message": "usage limit reached"}}}}))
    sys.exit({exit_code})
answer = json.dumps({{"cwd": os.getcwd(), "argv": sys.argv[1:], "prompt": prompt}})
print(json.dumps({{"type": "item.completed", "item": {{"type": "agent_message", "text": answer}}}}))
print(json.dumps({{"type": "turn.completed", "usage": {{"input_tokens": 10, "cached_input_tokens": 8, "output_tokens": 2}}}}))
""", encoding="utf-8")
    script.chmod(0o755)
    monkeypatch.setenv("ORKCRAFT_CODEX_BIN", str(script))
    return script


def test_the_real_events_give_the_last_message_the_tokens_and_the_thread():
    text, cost, tokens, session = roads.codex_result_of(FIXTURE.read_text(encoding="utf-8"))
    assert text == "done" and cost is None                    # Codex prints no price: unpriced, never $0
    assert tokens == 34612 + 121                                # cached input is part of the input
    assert session == "01a10872-003f-76b1-84f2-bc6657c93545"
    assert roads.codex_result_of("not json\n") == ("", None, None, "")


RESUMED = Path(__file__).parent / "fixtures" / "codex_exec_resumed.jsonl"
ROLLOUT = Path(__file__).parent / "fixtures" / "codex_rollout.jsonl"
THREAD = "01a10872-003f-76b1-84f2-bc6657c93545"


def test_turn_usage_is_a_running_total_so_the_last_one_counts():
    text, _, tokens, session = roads.codex_result_of(RESUMED.read_text(encoding="utf-8"))
    assert text == "done again" and session == THREAD
    assert tokens == 52000 + 450                                # not 40300 + 52450: each turn repeats the ones before
    assert roads.codex_result_of(RESUMED.read_text(encoding="utf-8"), before=34612 + 121)[2] == 52450 - 34733
    assert roads.codex_result_of(FIXTURE.read_text(encoding="utf-8"), before=10 ** 9)[2] == 0


def _codex_home(tmp_path: Path) -> Path:
    day = tmp_path / "codex-home" / "sessions" / "2026" / "10" / "05"
    day.mkdir(parents=True)
    (day / f"rollout-2026-10-05T09-00-00-{THREAD}.jsonl").write_text(ROLLOUT.read_text(encoding="utf-8"),
                                                                      encoding="utf-8")
    return tmp_path / "codex-home"


def test_a_threads_total_so_far_comes_from_its_rollout(tmp_path):
    env = {"CODEX_HOME": str(_codex_home(tmp_path))}
    assert roads.codex_thread_total(THREAD, env) == 34612 + 121      # the last total; a null `info` is skipped
    assert roads.codex_thread_total("another-thread", env) == 0
    assert roads.codex_thread_total("", env) == 0


def test_a_resumed_codex_run_counts_only_its_own_tokens(tmp_path, monkeypatch):
    fake_codex(tmp_path, monkeypatch)                     # its one turn reports a running total of 12
    day = _codex_home(tmp_path) / "sessions" / "2026" / "10" / "05"
    (day / f"rollout-2026-10-05T09-00-00-{THREAD}.jsonl").write_text(json.dumps(
        {"type": "event_msg", "payload": {"type": "token_count", "info": {
            "total_token_usage": {"input_tokens": 4, "cached_input_tokens": 0, "output_tokens": 1}}}}) + "\n",
        encoding="utf-8")
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "codex-home"))
    assert jobs.run_work("codex", "go on", tmp_path, threading.Event(), resume=THREAD)[2] == 12 - 5
    assert jobs.run_work("codex", "start", tmp_path, threading.Event())[2] == 12


def test_a_failed_turn_says_why():
    out = json.dumps({"type": "turn.failed", "error": {"message": "usage limit reached"}})
    assert roads.codex_error(out) == "usage limit reached"
    assert roads.codex_error(json.dumps({"type": "error", "message": "stream lost"})) == "stream lost"
    assert roads.failure("codex", 1, out, "mcp noise") == "codex exited with 1: usage limit reached"
    assert roads.failure("claude", 1, "", "boom") == "claude exited with 1: boom"


def test_codex_reads_the_repository_in_a_read_only_sandbox(tmp_path):
    cmd = roads._harness_cmd("codex", "hi", tmp_path, "gpt-6-luna")
    assert cmd[:4] == ["codex", "exec", "-", "--json"] and "hi" not in cmd        # the prompt goes on stdin
    assert 'sandbox_mode="read-only"' in cmd and 'web_search="disabled"' in cmd
    assert cmd[-2:] == ["--model", "gpt-6-luna"]
    assert 'web_search="live"' in roads._harness_cmd("codex", "hi", tmp_path, web=True)
    assert "--dangerously-bypass-approvals-and-sandbox" not in cmd
    assert roads.harness_stdin("codex", "hi") == "hi" and roads.harness_stdin("claude", "hi") is None


def test_a_codex_worker_writes_in_its_worktree_and_resumes(tmp_path):
    cmd = jobs.work_cmd("codex", "p", tmp_path, "gpt-6.1-sol")
    assert 'sandbox_mode="workspace-write"' in cmd and "p" not in cmd
    again = jobs.work_cmd("codex", "p", tmp_path, resume="th-1")
    assert again[:5] == ["codex", "exec", "resume", "th-1", "-"]


def test_run_agent_feeds_the_prompt_and_reads_a_long_stream(tmp_path, monkeypatch):
    fake_codex(tmp_path, monkeypatch, noise=200_000)          # more than a pipe holds
    repo = tmp_path / "repo"
    repo.mkdir()
    text, cost, tokens = roads.run_agent("codex", "-- orders that look like a flag", repo, {}, threading.Event())
    answer = json.loads(text)
    assert Path(answer["cwd"]).resolve() == repo.resolve()   # in the repository, like Claude
    assert answer["prompt"] == "-- orders that look like a flag" and answer["argv"][:2] == ["exec", "-"]
    assert (cost, tokens) == (None, 12)


def test_run_work_returns_the_session_and_a_failure_says_why(tmp_path, monkeypatch):
    fake_codex(tmp_path, monkeypatch)
    text, cost, tokens, session = jobs.run_work("codex", "do it", tmp_path, threading.Event())
    assert json.loads(text)["prompt"] == "do it" and session == "th-1" and tokens == 12
    fake_codex(tmp_path, monkeypatch, exit_code=1)
    with pytest.raises(RuntimeError, match="usage limit reached"):
        jobs.run_work("codex", "do it", tmp_path, threading.Event())


def test_codex_is_a_harness_everywhere_one_is_picked():
    assert "codex" in ts.HARNESSES and "codex" in jobs.HARNESSES
    assert team.parse_member("Reviewer:codex:elder") == team.Member("Reviewer", "codex", "gpt-6-astra")
    foreman = bk.Foreman({"providers": ["codex:laborer"]})
    assert foreman.providers == [("codex", "gpt-6-luna")] and "codex" in bk.RESUMABLE


@pytest.mark.parametrize("model, tier", [("gpt-6-astra", "elder"), ("gpt-6.1-sol", "warrior"),
                                         ("gpt-5.6-terra", "warrior"), ("gpt-6-luna", "laborer")])
def test_codex_models_have_tiers(model, tier):
    assert tiers.tier_of_model(model) == tier
    assert tiers.step_model({"harness": "codex", "tier": tier}) in tiers.MODELS["codex"].values()


def test_a_codex_step_wears_its_hexagon():
    assert looks.scheme_plain([{"role": "write", "harness": "codex"}, {"role": "review", "harness": "claude"}]) == "⌬→✻"


def test_the_schema_takes_a_codex_step():
    import jsonschema
    schema = json.loads((Path(ts.__file__).parent / "schemas" / "town-scroll.v3.json").read_text(encoding="utf-8"))
    step = {**schema["$defs"]["harness_step"], "$defs": schema["$defs"]}
    jsonschema.validate({"role": "run", "harness": "codex", "tier": "elder"}, step)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate({"role": "run", "harness": "openai"}, step)


# -- sessions and the War Tent ------------------------------------------------------------------------

def test_codex_sessions_start_resume_and_deploy(monkeypatch):
    monkeypatch.setenv("ORKCRAFT_CODEX_BIN", "codex")
    assert ss.new_command("codex") == ["codex"]
    assert ss.resume_command(ss.Session("codex", "th-1")) == ["codex", "resume", "th-1"]
    assert ss.Session("codex", "th-1").resumable
    assert ss.deploy_command("codex", "You are Scout. Orders: look") == ["codex", "You are Scout. Orders: look"]
    assert ss.deploy_command("codex", "--yolo") == ["codex", "Orders: --yolo"]


def test_a_codex_session_comes_from_the_hook_log(tmp_path):
    log = ss.log_file(tmp_path)
    log.parent.mkdir(parents=True)
    log.write_text(json.dumps({"ts": "2026-10-04T21:00:00", "harness": "codex", "session": "th-9",
                               "tickets": ["T1001"], "prompt": "fix the parser", "transcript": ""}) + "\n")
    found = ss.collect_sessions(tmp_path, max_age=0)
    assert [(s.key, s.title, s.tickets) for s in found] == [("codex:th-9", "fix the parser", {"T1001"})]


def test_a_codex_menu_is_an_order_to_wait_for():
    question, options = orcs.detect_prompt(TRUST_SCREEN.read_text(encoding="utf-8").splitlines())
    assert question.startswith("Trust this folder?")
    assert options == [("1", "Trust and continue"), ("2", "Back to Agent Command Center")]
    goblin = roster._worker(roster.WorkerInfo("new:codex:1", "codex", "", None, [], 0.0, False), 1)
    assert goblin.name == "Goblin #1"


@pytest.mark.asyncio
async def test_a_codex_menu_is_answered_with_enter(fake_repo: Path):
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=(160, 50)) as pilot:
        await pilot.pause()
        sent = []
        monkey = pytest.MonkeyPatch()
        monkey.setattr(app.chat, "send", lambda ref, data: sent.append((ref, data)))
        monkey.setattr(app.chat, "show_terminal", lambda ref: None)
        app.chat.meta["new:codex:1"] = ("codex", "", None)
        app.chat.meta["new:claude:1"] = ("claude", "", None)
        for ref in ("new:codex:1", "new:claude:1"):
            app.answer_alert(orcs.Alert(id=ref, title="?", options=[("1", "Yes")], source="terminal", ref=ref), "1")
        monkey.undo()
        assert sent == [("new:codex:1", b"1\r"), ("new:claude:1", b"1")]   # a digit alone only moves Codex's cursor


# -- onboarding: the autonomy guide ---------------------------------------------------------------------

def test_the_autonomy_guide_says_how_to_start_codex():
    from orkcraft import autonomy
    assert autonomy.codex_command(1) == "" and "nothing to change" in autonomy.codex_line(1)
    assert autonomy.codex_command(3) == "codex --sandbox workspace-write --ask-for-approval on-request"
    assert "Codex: start it with" in autonomy.guide(2, ("claude", "codex")) and "Antigravity" not in autonomy.guide(2, ("codex",))


@pytest.mark.asyncio
async def test_the_autonomy_step_has_a_codex_line_to_copy():
    from textual.app import App
    from textual.widgets import Static

    from orkcraft.screens.autonomy import AutonomyStep

    step = AutonomyStep(level=2, tools=("claude", "codex"))
    async with App().run_test(size=(120, 50)) as pilot:
        pilot.app.push_screen(step)
        await pilot.pause()
        line = str(step.query_one("#au-codex", Static).render())
        assert line.startswith("Codex: start it with") and not step.query("#au-agy")
        await pilot.press("o")
        await pilot.pause()
        assert step.copied == "codex --sandbox workspace-write --ask-for-approval on-request"
