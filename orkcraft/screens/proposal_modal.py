"""🔧 A self-improvement proposal: what the Council would change, and why.

Apply goes through the camp's git (a checkpoint the building's Z takes back); Later keeps it waiting
(F10 → Self-improvement); Dismiss drops it. Dismisses "apply" | "dismiss" | None (later).
"""
from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Label, Static

from orkcraft.realm import optimize
from orkcraft.screens.build_flow import MODAL_CSS

WHAT = {"shrink": "a shorter prompt", "chain": "chain ops instead of the agent",
        "script": "a script instead of the steward prompt"}


class ProposalModal(ModalScreen[str | None]):
    BINDINGS = [Binding("enter", "apply", "Apply"), Binding("escape", "later", "Later"),
                Binding("d", "dismiss_it", "Dismiss")]
    DEFAULT_CSS = MODAL_CSS.format(cls="ProposalModal", border_color="$warning", title_color="$warning") + """
    ProposalModal > Vertical { width: 110; }
    ProposalModal VerticalScroll { height: auto; max-height: 26; }
    """

    def __init__(self, p: optimize.Proposal, title: str = "") -> None:
        super().__init__()
        self.p, self.building_title = p, title or p.building

    def compose(self) -> ComposeResult:
        p = self.p
        with Vertical():
            yield Label(f"🔧 {self.building_title} · {WHAT.get(p.action, p.action)} for {p.target}", classes="build-title")
            cost = f" · the proposal cost ${p.cost_usd:.3f}" if p.cost_usd is not None else ""
            yield Static(Text(f"{p.why}\nsaves: {p.saving or '—'} · {p.tokens} tokens today{cost}", style="dim"),
                         classes="build-text")
            with VerticalScroll():
                yield Label("now", classes="build-section")
                yield Static(Text(p.before[:3000], style="red"), classes="build-text")
                yield Label("proposed", classes="build-section")
                yield Static(Text(p.after[:4000], style="green"), classes="build-text")
            with Horizontal():
                yield Button("✓ Apply [Enter]", variant="success", id="prop-apply")
                yield Button("Later [Esc]", id="prop-later")
                yield Button("✗ Dismiss [d]", variant="error", id="prop-dismiss")
            yield Static("Apply commits it to the camp's git — Z on the building takes it back", classes="build-hint")

    def action_apply(self) -> None:
        self.dismiss("apply")

    def action_later(self) -> None:
        self.dismiss(None)

    def action_dismiss_it(self) -> None:
        self.dismiss("dismiss")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        self.dismiss({"prop-apply": "apply", "prop-dismiss": "dismiss"}.get(event.button.id or ""))
