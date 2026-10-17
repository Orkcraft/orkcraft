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
ASKED = "question_asked"          # building, ork, task, harness, text, options, via ("block" | "line"), at_work
ASSUMED = "assumption_marked"     # building, ork, task, harness, text, at_work (the person's working hours held)
ANSWERED = "question_answered"    # building, ork, task, who ("person" | "steward" | "timer"), waited_s, text
STOPPED = "run_stopped_on_question"   # building, ork, task, harness: the run ended to wait for the person
# A wait the person skipped (ork-console.md §19): which wait, and how long it had lasted.
WAIT_SKIPPED = "wait_skipped"     # building, task, wait, waited_s
# Quiet working hours (audience.md §2a): a question's toast or push held for "since your last look".
HELD_AT_WORK = "question_held_at_work"   # how ("toast" | "push"), title
# Leaving the camp (audience.md §2a): "I'm off", and back (by the person, at evening, or the work done).
CAMP_LEFT = "camp_left"           # carts, first, cap_pct, until, on_power
CAMP_BACK = "camp_back"           # why ("person" | "evening"), minutes, window_pct, capped, carts_left
# Mission 1 (first-mission.md): a quest started, done or skipped.
QUEST_STARTED = "quest_started"   # quest
QUEST_DONE = "quest_done"         # quest, seconds
QUEST_SKIPPED = "quest_skipped"   # quest
# "Since your last look" (audience.md §2a): what the town made while the person was away, and their looks.
BUILT = "result_built"            # building, kind ("passed" | "launched" | "done"), title, ref, tokens, cost (None: unrecorded)
CART_MOVED = "cart_moved"         # source, target, title: a cart delivered along a road
LOOKED = "look"                   # started, seconds: the GUI in front of the person (looks a day, their length)

# The board (docs/specs/33-v1-shell.md §9): every action of the v1 shell, for the day's analysis. `device` is "desktop" or "phone".
IDEA_ADDED = "idea_added"         # idea, track, chars, now (the keeper reads it at once), device
IDEA_SAID = "idea_said"           # idea, section, chars, text, device (the person's turn to the Taskmaster)
KEEPER_STATE = "keeper_state"     # idea, state, was, seconds in the previous state
PLAN_MADE = "plan_made"           # idea, tasks, todos, usd_low, usd_high
PLAN_PASSED = "plan_passed"       # idea, tasks, device, seconds from plan_made
TODO_DONE = "todo_done"           # idea, todo, kind, device, seconds since the plan (a secret's value never)
TASK_STATE = "task_state"         # idea, task, state, was, round, tier, role, seconds in the previous state, tokens, cost
RESULT_READY = "result_ready"     # idea, task, round, passed, failed, files, added, removed, cost, role
RESULT_DECIDED = "result_decided"  # idea, task, round, decision, why, into, pushed, conflict, device, seconds from result_ready
TASK_STOPPED = "task_stopped"     # idea, task, device
STOP_ALL = "stop_all"             # count, device
INTO_CHANGED = "into_changed"     # branch, push, device
OPENED = "opened"                 # what (idea · plan · todo · task · result · tab), ref, device
LIMITS_READ = "limits_read"       # provider, left, window
# Round 2 (docs/specs/34-v1-round-2.md §4): goals by dialog, agents by task type.
GOAL_SAVED = "goal_saved"         # goal, new, metrics (their names), links, priority, device
GOAL_READ = "goal_read"           # goal, state (asks · ready · raw: not read), seconds the keeper took
ROLE_SAVED = "role_saved"         # role, model, max_parallel, new, device
ROLE_DROPPED = "role_dropped"     # role, kinds (the task types sent back to Grunt), device
KIND_SET = "kind_set"             # kind, role, device

EVENTS = (ASKED, ASSUMED, ANSWERED, STOPPED, WAIT_SKIPPED, HELD_AT_WORK, CAMP_LEFT, CAMP_BACK, QUEST_STARTED,
          QUEST_DONE, QUEST_SKIPPED, BUILT, CART_MOVED, LOOKED, IDEA_ADDED, IDEA_SAID, KEEPER_STATE, PLAN_MADE, PLAN_PASSED,
          TODO_DONE, TASK_STATE, RESULT_READY, RESULT_DECIDED, TASK_STOPPED, STOP_ALL, INTO_CHANGED, OPENED, LIMITS_READ, GOAL_SAVED, GOAL_READ, ROLE_SAVED,
          ROLE_DROPPED, KIND_SET)

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
