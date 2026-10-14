"""📒 The local event log (docs/design/dogfood-logs.md §3): every product event, exact, on this machine only.

    event_log.record(root, event_log.ASKED, building="pool", ork="Grunt", task="t1", text="Which port?")
    event_log.read(root, since="2026-10-14")       # the lines, oldest first
    event_log.counts(root, since="2026-10-14")     # {event: how many}
    event_log.summary(root, since=…)               # the counts the owner reads after a week (`orkcraft usage local`)

It sits beside the anonymous usage stats (core/usage.py) and is not them: whatever the person said to sharing,
these lines are written to `.orkcraft/usage/events.jsonl` in the town's folder and never leave the machine — no
proxy, no batch, no network. They may hold the town's own words (a question an ork asked, its options), because
only the person who owns the town reads them, by hand or in the analytics zip (realm/analytics.py).

A closed list of events (`EVENTS`); an unknown one is not written. A field is kept as it is when it is plain data
(a string, a number, a bool, a list of strings); a string is cut at `TEXT_MAX`. Writing never troubles the town:
a disk that refuses is ignored. Nothing is written in the demo (the caller passes no root).

No face here: a service records, a face reads (decisions §8: these counts size the way to ask after a week).
"""
from __future__ import annotations

import datetime as dt
import json
import threading
from collections import Counter
from pathlib import Path
from typing import Any

PATH = Path(".orkcraft") / "usage" / "events.jsonl"
TEXT_MAX = 2_000

# The way to ask (ork-console.md §4, §20): what an ork asked, marked, was answered, and where a run stopped.
ASKED = "question_asked"          # building, ork, task, harness, text, options, via ("block" | "line")
ASSUMED = "assumption_marked"     # building, ork, task, harness, text
ANSWERED = "question_answered"    # building, ork, task, who ("person" | "steward" | "timer"), waited_s, text
STOPPED = "run_stopped_on_question"   # building, ork, task, harness: the run ended to wait for the person
# A wait the person skipped (ork-console.md §19): which wait, and how long it had lasted.
WAIT_SKIPPED = "wait_skipped"     # building, task, wait, waited_s
# Mission 1 (first-mission.md): a quest started, done or skipped.
QUEST_STARTED = "quest_started"   # quest
QUEST_DONE = "quest_done"         # quest, seconds
QUEST_SKIPPED = "quest_skipped"   # quest
# "Since your last look" (audience.md §2a): what the town made while the person was away, and their looks.
BUILT = "result_built"            # building, kind ("passed" | "launched" | "done"), title, ref
CART_MOVED = "cart_moved"         # source, target, title: a cart delivered along a road
LOOKED = "look"                   # started, seconds: the GUI in front of the person (looks a day, their length)

EVENTS = (ASKED, ASSUMED, ANSWERED, STOPPED, WAIT_SKIPPED, QUEST_STARTED, QUEST_DONE, QUEST_SKIPPED,
          BUILT, CART_MOVED, LOOKED)

_LOCK = threading.Lock()


def path(root: Path) -> Path:
    return Path(root) / PATH


def _plain(value: Any) -> Any:
    """A field as it is kept: plain data only, strings cut; None for anything else (it is dropped)."""
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, (int, float)):
        return round(value, 3) if isinstance(value, float) else value
    if isinstance(value, str):
        return value[:TEXT_MAX]
    if isinstance(value, (list, tuple)) and all(isinstance(v, str) for v in value):
        return [v[:TEXT_MAX] for v in value][:50]
    return None


def line(event: str, at: dt.datetime | None = None, **fields: Any) -> dict | None:
    """The line `record` writes; None for an event not in `EVENTS`."""
    if event not in EVENTS:
        return None
    at = at or dt.datetime.now().astimezone()
    row: dict[str, Any] = {"at": at.isoformat(timespec="seconds"), "event": event}
    for k, v in fields.items():
        kept = _plain(v)
        if kept is not None or v is None:
            row[k] = kept
    return row


def record(root: Path | None, event: str, **fields: Any) -> bool:
    """One event, appended to the town's local log. False when nothing was written (no root, an unknown event,
    a disk that refused)."""
    row = line(event, **fields)
    if root is None or row is None:
        return False
    target = path(root)
    try:
        with _LOCK:
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("a", encoding="utf-8") as f:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except OSError:
        return False
    return True


def read(root: Path, since: str = "", until: str = "") -> list[dict]:
    """The lines, oldest first; `since` / `until`: ISO days or times (the line's `at` compared as text), inclusive
    of `since`'s day, exclusive of `until`'s."""
    try:
        text = path(root).read_text(encoding="utf-8")
    except OSError:
        return []
    rows = []
    for raw in text.splitlines():
        try:
            row = json.loads(raw)
        except ValueError:
            continue
        if not isinstance(row, dict) or row.get("event") not in EVENTS:
            continue
        at = str(row.get("at") or "")
        if (since and at < since) or (until and at >= until):
            continue
        rows.append(row)
    return rows


def counts(root: Path, since: str = "", until: str = "") -> dict[str, int]:
    """How many of each event, every event named (0 when none)."""
    found = Counter(r["event"] for r in read(root, since, until))
    return {e: found.get(e, 0) for e in EVENTS}


def summary(root: Path, since: str = "", until: str = "") -> dict[str, Any]:
    """What the owner reads after a week (decisions §8): the counts, and how long the person's answers took."""
    rows = read(root, since, until)
    c = Counter(r["event"] for r in rows)
    waits = sorted(float(r["waited_s"]) for r in rows if r["event"] == ANSWERED and r.get("who") == "person"
                   and isinstance(r.get("waited_s"), (int, float)))
    median = waits[len(waits) // 2] if waits else None
    runs = {(r.get("building"), r.get("task")) for r in rows if r["event"] in (ASKED, ASSUMED)}
    return {"counts": {e: c.get(e, 0) for e in EVENTS}, "answer_wait_median_s": median,
            "tasks_with_questions_or_assumptions": len(runs), "first": rows[0]["at"] if rows else "",
            "last": rows[-1]["at"] if rows else ""}
