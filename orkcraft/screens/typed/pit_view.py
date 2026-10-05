"""🕳️ The Pit: drop, paste, done — the Scavenger sorts it and sends it on.

Dragging a file onto the terminal types its path; with the Pit selected (or open) that paste is a
drop. A pasted link or text lands too, and 📋 takes the clipboard. Everything is sorted by kind
and kept in `.orkcraft/pit/` (realm/pit.py), then goes down the road: `drop.file` with a path,
`pit.link` with the URL, `pit.text` with the text.

The sorting and sending are the building's worker's (core/workers/pit.py); the view draws its
history and takes the paste.
"""
from __future__ import annotations

from rich.text import Text
from textual import events
from textual.app import ComposeResult
from textual.widgets import Input, OptionList
from textual.widgets.option_list import Option

from orkcraft.core.workers.pit import PitWorker
from orkcraft.realm import pit
from orkcraft.screens.typed.base import TypedView


class _DropInput(Input):
    """A drag-and-drop types the path as one paste: that is the drop, no Enter needed."""

    async def _on_paste(self, event: events.Paste) -> None:
        event.stop()
        self.post_message(self.Submitted(self, event.text))


class PitView(TypedView):
    TYPE = "pit"
    UI_PANES = {"drop": "#drop-input", "history": "#drop-list", "chain": "#drop-list"}
    clipboard_reader = staticmethod(pit.clipboard)      # tests put a fake clipboard here

    @property
    def worker(self) -> PitWorker:
        return super().worker

    @property
    def items(self) -> list[pit.Item]:
        return self.worker.items

    def compose_body(self) -> ComposeResult:
        yield _DropInput(placeholder="drop a file, paste a link or text — or 📋 for the clipboard", id="drop-input")
        yield OptionList(id="drop-list")

    def refresh_data(self) -> None:
        self.worker.refresh()

    def redraw(self) -> None:
        try:
            lst = self.query_one("#drop-list", OptionList)
        except Exception:
            return
        lst.clear_options()
        for it in self.items:
            row = Text(no_wrap=True, overflow="ellipsis")
            row.append(it.at[5:16].replace("T", " ") + " ", style="dim")
            row.append(f"{pit.ICON.get(it.kind, '·')} {it.kind:<7} ", style="cyan")
            row.append(it.value if it.is_file else it.title)
            if it.copied:
                row.append("  (copied in)", style="dim")
            lst.add_option(Option(row))

    def drop(self, text: str) -> int:
        """Take what a paste or a drop brought. Returns how many items it made."""
        return self.worker.drop(text)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "drop-input":
            event.stop()
            if self.drop(event.value):
                event.input.value = ""

    def on_paste(self, event: events.Paste) -> None:
        """A drop on the open building that did not land in the input."""
        event.stop()
        self.drop(event.text)

    # -- the hut ----------------------------------------------------------------------------------

    def mini_status(self) -> list[str]:
        return self.worker.mini_status()

    def quick_action(self, action_id: str) -> bool:
        if action_id != "pit.paste":
            return False
        self.worker.paste(type(self).clipboard_reader())
        return True
