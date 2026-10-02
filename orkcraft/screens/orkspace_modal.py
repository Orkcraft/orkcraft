"""Modal screen for creating a new orkspace (name + biome)."""
from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, RadioButton, RadioSet, Static

from orkcraft import scroll
from orkcraft.scroll import TownScroll


class OrkspaceModal(ModalScreen[str | None]):
    """Dialog to create a new orkspace (canvas)."""

    DEFAULT_CSS = """
    OrkspaceModal {
        align: center middle;
    }
    #orkspace-dialog {
        width: 55;
        height: auto;
        border: thick $accent;
        background: $surface;
        padding: 1 2;
    }
    #orkspace-title {
        text-style: bold;
        color: $accent;
        padding-bottom: 1;
    }
    #orkspace-name {
        margin-bottom: 1;
    }
    #biome-set {
        background: transparent;
        border: none;
        margin-bottom: 1;
    }
    #orkspace-error {
        color: $error;
        margin-bottom: 1;
        display: none;
    }
    #orkspace-buttons {
        width: 100%;
        height: auto;
        align-horizontal: right;
    }
    #orkspace-buttons > Button {
        margin-left: 1;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]

    def __init__(self, scroll_data: TownScroll) -> None:
        super().__init__()
        self.scroll_data = scroll_data

    def compose(self) -> ComposeResult:
        with Vertical(id="orkspace-dialog"):
            yield Static("─── ⛺ NEW ORKSPACE ───", id="orkspace-title")
            yield Static("Orkspace Name:", classes="label")
            yield Input(placeholder="e.g. Auth Core, Scratch Lab", id="orkspace-name")
            yield Static("Biome (Terrain):", classes="label")
            with RadioSet(id="biome-set"):
                yield RadioButton("void", id="biome-void")
                yield RadioButton("forest", id="biome-forest", value=True)
                yield RadioButton("ice", id="biome-ice")
            yield Static("", id="orkspace-error", markup=False)
            with Horizontal(id="orkspace-buttons"):
                yield Button("Cancel", variant="default", id="cancel-btn")
                yield Button("Create", variant="primary", id="create-btn")

    def on_mount(self) -> None:
        self.query_one("#orkspace-name", Input).focus()

    def _selected_biome(self) -> str:
        radio_set = self.query_one("#biome-set", RadioSet)
        pressed = radio_set.pressed_button
        if pressed is not None:
            text = str(pressed.label).lower().strip()
            if text in scroll.BIOMES:
                return text
        return "forest"

    def submit(self) -> None:
        name = self.query_one("#orkspace-name", Input).value.strip()
        biome = self._selected_biome()
        err_widget = self.query_one("#orkspace-error", Static)
        try:
            ork = scroll.new_orkspace(self.scroll_data, name, biome=biome)
            self.dismiss(ork.id)
        except ValueError as e:
            err_widget.update(str(e))
            err_widget.display = True

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.submit()
        event.stop()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "create-btn":
            self.submit()
        else:
            self.dismiss(None)
        event.stop()

    def action_cancel(self) -> None:
        self.dismiss(None)
