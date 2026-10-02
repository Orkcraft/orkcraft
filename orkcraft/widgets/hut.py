"""Hut: a building collapsed on the town map — its number and title on the fence,
the resident orc's state, an optional roof, live status lines and up to two quick-action buttons;
with the art on, an ASCII orc building above the lines. Its size comes from the building's type.
A click on a button runs that action; a click elsewhere expands the building; a drag moves the hut
(the town keeps the spot)."""
from __future__ import annotations

from rich.cells import cell_len
from rich.text import Text
from textual import events
from textual.message import Message
from textual.widget import Widget

from orkcraft import theme
from orkcraft.realm.orcs import ALERT_ICON
from orkcraft.realm.huts import ART_H, ART_STATUS_LINES, STATUS_LINES, STATUS_W  # noqa: F401
from orkcraft.wm.geometry import Geom

HUT_W = STATUS_W + 4         # round fence + one cell of padding each side
HUT_H = STATUS_LINES + 2                  # compact: fence + three lines
HUT_ART_H = ART_H + ART_STATUS_LINES + 2  # art: fence + art + two lines
LEGACY_SIZE = (HUT_W, HUT_H)              # buildings without a type keep the hut of T1102
PAD = 4                                   # fence + padding, both sides
FIRE = ("#ff8c1a", "#e8411c", "#ffc04d")   # a burning hut flickers between these
ART_COLOR = "#b98d55"        # weathered wood: the huts match the brown roads

_BIOME_RULES = "\n".join(
    f"    Desktop.biome-{name} Hut {{ background: {b.canvas}; border: round {b.border}; }}\n"
    f"    Desktop.biome-{name} Hut.-expanded {{ border: double {b.border_focus}; border-title-color: {b.border_focus}; color: {b.border_focus}; }}"
    for name, b in theme.BIOMES.items()
)


def hut_height(show_art: bool, size: tuple[int, int] = LEGACY_SIZE, roof: int = 0) -> int:
    """Rows of a hut: its size, plus its roof, plus the art (which takes one status line's place)."""
    return size[1] + roof + (ART_H - 1 if show_art else 0)


def clip(text: str, width: int) -> str:
    """Cut to `width` terminal cells, ending with … when something was cut."""
    if cell_len(text) <= width:
        return text
    out = ""
    for ch in text:
        if cell_len(out + ch) > width - 1:
            break
        out += ch
    return out + "…"


class Hut(Widget):
    SCOPED_CSS = False
    DEFAULT_CSS = f"""
    Hut {{
        position: absolute;
        padding: 0 1;
        border: round {theme.BIOMES[theme.DEFAULT_BIOME].border};
        border-title-color: $text;
        border-title-style: bold;
        border-subtitle-align: right;
        background: {theme.BIOMES[theme.DEFAULT_BIOME].canvas};
    }}
{_BIOME_RULES}
    Hut {{ color: {ART_COLOR}; }}
    Hut:hover {{ border-title-color: $warning; }}
    Desktop Hut.-alert {{ border: round {FIRE[0]}; border-title-color: {FIRE[0]}; }}
    Desktop Hut.-alert.-flame {{ border: round {FIRE[1]}; border-title-color: {FIRE[2]}; }}
    Desktop Hut.-rally-target {{ border: double $success; border-title-color: $success; }}
    """

    class Clicked(Message):
        def __init__(self, hut: Hut) -> None:
            super().__init__()
            self.hut = hut

    class Moved(Message):
        def __init__(self, hut: Hut) -> None:
            super().__init__()
            self.hut = hut

    class ActionPressed(Message):
        """A quick-action button on the hut was clicked."""
        def __init__(self, hut: Hut, action_id: str) -> None:
            super().__init__()
            self.hut = hut
            self.action_id = action_id

    def __init__(self, building_id: str, art: tuple[str, ...], show_art: bool = False,
                 size: tuple[int, int] = LEGACY_SIZE, roof: tuple[str, ...] = (),
                 actions: list | tuple = ()) -> None:
        super().__init__(id=f"hut-{building_id}")
        self.building_id = building_id
        self.art = art
        self.show_art = show_art
        self.size_wh = size
        self.roof = tuple(roof)
        self.actions = list(actions)          # catalog.ActionDef: id, label, glyph
        self._buttons: list[tuple[int, int, str]] = []   # (x0, x1, action id) on the action row
        self.geom = Geom(0, 0, size[0], hut_height(show_art, size, len(self.roof)))
        self.styles.width, self.styles.height = self.geom.w, self.geom.h
        self._lines: list[str] = []
        self.status: list[str] = []
        self.badge = ""
        self._title = ""
        self._drag: tuple[int, int, Geom] | None = None
        self._dragged = False
        self.fixed = False                    # a fixed hut (the Town Hall) does not move

    # -- content --------------------------------------------------------------------------------

    def set_title(self, number: int, title: str) -> None:
        # "🔮 Scrying Spire · Diff Inspector": the art already says what kind of building it is,
        # so a hut keeps the icon and the part after the dot.
        if " · " in title:
            icon, _, rest = title.partition(" ")
            title = f"{icon} {rest.rsplit(' · ', 1)[-1]}"
        # A narrow hut clips the words, then drops the number: "7 📋 Tasks" → "7 📋 Ta…" → "📋 Tasks" → "📋".
        room = self.geom.w - 5          # Textual keeps the corners and pads the title; one cell spare for wide emoji
        icon, _, words = title.partition(" ")
        head = f"{number} {icon} "
        if not words:
            options = [f"{number} {title}"]
        else:
            options = [f"{number} {title}"]
            if room - cell_len(head) >= 4:                   # at least "Ta…" of the name
                options.append(clip(f"{number} {title}", room))
            options += [f"{icon} {words}", clip(f"{icon} {words}", room) if room - cell_len(icon) >= 5 else "",
                        f"{number} {icon}", icon]
        text = next((o for o in options if o and cell_len(o) <= room), clip(options[-1], max(room, 1)))
        if text != self._title:
            self._title = text
            self.border_title = text

    def set_badge(self, badge: str) -> None:
        """The roster badge (`🧌 Smith+1 C 🔨 💤`) shortened to the lead's icon and state."""
        if badge == self.badge:
            return
        self.badge = badge
        parts = badge.split()
        self.border_subtitle = f" {parts[0]} {parts[-1]} " if len(parts) >= 2 else ""
        self.set_class(ALERT_ICON in badge, "-alert")

    @property
    def inner_w(self) -> int:
        return max(self.size_wh[0] - PAD, 1)

    @property
    def status_lines(self) -> int:
        """Lines left for the status once the action row and the art have their place."""
        rows = self.size_wh[1] - 2 - (1 if self.actions else 0) - (1 if self.show_art else 0)
        return max(rows, 1)

    def _reshape(self) -> None:
        h = hut_height(self.show_art, self.size_wh, len(self.roof))
        self.geom = Geom(self.geom.x, self.geom.y, self.size_wh[0], h)
        self.styles.width, self.styles.height = self.geom.w, self.geom.h
        self.set_status(self._lines)
        self.refresh()

    def set_show_art(self, on: bool) -> None:
        if on != self.show_art:
            self.show_art = on
            self._reshape()

    def set_shape(self, size: tuple[int, int], roof: tuple[str, ...] = (), actions: list | tuple = ()) -> None:
        """A new size, roof or set of quick actions (the spec changed, or the type's defaults)."""
        if (tuple(size), tuple(roof), [a.id for a in actions]) != (self.size_wh, self.roof, [a.id for a in self.actions]):
            self.size_wh, self.roof, self.actions = tuple(size), tuple(roof), list(actions)
            self._reshape()

    def set_status(self, lines: list[str]) -> None:
        self._lines = list(lines)
        lines = [clip(" ".join(str(x).split()), self.inner_w) for x in lines[:self.status_lines]]
        if lines != self.status:
            self.status = lines
            self.refresh()

    def _action_row(self) -> Text:
        """`[+ New task] [▶ Run]` when it fits, `[+] [▶]` when it does not; remembers where each is."""
        width = self.inner_w
        for long in (True, False):
            parts = [f"[{a.glyph} {a.label}]" if long else f"[{a.glyph}]" for a in self.actions]
            if cell_len(" ".join(parts)) <= width or not long:
                break
        row, x, self._buttons = Text(no_wrap=True, overflow="crop"), 0, []
        for a, part in zip(self.actions, parts):
            w = cell_len(part)
            self._buttons.append((x, x + w, a.id))
            row.append(part, style="bold #f2c66d")
            row.append(" ")
            x += w + 1
        return row

    def render(self) -> Text:
        text = Text(no_wrap=True, overflow="crop")
        w = self.inner_w
        for line in self.roof:
            text.append(line.center(w).rstrip() + "\n", style="#9b6a3c")
        if self.show_art:
            for line in self.art:
                text.append(line.center(w).rstrip() + "\n")
        n = self.status_lines
        for i in range(n):
            line = self.status[i] if i < len(self.status) else ""
            text.append(line, style="bold #e8e0c8" if i == 0 else "#a89f86")
            if i < n - 1 or self.actions:
                text.append("\n")
        if self.actions:
            text.append_text(self._action_row())
        return text

    def action_at(self, cx: int, cy: int) -> str | None:
        """The quick action under a content cell (x, y), if any: the buttons sit on the last row."""
        if not self.actions or cy != self.geom.h - 3:
            return None
        return next((aid for x0, x1, aid in self._buttons if x0 <= cx < x1), None)

    # -- place ----------------------------------------------------------------------------------

    def place(self, g: Geom) -> None:
        self.geom = g
        self.styles.offset = (g.x, g.y)

    # -- mouse ----------------------------------------------------------------------------------

    def on_mouse_down(self, event: events.MouseDown) -> None:
        if event.button != 1 or self.fixed:
            return
        self._drag = (event.screen_x, event.screen_y, self.geom)
        self._dragged = False
        self.capture_mouse()
        event.stop()

    def on_mouse_move(self, event: events.MouseMove) -> None:
        if self._drag is None:
            return
        sx, sy, start = self._drag
        dx, dy = event.screen_x - sx, event.screen_y - sy
        if not self._dragged and abs(dx) + abs(dy) < 2:
            return
        self._dragged = True
        parent = self.parent
        width, height = getattr(parent, "hut_room", None) or (
            (parent.size.width, parent.size.height) if isinstance(parent, Widget) else (200, 50))
        w, h = self.geom.w, self.geom.h
        x = max(0, min(start.x + dx, width - w))
        y = max(0, min(start.y + dy, height - h))
        if (x, y) != (self.geom.x, self.geom.y):
            self.place(Geom(x, y, w, h))
            replan = getattr(parent, "replan_roads", None)
            if replan is not None:
                replan()
        event.stop()

    def on_mouse_up(self, event: events.MouseUp) -> None:
        if self._drag is None:
            return
        self._drag = None
        self.release_mouse()
        if self._dragged:
            self.post_message(self.Moved(self))
        event.stop()

    def on_click(self, event: events.Click) -> None:
        # Open on the click itself, not on mouse up: the building opens over this spot, and a
        # click still on its way would land in the window that just appeared.
        event.stop()
        if not self._dragged:
            offset = event.get_content_offset(self)
            action = self.action_at(offset.x, offset.y) if offset is not None else None
            self.post_message(self.ActionPressed(self, action) if action else self.Clicked(self))
        self._dragged = False
