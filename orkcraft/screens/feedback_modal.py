"""👎 What went wrong? — the questionnaire behind a dislike.

1 the inputs were broken → its suppliers pay, upstream along the roads that delivered
2 its own logic was wrong → only this building pays
A note goes into the incident. Dismisses (kind, note) or None.
"""
from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Static

from orkcraft.realm import feedback
from orkcraft.screens.build_flow import MODAL_CSS


class DislikeModal(ModalScreen[tuple[str, str] | None]):
    BINDINGS = [Binding("escape", "cancel", "Cancel"), Binding("1", "pick('inputs')", show=False),
                Binding("2", "pick('logic')", show=False)]
    DEFAULT_CSS = MODAL_CSS.format(cls="DislikeModal", border_color="$error", title_color="$error")
    AUTO_FOCUS = "#dislike-inputs"          # 1 / 2 pick at once; Tab reaches the note

    def __init__(self, title: str, output: str, suppliers: list[tuple[str, float]]) -> None:
        super().__init__()
        self.heading, self.output, self.suppliers = title, output, suppliers   # (title, penalty)

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label(f"👎 {self.heading} — what went wrong?", classes="build-title")
            yield Static(Text(self.output[:600] or "(no result recorded yet)", style="dim"), classes="build-text")
            who = ", ".join(f"{t} −{p:g}" for t, p in self.suppliers) or "nobody feeds it — only it pays"
            yield Static(Text(f"[1] {feedback.KINDS['inputs']}\n    → {who}\n"
                              f"[2] {feedback.KINDS['logic']}\n    → only {self.heading} −1"), classes="build-text")
            yield Input(placeholder="a note for the incident (optional)", id="dislike-note")
            with Horizontal():
                yield Button("1 · Broken inputs", variant="warning", id="dislike-inputs")
                yield Button("2 · Its logic", variant="error", id="dislike-logic")
                yield Button("Cancel", id="dislike-cancel")

    def action_pick(self, kind: str) -> None:
        self.dismiss((kind, self.query_one("#dislike-note", Input).value))

    def action_cancel(self) -> None:
        self.dismiss(None)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        event.stop()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        if event.button.id == "dislike-inputs":
            self.action_pick("inputs")
        elif event.button.id == "dislike-logic":
            self.action_pick("logic")
        else:
            self.action_cancel()
