"""A movable, resizable window living on the Desktop."""
from __future__ import annotations

from rich.cells import cell_len
from rich.text import Text
from textual import events
from textual.containers import Container
from textual.message import Message
from textual.widget import Widget

from orkcraft import theme
from orkcraft.realm import lexicon
from orkcraft.wm import geometry as geo
from orkcraft.wm.geometry import Frac, Geom


_BIOME_RULES = "\n".join(
    f"    Desktop.biome-{name} Window {{ background: {b.window_bg}; border: round {b.border}; }}\n"
    f"    Desktop.biome-{name} Window.-active {{ border: round {b.border_focus}; border-title-color: {b.border_focus}; }}"
    for name, b in theme.BIOMES.items()
)


class Window(Container):
    """Bordered window. The top border is the title bar.

    Mouse: drag the title bar to move; drag the bottom-right corner (◢) to resize,
    the bottom edge for height, the right edge for width; double-click the title
    to maximize / restore.
    """

    # The biome rules select `Desktop.biome-<name> Window`: scoped CSS would prefix them with
    # `Window ` and they would never match.
    SCOPED_CSS = False
    DEFAULT_CSS = f"""
    Window {{
        position: absolute;
        width: 40;
        height: 12;
        border: round {theme.BIOMES[theme.DEFAULT_BIOME].border};
        border-title-color: $text-muted;
        border-title-style: bold;
        border-subtitle-align: right;
        border-subtitle-color: $text-muted;
        background: {theme.BIOMES[theme.DEFAULT_BIOME].window_bg};
        padding: 0;
    }}
{_BIOME_RULES}
    Window.-dragging {{
        border: heavy $warning;
        border-title-color: $warning;
    }}
    Desktop Window.-rally-target {{
        border: double $success;
        border-title-color: $success;
    }}
    Window.-rally-target {{
        border: double $success;
        border-title-color: $success;
    }}
    Window > .window-body {{
        width: 100%;
        height: 100%;
    }}
    """

    class Activated(Message):
        """Posted when the user clicks into the window."""
        def __init__(self, window: Window) -> None:
            super().__init__()
            self.window = window

    class Changed(Message):
        """Posted after the user finished moving or resizing with the mouse."""
        def __init__(self, window: Window) -> None:
            super().__init__()
            self.window = window

    class BadgeClicked(Message):
        """The resident-orc badge on the top border was clicked."""
        def __init__(self, window: Window) -> None:
            super().__init__()
            self.window = window

    class MaximizeToggled(Message):
        def __init__(self, window: Window) -> None:
            super().__init__()
            self.window = window

    def __init__(
        self,
        content: Widget,
        *,
        window_id: str,
        title: str,
        number: int,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__(content, id=id or f"win-{window_id}", classes=classes)
        content.add_class("window-body")
        self.window_id = window_id
        self.window_title = title
        self.number = number
        self.geom = Geom(0, 0, 40, 12)
        self.frac: Frac | None = None
        # Geometry to return to when un-maximizing.
        self.restore: tuple[Geom, Frac | None] | None = None
        self.last_focused: Widget | None = None
        self._drag: tuple[str, int, int, Geom] | None = None
        # Pinned windows keep their slot: no drag, no keyboard moves, no tiling.
        self.pinned = False
        # Resident orc (Unit Frame): badge text is set by the app from the roster.
        self.badge = ""
        self._badge_cells = 0
        # Rally pipe indicator (e.g. "🚩 ──► 🔮 Scrying Spire")
        self.rally = ""
        # Minimal mode draws the window wider than its stored slot.
        self.title_width: int | None = None
        self._update_title()
        self.border_subtitle = "◢"

    # -- state -----------------------------------------------------------------

    @property
    def hidden(self) -> bool:
        return not self.display

    @property
    def maximized(self) -> bool:
        return self.restore is not None

    def _update_title(self) -> None:
        """` N · Title 📌 ⛶ ── [ 🚩 ──► 🔮 Scrying Spire ] ──── [ 🧌 Smith+1 🔨 💤 ] `"""
        marks = (" 📌" if self.pinned else "") + (" ⛶" if self.restore is not None else "")
        left = f" {self.number} · {lexicon.words(self.window_title)}{marks} "
        title = Text(left)
        self._badge_cells = 0

        width = (self.title_width or self.geom.w) - 7
        left_len = cell_len(left)

        badge_text = f" [ {self.badge} ] " if self.badge else ""
        badge_len = cell_len(badge_text)

        # The rally segment shrinks before it goes: `🚩 ──► 🔮 Spire` → `🚩 ──► 🔮` → nothing
        # (the badge always wins).
        rally = lexicon.words(getattr(self, "rally", ""))
        candidates = [rally, rally.rsplit(" ", 1)[0]] if rally else []
        for text in candidates:
            rally_text = f"─[ {text} ]"
            rally_len = cell_len(rally_text)
            if width - left_len - badge_len - rally_len >= (1 if badge_text else 0):
                title.append(rally_text)
                left_len += rally_len
                break

        if badge_text:
            fill = width - left_len - badge_len
            if fill >= 1:
                title.append("─" * fill)
                title.append(badge_text, style="bold")
                self._badge_cells = badge_len

        self.border_title = title

    def set_title(self, title: str) -> None:
        self.window_title = title
        self._update_title()

    def set_number(self, number: int) -> None:
        if self.number != number:
            self.number = number
            self._update_title()

    def set_rally(self, text: str) -> None:
        if text != getattr(self, "rally", ""):
            self.rally = text
            self._update_title()

    def apply_geom(self, g: Geom, frac: Frac | None = None) -> None:
        """Place the window. `frac` keeps it in a fractional slot across terminal resizes."""
        width_changed = g.w != self.geom.w
        self.geom = g
        self.frac = frac
        self.styles.offset = (g.x, g.y)
        self.styles.width = g.w
        self.styles.height = g.h
        if width_changed:
            self._update_title()
        replan = getattr(self.parent, "replan_roads", None)
        if replan is not None:
            replan()   # roads follow their gates

    def set_badge(self, badge: str) -> None:
        if badge != self.badge:
            self.badge = badge
            self._update_title()

    def refresh_badge(self) -> None:
        """The mode changed: the title and the badge are drawn in its words (with or without emoji)."""
        self._update_title()

    def set_pinned(self, pinned: bool) -> None:
        self.pinned = pinned
        self._update_title()

    def set_restore(self, restore: tuple[Geom, Frac | None] | None) -> None:
        self.restore = restore
        self._update_title()

    # -- mouse -----------------------------------------------------------------

    def _hit(self, event: events.MouseEvent) -> str | None:
        """Which border part is under the pointer (screen coords survive bubbling)."""
        r = self.region
        rx, ry = event.screen_x - r.x, event.screen_y - r.y
        if not (0 <= rx < r.width and 0 <= ry < r.height):
            return None
        if ry == 0:
            if self._badge_cells and r.width - 1 - self._badge_cells - 1 <= rx < r.width - 1:
                return "badge"
            return "move"
        if ry == r.height - 1 and rx >= r.width - 3:
            return "resize"
        if ry == r.height - 1:
            return "resize-h"
        if rx == r.width - 1:
            return "resize-w"
        return None

    def on_mouse_down(self, event: events.MouseDown) -> None:
        self.post_message(self.Activated(self))
        if event.button != 1:
            return
        hit = self._hit(event)
        if hit == "badge":
            self.post_message(self.BadgeClicked(self))
            event.stop()
            return
        if hit is None or self.pinned or getattr(self.parent, "town_active", False):
            return   # the town view opens a building in its place: no dragging there
        self._drag = (hit, event.screen_x, event.screen_y, self.geom)
        self.add_class("-dragging")
        self.capture_mouse()
        event.stop()

    def on_mouse_move(self, event: events.MouseMove) -> None:
        if self._drag is None:
            return
        mode, sx, sy, start = self._drag
        dx, dy = event.screen_x - sx, event.screen_y - sy
        desktop = self.parent
        size = desktop.size if isinstance(desktop, Widget) else self.app.size
        if mode == "move":
            g = geo.move(start, dx, dy, size.width, size.height)
        else:
            dw = dx if mode in ("resize", "resize-w") else 0
            dh = dy if mode in ("resize", "resize-h") else 0
            g = geo.resize(start, dw, dh, size.width, size.height)
        if g != self.geom:
            # A manual move/resize detaches the window from its slot.
            self.set_restore(None)
            self.apply_geom(g, None)
        event.stop()

    def on_mouse_up(self, event: events.MouseUp) -> None:
        if self._drag is None:
            return
        moved = self._drag[3] != self.geom
        self._drag = None
        self.remove_class("-dragging")
        self.release_mouse()
        if moved:
            self.post_message(self.Changed(self))
        event.stop()

    def on_click(self, event: events.Click) -> None:
        if event.chain >= 2 and self._hit(event) == "move":
            self.post_message(self.MaximizeToggled(self))
            event.stop()
