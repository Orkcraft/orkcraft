"""🥁 War Drum in the GUI: the day by the hour and the week, the chosen meeting with its document,
and the calendar's settings — with the town's scheduled runs and ≈ when its limits are reached laid
over the meetings (realm/drumbeat.py). The work (loading, the clock, documents, adding) is the worker's
(core/workers/war_drum.py); a meeting's document opens in Lake on the page (openInLake)."""
from __future__ import annotations

import datetime as dt

from orkcraft.core.workers.war_drum import TICK_S
from orkcraft.gui.views import ActError, text
from orkcraft.realm import catalog, daybook, drumbeat

REFRESH_S = TICK_S             # the clock: what starts, what comes soon, the digest; a reload every 5 min
CARD = 6                       # beats (meetings, scheduled runs, limits) on the closed card
STRIP_H = 12                   # hours the closed card's strip spans from now


def refresh(w) -> None:
    w.tick()


def _hm(t) -> str:
    return t.strftime("%H:%M") if isinstance(t, dt.datetime) else ""


def _minutes(t) -> int:
    return t.hour * 60 + t.minute if isinstance(t, dt.datetime) else 0


def _from_wiki(w) -> dict[str, dict]:
    """What the town's Wikis keep for this calendar's meetings (docs/design/wiki-librarian.md §6), by meet id:
    the items still to discuss and the pages their notes link, summed over the Wikis that read it."""
    out: dict[str, dict] = {}
    for bid, spec in w.town.custom_specs.items():
        if catalog.migrate(spec).get("type") != "scrolls":
            continue
        kept = getattr(w.town.worker(bid), "kept_for", None)
        for mid, k in (kept(w.building_id) if kept else {}).items():
            got = out.setdefault(mid, {"discuss": 0, "pages": 0})
            got["discuss"] += k["discuss"]
            got["pages"] += k["pages"]
    return out


def _wiki_line(kept: dict, mid: str, doc: bool) -> dict | None:
    """A meeting's line from the Wiki: how many items to discuss; the pages once its brief is back."""
    k = kept.get(mid)
    return {"discuss": k["discuss"], "pages": k["pages"] if doc else 0} if k else None


def _event(w, e, docs: dict, now: dt.datetime, cur, kept: dict | None = None) -> dict:
    end = daybook._end(e)
    doc = docs.get(daybook.meet_id(e))
    return {
        "id": daybook.meet_id(e), "day": e.day.isoformat(), "title": e.summary, "location": e.location,
        "calendar": e.calendar, "all_day": e.all_day, "start": _hm(e.start), "end": _hm(end) if end and end.date() == e.day else "",
        "from_min": _minutes(e.start), "to_min": _minutes(end) if end and end.date() == e.day else 24 * 60,
        "when": daybook.when(e), "now": e is cur, "past": bool(end and end <= now),
        "doc": doc["path"] if doc else "", "link": doc.get("link", "") if doc else "",
        "wiki": _wiki_line(kept or {}, daybook.meet_id(e), bool(doc)),
    }


def _beat(b: drumbeat.Beat, now: dt.datetime, docs: dict | None = None, kept: dict | None = None) -> dict:
    """A beat for the page: the words are the page's (by `kind`), the title as written."""
    doc = bool(docs) and b.kind == "meeting" and b.ref in docs
    return {"kind": b.kind, "tone": b.tone, "at": _hm(b.at), "day": "" if b.at.date() == now.date() else f"{b.at:%a}",
            "date": b.at.date().isoformat(), "min": _minutes(b.at), "title": b.title[:60], "ref": b.ref,
            "detail": b.detail, "approx": b.approx, "now": b.now, "reached": b.reached, "more": b.more,
            "doc": doc, "wiki": _wiki_line(kept or {}, b.ref, doc) if b.kind == "meeting" else None}


def _limit(lim: drumbeat.Limit, now: dt.datetime) -> dict:
    unit = "/h"
    return {"what": lim.what, "value": drumbeat.amount(lim.what, lim.value), "limit": drumbeat.amount(lim.what, lim.limit),
            "share": round(lim.share, 3), "rate": drumbeat.amount(lim.what, lim.rate) + unit if lim.rate > 0 else "",
            "at": _hm(lim.at), "day": f"{lim.at:%a %d}" if lim.at and lim.at.date() != now.date() else "", "reached": lim.reached, "who": lim.who,
            "known": lim.limit > 0}


def card(w) -> dict:
    """Closed: the next beats of all three kinds (meetings, scheduled runs, ≈ limits) up to the end of
    tomorrow, and a strip of the next `STRIP_H` hours with each beat's mark."""
    now = w.clock()
    _, _, left = daybook.now_and_next(w.day.events, now)
    docs = w.docs()
    beats = w.beats(dt.datetime.combine(now.date() + dt.timedelta(days=2), dt.time()))
    span = dt.timedelta(hours=STRIP_H)
    strip: list[dict] = []
    for b in beats:
        mark = {"kind": b.kind, "tone": b.tone, "pos": round((max(b.at, now) - now) / span, 3), "approx": b.approx}
        if b.at < now + span and not any(m["kind"] == b.kind and abs(m["pos"] - mark["pos"]) < 0.02 for m in strip):
            strip.append(mark)                  # one mark where two of a kind fall together
    kept = _from_wiki(w)
    return {"beats": [_beat(b, now, docs, kept) for b in drumbeat.ahead(beats, CARD)], "strip": strip, "hours": STRIP_H,
            "now": _hm(now), "left": left, "error": bool(w.day.errors), "kinds": list(w.kinds)}


def detail(w) -> dict:
    now = w.clock()
    cur, nxt, left = daybook.now_and_next(w.day.events, now)
    docs = w.docs()
    kept = _from_wiki(w)
    limits = w.limits()
    week = w.week_beats(limits)
    beats = [b for day in week.values() for b in day]
    days = []
    for d in range(daybook.WEEK_DAYS):
        day = now.date() + dt.timedelta(days=d)
        days.append({"date": day.isoformat(), "label": "Today" if d == 0 else f"{day:%a %d %b}",
                     "events": [_event(w, e, docs, now, cur, kept) for e in w.day.events if e.day == day],
                     "beats": [_beat(b, now) for b in week[day]]})
    return {
        "date": f"{now:%A %d %B}", "now_min": now.hour * 60 + now.minute,
        "current": daybook.meet_id(cur) if cur else "", "next": daybook.meet_id(nxt) if nxt else "", "left": left,
        "errors": list(w.day.errors), "days": days,
        "limits": [_limit(x, now) for x in limits],
        "jobs": [{"title": j.title, "expr": j.expr, "what": j.what, "ref": j.ref, "count": j.count,
                  "next": _beat(b, now) if (b := next((x for x in beats if x.kind == "schedule" and x.title == j.title
                                                       and x.ref == j.ref), None)) else None}
                 for j in w.jobs()],
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
