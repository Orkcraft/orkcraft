"""The lower RTS console: War Map (orkspaces), Clan Roster (contextual garrison), Command Card.

One module per part: `cards` (what Info says, as text), `warmap`, `info`, `garrison` (the Clan
Roster and the Inventory) and `command_card`; the GUI mirrors them in `gui/info.py` and
`gui/console.py`. Every name stays importable from here."""
from __future__ import annotations

from typing import TYPE_CHECKING

from textual import events
from textual.containers import Horizontal
from textual.app import ComposeResult
from textual.css.query import NoMatches
from textual.message import Message
from textual.widgets import OptionList

from orkcraft.screens.console.cards import (
    STATUS_DISPLAY, _append_tier, _spend_of, building_about, building_listens, building_runs, orc_about,
    orc_info, orc_key, orc_runs, road_card, unit_details,
)
from orkcraft.screens.console.command_card import (
    BUILDING_ACTIONS, NEUTRAL_ACTIONS, QUICK_KEYS, RESIDENT_ACTIONS, ROAD_ACTIONS, UNIT_ACTIONS, CommandCard,
)
from orkcraft.screens.console.garrison import INVENTORY_W, ClanRoster
from orkcraft.screens.console.info import UnitInfo
from orkcraft.screens.console.warmap import WarMap, orkspace_has_alert

__all__ = [
    "BUILDING_ACTIONS",
    "CONSOLE_DEFAULT_PCT",
    "CONSOLE_MAX_PCT",
    "CONSOLE_MIN_PCT",
    "INVENTORY_W",
    "NEUTRAL_ACTIONS",
    "QUICK_KEYS",
    "RESIDENT_ACTIONS",
    "ROAD_ACTIONS",
    "STATUS_DISPLAY",
    "UNIT_ACTIONS",
    "ClanRoster",
    "CommandCard",
    "Console",
    "UnitInfo",
    "WarMap",
    "_append_tier",
    "_spend_of",
    "building_about",
    "building_listens",
    "building_runs",
    "orc_about",
    "orc_info",
    "orc_key",
    "orc_runs",
    "orkspace_has_alert",
    "road_card",
    "unit_details",
]

if TYPE_CHECKING:
    from orkcraft.app import FocusState
    from orkcraft.realm.roster import Roster


CONSOLE_DEFAULT_PCT = 15   # of the screen height (33 → 22 → 15 %: the operator asked for more room for the town)
CONSOLE_MIN_PCT, CONSOLE_MAX_PCT = 10, 60


class Console(Horizontal):
    """RTS console at the bottom of the screen (33/33/33 columns). Its height is a share of the
    screen: drag the top edge or press alt+- / alt+=; the app keeps it in the Town Scroll."""

    class Resized(Message):
        """The operator changed the console height (end of a drag, or a key)."""
        def __init__(self, pct: int) -> None:
            super().__init__()
            self.pct = pct

    height_pct = CONSOLE_DEFAULT_PCT
    _drag_start: int | None = None

    def on_mount(self) -> None:
        self.border_title = "⇕"

    def set_height_pct(self, pct: int) -> int:
        pct = max(CONSOLE_MIN_PCT, min(CONSOLE_MAX_PCT, int(pct)))
        self.height_pct = pct
        if self.has_class("-floating"):
            layout = getattr(self.app, "layout_console", None)   # the town places it in cells
            if layout is not None:
                layout()
        else:
            self.styles.height = f"{pct}%"
        return pct

    def on_mouse_down(self, event: events.MouseDown) -> None:
        if event.button == 1 and event.screen_y == self.region.y:   # the top edge is the grip
            self._drag_start = event.screen_y
            self.add_class("-dragging")
            self.capture_mouse()
            event.stop()

    def on_mouse_move(self, event: events.MouseMove) -> None:
        if self._drag_start is None:
            return
        # A % height is a share of the screen minus the HUD and the Footer (one row each); the
        # console spans from the pointer row down to its current bottom (the Footer's row).
        avail = max(self.app.size.height - 2, 1)
        rows = self.region.bottom - event.screen_y
        self.set_height_pct(round(rows * 100 / avail))
        event.stop()

    def on_mouse_up(self, event: events.MouseUp) -> None:
        if self._drag_start is None:
            return
        self._drag_start = None
        self.remove_class("-dragging")
        self.release_mouse()
        self.post_message(self.Resized(self.height_pct))
        event.stop()

    DEFAULT_CSS = """
    Console {
        height: 22%;
        min-height: 6;
        border-top: heavy $accent 45%;
        border-title-align: center;
        border-title-color: $accent 70%;
        background: $background;
    }
    Console.-dragging {
        border-top: heavy $warning;
    }
    /* Town view: a layer over the map's bottom edge, out of the layout, so the town keeps
       the whole height. Calm (nothing selected): the War Map alone. */
    Console.-floating {
        position: absolute;
        layer: overlay;
        min-height: 3;
    }
    Console.-floating.-calm #clan-roster, Console.-floating.-calm #unit-info, Console.-floating.-calm #command-card {
        display: none;
    }
    Console.-floating.-calm #warmap {
        width: 100%;
        max-width: 100%;
    }
    .console-col {
        height: 100%;
    }
    /* War Map (36) · Info (the rest) · garrison / inventory (22) · Command Card. */
    #warmap {
        width: 36;
    }
    #clan-roster {
        width: 22;
        border-left: vkey $accent 60%;
    }
    #unit-info {
        width: 1fr;
        border-left: vkey $accent 60%;
    }
    #info-body {
        height: 1fr;
        padding: 0 1;
    }
    #info-building {
        height: 1fr;
        padding: 0 1;
        display: none;
    }
    .ib-row { height: 1; }
    #ib-name, #ib-runs, #ib-listens { width: 1fr; }
    #ib-about, #io-about { height: auto; max-height: 3; color: $text; }
    #info-orc {
        height: 1fr;
        padding: 0 1;
        display: none;
    }
    #io-name, #io-runs { width: 1fr; }
    .ib-button { width: auto; margin-left: 1; background: $surface; text-style: bold; }
    .ib-button:hover { background: $warning; color: $background; }
    #ib-like, #io-like { background: $success 60%; }
    #ib-dislike, #io-dislike { background: $error 60%; }
    #command-card {
        width: 32;
        border-left: vkey $accent 60%;
    }
    #command-card.-empty { display: none; }
    .console-title {
        height: 1;
        text-style: bold;
        color: $accent;
        padding: 0 1;
        background: $surface;
    }
    .console-footer {
        dock: bottom;
        height: 1;
        color: $text-muted;
        padding: 0 1;
        background: $surface;
    }
    #warmap-list {
        height: 1fr;
        background: transparent;
        border: none;
        padding: 0;
    }
    #warmap-content {
        height: 1fr;
        padding: 1 1;
        display: none;
    }
    #roster-list {
        height: 1fr;
        background: transparent;
        border: none;
        padding: 0;
    }
    #roster-card {
        height: 1fr;
        padding: 0 1;
        display: none;
    }
    #command-actions {
        height: 1fr;
        background: transparent;
        border: none;
        padding: 0;
    }
    """

    def compose(self) -> ComposeResult:
        yield WarMap(id="warmap", classes="console-col")
        yield UnitInfo(id="unit-info", classes="console-col")       # the wide Info sits beside the map
        yield ClanRoster(id="clan-roster", classes="console-col")
        yield CommandCard(id="command-card", classes="console-col")

    def refresh_state(self, focus_state: FocusState, roster: Roster) -> None:
        # The roster timer can fire while the app shuts down and the columns are already gone.
        if not self.is_attached or len(self.children) < 4:
            return
        biome = getattr(self.app.desktop, "biome", "forest")
        try:
            self.query_one(WarMap).update_content(focus_state, roster, biome)
            self.query_one(ClanRoster).update_content(focus_state, roster)
            self.query_one(UnitInfo).update_content(focus_state, roster)
            self.query_one(CommandCard).update_content(focus_state, roster)
        except NoMatches:
            # Shutdown unmounts the columns' children before the columns themselves.
            return

    def focus_roster(self) -> None:
        if self.has_class("-calm"):        # the calm town shows the War Map only
            self.query_one(WarMap).query_one("#warmap-list", OptionList).focus()
            return
        self.query_one(ClanRoster).query_one("#roster-list", OptionList).focus()
