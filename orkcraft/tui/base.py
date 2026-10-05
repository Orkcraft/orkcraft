"""What every part of the TUI app shares: its timings, viewport widths, the Command Card's keys
per focus state, and the focus state itself."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

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


def delegate(holder: str, name: str) -> Any:
    """An attribute of the app that lives on one of its parts (`self.core.scroll` read and set as
    `self.scroll`): the parts own the state, the old names keep working."""
    return property(lambda self: getattr(getattr(self, holder), name),
                    lambda self, value: setattr(getattr(self, holder), name, value))
