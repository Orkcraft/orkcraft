"""The score per accepted result (realm/score.py, docs/design/the-score.md §2): wood and spend per result this week
against the last, the guard of 👎 and send-backs per result, and a lean week; from the local logs only, nothing
guessed. A result's spend is recorded when it lands (core/last_look.py)."""
from __future__ import annotations

import datetime as dt
import json
from types import SimpleNamespace

from orkcraft.core import last_look
from orkcraft.realm import event_log, feedback, pipes, score

NOW = dt.datetime(2026, 10, 14, 20, 0).astimezone()


def _built(root, days_ago, tokens=None, cost=None, kind="passed"):
    row = event_log.line(event_log.BUILT, at=NOW - dt.timedelta(days=days_ago), building="gate", kind=kind,
                         title="x", ref="1", tokens=tokens, cost=cost)
    p = event_log.path(root)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")


def _incident(root, days_ago, source=feedback.EXPLICIT):
    d = root / ".orkcraft" / "feedback"
    d.mkdir(parents=True, exist_ok=True)
    ts = (NOW - dt.timedelta(days=days_ago)).isoformat(timespec="seconds")
    with (d / "incidents.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": ts, "building": "gate", "kind": "logic", "note": "", "output": "", "source": source}) + "\n")


def test_a_lean_week_is_less_wood_per_result_with_the_guard_steady(tmp_path):
    for d in (8, 9, 10, 11):
        _built(tmp_path, d, tokens=20000, cost=0.4)
    for d in (1, 2, 3, 4):
        _built(tmp_path, d, tokens=15000, cost=0.3)
    _built(tmp_path, 2, kind="launched", tokens=999999)            # a launch is not a judgement
    s = score.town(tmp_path, now=NOW)
    assert s["results"] == 4 and s["tokens"] == 15000 and abs(s["cost"] - 0.3) < 1e-9
    assert abs(s["trend"] + 0.25) < 1e-9 and s["guard"] == "steady" and s["lean"] is True
    assert s["before"]["tokens"] == 20000


def test_a_cheaper_week_with_more_thumbs_down_is_not_a_win(tmp_path):
    for d in (8, 9):
        _built(tmp_path, d, tokens=20000)
    for d in (1, 2):
        _built(tmp_path, d, tokens=10000)
    _incident(tmp_path, 1)
    _incident(tmp_path, 2, source="loot.rework")
    _incident(tmp_path, 20)                                        # too old to count
    s = score.town(tmp_path, now=NOW)
    assert s["trend"] == -0.5 and s["dislikes"] == 0.5 and s["reworks"] == 0.5
    assert s["guard"] == "worse" and s["lean"] is False


def test_nothing_recorded_is_none_never_zero(tmp_path):
    _built(tmp_path, 1)                                            # an older line: no tokens kept
    s = score.town(tmp_path, now=NOW)
    assert s["results"] == 1 and s["tokens"] is None and s["cost"] is None and s["trend"] is None
    assert score.town(None)["results"] == 0


def test_a_result_keeps_the_spend_its_trail_recorded(tmp_path):
    town = SimpleNamespace(repo_root=tmp_path, demo=False)
    trail = (pipes.Hop("pool", tokens=12000, cost=0.2), pipes.Hop("gate"))
    last_look.built(town, "gate", "loot.passed", "Fix the login", "42", trail)
    row = [r for r in event_log.read(tmp_path) if r["event"] == event_log.BUILT][-1]
    assert (row["tokens"], row["cost"], row["kind"]) == (12000, 0.2, "passed")
