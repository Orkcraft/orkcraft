"""Road modals: subscribe a receiver to a source (event × handler), change a road's handler."""
from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import OptionList, Static
from textual.widgets.option_list import Option

PLAIN = "-"   # option id of "no handler"
RULE = "+rule"   # a road with a rule: the Recruiter makes its handler
WORDS = "+words"   # a road in words: the receiver's steward finds it (realm/road_planner.py)


class _PickModal(ModalScreen):
    """A titled list; Enter picks the highlighted row, Esc cancels (dismisses None)."""

    DEFAULT_CSS = """
    _PickModal { align: center middle; }
    #road-dialog {
        width: 72; height: auto; max-height: 80%;
        border: thick $accent; background: $surface; padding: 1 2;
    }
    #road-title { text-style: bold; color: $accent; padding-bottom: 1; }
    #road-list { height: auto; max-height: 14; background: transparent; border: none; }
    #road-footer { color: $text-muted; padding-top: 1; }
    """
    BINDINGS = [Binding("escape", "cancel", "Cancel")]

    def __init__(self, title: str, options: list[tuple[str, str]], footer: str) -> None:
        super().__init__()
        self.title_text, self.options, self.footer = title, options, footer

    def compose(self) -> ComposeResult:
        with Vertical(id="road-dialog"):
            yield Static(self.title_text, id="road-title", markup=False)
            yield OptionList(id="road-list")
            yield Static(self.footer, id="road-footer", markup=False)

    def on_mount(self) -> None:
        lst = self.query_one("#road-list", OptionList)
        for oid, label in self.options:
            lst.add_option(Option(Text(label), id=oid))
        if lst.option_count:
            lst.highlighted = 0
        lst.focus()

    def action_cancel(self) -> None:
        self.dismiss(None)

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        event.stop()
        self.dismiss(self.result_for(event.option_id or ""))

    def result_for(self, option_id: str):
        return option_id or None


class SubscribeModal(_PickModal):
    """Which event of the source, and which handler (or none) on the receiver.
    Dismisses `(event, handler_id | None)` or None."""

    def __init__(self, source_title: str, target_title: str, choices: list[tuple[str, str | None, str]]) -> None:
        # choices: (event, handler id or None, row label)
        self.choices = {f"{event}|{handler or PLAIN}": (event, handler) for event, handler, _ in choices}
        super().__init__(f"🛤 ROAD · {source_title} → {target_title}",
                         [(f"{event}|{handler or PLAIN}", label) for event, handler, label in choices],
                         "[Enter] Subscribe   [Esc] Cancel")

    def result_for(self, option_id: str):
        return self.choices.get(option_id)


class RoadHandlerModal(_PickModal):
    """Put a handler on a road, or none. Dismisses the handler id, PLAIN, or None (cancel)."""

    def __init__(self, road_title: str, handlers: list[tuple[str, str]], current: str | None) -> None:
        options = [(PLAIN, ("● " if current is None else "  ") + "plain (no handler)")]
        options += [(hid, ("● " if hid == current else "  ") + label) for hid, label in handlers]
        super().__init__(f"🔀 HANDLER · {road_title}", options, "[Enter] Pick   [Esc] Cancel")


class RoadPlanModal(_PickModal):
    """The roads the steward offers for what was said: (say, how) rows. Dismisses the index, or None."""

    def __init__(self, source_title: str, target_title: str, options: list[tuple[str, str]], cost: str = "") -> None:
        super().__init__(f"💬 ROAD · {source_title} → {target_title}",
                         [(str(i), f"{say}\n   {how}") for i, (say, how) in enumerate(options)],
                         "[Enter] Lay it   [Esc] Cancel" + (f"   · {cost}" if cost else ""))

    def result_for(self, option_id: str):
        return int(option_id) if option_id.isdigit() else None
