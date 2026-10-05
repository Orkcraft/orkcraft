"""🥁 War Drum in the GUI: the day by the hour and the week, the chosen meeting with its document,
and the calendar's settings. The work (loading, the clock, documents, adding) is the worker's
(core/workers/war_drum.py); a meeting's document opens in Lake on the page (openInLake)."""
from __future__ import annotations

import datetime as dt

from orkcraft.core.workers.war_drum import TICK_S
from orkcraft.gui.views import ActError, text
from orkcraft.realm import daybook

REFRESH_S = TICK_S             # the clock: what starts, what comes soon, the digest; a reload every 5 min
CARD = 3                       # meetings on the closed card


def refresh(w) -> None:
    w.tick()


def _hm(t) -> str:
    return t.strftime("%H:%M") if isinstance(t, dt.datetime) else ""


def _minutes(t) -> int:
    return t.hour * 60 + t.minute if isinstance(t, dt.datetime) else 0


def _event(w, e, docs: dict, now: dt.datetime, cur) -> dict:
    end = daybook._end(e)
    doc = docs.get(daybook.meet_id(e))
    return {
        "id": daybook.meet_id(e), "day": e.day.isoformat(), "title": e.summary, "location": e.location,
        "calendar": e.calendar, "all_day": e.all_day, "start": _hm(e.start), "end": _hm(end) if end and end.date() == e.day else "",
        "from_min": _minutes(e.start), "to_min": _minutes(end) if end and end.date() == e.day else 24 * 60,
        "when": daybook.when(e), "now": e is cur, "past": bool(end and end <= now),
        "doc": doc["path"] if doc else "",
    }


def card(w) -> dict:
    """Closed: the day's first three meetings still to come or under way."""
    now = w.clock()
    cur, _, left = daybook.now_and_next(w.day.events, now)
    docs = w.docs()
    ahead = [e for e in w.today() if not e.all_day and (daybook._end(e) or e.start) > now]
    return {"meetings": [{"at": _hm(e.start), "title": e.summary[:60], "now": e is cur,
                          "doc": daybook.meet_id(e) in docs} for e in ahead[:CARD]],
            "more": max(len(ahead) - CARD, 0), "error": bool(w.day.errors)}


def detail(w) -> dict:
    now = w.clock()
    cur, nxt, left = daybook.now_and_next(w.day.events, now)
    docs = w.docs()
    days = []
    for d in range(daybook.WEEK_DAYS):
        day = now.date() + dt.timedelta(days=d)
        days.append({"date": day.isoformat(), "label": "Today" if d == 0 else f"{day:%a %d %b}",
                     "events": [_event(w, e, docs, now, cur) for e in w.day.events if e.day == day]})
    return {
        "date": f"{now:%A %d %B}", "now_min": now.hour * 60 + now.minute,
        "current": daybook.meet_id(cur) if cur else "", "next": daybook.meet_id(nxt) if nxt else "", "left": left,
        "errors": list(w.day.errors), "days": days,
        "settings": {"ics": w.configured, "day_starts": str(w.config.get("day_starts") or ""),
                     "lead": str(w.config.get("lead") or ""), "writes_to": w.writable.name},
    }


def _meeting(w, args: dict):
    e = w.event(text(args, "id", 64))
    if e is None:
        raise ActError("That meeting is not in the calendar any more")
    return e


def _prepare(w, args: dict) -> str:
    """📄 Prepare doc: `meeting soon` for the chosen meeting (else the one on now or next) at once."""
    e = _meeting(w, args) if args.get("id") else None
    problem = w.prepare(e)
    if problem:
        raise ActError(problem)
    return daybook.line(e or w.selected())


def _doc(w, args: dict) -> dict:
    """A meeting's document: sent along a road that carries it, and handed to the page for Lake."""
    doc = w.open_doc(_meeting(w, args))
    if doc is None:
        raise ActError("This meeting has no document yet: Prepare doc asks for one")
    return doc


def _add(w, args: dict) -> str:
    try:
        minutes = 30 if args.get("minutes") in (None, "") else int(args["minutes"])
    except (TypeError, ValueError):
        raise ActError("Minutes are a number") from None
    if not 5 <= minutes <= 24 * 60:
        raise ActError("An event lasts 5 minutes to a day")
    try:
        start = w.add(text(args, "title", 300), text(args, "when", 100), minutes)
    except (ValueError, OSError) as e:
        raise ActError(str(e)) from None
    return f"{start:%a %d %H:%M}"


def _settings(w, args: dict) -> bool:
    """The calendar (.ics file or URL), when the morning digest goes out, how long before a meeting
    its document is asked for."""
    changes = {k: text(args, k, 2000).strip() for k in ("ics", "day_starts", "lead") if k in args}
    if "day_starts" in changes and changes["day_starts"]:
        try:
            dt.datetime.strptime(changes["day_starts"], "%H:%M")
        except ValueError:
            raise ActError("The day starts at HH:MM, e.g. 08:00") from None
    lead = changes.get("lead", "").lower()
    if lead and (not daybook._LEAD.findall(lead) or daybook._LEAD.sub("", lead).strip()):
        raise ActError("Before a meeting: e.g. 2h, 1d, 1h30m")
    if not changes:
        return False
    if not w.save_config(changes):
        raise ActError("Not saved")
    w.refresh()
    return True


ACTS = {"prepare": _prepare, "doc": _doc, "add": _add, "settings": _settings}
