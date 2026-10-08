"""📍 The Watchtower's places (docs/design/phone-places.md §4–§6): what a paired phone says, acted on as freely
as the place allows.

    desk.report(report)   a phone came to a place or left it → sent · asked · waiting · stale · no road
    desk.alert()          the oldest report that waits on the person, as a question in Answers
    desk.answer(key)      send · skip (dismiss skips)
    desk.tick()           Apply if unanswered: what waited its time goes; the history is pruned

Propose only (`chains`) asks in Answers and waits; Apply if unanswered (`clock`) asks and goes after
`places.CLOCK_MIN` minutes unless skipped; Apply at once (`free`) goes. A report older than its place's
shelf life is kept but goes nowhere, and so is one that no road takes. 🛑 Stop all keeps what waits
waiting: nothing goes by itself after it.

The cart says the place's `say` (never the place or the time) and takes the route `<place>-<change>`, so a
road laid on `watch.place#home-arrived` takes only that. A place's reports never reach signals.jsonl,
the Lookout or a model: they are kept in the machine's history (`places.History`).
"""
from __future__ import annotations

import datetime as dt
import time
from dataclasses import dataclass

from orkcraft.realm import places

EVENT = "watch.place"
PRUNE_S = 3600.0


@dataclass
class Waiting:
    report: places.Report
    due: float | None              # monotonic: when it goes by itself (Apply if unanswered); None: it waits


class Desk:
    def __init__(self, worker) -> None:
        self.w = worker
        self.waiting: list[Waiting] = []
        self._pruned = 0.0

    # -- what the tower knows -----------------------------------------------------------------------

    @property
    def places(self) -> list[places.Place]:
        return places.parse(self.w.config)

    def place(self, name: str) -> places.Place | None:
        return next((p for p in self.places if p.name == name), None)

    @property
    def names(self) -> list[str]:
        return [p.name for p in self.places]

    @property
    def history(self) -> places.History:
        return places.History(places.history_file(self.w.repo_root), places.keep_days(self.w.config))

    def routes_taken(self) -> set[str] | None:
        """The routes the roads out on `watch.place` take; None when one takes them all."""
        scroll = self.w.town.scroll
        taken: set[str] = set()
        for b in (scroll.buildings if scroll is not None else []):
            if b.demolished:
                continue
            for r in b.roads:
                event = str(r.event or "")
                if r.source != self.w.building_id or event.partition("#")[0] != EVENT:
                    continue
                routes = [str(x) for x in ((r.filter or {}).get("route") or [])] or \
                    ([event.split("#", 1)[1]] if "#" in event else [])
                if not routes:
                    return None
                taken.update(routes)
        return taken

    def has_road(self, route: str) -> bool:
        taken = self.routes_taken()
        return taken is None or route in taken

    def loose_ends(self) -> list[dict]:
        """A stub on the map for each place's arrived and left that no road takes yet."""
        taken = self.routes_taken()
        if taken is None:
            return []
        return [{"route": r, "name": f"{p.name} · {change}", "event": f"{EVENT}#{r}"}
                for p in self.places for change in places.CHANGES
                if (r := places.route(p.name, change)) not in taken]

    # -- a report -----------------------------------------------------------------------------------

    def report(self, report: places.Report, now: dt.datetime | None = None) -> str:
        """What came of a phone's report (the same answer again for a retry of it)."""
        history = self.history
        prior = next((h for h in history.all() if h.id == report.id), None)
        if prior is not None:
            return prior.outcome
        place = self.place(report.place)
        if place is None:
            raise places.PlaceError(f"No place named {report.place!r} here")
        if places.stale(report, place, now):
            outcome = "stale"
        elif not self.has_road(places.route(place.name, report.change)):
            outcome = "no road"
        elif place.autonomy == "free":
            outcome = "sent" if self._send(report, place) else "no road"
        else:
            due = time.monotonic() + places.CLOCK_MIN * 60 if place.autonomy == "clock" else None
            self.waiting.append(Waiting(report, due))
            outcome = "waiting" if due is not None else "asked"
        history.add(report, outcome, now)
        self.w.changed()
        return outcome

    def _send(self, report: places.Report, place: places.Place) -> bool:
        text = place.text(report.change)
        return self.w.emit(EVENT, text, f"📍 {text}", route=places.route(place.name, report.change))

    def _done(self, item: Waiting, outcome: str) -> None:
        if item in self.waiting:
            self.waiting.remove(item)
        self.history.mark(item.report.id, outcome)
        self.w.changed()

    def decide(self, rid: str, send: bool) -> str:
        item = next((x for x in self.waiting if x.report.id == rid), None)
        if item is None:
            return ""
        place = self.place(item.report.place)
        if not send or place is None:
            self._done(item, "refused")
            return "refused"
        if places.stale(item.report, place):
            self._done(item, "stale")
            return "stale"
        outcome = "sent" if self._send(item.report, place) else "no road"
        self._done(item, outcome)
        return outcome

    # -- Answers --------------------------------------------------------------------------------------

    def alert(self):
        if not self.waiting:
            return None
        item = self.waiting[0]
        r, place = item.report, self.place(item.report.place)
        text = place.text(r.change) if place else ""
        who = r.device or "A phone"
        context = [f"It sends: {text}", f"Seen at {r.at[11:16]}"]
        if item.due is not None:
            left = max(0, round((item.due - time.monotonic()) / 60))
            context.append(f"Goes by itself in {left} min unless skipped")
        if len(self.waiting) > 1:
            context.append(f"{len(self.waiting) - 1} more place news after this one")
        return (f"place:{r.id}", f"📍 {who}: {r.change} · {r.place}", context, [("send", "Send"), ("skip", "Skip")])

    def answer(self, key: str) -> str | None:
        if not self.waiting:
            return None
        return self.decide(self.waiting[0].report.id, key == "send")

    # -- the clock ------------------------------------------------------------------------------------

    def tick(self, now: float | None = None) -> None:
        now = time.monotonic() if now is None else now
        for item in [x for x in self.waiting if x.due is not None and x.due <= now]:
            self.decide(item.report.id, True)
        for item in list(self.waiting):              # what waited past its shelf life is news no longer
            place = self.place(item.report.place)
            if place is None or places.stale(item.report, place):
                self._done(item, "stale")
        if now - self._pruned >= PRUNE_S:
            self._pruned = now
            self.history.prune()

    def halt(self) -> int:
        """🛑 Stop all: nothing goes by itself; what waits stays a question."""
        n = sum(1 for x in self.waiting if x.due is not None)
        for x in self.waiting:
            x.due = None
        if n:
            self.w.changed()
        return n

    # -- the page -------------------------------------------------------------------------------------

    def view(self) -> dict:
        taken = self.routes_taken()
        rows = self.history.recent(20)
        return {
            "places": [{**p.as_dict(), "roads": [c for c in places.CHANGES
                                                 if taken is None or places.route(p.name, c) in taken]}
                       for p in self.places],
            "keep_days": places.keep_days(self.w.config),
            "waiting": len(self.waiting),
            "history": [{"place": h.place, "change": h.change, "at": h.at[:16].replace("T", " "),
                         "device": h.device, "outcome": h.outcome} for h in rows],
        }

    def save(self, rows: list, keep_days: object = None) -> bool:
        kept = [p.line() for p in places.parse({"places": rows})]
        changes: dict = {"places": kept or None}
        if keep_days is not None:
            changes["places_keep_days"] = int(places.keep_days({"places_keep_days": keep_days}))
        ok = self.w.save_config(changes)
        if ok:
            names = {places.place_of(x).name for x in kept}
            for item in [x for x in self.waiting if x.report.place not in names]:
                self._done(item, "refused")
            self.history.prune()
        return ok

    def clear(self) -> None:
        self.history.clear()
        self.w.changed()
