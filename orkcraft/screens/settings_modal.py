"""⚙ Self-improvement settings: the models and the schedules.

    fast_llm / fast_model    the Council's Fast Path: a light model on top of the rules
    optimize_at              the daily local proposal
    weekly_model / weekly_at the weekly self-audit
Dismisses the values to save, or None.
"""
from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Static, Switch

from orkcraft.screens.build_flow import MODAL_CSS

FIELDS = (("fast_model", "Fast Path model (light)", "haiku"), ("optimize_at", "Daily proposal at", "daily 06:20"),
          ("weekly_model", "Weekly self-audit model (heavy)", "opus"), ("weekly_at", "Weekly self-audit at",
                                                                          "weekly sun 05:00"))


class SettingsModal(ModalScreen[dict | None]):
    BINDINGS = [Binding("escape", "cancel", "Cancel"), Binding("ctrl+s", "save", "Save", priority=True)]
    DEFAULT_CSS = MODAL_CSS.format(cls="SettingsModal", border_color="$accent", title_color="$accent") + """
    SettingsModal .set-row { height: 3; }
    SettingsModal .set-row Label { width: 34; padding-top: 1; }
    SettingsModal .set-row Input { width: 1fr; }
    #set-errors { color: $error; height: auto; }
    """

    def __init__(self, values: dict) -> None:
        super().__init__()
        self.values = dict(values)

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label("⚙ Self-improvement — models and schedules", classes="build-title")
            with Horizontal(classes="set-row"):
                yield Label("Fast Path asks a light model")
                yield Switch(value=bool(self.values.get("fast_llm", True)), id="set-fast_llm")
            for key, label, placeholder in FIELDS:
                with Horizontal(classes="set-row"):
                    yield Label(label)
                    yield Input(str(self.values.get(key) or ""), placeholder=placeholder, id=f"set-{key}")
            yield Static("schedules: every 15m · hourly · daily 05:00 · weekly sun 05:00 · a 5-field cron; empty "
                         "switches it off", classes="build-hint")
            yield Static("", id="set-errors", markup=False)
            with Horizontal():
                yield Button("Save [ctrl+s]", variant="success", id="set-save")
                yield Button("Cancel", id="set-cancel")

    def action_save(self) -> None:
        from orkcraft.realm import watch
        out = {"fast_llm": self.query_one("#set-fast_llm", Switch).value}
        problems = []
        for key, label, _ in FIELDS:
            value = self.query_one(f"#set-{key}", Input).value.strip()
            if key.endswith("_at") and value and not watch.schedule_ok(value):
                problems.append(f"{label}: not a schedule")
            if key.endswith("_model") and not value:
                problems.append(f"{label}: name a model (haiku, sonnet, opus…)")
            out[key] = value
        if problems:
            self.query_one("#set-errors", Static).update("\n".join(f"⚠ {p}" for p in problems))
            return
        self.dismiss(out)

    def action_cancel(self) -> None:
        self.dismiss(None)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        if event.button.id == "set-save":
            self.action_save()
        else:
            self.action_cancel()
