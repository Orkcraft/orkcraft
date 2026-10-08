"""The bus: how the core tells a face what changed. A service never shows anything itself, it
publishes. Each face subscribes and decides how to show it: a toast, a redrawn road, a refreshed
hall. Payloads are plain data (strings, numbers, lists, dicts), so a daemon can later carry them
over a socket unchanged (`DELIVERED`, `CART` and `RUN` still carry the realm's dataclasses; they
become dicts when the socket comes).

    bus.subscribe(TOAST, lambda e: show(e.data["message"]))
    bus.publish(TOAST, message="🛤 Pit → Lake", title="Roads")
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable

ANY = "*"            # a subscriber to every topic (a log, a socket)

TOAST = "toast"      # message, title, severity ("information" | "warning" | "error"), timeout (s or None)
ROADS = "roads"      # the roads changed: save the scroll, redraw them
ROSTER = "roster"    # the orks or their questions changed
HALL = "hall"        # the Town Hall's lists changed (ratings, proposals, the Council's log)
SPEC = "spec"        # building, spec: a custom building's spec changed (its view takes the new one)
UI = "ui"            # building, ui: a building's UI document changed (its view lays itself out again)
HUD = "hud"          # the treasury or the clock changed
DELIVERED = "delivered"  # building, payload, title, markdown, label, worker: a cart arrived (worker: one took it)
OUTPUT = "output"    # building, orc, title, markdown, trail, ref: a handler's result for a custom building
CART = "cart"        # cart: a cart set off along a road (or was held)
RUN = "run"          # run, name: a handler or a building's own agent finished
LOOT = "loot"        # path, source: a report was kept in Loot
WORKER = "worker"    # building: a building's worker changed its state (its view draws it again)
SESSION = "session"  # key, state ("opened" | "exited" | "forgotten"), code: an ork's CLI session (core/sessions.py)
ORDER = "order"      # kind, building, source, order, card: the Warchief gave an order a face runs as its job
                     # (a road for the road planner, an ork for the Recruiter, a change for a keeper)


@dataclass(frozen=True)
class Event:
    topic: str
    data: dict[str, Any] = field(default_factory=dict)


class Bus:
    def __init__(self) -> None:
        self._subs: dict[str, list[Callable[[Event], Any]]] = defaultdict(list)

    def subscribe(self, topic: str, fn: Callable[[Event], Any]) -> Callable[[], None]:
        """`fn(event)` on every event of `topic` (ANY: of every topic). Returns the unsubscribe."""
        self._subs[topic].append(fn)

        def off() -> None:
            if fn in self._subs[topic]:
                self._subs[topic].remove(fn)
        return off

    def publish(self, topic: str, **data: Any) -> Event:
        """Synchronous, on the caller's thread: a face that draws on one thread hops itself."""
        event = Event(topic, data)
        for fn in list(self._subs.get(topic, ())) + list(self._subs.get(ANY, ())):
            fn(event)
        return event
