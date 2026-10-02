"""Build flow modal screens for custom buildings (Mason & Artisan).

Includes:
- `BuildProgress`: modal with spinner indicating Mason and Artisan are generating the spec
- `BuildPreview`: modal showing validated spec details before raising
- `BuildFailed`: modal displaying build/validation errors with option to retry
"""
from __future__ import annotations

import json
from typing import TYPE_CHECKING

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Label, LoadingIndicator, Static

if TYPE_CHECKING:
    from orkcraft.realm.builders import BuildResult


MODAL_CSS = """
{cls} {{
    align: center middle;
}}
{cls} > Vertical {{
    width: 76;
    max-width: 95%;
    height: auto;
    max-height: 90%;
    border: thick {border_color};
    background: $surface;
    padding: 1 2;
}}
{cls} .build-title {{
    text-style: bold;
    color: {title_color};
    margin-bottom: 1;
}}
{cls} .build-section {{
    margin-top: 1;
    text-style: bold;
    color: $secondary;
}}
{cls} .build-text {{
    color: $text;
}}
{cls} .build-hint {{
    color: $text-muted;
    margin-top: 1;
}}
{cls} Horizontal {{
    height: auto;
    margin-top: 1;
}}
{cls} Button {{
    margin-right: 1;
}}
"""


class BuildProgress(ModalScreen[None]):
    """Modal shown while Mason & Artisan are running in a background worker."""

    BINDINGS = [
        Binding("escape", "dismiss(None)", "Hide"),
    ]
    DEFAULT_CSS = """
    BuildProgress {
        align: center middle;
    }
    #build-progress-box {
        width: 60;
        height: auto;
        border: thick $accent;
        background: $surface;
        padding: 1 2;
        align: center middle;
    }
    .build-progress-title {
        text-style: bold;
        color: $accent;
        margin-bottom: 1;
        text-align: center;
    }
    .build-progress-hint {
        color: $text-muted;
        margin-top: 1;
        text-align: center;
    }
    """

    def __init__(self, label: str = "🧱 Mason and 🎨 Artisan are at work…") -> None:
        super().__init__()
        self.label = label

    def compose(self) -> ComposeResult:
        with Vertical(id="build-progress-box"):
            yield Label(self.label, classes="build-progress-title")
            yield LoadingIndicator()
            yield Static("Esc hides it — the build keeps running", classes="build-progress-hint")


class BuildPreview(ModalScreen[bool]):
    """Preview a validated spec with attempts and cost before confirming raising."""

    BINDINGS = [
        Binding("enter", "confirm", "Raise"),
        Binding("escape", "cancel", "Discard"),
    ]
    DEFAULT_CSS = MODAL_CSS.format(cls="BuildPreview", border_color="$accent", title_color="$accent")

    def __init__(self, spec: dict, result: BuildResult) -> None:
        super().__init__()
        self.spec = spec
        self.result = result

    def compose(self) -> ComposeResult:
        spec = self.spec
        orc = spec.get("orc") or {}
        cost_str = f"${self.result.cost_usd:.2f}" if self.result.cost_usd is not None else "—"
        attempts_str = str(len(self.result.attempts))

        with Vertical():
            yield Label(Text(f"🏗️ Build Preview: {spec.get('icon', '')} {spec.get('title', '')} [{spec.get('id', '')}]"), classes="build-title")
            with VerticalScroll():
                yield Static(Text(f"Resident Orc: 🧌 {orc.get('name', 'Peon')} ({orc.get('role', '')})\n"
                                  f"Summary: {spec.get('summary', '')}\n"
                                  f"Attempts: {attempts_str}  ·  Cost: {cost_str}"), classes="build-text")

                yield Label("Data Sources:", classes="build-section")
                data_lines = []
                for d in spec.get("data", []):
                    params_str = json.dumps(d.get("params", {}), ensure_ascii=False)
                    data_lines.append(f"  • {d.get('name')}: {d.get('source')} ({params_str})")
                yield Static(Text("\n".join(data_lines) if data_lines else "  • none"), classes="build-text")

                yield Label("Panes & Layout:", classes="build-section")
                layout = spec.get("layout", {})
                direction = layout.get("direction", "vertical")
                pane_lines = [f"  Direction: {direction}"]
                for p in layout.get("panes", []):
                    p_title = p.get("title") or p.get("data")
                    ratio_str = f" [ratio {p.get('ratio')}]" if p.get("ratio") else ""
                    pane_lines.append(f"  • {p_title}: {p.get('widget')} → {p.get('data')}{ratio_str}")
                yield Static(Text("\n".join(pane_lines)), classes="build-text")

                actions = spec.get("actions", [])
                if actions:
                    yield Label("Command Card Actions:", classes="build-section")
                    act_lines = [f"  • [{a.get('key')}] {a.get('label')} → {a.get('action')}" for a in actions]
                    yield Static(Text("\n".join(act_lines)), classes="build-text")

            with Horizontal():
                yield Button("Raise [Enter]", variant="primary", id="btn-raise")
                yield Button("Discard [Esc]", id="btn-discard")
            yield Static("Enter raises the building · Esc discards it", classes="build-hint")

    def action_confirm(self) -> None:
        self.dismiss(True)

    def action_cancel(self) -> None:
        self.dismiss(False)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-raise":
            self.dismiss(True)
        else:
            self.dismiss(False)


class BuildFailed(ModalScreen[str | None]):
    """Modal showing failure details with a Try Again button."""

    BINDINGS = [
        Binding("escape", "dismiss(None)", "Close"),
    ]
    DEFAULT_CSS = MODAL_CSS.format(cls="BuildFailed", border_color="$error", title_color="$error")

    def __init__(self, result: BuildResult) -> None:
        super().__init__()
        self.result = result

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label("💥 Building Could Not Be Raised", classes="build-title")
            err_text = ""
            if self.result.error:
                err_text = self.result.error
            elif self.result.attempts and self.result.attempts[-1].errors:
                err_text = "\n".join(f"• {e}" for e in self.result.attempts[-1].errors)
            else:
                err_text = "Validation failed after maximum attempts."

            with VerticalScroll():
                yield Static(Text(err_text), classes="build-text")
                if self.result.cost_usd is not None:
                    yield Static(Text(f"Cost incurred: ${self.result.cost_usd:.2f}"), classes="build-hint")

            with Horizontal():
                yield Button("Try again", variant="primary", id="btn-try-again")
                yield Button("Close", id="btn-close")
            yield Static("Try again reopens prompt · Esc closes", classes="build-hint")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-try-again":
            self.dismiss("retry")
        else:
            self.dismiss(None)
