"""Chronicles: building event log and Claude transcript runs."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from orkcraft import scroll as ts
from orkcraft.realm import chronicles
from orkcraft.sources import transcripts as tr
from orkcraft.sources.sessions import Session, sessions_for_orc

PRESETS = {"forge": {"title": "Forge", "icon": "⚒️", "orc": "Smith", "role": "kanban", "category": "core"}}


def test_record_describe_and_history(tmp_path: Path):
    scroll = ts.default_scroll(PRESETS)
    chronicles.record(tmp_path, scroll, "forge", "orc_recruited", orc="Coder")
    chronicles.record(tmp_path, scroll, "forge", "card_moved", id="T1001", to="done", by="Smith")
    chronicles.record(tmp_path, scroll, "forge", "orders_changed", orc="Coder", trigger="x" * 500 + "\nnext")
    events = chronicles.history(tmp_path, "forge")
    assert [e["type"] for e in events] == ["orders_changed", "card_moved", "orc_recruited"]
    assert chronicles.describe(events[1]) == ("🗂", "T1001 → done") and events[1]["by"] == "Smith"
    assert len(events[0]["trigger"]) == chronicles.FIELD_CHARS and "\n" not in events[0]["trigger"]
    assert chronicles.describe({"type": "rally_set"}) == ("🚩", "rally point ──► ? (?)")
    assert chronicles.describe({"type": "weird"})[0] == "·"
    with pytest.raises(ValueError):
        chronicles.record(tmp_path, scroll, "forge", "made_up")
    scroll.building("forge").chronicles = {"enabled": False}
    assert chronicles.record(tmp_path, scroll, "forge", "pinned") is None
    assert len(chronicles.history(tmp_path, "forge")) == 3


def _line(**kw) -> str:
    return json.dumps(kw) + "\n"


def test_transcript_run_steps_metrics_and_diff(tmp_path: Path):
    path = tmp_path / "abc.jsonl"
    usage = {"input_tokens": 10, "output_tokens": 5, "cache_read_input_tokens": 100, "cache_creation_input_tokens": 7}
    path.write_text(
        _line(type="summary", summary="x")
        + _line(type="user", timestamp="2026-09-29T10:00:00Z", message={"role": "user", "content": "Fix T1001 please"})
        + _line(type="assistant", timestamp="2026-09-29T10:00:05Z", message={
            "id": "m1", "role": "assistant", "usage": usage,
            "content": [{"type": "text", "text": "Looking."}]})
        + _line(type="assistant", timestamp="2026-09-29T10:00:06Z", message={   # same message id: usage once
            "id": "m1", "role": "assistant", "usage": usage,
            "content": [{"type": "tool_use", "id": "t1", "name": "Edit",
                         "input": {"file_path": "a.py", "old_string": "x = 1", "new_string": "x = 2"}}]})
        + _line(type="user", timestamp="2026-09-29T10:00:07Z", message={"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": "t1", "content": "ok"}]})
        + _line(type="assistant", timestamp="2026-09-29T10:01:00Z", message={
            "id": "m2", "role": "assistant", "usage": {"input_tokens": 1, "output_tokens": 2},
            "content": [{"type": "text", "text": "Done."}]})
        + "not json\n",
        encoding="utf-8",
    )
    run = tr.read_run(path)
    assert [s.kind for s in run.steps] == ["prompt", "text", "tool", "result", "text"]
    assert run.steps[0].title == "🗣 Fix T1001 please"
    assert run.steps[2].title == "🔧 Edit · a.py"
    assert run.diffs[0].diff == "--- a.py\n+++ a.py\n@@\n-x = 1\n+x = 2"
    assert (run.input_tokens, run.output_tokens, run.cache_read_tokens) == (11, 7, 100)
    assert run.tool_calls == 1 and run.duration_s == 60 and run.outcome == tr.DONE


def test_transcript_outcomes(tmp_path: Path):
    waiting = tmp_path / "w.jsonl"
    waiting.write_text(_line(type="assistant", message={"id": "m", "content": [
        {"type": "tool_use", "id": "t", "name": "Bash", "input": {"command": "rm -rf build"}}]}), encoding="utf-8")
    run = tr.read_run(waiting)
    assert run.outcome == tr.WAITING and run.steps[0].title == "🔧 Bash · rm -rf build"
    halted = tmp_path / "h.jsonl"
    halted.write_text(_line(type="user", message={"content": "[Request interrupted by user]"}), encoding="utf-8")
    assert tr.read_run(halted).outcome == tr.HALTED
    missing = tr.read_run(tmp_path / "nope.jsonl")
    assert missing.error and missing.steps == []


def test_sessions_of_a_garrison_orc():
    a, b = Session("claude", "1"), Session("claude", "2")
    a.orcs.add("forge/coder")
    assert sessions_for_orc([a, b], "forge/coder") == [a]
