"""👀 "Since your last look" as a service (docs/design/audience.md §2a; realm/last_look.py has the rules and words).

    built(town, building_id, event_id, title, ref)   # core/delivery.py: a result went through, launched, was done
    moved(town, cart)                                # core/delivery.py: a cart reached its building
    look = LastLook(town, muster, limits)            # a face makes one; `limits()` is the last quota reads
    look.beat()          # the face is in front of the person (a look): it may begin a new look and greet them
    look.snapshot()      # the greeting to draw, or None
    look.done()          # the person went back to the camp
    look.beat(face="phone")   # the same person's look, from the phone: it greets the phone, not the desktop

One person, one look: the desktop and the phone beat the same look, so a look on the phone counts on the desktop
too. The greeting belongs to the face that began the new look (`face`), and each face says it is done with its own.

Everything is written to the town's own folder (the local event log and `.orkcraft/usage/last_look.json`), never
sent; nothing in the demo. It changes no building and shows nothing itself: it publishes `bus.LOOK` and a face draws.
"""
from __future__ import annotations

import datetime as dt
import re
from typing import Any, Callable

from orkcraft.core import bus
from orkcraft.realm import event_log, last_look, modes, status

STUCK_S = 30 * 60           # a task waiting this long is a problem, with what it waits for
# Waits the questions already show (the person's answer or yes), and ones that end by themselves soon.
NOT_STUCK = (status.ANSWER, status.APPROVAL, status.TIMER)


def _root(town):
    return None if getattr(town, "demo", False) else getattr(town, "repo_root", None)


def built(town, building_id: str, event_id: str, title: str = "", ref: str = "") -> None:
    """A building sent an event that is a result (realm/last_look.py `BUILT_BY_EVENT`): kept in the local log."""
    kind = last_look.BUILT_BY_EVENT.get(event_id)
    if kind:
        title = modes.strip_emoji(title or "")
        if kind == "launched":                 # the Publisher titles a shot "<status> <url>": where it went is the news
            title = re.sub(r"^\d{3}\s+", "", title)
        event_log.record(_root(town), event_log.BUILT, building=building_id, kind=kind, title=title[:200], ref=ref)


def moved(town, cart) -> None:
    """A cart reached the building at the end of its road."""
    if getattr(cart, "status", "") == "delivered":
        event_log.record(_root(town), event_log.CART_MOVED, source=cart.source, target=cart.target,
                         title=modes.strip_emoji(getattr(cart.payload, "title", "") or "")[:200])


def _title(town, building_id: str) -> str:
    b = town.scroll.building(building_id) if getattr(town, "scroll", None) is not None else None
    return (b.title if b is not None and b.title else "") or building_id


class LastLook:
    def __init__(self, town, muster, limits: Callable[[], list], subscriptions: Callable[[], list[str]]) -> None:
        self.town, self.muster, self.limits, self.subscriptions = town, muster, limits, subscriptions
        self.root = _root(town)
        self.look = last_look.load(self.root)
        self.greetings: dict[str, dict[str, Any]] = {}  # face → since, the log's lines then, used, seen

    @property
    def greeting(self) -> dict[str, Any] | None:
        """The desktop's greeting (since, the log's lines then, used, seen); None: none shown."""
        return self.greetings.get("gui")

    # -- what stands now --------------------------------------------------------------------------------

    def used_now(self) -> dict[str, int]:
        """% of each subscription window used now, from the last quota reads (the Town Hall's)."""
        subs = set(self.subscriptions())
        out = {}
        for x in self.limits() or []:
            if x.provider in subs and x.remaining is not None:
                out[" · ".join(p for p in (x.provider, x.window) if p)] = round((1 - x.remaining) * 100)
        return out

    def questions(self) -> list[dict[str, Any]]:
        """The questions that wait for the person, each with its answers (one tap) — as Orders has them."""
        roster, who = self.muster.roster, self.muster.who()
        found = list(roster.alerts)
        ids = {a.id for a in found}
        found += [o.alert for o in roster.orcs if o.alert is not None and o.alert.id not in ids]
        first = self.muster.alert_first_seen
        found.sort(key=lambda a: first.get(a.id, float("inf")))
        where = {o.alert.id: o.building for o in roster.orcs if o.alert is not None and o.building}
        return [{"id": a.id, "who": modes.plain(who.get(a.id, "")), "title": modes.strip_emoji(a.title),
                 "options": [[k, modes.strip_emoji(label)] for k, label in a.options], "source": a.source,
                 "ref": a.ref, "building": where.get(a.id) or ""} for a in found]

    def problems(self, now: dt.datetime | None = None) -> list[dict[str, Any]]:
        """🔥 a building stopped on an error; a task stuck for `STUCK_S`, each with what it waits for."""
        now = now or dt.datetime.now().astimezone()
        out = []
        for bid, w in list(self.town.workers.items()):
            try:
                if w.status() == "ERROR":
                    err = getattr(w, "error", "")
                    why = modes.strip_emoji(err if isinstance(err, str) else "")[:160]
                    out.append({"id": f"{bid}:error", "building": bid, "title": _title(self.town, bid),
                                "line": "stopped on an error" + (f": {why}" if why else ""), "waits": "you: open it"})
                out += self._stuck(bid, w, now)
            except Exception:              # one building's state never hides the others'
                continue
        return out

    def _stuck(self, bid: str, w, now: dt.datetime) -> list[dict[str, Any]]:
        task_wait, queue = getattr(w, "task_wait", None), getattr(getattr(w, "state", None), "queue", None)
        if task_wait is None or not isinstance(queue, list):
            return []
        out = []
        for t in queue:
            arrived = last_look._parse(getattr(t, "arrived", "") or "")
            if arrived is None or (now - arrived).total_seconds() < STUCK_S:
                continue
            wait = task_wait(t, now.timestamp())
            if wait is None or wait.why in NOT_STUCK:
                continue
            out.append({"id": f"{bid}:{t.id}", "building": bid, "title": modes.strip_emoji(t.title),
                        "line": f"{_title(self.town, bid)}: waits {last_look.away_label((now - arrived).total_seconds())}",
                        "waits": wait.line})
        return out

    def working(self) -> list[str]:
        """What the orks are on now: the Agent pools' tasks in work, then the busy orks' own."""
        out: list[str] = []
        for w in list(self.town.workers.values()):
            st = getattr(w, "state", None)
            for o in getattr(st, "orcs", None) or []:
                if getattr(o, "status", "") == "working" and (t := st.task(o.task)) is not None:
                    out.append(modes.strip_emoji(t.title))
        out += [modes.strip_emoji(o.task) for o in self.muster.roster.orcs if o.status == "busy" and o.task]
        return list(dict.fromkeys(x for x in out if x))

    def _seen(self) -> list[str]:
        return [q["id"] for q in self.questions()] + [p["id"] for p in self.problems()]

    # -- the look ------------------------------------------------------------------------------------------

    def beat(self, now: dt.datetime | None = None, face: str = "gui") -> bool:
        """The face was in front of the person for a while. True when it began a new look and greets them there."""
        now = now or dt.datetime.now().astimezone()
        look, ended = last_look.beat(self.look, now)
        greets = False
        if ended is not None:
            event_log.record(self.root, event_log.LOOKED, started=ended.start, seconds=last_look.seconds(ended))
            if last_look.away_s(ended, now) >= last_look.AWAY_S:
                self.greetings[face] = {"since": ended.end, "rows": event_log.read(self.root, ended.end) if self.root else [],
                                 "used": dict(ended.used), "seen": list(ended.seen)}
                greets = True
        look.used, look.seen = self.used_now(), self._seen()
        self.look = look
        last_look.save(self.root, look)
        if greets:
            self.town.publish(bus.LOOK, greets=True, face=face)
        return greets

    def snapshot(self, now: dt.datetime | None = None, face: str = "gui") -> dict[str, Any] | None:
        g = self.greetings.get(face)
        if g is None:
            return None
        now = now or dt.datetime.now().astimezone()
        since = last_look._parse(g["since"]) or now
        d = last_look.digest(since, now, g["rows"], self.questions(), self.problems(now), self.working(),
                             g["used"], self.used_now(), g["seen"])
        for item in d["built"]["items"]:            # a building demolished since: nothing to open
            b = self.town.scroll.building(item["building"]) if item["building"] else None
            if b is None or b.demolished:
                item["building"] = ""
        return d

    def done(self, face: str = "gui") -> None:
        if self.greetings.pop(face, None) is not None:
            self.town.publish(bus.LOOK, greets=False, face=face)
