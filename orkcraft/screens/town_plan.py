"""📜 The Town Builder's plan, for the operator to approve before anything is raised.

    TownPlanReview(order, plan)   dismisses {"action": "raise"}, {"action": "again", "note": "…"}
                                  or None (later: the order keeps waiting in the Town Hall)
"""
from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Static

from orkcraft.realm import catalog, pipes
from orkcraft.realm.town_builder import TownPlan
from orkcraft.screens.build_flow import MODAL_CSS


def plan_text(order: str, plan: TownPlan) -> Text:
    t = Text()
    t.append("You asked: ", style="dim")
    t.append(f"“{order.strip()[:300]}”\n\n", style="italic")
    if plan.title:
        t.append(f"{plan.title}\n", style="bold")
    if plan.summary:
        t.append(f"{plan.summary}\n", style="dim")
    t.append(f"\n🏗 Buildings ({len(plan.specs)})\n", style="bold")
    for spec in plan.specs:
        t.append(f"  {spec.get('icon', '')} {spec.get('title', spec['id'])}", style="bold")
        t.append(f"  · {catalog.type_of(spec).title}\n", style="dim")
        if plan.whys.get(spec["id"]):
            t.append(f"     {plan.whys[spec['id']]}\n")
    titles = {s["id"]: f"{s.get('icon', '')} {s.get('title', s['id'])}".strip() for s in plan.specs}
    t.append(f"\n🛤 Roads ({len(plan.roads)})\n", style="bold")
    for r in plan.roads:
        t.append(f"  {titles.get(r.source, r.source)} → {titles.get(r.target, r.target)}", style="bold")
        t.append(f"  · {pipes.label(r.event)}{f' ({r.route})' if r.route else ''}\n", style="dim")
        if r.why:
            t.append(f"     {r.why}\n")
    if not plan.roads:
        t.append("  none — the buildings work on their own\n", style="dim")
    cost = f" · ${plan.cost_usd:.2f}" if plan.cost_usd is not None else ""
    t.append(f"\nPlanned in {len(plan.attempts)} attempt(s){cost}. Roads are plain: no model runs on them.",
             style="dim")
    return t


class TownPlanReview(ModalScreen[dict | None]):
    BINDINGS = [Binding("escape", "later", "Later"), Binding("ctrl+s", "raise", "Raise", priority=True)]
    DEFAULT_CSS = MODAL_CSS.format(cls="TownPlanReview", border_color="$accent", title_color="$accent") + """
    TownPlanReview > Vertical { width: 96; }
    TownPlanReview #tp-body { height: auto; max-height: 30; }
    TownPlanReview #tp-note { margin-top: 1; }
    TownPlanReview .tp-buttons { height: auto; margin-top: 1; align-horizontal: right; }
    TownPlanReview .tp-buttons Button { margin-left: 1; }
    """

    def __init__(self, order: str, plan: TownPlan) -> None:
        super().__init__()
        self.order = order
        self.plan = plan

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label("📜 The Town Builder's plan", classes="build-title")
            with VerticalScroll(id="tp-body"):
                yield Static(plan_text(self.order, self.plan), markup=False)
            yield Input(placeholder="not quite? say what to change, then Ask again", id="tp-note")
            with Horizontal(classes="tp-buttons"):
                yield Button("Later", id="tp-later")
                yield Button("Ask again", id="tp-again")
                yield Button("Raise the town [ctrl+s]", id="tp-raise", variant="success")

    def action_raise(self) -> None:
        self.dismiss({"action": "raise"})

    def action_later(self) -> None:
        self.dismiss(None)

    def action_again(self) -> None:
        note = self.query_one("#tp-note", Input).value.strip()
        if not note:
            self.query_one("#tp-note", Input).focus()
            self.notify("say what to change first", title="Ask again")
            return
        self.dismiss({"action": "again", "note": note})

    def on_input_submitted(self, event: Input.Submitted) -> None:
        event.stop()
        self.action_again()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        {"tp-raise": self.action_raise, "tp-again": self.action_again}.get(event.button.id or "", self.action_later)()
