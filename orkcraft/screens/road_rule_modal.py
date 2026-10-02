"""🛤 A road with a rule: one or several events of the source, and how to handle them.

The Recruiter makes the handler from the prompt (a chain or a script when the rule needs no
judgement), then the Council reviews it. A rejection comes back here with the prompt emptied.
Dismisses (events, prompt) or None.
"""
from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label, SelectionList, Static, TextArea

from orkcraft.screens.build_flow import MODAL_CSS


class RoadRuleModal(ModalScreen[tuple[list[str], str] | None]):
    BINDINGS = [Binding("escape", "cancel", "Cancel"), Binding("ctrl+s", "go", "Continue", priority=True)]
    DEFAULT_CSS = MODAL_CSS.format(cls="RoadRuleModal", border_color="$accent", title_color="$accent") + """
    RoadRuleModal > Vertical { width: 90; }
    RoadRuleModal SelectionList { height: auto; max-height: 8; }
    RoadRuleModal TextArea { height: 6; }
    #rule-errors { color: $error; height: auto; }
    """
    AUTO_FOCUS = "#rule-prompt"

    def __init__(self, source_title: str, target_title: str, events: list[tuple[str, str]],
                 picked: list[str] | None = None, note: str = "") -> None:
        super().__init__()
        self.source_title, self.target_title = source_title, target_title
        self.events, self.picked, self.note = events, set(picked or [e for e, _ in events[:1]]), note

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label(f"🛤 {self.source_title} → {self.target_title} — a listener with a prompt", classes="build-title")
            yield Label("Which events should it hear?", classes="build-section")
            yield SelectionList(*[(label, ev, ev in self.picked) for ev, label in self.events], id="rule-events")
            yield Label("How should it handle them?", classes="build-section")
            yield TextArea("", id="rule-prompt")
            yield Static("filter, reformat, count → a chain or a script · summarise, classify → an agent",
                         classes="build-hint")
            yield Static(self.note, id="rule-errors", markup=False)
            with Horizontal():
                yield Button("Continue → review [ctrl+s]", variant="success", id="rule-go")
                yield Button("Cancel", id="rule-cancel")

    def action_go(self) -> None:
        events = list(self.query_one("#rule-events", SelectionList).selected)
        prompt = self.query_one("#rule-prompt", TextArea).text.strip()
        problems = (["pick at least one event"] if not events else []) + \
            (["say in a few words what to do with each cart"] if len(prompt) < 5 else [])
        if problems:
            self.query_one("#rule-errors", Static).update("\n".join(f"⚠ {p}" for p in problems))
            return
        self.dismiss((events, prompt))

    def action_cancel(self) -> None:
        self.dismiss(None)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        if event.button.id == "rule-go":
            self.action_go()
        else:
            self.action_cancel()
