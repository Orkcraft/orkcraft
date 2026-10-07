"""🕰 The day bar: 00:00 → 24:00, one cell per half hour, with the 🌙 quiet hours on it.

    DayBar(quiet=Span | None)
    bar.quiet                        the span as edited; posts DayBar.Changed on every edit

Colours: the day light (amber), 🌙 quiet dark purple.
A ▼ marks the time now. Edit with the mouse (drag across the bar: the quiet hours take the
dragged stretch) or the keys: Tab picks an edge (quiet start, quiet end), ←/→ move it by half an
hour, shift+←/→ move the whole span, Delete turns the quiet hours off.
"""
from __future__ import annotations

import datetime as dt

from rich.text import Text
from textual import events
from textual.binding import Binding
from textual.message import Message
from textual.widget import Widget

from orkcraft.schedule import DAY, STEP, Span, fmt

CELLS = DAY // STEP                 # 48
DAY_COLOR = "#c99a3e"               # the amber of a focused border (theme.py)
QUIET_COLOR = "#3b1f5c"
EDGE_COLOR = "#ffffff"


class DayBar(Widget, can_focus=True):
    DEFAULT_CSS = f"""
    DayBar {{ height: 4; width: {CELLS + 2}; padding: 0 1; }}
    DayBar:focus {{ background: $boost; }}
    """
    BINDINGS = [
        Binding("left", "move(-1)", "Earlier", show=False),
        Binding("right", "move(1)", "Later", show=False),
        Binding("shift+left", "shift(-1)", "Span earlier", show=False),
        Binding("shift+right", "shift(1)", "Span later", show=False),
        Binding("tab", "next_edge", "Next edge", show=False, priority=True),
        Binding("shift+tab", "prev_edge", "Previous edge", show=False, priority=True),
        Binding("delete", "quiet_off", "Quiet off", show=False),
        Binding("backspace", "quiet_off", "Quiet off", show=False),
    ]

    class Changed(Message):
        def __init__(self, bar: DayBar) -> None:
            super().__init__()
            self.bar = bar

    def __init__(self, quiet: Span | None = None, id: str | None = None) -> None:
        super().__init__(id=id)
        self.quiet = quiet
        self.edge = 0                      # index into edges()
        self._drag: int | None = None      # the cell a drag started on
        self.now: dt.datetime | None = None   # tests pin the clock

    # -- the model --------------------------------------------------------------------------------

    def edges(self) -> list[tuple[str, str]]:
        return [("quiet", "start"), ("quiet", "end")] if self.quiet is not None else []

    @property
    def selected(self) -> tuple[str, str] | None:
        edges = self.edges()
        return edges[self.edge % len(edges)] if edges else None

    def set_quiet(self, span: Span | None) -> None:
        self.quiet = span
        self.edge = 0
        self._changed()

    def _put(self, span: Span) -> None:
        self.quiet = span
        self._changed()

    def _changed(self) -> None:
        self.refresh()
        self.post_message(self.Changed(self))

    def color_at(self, cell: int) -> str:
        minute = cell * STEP
        if self.quiet is not None and self.quiet.contains(minute):
            return QUIET_COLOR
        return DAY_COLOR

    # -- drawing ----------------------------------------------------------------------------------

    def render(self) -> Text:
        now = self.now or dt.datetime.now()
        now_cell = (now.hour * 60 + now.minute) // STEP
        sel = self.selected
        sel_cell = None
        if sel is not None and self.has_focus:
            span = self.quiet
            if span is not None:
                sel_cell = (span.start if sel[1] == "start" else span.end - STEP) // STEP % CELLS
        t = Text()
        t.append(" " * now_cell + "▼\n", style="bold")
        for cell in range(CELLS):
            if cell == sel_cell:
                t.append("▌", style=f"{self.color_at(cell)} on {EDGE_COLOR}")
            else:
                t.append("█", style=self.color_at(cell))
        t.append("\n")
        ticks = "".join(f"{h:02d}".ljust(6) for h in range(0, 24, 3))
        t.append(ticks[:CELLS - 2] + "24\n", style="dim")
        if sel_cell is not None:
            span = self.quiet
            at = fmt(span.start if sel[1] == "start" else span.end)
            name = f"{sel[0]} {sel[1]} {at}"
            if sel_cell + 2 + len(name) <= CELLS:
                t.append(" " * sel_cell + "▲ " + name, style="bold")
            else:                                    # near the right end: the words go left of the mark
                t.append(" " * max(0, sel_cell - len(name) - 1) + name + " ▲", style="bold")
        return t

    # -- the mouse --------------------------------------------------------------------------------

    def _cell(self, x: int) -> int:
        return max(0, min(CELLS - 1, x))

    def _at(self, event: events.MouseEvent) -> tuple[int, int] | None:
        at = event.get_content_offset(self)
        return (at.x, at.y) if at is not None else None

    def on_mouse_down(self, event: events.MouseDown) -> None:
        at = self._at(event)
        if at is not None and at[1] == 1:               # the bar's row
            self._drag = self._cell(at[0])
            self.capture_mouse()
            self.focus()
            event.stop()

    def on_mouse_up(self, event: events.MouseUp) -> None:
        if self._drag is None:
            return
        at = self._at(event)
        x = at[0] if at is not None else event.x - 1    # captured: may be outside the content
        a, b = sorted((self._drag, self._cell(x)))
        self._drag = None
        self.release_mouse()
        span = Span.between(a * STEP, (b + 1) * STEP)
        if span is not None:
            self._put(span)
        event.stop()

    # -- the keys ---------------------------------------------------------------------------------

    def action_next_edge(self) -> None:
        edges = self.edges()
        if edges and self.edge < len(edges) - 1:
            self.edge += 1
            self.refresh()
        else:
            self.edge = 0
            self.screen.focus_next()

    def action_prev_edge(self) -> None:
        if self.edge > 0:
            self.edge -= 1
            self.refresh()
        else:
            self.screen.focus_previous()

    def action_move(self, steps: int) -> None:
        sel, span = self.selected, self.quiet
        if sel is None or span is None:
            return
        by = int(steps) * STEP
        moved = span.with_start(span.start + by) if sel[1] == "start" else span.with_end(span.end + by)
        if moved != span:
            self._put(moved)

    def action_shift(self, steps: int) -> None:
        if self.quiet is not None:
            self._put(self.quiet.shifted(int(steps) * STEP))

    def action_quiet_off(self) -> None:
        if self.quiet is not None:
            self.set_quiet(None)

    def on_focus(self) -> None:
        self.refresh()

    def on_blur(self) -> None:
        self.refresh()
