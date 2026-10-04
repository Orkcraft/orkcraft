"""Codex as a harness: `codex exec` without a terminal, its JSONL events read back."""
from __future__ import annotations

import json
import sys
import threading
from pathlib import Path

import pytest

from orkcraft import scroll as ts
from orkcraft.realm import barracks as bk
from orkcraft.realm import jobs, looks, roads, team, tiers

FIXTURE = Path(__file__).parent / "fixtures" / "codex_exec.jsonl"


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
