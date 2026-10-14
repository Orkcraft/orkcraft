"""👀 "Since your last look" (docs/design/audience.md §2a): what greets the person when they come back, measured from
their last look, not the last day.

    look, ended = last_look.beat(last_look.load(root), now)   # the page is in front of the person: a beat
    last_look.save(root, look)                                # .orkcraft/usage/last_look.json, this machine only
    last_look.digest(since, now, rows, questions, problems, working, used_then, used_now, seen)

A **look** is the GUI in front of the person (focused and visible) for `LOOK_MIN_S`; while it stays there the page
beats every `BEAT_S`. Beats further apart than `GAP_S` mean the person was away: a new look begins, the one before
ended at its last beat, and when it ended `AWAY_S` ago or more the town greets them with the digest since then.

The digest, in this order, wins first: **what was built** (results through the Review gate, launched by the
Publisher, tasks done, carts that moved: the local event log, realm/event_log.py), **the questions** (each with its
answers), **the problems** (each with what it waits for), **what it cost** (the window's % used while away). Each
list shows at most `SHOWN` and says how many more: never an endless list, never a streak, never a dot to clear.
Honest when nothing changed: "Nothing new since 12:40; the orks are on «#42»."

Pure module: no face, no core. The service (core/last_look.py) gathers, the GUI draws (gui/static/js/lastlook.js).
"""
from __future__ import annotations

import datetime as dt
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from orkcraft.realm import event_log, lexicon
from orkcraft.realm.status import quoted

PATH = Path(".orkcraft") / "usage" / "last_look.json"
LOOK_MIN_S = 5          # in front this long before it counts as a look (js/lastlook.js keeps the same)
BEAT_S = 30             # the page beats this often while in front (js/lastlook.js keeps the same)
GAP_S = 120             # beats further apart: the person was away, a new look began
AWAY_S = 10 * 60        # away at least this long: the town greets them
SHOWN = 3               # at most this many of each list, then "and N more"

# What a result built is (event_log.BUILT `kind`), from the event its building sent (core/delivery.py).
BUILT_BY_EVENT = {"catapult.sent": "launched", "loot.passed": "passed", "pool.done": "done"}
KINDS = ("launched", "passed", "done")       # wins first: the launch is the cart's climax (camp-story.md §2)


@dataclass
class Look:
    start: str                                       # ISO, when it began
    end: str                                         # ISO, its last beat
    used: dict[str, int] = field(default_factory=dict)   # "claude · 5h session" → % of the window used then
    seen: list[str] = field(default_factory=list)        # the questions and problems in front of the person then


def iso(at: dt.datetime) -> str:
    return at.astimezone().isoformat(timespec="seconds")


def _parse(text: str) -> dt.datetime | None:
    try:
        at = dt.datetime.fromisoformat(text)
    except (TypeError, ValueError):
        return None
    return at if at.tzinfo else at.astimezone()


def path(root: Path) -> Path:
    return Path(root) / PATH


def load(root: Path | None) -> Look | None:
    if root is None:
        return None
    try:
        data = json.loads(path(root).read_text(encoding="utf-8"))
        look = Look(str(data["start"]), str(data["end"]),
                    {str(k): int(v) for k, v in (data.get("used") or {}).items()},
                    [str(x) for x in data.get("seen") or []])
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return None
    return look if _parse(look.start) and _parse(look.end) else None


def save(root: Path | None, look: Look) -> bool:
    if root is None:
        return False
    target = path(root)
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(asdict(look), ensure_ascii=False), encoding="utf-8")
    except OSError:
        return False
    return True


def beat(last: Look | None, now: dt.datetime) -> tuple[Look, Look | None]:
    """(the look now, the look that ended): the same look goes on while beats come within `GAP_S`; past that a new
    one begins and the one before is returned, ended at its last beat."""
    end = _parse(last.end) if last is not None else None
    if last is not None and end is not None and (now - end).total_seconds() <= GAP_S:
        return Look(last.start, iso(now), dict(last.used), list(last.seen)), None
    return Look(iso(now), iso(now)), last


def away_s(look: Look, now: dt.datetime) -> float:
    end = _parse(look.end)
    return (now - end).total_seconds() if end is not None else 0.0


def seconds(look: Look) -> int:
    start, end = _parse(look.start), _parse(look.end)
    return max(round((end - start).total_seconds()), 0) if start and end else 0


# -- the words -------------------------------------------------------------------------------------------

def _many(n: int, one: str, many: str = "") -> str:
    return f"{n} {one if n == 1 else (many or one + 's')}"


def at_label(since: dt.datetime, now: dt.datetime) -> str:
    """"12:40" today, "yesterday 18:10", "Oct 12, 18:10" before."""
    since, now = since.astimezone(), now.astimezone()
    if since.date() == now.date():
        return f"{since:%H:%M}"
    if since.date() == now.date() - dt.timedelta(days=1):
        return f"yesterday {since:%H:%M}"
    return f"{since:%b} {since.day}, {since:%H:%M}"


def away_label(s: float) -> str:
    """"40 min", "5 h 40 min", "14 h", "2 days": how long the person was away."""
    if s < 3600:
        return _many(max(round(s / 60), 1), "min", "min")
    if s < 10 * 3600:
        h, m = divmod(round(s / 60), 60)
        return f"{h} h" + (f" {m} min" if m else "")
    if s < 48 * 3600:
        return f"{round(s / 3600)} h"
    return _many(round(s / 86400), "day")


def _built_words(kind: str, n: int) -> str:
    if kind == "launched":
        return f"{n} launched by the {lexicon.term('catapult')}"
    if kind == "passed":
        return f"{n} through the {lexicon.term('loot_vault')}"
    return _many(n, "task") + " done"


def _short(kind: str, n: int) -> str:
    return {"launched": f"{n} launched", "passed": f"{n} through the {lexicon.term('loot_vault')}"}.get(
        kind, _many(n, "task") + " done")


def _item_line(kind: str) -> str:
    return {"launched": "Launched", "passed": "Passed", "done": "Done"}[kind]


def _capped(items: list[dict]) -> dict[str, Any]:
    return {"items": items[:SHOWN], "more": max(len(items) - SHOWN, 0)}


def cost(used_then: dict[str, int], used_now: dict[str, int]) -> list[dict[str, Any]]:
    """Each window that moved while the person was away: how much of it, and where it stands now."""
    out = []
    for key, now in used_now.items():
        then = used_then.get(key)
        if then is None:
            continue
        if now < then:                          # the window started again while they were away
            out.append({"key": key, "used": now, "now": now, "line": f"{key}: the window started again; {now} % used since"})
        elif now > then:
            out.append({"key": key, "used": now - then, "now": now,
                        "line": f"{key}: {now - then} % used while you were away (now {now} %)"})
    return sorted(out, key=lambda c: -c["used"])


def _working(working: list[str]) -> str:
    if not working:
        return "the orks rest"
    more = f" and {_many(len(working) - 1, 'more', 'more')}" if len(working) > 1 else ""
    return f"the orks are on {quoted(working[0])}{more}"


def digest(since: dt.datetime, now: dt.datetime, rows: list[dict], questions: list[dict], problems: list[dict],
           working: list[str], used_then: dict[str, int] | None = None, used_now: dict[str, int] | None = None,
           seen: list[str] | set[str] = ()) -> dict[str, Any]:
    """What greets the person: since when, what was built, the questions, the problems, the cost, and one line
    that says it all (or, honestly, that nothing changed). `rows`: the event log's lines since then; `questions`
    and `problems`: what stands now, each with an `id` (marked `new` when it was not in front of them before)."""
    seen = set(seen)
    built = [r for r in rows if r.get("event") == event_log.BUILT and r.get("kind") in KINDS]
    built.sort(key=lambda r: KINDS.index(r["kind"]))
    moved = sum(1 for r in rows if r.get("event") == event_log.CART_MOVED)
    by_kind = {k: sum(1 for r in built if r["kind"] == k) for k in KINDS}
    items = [{"kind": r["kind"], "title": str(r.get("title") or r.get("ref") or ""), "building": str(r.get("building") or ""),
              "line": f"{_item_line(r['kind'])}: {quoted(str(r.get('title') or r.get('ref') or 'a cart'))}"} for r in built]
    summary = [_built_words(k, n) for k, n in by_kind.items() if n]
    if moved:
        summary.append(_many(moved, "cart") + " moved")
    questions = [{**q, "new": q["id"] not in seen} for q in questions]
    problems = [{**p, "new": p["id"] not in seen} for p in problems]
    new_q = sum(1 for q in questions if q["new"])
    new_p = sum(1 for p in problems if p["new"])
    spent = cost(used_then or {}, used_now or {})
    at = at_label(since, now)
    empty = not built and not moved and not new_q and not new_p
    if empty:
        still = [_many(len(questions), "question") + (" still waits" if len(questions) == 1 else " still wait")
                 if questions else "",
                 _many(len(problems), "problem") + " still open" if problems else ""]
        headline = f"Nothing new since {at}; " + "; ".join([_working(working)] + [s for s in still if s]) + "."
    else:
        parts = [_short(k, n) for k, n in by_kind.items() if n]
        if moved:
            parts.append(_many(moved, "cart") + " moved")
        if new_q:
            parts.append(_many(new_q, "question"))
        if new_p:
            parts.append(_many(new_p, "problem"))
        headline = f"Since {at}: " + ", ".join(parts) + "."
    return {"since": iso(since), "at": at, "away": away_label((now - since).total_seconds()), "empty": empty,
            "headline": headline, "working": _working(working),
            "built": {**_capped(items), "summary": " · ".join(summary), "moved": moved},
            "questions": _capped(questions), "problems": _capped(problems),
            "cost": spent, "cost_known": bool(set(used_then or {}) & set(used_now or {}))}
