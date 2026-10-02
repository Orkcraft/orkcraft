"""Modal dialogs for orkcraft: a message box, a one-line prompt, a block of lines and a yes / no."""
from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.binding import Binding
from textual.widgets import Button, Input, Label, Static, TextArea


class MessageModal(ModalScreen[None]):
    """Generic alert/information modal."""

    DEFAULT_CSS = """
    MessageModal {
        align: center middle;
    }
    .msg-box {
        width: 55;
        height: auto;
        border: thick $primary;
        background: $surface;
        padding: 1 2;
    }
    .msg-title {
        text-style: bold;
        margin-bottom: 1;
        text-align: center;
    }
    .msg-content {
        margin-bottom: 1;
    }
    .msg-btn {
        width: 100%;
        align: center middle;
    }
    """

    def __init__(
        self,
        title: str,
        message: str,
        is_error: bool = False,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
        disabled: bool = False,
    ) -> None:
        super().__init__(name=name, id=id, classes=classes)
        self.disabled = disabled
        self.dialog_title = title
        self.message = message
        self.is_error = is_error

    def compose(self) -> ComposeResult:
        border_class = "error" if self.is_error else "primary"
        with Vertical(classes="msg-box"):
            yield Label(self.dialog_title, classes=f"msg-title text-{border_class}")
            yield Static(self.message, classes="msg-content")
            with Horizontal(classes="msg-btn"):
                yield Button("OK", variant="primary", id="btn-ok")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(None)


class TextPrompt(ModalScreen[str | None]):
    """One line of text: Enter keeps it, Esc cancels. `fields` adds more lines (returned joined by \\t)."""

    BINDINGS = [Binding("escape", "cancel", "Cancel")]
    DEFAULT_CSS = """
    TextPrompt { align: center middle; }
    #prompt-box { width: 70; height: auto; border: thick $accent; background: $surface; padding: 1 2; }
    #prompt-title { text-style: bold; margin-bottom: 1; }
    #prompt-help { color: $text-muted; }
    """

    def __init__(self, title: str, value: str = "", placeholder: str = "", help: str = "",
                 fields: tuple[tuple[str, str], ...] = ()) -> None:
        super().__init__()
        self.prompt_heading, self.prompt_value, self.prompt_placeholder, self.prompt_help = title, value, placeholder, help
        self.prompt_fields = fields          # (placeholder, value) of extra lines

    def compose(self) -> ComposeResult:
        with Vertical(id="prompt-box"):
            yield Label(self.prompt_heading, id="prompt-title")
            yield Input(self.prompt_value, placeholder=self.prompt_placeholder, id="prompt-input")
            for i, (ph, val) in enumerate(self.prompt_fields):
                yield Input(val, placeholder=ph, id=f"prompt-field-{i}")
            if self.prompt_help:
                yield Static(self.prompt_help, id="prompt-help")

    AUTO_FOCUS = "#prompt-input"

    def on_input_submitted(self, event: Input.Submitted) -> None:
        inputs = [self.query_one("#prompt-input", Input)] + [self.query_one(f"#prompt-field-{i}", Input)
                                                             for i in range(len(self.prompt_fields))]
        idx = inputs.index(event.input) if event.input in inputs else 0
        if idx + 1 < len(inputs):
            inputs[idx + 1].focus()
            return
        values = [i.value.strip() for i in inputs]
        self.dismiss("\t".join(values) if self.prompt_fields else values[0])

    def action_cancel(self) -> None:
        self.dismiss(None)


class TextBlock(ModalScreen[str | None]):
    """Several lines (steps, rules): ctrl+s keeps them, Esc cancels."""

    BINDINGS = [Binding("escape", "cancel", "Cancel"), Binding("ctrl+s", "save", "Save")]
    DEFAULT_CSS = """
    TextBlock { align: center middle; }
    #block-box { width: 90; height: 24; border: thick $accent; background: $surface; padding: 1 2; }
    #block-title { text-style: bold; }
    #block-help { color: $text-muted; height: auto; }
    #block-text { height: 1fr; }
    """
    AUTO_FOCUS = "#block-text"

    def __init__(self, title: str, text: str = "", help: str = "") -> None:
        super().__init__()
        self.block_heading, self.block_text, self.block_help = title, text, help

    def compose(self) -> ComposeResult:
        with Vertical(id="block-box"):
            yield Label(f"{self.block_heading}   (ctrl+s saves)", id="block-title")
            if self.block_help:
                yield Static(self.block_help, id="block-help", markup=False)
            yield TextArea(self.block_text, id="block-text")

    def action_save(self) -> None:
        self.dismiss(self.query_one("#block-text", TextArea).text)

    def action_cancel(self) -> None:
        self.dismiss(None)


class Confirm(ModalScreen[bool]):
    """Yes (y / Enter) or no (n / Esc)."""

    BINDINGS = [Binding("y", "yes", "Yes"), Binding("enter", "yes", "Yes"), Binding("n", "no", "No"),
                Binding("escape", "no", "No")]
    DEFAULT_CSS = """
    Confirm { align: center middle; }
    #confirm-box { width: 70; height: auto; border: thick $warning; background: $surface; padding: 1 2; }
    #confirm-title { text-style: bold; margin-bottom: 1; }
    """

    def __init__(self, title: str, text: str = "") -> None:
        super().__init__()
        self.confirm_heading, self.confirm_text = title, text

    def compose(self) -> ComposeResult:
        with Vertical(id="confirm-box"):
            yield Label(self.confirm_heading, id="confirm-title")
            if self.confirm_text:
                yield Static(self.confirm_text, markup=False)
            yield Static("[y] yes   [n] no", id="confirm-keys")

    def action_yes(self) -> None:
        self.dismiss(True)

    def action_no(self) -> None:
        self.dismiss(False)

