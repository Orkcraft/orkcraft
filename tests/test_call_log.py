"""The Test bench's log of model calls (realm/call_log.py): kept only inside a bench run, a line and the call each."""
from __future__ import annotations

import json
import threading

import pytest

from orkcraft.realm import call_log, jobs, road_agents

ENVELOPE = json.dumps({"result": "done", "total_cost_usd": 0.03, "session_id": "s1",
                       "usage": {"input_tokens": 900, "output_tokens": 100, "cache_read_input_tokens": 4000}})


@pytest.fixture
def tool(monkeypatch):
    seen = {}

    def run_proc(cmd, cwd, env, stdin, wait, harness=""):
        seen["env"] = env
        return seen.get("code", 0), seen.get("out", ENVELOPE), "a warning"

    monkeypatch.setattr(road_agents, "run_proc", run_proc)
    return seen


def test_outside_a_bench_run_no_call_is_kept(tmp_path, tool):
    jobs.run_work("claude", "do it", tmp_path, threading.Event())
    assert not list(tmp_path.rglob(call_log.LINES))


def test_a_call_in_a_bench_run_keeps_its_line_and_itself(tmp_path, tool):
    with call_log.kept(tmp_path / "calls", "building"):
        jobs.run_work("claude", "fix the tests", tmp_path, threading.Event(), "sonnet",
                      env={"ORKCRAFT_ORC": "pool/Grub", "SECRET_KEY": "x"})
    jobs.run_work("claude", "after the run", tmp_path, threading.Event())          # no longer kept
    [line] = call_log.read(tmp_path / "calls")
    assert (line["side"], line["who"], line["mode"], line["tool"], line["model"]) == \
        ("building", "Grub", "work", "claude", "sonnet")
    assert (line["code"], line["cost"], line["tokens"]) == (0, 0.03, 5000)
    assert line["usage"] == {"input_tokens": 900, "output_tokens": 100, "cache_read_input_tokens": 4000}
    raw = call_log.raw(tmp_path / "calls", line)
    assert raw["prompt"] == "fix the tests" and raw["stdout"] == ENVELOPE and raw["stderr"] == "a warning"
    assert "SECRET_KEY" not in (tmp_path / "calls" / call_log.LINES).read_text()


def test_a_call_that_fails_is_kept_too(tmp_path, tool):
    tool.update(code=1, out="not logged in")
    with call_log.kept(tmp_path / "calls", "bare"), pytest.raises(RuntimeError):
        jobs.run_read("claude", "read it", tmp_path, threading.Event())
    [line] = call_log.read(tmp_path / "calls")
    assert (line["side"], line["who"], line["mode"], line["code"], line["tokens"]) == ("bare", "", "read", 1, None)


def test_the_calls_add_up_by_side_who_and_purpose(tmp_path, tool):
    with call_log.kept(tmp_path / "calls", "building"):
        for who in ("Grub", "Grub", "steward"):
            jobs.run_work("claude", "x", tmp_path, threading.Event(), env={"ORKCRAFT_ORC": f"pool/{who}"})
    with call_log.kept(tmp_path / "calls", "bare"):                   # a second block goes on numbering
        jobs.run_work("claude", "x", tmp_path, threading.Event())
    lines = call_log.read(tmp_path / "calls")
    assert [x["n"] for x in lines] == [1, 2, 3, 4] and len({x["raw"] for x in lines}) == 4
    rows = {(t["side"], t["who"]): t for t in call_log.totals(lines)}
    assert rows[("building", "Grub")]["calls"] == 2 and rows[("building", "Grub")]["tokens"] == 10000
    assert rows[("building", "Grub")]["usage"]["input_tokens"] == 1800
    assert rows[("bare", "")]["calls"] == 1


def test_the_usage_is_read_from_an_envelope_or_the_last_event():
    assert call_log.usage_of(ENVELOPE)["output_tokens"] == 100
    lines = "\n".join(json.dumps(e) for e in ({"type": "turn.completed", "usage": {"input_tokens": 1}},
                                              {"type": "turn.completed", "usage": {"input_tokens": 7, "output_tokens": 2}}))
    assert call_log.usage_of(lines) == {"input_tokens": 7, "output_tokens": 2}
    assert call_log.usage_of("plain text") == {}
