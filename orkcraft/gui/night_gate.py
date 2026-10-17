"""The night gate's face (docs/specs/32-night-gate.md §2–3): its two commands, its clock, its card.

    night = Night(ideas)                  # made by gui/ideas.py, which wires it into the host
    night.commands()                      # gate.pass_night {"date"}, gate.run_night {}
    night.tick()                          # the host's clock: the run starts by itself at `gate.night_hour`
    night.card()                          # the Night report as the board's Today and the Review gate show it
    night.stop_all()                      # Stop all

The run itself is core/night_gate.py's; this only asks it and says what came back. Pass to main blocks on git (a
fast-forward and a push), so it runs on the host's thread like the board's other commands; the night's run never does.
"""
from __future__ import annotations

import time
from typing import Any, Callable

from orkcraft.core.night_gate import NightGate

TICK_S = 30.0                    # how often the clock looks at the hour


class Night:
    def __init__(self, ideas) -> None:
        self.ideas = ideas
        town = ideas.town
        self.gate = NightGate(town.repo_root, ideas.state_dir, lambda: town.machine.gate, ideas.hop,
                              demo=bool(town.demo), budget_ok=lambda: town.budget_ok())
        self._at = -TICK_S

    def tick(self, now: float | None = None) -> None:
        now = time.monotonic() if now is None else now
        if now - self._at < TICK_S:
            return
        self._at = now
        if self.gate.tick():
            self.ideas.changed("")

    def stop_all(self) -> None:
        self.gate.stop_all()

    def card(self) -> dict | None:
        try:
            return self.gate.card()
        except Exception:                     # a broken report never breaks the board
            return None

    def red(self, card: dict | None) -> bool:
        """A red night that waits for the person (Needs you): finished, not green, not passed."""
        return bool(card) and not card["running"] and not card["green"] and not card["passed_at"]

    def pass_night(self, args: dict) -> dict:
        date = args.get("date")
        if not isinstance(date, str) or not date.strip():
            return {"error": "Which night? Its date is missing"}
        try:
            got = self.gate.pass_night(date.strip())
        except ValueError as e:
            return {"error": str(e)}
        if got.get("ok"):
            words = "Passed to main" + (f" · {got['note']}" if got.get("note") else "")
            self.ideas.town.toast(words, title=f"Night report · {date}")
        self.ideas.changed("")
        return got

    def run_night(self, _args: dict) -> dict:
        try:
            started = self.gate.run_now()
        except RuntimeError as e:
            return {"error": str(e)}
        if not started:
            return {"error": "The night run is on already"}
        self.ideas.changed("")
        return {"ok": True}

    def commands(self) -> dict[str, Callable[[dict], Any]]:
        return {"gate.pass_night": self.pass_night, "gate.run_night": self.run_night}
