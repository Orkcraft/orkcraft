"""Orkcraft: an RTS-style terminal harness for multi-agent work in any git project.

Layout: HUD on top · desktop of buildings (movable windows) · lower RTS console
(War Map, Clan Roster, Command Card) · taskbar · footer.
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path

from textual.screen import Screen
from textual.app import App, ComposeResult
from textual.binding import Binding

from orkcraft.realm import feedback
from orkcraft.realm.buildings import Building
from orkcraft.screens.console import CONSOLE_DEFAULT_PCT, Console
from orkcraft.env import getenv
from orkcraft import schedule
from orkcraft.screens.orc_chat import OrcChat
from orkcraft.screens.chat_view import ChatView
from orkcraft.widgets.hud import Hud
from orkcraft.widgets.office import OfficeFooter
from orkcraft.wm import Desktop, Taskbar, Window
from orkcraft.core import bus
from orkcraft.core.night import Night
from orkcraft.core.roster import Muster
from orkcraft.core.sessions import Sessions
from orkcraft.core.town import Town
from orkcraft.core.treasury import Treasury
from orkcraft.tui import wording
from orkcraft.tui.base import delegate
from orkcraft.tui.views import make_view
# Re-exported: tests and older callers import these from orkcraft.app.
from orkcraft.tui.base import (  # noqa: F401
    STEWARD_CHECK_S, FULL_MIN_COLS, COMPACT_MIN_COLS, ROSTER_REFRESH_S, HUT_REFRESH_S, SCHEDULE_TICK_S,
    PROBATION_CHECK_S, FIRE_FLICKER_S, ORC_CHAT_REFRESH_S, ORC_CHAT_PCT, BUILDING_CONSOLE_MIN_H,
    WARMAP_FLOAT_W, ROADS_TICK_S, TELEMETRY_REFRESH_S, HALT_RESET_S, ACTIVE_COMMAND_KEYS, FocusState,
    mode_for,
)
from orkcraft.tui.focus import FocusMixin
from orkcraft.tui.layout import LayoutMixin
from orkcraft.tui.night import NightMixin
from orkcraft.tui.raising import RaisingMixin
from orkcraft.tui.commands import CommandsMixin
from orkcraft.tui.orkspaces import OrkspacesMixin
from orkcraft.tui.sessions import SessionsMixin
from orkcraft.tui.delivery import DeliveryMixin
from orkcraft.tui.roads import RoadsMixin
from orkcraft.tui.garrison import GarrisonMixin
from orkcraft.tui.treasury import TreasuryMixin
from orkcraft.tui.roster import RosterMixin
from orkcraft.tui.council import CouncilMixin
from orkcraft.tui.building import BuildingMixin
from orkcraft.tui.retros import RetrosMixin


class OrkcraftApp(
    FocusMixin,
    LayoutMixin,
    NightMixin,
    RaisingMixin,
    CommandsMixin,
    OrkspacesMixin,
    SessionsMixin,
    DeliveryMixin,
    RoadsMixin,
    GarrisonMixin,
    TreasuryMixin,
    RosterMixin,
    CouncilMixin,
    BuildingMixin,
    RetrosMixin,
    App[int],
):
    """Orkcraft TUI."""

    TITLE = "Orkcraft"
    # ctrl+p belongs to Halt All; Textual's command palette moves to ctrl+k.
    COMMAND_PALETTE_BINDING = "ctrl+k"

    BINDINGS = [
        Binding("q", "graceful_quit", "Quit"),
        Binding("ctrl+p", "halt('ctrl+p')", "Halt All", priority=True, show=False),
        Binding("space", "halt('space')", "🛑 Halt All", show=True),
        Binding("escape", "escape", "Deselect", show=False),
        *[Binding(str(i), f"focus_number({i})", show=False) for i in range(1, 10)],
        *[Binding(f"alt+{i}", f"focus_number({i})", show=False) for i in range(1, 10)],
        Binding("plus", "spawn_orc", "Spawn Ork", show=True),
        Binding("exclamation_mark", "next_alert", "🔥 Orders", show=True),
        Binding("ctrl+b", "toggle_console", "Console", show=False),
        Binding("alt+b", "toggle_pin", "📌 Pin", show=False),
        Binding("alt+t", "toggle_terrain", "Terrain", show=False),
        Binding("alt+c", "cycle_carts", "Carts", show=False),
        Binding("alt+v", "toggle_view", "Town / Tiles", show=False),
        Binding("slash", "focus_orc_chat", "Type to the ork", show=False),
        Binding("left_square_bracket", "quick_action(0)", "Quick action 1", show=False),
        Binding("right_square_bracket", "quick_action(1)", "Quick action 2", show=False),
        Binding("f10", "system_menu", "Menu", show=True),
        # Orkspace canvas switching (F1-F8) and creation (N)
        *[Binding(f"f{i}", f"orkspace('F{i}')", show=False) for i in range(1, 9)],
        Binding("N", "new_orkspace", "New Orkspace", show=False),
        Binding("G", "command_card('G')", "Worktree", show=False),
        Binding("alt+minus", "console_height(-3)", "Console smaller", show=False),
        Binding("alt+equals_sign", "console_height(3)", "Console taller", show=False),
        # Command Card keys (capital letters, gated per state in check_action)
        Binding("B", "command_card('B')", "Build", show=False),
        Binding("P", "command_card('P')", "Presets / Pin", show=False),
        Binding("S", "command_card('S')", "Spawn", show=False),
        Binding("T", "command_card('T')", "Terrain / Triggers", show=False),
        Binding("R", "command_card('R')", "Recruit", show=False),
        Binding("L", "command_card('L')", "Chronicles", show=False),
        Binding("Y", "command_card('Y')", "Rally Points", show=False),
        Binding("U", "command_card('U')", "Clear Rally", show=False),
        Binding("M", "command_card('M')", "Window Mode", show=False),
        Binding("X", "command_card('X')", "Demolish", show=False),
        Binding("Z", "command_card('Z')", "Revert", show=False),
        Binding("K", "command_card('K')", "Like", show=False),
        Binding("F", "command_card('F')", "Dislike", show=False),
        Binding("C", "command_card('C')", "Chat / Orders", show=False),
        Binding("D", "command_card('D')", "Dismiss / Redesign", show=False),
        Binding("H", "command_card('H')", "Halt", show=False),
        Binding("W", "command_card('W')", "Watch (steward)", show=False),
        # Custom building action keys (free keys)
        *[Binding(k, f"custom_action('{k}')", show=False) for k in ("A", "E", "F", "G", "I", "J", "K", "O", "Q", "V", "W", "Z")],
        Binding("o", "open_chat", "Session", show=True),
        Binding("r", "refresh_graph", "Refresh", show=False),
        Binding("c", "toggle_commit", "Commit", show=False),
        Binding("ctrl+w", "window_mode", "Windows", show=True),
        Binding("f9", "cycle_window(1)", show=False),
        Binding("shift+f9", "cycle_window(-1)", show=False),
        Binding("tab", "tab_cycle(1)", show=False, priority=True),  # Minimal only (check_action)
        Binding("shift+tab", "tab_cycle(-1)", show=False, priority=True),
        # Move / resize the active window without entering window mode.
        *[Binding(f"alt+{k}", f"move_active({dx}, {dy})", show=False)
          for keys, dx, dy in ((("h", "left"), -1, 0), (("l", "right"), 1, 0), (("k", "up"), 0, -1), (("j", "down"), 0, 1))
          for k in keys],
        *[Binding(k, f"resize_active({dx}, {dy})", show=False)
          for keys, dx, dy in ((("alt+shift+h", "alt+H", "alt+shift+left"), -1, 0),
                               (("alt+shift+l", "alt+L", "alt+shift+right"), 1, 0),
                               (("alt+shift+k", "alt+K", "alt+shift+up"), 0, -1),
                               (("alt+shift+j", "alt+J", "alt+shift+down"), 0, 1))
          for k in keys],
        Binding("question_mark", "show_help", "Help", show=False),
    ]

    DEFAULT_CSS = """
    Screen { background: $background; color: $text; layout: vertical; layers: base overlay; }
    """

    def __init__(
        self,
        repo_root: Path | None = None,
        auto_commit: bool | None = None,
        layout_file: Path | None = None,
        reset_layout: bool = False,
        demo: bool = False,
    ) -> None:
        wording.install()                    # in the Office every label says the Office's words
        super().__init__()
        # The town without a face (core/town.py): the project, its Town Scroll, specs and treasury.
        self.core = Town(repo_root, auto_commit, layout_file, reset_layout, demo)
        self.core.saver = lambda: self.desktop.save()        # the desktop records what it laid out first
        self.treasury = Treasury(self.core)
        self.muster = Muster(self.core)     # the roster: every ork, their questions
        self.night = Night(self.core)       # quiet hours: the Elders and the orks' own changes
        self.tent = Sessions(self.core)     # the orks' CLI sessions (the War Tent draws them)
        self.tent.on_output = self._session_output
        self._wire_bus()
        self.selected_node: str | None = None
        self._hushed = False                 # the orcs at work: no toasts, no dialogs (the ledger tells)
        self.worktree_marks: dict[str, str] = {}
        self._watching: set[str] = set()
        # Roads (core/delivery.py): the engine is the town's; its callbacks reach the UI thread.
        self.core.call = self._call_on_ui
        self.core.budget_ok = lambda: not self.demo and not self.gold_exhausted()
        self.focus_state = FocusState("neutral")
        self.mode = "full"
        self._console_forced: bool | None = None  # user toggle in Compact / Minimal / Full

    # What the town without a face owns, seen as the app's own attributes (views and tests read them).
    demo = delegate("core", "demo")
    repo_root = delegate("core", "repo_root")
    config = delegate("core", "config")
    graph = delegate("core", "graph")
    buildings = delegate("core", "buildings")
    custom_specs = delegate("core", "custom_specs")
    mason_problems = delegate("core", "mason_problems")
    scroll = delegate("core", "scroll")
    scroll_problems = delegate("core", "scroll_problems")
    first_run = delegate("core", "first_run")
    run_id = delegate("core", "run_id")
    telemetry = delegate("core", "telemetry")
    snapshot = delegate("core", "snapshot")
    roads = delegate("core", "roads")
    roster = delegate("muster", "roster")
    dismissed = delegate("muster", "dismissed")
    deployments = delegate("muster", "deployments")
    alert_first_seen = delegate("muster", "alert_first_seen")
    advice = delegate("night", "advice")
    _elders_seen = delegate("night", "elders_seen")
    _elders_busy = delegate("night", "elders_busy")
    _elders_count = delegate("night", "elders_count")
    _quiet_since = delegate("night", "quiet_since")
    _evolve_busy = delegate("night", "evolve_busy")
    _evolve_tried = delegate("night", "evolve_tried")
    _evolve_count = delegate("night", "evolve_count")
    _probation_at = delegate("night", "probation_at")

    def _wire_bus(self) -> None:
        """What the core publishes, shown the Textual way (core/bus.py)."""
        on = self.core.bus.subscribe
        on(bus.TOAST, lambda e: self.notify(e.data["message"], title=e.data.get("title", ""),
                                            severity=e.data.get("severity", "information"),
                                            **({"timeout": e.data["timeout"]} if e.data.get("timeout") else {})))
        on(bus.ROADS, lambda e: self._roads_changed())
        on(bus.ROSTER, lambda e: self.refresh_roster())
        on(bus.HALL, lambda e: self._refresh_hall())
        on(bus.HUD, lambda e: self.refresh_hud())
        on(bus.SPEC, lambda e: self._spec_changed(e.data["building"], e.data["spec"], e.data.get("refresh", False)))
        on(bus.UI, lambda e: self._ui_changed(e.data["building"], e.data["ui"]))
        on(bus.SESSION, self._session_changed)
        self._wire_delivery()

    def get_default_screen(self) -> Screen:
        # The desktop focuses the home building itself; Textual's auto focus would pick the first
        # focusable widget in the DOM (the War Tent's session list) and make it the active window.
        # Only the town screen opts out: modals keep focusing their first input.
        screen = Screen(id="_default")
        screen.AUTO_FOCUS = ""
        return screen

    def compose(self) -> ComposeResult:
        desktop = Desktop(
            *(
                Window(make_view(b), window_id=b.id, title=b.label, number=n)
                for n, b in enumerate(self.buildings, 1)
            ),
            scroll=self.scroll,
            scroll_path=self.config.layout_file,
            preview_id="",
            home_id="loot",
            id="desktop",
            town=self.core,
        )
        self.mode = mode_for(self.size.width)
        console = Console(id="console")
        console.display = self.mode in ("full", "compact")
        desktop.single = self.mode == "minimal"
        self._desktop, self._console = desktop, console
        self._hud = Hud(id="hud", budget=self.scroll.budget)
        self._taskbar = Taskbar(desktop, id="taskbar")
        self._orc_chat = OrcChat(id="orc-chat")
        self._orc_chat.display = False
        self._console_signature: tuple = ()
        self.seen_alerts: set[str] = set()     # questions the operator opened from the garrison (no ❓ there)
        yield self._hud
        yield desktop
        # The console flows below the taskbar: docked at the bottom it would sit under the Footer.
        yield self._taskbar
        yield console
        yield self._orc_chat
        yield OfficeFooter()

    def on_mount(self) -> None:
        try:
            feedback.start_session(self.repo_root)        # the session's graph starts empty
        except OSError:
            pass
        if self.demo:
            self.call_after_refresh(self._show_demo_samples)
            self.notify("Showcase sandbox — simulated data. Chains run for real; agents show a prepared "
                        "last result and do not call a model. F1–F8 switch the scenarios.",
                        title="🎪 Orkcraft demo", timeout=10)
        pct = self.scroll.preferences.get("console_height_pct")
        self._console.set_height_pct(pct if isinstance(pct, int) else CONSOLE_DEFAULT_PCT)
        if self.scroll_problems:
            self.notify("\n".join(self.scroll_problems), title="Town Scroll", severity="warning")
        self.refresh_roster()
        self.refresh_telemetry()
        self.refresh_rally_indicators()
        self.set_interval(ROSTER_REFRESH_S, self.refresh_roster)
        self.set_interval(TELEMETRY_REFRESH_S, self.refresh_telemetry)
        self.set_interval(ROADS_TICK_S, self.roads.tick)
        self.set_interval(STEWARD_CHECK_S, self.check_stewards)
        self.set_interval(HUT_REFRESH_S, self.desktop.refresh_huts)
        self.set_interval(SCHEDULE_TICK_S, self.tick_schedule)
        self.set_interval(FIRE_FLICKER_S, self.desktop.flicker_fires)
        self.set_interval(ORC_CHAT_REFRESH_S, self._tick_orc_chat)
        self.call_after_refresh(self.desktop.refresh_huts)
        self.order_burning = self._order_burns()
        if self.desktop.quiet:
            began = schedule.quiet_started(self.desktop.machine) or dt.datetime.now()
            self._quiet_since = began.isoformat(timespec="seconds")
        self._elders_restore()
        if self.first_run and getenv("ONBOARDING").lower() not in ("0", "false", "no", "off"):
            self.call_after_refresh(self.start_onboarding)

    @property
    def desktop(self) -> Desktop:
        return self._desktop

    @property
    def chat(self) -> ChatView:
        return self._desktop.query_one("#chat-view", ChatView)

    def building(self, building_id: str) -> Building | None:
        return self.core.building(building_id)

    def on_unmount(self) -> None:
        self.roads.stop()
        try:
            self.desktop.save()
        except Exception:
            pass
