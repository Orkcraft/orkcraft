"""Desktop: hosts windows, keeps z-order and focus, snaps, tiles and persists them."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from rich.text import Text
from textual import events
from textual.binding import Binding
from textual.containers import Container, Horizontal
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Static

from orkcraft import settings, theme
from orkcraft.realm import lexicon, pipes
from orkcraft.realm.buildings import TOWN_HALL
from orkcraft.scroll import TownScroll
from orkcraft.widgets.carts import Traffic
from orkcraft.widgets.ghost import Ghost
from orkcraft.widgets.hut import Hut
from orkcraft.widgets.terrain import Terrain
from orkcraft.wm import roadmap
from orkcraft.wm.arrange import MOVE_STEP_X, MOVE_STEP_Y, ArrangeMixin
from orkcraft.wm.focus import FocusMixin, node_id_of
from orkcraft.wm.layout import LayoutMixin
from orkcraft.wm.roads import RoadsMixin
from orkcraft.wm.town_view import TownViewMixin
from orkcraft.wm.window import Window

__all__ = ["MOVE_STEP_X", "MOVE_STEP_Y", "Desktop", "Taskbar", "TaskbarItem", "node_id_of"]


class Desktop(LayoutMixin, FocusMixin, ArrangeMixin, TownViewMixin, RoadsMixin, Container):
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

    class HutSelected(Message):
        """A first click on a hut: the building is selected, not opened (a second click opens it)."""
        def __init__(self, building_id: str) -> None:
            super().__init__()
            self.building_id = building_id

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
        town: Any = None,
    ) -> None:
        self._town = town              # core.Town: it owns the machine's settings; None: the desktop keeps its own
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
        if town is None:
            self._machine = settings.load()
        self.huts: dict[str, Hut] = {}
        self.selected_hut: str | None = None    # a hut picked by a first click, still collapsed
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

    @property
    def machine(self) -> settings.MachineSettings:
        """The machine's settings (settings.py): the town's when there is one."""
        return self._town.machine if self._town is not None else self._machine

    @machine.setter
    def machine(self, value: settings.MachineSettings) -> None:
        if self._town is not None:
            self._town.machine = value
        else:
            self._machine = value

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
                title = lexicon.words(w.window_title) or w.window_title
                item.update(Text(f"{w.number} {title.split()[0]}" if self.compact else f"{w.number} {title}"))
        status = Text()
        if getattr(self.desktop, "rally_mode", False):
            status.append("🛤 " + "ROAD — click the source building (or press its number) · esc cancels")
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
        super().__init__(f"{window.number} {lexicon.words(window.window_title)}", classes=classes,
                         id=f"taskbar-{window.window_id}")
        self.window = window

    def on_click(self, event: events.Click) -> None:
        desktop = self.window.parent
        if isinstance(desktop, Desktop):
            desktop.toggle_window(self.window)
        event.stop()
