"""Ambient HUD: `[ 🧌 Orkcraft v0.1 ]──[ ⚙️ Menu (F10) · 🛑 READY ]   … [🪙 $— / $20.00] [🪵 — / 128k] [🥩 n/max]`.

The menu and Halt All share one segment: a click opens the system menu, whose first item is
Halt; the segment shows the halt state (READY / HALTED — n stopped)."""
from __future__ import annotations

from dataclasses import dataclass, field

from rich.cells import cell_len
from rich.text import Text
from textual import events
from textual.message import Message
from textual.widgets import Static

from orkcraft import __version__
from orkcraft.scroll import Budget
from orkcraft.sources.telemetry import fmt_tokens

_DEFAULT_BUDGET = Budget()


def default_gold(budget: Budget) -> str:
    return f"$— / ${budget.gold_session_limit_usd:.2f}"


def default_lumber(budget: Budget) -> str:
    return f"— / {fmt_tokens(budget.lumber_context_limit_tokens)}"


@dataclass
class Resources:
    gold: str = ""        # 🪙 this run's spend vs limit ("$1.24 / $20.00"; "$— / …" before any)
    lumber: str = ""      # 🪵 context of the active session vs limit ("91k / 128k")
    gold_level: str = "ok"    # ok | warn (≥ 80 %) | over (≥ 100 %)
    lumber_level: str = "ok"
    supply: int = 0       # 🥩 running orcs
    supply_max: int = 5
    alerts: int = 0       # ❓ orcs waiting for orders
    commit: bool = True   # §10 per-action commits
    budget: Budget = field(default_factory=Budget)

    def __post_init__(self) -> None:
        if not self.gold:
            self.gold = default_gold(self.budget)
        if not self.lumber:
            self.lumber = default_lumber(self.budget)


class Hud(Static):
    class MenuClicked(Message):
        """Posted when the [ ⚙️ Menu (F10) · 🛑 … ] segment is clicked."""

    class AlertsClicked(Message):
        """Posted when the [ ❓ … awaiting orders ] segment is clicked."""

    DEFAULT_CSS = """
    Hud {
        dock: top;
        height: 1;
        width: 100%;
        background: $panel;
        color: $text;
    }
    """

    def __init__(self, id: str | None = None, budget: Budget | None = None) -> None:
        super().__init__("", id=id)
        self.budget = budget or Budget()
        self.resources = Resources(budget=self.budget, supply_max=self.budget.supply_max_workers)
        self.halt = "READY"
        self._menu_span = (0, 0)   # cells of the Menu · Halt All segment (set by update_hud)
        self._alerts_span = (0, 0)  # cells of the Awaiting Orders segment (set by update_hud)
        self.mode = "full"

    def on_mount(self) -> None:
        self.update_hud()

    def on_resize(self) -> None:
        self.update_hud()

    def set_budget(self, budget: Budget) -> None:
        self.budget = budget
        self.resources.budget = budget
        self.update_hud()

    def set_halt(self, state: str) -> None:
        self.halt = state
        self.update_hud()

    def set_resources(self, resources: Resources) -> None:
        self.resources = resources
        if resources.budget:
            self.budget = resources.budget
        self.update_hud()

    def on_click(self, event: events.Click) -> None:
        start, end = self._menu_span
        if start <= event.x < end:
            self.post_message(self.MenuClicked())
            event.stop()
            return
        astart, aend = self._alerts_span
        if astart <= event.x < aend:
            self.post_message(self.AlertsClicked())
            event.stop()

    def update_hud(self) -> None:
        r = self.resources
        left = Text()
        left.append("[ 🧌 Orkcraft ", style="bold")
        left.append(f"v{'.'.join(__version__.split('.')[:2])} ", style="dim")
        left.append("]")
        left.append("──")
        narrow = self.size.width < 130
        halt_style = "bold green" if self.halt == "READY" else "bold reverse red"
        start = cell_len(left.plain)
        left.append("[ ⚙️ F10 · 🛑 " if narrow else "[ ⚙️ Menu (F10) · 🛑 ", style="bold")
        left.append(self.halt, style=halt_style)
        left.append(" ]")
        self._menu_span = (start, cell_len(left.plain))
        if r.alerts:
            left.append("──")
            astart = cell_len(left.plain)
            left.append(f"[ 🔥 {r.alerts} ]" if narrow else f"[ 🔥 {r.alerts} awaiting orders ]", style="bold yellow")
            self._alerts_span = (astart, cell_len(left.plain))
        else:
            self._alerts_span = (0, 0)

        gold_limit = f"${self.budget.gold_session_limit_usd:.2f}"
        lumber_limit = fmt_tokens(self.budget.lumber_context_limit_tokens)
        gold_disp = r.gold if "/" in r.gold else f"${r.gold} / {gold_limit}"
        lumber_disp = r.lumber if "/" in r.lumber else f"{r.lumber} / {lumber_limit}"

        right = Text()
        if not narrow:
            right.append(f"⛏ commit {'ON' if r.commit else 'OFF'} ", style="dim")
        levels = {"warn": "bold yellow", "over": "bold reverse red"}
        right.append(f"[🪙 {gold_disp}]", style=levels.get(r.gold_level, ""))
        right.append(" ")
        right.append(f"[🪵 {lumber_disp}]", style=levels.get(r.lumber_level, ""))
        right.append(" ")
        supply_style = "bold red" if r.supply >= r.supply_max else ("yellow" if r.supply else "")
        right.append(f"[🥩 {r.supply}/{r.supply_max}]", style=supply_style)

        gap = self.size.width - cell_len(left.plain) - cell_len(right.plain)
        line = left + Text(" " * max(gap, 1)) + right
        line.truncate(max(self.size.width, 1), overflow="ellipsis")
        self.update(line)
