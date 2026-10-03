"""🧾 What the orcs changed by themselves (realm/evolution.py): shown when quiet hours end, after a
probation revert, and from F10.

    ChangesModal(changes, titles)    dismisses the id of a change to take back (z), or None

Each row: when, the building, what changed and why, and where it stands — 🧪 on probation until
<time>, ✓ kept, ↩ taken back (and why), ⚠ stuck (changed since: Z on the building decides).
"""
from __future__ import annotations

import datetime as dt

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label, OptionList, Static
from textual.widgets.option_list import Option

from orkcraft.realm.evolution import Change
from orkcraft.screens.build_flow import MODAL_CSS

MARKS = {"probation": ("🧪", "yellow"), "kept": ("✓", "green"), "reverted": ("↩", "dim"), "stuck": ("⚠", "bold red")}


def status_text(c: Change, now: dt.datetime | None = None) -> str:
    if c.status == "probation":
        left = c.until - (now or dt.datetime.now())
        hours = max(0, int(left.total_seconds() // 3600))
        return f"on probation for {hours} h more"
    return {"kept": "kept", "reverted": f"taken back — {c.note}", "stuck": c.note or "stuck"}.get(c.status, c.status)


def row(c: Change, title: str) -> Text:
    mark, style = MARKS.get(c.status, ("·", ""))
    t = Text()
    t.append(f"{mark} ", style=style)
    t.append(f"{c.ts[5:16].replace('T', ' ')}  ", style="dim")
    t.append(f"{title}", style="bold")
    t.append(f" · {c.summary}")
    t.append(f"  ({c.source})", style="dim")
    return t


class ChangesModal(ModalScreen[str | None]):
    BINDINGS = [Binding("escape", "close", "Close"), Binding("enter", "close", "Close", show=False),
                Binding("z", "take_back", "Take back")]
    DEFAULT_CSS = MODAL_CSS.format(cls="ChangesModal", border_color="$accent", title_color="$accent") + """
    ChangesModal > Vertical { width: 100; }
    ChangesModal #ch-list { height: auto; max-height: 14; border: solid $surface-lighten-2; }
    ChangesModal #ch-detail { height: auto; margin-top: 1; }
    ChangesModal .ch-buttons { height: auto; margin-top: 1; align-horizontal: right; }
    ChangesModal .ch-buttons Button { margin-left: 1; }
    """

    def __init__(self, changes: list[Change], titles: dict[str, str] | None = None) -> None:
        super().__init__()
        self.changes = changes
        self.titles = titles or {}

    def compose(self) -> ComposeResult:
        with Vertical():
            n = len(self.changes)
            yield Label(f"🧾 What the orcs changed by themselves ({n})" if n else "🧾 The orcs changed nothing",
                        classes="build-title")
            lst = OptionList(id="ch-list")
            for c in self.changes:
                lst.add_option(Option(row(c, self.titles.get(c.building, c.building)), id=c.id))
            yield lst
            yield Static("", id="ch-detail", markup=False)
            yield Static("Each change has its own checkpoint. On probation for 24 h: a 👎 on the building or more "
                         "failed runs take it back by itself.", classes="build-hint")
            with Horizontal(classes="ch-buttons"):
                yield Button("Take back [z]", id="ch-back", variant="warning")
                yield Button("Close", id="ch-close", variant="primary")

    def on_mount(self) -> None:
        lst = self.query_one("#ch-list", OptionList)
        if self.changes:
            lst.highlighted = 0
            lst.focus()
        self._detail()

    @property
    def selected(self) -> Change | None:
        lst = self.query_one("#ch-list", OptionList)
        if lst.highlighted is None or not self.changes:
            return None
        return self.changes[lst.highlighted]

    def _detail(self) -> None:
        c = self.selected
        detail = self.query_one("#ch-detail", Static)
        back = self.query_one("#ch-back", Button)
        if c is None:
            detail.update("")
            back.display = False
            return
        t = Text()
        t.append(f"{self.titles.get(c.building, c.building)} — {c.change}\n", style="bold")
        if c.why:
            t.append(f"why: {c.why}\n")
        t.append(status_text(c), style=MARKS.get(c.status, ("", ""))[1])
        detail.update(t)
        back.display = c.status in ("probation", "kept", "stuck")

    def on_option_list_option_highlighted(self, event: OptionList.OptionHighlighted) -> None:
        event.stop()
        self._detail()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        event.stop()
        self.action_close()

    def action_take_back(self) -> None:
        c = self.selected
        if c is not None and c.status in ("probation", "kept", "stuck"):
            self.dismiss(c.id)

    def action_close(self) -> None:
        self.dismiss(None)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        if event.button.id == "ch-back":
            self.action_take_back()
        else:
            self.action_close()
