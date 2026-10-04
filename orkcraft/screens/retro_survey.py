"""🗓 The Town retro's survey: a few results of the week, one card at a time — were they good?

👍 keeps the result as a reference; 👎 asks, as `F` does, whether its inputs were broken (its
suppliers pay, upstream) or its own logic (only it pays); Skip records nothing. Esc ends the survey
with what was answered. Dismisses [(sample, "good" | "inputs" | "logic")].
"""
from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label, Static

from orkcraft.realm import retro
from orkcraft.screens.build_flow import MODAL_CSS


class RetroSurveyModal(ModalScreen[list[tuple[retro.Sample, str]]]):
    BINDINGS = [Binding("escape", "finish", "Done"), Binding("1", "answer('good')", show=False),
                Binding("2", "answer('inputs')", show=False), Binding("3", "answer('logic')", show=False),
                Binding("4", "answer('skip')", show=False)]
    DEFAULT_CSS = MODAL_CSS.format(cls="RetroSurveyModal", border_color="$accent", title_color="$accent") + """
    RetroSurveyModal > Vertical { width: 110; }
    """

    def __init__(self, samples: list[retro.Sample], titles: dict[str, str] | None = None) -> None:
        super().__init__()
        self.samples, self.titles = samples, titles or {}
        self.at = 0
        self.answers: list[tuple[retro.Sample, str]] = []

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label(f"🗓 Town retro — {len(self.samples)} result(s) of the week, were they good?",
                        classes="build-title")
            yield Static("", id="survey-card", classes="build-text")
            with Horizontal():
                yield Button("1 · 👍 Good", variant="success", id="survey-good")
                yield Button("2 · 👎 Broken inputs", variant="warning", id="survey-inputs")
                yield Button("3 · 👎 Its logic", variant="error", id="survey-logic")
                yield Button("4 · Skip", id="survey-skip")

    def on_mount(self) -> None:
        self._show()

    def card(self) -> Text:
        s = self.samples[self.at]
        t = Text()
        t.append(f"{self.at + 1}/{len(self.samples)}  ", style="dim")
        t.append(self.titles.get(s.building, s.building), style="bold")
        when = s.ts[:16].replace("T", " ")
        t.append(f" · {when}" + (f" · {s.why}" if s.why else "") + (f" · {s.outcome}" if s.outcome != "done" else ""),
                 style="dim")
        t.append("\n  in   ", style="bold")
        t.append(s.input or "—")
        t.append("\n  out  ", style="bold")
        t.append(s.output or "—")
        return t

    def _show(self) -> None:
        if self.at >= len(self.samples):
            self.dismiss(self.answers)
            return
        self.query_one("#survey-card", Static).update(self.card())

    def action_answer(self, kind: str) -> None:
        if self.at >= len(self.samples):
            return
        if kind != "skip":
            self.answers.append((self.samples[self.at], kind))
        self.at += 1
        self._show()

    def action_finish(self) -> None:
        self.dismiss(self.answers)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        self.action_answer((event.button.id or "survey-skip").split("-", 1)[1])
