"""Orkcraft: an RTS-style terminal harness for multi-agent work in any git project.

Layout: HUD on top · desktop of buildings (movable windows) · lower RTS console
(War Map, Clan Roster, Command Card) · taskbar · footer.
"""
from __future__ import annotations

from dataclasses import dataclass
import contextlib
import copy
import dataclasses
import functools
import datetime as dt
import json
import threading
import time
from pathlib import Path
from typing import Any, Callable

from textual import events, work
from textual.screen import Screen
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Footer

from orkcraft.config import Config, find_project_root
from orkcraft import scroll
from orkcraft.scroll import OrcSpec
from orkcraft.realm import audit, blueprint, checkpoint, fastpath, feedback, housekeeping, optimize, weekly, metrics, builders, catalog, chronicles, huts, masonry, silhouettes, pipes, recruiter, roads, steward
from orkcraft.screens.orc_flow import OrcProgress, RecruitFailed, RecruitPreview, StewardView
from orkcraft.realm.buildings import BUILTIN_SPECS, TOWN_HALL, Building, custom_building, presets, registry
from orkcraft.realm.orcs import ALERT_ICON, Alert, Trigger, WORKER, RESIDENT, Orc, garrison_badge
from orkcraft.realm.roster import Roster, build_roster, worker_infos
from orkcraft.widgets.hut import footprint
from orkcraft.screens.build_flow import BuildFailed, BuildPreview, BuildProgress
from orkcraft.screens import builder_interview as bp_chat
from orkcraft.screens.builder_interview import BlueprintReview, BuilderChat, BuilderInterview
from orkcraft.screens.council_review import CouncilProgress, CouncilVerdict
from orkcraft.screens.feedback_modal import DislikeModal
from orkcraft.screens.proposal_modal import ProposalModal
from orkcraft.screens.road_rule_modal import RoadRuleModal
from orkcraft.screens.settings_modal import SettingsModal
from orkcraft.screens.weekly_modal import WeeklyReportModal
from orkcraft.screens.console import CONSOLE_DEFAULT_PCT, ClanRoster, Console, orc_key
from orkcraft.screens.chronicles_view import BuildingChronicles, UnitChronicles
from orkcraft.screens.custom_view import CustomBuildingView
from orkcraft.screens.typed import view_for
from orkcraft.screens.presets_modal import PresetsModal
from orkcraft.screens.orkspace_modal import OrkspaceModal
from orkcraft.screens.garrison_modal import GarrisonModal, OrcModelModal
from orkcraft.screens.build_wizard import BuildReview, BuildWizard
from orkcraft.screens.town_hall import TownHallView
from orkcraft.screens import onboarding
from orkcraft.realm import elders, evolution, town_builder, town_presets
from orkcraft.screens.changes import ChangesModal
from orkcraft import autonomy
from orkcraft.screens.autonomy import AutonomyStep
from orkcraft.screens.town_plan import TownPlanReview
from orkcraft.env import getenv
from orkcraft import schedule, settings
from orkcraft.screens.orc_chat import OrcChat
from orkcraft.screens.road_modal import PLAIN, RULE, RoadHandlerModal, SubscribeModal, _PickModal
from orkcraft.widgets.carts import CartClicked
from orkcraft.widgets.road_layer import RoadClicked, road_key, split_key
from orkcraft.screens.chat_view import ChatView
from orkcraft.screens.dialogs import Confirm, MessageModal, TextPrompt
from orkcraft.screens.orders import AlertModal, AwaitingOrdersModal, BuildModal, UnitModal
from orkcraft.screens.system_menu import (
    KEY_GROUPS,
    KeysCheatSheet,
    QuitConfirm,
    SystemMenu,
)
from orkcraft.sources.sessions import deploy_command
from orkcraft.sources import telemetry
from orkcraft.realm import modes, tiers, workshop, worktrees
from orkcraft.screens.worktree_modal import WorktreeModal
from orkcraft.widgets.hud import Hud, Resources
from orkcraft.widgets.office import OfficeFooter, OfficeStatic
from orkcraft.widgets.terminal import Terminal
from orkcraft.wm import Desktop, Taskbar, Window

BUILD_RUNNER = None
ELDERS_RUNNER = None        # tests: the Elders' model call (realm/elders.py)
RECRUIT_RUNNER = None     # tests replace the Recruiter's and the steward's Claude call
STEWARD_RUNNER = None
FASTPATH_RUNNER = None    # tests put a fake light model for the Council's Fast Path here
OPTIMIZE_RUNNER = None    # … and for the self-improvement proposals
WEEKLY_RUNNER = None      # … and for the weekly self-audit
STEWARD_CHECK_S = 60.0

FULL_MIN_COLS = 140     # ≥ 140: Full RTS — console + windows
COMPACT_MIN_COLS = 100  # 100–139: Compact — console + windows; < 100: Minimal single window
ROSTER_REFRESH_S = 1.0
HUT_REFRESH_S = 5.0      # status lines of the huts in the town view
SCHEDULE_TICK_S = 30.0   # Shift switches Office on and off, quiet hours begin and end
PROBATION_CHECK_S = 300.0  # how often the orcs' changes on probation are looked at
FIRE_FLICKER_S = 0.4     # a hut whose orc waits for orders burns
ORC_CHAT_REFRESH_S = 0.5  # the orc's chat mirrors its live session
ORC_CHAT_PCT = 45        # the chat column rises to this share of the screen; the rest stays low
BUILDING_CONSOLE_MIN_H = 9   # border, title, name, up to 3 lines about it, runs, roads, a spare row
WARMAP_FLOAT_W = 36      # the War Map's width when the console floats over the town
ROADS_TICK_S = 1.0
TELEMETRY_REFRESH_S = 5.0
HALT_RESET_S = 4.0

ACTIVE_COMMAND_KEYS = {
    "neutral": {"B", "P", "S", "T", "G"},
    "building": {"R", "L", "Y", "U", "P", "M", "X", "Z", "K", "F"},
    "unit": {"C", "L", "T", "D", "H", "W"},
    "road": {"H", "U"},
}


@dataclass
class FocusState:
    mode: str = "neutral"  # "neutral" | "building" | "unit" | "road"
    building_id: str | None = None
    orc_key: str | None = None
    road_key: str | None = None   # "<target id>:<road id>" in the road state


def mode_for(width: int) -> str:
    """Full RTS (console + windows) · Compact (console + windows) · Minimal (one window)."""
    return "full" if width >= FULL_MIN_COLS else ("compact" if width >= COMPACT_MIN_COLS else "minimal")


class OrkcraftApp(App[int]):
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
        Binding("plus", "spawn_orc", "Spawn Orc", show=True),
        Binding("exclamation_mark", "next_alert", "🔥 Orders", show=True),
        Binding("ctrl+b", "toggle_console", "Console", show=False),
        Binding("alt+b", "toggle_pin", "📌 Pin", show=False),
        Binding("alt+t", "toggle_terrain", "Terrain", show=False),
        Binding("alt+c", "cycle_carts", "Carts", show=False),
        Binding("alt+v", "toggle_view", "Town / Tiles", show=False),
        Binding("slash", "focus_orc_chat", "Type to the orc", show=False),
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
        Binding("D", "command_card('D')", "Dismiss", show=False),
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
        super().__init__()
        # The showcase sandbox (orkcraft --demo): simulated data, agent handlers never run.
        self.demo = demo
        self.repo_root = repo_root or find_project_root()
        self.config = Config(repo_root=self.repo_root)
        if auto_commit is not None:
            self.config.auto_commit = auto_commit
        if layout_file is not None:
            self.config.layout_file = layout_file
        target_layout = self.config.layout_file
        if reset_layout and target_layout is not None:
            target_layout.unlink(missing_ok=True)
        self.selected_node: str | None = None
        if self.demo:
            from orkcraft.demo.graph import Graph
            self.graph = Graph(self.repo_root)
        else:
            self.graph = None
        self.buildings: list[Building] = registry()
        specs, self.mason_problems = masonry.load_specs(self.repo_root)
        self.custom_specs: dict[str, dict] = {s["id"]: s for s in specs}
        pipes.TYPED.clear()                               # one town at a time (tests open several)
        for s in specs:                                   # what each typed building sends
            pipes.set_typed(s["id"], catalog.events_of(s))
        # Presets are the core registry only: a custom building is registered as `custom:<id>`
        # below, never as a preset (ensure_presets would add it demolished, as `legacy:<id>`).
        preset_specs = presets(self.buildings)
        for s in specs:
            self.buildings.append(custom_building(s))
        # 🧭 Onboarding (screens/onboarding.py) runs for a project with no Town Scroll yet.
        self.first_run = False
        if target_layout is None:
            self.scroll, self.scroll_problems = scroll.default_scroll(preset_specs), []
        else:
            legacy = [target_layout.with_name(".orcraft.json")] if target_layout.name == ".orkcraft.json" else []
            self.first_run = not demo and not target_layout.exists() and not any(p.exists() for p in legacy)
            self.scroll, self.scroll_problems = scroll.load(target_layout, preset_specs, legacy=legacy)
        scroll.ensure_presets(self.scroll, preset_specs)
        hall = self.scroll.building(TOWN_HALL)
        if hall is not None:
            hall.demolished = False          # the town's own building: always standing, on every canvas
        for s in specs:
            if self.scroll.building(s["id"]) is None:
                scroll.add_custom_building(self.scroll, s)
        self.scroll_problems.extend(self.mason_problems)
        self.roster = Roster()
        self.dismissed: set[str] = set()
        # 🏛 The Elders' advice on the orcs' questions, left in quiet hours (realm/elders.py).
        self.advice: dict[tuple, elders.Decision] = {}
        self._elders_seen: set[tuple] = set()
        self._elders_busy = False
        self._elders_count = 0
        self._quiet_since: str | None = None
        # 🔧 The orcs' own self-improvement in quiet hours (realm/evolution.py).
        self._hushed = False                 # the orcs at work: no toasts, no dialogs (the ledger tells)
        self._evolve_busy = False
        self._evolve_tried: set[str] = set()
        self._evolve_count = 0
        self._probation_at = 0.0          # 0: never looked yet
        # 🪙 / 🪵: sessions this run starts are tagged with its id (sources/telemetry.py).
        self.run_id = telemetry.new_run_id()
        self.telemetry = telemetry.Telemetry(self.repo_root, self.run_id)
        self.snapshot = telemetry.Snapshot()
        self._gold_warned = False
        self.worktree_marks: dict[str, str] = {}
        self._lumber_warned: set[str] = set()
        self.deployments: dict[str, str] = {}
        self._watching: set[str] = set()
        # Roads: events from a source building to the receivers' plain deliveries and handlers.
        self.roads = roads.Engine(
            lambda: self.scroll, self.repo_root,
            deliver=lambda target_id, payload: self.deliver_payload(target_id, payload),
            on_output=self.deliver_handler_output, on_run=self.on_handler_run, meta=self.payload_meta,
            on_cart=self.on_road_cart,
            budget_ok=lambda: not self.demo and not self.gold_exhausted(), call=self._call_on_ui,
            run_env={"ORKCRAFT_RUN": self.run_id},
        )
        self.focus_state = FocusState("neutral")
        self.mode = "full"
        self._console_forced: bool | None = None  # user toggle in Compact / Minimal / Full

    # -- layout --------------------------------------------------------------------------

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
                Window(b.factory(), window_id=b.id, title=b.label, number=n)
                for n, b in enumerate(self.buildings, 1)
            ),
            scroll=self.scroll,
            scroll_path=self.config.layout_file,
            preview_id="",
            home_id="loot",
            id="desktop",
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
        self.alert_first_seen: dict[str, float] = {}   # alert id → when the roster first had it
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
            self._quiet_since = dt.datetime.now().isoformat(timespec="seconds")
        if self.first_run and getenv("ONBOARDING").lower() not in ("0", "false", "no", "off"):
            self.call_after_refresh(self.start_onboarding)

    @property
    def desktop(self) -> Desktop:
        return self._desktop

    @property
    def chat(self) -> ChatView:
        return self._desktop.query_one("#chat-view", ChatView)


    def building(self, building_id: str) -> Building | None:
        return next((b for b in self.buildings if b.id == building_id), None)

    # -- responsive viewports ---------------------------------------------------------------

    def on_resize(self, event: events.Resize) -> None:
        mode = mode_for(event.size.width)
        if mode != self.mode:
            self._console_forced = None
        self.mode = mode
        self._apply_mode()

    def _apply_mode(self) -> None:
        console = self._console
        default_display = self.mode in ("full", "compact")
        console.display = self._console_forced if self._console_forced is not None else default_display
        self.desktop.set_single(self.mode == "minimal")
        self._hud.mode = self.mode
        self._taskbar.compact = self.mode != "full"
        self.on_desktop_layout_changed(None)
        self.layout_console()

    def action_toggle_console(self) -> None:
        console = self._console
        self._console_forced = not console.display
        self._apply_mode()

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        if action == "tab_cycle":
            return self.mode == "minimal"
        if action == "command_card":
            key = str(parameters[0]) if parameters else ""
            return key in ACTIVE_COMMAND_KEYS.get(self.focus_state.mode, set())
        if action == "custom_action":
            key = str(parameters[0]) if parameters else ""
            if self.focus_state.mode != "building" or not self.focus_state.building_id:
                return False
            spec = self.custom_specs.get(self.focus_state.building_id)
            if not spec:
                return False
            return any(a.get("key") == key for a in spec.get("actions", []))
        if action == "halt":
            if parameters and parameters[0] == "space":
                if self.focus_state.mode != "neutral":
                    return False
                focused = self.focused
                if focused is not None and getattr(focused, "can_focus", False):
                    if hasattr(focused, "value") or focused.__class__.__name__ in ("Input", "TextArea"):
                        return False
            return True
        if action == "new_orkspace":
            focused = self.focused
            if focused is not None and getattr(focused, "can_focus", False):
                if hasattr(focused, "value") or focused.__class__.__name__ in ("Input", "TextArea"):
                    return False
            return True
        return True

    def action_tab_cycle(self, step: int) -> None:
        self.desktop.cycle(step)

    # -- focus state machine -----------------------------------------------------------------

    def set_focus_state(
        self,
        mode: str,
        building_id: str | None = None,
        orc_key_val: str | None = None,
        road: str | None = None,
    ) -> None:
        if mode == "road" and road:
            self.focus_state = FocusState("road", building_id=split_key(road)[0], road_key=road)
        elif mode == "neutral":
            self.focus_state = FocusState("neutral", None, None)
        elif mode == "building":
            self.focus_state = FocusState("building", building_id=building_id, orc_key=None)
        elif mode == "unit":
            if not building_id and orc_key_val:
                orc = next((o for o in self.roster.orcs if orc_key(o) == orc_key_val), None)
                if orc and orc.building:
                    building_id = orc.building
            self.focus_state = FocusState("unit", building_id=building_id, orc_key=orc_key_val)
        if self.focus_state.mode != "road" and getattr(self, "_desktop", None) is not None:
            self._desktop.select_road(None)
        if hasattr(self, "_console") and self._console is not None:
            self._console.refresh_state(self.focus_state, self.roster)
            self.layout_console()
        self.refresh_bindings()  # check_action gates keys by state: the Footer must follow

    def action_escape(self) -> None:
        if getattr(self.desktop, "rally_mode", False):
            self.desktop.exit_rally_mode()
            return
        if self.focus_state.mode == "road" or (self.focus_state.mode == "unit" and self.focus_state.building_id
                                                and self.desktop.get_window(self.focus_state.building_id) is not None):
            # Back to the building: a garrison orc's inventory folds back into the garrison.
            self.set_focus_state("building", building_id=self.focus_state.building_id)
            return
        self.set_focus_state("neutral")
        self.desktop.set_active(None)
        if hasattr(self, "_console") and self._console is not None:
            self._console.focus_roster()

    def on_key(self, event: events.Key) -> None:
        if getattr(self.desktop, "rally_mode", False):
            if event.key in "123456789":
                self.rally_pick_number(int(event.key))
            else:
                self.desktop.exit_rally_mode()
            event.stop()
            event.prevent_default()

    def on_road_clicked(self, message: RoadClicked) -> None:
        self.select_road(message.key)

    def select_road(self, key: str) -> None:
        target_id, road_id = split_key(key)
        if self.scroll is None or scroll.find_road(self.scroll, road_id, target_id) is None:
            return
        self.desktop.select_road(key)
        self.set_focus_state("road", road=key)

    def on_desktop_canvas_clicked(self, message: Desktop.CanvasClicked) -> None:
        self.set_focus_state("neutral")
        self.desktop.set_active(None)
        if hasattr(self, "_console") and self._console is not None:
            self._console.focus_roster()

    def on_window_activated(self, message: Window.Activated) -> None:
        self.set_focus_state("building", building_id=message.window.window_id)
        if message.window.window_id == TOWN_HALL and getattr(self, "order_burning", False):
            town_presets.mark_order_seen(self.repo_root)      # opened: the order stops burning
            self.order_burning = False
            self.refresh_roster()
            order = town_presets.pending_order(self.repo_root)
            if order is not None:
                self.push_screen(Confirm("📜 A town waits to be raised. Plan it now?",
                                         f"“{order['prompt'][:300]}”\n\nThe Town Builder plans it from the "
                                         "building catalog (one Claude call); you approve the plan before "
                                         "anything is raised."),
                                 lambda yes: yes and self.build_town_from_order())

    # -- 🧭 onboarding ----------------------------------------------------------------------------

    def tick_schedule(self) -> None:
        """Every half minute: Shift turns Office on and off, quiet hours begin and end (schedule.py)."""
        self.desktop.apply_schedule()
        self.refresh_hud()
        quiet = self.desktop.quiet
        if quiet and self._quiet_since is None:
            self._quiet_since = dt.datetime.now().isoformat(timespec="seconds")
        elif not quiet and self._quiet_since is not None:
            self._elders_morning()
            self._quiet_since, self._elders_count, self._evolve_count = None, 0, 0
            self.show_changes(only_unseen=True)                  # what the orcs changed overnight
        self._elders_consider()
        self._evolve_consider()
        self._probation_tick()

    # -- 🔧 the orcs improve the camp themselves, in quiet hours, by autonomy (realm/evolution.py) ---

    @contextlib.contextmanager
    def hushed(self):
        """The orcs at work in quiet hours: no toasts and no dialogs — the ledger and the list tell."""
        if self._hushed:
            yield
            return
        self._hushed = True
        self.notify = lambda *a, **k: None                       # type: ignore[method-assign]
        try:
            yield
        finally:
            del self.notify
            self._hushed = False

    def _evolve_candidates(self) -> list[dict]:
        """What the daily proposal, the latest weekly report and the stewards left, that this level
        lets the orcs apply themselves and that was not applied or tried yet."""
        level, done = self.desktop.machine.autonomy, evolution.applied_keys(self.repo_root)
        out: list[dict] = []
        for p in optimize.pending(self.repo_root):
            out.append({"key": p.id, "change": p.action, "source": "daily", "building": p.building, "proposal": p})
        report = weekly.latest(self.repo_root)
        if report is not None and dt.datetime.fromisoformat(report.ts) > dt.datetime.now() - dt.timedelta(days=7):
            for item in report.items:
                if item.applicable and item.n not in report.applied:
                    key = (f"w{report.ts[:10]}-{item.n}" if item.change in ("shrink", "chain", "script")
                           else f"weekly:{report.ts}:{item.n}")
                    out.append({"key": key, "change": item.change, "source": "weekly", "building": item.building,
                                "report": report, "item": item})
        for b in self.scroll.buildings:
            data = steward.load_report(self.repo_root, b.id)
            for i, prop in enumerate((data or {}).get("proposals") or []):
                replay = prop.get("replay") or {}
                if prop.get("type") == "demote" and not replay.get("ready"):
                    continue
                out.append({"key": f"steward:{b.id}:{data.get('ts', '')}:{i}", "change": str(prop.get("type")),
                            "source": "steward", "building": b.id, "data": data, "index": i})
        return [c for c in out if evolution.allowed(c["change"], level)
                and c["key"] not in done and c["key"] not in self._evolve_tried]

    def _evolve_subject(self, c: dict) -> fastpath.Subject:
        """What the Council looks at for one change: the building, the orc or the road as it would be."""
        bid = c["building"]
        if c["source"] == "steward":
            prop = c["data"]["proposals"][c["index"]]
            if c["change"] in ("filter", "new_road"):
                return fastpath.Subject("road", bid, {"source": prop.get("from") or bid, "target": bid,
                                                      "event": prop.get("event", ""), "filter": prop.get("filter") or {}})
            b = self.scroll.building(bid)
            orc = b.garrison.handler(str(prop.get("orc"))) if b is not None else None
            data = {k: v for k, v in dataclasses.asdict(orc).items() if v is not None} if orc is not None else {"id": str(prop.get("orc"))}
            data.update({"kind": "chain", "chain": prop.get("chain") or []} if c["change"] == "demote"
                        else {"run": prop.get("run") or {}})
            return fastpath.Subject("agent", bid, {"orc": data})
        if c["source"] == "weekly" and c["change"] == "add_building":
            spec = weekly.new_spec(c["item"])
            return fastpath.Subject("building", spec["id"], spec)
        if c["source"] == "weekly" and c["change"] == "set_config":
            spec = dict(self.custom_specs.get(bid) or {})
            spec["config"] = {**(spec.get("config") or {}), str(c["item"].data["key"]): c["item"].data.get("value")}
            return fastpath.Subject("building", bid, spec)
        p = c.get("proposal")
        if p is None:
            item = c["item"]
            p = optimize.Proposal(c["key"], c["report"].ts, bid, item.change, str(item.data.get("target")),
                                  item.before, item.after, item.why)
            c["proposal"] = p
        if p.action == "script":
            return fastpath.Subject("building", bid, dict(self.custom_specs.get(bid) or {}), script=p.after)
        if p.target.startswith("orc:"):
            b = self.scroll.building(bid)
            orc = b.garrison.handler(p.target[4:]) if b is not None else None
            data = {k: v for k, v in dataclasses.asdict(orc).items() if v is not None} if orc is not None else {"id": p.target[4:]}
            data.update({"kind": "chain", "chain": json.loads(p.after), "orders": ""} if p.action == "chain"
                        else {"orders": p.after})
            return fastpath.Subject("agent", bid, {"orc": data})
        spec = dict(self.custom_specs.get(bid) or {})
        key = "steward_prompt" if p.target == "steward" else "orders"
        spec["config"] = {**(spec.get("config") or {}), key: p.after}
        return fastpath.Subject("building", bid, spec)

    @staticmethod
    def council_lets(verdict: fastpath.Verdict) -> bool:
        """The Council lets the orcs apply a change themselves: no block, no objection, no Warder warning."""
        return not verdict.blocked and not verdict.objections and not verdict.of("warder")

    def _evolve_consider(self) -> None:
        if (self.demo or self._evolve_busy or not self.desktop.quiet or self._evolve_count >= evolution.MAX_PER_NIGHT
                or self.desktop.machine.autonomy < 2 or self.gold_exhausted_quietly()):
            return
        candidates = self._evolve_candidates()
        if not candidates:
            return
        c = candidates[0]
        self._evolve_tried.add(c["key"])
        try:
            subject = self._evolve_subject(c)
        except (KeyError, ValueError, TypeError, AttributeError):
            return
        self._evolve_busy = True
        self._evolve_work(c, subject)

    def gold_exhausted_quietly(self) -> bool:
        limit = self.scroll.budget.gold_session_limit_usd
        return limit > 0 and self.snapshot.spent_usd >= limit

    @work(thread=True, group="evolve")
    def _evolve_work(self, c: dict, subject: fastpath.Subject) -> None:
        runner = FASTPATH_RUNNER or fastpath.light_runner(self.repo_root)
        verdict = fastpath.review(subject, self.repo_root, self._taken_building_ids() - {subject.id}, runner=runner)
        self.call_from_thread(self._evolve_apply, c, verdict)

    def _evolve_apply(self, c: dict, verdict: fastpath.Verdict) -> None:
        """Applied by the orcs only while it is still quiet and the Council let it; else it stays a proposal."""
        self._evolve_busy = False
        if not self.desktop.quiet or not self.council_lets(verdict):
            return
        with self.hushed():
            if c["source"] == "steward":
                ok = self.apply_steward_proposal(c["building"], c["data"], c["index"], by="orcs") is not None
            elif c["source"] == "daily" or c["change"] in ("shrink", "chain", "script"):
                ok = self.apply_proposal(c["proposal"], kind="auto-improve" if c["source"] == "daily" else "weekly")
                if ok and c["source"] == "weekly":
                    c["report"].applied = sorted(set(c["report"].applied) | {c["item"].n})
                    weekly.save(self.repo_root, c["report"])
            else:
                ok = bool(self.apply_weekly(c["report"], [c["item"].n]))
        if ok:
            self._evolve_count += 1

    # -- probation: 24 hours for each change the orcs made ----------------------------------------

    def _probation_tick(self, now: dt.datetime | None = None) -> None:
        """Every few minutes: a change on probation with a 👎 or more failures since goes back by
        itself (the operator is told); one that lived through 24 hours is kept."""
        now = now or dt.datetime.now()
        if self.demo or (self._probation_at and time.monotonic() - self._probation_at < PROBATION_CHECK_S):
            return
        self._probation_at = time.monotonic()
        reverted = []
        for change in evolution.on_probation(self.repo_root):
            reason = evolution.verdict(self.repo_root, change, now)
            if reason is None:
                if now >= change.until:
                    change.status = "kept"
                    evolution.update(self.repo_root, change)
                continue
            if self.revert_change(change, f"probation: {reason}"):
                reverted.append(change)
        if reverted:
            names = ", ".join(f"{self._title_of(c.building)} ({c.change})" for c in reverted[:3])
            self.notify(f"{names} — {reverted[0].note}", title=f"↩ {len(reverted)} change(s) by the orcs taken back",
                        severity="warning", timeout=15)
            if not self.desktop.quiet:
                self.show_changes(only_unseen=True)

    def revert_change(self, change: evolution.Change, note: str, seen: bool = False) -> bool:
        """Take one change back — only when it is still its building's last checkpoint, so nothing
        newer is lost; otherwise it is marked stuck and the operator decides (Z on the building)."""
        last = checkpoint.history(self.repo_root, change.building, 1)
        if not change.sha or not last or last[0].sha != change.sha:
            change.status, change.note, change.seen = "stuck", f"{note} — changed since, Z on it decides", seen
            evolution.update(self.repo_root, change)
            return False
        with self.hushed():
            ok = self.revert_building(change.building)
        change.status, change.note, change.seen = ("reverted" if ok else "stuck"), note, seen
        evolution.update(self.repo_root, change)
        return ok

    def show_changes(self, only_unseen: bool = False) -> None:
        """🧾 The list of what the orcs changed: after quiet hours, after a probation revert, F10."""
        changes = evolution.unseen(self.repo_root) if only_unseen else \
            [c for c in evolution.load(self.repo_root) if c.by == "orcs"][-40:][::-1]
        if only_unseen and not changes:
            return
        titles = {c.building: self._title_of(c.building) for c in changes}

        def done(picked: str | None) -> None:
            evolution.mark_seen(self.repo_root)
            if picked:
                change = next((c for c in evolution.load(self.repo_root) if c.id == picked), None)
                if change is not None and change.status in ("probation", "kept", "stuck"):
                    if self.revert_change(change, "taken back by you", seen=True):
                        self.notify(f"{titles.get(change.building, change.building)}: {change.summary}",
                                    title="↩ Taken back")

        self.push_screen(ChangesModal(changes, titles), done)

    # -- 🏛 the Elders: in quiet hours they leave advice; the operator follows it (realm/elders.py) --

    @staticmethod
    def elders_mark(alert: Alert) -> tuple:
        return (alert.id, alert.title, tuple(alert.options), tuple(alert.context[-3:]))

    def advice_for(self, alert: Alert) -> elders.Decision | None:
        d = self.advice.get(self.elders_mark(alert))
        return d if d is not None and d.advised else None

    def _elders_consider(self) -> None:
        """One question at a time goes to the Elders: quiet hours, autonomy from 1, budget left."""
        if (self.demo or self._elders_busy or not self.desktop.quiet
                or not autonomy.advises(self.desktop.machine.autonomy) or self._elders_count >= elders.MAX_PER_NIGHT):
            return
        budget = self.scroll.budget.gold_session_limit_usd
        if budget > 0 and self.snapshot.spent_usd >= budget:
            return
        pending = [a for a in self.roster.alerts if elders.qualifies(a) and self.elders_mark(a) not in self._elders_seen]
        if not pending:
            return
        alert = pending[0]
        self._elders_seen.add(self.elders_mark(alert))
        self._elders_busy = True
        self._elders_count += 1
        self._elders_work(alert, self._alert_who_map().get(alert.id, ""))

    @work(thread=True, group="elders")
    def _elders_work(self, alert: Alert, who: str) -> None:
        runner = ELDERS_RUNNER or fastpath.light_runner(self.repo_root)
        decision = elders.judge(alert, runner)
        self.call_from_thread(self._elders_done, alert, who, decision)

    def _elders_done(self, alert: Alert, who: str, decision: elders.Decision) -> None:
        """The Elders' advice is kept for the operator. At ⛓️‍💥 Free orcs (autonomy.answers) they also
        answer: their key goes to the agent — only while it is still quiet and the very same question
        still waits, so an answer never lands on a question that changed meanwhile."""
        self._elders_busy = False
        mark = self.elders_mark(alert)
        sent = False
        if (decision.advised and autonomy.answers(self.desktop.machine.autonomy) and self.desktop.quiet
                and any(self.elders_mark(a) == mark for a in self.roster.alerts)):
            key = decision.key or ""
            self.chat.send(alert.ref, (key if key.isdigit() else f"{key}\r").encode())   # no focus: they sleep
            sent = True
        else:
            self.advice[mark] = decision
        elders.log(self.repo_root, alert, decision, who, sent=sent)
        self.refresh_roster()

    def _elders_morning(self) -> None:
        answered = [r for r in elders.since(self.repo_root, self._quiet_since or "") if r.get("sent")]
        waiting = [a for a in self.roster.alerts if self.advice_for(a) is not None]
        words = []
        if answered:
            words.append(f"{len(answered)} question(s) answered by the Elders — the Town Hall lists them")
        if waiting:
            words.append(f"{len(waiting)} have their advice — ! opens them, a follows it, A for all")
        if words:
            self.notify(".\n".join(words) + ".", title="🏛 While you were away, the Elders", timeout=15)

    def follow_advice(self, alert: Alert) -> bool:
        """The operator follows the Elders' advice on one question: their key, sent as their own answer."""
        d = self.advice_for(alert)
        if d is None or d.key is None:
            return False
        self.answer_alert(alert, d.key)
        return True

    def open_autonomy(self) -> None:
        """F10 → 🏛 Orc autonomy: the slider and the guide for the agents' own settings."""
        machine = self.desktop.machine
        tools_ = tuple(t for t, c in machine.tools.items() if c.enabled) or ("claude", "agy")

        def done(result: dict | str | None) -> None:
            if isinstance(result, dict):
                machine.autonomy = int(result.get("autonomy", machine.autonomy))
                settings.save(machine)
                lvl = autonomy.LEVELS[machine.autonomy]
                self.notify(f"❓ {lvl.questions}\n🔧 {lvl.improves}", title=f"{lvl.icon} {lvl.title}")

        self.push_screen(AutonomyStep(machine.autonomy, tools_, standalone=True), done)

    def open_day(self) -> None:
        """F10 → 🕰 Your day: the mode, the quiet hours and the office hours, on the day bar."""
        def done(result: dict | None) -> None:
            if result:
                self.apply_day(result)

        self.push_screen(onboarding.ModeStep(self.desktop.machine, standalone=True), done)

    def apply_day(self, result: dict) -> None:
        machine = self.desktop.machine
        machine.quiet, machine.office = result.get("quiet"), result.get("office") or machine.office
        machine.office_days = tuple(result.get("office_days", machine.office_days))
        settings.save(machine)
        self.desktop.set_mode(result.get("mode", machine.mode))
        self.desktop.apply_schedule()
        self.refresh_hud()

    def _order_burns(self) -> bool:
        order = town_presets.pending_order(self.repo_root)
        return order is not None and not order.get("seen")

    def start_onboarding(self, machine_steps: bool | None = None, town_step: bool = True) -> None:
        """Steps 1–2 once per machine (or when asked, F10), step 3 for a project with no town yet."""
        if machine_steps is None:
            machine_steps = not self.desktop.machine.onboarded
        onboarding.Onboarding(self, machine_steps, town_step, on_town=self.raise_town).start()

    def raise_town(self, choice: dict) -> None:
        """Step 4: raise the chosen town over the map, a progress bar along the bottom."""
        steps = onboarding.raising_steps(choice)
        bar = onboarding.mount_raise_bar(self.screen, len(steps))
        self._raise_town_work(choice, steps, bar)

    @work(thread=True, exclusive=True, group="raise-town")
    def _raise_town_work(self, choice: dict, steps: list[str], bar) -> None:
        problems: list[str] = []
        for i, label in enumerate(steps):
            self.call_from_thread(bar.step, label + "…", i)
            try:
                if label.startswith("Opening"):
                    checkpoint.ensure(self.repo_root)
                elif "Warder" in label:
                    from orkcraft.hooks import install as hooks_install
                    hooks_install.install(self.repo_root)
                elif label.startswith("Raising"):
                    self.call_from_thread(self._raise_buildings, choice)
                elif "order" in label:
                    town_presets.save_order(self.repo_root, choice.get("prompt", ""), choice.get("domain", ""))
            except (OSError, ValueError, RuntimeError) as e:
                problems.append(f"{label}: {e}")
            onboarding.pause()
        self.call_from_thread(self._town_raised, choice, steps, bar, problems)

    def _raise_buildings(self, choice: dict) -> None:
        """The preset's buildings and roads, placed one by one — none yet: every preset is a stub
        (town_presets.buildings_of is empty) and the town stays the Town Hall alone."""

    def _town_raised(self, choice: dict, steps: list[str], bar, problems: list[str]) -> None:
        bar.step("The town stands", len(steps))
        self.desktop.save()
        preset = town_presets.preset(choice.get("preset", ""))
        reason = f"onboarding: {preset.title}" if preset else f"onboarding: {choice.get('preset', 'empty')} town"
        checkpoint.commit(self.repo_root, "create", "camp", reason, self.config.layout_file)
        self.order_burning = self._order_burns()
        self.refresh_roster()
        self.set_timer(1.5, bar.remove)
        if problems:
            self.notify("\n".join(problems), title="🏗 Raising the town", severity="warning")
        self.notify("B build · P presets · ? all keys.", title="🏰 The town stands", timeout=10)
        if choice.get("preset") == onboarding.CUSTOM and town_presets.pending_order(self.repo_root) is not None:
            self.set_timer(1.6, self.build_town_from_order)       # after the bar has gone

    # -- 📜 the Town Builder: an order in words → a plan → approved → raised ----------------------

    def build_town_from_order(self, note: str = "") -> None:
        order = town_presets.pending_order(self.repo_root)
        if order is None:
            self.notify("no town order waits in the Town Hall", title="📜 Town Builder")
            return
        if self.query(onboarding.RaiseBar):
            return                                                # one town at a time
        bar = onboarding.mount_raise_bar(self.screen, None)
        bar.say("📜 The Town Builder is drawing your town…")
        self._plan_town_work(order["prompt"], note, bar)

    @work(thread=True, exclusive=True, group="town-builder")
    def _plan_town_work(self, order: str, note: str, bar) -> None:
        runner = BUILD_RUNNER or builders.claude_runner
        result = town_builder.plan(order, self.repo_root, self._taken_building_ids(), runner, feedback=note)
        self.call_from_thread(self._on_town_plan, order, result, bar)

    def _on_town_plan(self, order: str, result: town_builder.TownPlan, bar) -> None:
        bar.remove()
        self._log_build_request(f"town: {order}", result)
        if not result.ok:
            self.order_burning = self._order_burns()
            self.notify(f"{result.error or 'no plan'}\nThe order keeps waiting in the 🏰 Town Hall.",
                        title="📜 Town Builder", severity="error", timeout=12)
            return

        def done(answer: dict | None) -> None:
            if answer is None:
                town_presets.save_order(self.repo_root, order, (town_presets.pending_order(self.repo_root)
                                                                or {}).get("domain", ""))
                self.order_burning = True                         # later: it burns until the Hall is opened
                self.refresh_roster()
                self.notify("The order waits in the 🏰 Town Hall.", title="📜 Town Builder")
            elif answer.get("action") == "again":
                self.build_town_from_order(answer.get("note", ""))
            else:
                self.raise_town_plan(result)

        self.push_screen(TownPlanReview(order, result), done)

    def raise_town_plan(self, plan: town_builder.TownPlan) -> None:
        """Raise an approved plan: its buildings one by one, then its roads, with the bar along the bottom."""
        steps: list[tuple[str, Callable[[], Any]]] = []
        for spec in plan.specs:
            label = f"{spec.get('icon', '')} {spec.get('title', spec['id'])}".strip()
            steps.append((f"Raising {label}", functools.partial(self.raise_spec, spec, None, True)))
        for r in plan.roads:
            steps.append((f"Laying the road {r.source} → {r.target}",
                          functools.partial(self.add_road, r.target, r.source, r.event, None, True)))
        bar = onboarding.mount_raise_bar(self.screen, len(steps))

        def run(i: int) -> None:
            if i == len(steps):
                bar.step("The town stands", len(steps))
                town_presets.close_order(self.repo_root, plan.title)
                self.order_burning = False
                self.checkpoint("create", "camp", f"town: {plan.title or 'from an order'}")
                self.desktop.set_active(None)                 # the whole town on the map, nothing open
                self.set_focus_state("neutral")
                self.refresh_roster()
                self.desktop.refresh_huts()
                self.set_timer(1.5, bar.remove)
                self.notify(f"{len(plan.specs)} buildings · {len(plan.roads)} roads. B build · Y roads · ? all keys.",
                            title=f"🏰 {plan.title or 'The town'} stands", timeout=10)
                return
            label, act = steps[i]
            bar.step(label + "…", i)
            try:
                act()
            except Exception as e:      # one building that will not stand must not stop the rest
                self.notify(f"{label}: {e}", title="🏗 Raising the town", severity="warning")
            self.set_timer(onboarding.STEP_PAUSE_S or 0.01, lambda: run(i + 1))

        run(0)

    def on_desktop_hut_selected(self, message: Desktop.HutSelected) -> None:
        self.set_focus_state("building", building_id=message.building_id)
        if hasattr(self, "_console") and self._console is not None:
            self._console.focus_roster()     # keys must not land in a building that just closed

    def on_clan_roster_building_selected(self, message: ClanRoster.BuildingSelected) -> None:
        w = self.desktop.get_window(message.building_id)
        if w is not None:
            self.desktop.focus_window(w)
        self.set_focus_state("building", building_id=message.building_id)

    def on_clan_roster_orc_selected(self, message: ClanRoster.OrcSelected) -> None:
        orc = next((o for o in self.roster.orcs if orc_key(o) == message.key), None)
        if orc is None:
            return
        if (self.focus_state.mode == "building" and orc.alert is not None
                and orc.building == self.focus_state.building_id):
            # A question in the selected building: show it, keep the building selected, drop its ❓.
            self.seen_alerts.add(orc.alert.id)
            self.open_alert(orc.alert, orc.name)
            if getattr(self, "_console", None) is not None:
                self._console.refresh_state(self.focus_state, self.roster)
            return
        self.set_focus_state("unit", orc_key_val=message.key, building_id=orc.building)
        if orc.alert is not None:
            self.open_alert(orc.alert, orc.name)

    def on_hud_menu_clicked(self, message: Hud.MenuClicked) -> None:
        self.action_system_menu()

    def on_hud_alerts_clicked(self, message: Hud.AlertsClicked) -> None:
        self.action_awaiting_orders()

    def wear_mode(self) -> None:
        """The mode changed (immersion ↔ hidden): everything outside the town follows it."""
        self._hud.update_hud()
        self._taskbar.refresh_items()
        self.refresh_bindings()                  # the footer recomposes in the mode's words
        for widget in self.query(OfficeStatic):
            widget.rewear()
        if getattr(self, "_console", None) is not None:
            self._console.refresh_state(self.focus_state, self.roster)

    def notify(self, message, *, title: str = "", **kwargs) -> None:  # type: ignore[override]
        if modes.hidden():                       # the office: no emoji in the toasts either
            message = modes.strip_rich(message) if not isinstance(message, str) else modes.strip_emoji(message)
            title = modes.strip_emoji(title)
        super().notify(message, title=title, **kwargs)

    def action_system_menu(self) -> None:
        if isinstance(self.screen, SystemMenu):
            self.screen.dismiss(None)
            return

        def done(action: str | None) -> None:
            if not action:
                return
            if action == "halt":
                self.action_halt()
            elif action == "screenshot":
                self.call_after_refresh(self._save_screenshot)
            elif action == "keys":
                self.push_screen(KeysCheatSheet())
            elif action in settings.MODES:
                self.desktop.set_mode(action)
                self.refresh_hud()
                self.notify({"camp": "the town of orcs, fire and gold", "office": "hidden — frames, people and plain words",
                             "shift": "Office in office hours, Camp otherwise — F10 → 🕰 Your day"}[action],
                            title=settings.MODE_TITLES[action])
            elif action == "day":
                self.open_day()
            elif action == "autonomy":
                self.open_autonomy()
            elif action == "changes":
                self.show_changes()
            elif action == "terrain":
                self.action_toggle_terrain()
            elif action == "save":
                if self.desktop.save():
                    self.notify("💾 Town Scroll saved", title="Town Scroll")
                else:
                    self.notify("Town Scroll not saved", title="Town Scroll", severity="warning")
            elif action == "audit":
                self.run_audit()
            elif action == "cleanup":
                self.cleanup()
            elif action == "settings":
                self.open_settings()
            elif action == "improve":
                self.open_proposals()
            elif action == "weekly":
                self.open_weekly()
            elif action == "town_order":
                self.build_town_from_order()
            elif action == "onboarding":
                self.start_onboarding(machine_steps=True, town_step=False)
            elif action == "quit":
                self.action_graceful_quit()

        self.push_screen(SystemMenu(self.desktop.mode), done)

    def _save_screenshot(self) -> None:
        now_str = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
        filename = f"orkcraft-{now_str}.svg"
        screenshot_dir = self.repo_root / "loot" / "screenshots"
        try:
            screenshot_dir.mkdir(parents=True, exist_ok=True)
            self.save_screenshot(filename=filename, path=str(screenshot_dir))
            self.notify(f"📸 loot/screenshots/{filename}", title="Screenshot")
        except OSError as e:
            self.notify(f"Screenshot failed: {e}", title="Screenshot", severity="error")

    # -- command card actions ----------------------------------------------------------------

    def action_command_card(self, key: str) -> None:
        mode = self.focus_state.mode
        if mode == "neutral":
            if key == "B":
                self.action_build_menu()
            elif key == "P":
                self.action_presets_catalog()
            elif key == "S":
                self.action_spawn_orc()
            elif key == "T":
                self.action_toggle_terrain()
            elif key == "G":
                self.action_worktree()
        elif mode == "building":
            b_id = self.focus_state.building_id
            w = self.desktop.get_window(b_id) if b_id else self.desktop.active
            if key == "R":
                spec = self.scroll.building(b_id) if b_id else None
                b_title = spec.title if spec else "Building"

                def done(orc: OrcSpec | str | None) -> None:
                    if isinstance(orc, str):
                        self.recruit_from_prompt(b_id, orc)
                        return
                    if orc is not None:
                        self.desktop.save()
                        self.refresh_roster()
                        try:
                            chronicles.record(self.repo_root, self.scroll, b_id, "orc_recruited", orc=orc.name)
                        except OSError:
                            pass
                        self.notify(f"🧌 {orc.name} joined the {b_title} garrison", title="Garrison")

                self.push_screen(GarrisonModal(b_title, b_id), done)
            elif key == "L":
                b_id = self.focus_state.building_id or (self.desktop.active.window_id if self.desktop.active else "forge")
                self.push_screen(BuildingChronicles(self.repo_root, self.scroll, b_id))
            elif key == "Y":
                target_id = b_id or (self.desktop.active.window_id if self.desktop.active else None)
                if target_id:
                    sources = {w.window_id for w in self.desktop.windows
                               if self.desktop.in_view(w) and not w.hidden
                               and (self._road_choices(w.window_id, target_id) or self._rule_choices(w.window_id, target_id))}
                    self.desktop.enter_rally_mode(target_id, candidates=sources)
                    # The taskbar status is squeezed out by the window tabs on common widths.
                    tgt = self.scroll.building(target_id)
                    self.notify("click the source building (or press its number) · any other key cancels",
                                title=f"🛤 Road into {tgt.title if tgt else target_id}")
            elif key == "U":
                target_id = b_id or (self.desktop.active.window_id if self.desktop.active else None)
                spec = self.scroll.building(target_id) if target_id else None
                if spec is not None:
                    if not spec.roads:
                        self.notify("no incoming roads", title="Roads")
                    elif len(spec.roads) > 1:
                        self.notify("select a road first — click it or its gate", title="Roads")
                    else:
                        self.remove_road(road_key(spec.id, spec.roads[0].id))
            elif key == "P":
                if w is not None:
                    self.desktop.toggle_pin(w)
                    self.notify(f"📌 {w.window_title} {'pinned' if w.pinned else 'unpinned'}", title="Windows")
            elif key == "M":
                if w is not None:
                    self.desktop.focus_window(w)
                self.desktop.enter_window_mode()
            elif key == "X":
                if w is not None:
                    self.desktop.hide(w)
                    self.desktop.save()
                self.set_focus_state("neutral")
                self.desktop.set_active(None)
                if hasattr(self, "_console") and self._console is not None:
                    self._console.focus_roster()
            elif key == "Z":
                if b_id:
                    self.revert_building(b_id)
            elif key == "K":
                if b_id:
                    self.like_building(b_id)
            elif key == "F":
                if b_id:
                    self.dislike_building(b_id)
            elif b_id and any(a.get("key") == key for a in self.custom_specs.get(b_id, {}).get("actions", [])):
                self.action_custom_action(key)
        elif mode == "road":
            road = self.focus_state.road_key
            if road and key == "U":
                self.remove_road(road)
            elif road and key == "H":
                self.change_road_handler(road)
        elif mode == "unit":
            if key == "W":
                orc = next((o for o in self.roster.orcs if orc_key(o) == self.focus_state.orc_key), None)
                if orc is not None and orc.category == RESIDENT and orc.lead and orc.building:
                    self.watch_building(orc.building, interactive=True)
                else:
                    self.notify("W is the steward's: select a building's ★ orc", title="Steward")
                return
            orc_k = self.focus_state.orc_key
            orc = next((o for o in self.roster.orcs if orc_key(o) == orc_k), None) if orc_k else None
            if orc is None:
                return
            if orc.category == RESIDENT:
                b_id, orc_id = orc.ref.split("/", 1) if "/" in orc.ref else (orc.building or "", "")
                b_spec = self.scroll.building(b_id) if b_id else None
                m_spec = next((m for m in b_spec.garrison.members if m.id == orc_id), None) if b_spec else None
                b_title = b_spec.title if b_spec else (orc.building or "Building")
                w = self.desktop.get_window(b_id) if b_id else None

                if key == "C":
                    self.deploy_resident(orc)
                elif key == "T":
                    if w is not None and m_spec is not None:
                        self.open_unit(w, member=m_spec)
                    else:
                        self.notify(f"{orc.name}: no window or spec found", title="⚡ Triggers")
                elif key == "D":
                    term = self.chat.terminals.get(orc.session) if orc.session else None
                    if term is not None and term.running:
                        self.notify("halt it first", title="Dismiss", severity="warning")
                        return
                    try:
                        scroll.dismiss_orc(self.scroll, b_id, orc_id)
                    except ValueError as e:
                        self.notify(str(e), title="Dismiss", severity="warning")
                        return
                    self.desktop.save()
                    self.set_focus_state("building", building_id=b_id)
                    self.refresh_roster()
                    try:
                        chronicles.record(self.repo_root, self.scroll, b_id, "orc_dismissed", orc=orc.name)
                    except OSError:
                        pass
                elif key == "H":
                    term = self.chat.terminals.get(orc.session) if orc.session else None
                    if term is not None and term.running:
                        term.interrupt()
                        try:
                            chronicles.record(self.repo_root, self.scroll, b_id, "orc_halted", orc=orc.name)
                        except OSError:
                            pass
                        self.notify(f"🛑 Halted {orc.name}", title="Halt")
                    else:
                        self.notify("nothing to halt", title="Halt")
                elif key == "L":
                    self.push_screen(UnitChronicles(orc, self.repo_root))
            else:
                w = self.desktop.get_window(orc.building) if orc.building else None
                if key == "C":
                    if orc.category == WORKER:
                        chat_win = self._sessions_window()
                        if chat_win:
                            self.desktop.focus_window(chat_win)
                        self.chat.show_terminal(orc.ref)
                    else:
                        self.notify(f"{orc.name}: no terminal or window", title="🧌 Unit")
                elif key == "L":
                    self.push_screen(UnitChronicles(orc, self.repo_root))
                elif key == "T":
                    self.notify(f"{orc.name}: triggers only for residents", title="⚡ Triggers")
                elif key == "H":
                    if orc.category == WORKER and orc.ref in getattr(self.chat, "terminals", {}):
                        self.chat.terminals[orc.ref].interrupt()
                        if orc.building:
                            try:
                                chronicles.record(self.repo_root, self.scroll, orc.building, "orc_halted", orc=orc.name)
                            except OSError:
                                pass
                        self.notify(f"🛑 Halted {orc.name}", title="Halt")
                    else:
                        self.notify("nothing to halt", title="Halt")
                elif key == "D":
                    self.notify("Dismiss is only for garrison members", title="Dismiss")

    def action_custom_action(self, key: str) -> None:
        if self.focus_state.mode != "building" or not self.focus_state.building_id:
            return
        spec = self.custom_specs.get(self.focus_state.building_id)
        if not spec:
            return
        action_item = next((a for a in spec.get("actions", []) if a.get("key") == key), None)
        if not action_item:
            return
        action_type = action_item.get("action")

        w = self.desktop.get_window(self.focus_state.building_id)
        custom_view = None
        if w is not None:
            try:
                custom_view = w.query_one(CustomBuildingView)
            except Exception:
                custom_view = None

        node_id = custom_view.get_selected_node() if custom_view else None

        if action_type == "node:open":
            self.notify("node detail view is not available")
        elif action_type == "node:chat":
            if not node_id:
                self.notify("select a node first")
                return
            self.open_chat(node_id)
        elif action_type == "node:preview":
            self.notify("preview view is not available")
        elif action_type == "building:refresh":
            if custom_view:
                custom_view.refresh_data()
            self.notify("Building data reloaded", title="Refresh")

    def action_presets_catalog(self) -> None:
        numbers = {w.window_id: w.number for w in self.desktop.windows if self.desktop.in_view(w)}

        def done(building_id: str | None) -> None:
            if not building_id:
                return
            if building_id.startswith("type:"):
                self.preset_params(building_id[5:])
                return
            active_id = self.scroll.active_orkspace_id
            spec = self.scroll.building(building_id)
            cur_ork = self.scroll.orkspace_of(building_id)
            raised = cur_ork is None or (spec is not None and spec.demolished)
            moved = (not raised) and (cur_ork is not None and cur_ork.id != active_id)

            if raised or moved:
                scroll.move_building(self.scroll, building_id, active_id)
                self.desktop.apply_orkspace(active_id)
                self.desktop.save()
                active_ork = self.scroll.orkspace(active_id)
                ork_name = active_ork.name if active_ork else active_id
                try:
                    ev_type = "building_raised" if raised else "building_moved"
                    chronicles.record(self.repo_root, self.scroll, building_id, ev_type, orkspace=ork_name)
                except OSError:
                    pass

            w = self.desktop.get_window(building_id)
            if w is not None:
                self.desktop.focus_window(w)
                self.set_focus_state("building", building_id=building_id)

        self.push_screen(PresetsModal(self.buildings, self.scroll, numbers), done)

    # -- orkspaces ---------------------------------------------------------------------------

    def action_orkspace(self, hotkey: str) -> None:
        ork = scroll.orkspace_by_hotkey(self.scroll, hotkey)
        if ork is None:
            self.notify(f"No orkspace on {hotkey} — N creates one", title="Orkspaces")
            return
        self.desktop.switch_orkspace(ork.id)

    def action_new_orkspace(self) -> None:
        def done(orkspace_id: str | None) -> None:
            if orkspace_id:
                self.desktop.switch_orkspace(orkspace_id)
                self.set_focus_state("neutral")
        self.push_screen(OrkspaceModal(self.scroll), done)

    def on_desktop_orkspace_changed(self, message: Desktop.OrkspaceChanged) -> None:
        self.set_focus_state("neutral")
        self.desktop.set_active(None)
        self.refresh_roster()
        self.refresh_rally_indicators()
        try:
            self._taskbar.refresh_items()
        except Exception:
            pass
        if hasattr(self, "_console") and self._console is not None:
            self._console.refresh_state(self.focus_state, self.roster)
            visible = [w for w in self.desktop.windows if self.desktop.in_view(w) and not w.hidden]
            if not visible:
                self._console.focus_roster()
        self.questions_on_arrival(message.orkspace_id)

    def _note_alerts(self) -> None:
        """Remember when each question first came up (the oldest opens first); forget the answered ones."""
        now = time.monotonic()
        live = {a.id for a in self.roster.alerts} | {o.alert.id for o in self.roster.orcs if o.alert is not None}
        for aid in live:
            self.alert_first_seen.setdefault(aid, now)
        for aid in set(self.alert_first_seen) - live:
            del self.alert_first_seen[aid]

    def questions_of(self, orkspace_id: str) -> list[Orc]:
        """The orcs of an orkspace's buildings that wait for an answer, the longest waiting first."""
        self._note_alerts()
        asking = [o for o in self.roster.orcs if o.alert is not None and o.building
                  and (ork := self.scroll.orkspace_of(o.building)) is not None and ork.id == orkspace_id]
        return sorted(asking, key=lambda o: self.alert_first_seen.get(o.alert.id, float("inf")))   # stable

    def questions_on_arrival(self, orkspace_id: str) -> None:
        """Arriving on an orkspace with questions: the first one opens at once, its building and its orc
        selected behind it (the others wait in the same dialog, ↑↓)."""
        if len(self.screen_stack) > 1:                 # the operator is busy in a dialog
            return
        asking = self.questions_of(orkspace_id)
        if not asking:
            return
        first = asking[0]
        self.desktop.select_hut(first.building)
        self.set_focus_state("unit", orc_key_val=orc_key(first), building_id=first.building)
        self.seen_alerts.update(o.alert.id for o in asking if o.alert is not None)
        self.push_screen(AwaitingOrdersModal([o.alert for o in asking if o.alert is not None],
                                             {o.alert.id: o.name for o in asking if o.alert is not None}))

    # -- windows -----------------------------------------------------------------------------

    def action_focus_number(self, number: int) -> None:
        if getattr(self.desktop, "rally_mode", False):
            self.rally_pick_number(number)
            return
        # The key of the building already in focus opens its resident orc's orders.
        w = next((x for x in self.desktop.windows if x.number == number and self.desktop.in_view(x)), None)
        selected = self.focus_state.mode != "neutral" and self.focus_state.building_id == getattr(w, "window_id", None)
        if w is not None and w is self.desktop.active and not w.hidden and selected:
            self.open_unit(w)
            return
        self.desktop.action_focus_number(number)
        if w is not None:
            self.set_focus_state("building", building_id=w.window_id)

    def action_cycle_window(self, step: int) -> None:
        self.desktop.cycle(step)

    def action_window_mode(self) -> None:
        self.desktop.enter_window_mode()

    def action_move_active(self, dx: int, dy: int) -> None:
        if self.desktop.active is not None:
            self.desktop.move_by(self.desktop.active, dx, dy)

    def action_resize_active(self, dw: int, dh: int) -> None:
        if self.desktop.active is not None:
            self.desktop.resize_by(self.desktop.active, dw, dh)

    def action_toggle_pin(self) -> None:
        w = self.desktop.active
        if w is not None:
            self.desktop.toggle_pin(w)
            self.notify(f"📌 {w.window_title} {'pinned' if w.pinned else 'unpinned'}", title="Windows")

    def action_toggle_terrain(self) -> None:
        self.desktop.toggle_terrain()

    def layout_console(self) -> None:
        """Town view: the console floats over the map's bottom edge. Calm (nothing
        selected) → the War Map alone, bottom left, and the Build button bottom right; a
        selection → the full console. The huts are laid out above the calm strip, which never
        changes with the selection, so the town does not move; the open building shrinks to stay
        clear of the full console. Tiles: the docked console of old."""
        console = getattr(self, "_console", None)
        if console is None or not console.is_attached:
            return
        desk = self.desktop
        town = desk.town_active
        width, height = self.size
        calm = self.focus_state.mode == "neutral"
        shown = bool(console.display)
        strip = len(self.scroll.orkspaces) + 3                     # border, title, one row each, footer
        full = max(strip, 6, round(console.height_pct * max(height - 2, 1) / 100))
        if self.focus_state.mode in ("building", "unit"):
            full = max(full, BUILDING_CONSOLE_MIN_H)    # Info's name, about, runs and roads all show
        orc = next((o for o in self.roster.orcs if orc_key(o) == self.focus_state.orc_key), None) \
            if self.focus_state.mode == "unit" else None
        chat = shown and OrcChat.supports(orc)
        chat_w = max(56, round(width * 0.32)) if chat else 0
        sig = (town, calm, shown, width, height, strip, full, chat, self.focus_state.orc_key)
        if sig == self._console_signature:
            return
        self._console_signature = sig
        self._orc_chat.display = chat
        if chat:
            chat_h = max(full, round(ORC_CHAT_PCT * max(height - 2, 1) / 100))
            self._orc_chat.styles.width, self._orc_chat.styles.height = chat_w, chat_h
            self._orc_chat.styles.offset = (max(width - chat_w, 0), max(height - 1 - chat_h, 0))
            self._orc_chat.show_orc(self.focus_state.orc_key)
        console.set_class(town, "-floating")
        console.set_class(town and calm, "-calm")
        self._taskbar.display = not town
        if not town:
            console.styles.offset = (0, 0)
            console.styles.width = max(width - chat_w, WARMAP_FLOAT_W + 22 + 20) if chat else "100%"
            console.styles.height = f"{console.height_pct}%"
            desk.set_reserves(0, 0, 0)
            return
        # A selected orc's chat stands at the right edge: the console ends where the chat begins.
        h, w = (strip, WARMAP_FLOAT_W) if calm else (full, max(width - chat_w, WARMAP_FLOAT_W + 22 + 20))
        console.styles.width, console.styles.height = w, h
        console.styles.offset = (0, max(height - 1 - h, 0))
        bottom = strip if shown else 0
        desk.set_reserves(bottom, (bottom if calm else full) if shown else 0, chat_w)

    def deploy_resident(self, orc, first_message: str = "", show_tent: bool = True) -> str | None:
        """C on a garrison orc (and the orc's chat line): its running session, else a new Claude
        session with its orders — and, from the chat, the operator's first message."""
        b_id, orc_id = orc.ref.split("/", 1) if "/" in orc.ref else (orc.building or "", "")
        b_spec = self.scroll.building(b_id) if b_id else None
        m_spec = next((m for m in b_spec.garrison.members if m.id == orc_id), None) if b_spec else None
        b_title = b_spec.title if b_spec else (orc.building or "Building")
        term = self.chat.terminals.get(orc.session) if orc.session else None
        if term is not None and term.running:
            if first_message:
                term.write((first_message + "\r").encode())
            if show_tent:
                chat_win = self._sessions_window()
                if chat_win:
                    self.desktop.focus_window(chat_win)
                self.chat.show_terminal(orc.session)
            return orc.session
        if self.roster.active >= self.scroll.budget.supply_max_workers:
            self.notify(
                f"🥩 Supply {self.roster.active}/{self.scroll.budget.supply_max_workers}: build more farms first "
                "(stop a session with x in the War Tent)", title="Not enough food", severity="warning"
            )
            return None
        if self.gold_exhausted():
            return None
        orders_text = m_spec.orders if m_spec else orc.task
        prompt = f"You are {orc.name}, {orc.role}, a garrison orc of the {b_title} building in orkcraft."
        if orders_text:
            prompt += f" Orders: {orders_text}"
        if first_message:
            prompt += f"\n\nThe operator says: {first_message}"
        command = deploy_command("claude", prompt)
        if command is None:
            self.notify("agy deployment is not supported yet — open an agy session in the War Tent", title="Deploy",
                        severity="warning")
            return None
        chat_key = self.chat.deploy(f"deploy:{b_id}/{orc_id}", command, "claude", f"{orc.name} · {b_title}",
                                    env={"ORKCRAFT_ORC": f"{b_id}/{orc_id}"})
        self.deployments[chat_key] = f"{b_id}/{orc_id}"
        try:
            chronicles.record(self.repo_root, self.scroll, b_id, "orc_deployed", orc=orc.name, harness="claude")
        except OSError:
            pass
        if show_tent:
            chat_win = self._sessions_window()
            if chat_win:
                self.desktop.focus_window(chat_win)
        self.refresh_roster()
        return chat_key

    def resume_for_orc(self, orc, session) -> None:
        """An earlier session of the orc, reopened in the War Tent and bound to the orc again."""
        self.chat.open_session(session)
        if session.key in self.chat.terminals and orc.ref:
            self.deployments[session.key] = orc.ref
        self.refresh_roster()

    def action_focus_orc_chat(self) -> None:
        if self._orc_chat.display:
            self._orc_chat.query_one("#orc-chat-input").focus()

    def _tick_orc_chat(self) -> None:
        if getattr(self, "_orc_chat", None) is not None and self._orc_chat.display:
            self._orc_chat.refresh_chat()

    # -- quick actions -------------------------------------------------------------------

    def spec_of(self, building_id: str | None) -> dict | None:
        """A building's spec: a custom one's file, or the catalog type a built-in wears."""
        if not building_id:
            return None
        return self.custom_specs.get(building_id) or BUILTIN_SPECS.get(building_id)

    def action_quick_action(self, index: int) -> None:
        """`[` / `]`: the selected building's first / second quick action."""
        b_id = self.focus_state.building_id if self.focus_state.mode == "building" else None
        actions = catalog.quick_actions_of(self.spec_of(b_id)) if b_id else []
        if index < len(actions):
            self.run_quick_action(b_id, actions[index].id)

    def run_quick_action(self, building_id: str, action_id: str) -> None:
        """A hut button or `[` / `]`. Each type's view brings its own handler (`quick_action`);
        until it lands the operator is told so, never left with a silent button."""
        spec = self.spec_of(building_id)
        t = catalog.type_of(spec)
        act = t.action(action_id)
        if act is None:
            return
        w = self.desktop.get_window(building_id)
        view = next(iter(w.children), None) if w is not None else None
        handler = getattr(view, "quick_action", None)
        if handler is not None and handler(action_id):
            return
        self.notify(f"{act.glyph} {act.label}: arrives with the {t.title} view", title=f"{t.icon} {spec.get('title', building_id) if spec else building_id}")

    def _sessions_window(self) -> Window | None:
        """The live sessions (the War Tent of old) live in the Town Hall's Sessions tab."""
        w = self.desktop.get_window(TOWN_HALL)
        view = next(iter(w.query(TownHallView)), None) if w is not None else None
        if view is not None:
            view.show_tab("sessions")
        return w

    def run_audit(self) -> None:
        """🔍 Audit: the hall's three agents look over the town (rules, no model call)."""
        report = audit.run(self.repo_root, self.scroll, dict(self.custom_specs), self.snapshot.spent_usd,
                           self.scroll.budget.gold_session_limit_usd)
        try:
            audit.save(self.repo_root, report)
        except OSError:
            pass
        w = self.desktop.get_window(TOWN_HALL)
        view = next(iter(w.query(TownHallView)), None) if w is not None else None
        if view is not None:
            view.refresh_hall(report)
            view.show_tab("hall")
        if scroll.has_outgoing(self.scroll, TOWN_HALL, "hall.audit_done"):
            self.roads.emit(pipes.Payload(pipes.TEXT, report.markdown(), TOWN_HALL, "hall.audit_done", "Audit"))
        serious = sum(f.severity != "info" for f in report.findings)
        self.notify(f"{report.summary()}" + (f" — {serious} to look at" if serious else ""), title="🔍 Audit")

    def action_build_menu(self) -> None:
        """One way to build: raise a preset (built-in or saved) or describe a new one."""
        def done(choice: str | None) -> None:
            if choice == "preset":
                self.action_presets_catalog()
            elif choice == "scratch":
                self.action_build_scratch()
            elif choice == "new":
                self.action_build_wizard()

        self.push_screen(_PickModal("🏗 Build", [
            ("preset", "📜 From presets — pick what you need, name it, place it"),
            ("scratch", "🛠 From scratch — the Builder asks, writes a script, tests it in a sandbox"),
            ("new", "✨ A camp building the Foreman prefills from a description"),
        ], "Enter picks · Esc cancels"), done)

    def on_desktop_layout_changed(self, message: Desktop.LayoutChanged | None) -> None:
        self.layout_console()
        try:
            self._taskbar.refresh_items()
            self.refresh_rally_indicators()
            if hasattr(self, "_console") and self._console is not None:
                self._console.refresh_state(self.focus_state, self.roster)
        except Exception:
            pass

    def _windows_alive(self) -> bool:
        """False while the app shuts down: selection events can still arrive after the War Tent
        and the Scrying Spire are unmounted (a board refresh finishing during exit)."""
        return self._desktop.is_attached and bool(self._desktop.query("#chat-view"))

    def on_desktop_node_highlighted(self, message: Desktop.NodeHighlighted) -> None:
        if not self._windows_alive():
            return
        self.selected_node = message.node_id
        self.chat.set_node(message.node_id)


    def on_window_badge_clicked(self, message: Window.BadgeClicked) -> None:
        self.open_unit(message.window)

    def on_desktop_payload_emitted(self, message: Desktop.PayloadEmitted) -> None:
        if not self._windows_alive():
            return
        payload = message.payload
        if self.scroll is None:
            return
        self.roads.emit(payload)

    def _show_demo_samples(self) -> None:
        from orkcraft.demo import SAMPLES
        try:
            data = json.loads((self.repo_root / SAMPLES).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        for bid, sample in data.items():
            view = self._custom_view(bid)
            if view is not None:
                view.show_incoming(sample.get("title", ""), sample.get("markdown", ""))

    def _custom_view(self, building_id: str):
        w = self.desktop.get_window(building_id)
        if w is None:
            return None
        try:
            return w.query_one(CustomBuildingView)
        except Exception:
            return None

    def _payload_markdown(self, payload: pipes.Payload) -> tuple[str, str]:
        """(title, markdown) of what a road carries, for a custom building's 📥 pane."""
        if payload.kind == pipes.FILE:
            return pipes.read_file_payload(self.repo_root, payload.value)
        return payload.title or "report", payload.value

    def on_paste(self, event: events.Paste) -> None:
        """A file dragged onto the terminal while a Drop Zone is selected is a drop."""
        bid = self.focus_state.building_id if self.focus_state.mode == "building" else None
        drop = getattr(self._custom_view(bid), "drop", None) if bid else None
        if drop is not None:
            event.stop()
            drop(event.text)

    def emit_typed(self, building_id: str, event_id: str, value: str, title: str = "") -> bool:
        """A typed building sends one of its events: only when a road carries it."""
        spec = self.custom_specs.get(building_id)
        ev = catalog.type_of(spec).event(event_id) if spec else None
        if ev is not None:
            feedback.record_output(self.repo_root, building_id, event_id, value)      # what 👍 / 👎 rate
        if ev is None or self.scroll is None or not scroll.has_outgoing(self.scroll, building_id, event_id):
            return False
        self.roads.emit(pipes.Payload(ev.kind, value, building_id, event_id, title))
        return True

    def deliver_payload(self, target_id: str, payload: pipes.Payload, title: str = "", markdown: str = "") -> None:
        feedback.record_delivery(self.repo_root, target_id, payload.source)            # the session's graph
        view = self._custom_view(target_id)
        if view is not None:
            t, md = (title, markdown) if markdown else self._payload_markdown(payload)
            src = self.scroll.building(payload.source) if self.scroll is not None else None
            view.show_incoming(f"{src.title if src else payload.source} → {t}", md)
            receive = getattr(view, "receive", None)
            if receive is not None:
                receive(payload, t, md)
        if target_id == "loot":
            if payload.kind == pipes.TEXT:
                t = title or payload.title
                md = markdown or payload.value
                path = pipes.write_loot(self.repo_root, payload.source, t, md)
                loot_win = self.desktop.get_window("loot")
                if loot_win is not None:
                    try:
                        from orkcraft.screens.loot_view import LootView
                        loot_view = loot_win.query_one(LootView)
                        loot_view.refresh_view()
                    except Exception:
                        pass
                self.notify(f"📦 report saved: loot/pipes/{path.name}", title="Loot")
        try:
            src_spec = self.scroll.building(payload.source) if self.scroll is not None else None
            src_title = src_spec.title if src_spec and src_spec.title else payload.source
            chronicles.record(self.repo_root, self.scroll, target_id, "payload_received",
                              kind=payload.kind, source=src_title)
        except OSError:
            pass

    def on_terminal_exited(self, event: Terminal.Exited) -> None:
        term = event.terminal
        chat = getattr(self, "chat", None)
        terminals = getattr(chat, "terminals", {}) if chat else {}
        term_key = next((k for k, t in terminals.items() if t is term), None)
        if not term_key or term_key not in self.deployments:
            return
        deployment_ref = self.deployments[term_key]
        if "/" not in deployment_ref:
            return
        b_id, orc_id = deployment_ref.split("/", 1)
        b_spec = self.scroll.building(b_id) if self.scroll is not None else None
        m_spec = next((m for m in b_spec.garrison.members if m.id == orc_id), None) if b_spec else None
        orc_name = m_spec.name if m_spec else orc_id
        try:
            chronicles.record(self.repo_root, self.scroll, b_id, "orc_returned", orc=orc_name, by=orc_name)
        except OSError:
            pass
        if b_spec is None or not self.roads.has_roads(b_id, pipes.ON_TASK):
            return
        title, md = pipes.task_report(orc_name, b_spec.title, term.text_lines())
        payload = pipes.Payload(kind=pipes.TEXT, value=md, source=b_id, mode=pipes.ON_TASK, title=title)
        self.roads.emit(payload)

    # -- roads ------------------------------------------------------------------------------------

    def _call_on_ui(self, fn, *args) -> None:
        """Road engine callbacks come from agent threads too; Textual widgets live on the UI thread."""
        if threading.current_thread() is threading.main_thread() or not self.is_running:
            fn(*args)
            return
        try:
            self.call_from_thread(fn, *args)
        except RuntimeError:
            pass  # the app is shutting down

    def payload_meta(self, payload: pipes.Payload) -> dict:
        """Type / status / subtype of the Markdown item a payload names (the source filter and the
        personal guard). Only the showcase sandbox indexes items; elsewhere the dict is empty and road
        filters on node_type / node_status do not match."""
        if self.graph is None:
            return {}
        ident = payload.value if payload.kind == pipes.NODE else ""
        if payload.kind == pipes.FILE and payload.value.endswith(".md"):
            ident = Path(payload.value).stem
        entity = self.graph.get_entity(ident) if ident else None
        if entity is None:
            return {}
        return {"type": entity.type, "status": entity.status, "title": entity.title,
                "subtype": "personal" if entity.is_personal else entity.subtype}

    def deliver_handler_output(self, target_id: str, orc: scroll.OrcSpec, title: str, markdown: str) -> None:
        """A handler's result: shown by a receiver that renders text, otherwise kept as a Loot report."""
        if not self._windows_alive():
            return
        payload = pipes.Payload(kind=pipes.TEXT, value=markdown, source=target_id, mode="handler", title=title)
        view = self._custom_view(target_id)
        if view is not None:
            view.show_incoming(title, markdown)
        else:
            path = pipes.write_loot(self.repo_root, target_id, title, markdown)
            self.notify(f"📦 {title}: loot/pipes/{path.name}", title="Handler")

    def on_road_cart(self, cart: roads.Cart) -> None:
        if self._windows_alive():
            self.desktop.traffic.launch(cart)

    def on_cart_clicked(self, message: CartClicked) -> None:
        cart = message.cart
        payload = getattr(cart, "payload", None)
        what = "a failed run" if payload is None else (
            f"{payload.kind} {payload.title or payload.value[:80]}".strip())
        detail = f" — {cart.detail}" if getattr(cart, "detail", "") else ""
        self.notify(f"🛒 {cart.status}: {what}{detail}", title=f"Cart · {cart.source} → {cart.target}")

    def action_toggle_view(self) -> None:
        """alt+v: the town (huts, one building open) ↔ tiles (every window side by side)."""
        town = not self.desktop.town
        self.desktop.set_town(town)
        if town:
            self.desktop.refresh_huts()
        self.notify("🏘 Town: click a hut or press its number to open it, esc closes it" if town
                    else "🪟 Tiles: every building open side by side", title="View")

    def action_cycle_carts(self) -> None:
        order = list(scroll.CART_MODES)
        cur = self.scroll.preferences.get("carts", "selected")
        nxt = order[(order.index(cur) + 1) % len(order)] if cur in order else "selected"
        self.scroll.preferences["carts"] = nxt
        if nxt == "off":
            self.desktop.traffic.clear()
        self.desktop.save()
        label = {"off": "off", "selected": "the selected building's roads", "all": "all roads"}[nxt]
        self.notify(f"🛒 carts: {label}", title="Roads")

    def on_handler_run(self, run: roads.HandlerRun) -> None:
        if run.outcome in ("done", "error"):         # every run of the camp, for the Tally Crag
            try:
                metrics.record_run(self.repo_root, run.target, run.outcome, run.cost_usd, run.tokens)
            except OSError:
                pass
        if self._windows_alive():
            if run.outcome == "error":
                self.desktop.traffic.mark_error(run.target, list(run.roads))
            if run.cost_usd:
                self.desktop.traffic.flash_coin(run.target)
        b_spec = self.scroll.building(run.target) if self.scroll is not None else None
        orc = b_spec.garrison.orc(run.orc_id) if b_spec else None
        name = orc.name if orc else run.orc_id
        try:
            chronicles.record(self.repo_root, self.scroll, run.target, "handler_ran", by=name, orc=name,
                              outcome=run.outcome, roads=len(run.roads))
        except OSError:
            pass
        if run.outcome == "error" and self.is_running:
            self.notify(f"{name}: {run.error}", title="Handler", severity="warning")

    # -- recruiter and steward -----------------------------------------------------------------

    def recruit_from_prompt(self, building_id: str, prompt: str, road=None,
                            on_rejected: Callable[[str], Any] | None = None) -> None:
        """R → a description → the Recruiter (one Claude call per attempt, in a thread) → preview."""
        if self.gold_exhausted():
            self.notify("🪙 budget exhausted — the Recruiter costs a Claude call", title="Recruiter", severity="warning")
            return
        snapshot = copy.deepcopy(self.scroll)
        self.push_screen(OrcProgress("🧙 The Recruiter is choosing chain → script → agent…"))

        def _worker() -> None:
            result = recruiter.recruit(prompt, snapshot, building_id, runner=RECRUIT_RUNNER or builders.claude_runner,
                                       road=road)
            self.call_from_thread(self._on_recruited, building_id, prompt, result, on_rejected)

        self.run_worker(_worker, thread=True, name="recruiter")

    def _on_recruited(self, building_id: str, prompt: str, result: recruiter.RecruitResult,
                      on_rejected: Callable[[str], Any] | None = None) -> None:
        if isinstance(self.screen, OrcProgress):
            self.screen.dismiss(None)
        spec = self.scroll.building(building_id)
        title = spec.title if spec else building_id
        if not result.ok:
            why = result.error or "; ".join(result.attempts[-1].errors[:2] if result.attempts else []) or "no handler"
            self.push_screen(RecruitFailed(result), lambda _: on_rejected and on_rejected(f"the Recruiter failed: {why}"))
            return
        titles = {b.id: f"{b.icon} {b.title}".strip() for b in self.scroll.buildings}

        def done(ok: bool | None) -> None:
            if ok:
                subject = fastpath.Subject("agent", str((result.orc or {}).get("name") or "orc"),
                                           {"building": building_id, "orc": result.orc, "roads": result.roads},
                                           result.script_source)
                self.council_gate(subject, hire, on_rejected=(lambda why: on_rejected(f"the Council: {why}"))
                                  if on_rejected else None)
            elif on_rejected:
                on_rejected("you declined the handler — try another prompt")

        def hire() -> None:
            try:
                orc = recruiter.apply(self.scroll, building_id, result, self.repo_root)
            except (ValueError, OSError) as e:
                self.notify(str(e), title="Recruiter", severity="error")
                return
            if orc.script is not None:          # the operator saw it and the Council passed it
                orc.script = {**orc.script, "reviewed": True}
                orc.status = "idle"
            self._roads_changed()
            self.refresh_roster()
            try:
                chronicles.record(self.repo_root, self.scroll, building_id, "orc_recruited", orc=orc.name)
            except OSError:
                pass
            self.notify(f"{orc.avatar} {orc.name} ({orc.kind}) joined {title}", title="Recruiter")

        self.push_screen(RecruitPreview(title, result, titles), done)

    def watch_building(self, building_id: str, interactive: bool = False) -> None:
        """The steward's watch in a thread: free metrics, a model only when there are findings."""
        if building_id in self._watching:
            return
        self._watching.add(building_id)
        snapshot = copy.deepcopy(self.scroll)
        carts, runs = list(self.roads.carts), list(self.roads.runs)
        budget_ok = not self.gold_exhausted()
        if interactive:
            self.push_screen(OrcProgress("🔎 The steward is looking at the building…"))

        def _worker() -> None:
            report = steward.watch(self.repo_root, snapshot, building_id, carts=carts, runs=runs,
                                   runner=STEWARD_RUNNER or builders.claude_runner, budget_ok=budget_ok)
            try:
                steward.save_report(self.repo_root, report)
            except OSError:
                pass
            self.call_from_thread(self._on_watched, building_id, report, interactive)

        self.run_worker(_worker, thread=True, name=f"steward-{building_id}")

    def _on_watched(self, building_id: str, report: steward.StewardReport, interactive: bool) -> None:
        self._watching.discard(building_id)
        if isinstance(self.screen, OrcProgress):
            self.screen.dismiss(None)
        try:
            chronicles.record(self.repo_root, self.scroll, building_id, "steward_report",
                              findings=len(report.findings), proposals=len(report.proposals))
        except OSError:
            pass
        spec = self.scroll.building(building_id)
        title = spec.title if spec else building_id
        if interactive:
            self.open_steward_report(building_id)
        elif report.findings:
            self.notify(f"{len(report.findings)} finding(s), {len(report.proposals)} proposal(s) — select its ★ orc, W",
                        title=f"🔎 Steward · {title}")
        self.refresh_roster()

    def open_steward_report(self, building_id: str) -> None:
        data = steward.load_report(self.repo_root, building_id)
        if data is None:
            return
        spec = self.scroll.building(building_id)
        title = spec.title if spec else building_id

        def done(index: int | None) -> None:
            if index is None:
                return
            what = self.apply_steward_proposal(building_id, data, index, by="you")
            if what is None:
                return
            self.notify(f"✅ {what} — Z on it takes it back", title=f"Steward · {title}")

        self.push_screen(StewardView(title, data), done)

    def apply_steward_proposal(self, building_id: str, data: dict, index: int, by: str) -> str | None:
        """One steward proposal applied, with its own checkpoint (Z takes it back) and a line in the
        ledger of changes (realm/evolution.py). None when it could not be applied."""
        proposal = data["proposals"][index]
        try:
            what = steward.apply_proposal(self.scroll, building_id, proposal)
        except (ValueError, TypeError, KeyError) as e:
            self.notify(f"not applied: {e}", title="Steward", severity="warning")
            return None
        self._roads_changed()
        self.refresh_roster()
        try:
            chronicles.record(self.repo_root, self.scroll, building_id, "proposal_applied", what=what)
        except OSError:
            pass
        sha = self.checkpoint("auto-improve", building_id, f"steward: {what[:60]}") or ""
        evolution.record(self.repo_root, evolution.Change(
            building_id, str(proposal.get("type")), "steward", what, str(proposal.get("why") or "")[:200], by=by,
            sha=sha, key=f"steward:{building_id}:{data.get('ts', '')}:{index}"))
        return what

    def check_stewards(self) -> None:
        """Run each steward whose trigger is a schedule that came due since its last watch."""
        now = dt.datetime.now()
        self._maybe_optimize(now)
        self._maybe_weekly(now)
        for b in self.scroll.buildings:
            st = b.garrison.steward
            if b.demolished or st is None or st.trigger.get("type") != "cron":
                continue
            expr = str(st.trigger.get("expression") or "")
            last_report = steward.load_report(self.repo_root, b.id)
            try:
                last = dt.datetime.fromisoformat(last_report["ts"]) if last_report else None
            except (KeyError, ValueError):
                last = None
            if steward.due(expr, last, now):
                self.watch_building(b.id)

    def rally_pick_number(self, number: int) -> None:
        """`Y` picked a source window for the receiver: choose the event and the handler."""
        target_id = getattr(self.desktop, "rally_source", None)
        self.desktop.exit_rally_mode()
        if not target_id or self.scroll is None:
            return
        source_w = next((w for w in self.desktop.windows if w.number == number and self.desktop.in_view(w)), None)
        if source_w is None:
            return
        source_id = source_w.window_id
        src_spec, tgt_spec = self.scroll.building(source_id), self.scroll.building(target_id)
        src_title = src_spec.title if src_spec else source_id
        tgt_title = tgt_spec.title if tgt_spec else target_id
        choices = self._road_choices(source_id, target_id) + self._rule_choices(source_id, target_id)
        if not choices:
            self.notify(f"{tgt_title} can take nothing from {src_title}", title="Roads")
            return

        def done(choice: tuple[str, str | None] | None) -> None:
            if choice and choice[1] == RULE:
                self.road_with_rule(target_id, source_id)
                return
            if choice:
                event, handler = choice
                orc = tgt_spec.garrison.handler(handler) if handler and tgt_spec else None
                base, _, route = event.partition("#")
                subject = fastpath.Subject("road", f"{source_id}->{target_id}", {
                    "source": source_id, "target": target_id, "event": base,
                    "handler_kind": orc.kind if orc else "", "filter": {"route": [route]} if route else {}})
                self.council_gate(subject, lambda: self.add_road(target_id, source_id, event, handler))

        self.push_screen(SubscribeModal(src_title, tgt_title, choices), done)

    def _road_choices(self, source_id: str, target_id: str) -> list[tuple[str, str | None, str]]:
        """(event, handler or None, label) the receiver can subscribe to from the source."""
        if self.scroll is None or source_id == target_id:
            return []
        src, tgt = self.scroll.building(source_id), self.scroll.building(target_id)
        if src is None or tgt is None:
            return []
        has_garrison = bool(src.garrison.members)
        out = [(ev, None, f"plain · {pipes.label(ev)}")
               for ev in pipes.road_events(source_id, target_id, has_garrison, handler=False)]
        spec = self.custom_specs.get(source_id)
        if spec is not None and catalog.type_of(spec).id == "totem":     # one road per route
            from orkcraft.realm import totem
            out = [(f"totem.routed#{r}", None, f"plain · route {r}")
                   for r in totem.routes((spec.get("config") or {}).get("rules") or [])] + out
        for orc in tgt.garrison.handlers:
            for ev in pipes.road_events(source_id, target_id, has_garrison, handler=True):
                out.append((ev, orc.id, f"{orc.avatar} {orc.name} ({orc.kind}) · {pipes.label(ev)}"))
        return out

    def _rule_choices(self, source_id: str, target_id: str) -> list[tuple[str, str | None, str]]:
        """Roads v2: one ✨ row per event the source sends — a rule makes the handler."""
        src = self.scroll.building(source_id) if self.scroll is not None else None
        if self.demo or src is None or source_id == target_id:
            return []
        if not pipes.road_events(source_id, target_id, bool(src.garrison.members), handler=True):
            return []
        return [("*", RULE, "✨ Listen with a prompt… — pick one or several events, say how to handle them")]

    def road_with_rule(self, target_id: str, source_id: str, picked: list[str] | None = None, note: str = "") -> None:
        """Roads v3: one or several events + a prompt → the Recruiter makes the handler
        (a chain or a script when the rule needs no judgement) → the Council reviews it. A rejection
        comes back here with the prompt emptied and the reason shown."""
        src, tgt = self.scroll.building(source_id), self.scroll.building(target_id)
        has = bool(src.garrison.members) if src else False
        events = [(ev, pipes.label(ev)) for ev in pipes.road_events(source_id, target_id, has, handler=True)]
        if not events:
            self.notify("this source sends nothing a listener can take", title="Roads")
            return

        def done(answer: tuple[list[str], str] | None) -> None:
            if not answer:
                return
            chosen, prompt = answer
            self.recruit_from_prompt(target_id, prompt, road=[(source_id, e) for e in chosen],
                                     on_rejected=lambda why: self.road_with_rule(target_id, source_id, chosen, why))

        self.push_screen(RoadRuleModal(src.title if src else source_id, tgt.title if tgt else target_id, events,
                                       picked, note), done)

    def _roads_changed(self) -> None:
        self.desktop.save()
        self.desktop.replan_roads()
        self.refresh_rally_indicators()

    def add_road(self, target_id: str, source_id: str, event: str, handler: str | None, quiet: bool = False) -> None:
        event, _, route = event.partition("#")             # a Totem's route: a road that waits for it
        flt = {"route": [route]} if route else None
        try:
            road = scroll.subscribe(self.scroll, target_id, source_id, event, flt, handler=handler,
                                    label=route)
        except ValueError as e:
            self.notify(str(e), title="Roads", severity="warning")
            return
        self._roads_changed()
        if not quiet:
            self.checkpoint("road", target_id, f"road from {source_id} on {event}{' (' + route + ')' if route else ''}")
        src, tgt = self.scroll.building(source_id), self.scroll.building(target_id)
        orc = tgt.garrison.handler(handler) if handler and tgt else None
        who = orc.name if orc else "plain"
        src_title = src.title if src else source_id
        try:
            chronicles.record(self.repo_root, self.scroll, target_id, "road_subscribed",
                              source=src_title, event=pipes.label(event), handler=who)
        except OSError:
            pass
        if not quiet:
            self.notify(f"🛤 {src_title} → {tgt.title if tgt else target_id} ({pipes.label(event)}, {who})",
                        title="Roads")
        return road

    def remove_road(self, key: str) -> None:
        target_id, road_id = split_key(key)
        try:
            road = scroll.unsubscribe(self.scroll, target_id, road_id)
        except ValueError as e:
            self.notify(str(e), title="Roads", severity="warning")
            return
        self._roads_changed()
        self.checkpoint("road", target_id, f"remove road {road_id}")
        src = self.scroll.building(road.source)
        try:
            chronicles.record(self.repo_root, self.scroll, target_id, "road_removed",
                              source=src.title if src else road.source, event=pipes.label(road.event))
        except OSError:
            pass
        if self.focus_state.mode == "road":
            self.set_focus_state("building", building_id=target_id)
        self.notify(f"🚧 road from {src.title if src else road.source} removed", title="Roads")

    def change_road_handler(self, key: str) -> None:
        target_id, road_id = split_key(key)
        found = scroll.find_road(self.scroll, road_id, target_id)
        if found is None:
            return
        tgt, road = found
        src = self.scroll.building(road.source)
        # a handler takes whatever the source emits; plain only what the receiver shows
        handlers = [(o.id, f"{o.avatar} {o.name} ({o.kind})") for o in tgt.garrison.handlers]

        def done(choice: str | None) -> None:
            if choice is None:
                return
            handler = None if choice == PLAIN else choice
            if handler is None and road.event not in pipes.road_events(road.source, target_id, handler=False):
                self.notify(f"{tgt.title} cannot show this event without a handler", title="Roads", severity="warning")
                return
            try:
                scroll.set_road_handler(self.scroll, target_id, road_id, handler)
            except ValueError as e:
                self.notify(str(e), title="Roads", severity="warning")
                return
            self._roads_changed()
            orc = tgt.garrison.handler(handler) if handler else None
            try:
                chronicles.record(self.repo_root, self.scroll, target_id, "road_changed",
                                  source=src.title if src else road.source, handler=orc.name if orc else "plain")
            except OSError:
                pass
            self.set_focus_state("road", road=key)

        self.push_screen(RoadHandlerModal(self.desktop._road_label(key), handlers, road.handler), done)

    def refresh_rally_indicators(self) -> None:
        if self.scroll is None:
            return
        for w in self.desktop.windows:
            rally = self.scroll.rally_of(w.window_id)
            if rally:
                target_id = rally.target_building_id
                target_spec = self.scroll.building(target_id)
                target_title = target_spec.title if target_spec else target_id
                target_icon = target_spec.icon if target_spec and target_spec.icon else ""
                # Short, as in the spec's frame `[ 🚩 ──► 🔮 Spire ]`: the full title rarely fits beside the badge.
                short = (target_title.split() or [target_id])[-1].strip("()")
                target_label = f"{target_icon} {short}".strip()
                arrow = "🚩 ⏹──►" if rally.pipe_mode == pipes.ON_TASK else "🚩 ──►"
                w.set_rally(f"{arrow} {target_label}")
            else:
                w.set_rally("")

    # -- console height ----------------------------------------------------------------------------

    def action_console_height(self, step: int) -> None:
        pct = self._console.set_height_pct(self._console.height_pct + step)
        self._store_console_height(pct)

    def on_console_resized(self, message: Console.Resized) -> None:
        self._store_console_height(message.pct)

    def _store_console_height(self, pct: int) -> None:
        self.scroll.preferences["console_height_pct"] = pct
        self.desktop.save()

    # -- worktrees (stage 12) ---------------------------------------------------------------------

    def session_cwd(self) -> Path:
        """Where new War Tent sessions run: the active orkspace's worktree, else the repository."""
        return worktrees.cwd_for(self.scroll, self.scroll.active_orkspace_id, self.repo_root)

    def action_worktree(self) -> None:
        ork = self.scroll.active_orkspace
        if ork.git.enabled and ork.git.mode == "root":
            self.notify(f"{ork.name} works in the repository itself — create another orkspace (N) for a worktree",
                        title="⎇ Worktree")
            return

        def done(changed: bool | None) -> None:
            if changed:
                self.desktop.save()
                self.refresh_worktree_marks()
                g = self.scroll.active_orkspace.git
                self.notify(f"⎇ {ork.name}: " + (f"{g.branch} in {g.path}" if g.enabled else "no worktree"),
                            title="Worktree")
                self.refresh_roster()

        self.push_screen(WorktreeModal(self.scroll, self.repo_root, ork.id), done)

    def refresh_worktree_marks(self) -> None:
        """War Map marks: `⎇ branch` (+ `*` when there is uncommitted work, `?` when the folder is gone)."""
        marks: dict[str, str] = {}
        for ork in self.scroll.orkspaces:
            if not (ork.git.enabled and ork.git.mode == "worktree"):
                continue
            path = (self.repo_root / ork.git.path).resolve()
            if self.demo:   # the sandbox describes worktrees, it does not create them
                marks[ork.id] = f"⎇ {ork.git.branch}"
                continue
            try:
                st = worktrees.status(path)
                marks[ork.id] = f"⎇ {ork.git.branch}{'*' if st.dirty else ''}"
            except (worktrees.WorktreeError, OSError, Exception):
                marks[ork.id] = f"⎇ {ork.git.branch}?"
        self.worktree_marks = marks

    # -- telemetry 🪙 / 🪵 ------------------------------------------------------------------------

    def refresh_telemetry(self) -> None:
        """Re-read this run's transcripts (only new bytes) and warn once when a limit is crossed."""
        self.refresh_worktree_marks()
        try:
            self.snapshot = self.telemetry.refresh()
        except OSError:
            return
        budget = self.scroll.budget
        if not self._gold_warned and self.snapshot.spent_usd >= budget.gold_session_limit_usd > 0:
            self._gold_warned = True
            self.notify(
                f"🪙 ${self.snapshot.spent_usd:.2f} spent of ${budget.gold_session_limit_usd:.2f} this run — new "
                "sessions are held until you raise budget.gold_session_limit_usd in .orkcraft.json",
                title="Treasury empty", severity="error", timeout=12,
            )
        for key, ctx in self.snapshot.context_by_terminal.items():
            if ctx >= budget.lumber_context_limit_tokens > 0 and key not in self._lumber_warned:
                self._lumber_warned.add(key)
                self.notify(
                    f"🪵 {telemetry.fmt_tokens(ctx)} of context in {key} (limit "
                    f"{telemetry.fmt_tokens(budget.lumber_context_limit_tokens)}) — /compact or start fresh",
                    title="Lumber over the limit", severity="warning", timeout=10,
                )

    def _resource_texts(self) -> tuple[str, str, str, str]:
        """(gold, gold level, lumber, lumber level) for the HUD; "—" until a session reports."""
        budget, snap = self.scroll.budget, self.snapshot
        gold_limit = f"${budget.gold_session_limit_usd:.2f}"
        if snap.sessions or snap.unpriced:
            # "+" marks spend that could not be priced (agy, or a model with no published price).
            gold = f"${snap.spent_usd:.2f}{'+' if snap.unpriced else ''} / {gold_limit}"
        else:
            gold = f"$— / {gold_limit}"
        gold_level = telemetry.level(snap.spent_usd, budget.gold_session_limit_usd)
        key = self._active_terminal_key()
        ctx = snap.context_by_terminal.get(key) if key else None
        if ctx is None and snap.context_by_terminal:
            ctx = max(snap.context_by_terminal.values())
        lumber_limit = telemetry.fmt_tokens(budget.lumber_context_limit_tokens)
        lumber = f"{telemetry.fmt_tokens(ctx)} / {lumber_limit}" if ctx is not None else f"— / {lumber_limit}"
        lumber_level = telemetry.level(ctx or 0, budget.lumber_context_limit_tokens)
        return gold, gold_level, lumber, lumber_level

    def _quota_text(self) -> tuple[str, str, bool]:
        """(quota, its level, whether 🪙 shows): the HUD corner follows each tool's billing
        (settings.py) — the used share of the tightest window for a subscription, 🪙 for an API."""
        machine = self.desktop.machine
        on = [t for t, c in machine.tools.items() if c.enabled]
        subs = [t for t in on if machine.tools[t].billing == "subscription"]
        if not subs:
            return "", "ok", True
        from orkcraft.screens.limits_view import LimitsView
        limits = next((lv.limits for lv in self.query(LimitsView)), None) or []
        parts, worst = [], 0.0
        for t in subs:
            left = [x.remaining for x in limits if x.provider == t and x.remaining is not None]
            if left:
                used = round((1 - min(left)) * 100)
                worst = max(worst, used)
                parts.append(f"{t} {used}%")
            else:
                parts.append(f"{t} —")
        return " · ".join(parts), telemetry.level(worst, 100), len(subs) < len(on)

    def _active_terminal_key(self) -> str | None:
        try:
            term = self.chat.current_terminal
        except Exception:  # the War Tent may be unmounted during shutdown
            return None
        if term is None:
            return None
        return next((k for k, t in self.chat.terminals.items() if t is term), None)

    def gold_exhausted(self) -> bool:
        """True (and says so) when this run's spend reached the 🪙 limit: no new sessions."""
        limit = self.scroll.budget.gold_session_limit_usd
        if limit > 0 and self.snapshot.spent_usd >= limit:
            self.notify(f"🪙 ${self.snapshot.spent_usd:.2f} of ${limit:.2f} spent this run — raise "
                        "budget.gold_session_limit_usd in .orkcraft.json to summon more",
                        title="Treasury empty", severity="warning")
            return True
        return False

    # -- roster, alerts ----------------------------------------------------------------------

    def refresh_roster(self) -> None:
        # The 1 s timer can fire while the app shuts down and the windows are already unmounted.
        if not self._desktop.is_attached or not self._desktop.query("#chat-view"):
            return
        existing_terms = getattr(self.chat, "terminals", {})
        self.deployments = {k: v for k, v in self.deployments.items() if k in existing_terms}

        built = []
        for b_spec in self.scroll.buildings:
            if b_spec.demolished:
                continue
            b = self.building(b_spec.id)
            if b is None:
                continue
            labels: dict[str, list[str]] = {}
            for road in b_spec.roads:
                if road.handler:
                    src = self.scroll.building(road.source)
                    src_label = f"{src.icon} {src.title}".strip() if src else road.source
                    labels.setdefault(road.handler, []).append(f"{src_label} · {pipes.label(road.event)}")
            built.append((b, b_spec.garrison.members, b_spec.garrison.lead_orc_id, labels))

        workers = worker_infos(self.chat.terminals, self.chat.meta)
        self.roster = build_roster(
            self.repo_root, built, workers, self.dismissed, deployments=self.deployments
        )
        self._note_alerts()
        for w in self.desktop.windows:
            badge = garrison_badge(self.roster.garrison(w.window_id))
            if w.window_id == TOWN_HALL and getattr(self, "order_burning", False) and ALERT_ICON not in badge:
                badge = f"{badge} {ALERT_ICON}".strip()      # a town described in words waits for the Builder
            w.set_badge(badge)
            if (hut := self.desktop.huts.get(w.window_id)) is not None:
                hut.set_badge(w.badge)

        if hasattr(self, "_console") and self._console is not None:
            self._console.refresh_state(self.focus_state, self.roster)
        self.refresh_hud()
        self._elders_consider()

    def refresh_hud(self) -> None:
        gold, gold_level, lumber, lumber_level = self._resource_texts()
        quota, quota_level, show_gold = self._quota_text()
        hour = schedule.status(self.desktop.machine)
        self._hud.set_resources(Resources(
            budget=self.scroll.budget,
            supply=self.roster.active, supply_max=self.scroll.budget.supply_max_workers,
            alerts=len(self.roster.alerts), commit=self.config.auto_commit,
            gold=gold, gold_level=gold_level, lumber=lumber, lumber_level=lumber_level,
            quota=quota, quota_level=quota_level, show_gold=show_gold, hour=hour,
        ))

    # -- orders (modals only on explicit request) ----------------------------------------------------

    def open_unit(self, w: Window, member: OrcSpec | None = None) -> None:
        b = self.building(w.window_id)
        b_spec = self.scroll.building(w.window_id)
        if b is None or b_spec is None:
            return
        if member is None:
            member = b_spec.garrison.lead
        if member is None:
            return
        ref = f"{w.window_id}/{member.id}"
        orc = next((o for o in self.roster.orcs if o.category == RESIDENT and o.ref == ref), None)
        if orc is None:
            orc = Orc(
                name=member.name,
                role=member.role or b.role,
                category=RESIDENT,
                trigger=Trigger.from_dict(member.trigger),
                status="idle",
                task=member.orders,
                building=w.window_id,
                ref=ref,
                lead=(member.id == b_spec.garrison.lead_orc_id),
            )

        def done(result: dict | None) -> None:
            if not result:
                return
            if result.get("answer") and orc.alert is not None:
                self.open_alert(orc.alert, orc.name)
                return
            trig = result["trigger"].to_dict()
            if "expression" in trig and not trig["expression"]:
                del trig["expression"]
            member.trigger = trig
            member.orders = result["context"]
            if "tier" in result:
                member.harness = tiers.with_tier(member.harness, result["tier"] or None)
            self.desktop.save()
            self.refresh_roster()
            try:
                chronicles.record(self.repo_root, self.scroll, w.window_id, "orders_changed",
                                  orc=member.name, trigger=result["trigger"].label)
            except OSError:
                pass
            self.notify(f"🧌 {member.name}: orders saved ({result['trigger'].label})", title="Orders")

        is_steward = member.id == b_spec.garrison.lead_orc_id
        tier = None if is_steward or not member.uses_model else (tiers.orc_tier(member.harness, member.kind) or "")
        self.push_screen(UnitModal(orc, b.label, member.orders, tier=tier), done)

    def _alert_who_map(self) -> dict[str, str]:
        who_map: dict[str, str] = {}
        for o in self.roster.orcs:
            if o.alert:
                who_map[o.alert.id] = o.name
        for a in self.roster.alerts:
            if a.id not in who_map:
                if a.source == "ticket":
                    who_map[a.id] = f"Ticket {a.ref}" if a.ref else "Ticket"
                elif a.source == "warder":
                    who_map[a.id] = "Warder"
                elif a.source == "terminal":
                    who_map[a.id] = f"Session {a.ref}"
                else:
                    who_map[a.id] = "Alert"
        return who_map

    def open_alert(self, alert: Alert, who: str = "") -> None:
        who_map = {alert.id: who} if who else self._alert_who_map()
        self.push_screen(AwaitingOrdersModal([alert], who_map, who=who))

    def answer_alert(self, alert: Alert, key: str) -> None:
        if alert.source == "terminal":
            # Claude / agy menus take digits directly; yes/no or input prompts take newline
            to_send = key if key.isdigit() else f"{key}\r"
            self.chat.send(alert.ref, to_send.encode())
            self.desktop.focus_window(self._sessions_window())  # type: ignore[arg-type]
            self.chat.show_terminal(alert.ref)
        elif alert.source == "warder":
            if key == "1":
                self.dismissed.add(alert.id)      # acknowledged; the log keeps it
        self.refresh_roster()

    def action_awaiting_orders(self) -> None:
        if self.roster.alerts:
            who_map = self._alert_who_map()
            self.push_screen(AwaitingOrdersModal(self.roster.alerts, who_map))
        else:
            self.notify("No units requiring orders", title="❓")

    def action_next_alert(self) -> None:
        self.action_awaiting_orders()

    def action_spawn_orc(self) -> None:
        """A new Claude session in the War Tent, tied to the selected node."""
        w = self._sessions_window()
        if w is None:
            return
        if self.roster.active >= self.scroll.budget.supply_max_workers:
            self.notify(f"🥩 Supply {self.roster.active}/{self.scroll.budget.supply_max_workers}: build more farms first "
                        "(stop a session with x in the War Tent)", title="Not enough food", severity="warning")
            return
        if self.gold_exhausted():
            return
        self.desktop.focus_window(w)
        self.chat.set_node(self.selected_node)
        self.chat.action_new_session("claude")

    def action_build_window(self, initial_prompt: str = "") -> None:
        def done(prompt: str | None) -> None:
            if not prompt:
                return
            self._start_build(prompt)

        self.push_screen(BuildModal(initial_prompt=initial_prompt), done)

    def _taken_building_ids(self) -> set[str]:
        """Ids a new building may not take: loaded buildings and every building the scroll remembers
        (a custom building whose spec file was deleted still has its scroll entry)."""
        return {b.id for b in self.buildings} | {b.id for b in self.scroll.buildings}

    def _start_build(self, prompt: str) -> None:
        self.push_screen(BuildProgress())

        def _worker() -> None:
            existing_ids = self._taken_building_ids()
            runner = BUILD_RUNNER or builders.claude_runner
            result = builders.build(prompt, self.repo_root, existing_ids=existing_ids, runner=runner)
            self.call_from_thread(self._on_build_finished, prompt, result)

        self.run_worker(_worker, thread=True, name="mason_artisan_build")

    def _on_build_finished(self, prompt: str, result: builders.BuildResult) -> None:
        self._log_build_request(prompt, result)
        self._show_build_result(prompt, result)

    def _log_build_request(self, prompt: str, result: builders.BuildResult | town_builder.TownPlan) -> None:
        """Every build request, kept in `.orkcraft/build-requests.jsonl`."""
        record: dict[str, Any] = {
            "ts": dt.datetime.now().isoformat(timespec="seconds"),
            "prompt": prompt,
            "ok": result.ok,
            "attempts": len(result.attempts),
            "cost_usd": result.cost_usd,
        }
        if result.ok:
            spec = getattr(result, "spec", None)
            record["id"] = spec["id"] if spec else [s["id"] for s in getattr(result, "specs", [])]
        else:
            last_errs = result.attempts[-1].errors if result.attempts else []
            record["error"] = result.error or ("; ".join(last_errs) if last_errs else "build failed")

        queue = self.repo_root / ".orkcraft" / "build-requests.jsonl"
        try:
            queue.parent.mkdir(parents=True, exist_ok=True)
            with queue.open("a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        except OSError:
            pass

    def _show_build_result(self, prompt: str, result: builders.BuildResult) -> None:
        if isinstance(self.screen, BuildProgress):
            self.screen.dismiss(None)

        if result.ok and result.spec:
            spec = result.spec

            def on_preview_done(confirmed: bool | None) -> None:
                if confirmed:
                    self.review_and_raise(spec)

            self.push_screen(BuildPreview(spec, result), on_preview_done)
        else:
            def on_failed_done(action: str | None) -> None:
                if action == "retry":
                    self.action_build_window(initial_prompt=prompt)

            self.push_screen(BuildFailed(result), on_failed_done)

    # -- 👍 / 👎 on a building's steward -----------------------------------------------

    def _title_of(self, building_id: str) -> str:
        b = self.scroll.building(building_id) if self.scroll is not None else None
        return f"{b.icon} {b.title}".strip() if b else building_id

    def like_building(self, building_id: str) -> bool:
        """K 👍: the building's last result becomes a reference."""
        out = feedback.like(self.repo_root, building_id)
        if out is None:
            self.notify("nothing to rate yet — it has sent no result", title="👍")
            return False
        self.notify(f"{self._title_of(building_id)}: its last result is a reference now", title="👍 Good")
        self._refresh_hall()
        return True

    def dislike_building(self, building_id: str) -> None:
        """F 👎: what went wrong? Broken inputs penalise its suppliers upstream, its logic only it."""
        out = feedback.last_output(self.repo_root, building_id) or {}
        cascade = [(self._title_of(b), feedback.CASCADE[hop - 1])
                   for b, hop in feedback.suppliers(self.repo_root, self.scroll, building_id)]

        def done(answer: tuple[str, str] | None) -> None:
            if answer is None:
                return
            incident = feedback.dislike(self.repo_root, self.scroll, building_id, *answer)
            who = ", ".join(f"{self._title_of(b)} −{p:g}" for b, p in incident.blamed.items()) or "nobody"
            self.notify(f"incident saved · {who}", title=f"👎 {self._title_of(building_id)}")
            self._refresh_hall()

        self.push_screen(DislikeModal(self._title_of(building_id), str(out.get("value", "")), cascade), done)

    def _orc_ids(self, orc: Orc) -> tuple[str, str]:
        """(building id, orc id) of a garrison orc."""
        return tuple(orc.ref.split("/", 1)) if "/" in orc.ref else (orc.building or "", "")  # type: ignore[return-value]

    def like_orc(self, orc: Orc) -> None:
        """👍 on an orc's own work (its building's results are rated on the building)."""
        b_id, orc_id = self._orc_ids(orc)
        if not orc_id:
            return
        feedback.rate_orc(self.repo_root, b_id, orc_id, True)
        self.notify(f"{orc.name}: noted as good work", title="👍 Good")
        self._console_refresh()

    def dislike_orc(self, orc: Orc) -> None:
        """👎 on an orc's work: what went wrong (a note), kept as an incident."""
        b_id, orc_id = self._orc_ids(orc)
        if not orc_id:
            return

        def done(note: str | None) -> None:
            if note is None:
                return
            feedback.rate_orc(self.repo_root, b_id, orc_id, False, note)
            self.notify(f"{orc.name}: incident saved", title="👎 Bad")
            self._console_refresh()

        self.push_screen(TextPrompt(f"👎 {orc.name} — what went wrong?", placeholder="optional"), done)

    def open_orc_model(self, orc: Orc) -> None:
        """🎒 The inventory's model button: change a garrison orc's harness and tier."""
        b_id, orc_id = self._orc_ids(orc)
        b_spec = self.scroll.building(b_id) if b_id else None
        member = next((m for m in b_spec.garrison.members if m.id == orc_id), None) if b_spec else None
        if member is None or not member.uses_model:
            self.notify(f"{orc.name}: its model is not set here", title="🎒 Model")
            return

        def done(harness: list[dict] | None) -> None:
            if harness is None:
                return
            try:
                scroll.update_orc(self.scroll, b_id, orc_id, harness=harness)
            except ValueError as e:
                self.notify(str(e), title="🎒 Model", severity="error")
                return
            self.desktop.save()
            self.refresh_roster()
            self.notify(f"{member.name}: {tiers.label(tiers.orc_tier(harness, member.kind)) or 'CLI default model'}",
                        title="🎒 Model")

        self.push_screen(OrcModelModal(member.name, member.harness), done)

    def _console_refresh(self) -> None:
        if getattr(self, "_console", None) is not None:
            self._console.refresh_state(self.focus_state, self.roster)

    def _refresh_hall(self) -> None:
        w = self.desktop.get_window(TOWN_HALL)
        view = next(iter(w.query(TownHallView)), None) if w is not None else None
        if view is not None:
            view.refresh_hall()

    # -- ⛏ the Peon's housekeeping ---------------------------------------------------

    def _daemon_chores(self) -> list[housekeeping.Chore]:
        out = []
        for w in self.desktop.windows:
            view = self._custom_view(w.window_id)
            if w.hidden and getattr(view, "hook", None) is not None:
                out.append(housekeeping.Chore("daemon", w.window_id, "a demolished building still listens (webhook)"))
        return out

    def cleanup(self, confirm: bool = True) -> list[str]:
        """F10 → 🧹: what piled up, shown first; Enter cleans it."""
        chores = housekeeping.scan(self.repo_root, {b.id for b in self.scroll.buildings}) + self._daemon_chores()
        if not chores:
            self.notify("nothing to clean", title="⛏ Peon")
            return []

        def go(yes: bool | None = True) -> list[str]:
            if not yes:
                return []
            done = housekeeping.clean(self.repo_root, [c for c in chores if c.kind != "daemon"])
            for c in chores:
                if c.kind == "daemon":
                    view = self._custom_view(c.path)
                    if view is not None and view.hook is not None:
                        view.hook.stop()
                        view.hook = None
                        done.append(f"stopped the webhook of {c.path}")
            self.notify("\n".join(done[:6]) + (f"\n… {len(done) - 6} more" if len(done) > 6 else ""), title="⛏ Cleaned")
            return done

        if not confirm:
            return go()
        listing = "\n".join(f"· {c.detail}: {c.path}" for c in chores[:12])
        self.push_screen(Confirm(f"🧹 Clean {len(chores)} thing(s)?", listing), go)
        return []

    # -- 🔧 local optimisation: a proposal, applied with one click ---------------------

    def _maybe_optimize(self, now: dt.datetime) -> None:
        if self.demo or self.gold_exhausted():
            return
        expr = str(fastpath.settings(self.repo_root).get("optimize_at") or "")
        if expr and steward.due(expr, optimize.last_run(self.repo_root), now):
            optimize.mark_run(self.repo_root, now)
            self.optimize_now(interactive=False)

    def optimize_now(self, interactive: bool = True) -> bool:
        """Today's hungriest building the operator is not happy with → the Council's proposal (in a
        thread). False when there is nothing to propose."""
        cand = optimize.leader(self.repo_root)
        if cand is None:
            if interactive:
                self.notify("nothing to improve: today's top spender is liked, or nothing was spent",
                            title="🔧 Self-improvement")
            return False
        spec = self.custom_specs.get(cand.building)
        ps = optimize.parts(self.scroll, spec, cand.building, self.repo_root)
        if not ps:
            if interactive:
                self.notify(f"{self._title_of(cand.building)} spends the most but has no prompt to shrink",
                            title="🔧 Self-improvement")
            return False
        cfg = (spec or {}).get("config") or {}
        mocks = workshop.load_blueprint(self.repo_root, cand.building).get("mocks") or []
        runtime = str(cfg.get("runtime") or "python")
        if interactive:
            self.notify(f"the Council looks at {self._title_of(cand.building)} ({cand.tokens} tokens today)",
                        title="🔧 Self-improvement")

        def _worker() -> None:
            result = optimize.propose(self.repo_root, cand, ps, OPTIMIZE_RUNNER or builders.claude_runner, runtime, mocks)
            self.call_from_thread(self._on_proposal, result, interactive)

        self.run_worker(_worker, thread=True, name="council_optimize")
        return True

    def _on_proposal(self, result: optimize.Result, interactive: bool) -> None:
        if result.proposal is None:
            if interactive:
                why = result.error or "; ".join(result.problems[:3]) or "no proposal"
                self.notify(why, title="🔧 The Council found nothing it could prove", severity="warning")
            return
        optimize.save(self.repo_root, result.proposal)
        self._refresh_hall()
        if len(self.screen_stack) > 1:              # the operator is busy in a dialog: leave it waiting
            self.notify(f"a proposal for {self._title_of(result.proposal.building)} waits — F10 → Self-improvement",
                        title="🔧 Self-improvement")
            return
        self.show_proposal(result.proposal)

    def open_proposals(self) -> None:
        waiting = optimize.pending(self.repo_root)
        if waiting:
            self.show_proposal(waiting[0])
        else:
            self.optimize_now(interactive=True)

    def show_proposal(self, p: optimize.Proposal) -> None:
        def done(choice: str | None) -> None:
            if choice == "apply":
                self.apply_proposal(p)
            elif choice == "dismiss":
                p.status = "dismissed"
                optimize.save(self.repo_root, p)
                self._refresh_hall()

        self.push_screen(ProposalModal(p, self._title_of(p.building)), done)

    def apply_proposal(self, p: optimize.Proposal, kind: str = "auto-improve") -> bool:
        """The change, a checkpoint `<kind>(<id>)` (Z takes it back), the proposal marked applied."""
        if p.status != "pending":
            self.notify(f"this proposal was {p.status} already", title="🔧 Not applied", severity="warning")
            return False
        bid = p.building
        b = self.scroll.building(bid)
        spec = self.custom_specs.get(bid)
        stale = "it changed since the proposal — ask again"
        if p.target.startswith("orc:"):
            orc = b.garrison.handler(p.target[4:]) if b is not None else None
            if orc is None or orc.orders != p.before:
                self.notify(stale, title="🔧 Not applied", severity="warning")
                return False
            if p.action == "chain":
                orc.kind, orc.chain, orc.orders = "chain", json.loads(p.after), ""
            else:
                orc.orders = p.after
            self.desktop.save()
            self.refresh_roster()
        else:
            cfg = dict((spec or {}).get("config") or {})
            key = "steward_prompt" if p.target == "steward" else "orders"
            if spec is None or cfg.get(key) != p.before:
                self.notify(stale, title="🔧 Not applied", severity="warning")
                return False
            if p.action == "script":
                cfg.pop(key, None)
                workshop.save_script(self.repo_root, bid, str(cfg.get("runtime") or "python"), p.after)
            else:
                cfg[key] = p.after
            new = dict(spec, config=cfg)
            problems = masonry.save_spec(self.repo_root, new, existing_ids=set(self.custom_specs) - {bid})
            if problems:
                self.notify("\n".join(problems), title="🔧 Not applied", severity="error")
                return False
            self.custom_specs[bid] = new
            view = self._custom_view(bid)
            if view is not None:
                view.spec = new
        sha = self.checkpoint(kind, bid, f"{p.action} {p.target}: {p.why[:60]}")
        p.status, p.commit = "applied", sha or ""
        optimize.save(self.repo_root, p)
        evolution.record(self.repo_root, evolution.Change(
            bid, p.action, "weekly" if kind == "weekly" else "daily", f"{p.action} {p.target}", p.why[:200],
            by="orcs" if self._hushed else "you", sha=p.commit, key=p.id))
        self._refresh_hall()
        self.notify(f"{self._title_of(bid)}: {p.action} applied — Z on it takes it back", title="🔧 Applied")
        return True

    # -- 🗓 the weekly self-audit ------------------------------------------------------

    def _maybe_weekly(self, now: dt.datetime) -> None:
        if self.demo or self.gold_exhausted():
            return
        expr = str(fastpath.settings(self.repo_root).get("weekly_at") or "")
        if expr and steward.due(expr, weekly.last_run(self.repo_root), now):
            weekly.mark_run(self.repo_root, now)
            self.weekly_audit_now(interactive=False)

    def open_weekly(self) -> None:
        report = weekly.latest(self.repo_root)
        fresh = report is not None and dt.datetime.fromisoformat(report.ts) > dt.datetime.now() - dt.timedelta(days=7)
        if fresh and any(i.applicable and i.n not in report.applied for i in report.items):
            self.show_weekly(report)
        else:
            self.weekly_audit_now(interactive=True)

    def weekly_audit_now(self, interactive: bool = True) -> None:
        """The heavy model over the whole camp (in a thread), then the report with checkboxes."""
        model = str(fastpath.settings(self.repo_root).get("weekly_model") or "opus")
        runner = WEEKLY_RUNNER or functools.partial(builders.claude_runner, model=model)
        snapshot, specs = copy.deepcopy(self.scroll), copy.deepcopy(self.custom_specs)
        rules = audit.run(self.repo_root, self.scroll, dict(self.custom_specs), self.snapshot.spent_usd,
                          self.scroll.budget.gold_session_limit_usd)
        self.notify(f"{model} looks over the camp — the report follows", title="🗓 Weekly self-audit")

        def _worker() -> None:
            result = weekly.run(self.repo_root, snapshot, specs, runner, model, rules)
            self.call_from_thread(self._on_weekly, result, interactive)

        self.run_worker(_worker, thread=True, name="weekly_audit")

    def _on_weekly(self, result: weekly.Result, interactive: bool) -> None:
        if result.report is None:
            self.notify(result.error or "no report", title="🗓 Weekly self-audit failed", severity="warning")
            return
        if len(self.screen_stack) > 1:
            self.notify("the weekly report waits — F10 → Weekly self-audit", title="🗓 Weekly self-audit")
            return
        self.show_weekly(result.report)

    def show_weekly(self, report: weekly.Report) -> None:
        def done(picked: list[int] | None) -> None:
            if picked:
                self.apply_weekly(report, picked)

        self.push_screen(WeeklyReportModal(report), done)

    def apply_weekly(self, report: weekly.Report, picked: list[int]) -> list[int]:
        """Each ticked item, checked again against the camp as it is now, applied as its own
        checkpoint `weekly(<id>)`; then the Town Scroll is saved and the touched daemons restart."""
        done, touched, failed = [], set(), []
        restart = report.restart
        for item in report.items:
            if item.n not in picked or item.n in report.applied:
                continue
            item = weekly.check_item(item, self.repo_root, self.scroll, self.custom_specs)
            if not item.applicable:
                failed.append(f"{item.title}: {'; '.join(item.problems) or 'advice only'}")
                continue
            bid = item.building
            ok = False
            if item.change in ("shrink", "chain", "script"):
                p = optimize.Proposal(f"w{report.ts[:10]}-{item.n}", report.ts, bid, item.change,
                                      str(item.data.get("target")), item.before, item.after, item.why)
                ok = self.apply_proposal(p, kind="weekly")
            elif item.change == "remove_road":
                try:
                    scroll.unsubscribe(self.scroll, bid, str(item.data.get("road")))
                except ValueError as e:
                    failed.append(f"{item.title}: {e}")
                else:
                    self._roads_changed()
                    self.checkpoint("weekly", bid, f"remove road {item.data.get('road')}: {item.why[:60]}")
                    ok = True
            elif item.change == "remove_building":
                w = self.desktop.get_window(bid)
                if w is not None:
                    self.desktop.hide(w)
                    self.desktop.save()
                self.checkpoint("weekly", bid, f"remove: {item.why[:60]}")
                ok, restart = True, True
            elif item.change == "add_building":
                ok = self.raise_spec(weekly.new_spec(item))
                restart = restart or ok
            elif item.change == "set_config":
                spec = self.custom_specs[bid]
                new = dict(spec, config={**(spec.get("config") or {}), str(item.data["key"]): item.data.get("value")})
                problems = masonry.save_spec(self.repo_root, new, existing_ids=set(self.custom_specs) - {bid})
                if problems:
                    failed.append(f"{item.title}: {'; '.join(problems)}")
                else:
                    self.custom_specs[bid] = new
                    view = self._custom_view(bid)
                    if view is not None:
                        view.spec = new
                    self.checkpoint("weekly", bid, f"set {item.data['key']}: {item.why[:60]}")
                    ok = True
            if ok:
                done.append(item.n)
                touched.add(bid)
                if item.change not in ("shrink", "chain", "script"):    # those are in the ledger already
                    where = weekly.new_spec(item)["id"] if item.change == "add_building" else bid
                    last = checkpoint.history(self.repo_root, where, 1)
                    evolution.record(self.repo_root, evolution.Change(
                        where, item.change, "weekly", item.title[:120], item.why[:200],
                        by="orcs" if self._hushed else "you", sha=last[0].sha if last else "",
                        key=f"weekly:{report.ts}:{item.n}"))
        self.desktop.save()
        for bid in touched:                                   # the daemons pick up what changed
            again = getattr(self._custom_view(bid), "restart", None)
            if again is not None:
                again()
        report.applied = sorted(set(report.applied) | set(done))
        weekly.save(self.repo_root, report)
        self._refresh_hall()
        msg = f"{len(done)} applied" + (f" · {len(failed)} not: " + " | ".join(failed[:3]) if failed else "")
        self.notify(msg, title="🗓 Weekly self-audit", severity="warning" if failed else "information")
        if restart and done and not self._hushed:
            self.push_screen(Confirm("🔄 Restart orkcraft now?", "the camp changed its buildings — a fresh start "
                                     "reloads everything (the Town Scroll is saved)"),
                             lambda yes: yes and self.restart_app())
        return done

    def restart_app(self) -> None:
        """Save everything and start again (the CLI runs the app anew on "restart")."""
        self.desktop.save()
        self.exit(result="restart")

    def open_settings(self) -> None:
        """F10 → ⚙: the self-improvement's models and schedules (`.orkcraft/council/settings.json`)."""
        def done(values: dict | None) -> None:
            if values:
                fastpath.save_settings(self.repo_root, values)
                self.notify("saved", title="⚙ Self-improvement settings")

        self.push_screen(SettingsModal(fastpath.settings(self.repo_root)), done)

    # -- the Council's Fast Path ------------------------------------------------------

    def review_and_raise(self, spec: dict) -> bool:
        """A building made from scratch: past the Council, then raised (presets skip this)."""
        return self.council_gate(fastpath.Subject("building", str(spec.get("id") or "?"), spec),
                                 lambda: self.place_and_raise(spec))

    def council_gate(self, subject: fastpath.Subject, on_approved: Callable[[], Any],
                     on_rejected: Callable[[str], Any] | None = None) -> bool:
        """Review `subject`, then `on_approved()` once it passes. A clean review (and a road with
        notes only) goes straight through; anything else shows the verdict. True when it went
        through at once."""
        existing = set(self._taken_building_ids()) if subject.kind == "building" else set()
        runner = None
        if not self.demo and (subject.kind != "road" or subject.data.get("handler_kind") in ("agent", "hybrid", "script")):
            runner = FASTPATH_RUNNER or fastpath.light_runner(self.repo_root)
        model = str(fastpath.settings(self.repo_root).get("fast_model") or "")
        went: list[bool] = []

        def record(verdict: fastpath.Verdict, decision: str) -> None:
            fastpath.log(self.repo_root, verdict, decision)
            w = self.desktop.get_window(TOWN_HALL)
            view = next(iter(w.query(TownHallView)), None) if w is not None else None
            if view is not None:
                view.refresh_hall()

        def finish(verdict: fastpath.Verdict) -> None:
            if verdict.clean or (subject.kind == "road" and not verdict.blocked and not verdict.objections):
                record(verdict, "approved")
                if verdict.warnings:
                    self.notify("\n".join(f"⚠ {n.text}" for n in verdict.warnings), title="🏛 Council")
                went.append(True)
                on_approved()
                return

            def done(ok: bool | None) -> None:
                decision = ("overridden" if verdict.objections else "approved") if ok else \
                    "rejected" if verdict.blocked else "cancelled"
                record(verdict, decision)
                if ok:
                    on_approved()
                    return
                if verdict.blocked:
                    self.notify("\n".join(verdict.reasons()[:4]), title=f"🏛 Council rejected the {subject.kind}",
                                severity="warning")
                if on_rejected is not None:
                    on_rejected("; ".join(verdict.reasons()[:2]) or "sent back")

            self.push_screen(CouncilVerdict(verdict), done)

        if runner is None:
            finish(fastpath.review(subject, self.repo_root, existing))
            return bool(went)
        self.push_screen(CouncilProgress(subject.kind))

        def _worker() -> None:
            verdict = fastpath.review(subject, self.repo_root, existing, runner, model)
            self.call_from_thread(self._council_reviewed, verdict, finish)

        self.run_worker(_worker, thread=True, name="council_fast_path")
        return False

    def _council_reviewed(self, verdict: fastpath.Verdict, finish: Callable[[fastpath.Verdict], None]) -> None:
        if isinstance(self.screen, CouncilProgress):
            self.screen.dismiss(None)
        finish(verdict)

    # -- checkpoints: the camp's own git in .orkcraft/ -----------------------------------------

    def checkpoint(self, kind: str, building: str, reason: str) -> str | None:
        """Save the scroll and commit the change in the service repository (never in the demo)."""
        if self.demo:
            return None
        try:
            self.desktop.save()
        except Exception:
            pass
        return checkpoint.commit(self.repo_root, kind, building, reason, self.config.layout_file)

    def action_revert_building(self) -> None:
        bid = self.focus_state.building_id if self.focus_state.mode == "building" else None
        if bid:
            self.revert_building(bid)

    def revert_building(self, building_id: str) -> bool:
        """Z: this building back to its previous checkpoint — its files, incoming roads and garrison;
        nothing else in the camp changes."""
        before = checkpoint.building_before(self.repo_root, building_id)
        if before is None:
            self.notify("no earlier checkpoint for this building", title="↶ Revert")
            return False
        parent, spec, entry, files = before
        if entry is None and spec is None:
            self.notify("this is the building's first checkpoint — demolish it with X instead", title="↶ Revert")
            return False
        checkpoint.restore_files(self.repo_root, building_id, spec, files)
        current = self.scroll.building(building_id) if self.scroll is not None else None
        if current is not None and entry is not None:
            old = scroll.TownScroll.from_dict({"active_orkspace_id": "x", "orkspaces": [], "buildings": [entry]}).buildings[0]
            known = {b.id for b in self.scroll.buildings}
            current.roads = [r for r in old.roads if r.source in known]
            current.garrison, current.actions = old.garrison, old.actions
            current.title, current.icon = old.title, old.icon
        if spec is not None:
            spec = catalog.migrate(spec)
            self.custom_specs[building_id] = spec
            pipes.set_typed(building_id, catalog.events_of(spec))
            view = self._custom_view(building_id)
            if view is not None:
                view.spec = spec
                refresh = getattr(view, "refresh_data", None)
                if refresh is not None:
                    refresh()
        self._roads_changed()
        self.refresh_roster()
        self.checkpoint("revert", building_id, f"back to {parent[:8]}")
        self.notify(f"back to checkpoint {parent[:8]}", title=f"↶ {building_id}")
        return True

    def _type_spec(self, type_id: str) -> dict | None:
        """A camp building's spec from the catalog: the type's defaults and a free id."""
        t = catalog.TYPES.get(type_id)
        if t is None or type_id in catalog.SYSTEM_TYPES | catalog.SCRATCH_TYPES or type_id == catalog.DEFAULT_TYPE:
            return None
        taken = self._taken_building_ids() | masonry.ID_RESERVED
        bid, n = type_id, 1
        while bid in taken:
            bid, n = f"{type_id}_{n}", n + 1
        return {"id": bid, "type": type_id, "title": t.title, "icon": t.icon, "summary": t.summary[:200],
                "orc": {"name": t.orc, "role": t.preview[:80]}}

    def build_from_type(self, type_id: str) -> bool:
        """A camp building straight from the catalog: the type's defaults, no model call."""
        spec = self._type_spec(type_id)
        return spec is not None and self.raise_spec(spec)

    def preset_params(self, type_id: str) -> None:
        """A preset's step 2: this building's name, icon, description and settings.
        Presets are reviewed code — no Council, no model call."""
        spec = self._type_spec(type_id)
        if spec is None:
            return
        t = catalog.TYPES[type_id]

        def check(s: dict) -> list[str]:
            return masonry.validate_spec(s, self.repo_root, self._taken_building_ids())

        def done(final: dict | None) -> None:
            if final:
                self.place_and_raise(final)

        self.push_screen(BuildReview(spec, check=check, heading=f"🏗 FROM A PRESET · 2/3 — {t.icon} {t.title}: "
                                                               "this building's name and settings"), done)

    # -- a building from scratch: interview → blueprint → Council + sandbox → approval

    def _scratch_sources(self) -> list[tuple[str, str]]:
        sources = []
        for b in self.scroll.buildings_in(self.scroll.active_orkspace_id):
            if b.demolished or b.id == TOWN_HALL:
                continue
            for ev in pipes.TYPED.get(b.id, ()):
                sources.append((f"{b.id}:{ev}", f"{b.icon} {b.title} → {pipes.label(ev)}"))
        return sources

    def action_build_scratch(self, previous: dict | None = None, history: list | None = None,
                             rejected: dict | None = None) -> None:
        """From scratch: a conversation with the Builder. A rejected blueprint comes
        back here — what the operator says after it is the Builder's feedback for the next draft."""
        sources = self._scratch_sources()
        runner = BUILD_RUNNER or builders.claude_runner
        opening = ("What should I change in the blueprint?" if rejected is not None else bp_chat.GREETING)
        start = len(history or [])

        def done(answer: dict | str | None) -> None:
            if answer == "form":
                self.push_screen(BuilderInterview(sources, previous), lambda iv: iv and self.start_blueprint(iv))
            elif isinstance(answer, dict):
                notes = [t for who, t in (answer.get("history") or [])[start + 1:] if who == "operator"]
                self.start_blueprint(answer, "\n".join(notes) if rejected is not None else "", rejected)

        self.push_screen(BuilderChat(sources, lambda h: blueprint.talk(h, sources, runner), history, opening), done)

    def start_blueprint(self, interview: dict, feedback: str = "", previous: dict | None = None) -> None:
        self.push_screen(BuildProgress("🛠 The Builder drafts a script, the Council and the sandbox check it…"))
        taken = self._taken_building_ids() | masonry.ID_RESERVED

        def _worker() -> None:
            result = blueprint.build(interview, taken, BUILD_RUNNER or builders.claude_runner, feedback, previous)
            verdict, runs = self.check_blueprint(result.blueprint, light=True) if result.ok else (None, [])
            self.call_from_thread(self._on_blueprint, interview, result, verdict, runs)

        self.run_worker(_worker, thread=True, name="builder_blueprint")

    def check_blueprint(self, bp: dict, light: bool = False) -> tuple[fastpath.Verdict, list[workshop.Run]]:
        """The Council on the blueprint (rules; the light model too when `light`), then — unless a
        rule blocks it — its script on the mock carts in the sandbox. Safe off the UI thread."""
        spec = blueprint.to_spec(bp)
        runner = (FASTPATH_RUNNER or fastpath.light_runner(self.repo_root)) if light and not self.demo else None
        model = str(fastpath.settings(self.repo_root).get("fast_model") or "")
        taken = self._taken_building_ids()
        verdict = fastpath.review(fastpath.Subject("building", bp["id"], spec, bp.get("script") or ""),
                                  self.repo_root, taken, runner, model)
        runs = [] if verdict.blocked else workshop.sandbox(bp.get("script") or "", bp["runtime"], bp.get("mocks") or [])
        return verdict, runs

    def _on_blueprint(self, interview: dict, result: blueprint.Result, verdict: fastpath.Verdict | None,
                      runs: list[workshop.Run]) -> None:
        if isinstance(self.screen, BuildProgress):
            self.screen.dismiss(None)
        if not result.ok or verdict is None:
            def on_failed(action: str | None) -> None:
                if action == "retry":
                    self.action_build_scratch(interview)
            self.push_screen(BuildFailed(result), on_failed)
            return
        bp = result.blueprint

        def done(choice: tuple[str, object] | None) -> None:
            if choice is None:
                fastpath.log(self.repo_root, verdict, "cancelled")
                return
            action, value = choice
            if action == "reject":
                fastpath.log(self.repo_root, verdict, "cancelled")
                if interview.get("history"):                 # back to the conversation with the Builder
                    self.action_build_scratch(previous=interview, history=interview["history"], rejected=bp)
                else:
                    self.push_screen(TextPrompt("✗ What should the Builder change?"),
                                     lambda note: note and self.start_blueprint(interview, note, bp))
                return
            final = dict(value)
            fastpath.log(self.repo_root, verdict, "overridden" if verdict.objections else "approved")
            self.raise_blueprint(final)

        self.push_screen(BlueprintReview(bp, verdict, runs, self.check_blueprint, result.cost_usd), done)

    def raise_blueprint(self, bp: dict) -> bool:
        """An approved blueprint: its script and blueprint go into the camp's git with the building,
        then the roads it asked for. True when it was raised at once (no ghost to place)."""
        def before() -> None:
            workshop.save_script(self.repo_root, bp["id"], bp["runtime"], bp["script"])
            workshop.save_blueprint(self.repo_root, bp["id"], bp)

        def after() -> None:
            for item in bp.get("inputs") or []:
                source, _, event = str(item).partition(":")
                if source and event:
                    self.add_road(bp["id"], source, event, None)

        return self.place_and_raise(blueprint.to_spec(bp), before=before, after=after)

    def place_and_raise(self, spec: dict, before: Callable[[], Any] | None = None,
                        after: Callable[[], Any] | None = None) -> bool:
        """The last step of a build: its ghost walks the town — Enter or a click
        raises it there, Esc builds nothing. Without a town on screen it is raised at once.
        True when it was raised at once."""
        label = f"{spec.get('icon', '')} {spec.get('title', '')}".strip()
        sil = silhouettes.styled(silhouettes.of(spec), self.desktop.plain)
        size = footprint(sil, silhouettes.label(len(self.desktop.huts) + 1, label, sil.width),
                         len(catalog.quick_actions_of(spec)))

        def raise_at(hut: list[float] | None) -> bool:
            if before is not None:
                before()
            ok = self.raise_spec(spec, hut=hut)
            if ok and after is not None:
                after()
            return ok

        def done(frac: tuple[float, float] | None) -> None:
            if frac is None:
                self.notify(f"{label}: nothing was built", title="👻 Build cancelled")
                return
            raise_at(list(frac))

        if self.desktop.start_ghost(label, size, done):
            self.notify("arrows or the mouse move it · Enter or a click builds · Esc cancels",
                        title=f"👻 Place {label}")
            return False
        return raise_at(None)

    def raise_spec(self, spec: dict, hut: list[float] | None = None, quiet: bool = False) -> bool:
        """Save a checked spec and raise its building in the active orkspace (at `hut`, the
        fractions of the town where its ghost settled). `quiet`: one of many (a town plan) — no toast,
        no focus, no commit of its own."""
        spec = catalog.migrate(spec)
        existing_ids = self._taken_building_ids()
        problems = masonry.save_spec(self.repo_root, spec, existing_ids=existing_ids)
        if problems:
            self.notify("\n".join(problems), title="Save failed", severity="error")
            return False
        scroll.add_custom_building(self.scroll, spec)
        placed = self.scroll.building(spec["id"])
        if hut is not None and placed is not None:
            placed.hut = hut
        building = custom_building(spec)
        self.buildings.append(building)
        self.custom_specs[spec["id"]] = spec
        pipes.set_typed(spec["id"], catalog.events_of(spec))

        active_ork = self.scroll.active_orkspace
        next_number = len(active_ork.buildings) if active_ork else 1
        new_win = Window(view_for(spec), window_id=spec["id"], title=building.label, number=next_number)
        self.desktop.add_window(new_win)
        self.desktop.save()

        active_ork = self.scroll.active_orkspace
        ork_name = active_ork.name if active_ork else self.scroll.active_orkspace_id
        try:
            chronicles.record(self.repo_root, self.scroll, spec["id"], "building_raised", orkspace=ork_name)
        except OSError:
            pass
        self.refresh_roster()
        if quiet:
            return True
        self.notify(f"🏗️ {spec['title']} raised", title="Build")
        self.set_focus_state("building", building_id=spec["id"])
        self.checkpoint("create", spec["id"], f"raise {spec.get('type') or 'custom'} {spec['title']}")
        return True

    # -- build wizard ----------------------------------------------------------------------

    def action_build_wizard(self) -> None:
        def done(choice: tuple[str | None, str] | None) -> None:
            if choice:
                self.start_wizard_build(*choice)

        self.push_screen(BuildWizard(), done)

    def start_wizard_build(self, type_id: str | None, request: str) -> None:
        self.push_screen(BuildProgress())

        def _worker() -> None:
            runner = BUILD_RUNNER or builders.claude_runner
            result = builders.propose(request, self.repo_root, type_id, self._taken_building_ids(), runner)
            self.call_from_thread(self._on_wizard_proposal, type_id, request, result)

        self.run_worker(_worker, thread=True, name="foreman_build")

    def _on_wizard_proposal(self, type_id: str | None, request: str, result: builders.BuildResult) -> None:
        self._log_build_request(request, result)
        if isinstance(self.screen, BuildProgress):
            self.screen.dismiss(None)
        if not (result.ok and result.spec):
            def on_failed(action: str | None) -> None:
                if action == "retry":
                    self.action_build_wizard()
            self.push_screen(BuildFailed(result), on_failed)
            return
        spec = result.spec
        if (spec.get("type") or catalog.DEFAULT_TYPE) == catalog.DEFAULT_TYPE:
            # Mason & Artisan's panes: their own preview
            self.push_screen(BuildPreview(spec, result), lambda ok: ok and self.review_and_raise(spec))
            return

        def check(s: dict) -> list[str]:
            return masonry.validate_spec(s, self.repo_root, self._taken_building_ids())

        def done(final: dict | None) -> None:
            if final:
                self.review_and_raise(final)

        self.push_screen(BuildReview(spec, len(result.attempts), result.cost_usd, check), done)

    # -- Halt All ----------------------------------------------------------------------------

    def action_halt(self, source: str = "") -> None:
        """Emergency freeze: interrupt every running agent session; the TUI stays open."""
        halted = self.chat.interrupt_all()
        for worker in self.workers:
            if worker.group.startswith("orkcraft-agent"):
                worker.cancel()
        hud = self._hud
        hud.set_halt(f"HALTED — {halted} stopped")
        self.notify(f"🛑 Halt All: {halted} running session{'s' if halted != 1 else ''} interrupted",
                    title="Emergency freeze", severity="warning")
        self.set_timer(HALT_RESET_S, lambda: hud.set_halt("READY"))

    # -- sessions ------------------------------------------------------------------------------------

    def open_chat(self, node_id: str | None = None) -> None:
        """Show the War Tent with the node's latest session (or a new one)."""
        node_id = node_id or self.selected_node
        w = self._sessions_window()
        if w is not None:
            self.desktop.focus_window(w)
        if node_id:
            self.chat.open_for_node(node_id)

    def open_session(self, session) -> None:
        w = self._sessions_window()
        if w is not None:
            self.desktop.focus_window(w)
        self.chat.open_session(session)

    def action_open_chat(self) -> None:
        self.open_chat()

    def on_unmount(self) -> None:
        self.roads.stop()
        try:
            self.desktop.save()
        except Exception:
            pass

    # -- graph actions ---------------------------------------------------------------------------------

    def action_toggle_commit(self) -> None:
        self.config.auto_commit = not self.config.auto_commit
        self.refresh_roster()
        status_str = "ENABLED" if self.config.auto_commit else "DISABLED"
        self.notify(f"§10 per-action git commits are now {status_str}", title="Auto-Commit Setting")

    def action_refresh_graph(self) -> None:
        for w in self.desktop.windows:
            for view in w.children:
                refresh = getattr(view, "refresh_view", None)
                if refresh is not None:
                    try:
                        refresh()
                    except Exception as e:  # one broken source must not block the others
                        self.notify(f"{w.window_title}: {e}", severity="error")
        self.refresh_roster()
        self.notify("Data reloaded from disk", title="Refresh")

    def action_show_help(self) -> None:
        self.push_screen(KeysCheatSheet())

    def action_graceful_quit(self) -> None:
        chat = getattr(self, "chat", None)
        terminals = getattr(chat, "terminals", {}) if chat else {}
        running = [t for t in terminals.values() if getattr(t, "running", False)]
        if not running:
            try:
                self.desktop.save()
            except Exception:
                pass
            self.exit(0)
            return

        def done(confirmed: bool | None) -> None:
            if confirmed:
                try:
                    self.desktop.save()
                except Exception:
                    pass
                chat_obj = getattr(self, "chat", None)
                terms = getattr(chat_obj, "terminals", {}) if chat_obj else {}
                for t in terms.values():
                    if getattr(t, "running", False):
                        try:
                            t.stop()
                        except Exception:
                            pass
                self.exit(0)

        self.push_screen(QuitConfirm(len(running)), done)

    def action_quit(self) -> None:
        self.action_graceful_quit()
