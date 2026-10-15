"""🚶 Leaving the camp in the GUI (docs/design/audience.md §2a, backlog W3): the sun dial's "I'm off", the Workchief's
line that says what the orks will do until evening and asks what to take first, and the computer kept awake only while
carts are in work and it is on power (gui/awake.py), let go when the work is done or the cap is reached. With "Stay
reachable from your phone" (decisions-2026-10 §18) it is also held while a phone is paired, carts or not, on power
only: on battery it falls back to "while carts work", which on battery holds nothing, and the phone says so.

    away = Away(host)
    host.commands.update(away.commands())   # away.plan, away.leave, away.back
    away.tick(now)                          # from the host's clock: the cap, evening, the keep-awake hold
    away.keep_awake()                       # hold or let go, at once (the town opened, the setting changed)
    away.why                                # why it holds now: "phone", "carts" or "" (it does not)
    away.power_state()                      # for the page and the phone: the mode, why, on battery, "Mac" or "computer"
    away.snapshot()                         # what the page shows while away, or None

What the service says when the cap is reached or evening comes is said once in the Workchief's line, as the end of
Do not disturb is (`you.summary`).
"""
from __future__ import annotations

import sys
import time
from typing import Any, Callable

from orkcraft import settings
from orkcraft.core import leaving
from orkcraft.gui import awake
from orkcraft.gui.pairing import Pairing

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
        self.why = ""                           # why the computer is held now: "phone", "carts", or "" (it is not)
        self.platform = sys.platform
        self.pairing = Pairing()                # the paired phones, as the settings file has them (gui/pairing.py)

    def on_power(self, now: float | None = None) -> bool:
        """On mains power (unknown counts as yes: a desktop tells nothing), read at most once a minute."""
        now = time.monotonic() if now is None else now
        if now - self._power_at >= POWER_S:
            self._power_at = now
            self._on_power = self.power()
        return self._on_power is not False

    def reason(self) -> str:
        """Why the computer should be held now, by the setting: "phone" (a phone paired, on power), "carts" (carts
        in work, on power, under the cap), or "" — on battery never, whatever the setting."""
        m = self.host.town.machine
        mode = settings.awake_mode(m.keep_awake)
        if mode == "off" or not self.on_power():
            return ""
        if mode == "phone" and self.paired():
            return "phone"
        s = self.service
        return "carts" if s.busy() and not s.capped else ""

    def keep_awake(self) -> str:
        """Hold the computer awake when `reason` says so; else let go."""
        a = self.host.awake
        if not a.running:                       # only while the town is open in its window or the browser
            return a.how
        why = self.reason()
        how = a.apply(bool(why))
        self.why = why if how else ""
        return how

    def paired(self) -> bool:
        """A phone is paired with this machine (read again only when the settings file changed)."""
        return bool(self.pairing.devices())

    def machine(self) -> str:
        return "Mac" if self.platform == "darwin" else "computer"

    def power_state(self) -> dict[str, Any]:
        """The mode, why it holds now, and whether it is on battery (`battery`: True only when it says so)."""
        return {"mode": self.host.town.machine.keep_awake, "why": self.why, "battery": self._on_power is False,
                "machine": self.machine()}

    def offer(self) -> str:
        """The machine's word ("Mac") while "keep it awake for the phone" is to be asked: a phone paired, the
        setting not already that, not asked before; else ""."""
        m = self.host.town.machine
        if self.host.town.demo or m.awake_offered or m.keep_awake == "phone" or not self.paired():
            return ""
        return self.machine()

    def phone_line(self) -> str:
        """What the phone says of the host's sleep: one quiet line on battery, else nothing."""
        self.on_power()
        return f"Your {self.machine()} is on battery and may sleep." if self._on_power is False else ""

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
        m = self.host.town.machine
        return {**self.service.plan(), "awake_how": self.host.awake.how, "keep_awake": m.keep_awake != "off",
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
