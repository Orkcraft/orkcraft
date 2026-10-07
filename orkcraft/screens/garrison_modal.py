"""Modal to recruit an orc into a building's garrison."""
from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Select, Static

from orkcraft import scroll
from orkcraft.realm import tiers
from orkcraft.scroll import OrcSpec

MODAL_CSS = """
GarrisonModal {
    align: center middle;
}
GarrisonModal > Vertical {
    width: 60;
    max-width: 90%;
    height: auto;
    max-height: 90%;
    border: thick $accent;
    background: $surface;
    padding: 1 2;
}
GarrisonModal .order-title {
    text-style: bold;
    color: $accent;
    margin-bottom: 1;
}
GarrisonModal .order-error {
    color: $error;
    margin-bottom: 1;
}
GarrisonModal Horizontal {
    height: auto;
    margin-top: 1;
}
GarrisonModal Button {
    margin-right: 1;
}
"""


def tier_options() -> list[tuple[str, str]]:
    """The tier picker: the heavy models first, then the CLI's own default ("")."""
    out = [(f"{tiers.label(t)} — {' · '.join(m[t] for m in tiers.MODELS.values() if t in m)}", t) for t in tiers.TIERS]
    return out + [("· CLI default model", "")]


class GarrisonModal(ModalScreen["OrcSpec | str | None"]):
    """Recruit a garrison orc: describe it for the Recruiter (dismisses the prompt text), or by
    hand as an agent (dismisses the new OrcSpec)."""

    BINDINGS = [Binding("escape", "dismiss(None)", "Cancel")]
    DEFAULT_CSS = MODAL_CSS

    def __init__(self, building_title: str, building_id: str | None = None) -> None:
        super().__init__()
        self.building_title = building_title
        self.building_id = building_id

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label(f"➕ Recruit Ork — {self.building_title}", classes="order-title")
            yield Static("", id="recruit-error", classes="order-error")
            yield Label("What should it do? (the Recruiter picks chain → script → agent):")
            yield Input(placeholder="e.g. when a task in the Forge is done, show its id and title", id="recruit-prompt")
            with Horizontal():
                yield Button("🧙 Ask the Recruiter", variant="primary", id="recruit-ask")
            yield Label("…or by hand (an agent):", classes="order-hint")
            yield Label("Name:")
            yield Input(placeholder="e.g. Coder", id="recruit-name")
            yield Label("Role:")
            yield Input(placeholder="e.g. tickets, testing, frontend", id="recruit-role")
            yield Label("Orders:")
            yield Input(placeholder="e.g. keep an eye on T1001", id="recruit-orders")
            yield Label("Tier:")
            yield Select(tier_options(), value="warrior", allow_blank=False, id="recruit-tier")
            with Horizontal():
                yield Button("Recruit", variant="primary", id="recruit-submit")
                yield Button("Cancel", id="recruit-cancel")

    def on_mount(self) -> None:
        err = self.query_one("#recruit-error", Static)
        err.display = False

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "recruit-prompt":
            self._ask()
        else:
            self._submit()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "recruit-submit":
            self._submit()
        elif event.button.id == "recruit-ask":
            self._ask()
        else:
            self.dismiss(None)

    def _ask(self) -> None:
        prompt = self.query_one("#recruit-prompt", Input).value.strip()
        if not prompt:
            err = self.query_one("#recruit-error", Static)
            err.update("describe what the ork should do")
            err.display = True
            return
        self.dismiss(prompt)

    def _submit(self) -> None:
        name = self.query_one("#recruit-name", Input).value.strip()
        role = self.query_one("#recruit-role", Input).value.strip()
        orders = self.query_one("#recruit-orders", Input).value.strip()
        tier = str(self.query_one("#recruit-tier", Select).value) or None
        b_id = self.building_id or getattr(self.app.focus_state, "building_id", "")
        err = self.query_one("#recruit-error", Static)
        try:
            orc = scroll.recruit(self.app.scroll, b_id, name, role=role, orders=orders, tier=tier)
        except ValueError as e:
            err.update(str(e))
            err.display = True
            return
        self.dismiss(orc)


class OrcModelModal(ModalScreen["list[dict] | None"]):
    """The 🎒 inventory's model button: harness and tier per step. Dismisses the new harness
    steps (a tier replaces a model named outright), or None."""

    BINDINGS = [Binding("escape", "dismiss(None)", "Cancel")]
    DEFAULT_CSS = MODAL_CSS.replace("GarrisonModal", "OrcModelModal") + """
OrcModelModal .model-row { margin-top: 0; }
OrcModelModal .model-row Select { width: 1fr; }
"""

    def __init__(self, orc_name: str, harness: list[dict]) -> None:
        super().__init__()
        self.orc_name = orc_name
        self.steps = [dict(s) for s in harness]

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label(f"🎒 {self.orc_name} — model and tier", classes="order-title")
            for i, step in enumerate(self.steps):
                harness = str(step.get("harness", "claude"))
                if harness not in scroll.HARNESSES:           # a pipeline keeps its own models
                    yield Label(f"{step.get('role', 'run')}: {harness}", classes="order-hint")
                    continue
                current = tiers.step_tier(step) if (step.get("tier") or step.get("model")) else ""
                yield Label(f"{step.get('role', 'run')}:")
                with Horizontal(classes="model-row"):
                    yield Select([(h, h) for h in scroll.HARNESSES], value=harness,
                                 allow_blank=False, id=f"step-harness-{i}")
                    yield Select(tier_options(), value=current or "", allow_blank=False, id=f"step-tier-{i}")
            with Horizontal():
                yield Button("Save", variant="primary", id="model-save")
                yield Button("Cancel", id="model-cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id != "model-save":
            self.dismiss(None)
            return
        out = []
        for i, step in enumerate(self.steps):
            if not self.query(f"#step-harness-{i}"):
                out.append(step)
                continue
            harness = str(self.query_one(f"#step-harness-{i}", Select).value)
            tier = str(self.query_one(f"#step-tier-{i}", Select).value) or None
            out += tiers.with_tier([{**step, "harness": harness}], tier)
        self.dismiss(out)
