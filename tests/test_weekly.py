"""🗓 The weekly self-audit (T1108 stage 9): a heavy model's report, ticked items applied as checkpoints."""
from __future__ import annotations

import datetime as dt
from pathlib import Path


from orkcraft.realm import weekly

ORDERS = ("Read every incoming event carefully, summarise it in plain words, list what changed, flag anything "
          "risky and end with a one-line verdict for the operator. Be thorough and careful.")


def _report(**extra) -> dict:
    return {"summary": "The hall's agent talks too much; the crag window is too wide.",
            "items": [
                {"title": "Shorter orders", "why": "same job", "change": "shrink", "building": "town_hall",
                 "target": "orc:seer", "prompt": "Summarise, flag risk, verdict."},
                {"title": "A day of bars", "why": "a week is noise", "change": "set_config", "building": "crag",
                 "key": "window", "value": "24h"},
                {"title": "Bad window", "why": "x", "change": "set_config", "building": "crag", "key": "window",
                 "value": "forever"},
                {"title": "Drop the loot road", "why": "nobody reads it", "change": "remove_road",
                 "building": "town_hall", "road": "nope"},
                {"title": "Think about mail", "why": "advice", "change": "note", "building": ""},
            ], **extra}


def test_a_broken_answer_is_an_error(tmp_path: Path):
    from types import SimpleNamespace as NS

    scroll = NS(buildings=[], building=lambda bid: None)
    assert "JSON" in weekly.run(tmp_path, scroll, {}, lambda p: ("no idea", None)).error
    assert "claude" in weekly.run(tmp_path, scroll, {}, lambda p: (_ for _ in ()).throw(RuntimeError("claude missing"))).error
    assert weekly.latest(tmp_path) is None
    weekly.mark_run(tmp_path, dt.datetime(2026, 10, 4, 5, 0))
    assert weekly.latest(tmp_path) is None and weekly.last_run(tmp_path).hour == 5   # last.json is not a report
