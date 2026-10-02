"""👻 The ghost of a building: the outline `[░░░]` of a hut that is not raised yet.

The operator walks it over the town with the arrows (shift: three cells at a time) or the mouse;
Enter or a click fixes the spot and the building is raised there; Esc cancels and nothing is
built. Over another hut the ghost turns red and will not settle.
"""
from __future__ import annotations

from rich.cells import cell_len
from rich.text import Text
from textual import events
from textual.binding import Binding
from textual.message import Message
from textual.widget import Widget

from orkcraft.wm import geometry as geo
from orkcraft.wm.geometry import Geom

STEP, BIG_STEP = 1, 3


class Ghost(Widget, can_focus=True):
    SCOPED_CSS = False
    DEFAULT_CSS = """
    Ghost { position: absolute; color: $text-muted; background: transparent; }
    Ghost.-blocked { color: $error; }
    """
    BINDINGS = [
        Binding("up", "nudge(0, -1)", "Up", show=False), Binding("down", "nudge(0, 1)", "Down", show=False),
        Binding("left", "nudge(-1, 0)", "Left", show=False), Binding("right", "nudge(1, 0)", "Right", show=False),
        Binding("shift+up", "nudge(0, -3)", show=False), Binding("shift+down", "nudge(0, 3)", show=False),
        Binding("shift+left", "nudge(-3, 0)", show=False), Binding("shift+right", "nudge(3, 0)", show=False),
        Binding("enter", "fix", "Build here"), Binding("escape", "cancel", "Cancel"),
    ]

    class Done(Message):
        """`geom` where it settled, or None when the operator cancelled."""
        def __init__(self, ghost: Ghost, geom: Geom | None) -> None:
            super().__init__()
            self.ghost = ghost
            self.geom = geom

    def __init__(self, label: str, start: Geom, room: tuple[int, int], taken: list[Geom]) -> None:
        super().__init__(id="ghost")
        self.label = label
        self.room = room
        self.taken = list(taken)
        self.geom = start
        self.styles.width, self.styles.height = start.w, start.h
        self.place(start)

    @property
    def blocked(self) -> bool:
        return any(geo.overlaps(self.geom, t, 1, 0) for t in self.taken)

    def place(self, g: Geom) -> None:
        w, h = self.room
        x = min(max(g.x, 0), max(w - g.w, 0))
        y = min(max(g.y, 0), max(h - g.h, 0))
        self.geom = Geom(x, y, g.w, g.h)
        self.styles.offset = (x, y)
        self.set_class(self.blocked, "-blocked")
        self.refresh()

    def render(self) -> Text:
        from orkcraft.widgets.hut import clip
        w, h = self.geom.w, self.geom.h
        out = Text(no_wrap=True, overflow="crop")
        label = clip(self.label, max(w - 2, 1))
        hint = "taken" if self.blocked else "⏎ build"
        rows = {max(h // 2 - 1, 0): label, min(h // 2 + 1, h - 1): hint} if h > 3 else {h // 2: label}
        for y in range(h):
            text = rows.get(y)
            if text is None or cell_len(text) > w - 2:
                out.append("░" * w, style="dim")
            else:
                pad = (w - cell_len(text)) // 2
                out.append("░" * pad, style="dim")
                out.append(text, style="bold")
                out.append("░" * (w - pad - cell_len(text)), style="dim")
            if y < h - 1:
                out.append("\n")
        return out

    # -- keys -----------------------------------------------------------------------------------

    def action_nudge(self, dx: int, dy: int) -> None:
        self.place(Geom(self.geom.x + dx, self.geom.y + dy, self.geom.w, self.geom.h))

    def action_fix(self) -> None:
        if self.blocked:
            self.app.bell()
            self.app.notify("another hut stands here — move the ghost", title="👻 Ghost")
            return
        self.post_message(self.Done(self, self.geom))

    def action_cancel(self) -> None:
        self.post_message(self.Done(self, None))

    # -- mouse: the ghost follows it, a click settles ---------------------------------------------

    def on_mouse_move(self, event: events.MouseMove) -> None:
        parent = self.parent.region if self.parent is not None else None
        if parent is None:
            return
        x = event.screen_x - parent.x - self.geom.w // 2
        y = event.screen_y - parent.y - self.geom.h // 2
        self.place(Geom(x, y, self.geom.w, self.geom.h))

    def on_mouse_down(self, event: events.MouseDown) -> None:
        event.stop()
        if event.button == 1:
            self.action_fix()
        else:
            self.action_cancel()
