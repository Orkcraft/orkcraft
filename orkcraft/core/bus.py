"""The bus: how the core tells a face what changed. A service never shows anything itself, it
publishes. Each face subscribes and decides how to show it: a toast, a redrawn road, a refreshed
hall. Payloads are plain data (strings, numbers, lists, dicts), so a daemon can later carry them
over a socket unchanged.

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
RAISED = "raised"    # building: a new custom building stands in the scroll; a face opens its view
HUD = "hud"          # the treasury or the clock changed

SEVERITIES = ("information", "warning", "error")


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
