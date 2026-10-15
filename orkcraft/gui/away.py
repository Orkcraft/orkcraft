"""🚶 Leaving the camp in the GUI (docs/design/audience.md §2a, backlog W3): the sun dial's "I'm off", the Workchief's
line that says what the orks will do until evening and asks what to take first, and the computer kept awake only while
carts are in work and it is on power (gui/awake.py), let go when the work is done or the cap is reached.

    away = Away(host)
    host.commands.update(away.commands())   # away.plan, away.leave, away.back
    away.tick(now)                          # from the host's clock: the cap, evening, the keep-awake hold
    away.keep_awake()                       # hold or let go, at once (the town opened, the setting changed)
    away.snapshot()                         # what the page shows while away, or None

What the service says when the cap is reached or evening comes is said once in the Workchief's line, as the end of
Do not disturb is (`you.summary`).
"""
from __future__ import annotations

import time
from typing import Any, Callable

from orkcraft.core import leaving
from orkcraft.gui import awake

TICK_S = 30.0                  # how often the window's share and the hold are looked at
POWER_S = 60.0                 # how often the power is read (pmset is a process)


class Away:
    def __init__(self, host) -> None:
        self.host = host
        self.service = leaving.Leaving(host.town)
        self.power = awake.on_power
        self._at = -TICK_S
        self._power_at = -POWER_S
        self._on_power: bool | None = None

    def on_power(self, now: float | None = None) -> bool:
        """On mains power (unknown counts as yes: a desktop tells nothing), read at most once a minute."""
        now = time.monotonic() if now is None else now
        if now - self._power_at >= POWER_S:
            self._power_at = now
            self._on_power = self.power()
        return self._on_power is not False

    def keep_awake(self) -> str:
        """Hold the computer awake while carts are in work, on power, under the cap (and the setting on); else let go."""
        a = self.host.awake
        if not a.running:                       # only while the town is open in its window or the browser
            return a.how
        s = self.service
        return a.apply(self.host.town.machine.keep_awake and s.busy() and not s.capped and self.on_power())

    def tick(self, now: float | None = None) -> None:
        now = time.monotonic() if now is None else now
        if now - self._at < TICK_S:
            return
        self._at = now
        said = self.service.tick()
        if said:
            self._say(said)
        self.keep_awake()

    def _say(self, text: str) -> None:
        you = self.host.you
        you.summary = {"id": f"away:{time.time():.0f}", "text": text,
                       "open": "orders" if self.host.muster.roster.alerts else "", "building": ""}
        you.on_news({"kind": "away", "line": text})
        self.host.on_change()

    def snapshot(self) -> dict[str, Any] | None:
        return self.service.snapshot()

    # -- the page's commands --------------------------------------------------------------------------

    def _plan(self, args: dict) -> dict[str, Any]:
        return {**self.service.plan(), "awake_how": self.host.awake.how, "keep_awake": self.host.town.machine.keep_awake,
                "on_power": self.on_power()}

    def _leave(self, args: dict) -> dict[str, Any]:
        first = str(args.get("first") or "")[:80]
        snap = self.service.leave(first, on_power=self.on_power())
        self.keep_awake()
        self.host.on_change()
        return snap

    def _back(self, args: dict) -> dict[str, Any]:
        said = self.service.back("person")
        self.keep_awake()
        if said:
            self._say(said)
        return {"said": said}

    def commands(self) -> dict[str, Callable[[dict], Any]]:
        return {"away.plan": self._plan, "away.leave": self._leave, "away.back": self._back}
