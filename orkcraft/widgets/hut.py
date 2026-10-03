"""Hut: a building collapsed on the town map, drawn as its own silhouette (realm/silhouettes.py).

Above the building stand its number, its one icon and its name on one line (two when long),
then one blank row. The silhouette is the building itself: a frame with live status lines in it. Under it, up to
two quick-action buttons. A click on a button runs that action; a click elsewhere expands the
building; a drag moves the hut (the town keeps the spot).

The frame takes the colour of the biome, so the rules for that are CSS; only the text carries
styles of its own. An orc waiting for an answer sets the hut on fire (immersion, `realm/modes.py`):
the whole card — name, frame, text, buttons and its ground — flickers orange, turns red when the
question is left waiting, then the roof turns to 🔥 bit by bit. In the hidden mode it only turns red.
"""
from __future__ import annotations

from rich.cells import cell_len
from rich.text import Text
from textual import events
from textual.message import Message
from textual.widget import Widget

from orkcraft import theme
from orkcraft.realm import modes, silhouettes
from orkcraft.realm.orcs import ALERT_ICON
from orkcraft.realm.silhouettes import clip  # noqa: F401  (the ghost clips its label the same way)
from orkcraft.wm.geometry import Geom

FIRE = ("#ff8c1a", "#e8411c", "#ffc04d", "#b31b0f")   # orange ↔ amber, then red ↔ dark red
ALERT_RED = "#ef4444"                                   # the hidden mode: a waiting hut is only red
FIRE_GROUND = ("#3a1c06", "#420d07", "#3d0b0b")         # the card's ground: orange, red, hidden red
HEAD_STYLE, LIVE_STYLE = "bold #e8e0c8", "#a89f86"
NAME_STYLE, BUTTON_STYLE, ORC_STYLE = "bold #e8e0c8", "bold #f2c66d", "bold #f2c66d"
DEFAULT_SIL = silhouettes.frame(silhouettes.FRAME_SIZES["S"])

_BIOME_RULES = "\n".join(
    f"    Desktop.biome-{name} Hut {{ background: {b.canvas}; color: {b.border}; }}\n"
    f"    Desktop.biome-{name} Hut.-expanded {{ color: {b.border_focus}; text-style: bold; }}"
    for name, b in theme.BIOMES.items()
)


def footprint(sil: silhouettes.Silhouette, label: silhouettes.Label, actions: int) -> tuple[int, int]:
    """(width, height) of a hut: the label over the silhouette, its caption and the buttons under it."""
    return (max(sil.width, label.width),
            len(label.lines) + sil.height + (1 if sil.caption else 0) + (1 if actions else 0))


class Hut(Widget):
    SCOPED_CSS = False
    DEFAULT_CSS = f"""
    Hut {{
        position: absolute;
        padding: 0;
        border: none;
        color: {theme.BIOMES[theme.DEFAULT_BIOME].border};
        background: {theme.BIOMES[theme.DEFAULT_BIOME].canvas};
    }}
{_BIOME_RULES}
    Hut:hover {{ color: $warning; }}
    Desktop Hut.-alert {{ color: {FIRE[0]}; background: {FIRE_GROUND[0]}; }}
    Desktop Hut.-alert.-flame {{ color: {FIRE[2]}; }}
    Desktop Hut.-alert.-burning {{ color: {FIRE[1]}; background: {FIRE_GROUND[1]}; text-style: bold; }}
    Desktop Hut.-alert.-burning.-flame {{ color: {FIRE[3]}; }}
    Desktop.-hidden Hut.-alert {{ color: {ALERT_RED}; background: {FIRE_GROUND[2]}; text-style: bold; }}
    Desktop Hut.-rally-target {{ color: $success; text-style: bold; }}
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

    def __init__(self, building_id: str, sil: silhouettes.Silhouette | None = None,
                 actions: list | tuple = ()) -> None:
        super().__init__(id=f"hut-{building_id}")
        self.building_id = building_id
        self.base = sil or DEFAULT_SIL         # the silhouette as its type draws it
        self.sil = self.base                  # …grown to the content, for the types that grow
        self.rows = 0
        self.plain = False                    # the hidden mode: just frames
        self.alert_since: float | None = None  # when the orc started waiting for an answer
        self.burnt = 0.0                      # share of the roof on fire
        self.actions = list(actions)          # catalog.ActionDef: id, label, glyph
        self._buttons: list[tuple[int, int, str]] = []   # (x0, x1, action id) on the button row
        self.number, self.title, self.badge = 0, "", ""
        self.label = silhouettes.label(0, "", self.sil.width)
        self.status: list[str] = []           # the live lines the view gave
        self.geom = Geom(0, 0, *footprint(self.sil, self.label, len(self.actions)))
        self.styles.width, self.styles.height = self.geom.w, self.geom.h
        self._drag: tuple[int, int, Geom] | None = None
        self._dragged = False
        self.fixed = False                    # a fixed hut (the Town Hall) does not move

    # -- content --------------------------------------------------------------------------------

    @property
    def live_widths(self) -> list[int]:
        """The widths of the slots live text goes to — a view may tailor its lines to them."""
        return self.sil.live_widths

    @staticmethod
    def _badge_short(badge: str) -> str:
        parts = modes.skin(badge).split()     # `🧌 Smith+1 C 🔨 💤` → `🧌 💤` (`🧑 💤` when hidden)
        return f"{parts[0]} {parts[-1]}" if len(parts) >= 2 else ""

    def _relabel(self) -> None:
        label = silhouettes.label(self.number, self.title, self.sil.width)
        if label != self.label:
            self.label = label
            self._reshape()
        self.refresh()

    def set_title(self, number: int, title: str) -> None:
        if (number, title) != (self.number, self.title):
            self.number, self.title = number, title
            self._relabel()

    def set_badge(self, badge: str, now: float | None = None) -> None:
        """The roster badge: the hut keeps one icon, so it only shows in the fence — it burns when an orc waits."""
        if badge != self.badge:
            self.badge = badge
            alert = ALERT_ICON in badge
            self.set_class(alert, "-alert")
            if alert and self.alert_since is None:
                self.alert_since = modes.now() if now is None else now
            elif not alert:
                self.alert_since = None
            self.update_fire(now)
            self.refresh()

    def update_fire(self, now: float | None = None) -> None:
        """How far the fire got: orange, then red, then the roof burns (immersion only)."""
        stage, burnt = "", 0.0
        if self.alert_since is not None and not self.plain:
            stage, burnt = modes.fire_stage((modes.now() if now is None else now) - self.alert_since)
        self.set_class(stage == "red", "-burning")
        if not stage:
            self.remove_class("-flame")
        if burnt != self.burnt:
            self.burnt = burnt
            self.refresh()

    def _reshape(self) -> None:
        w, h = footprint(self.sil, self.label, len(self.actions))
        if (w, h) != (self.geom.w, self.geom.h):
            self.geom = Geom(self.geom.x, self.geom.y, w, h)
            self.styles.width, self.styles.height = w, h

    def set_silhouette(self, sil: silhouettes.Silhouette, actions: list | tuple = ()) -> None:
        """A new shape or set of quick actions (the spec changed, or the type's defaults)."""
        if sil != self.base:
            self.base = sil
            self.rows = 0
        self._apply(self._look(), actions)

    def _look(self) -> silhouettes.Silhouette:
        """The base shape, grown to its content, in the town's mode (decorated or plain)."""
        sil = silhouettes.fit(self.base, self.rows) if self.rows else self.base
        return silhouettes.styled(sil, self.plain)

    def set_plain(self, plain: bool) -> bool:
        """Immersion (decorated) or plain (just a frame); True when the hut changed size."""
        if plain == self.plain:
            return False
        self.plain = plain
        self.update_fire()
        before = (self.geom.w, self.geom.h)
        self._apply(self._look(), self.actions)
        self.refresh()
        return (self.geom.w, self.geom.h) != before

    def set_rows(self, rows: int) -> bool:
        """The content wants `rows` text rows (a growing building only); True when the hut changed size."""
        if not self.base.grow or rows == self.rows:
            return False
        self.rows = rows
        before = (self.geom.w, self.geom.h)
        self._apply(self._look(), self.actions)
        return (self.geom.w, self.geom.h) != before

    def _apply(self, sil: silhouettes.Silhouette, actions: list | tuple) -> None:
        if sil != self.sil or [a.id for a in actions] != [a.id for a in self.actions]:
            self.sil, self.actions = sil, list(actions)
            self.label = silhouettes.label(self.number, self.title, sil.width)
            self._reshape()
            self.refresh()

    def set_status(self, lines: list[str]) -> None:
        lines = [" ".join(str(x).split()) for x in lines]
        if lines != self.status:
            self.status = lines
            self.refresh()

    def _action_row(self, width: int, fire: str | None = None) -> Text:
        """`[+ New task] [▶ Run]` when it fits, `[+] [▶]` when it does not; remembers where each is."""
        for long in (True, False):
            parts = [f"[{a.glyph} {a.label}]" if long else f"[{a.glyph}]" for a in self.actions]
            if cell_len(" ".join(parts)) <= width or not long:
                break
        total = cell_len(" ".join(parts))
        x = max((width - total) // 2, 0)
        row, self._buttons = Text(" " * x, no_wrap=True, overflow="crop"), []
        for a, part in zip(self.actions, parts):
            w = cell_len(part)
            self._buttons.append((x, x + w, a.id))
            row.append(part, style=fire or BUTTON_STYLE)
            row.append(" ")
            x += w + 1
        return row

    @property
    def on_fire(self) -> bool:
        """An orc waits for an answer: the whole card takes the fire's colour (the hidden mode's red)."""
        return self.alert_since is not None

    def fire_style(self) -> str | None:
        """The one style of every cell of a card on fire (it wins over the selection and the hover)."""
        if not self.on_fire:
            return None
        if self.plain:
            return f"bold {ALERT_RED}"
        flame = self.has_class("-flame")
        if self.has_class("-burning"):
            return f"bold {FIRE[3] if flame else FIRE[1]}"
        return FIRE[2] if flame else FIRE[0]

    def render(self) -> Text:
        w = self.geom.w
        fire = self.fire_style()
        text = Text(no_wrap=True, overflow="crop")
        for i, line in enumerate(self.label.lines):
            pad = max((w - cell_len(line)) // 2, 0)
            text.append(" " * pad + line + "\n", style=fire or NAME_STYLE)
        left = (w - self.sil.width) // 2
        rows = self._burning(self.sil.draw(self.status))
        for n, row in enumerate(rows):
            text.append(" " * left)
            if n == len(rows) - 1:
                row = self._orc_in_frame(row)
            for piece, role in row:
                text.append(piece, style=fire or (HEAD_STYLE if role == "head" else LIVE_STYLE if role == "live"
                                                  else ORC_STYLE if role == "orc" else None))
            text.append("\n")
        if self.sil.caption:
            cap = self.sil.caption_text(self.status)
            text.append(" " * max((w - cell_len(cap)) // 2, 0) + cap + "\n", style=fire or LIVE_STYLE)
        if self.actions:
            text.append_text(self._action_row(w, fire))
        else:
            text.rstrip()
        return text

    def _burning(self, rows: list[list[tuple[str, str]]]) -> list[list[tuple[str, str]]]:
        """The roof — the rows above the first line of text — with its share of 🔥."""
        if self.burnt <= 0 or self.plain or not self.sil.slots:
            return rows
        top = min(y for y, _, _ in self.sil.slots)
        if top == 0:
            return rows
        roof = modes.burn(["".join(piece for piece, _ in row) for row in rows[:top]], self.burnt)
        return [[(line, "frame")] for line in roof] + rows[top:]

    def _orc_in_frame(self, row: list[tuple[str, str]]) -> list[tuple[str, str]]:
        """The orc stands in the bottom of the frame: ` 🧌 💤 ` set into the last line, in the middle."""
        orc = self._badge_short(self.badge)
        line = "".join(piece for piece, _ in row)
        if not orc or any(role != "frame" for _, role in row):
            return row
        for mark in (f" {orc} ", f" {orc.split()[0]} "):
            n = cell_len(mark)
            if n + 2 <= len(line):
                at = (len(line) - n) // 2
                return [(line[:at], "frame"), (mark, "orc"), (line[at + n:], "frame")]
        return row

    def action_at(self, cx: int, cy: int) -> str | None:
        """The quick action under a cell (x, y) of the hut, if any: the buttons sit on its last row."""
        if not self.actions or cy != self.geom.h - 1:
            return None
        return next((aid for x0, x1, aid in self._buttons if x0 <= cx < x1), None)

    @property
    def body_geom(self) -> Geom:
        """The silhouette alone, in canvas cells: roads attach here, not to the label or the buttons."""
        g = self.geom
        return Geom(g.x + (g.w - self.sil.width) // 2, g.y + len(self.label.lines), self.sil.width, self.sil.height)

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
