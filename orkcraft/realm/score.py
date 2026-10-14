"""The game's score at its smallest (docs/design/the-score.md §2, decisions-2026-10.md §13.5): the wood (tokens) and the
money spent **per accepted result** — a cart passed at the Review gate, a task done — this week against the week
before, and the quality that guards it: the 👎 and the send-backs per result, so a cheaper week with worse work never
reads as a win.

    score.town(root)        {"results", "tokens", "cost", "trend", "dislikes", "reworks", "guard", "lean", …}
    score.lean_weeks(root)  [True, False, …]   the last five weeks, newest first: was each lean against the one before

Read from what the town already writes on this machine: the local event log's `result_built` lines (each carries
the tokens and spend its cart's trail recorded when it landed, realm/event_log.py) and the feedback log's incidents
(realm/feedback.py: a 👎, a cart sent back). Nothing is estimated: a week with no recorded spend has None, and the
page says "not recorded". No face here.
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Any

from orkcraft.realm import event_log, feedback

ACCEPTED = ("passed", "done")                  # a Review gate's pass, a task done; a launch is not a judgement
REWORK = ("loot.rework", "loot.needs_you")     # a result sent back
WEEK = dt.timedelta(days=7)
STEADY = 0.05                                   # the guard holds while 👎 / reworks per result rise less than this


def _when(s: str) -> dt.datetime | None:
    try:
        t = dt.datetime.fromisoformat(s)
    except (TypeError, ValueError):
        return None
    return t if t.tzinfo else t.astimezone()


def _mean(xs: list[float]) -> float | None:
    return sum(xs) / len(xs) if xs else None


def week(results: list[dict], incidents: list[dict]) -> dict[str, Any]:
    """One week: how many results, the mean tokens and spend of those that recorded them, 👎 and reworks per result."""
    n = len(results)
    toks = [float(r["tokens"]) for r in results if isinstance(r.get("tokens"), (int, float))]
    costs = [float(r["cost"]) for r in results if isinstance(r.get("cost"), (int, float))]
    bad = sum(1 for i in incidents if i.get("source", feedback.EXPLICIT) == feedback.EXPLICIT)
    back = sum(1 for i in incidents if i.get("source") in REWORK)
    return {"results": n, "tokens": _mean(toks), "cost": _mean(costs), "recorded": len(toks),
            "dislikes": bad / n if n else None, "reworks": back / n if n else None}


def compare(now: dict, before: dict) -> dict[str, Any]:
    """This week against the last: the trend of the wood per result (−0.12: 12 % less), and the guard — "steady" when
    neither 👎 nor reworks per result rose, "worse" when one did; a lean week is less wood with the guard steady."""
    trend = None
    if now["tokens"] is not None and before["tokens"]:
        trend = (now["tokens"] - before["tokens"]) / before["tokens"]
    guard = None
    if now["results"] and before["results"]:
        up = any((now[k] or 0) - (before[k] or 0) > STEADY for k in ("dislikes", "reworks"))
        guard = "worse" if up else "steady"
    return {"trend": trend, "guard": guard, "lean": trend is not None and trend < 0 and guard == "steady"}


def _weeks(root: Path | None, now: dt.datetime, n: int, rows: list[dict] | None = None) -> list[dict]:
    """The last `n` weeks ending now, newest first."""
    since = (now - n * WEEK).date().isoformat()
    lines = rows if rows is not None else event_log.read(Path(root), since=since)
    rows = [r for r in lines if r.get("event") == event_log.BUILT and r.get("kind") in ACCEPTED]
    incs = [vars(i) for i in feedback.incidents(Path(root), limit=2000)] if root is not None else []

    def within(t: dt.datetime | None, a: dt.datetime, b: dt.datetime) -> bool:
        return t is not None and a < t <= b

    out = []
    for k in range(n):
        a, b = now - (k + 1) * WEEK, now - k * WEEK
        out.append(week([r for r in rows if within(_when(r.get("at")), a, b)],
                        [i for i in incs if within(_when(i.get("ts")), a, b)]))
    return out


def town(root: Path | None, now: dt.datetime | None = None, rows: list[dict] | None = None) -> dict[str, Any]:
    """The town's score now: this week's numbers, the last week's, the trend and the guard (all None-safe). `rows`:
    result lines given instead of the log's (the demo's, which writes none)."""
    now = now or dt.datetime.now().astimezone()
    empty = {"results": 0, "tokens": None, "cost": None, "recorded": 0, "dislikes": None, "reworks": None}
    if root is None and rows is None:
        return {**empty, "before": dict(empty), "trend": None, "guard": None, "lean": False}
    this, last = _weeks(root, now, 2, rows)
    return {**this, "before": last, **compare(this, last)}


def lean_weeks(root: Path | None, now: dt.datetime | None = None, n: int = 5) -> list[dict]:
    """The last `n` weeks, newest first, each compared with the week before it: {"lean", "trend", "guard"}. A lean
    month (growth.md, v3-prompts.md §13) is four lean weeks in five."""
    now = now or dt.datetime.now().astimezone()
    if root is None:
        return [{"lean": False, "trend": None, "guard": None} for _ in range(n)]
    ws = _weeks(root, now, n + 1)
    return [compare(ws[k], ws[k + 1]) for k in range(n)]
