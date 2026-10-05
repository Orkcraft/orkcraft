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


class ReworkModal(ModalScreen[tuple[str, str] | None]):
    """↩ Why does the cart go back? A chip (1–6, or a click) picks the reason and moves to the note;
    Enter sends it — the chip alone is enough, a note alone too. Dismisses (tag, reason) or None."""
    BINDINGS = [Binding("escape", "cancel", "Cancel")] + \
        [Binding(str(i), f"pick('{tag}')", show=False) for i, (tag, _, _) in enumerate(feedback.REASONS, 1)]
    DEFAULT_CSS = MODAL_CSS.format(cls="ReworkModal", border_color="$warning", title_color="$warning") + """
    ReworkModal .rework-chips { height: auto; }
    ReworkModal .rework-chips Button { min-width: 10; margin-right: 1; }
    """
    AUTO_FOCUS = "#rework-wrong"            # 1–6 pick at once; Tab reaches the note

    def __init__(self, title: str, help: str = "") -> None:
        super().__init__()
        self.heading, self.help, self.tag = title, help, ""

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label(self.heading, classes="build-title")
            if self.help:
                yield Static(Text(self.help, style="dim"), classes="build-text")
            chips = list(feedback.REASONS)
            for row in (chips[:3], chips[3:]):
                with Horizontal(classes="rework-chips"):
                    for tag, label, _ in row:
                        yield Button(f"{chips.index((tag, label, _)) + 1} · {label}", id=f"rework-{tag}")
            yield Input(placeholder="what to fix (optional with a reason picked) — Enter sends", id="rework-note")
            with Horizontal():
                yield Button("Send back", variant="warning", id="rework-send")
                yield Button("Cancel", id="rework-cancel")

    def reason(self) -> str:
        note = self.query_one("#rework-note", Input).value.strip()
        label = next((lbl for t, lbl, _ in feedback.REASONS if t == self.tag), "")
        return f"{label}: {note}" if label and note else (label or note)

    def action_pick(self, tag: str) -> None:
        self.tag = tag
        for t, _, _ in feedback.REASONS:
            self.query_one(f"#rework-{t}", Button).variant = "warning" if t == tag else "default"
        self.query_one("#rework-note", Input).focus()

    def action_send(self) -> None:
        if reason := self.reason():
            self.dismiss((self.tag, reason))

    def action_cancel(self) -> None:
        self.dismiss(None)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        event.stop()
        self.action_send()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        bid = event.button.id or ""
        if bid == "rework-cancel":
            self.action_cancel()
        elif bid == "rework-send":
            self.action_send()
        elif bid.startswith("rework-"):
            self.action_pick(bid[len("rework-"):])
