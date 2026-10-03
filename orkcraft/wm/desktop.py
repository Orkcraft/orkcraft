"""Desktop: hosts windows, keeps z-order and focus, snaps, tiles and persists them."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from rich.text import Text
from textual import events
from textual.binding import Binding
from textual.containers import Container, Horizontal
from textual.message import Message
from textual.widget import Widget
from textual.widgets import DataTable, ListView, OptionList, Select, Static, Tree

from orkcraft.wm import geometry as geo
from orkcraft.wm.geometry import SNAP_SLOTS, Frac, Geom
from orkcraft import scroll
from orkcraft.scroll import TownScroll, has_outgoing
from orkcraft import theme
from orkcraft.realm import chronicles, pipes
from orkcraft.widgets.road_layer import (ENTRY_GLYPH, EXIT_GLYPH, ROAD_SELECTED, RoadClicked, RoadGate, RoadLabel,
                                         RoadRun, road_key, runs)
from orkcraft.widgets.carts import FPS as CART_FPS, Traffic
from orkcraft.realm.buildings import TOWN_HALL
from orkcraft.widgets.ghost import Ghost
from orkcraft.widgets.hut import Hut
from orkcraft.realm import catalog, silhouettes
from orkcraft.widgets.terrain import Terrain
from orkcraft.wm import roadmap
from orkcraft.wm.window import Window

MOVE_STEP_X = 2
MOVE_STEP_Y = 1
# Only graph nodes go to the preview; agent rows, systems and calendar events do not.
_NODE_ID = re.compile(r"^[CTP]\d+$")


def node_id_of(value: object) -> str | None:
    """Row keys, tree data and option ids → a graph node id, if they carry one."""
    if value is None:
        return None
    text = str(value).split("#", 1)[0]
    return text if _NODE_ID.match(text) else None


class Desktop(Container):
    """Window container.

    Window mode (`ctrl+w`) moves focus to the desktop itself; its bindings below are
    active only then, so they never shadow keys of the widgets inside windows.
    """

    BINDINGS = [
        Binding("escape", "exit_window_mode", "Done", show=True),
        Binding("enter", "exit_window_mode", "Done", show=False),
        Binding("ctrl+w", "exit_window_mode", "Done", show=False),
        Binding("left", "nudge(-1, 0)", "Move", show=False),
        Binding("right", "nudge(1, 0)", "Move", show=False),
        Binding("up", "nudge(0, -1)", "Move", show=False),
        Binding("down", "nudge(0, 1)", "Move", show=False),
        Binding("shift+left", "grow(-1, 0)", "Resize", show=False),
        Binding("shift+right", "grow(1, 0)", "Resize", show=False),
        Binding("shift+up", "grow(0, -1)", "Resize", show=False),
        Binding("shift+down", "grow(0, 1)", "Resize", show=False),
        Binding("h", "snap('left')", "◧ Left", show=True),
        Binding("l", "snap('right')", "◨ Right", show=True),
        Binding("k", "snap('top')", "⬒ Top", show=True),
        Binding("j", "snap('bottom')", "⬓ Bottom", show=True),
        Binding("y", "snap('top-left')", "◰", show=True),
        Binding("u", "snap('top-right')", "◳", show=True),
        Binding("b", "snap('bottom-left')", "◱", show=True),
        Binding("n", "snap('bottom-right')", "◲", show=True),
        Binding("c", "snap('center')", "Center", show=False),
        Binding("f", "toggle_maximize", "Max", show=True),
        Binding("t", "tile", "Tile", show=True),
        Binding("x", "hide_window", "Hide", show=True),
        Binding("tab", "cycle(1)", "Next", show=False),
        Binding("shift+tab", "cycle(-1)", "Prev", show=False),
        Binding("1", "focus_number(1)", show=False),
        Binding("2", "focus_number(2)", show=False),
        Binding("3", "focus_number(3)", show=False),
        Binding("4", "focus_number(4)", show=False),
        Binding("5", "focus_number(5)", show=False),
        Binding("6", "focus_number(6)", show=False),
        Binding("7", "focus_number(7)", show=False),
        Binding("8", "focus_number(8)", show=False),
        Binding("9", "focus_number(9)", show=False),
        Binding("p", "toggle_link", "Link", show=True),
        Binding("s", "save_layout", "Save", show=True),
        Binding("r", "reset_layout", "Reset", show=True),
    ]

    DEFAULT_CSS = """
    Desktop {
        width: 1fr;
        height: 1fr;
        layers: base roads overlay;
    }
    Desktop > Window.-town-open {
        layer: overlay;
    }
    """

    class LayoutChanged(Message):
        """Z-order, visibility, focus or link state changed (the taskbar listens)."""

    class PayloadEmitted(Message):
        """A data payload was emitted across a rally pipe."""
        def __init__(self, payload: pipes.Payload) -> None:
            super().__init__()
            self.payload = payload

    class NodeHighlighted(Message):
        """A node was highlighted in a window; the linked preview follows it."""
        def __init__(self, node_id: str, source_id: str | None = None) -> None:
            super().__init__()
            self.node_id = node_id
            self.source_id = source_id

    class CanvasClicked(Message):
        """A click landed on the desktop canvas or terrain (not on a window)."""

    class OrkspaceChanged(Message):
        """Posted when switching to a different orkspace canvas."""
        def __init__(self, orkspace_id: str) -> None:
            super().__init__()
            self.orkspace_id = orkspace_id

    def __init__(
        self,
        *windows: Window,
        scroll: TownScroll | None = None,
        scroll_path: Path | None = None,
        layout_file: Path | None = None,
        preview_id: str = "preview",
        home_id: str = "board",
        id: str | None = None,
    ) -> None:
        self.terrain = Terrain(id="terrain")
        super().__init__(self.terrain, *windows, id=id)
        # Known before mount (the taskbar composes before the desktop's children attach).
        self.window_list = list(windows)
        self.scroll = scroll
        self.scroll_path = scroll_path or layout_file
        self.layout_file = self.scroll_path
        self.preview_id = preview_id
        self.home_id = home_id
        # Minimal (narrow terminal) mode: only the active window, full size.
        self.single = False
        self.preview_linked = True
        self.window_mode = False
        self.rally_mode = False
        self.rally_source: str | None = None
        # Roads: the plan of the visible roads, the selected road, what is on the layer.
        self.road_paths: dict[str, roadmap.RoadPath] = {}
        self.selected_road: str | None = None
        self._replan_pending = False
        self._road_signature: tuple = ()
        self.traffic = Traffic(self)
        # Town view: every building a hut, the active one expanded over the map.
        self.town = bool(scroll is not None and scroll.preferences.get("view", "town") == "town")
        self.huts: dict[str, Hut] = {}
        self.ghost: Ghost | None = None          # a building being placed
        self._ghost_done = None
        # Rows at the bottom under the floating console: huts stay above `hut_reserve`
        # (the calm strip, constant), the open building above `open_reserve` (the current console).
        self.hut_reserve = 0
        self.open_reserve = 0
        self.open_right = 0      # columns at the right edge under the orc's chat
        self._traffic_timer = None
        self.active: Window | None = None
        self._laid_out = False
        self._mode_return_focus: Widget | None = None
        self.biome: str = theme.DEFAULT_BIOME
        self.solid_black: bool = False
        if self.scroll is not None:
            self.solid_black = bool(self.scroll.preferences.get("terrain_solid_black", False))
            self.set_biome(self.scroll.active_orkspace.biome)
            self.renumber_orkspace(self.scroll.active_orkspace_id)
        else:
            self.set_biome(self.biome)

    def in_view(self, w: Window | None) -> bool:
        if w is None or not isinstance(w, Window):
            return False
        if self.scroll is None:
            return True
        if w.window_id == TOWN_HALL:
            return True                      # the town's own building stands on every canvas
        active_ork = self.scroll.active_orkspace
        return active_ork is not None and w.window_id in active_ork.buildings

    # -- lookup ----------------------------------------------------------------

    @property
    def windows(self) -> list[Window]:
        """Windows bottom-to-top (DOM order is paint order)."""
        return [w for w in self.children if isinstance(w, Window)]

    def by_number(self) -> list[Window]:
        return sorted(self.windows, key=lambda w: w.number)

    def get_window(self, window_id: str) -> Window | None:
        for w in self.windows:
            if w.window_id == window_id:
                return w
        return None

    def window_of(self, widget: Widget | None) -> Window | None:
        node = widget
        while node is not None and node is not self:
            if isinstance(node, Window):
                return node
            node = node.parent  # type: ignore[assignment]
        return None

    @property
    def dims(self) -> tuple[int, int]:
        return self.size.width, self.size.height

    # -- layout ----------------------------------------------------------------

    def on_resize(self, event: events.Resize) -> None:
        width, height = self.dims
        if width <= 0 or height <= 0:
            return
        if not self._laid_out:
            self._laid_out = True
            if self.scroll is not None:
                self.apply_orkspace(self.scroll.active_orkspace_id)
                # Write the v2 scroll at once: a first start and a migrated v1 file land on disk.
                self.save()
            else:
                self.apply_default_layout()
            return
        for w in self.windows:
            if w.frac is not None:
                w.apply_geom(geo.frac_to_geom(w.frac, width, height), w.frac)
            else:
                w.apply_geom(geo.clamp(w.geom, width, height), None)
        self._apply_single()
        self.sync_huts()
        self._apply_town()
        self.replan_roads()

    def place(self, w: Window, frac: Frac) -> None:
        w.apply_geom(geo.frac_to_geom(frac, *self.dims), frac)

    def apply_default_layout(self) -> None:
        width, height = self.dims
        defaults = geo.default_fracs()
        active_buildings = (
            set(self.scroll.active_orkspace.buildings)
            if self.scroll is not None
            else {w.window_id for w in self.windows}
        )
        for w in self.windows:
            if w.window_id not in active_buildings:
                continue
            frac = defaults.get(w.window_id, SNAP_SLOTS["center"])
            w.display = frac is not None
            if w.pinned:
                continue  # a pinned window keeps its slot even through a reset
            w.set_restore(None)
            self.place(w, frac or SNAP_SLOTS["center"])
        self.preview_linked = True
        self.solid_black = False
        self.remove_class("-solid-black")
        if self.scroll is not None:
            self.set_biome(self.scroll.active_orkspace.biome)
        else:
            self.set_biome(theme.DEFAULT_BIOME)
        first = self.get_window(self.home_id) if self.in_view(self.get_window(self.home_id)) else None
        if first is None:
            first = self._top_visible()
        if self.scroll is not None:
            for b in self.scroll.buildings_in(self.scroll.active_orkspace_id):
                b.hut = None   # the town is laid out again too
        self.sync_huts()
        if self.town_active:
            first = None   # the town starts with every building collapsed
        if first is not None:
            self.focus_window(first)
        else:
            self.set_active(None)
        self.post_message(self.LayoutChanged())

    def renumber_orkspace(self, orkspace_id: str) -> None:
        if self.scroll is None:
            return
        ork = self.scroll.orkspace(orkspace_id)
        if ork is None:
            return
        for n, bid in enumerate(ork.buildings, 1):
            w = self.get_window(bid)
            if w is not None:
                w.set_number(n)
        other_n = len(ork.buildings) + 1
        for w in self.windows:
            if w.window_id not in ork.buildings:
                w.set_number(other_n)
                other_n += 1

    def apply_orkspace(self, orkspace_id: str) -> None:
        if self.scroll is None:
            return
        ork = self.scroll.orkspace(orkspace_id)
        if ork is None:
            return
        self.renumber_orkspace(orkspace_id)
        width, height = self.dims
        defaults = geo.default_fracs()
        for w in self.windows:
            if w.window_id in ork.buildings or w.window_id == TOWN_HALL:
                spec = self.scroll.building(w.window_id)
                demolished = spec.demolished if spec is not None else False
                if spec is not None and spec.frac is not None:
                    frac = tuple(float(v) for v in spec.frac)
                    if len(frac) == 4 and width > 0 and height > 0:
                        w.apply_geom(geo.frac_to_geom(frac, width, height), frac)
                elif spec is not None and spec.bounds is not None:
                    b = spec.bounds
                    g = Geom(int(b.get("x", 0)), int(b.get("y", 0)), int(b.get("width", 40)), int(b.get("height", 12)))
                    if width > 0 and height > 0:
                        w.apply_geom(geo.clamp(g, width, height), None)
                else:
                    slot = defaults.get(w.window_id)
                    if slot is None:
                        if spec is None or spec.preset_ref.startswith("custom:"):
                            slot = SNAP_SLOTS["center"]
                        else:
                            demolished = True
                            slot = SNAP_SLOTS["center"]
                    if width > 0 and height > 0:
                        self.place(w, slot)
                w.set_restore(None)
                w.display = not demolished
                if spec is not None:
                    w.set_pinned(bool(spec.pinned))
            else:
                w.display = False

        for window_id in ork.window_order:
            w = self.get_window(window_id)
            if w is not None and w.window_id in ork.buildings:
                self.raise_window(w)

        self.solid_black = bool(self.scroll.preferences.get("terrain_solid_black", False))
        if self.solid_black:
            self.add_class("-solid-black")
        else:
            self.remove_class("-solid-black")
        self.set_biome(ork.biome)
        self.preview_linked = bool(self.scroll.preferences.get("preview_linked", True))

        active = None
        if ork.active_building:
            target = self.get_window(ork.active_building)
            if target is not None and target.window_id in ork.buildings and not target.hidden:
                active = target
        self.sync_huts()
        if active is None and not self.town_active:
            # Fresh canvas (no stored active window): the home building, as the default layout does.
            home = self.get_window(self.home_id)
            if home is not None and home.window_id in ork.buildings and not home.hidden:
                active = home
            if active is None:
                active = self._top_visible()
        if active is not None:
            self.focus_window(active)
        else:
            self.set_active(None)
        self._apply_town()   # windows were just placed in their tile slots

        self.replan_roads()
        self.post_message(self.LayoutChanged())

    def capture(self) -> None:
        if self.scroll is None or not self._laid_out:
            return   # before the first layout every window still shows: nothing true to record
        active_ork = self.scroll.active_orkspace
        if active_ork is None:
            return
        for bid in active_ork.buildings:
            w = self.get_window(bid)
            spec = self.scroll.building(bid)
            if w is None or spec is None:
                continue
            g, frac = w.restore if w.restore is not None else (w.geom, w.frac)
            spec.bounds = {"x": g.x, "y": g.y, "width": g.w, "height": g.h}
            spec.frac = list(frac) if frac is not None else None
            spec.pinned = bool(w.pinned)
            spec.demolished = bool(w.hidden)
            hut = self.huts.get(bid)
            if hut is not None and hut.display and self.dims[0] > 0:
                spec.hut = list(geo.hut_to_frac(hut.geom.x, hut.geom.y, *self.hut_room, hut.geom.w, hut.geom.h))
        active_ork.window_order = [w.window_id for w in self.windows if w.window_id in active_ork.buildings]
        active_ork.active_building = (
            self.active.window_id
            if self.active is not None and self.active.window_id in active_ork.buildings and not self.active.hidden
            else None
        )
        active_ork.biome = self.biome
        self.scroll.preferences["preview_linked"] = bool(self.preview_linked)
        self.scroll.preferences["terrain_solid_black"] = bool(self.solid_black)

    def save(self) -> bool:
        if self.scroll_path is None or not self._laid_out or not self.windows or self.scroll is None:
            return False
        self.capture()
        problems = scroll.save(self.scroll_path, self.scroll)
        if problems:
            self.app.notify("\n".join(problems), title="Town Scroll Save Refused", severity="error")
            return False
        return True

    def switch_orkspace(self, orkspace_id: str) -> None:
        if self.scroll is None or self.scroll.active_orkspace_id == orkspace_id:
            return
        if self.scroll.orkspace(orkspace_id) is None:
            return
        self.capture()
        self.scroll.active_orkspace_id = orkspace_id
        self.apply_orkspace(orkspace_id)
        self.save()
        self.post_message(self.OrkspaceChanged(orkspace_id))

    # -- biome & terrain ---------------------------------------------------------

    def set_biome(self, name: str) -> None:
        """Switch desktop biome. Unknown names fall back to DEFAULT_BIOME."""
        if name not in theme.BIOMES:
            name = theme.DEFAULT_BIOME
        self.biome = name
        for b in theme.BIOMES:
            self.remove_class(f"biome-{b}")
        self.add_class(f"biome-{name}")
        biome = theme.BIOMES[name]
        bg_color = theme.SOLID_BLACK if self.solid_black else biome.canvas
        self.styles.background = bg_color
        if hasattr(self, "terrain"):
            self.terrain.set_biome(biome, self.solid_black)

    def toggle_terrain(self) -> None:
        """Toggle solid black canvas on/off and save layout."""
        self.solid_black = not self.solid_black
        if self.solid_black:
            self.add_class("-solid-black")
        else:
            self.remove_class("-solid-black")
        biome = theme.BIOMES.get(self.biome, theme.BIOMES[theme.DEFAULT_BIOME])
        bg_color = theme.SOLID_BLACK if self.solid_black else biome.canvas
        self.styles.background = bg_color
        if hasattr(self, "terrain"):
            self.terrain.set_biome(biome, self.solid_black)
        self.save()

    # -- focus & z-order ---------------------------------------------------------

    def _top_visible(self) -> Window | None:
        visible = [w for w in self.windows if self.in_view(w) and not w.hidden]
        return visible[-1] if visible else None

    def raise_window(self, w: Window) -> None:
        top = self.windows[-1]
        if w is not top:
            self.move_child(w, after=top)

    def set_active(self, w: Window | None) -> None:
        if w is self.active:
            return
        if self.active is not None:
            self.active.remove_class("-active")
        self.active = w
        if w is not None:
            w.add_class("-active")
        self._apply_single()  # Minimal mode shows the active window, whoever made it active
        self._apply_town()
        self.replan_roads()   # the active building's roads are drawn brighter
        self.post_message(self.LayoutChanged())

    def focus_window(self, w: Window) -> None:
        """Show, raise and focus a window (its last focused widget, else the first)."""
        if not self.in_view(w) and self.scroll is not None:
            ork = self.scroll.orkspace_of(w.window_id)
            if ork is not None:
                self.switch_orkspace(ork.id)
        if w.hidden:
            w.display = True
            self.sync_huts()
            self.replan_roads()
        self.raise_window(w)
        self.set_active(w)
        self._apply_single()
        if self.window_mode:
            return
        target = w.last_focused
        if target is None or not target.is_attached or self.window_of(target) is not w:
            # Not inside a hidden tab: focusing there would switch the tab (the Town Hall's Sessions).
            focusable = [d for d in w.query("*") if d.focusable
                         and all(a.display for a in d.ancestors_with_self if a is not w and w in a.ancestors)]
            # Prefer the list/table a window is about over filters and buttons.
            # (A Select's dropdown is an OptionList too — skip it.)
            target = next(
                (
                    d for d in focusable
                    if isinstance(d, (ListView, DataTable, Tree, OptionList))
                    and not any(isinstance(a, Select) for a in d.ancestors)
                ),
                None,
            )
            target = target or (focusable[0] if focusable else None)
        if target is not None:
            already = target.has_focus
            target.focus()
            if already:
                self.announce_selection(target)
        self.post_message(self.LayoutChanged())

    def announce_selection(self, widget: Widget) -> None:
        """Tell the linked preview what is selected in `widget`, if anything."""
        w = self.window_of(widget)
        if w is None or w.window_id == self.preview_id:
            return
        node_id = self._selected_node(widget)
        if node_id:
            self._route(widget, node_id)

    def on_descendant_focus(self, event: events.DescendantFocus) -> None:
        w = self.window_of(event.widget)
        if w is None:
            return
        if self.town_active and not w.visible:
            # Focus wandered into a collapsed building (start-up auto focus, tab): it stays a hut.
            event.widget.blur()
            self.post_message(self.CanvasClicked())
            return
        w.last_focused = event.widget
        if w is not self.active:
            self.raise_window(w)
            self.set_active(w)
        # Re-announce the current selection so the linked preview follows focus too.
        self.announce_selection(event.widget)

    @staticmethod
    def _selected_node(widget: Widget) -> str | None:
        if isinstance(widget, ListView):
            return node_id_of(getattr(widget.highlighted_child, "task_id", None))
        if isinstance(widget, DataTable) and widget.row_count:
            try:
                return node_id_of(widget.coordinate_to_cell_key(widget.cursor_coordinate).row_key.value)
            except Exception:
                return None
        if isinstance(widget, Tree) and widget.cursor_node is not None:
            return node_id_of(widget.cursor_node.data)
        if isinstance(widget, OptionList) and widget.highlighted is not None:
            try:
                return node_id_of(widget.get_option_at_index(widget.highlighted).id)
            except Exception:
                return None
        return None

    def on_window_activated(self, message: Window.Activated) -> None:
        w = message.window
        if self._rally_click(w):
            return
        if self.window_of(self.app.focused) is not w:
            # A click on the border or an unfocusable area still moves keyboard focus here.
            self.focus_window(w)
        elif w is not self.active or w is not self.windows[-1]:
            self.raise_window(w)
            self.set_active(w)

    def on_window_changed(self, message: Window.Changed) -> None:
        self.save()

    def on_window_maximize_toggled(self, message: Window.MaximizeToggled) -> None:
        self.toggle_maximize(message.window)

    def on_click(self, event: events.Click) -> None:
        # Decide by position: a click on a window's border bubbles here with a widget that is
        # not inside the window (the mouse was captured for dragging), so `event.widget` lies.
        x, y = event.screen_x, event.screen_y
        if any(not w.hidden and w.visible and w.region.contains(x, y) for w in self.windows):
            return
        if self.region.contains(x, y):
            key = roadmap.hit(self.road_paths, x - self.region.x, y - self.region.y)
            if key is not None and self.scroll is not None and self.scroll.preferences.get("roads", "faint") != "off":
                self.post_message(RoadClicked(key))
                return
            self.post_message(self.CanvasClicked())

    # -- minimal (single window) mode ----------------------------------------------

    def set_single(self, on: bool) -> None:
        if on == self.single:
            return
        self.single = on
        if not on:
            for w in self.windows:
                if not self.in_view(w):
                    continue
                w.styles.visibility = "visible"
                w.title_width = None
                w.apply_geom(w.geom, w.frac)  # back to the stored slot
                w._update_title()
        self._apply_single()
        self.sync_huts()
        self._apply_town()

    def _apply_single(self) -> None:
        """Show only the active window over the whole desktop; stored geometry is untouched."""
        if not self.single:
            return
        width, height = self.dims
        for w in self.windows:
            if not self.in_view(w):
                continue
            w.remove_class("-town-open")
            if w is self.active:
                w.styles.visibility = "visible"
                w.styles.offset = (0, 0)
                w.styles.width, w.styles.height = width, height
                if w.title_width != width:
                    w.title_width = width
                    w._update_title()
            else:
                w.styles.visibility = "hidden"
        self.replan_roads()

    # -- window operations -------------------------------------------------------

    def _refuse_pinned(self, w: Window) -> bool:
        if self.town_active:
            self.app.notify("Town view: the building opens in its place — alt+v switches to tiles to arrange windows",
                            title="Windows")
            return True
        if w.pinned:
            self.app.notify(f"📌 {w.window_title} is pinned — alt+b unpins it", title="Windows")
        return w.pinned

    def toggle_pin(self, w: Window) -> None:
        w.set_pinned(not w.pinned)
        self.save()
        self.post_message(self.LayoutChanged())
        try:
            repo_root = getattr(self.app, "repo_root", None)
            if repo_root is not None:
                ev_type = "pinned" if w.pinned else "unpinned"
                chronicles.record(repo_root, self.scroll, w.window_id, ev_type)
        except OSError:
            pass

    def snap(self, w: Window, slot: str) -> None:
        if self._refuse_pinned(w):
            return
        w.set_restore(None)
        self.place(w, SNAP_SLOTS[slot])

    def move_by(self, w: Window, dx: int, dy: int) -> None:
        if self._refuse_pinned(w):
            return
        w.set_restore(None)
        w.apply_geom(geo.move(w.geom, dx * MOVE_STEP_X, dy * MOVE_STEP_Y, *self.dims), None)

    def resize_by(self, w: Window, dw: int, dh: int) -> None:
        if self._refuse_pinned(w):
            return
        w.set_restore(None)
        w.apply_geom(geo.resize(w.geom, dw * MOVE_STEP_X, dh * MOVE_STEP_Y, *self.dims), None)

    def toggle_maximize(self, w: Window) -> None:
        if self._refuse_pinned(w):
            return
        if w.restore is not None:
            g, frac = w.restore
            w.set_restore(None)
            if frac is not None:
                self.place(w, frac)
            else:
                w.apply_geom(geo.clamp(g, *self.dims), None)
        else:
            w.set_restore((w.geom, w.frac))
            self.place(w, SNAP_SLOTS["max"])
            self.raise_window(w)

    def tile(self) -> None:
        if self.town_active:
            self.set_town(False)
            return
        visible = [w for w in self.by_number() if self.in_view(w) and not w.hidden and not w.pinned]
        for w, frac in zip(visible, geo.tile_fracs(len(visible))):
            w.set_restore(None)
            self.place(w, frac)

    def hide(self, w: Window) -> None:
        if w.hidden:
            return
        w.display = False
        self.sync_huts()
        self.replan_roads()
        if w is self.active:
            nxt = None if self.town_active else self._top_visible()
            self.set_active(None)
            if nxt is not None:
                self.focus_window(nxt)
        self.post_message(self.LayoutChanged())
        try:
            repo_root = getattr(self.app, "repo_root", None)
            if repo_root is not None:
                chronicles.record(repo_root, self.scroll, w.window_id, "building_demolished")
        except OSError:
            pass

    def cycle(self, step: int) -> None:
        visible = [w for w in self.by_number() if self.in_view(w) and not w.hidden]
        if not visible:
            return
        idx = visible.index(self.active) if self.active in visible else -step
        self.focus_window(visible[(idx + step) % len(visible)])

    def toggle_window(self, w: Window) -> None:
        """Taskbar click: focus a background window, hide the active one."""
        if not self.in_view(w):
            self.focus_window(w)
            return
        if w is self.active and not w.hidden:
            self.hide(w)
        else:
            self.focus_window(w)

    def add_window(self, window: Window) -> None:
        """Mount a newly raised custom building window and register it with the taskbar."""
        self.window_list.append(window)
        self.mount(window)
        self.place(window, SNAP_SLOTS["center"])
        if self.scroll is not None:
            self.renumber_orkspace(self.scroll.active_orkspace_id)
        self.sync_huts()
        try:
            taskbar = self.app.query_one(Taskbar)
            status_item = taskbar.query_one("#taskbar-status")
            taskbar.mount(TaskbarItem(window, classes="taskbar-item"), before=status_item)
            taskbar.refresh_items()
        except Exception:
            pass
        self.focus_window(window)
        self.post_message(self.LayoutChanged())

    # -- window mode -------------------------------------------------------------

    def enter_window_mode(self) -> None:
        if self.window_mode:
            return
        self._mode_return_focus = self.app.focused
        self.window_mode = True
        self.can_focus = True
        self.add_class("-window-mode")
        if self.active is None:
            top = self._top_visible()
            if top is not None:
                self.set_active(top)
        self.focus()
        self.refresh_bindings()
        self.post_message(self.LayoutChanged())

    def exit_window_mode(self) -> None:
        if not self.window_mode:
            return
        self.window_mode = False
        self.remove_class("-window-mode")
        self.can_focus = False
        self.save()
        if self.active is not None and not self.active.hidden:
            self.focus_window(self.active)
        elif self._mode_return_focus is not None and self._mode_return_focus.is_attached:
            self._mode_return_focus.focus()
        self._mode_return_focus = None
        self.refresh_bindings()
        self.post_message(self.LayoutChanged())

    # -- town view ----------------------------------------------------------

    @property
    def town_active(self) -> bool:
        """Huts on the map: the town view, unless Minimal mode shows one window full size."""
        return self.town and not self.single and self.scroll is not None

    def anchor_geom(self, building_id: str) -> Geom | None:
        """Where a building sits on the map: its hut in the town view, else its window."""
        if self.town_active:
            hut = self.huts.get(building_id)
            return hut.geom if hut is not None and hut.display else None
        w = self.get_window(building_id)
        return w.geom if w is not None and not w.hidden and self.in_view(w) else None

    def set_town(self, on: bool) -> None:
        if on == self.town:
            return
        self.town = on
        if self.scroll is not None:
            self.scroll.preferences["view"] = "town" if on else "tiles"
        self.sync_huts()
        self._apply_town()
        if not on and self.active is None:
            top = self._top_visible()
            if top is not None:
                self.focus_window(top)
        self.replan_roads()
        self.save()
        self.post_message(self.LayoutChanged())

    def set_reserves(self, hut: int, open_: int, right: int = 0) -> None:
        if (hut, open_, right) == (self.hut_reserve, self.open_reserve, self.open_right):
            return
        moved = hut != self.hut_reserve
        if moved:
            self.capture()                   # spots as fractions of the old room
        self.hut_reserve, self.open_reserve, self.open_right = hut, open_, right
        if moved:
            self.sync_huts()
            self.replan_roads()
        self._apply_town()

    @property
    def hut_room(self) -> tuple[int, int]:
        """The part of the canvas the huts live in: all of it but the floating console's strip."""
        width, height = self.dims
        return width, max(height - self.hut_reserve, 1)

    def sync_huts(self) -> None:
        """One hut per shown building of this canvas, at its spot; the rest are hidden."""
        if not self.is_attached:
            return
        width, height = self.hut_room
        on = self.town_active and self.dims[0] > 0 and self.dims[1] > 0
        wanted = [w for w in self.by_number() if self.in_view(w) and not w.hidden] if on else []
        ids = {w.window_id for w in wanted}
        for bid, hut in self.huts.items():
            if bid not in ids:
                hut.display = False
        placed: list[Geom] = []
        new: list[tuple[Window, Hut]] = []
        for w in wanted:
            hut = self.huts.get(w.window_id)
            spec = self.app.spec_of(w.window_id) if hasattr(self.app, "spec_of") else None
            sil, actions = silhouettes.of(spec, w.window_id), catalog.quick_actions_of(spec) if spec else []
            if hut is None:
                hut = Hut(w.window_id, sil, actions)
                self.huts[w.window_id] = hut
                self.mount(hut, after=self.terrain)
            hut.display = True
            hut.set_silhouette(sil, actions)
            hut.set_title(w.number, w.window_title)
            hut.set_badge(w.badge)
            hut.set_class(w is self.active, "-expanded")
            hw, hh = hut.geom.w, hut.geom.h
            if w.window_id == TOWN_HALL:     # fixed in the bottom-right corner
                hut.fixed = True
                hut.place(Geom(max(width - hw, 0), max(height - hh, 0), hw, hh))
                placed.append(hut.geom)
                continue
            spec = self.scroll.building(w.window_id) if self.scroll is not None else None
            if spec is not None and spec.hut and len(spec.hut) == 2:
                hut.place(geo.hut_from_frac(float(spec.hut[0]), float(spec.hut[1]), width, height, hw, hh))
                placed.append(hut.geom)
            else:
                new.append((w, hut))
        # New huts take their place on shelves cut for the sizes of all of them (each row spread over
        # the width, the rows over the height); a spot that is taken falls back to the first free one.
        shown = [self.huts[w.window_id] for w in wanted]
        cells = geo.hut_shelves(width, height, [(h.geom.w, h.geom.h) for h in shown])
        index = {w.window_id: i for i, w in enumerate(wanted)}
        for w, hut in new:
            hw, hh = hut.geom.w, hut.geom.h
            x, y = cells[index[w.window_id]]
            spot = Geom(x, y, hw, hh)
            if any(geo.overlaps(spot, p, 1, 0) for p in placed):
                spot = geo.first_free(width, height, hw, hh, placed) or geo.clamp(Geom(x + 2, y + 1, hw, hh), width, height)
            hut.place(spot)
            placed.append(spot)

    # -- the ghost of a building being placed ---------------------------------------

    def start_ghost(self, label: str, size: tuple[int, int], on_done) -> bool:
        """Walk a ghost hut over the town; `on_done((fx, fy))` where it settles, `on_done(None)` on
        Esc. False when there is no town on screen to place it in (tiles, Minimal)."""
        if not self.town_active or self.dims[0] <= 0 or self.dims[1] <= 0 or self.ghost is not None:
            return False
        width, height = self.hut_room
        w, h = size
        taken = [hut.geom for hut in self.huts.values() if hut.display]
        start = Geom(max((width - w) // 2, 0), max((height - h) // 2, 0), w, h)   # the middle of the town
        self.ghost = Ghost(label, start, (width, height), taken)
        self._ghost_done = on_done
        self.mount(self.ghost)
        self.ghost.focus()
        self.ghost.capture_mouse()
        return True

    def on_ghost_done(self, message: Ghost.Done) -> None:
        message.stop()
        ghost, done = self.ghost, self._ghost_done
        self.ghost, self._ghost_done = None, None
        if ghost is not None:
            ghost.release_mouse()
            ghost.remove()
        if done is not None:
            g = message.geom
            done(geo.hut_to_frac(g.x, g.y, *self.hut_room, g.w, g.h) if g is not None else None)

    def _settle(self, hut: Hut) -> None:
        """A hut that changed size stays on the canvas and off its neighbours: it keeps its spot when
        that is free, else takes the nearest free one (and the town keeps it)."""
        width, height = self.hut_room
        others = [h.geom for h in self.huts.values() if h is not hut and h.display]
        g = hut.geom
        g = Geom(min(max(g.x, 0), max(width - g.w, 0)), min(max(g.y, 0), max(height - g.h, 0)), g.w, g.h)
        if any(geo.overlaps(g, o, 1, 0) for o in others):
            g = geo.first_free(width, height, g.w, g.h, others) or g
        if g != hut.geom:
            hut.place(g)
        self.post_message(Hut.Moved(hut))

    def refresh_huts(self) -> None:
        """Live status lines: each building's view says what its hut shows (`hut_lines`, else `mini_status`)."""
        for bid, hut in self.huts.items():
            if not hut.display:
                continue
            w = self.get_window(bid)
            body = next(iter(w.children), None) if w is not None else None
            lines_of = getattr(body, "hut_lines", None)
            status = getattr(body, "mini_status", None)
            try:
                if hut.base.grow and lines_of is not None:   # a chart or a preview takes the rows it needs
                    probe = lines_of(silhouettes.fit(hut.base, silhouettes.GROW_ROWS[hut.base.grow][1]).live_widths)
                    if hut.set_rows(silhouettes.rows_needed(hut.base, probe)):
                        self._settle(hut)
                lines = lines_of(hut.live_widths) if lines_of is not None else status() if status is not None else []
            except Exception:   # a status line must never take the town down
                lines = []
            hut.set_status(lines)
            if w is not None:
                hut.set_badge(w.badge)
                hut.set_title(w.number, w.window_title)

    def flicker_fires(self) -> None:
        """A hut whose orc waits for orders burns: its fence flickers."""
        for hut in self.huts.values():
            if hut.display and hut.has_class("-alert"):
                hut.toggle_class("-flame")
            elif hut.has_class("-flame"):
                hut.remove_class("-flame")

    def _rally_click(self, w: Window) -> bool:
        """Road mode: a click on a building picks it as the source."""
        if not self.rally_mode:
            return False
        pick = getattr(self.app, "rally_pick_number", None)
        if pick is not None and w.window_id != self.rally_source:
            pick(w.number)
        return True

    def on_hut_clicked(self, message: Hut.Clicked) -> None:
        w = self.get_window(message.hut.building_id)
        if w is None or self._rally_click(w):
            return
        if w is self.active:
            self.post_message(self.CanvasClicked())   # a second click collapses it
            return
        self.focus_window(w)
        self.post_message(Window.Activated(w))

    def on_hut_action_pressed(self, message: Hut.ActionPressed) -> None:
        message.stop()
        run = getattr(self.app, "run_quick_action", None)
        if run is not None:
            run(message.hut.building_id, message.action_id)

    def on_hut_moved(self, message: Hut.Moved) -> None:
        self.save()
        self.replan_roads()

    def _apply_town(self) -> None:
        """Town view: only the active building is shown, opened over the map; tiles: all of them."""
        if self.single or not self.is_attached:
            return
        on = self.town_active
        width, height = self.dims
        for w in self.windows:
            if not self.in_view(w):
                continue
            if not on:
                if w.has_class("-town-open") or w.styles.visibility == "hidden":
                    w.remove_class("-town-open")
                    w.styles.visibility = "visible"
                    w.title_width = None
                    w.apply_geom(w.geom, w.frac)
                    w._update_title()
                continue
            if w is self.active and not w.hidden and width > 0 and height > 0:
                g = geo.frac_to_geom(geo.TOWN_SLOT, width, max(height - self.open_reserve, geo.MIN_H + 2))
                if self.open_right and g.x + g.w > width - self.open_right:   # clear of the orc's chat
                    g = Geom(g.x, g.y, max(width - self.open_right - g.x - 1, geo.MIN_W), g.h)
                w.add_class("-town-open")
                w.styles.visibility = "visible"
                w.styles.offset = (g.x, g.y)
                w.styles.width, w.styles.height = g.w, g.h
                if w.title_width != g.w:
                    w.title_width = g.w
                    w._update_title()
            else:
                w.remove_class("-town-open")
                w.styles.visibility = "hidden"
        for bid, hut in self.huts.items():
            hut.set_class(on and self.active is not None and self.active.window_id == bid, "-expanded")

    # -- roads -------------------------------------------------------------------

    def replan_roads(self) -> None:
        """Re-plan the roads after the current refresh (at most once per refresh)."""
        if self._replan_pending or not self.is_attached:
            return
        self._replan_pending = True
        self.call_after_refresh(self._replan_now)

    def select_road(self, key: str | None) -> None:
        if key != self.selected_road:
            self.selected_road = key
            self._render_roads()

    def _visible_geoms(self) -> dict[str, Geom]:
        if self.single:
            return {}
        if self.town_active:   # roads join the huts, so expanding a building never moves them
            return {bid: h.geom for bid, h in self.huts.items() if h.display}
        return {w.window_id: w.geom for w in self.windows if self.in_view(w) and not w.hidden}

    def _replan_now(self) -> None:
        self._replan_pending = False
        if not self.is_attached or self.scroll is None:
            return
        width, height = self.dims
        geoms = self._visible_geoms()
        roads = [(road_key(b.id, r.id), r.source, b.id) for b in self.scroll.buildings for r in b.roads
                 if b.id in geoms and r.source in geoms]
        anchors = {bid: h.body_geom for bid, h in self.huts.items() if bid in geoms} if self.town_active else None
        self.road_paths = roadmap.plan(geoms, roads, width, height, anchors) if roads else {}
        if self.selected_road is not None and self.selected_road not in self.road_paths:
            self.selected_road = None
        self._render_roads()
        self.traffic.replaced()

    def _road_label(self, key: str) -> str:
        from orkcraft.widgets.road_layer import split_key
        target_id, road_id = split_key(key)
        if self.scroll is None:
            return key
        found = scroll.find_road(self.scroll, road_id, target_id)
        if found is None:
            return key
        target, road = found
        src = self.scroll.building(road.source)
        orc = target.garrison.handler(road.handler) if road.handler else None
        who = f"{orc.avatar} {orc.name}" if orc else "plain"
        src_label = f"{src.icon} {src.title}".strip() if src else road.source
        signal = f" ({road.label})" if road.label else ""
        return f"{who} · {src_label} → {f'{target.icon} {target.title}'.strip()}{signal}"

    def _render_roads(self) -> None:
        """Gap cells to the Terrain, gates and the selected road to the `roads` layer."""
        if not self.is_attached:
            return
        mode = self.scroll.preferences.get("roads", "faint") if self.scroll is not None else "faint"
        focus = self.active.window_id if self.active is not None and not self.active.hidden else None
        cells: dict[tuple[int, int], tuple[str, str]] = {}
        for key, p in self.road_paths.items():
            selected = key == self.selected_road
            bright = selected or (focus is not None and focus in (p.source, p.target))
            if mode == "off" and not bright:
                continue
            for x, y, ch in p.glyphs:
                if (x, y) not in p.covered:
                    cells[(x, y)] = (ch, "selected" if selected else "bright" if bright else "faint")
        self.terrain.set_roads(cells)
        biome = theme.BIOMES.get(self.biome, theme.BIOMES[theme.DEFAULT_BIOME])
        signature = (tuple(sorted((k, p.exit, p.entry, tuple(p.cells)) for k, p in self.road_paths.items())),
                     self.selected_road, self.biome, self._handler_keys())
        if signature == self._road_signature:
            return
        self._road_signature = signature
        for piece in list(self.query(".road-gate, .road-run, .road-label")):
            piece.remove()
        pieces = []
        handled = self._handler_keys()
        for key, p in self.road_paths.items():
            colour = biome.border_focus if key in handled else biome.border
            gate_style = f"bold {colour} on {biome.window_bg}"
            pieces.append(RoadGate(key, EXIT_GLYPH[p.exit.side], p.exit.x, p.exit.y, gate_style))
            pieces.append(RoadGate(key, ENTRY_GLYPH, p.entry.x, p.entry.y, gate_style))
        p = self.road_paths.get(self.selected_road) if self.selected_road else None
        if p is not None:
            style = f"bold {ROAD_SELECTED} on {biome.canvas}"
            covered = [c for c in p.glyphs if (c[0], c[1]) in p.covered]
            for run in runs(covered):
                pieces.append(RoadRun(p.road_id, run, style))
            label = self._road_label(p.road_id)
            mx, my, _ = p.glyphs[len(p.glyphs) // 2] if p.glyphs else (p.exit.x, p.exit.y, "")
            width = self.dims[0]
            lx = max(0, min(mx - (len(label) + 2) // 2, width - len(label) - 2))
            ly = my - 1 if my > 0 else my + 1
            pieces.append(RoadLabel(p.road_id, label, lx, ly, f"bold #1a1206 on {ROAD_SELECTED}"))
        if pieces:
            self.mount_all(pieces)

    def traffic_changed(self) -> None:
        """Carts or coins appeared: run the 8 fps timer only while something moves."""
        if self._traffic_timer is None:
            self._traffic_timer = self.set_interval(1 / CART_FPS, self._traffic_tick)
        else:
            self._traffic_timer.resume()

    def _traffic_tick(self) -> None:
        self.traffic.tick()
        if not self.traffic.busy and self._traffic_timer is not None:
            self._traffic_timer.pause()

    def _handler_keys(self) -> frozenset[str]:
        if self.scroll is None:
            return frozenset()
        return frozenset(road_key(b.id, r.id) for b in self.scroll.buildings for r in b.roads if r.handler)

    # -- rally mode --------------------------------------------------------------

    def enter_rally_mode(self, anchor_id: str, candidates: set[str] | None = None) -> None:
        """Pick a window by its number. `candidates` are highlighted (default: the rally-pipe
        targets of `anchor_id`); `Y` passes the possible road sources of the receiver."""
        self.rally_mode = True
        self.rally_source = anchor_id
        for w in self.windows:
            if self.in_view(w) and w.window_id != anchor_id:
                ok = (w.window_id in candidates) if candidates is not None else bool(pipes.modes_for(anchor_id, w.window_id))
                w.set_class(ok, "-rally-target")
            else:
                w.remove_class("-rally-target")
            if (hut := self.huts.get(w.window_id)) is not None:
                hut.set_class(w.has_class("-rally-target"), "-rally-target")
        self.can_focus = True
        self.focus()
        self.post_message(self.LayoutChanged())

    def exit_rally_mode(self) -> None:
        if not self.rally_mode:
            return
        self.rally_mode = False
        self.rally_source = None
        for w in self.windows:
            w.remove_class("-rally-target")
        for hut in self.huts.values():
            hut.remove_class("-rally-target")
        self.can_focus = False
        if self.active is not None and not self.active.hidden:
            self.focus_window(self.active)
        self.post_message(self.LayoutChanged())

    def on_key(self, event: events.Key) -> None:
        if self.rally_mode:
            app = self.app
            if event.key in "123456789":
                if hasattr(app, "rally_pick_number"):
                    app.rally_pick_number(int(event.key))
            else:
                self.exit_rally_mode()
            event.stop()
            event.prevent_default()

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        # Every desktop binding is a window-mode binding.
        return self.window_mode

    def _need_active(self) -> Window | None:
        if self.active is None or self.active.hidden:
            return None
        return self.active

    def action_exit_window_mode(self) -> None:
        self.exit_window_mode()

    def action_nudge(self, dx: int, dy: int) -> None:
        if (w := self._need_active()) is not None:
            self.move_by(w, dx, dy)

    def action_grow(self, dw: int, dh: int) -> None:
        if (w := self._need_active()) is not None:
            self.resize_by(w, dw, dh)

    def action_snap(self, slot: str) -> None:
        if (w := self._need_active()) is not None:
            self.snap(w, slot)

    def action_toggle_maximize(self) -> None:
        if (w := self._need_active()) is not None:
            self.toggle_maximize(w)

    def action_tile(self) -> None:
        self.tile()

    def action_hide_window(self) -> None:
        if (w := self._need_active()) is not None:
            self.hide(w)

    def action_cycle(self, step: int) -> None:
        self.cycle(step)

    def action_focus_number(self, number: int) -> None:
        for w in self.windows:
            if w.number == number and self.in_view(w):
                self.focus_window(w)
                return

    def action_toggle_link(self) -> None:
        self.preview_linked = not self.preview_linked
        state = "linked to the selection" if self.preview_linked else "pinned"
        self.app.notify(f"Preview is {state}", title="Windows")
        self.post_message(self.LayoutChanged())

    def action_save_layout(self) -> None:
        ok = self.save()
        self.app.notify(
            f"Scroll saved to {self.scroll_path}" if ok else "Scroll could not be saved",
            title="Town Scroll",
            severity="information" if ok else "error",
        )

    def action_reset_layout(self) -> None:
        self.apply_default_layout()
        self.save()

    # -- preview link --------------------------------------------------------------

    def _from_preview(self, widget: Widget | None) -> bool:
        w = self.window_of(widget)
        return w is not None and w.window_id == self.preview_id

    def _route(self, source: Widget, value: object) -> None:
        if self._from_preview(source):
            return
        node_id = node_id_of(value)
        if not node_id:
            return
        w = self.window_of(source)
        source_id = w.window_id if w is not None else None
        self.post_message(self.NodeHighlighted(node_id, source_id=source_id))
        if source_id and self.scroll is not None:
            if has_outgoing(self.scroll, source_id, pipes.ON_SELECTION):
                self.post_message(self.PayloadEmitted(
                    pipes.Payload(kind=pipes.NODE, value=node_id, source=source_id, mode=pipes.ON_SELECTION)
                ))

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        self._route(event.list_view, getattr(event.item, "task_id", None))

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        self._route(event.data_table, event.row_key.value if event.row_key is not None else None)

    def on_tree_node_highlighted(self, event: Tree.NodeHighlighted) -> None:
        w = self.window_of(event.node.tree)
        if w is not None and w.window_id == "loot":
            node_data = event.node.data
            if hasattr(node_data, "path"):
                p = Path(node_data.path)
                if p.is_file():
                    if self.scroll is not None:
                        if has_outgoing(self.scroll, "loot", pipes.ON_SELECTION):
                            repo_root = getattr(self.app, "repo_root", None)
                            if repo_root is not None:
                                try:
                                    rel = str(p.resolve().relative_to(Path(repo_root).resolve()))
                                except ValueError:
                                    rel = str(p)
                                self.post_message(self.PayloadEmitted(
                                    pipes.Payload(kind=pipes.FILE, value=rel, source="loot", mode=pipes.ON_SELECTION)
                                ))
        self._route(event.node.tree, event.node.data)

    def on_option_list_option_highlighted(self, event: OptionList.OptionHighlighted) -> None:
        self._route(event.option_list, event.option_id)


class Taskbar(Horizontal):
    """One clickable tab per window: active highlighted, hidden dimmed."""

    DEFAULT_CSS = """
    Taskbar {
        height: 1;
        width: 100%;
        background: $surface;
    }
    Taskbar > .taskbar-item {
        width: auto;
        padding: 0 1;
        color: $text-muted;
    }
    Taskbar > .taskbar-item:hover {
        background: $surface-lighten-2;
    }
    Taskbar > .taskbar-item.-active {
        background: $accent 40%;
        color: $text;
        text-style: bold;
    }
    Taskbar > .taskbar-item.-hidden {
        color: $text-disabled;
        text-style: italic;
    }
    Taskbar > .taskbar-status {
        width: 1fr;
        content-align: right middle;
        padding: 0 1;
        color: $text-muted;
    }
    """

    def __init__(self, desktop: Desktop, id: str | None = None) -> None:
        super().__init__(id=id)
        self.desktop = desktop
        self.compact = False  # narrow terminals: number + icon only

    def compose(self):  # type: ignore[override]
        for w in sorted(self.desktop.window_list, key=lambda w: w.number):
            yield TaskbarItem(w, classes="taskbar-item")
        yield Static("", id="taskbar-status", classes="taskbar-status")

    def refresh_items(self) -> None:
        for item in self.query(TaskbarItem):
            w = item.window
            in_active = self.desktop.in_view(w)
            item.display = in_active
            if in_active:
                item.set_class(w is self.desktop.active and not w.hidden, "-active")
                item.set_class(w.hidden, "-hidden")
                item.update(Text(f"{w.number} {w.window_title.split()[0]}" if self.compact else f"{w.number} {w.window_title}"))
        status = Text()
        if getattr(self.desktop, "rally_mode", False):
            status.append("🛤 ROAD — click the source building (or press its number) · esc cancels")
        elif self.desktop.window_mode:
            status.append(" WINDOW MODE ", style="bold reverse")
            status.append("  ←↑↓→ move · shift+←↑↓→ resize · esc done ")
        else:
            status.append("preview: ")
            status.append("linked" if self.desktop.preview_linked else "pinned", style="bold")
            status.append("  ·  ctrl+w windows · ? help ")
        self.query_one("#taskbar-status", Static).update(status)


class TaskbarItem(Static):
    def __init__(self, window: Window, classes: str | None = None) -> None:
        super().__init__(f"{window.number} {window.window_title}", classes=classes, id=f"taskbar-{window.window_id}")
        self.window = window

    def on_click(self, event: events.Click) -> None:
        desktop = self.window.parent
        if isinstance(desktop, Desktop):
            desktop.toggle_window(self.window)
        event.stop()
