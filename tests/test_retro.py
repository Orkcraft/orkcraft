"""🗓 The Town retro's survey: a few results of the week to rate, when nothing was rated
(docs/design/retros-and-goals.md §4)."""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from types import SimpleNamespace as NS


from orkcraft.realm import evolution, feedback, metrics, retro, workshop


def _scroll(*ids: str, goals: dict | None = None):
    bs = [NS(id=i, demolished=False, goal=(goals or {}).get(i, "balance")) for i in ids]
    return NS(buildings=bs, building=lambda bid: next((b for b in bs if b.id == bid), None))


def _run(root: Path, bid: str, value: str, code: int = 0, ago: dt.timedelta = dt.timedelta(hours=2)) -> None:
    at = (dt.datetime.now() - ago).isoformat(timespec="seconds")
    workshop.log(root / ".orkcraft/workshop" / bid, workshop.Run(at, "e", "s", value, code, out=f"out of {value}"))


def test_samples_read_every_kind_of_run_log(tmp_path: Path):
    _run(tmp_path, "w", "red green")
    _run(tmp_path, "w", "old", ago=dt.timedelta(days=9))
    jobs = tmp_path / ".orkcraft/mill/w/runs.jsonl"
    jobs.parent.mkdir(parents=True)
    jobs.write_text(json.dumps({"id": "1", "title": "t", "harness": "claude", "input": "x" * 400,
                                "ended": dt.datetime.now().isoformat(timespec="seconds"),
                                "outcome": "error", "error": "boom"}) + "\n")
    since = (dt.datetime.now() - dt.timedelta(days=7)).isoformat(timespec="seconds")
    got = retro.samples(tmp_path, "w", since)
    assert [s.outcome for s in got] == ["error", "done"]
    assert len(got[0].input) == retro.CUT and got[0].input.endswith("…") and got[0].output == "boom"
    assert got[1].input == "red green" and got[1].output == "out of red green"
    feedback.record_output(tmp_path, "only_last", "mill.done", "a brief")
    assert [s.output for s in retro.samples(tmp_path, "only_last", since)] == ["a brief"]


def test_the_survey_is_needed_only_without_ratings_this_week(tmp_path: Path):
    assert retro.needed(tmp_path)
    feedback.record_output(tmp_path, "a", "mill.done", "fine")
    feedback.like(tmp_path, "a")
    assert not retro.needed(tmp_path)
    assert retro.needed(tmp_path, dt.datetime.now() + dt.timedelta(days=8))


def test_pick_the_most_useful_one_per_building_at_most_four(tmp_path: Path):
    for bid in ("changed", "gem", "broken", "heavy", "quiet", "extra"):
        _run(tmp_path, bid, f"{bid} in")
    _run(tmp_path, "broken", "bad in", code=1, ago=dt.timedelta(hours=5))
    evolution.record(tmp_path, evolution.Change("changed", "shrink", "daily", "shorter"))
    metrics.record_run(tmp_path, "heavy", "done", 0.1, 9000)
    metrics.record_run(tmp_path, "quiet", "done", 0.1, 10)
    scroll = _scroll("quiet", "heavy", "broken", "gem", "changed", "extra", goals={"gem": "quality"})
    got = retro.pick(tmp_path, scroll)
    assert [(s.building, s.why) for s in got] == [
        ("changed", "changed this week"), ("gem", "💎 quality, not rated this week"),
        ("broken", "a run went wrong"), ("heavy", "eats the most of the camp")]
    assert got[2].outcome == "failed" and got[2].input == "bad in"
    assert len(retro.pick(tmp_path, scroll, limit=2)) == 2


def test_a_survey_answer_rates_the_very_result_it_showed(tmp_path: Path):
    s = retro.Sample("a", "2026-10-01T09:00:00", "in", "the old brief")
    feedback.record_output(tmp_path, "a", "mill.done", "today's brief")
    assert feedback.like(tmp_path, "a", s.as_output())["value"] == "the old brief"
    inc = feedback.dislike(tmp_path, None, "a", "logic", "survey", s.as_output())
    assert inc.output == "the old brief" and feedback.scores(tmp_path)["a"] == {
        "likes": 1, "dislikes": 1, "penalty": 1.0, "liked": 1.0, "disliked": 1.0, "by": {"explicit": 0.0}}
