"""What of a road is drawn over the windows: gates on the frames and the selected road.

The gap cells of roads are drawn by the Terrain; everything here lives on the desktop's `roads`
layer, above the windows, as small absolutely positioned widgets — never a full-screen overlay,
so the windows stay visible and clickable.
"""
from __future__ import annotations

from rich.cells import cell_len
from rich.text import Text
from textual import events
from textual.message import Message
from textual.widgets import Static

# Roads are dirt paths: shades of brown, lighter the more attention they get (faint → selected).
ROAD_FAINT = "#5c4326"
ROAD_BRIGHT = "#a0703c"
ROAD_SELECTED = "#d9a066"
EXIT_GLYPH = {"right": "▶", "left": "◀", "top": "▲", "bottom": "▼"}
EXIT_EMOJI = {"right": "⏩", "left": "⏪", "top": "⏫", "bottom": "⏬"}     # the immersion mode: two cells wide
ENTRY_GLYPH = "●"


def road_key(target_id: str, road_id: str) -> str:
    """Road ids are unique per receiver; the canvas needs one key for all roads."""
    return f"{target_id}:{road_id}"


def split_key(key: str) -> tuple[str, str]:
    target, _, road = key.partition(":")
    return target, road


class RoadClicked(Message):
    """A gate, a selected road's run or a road's gap cell was clicked."""

    def __init__(self, key: str) -> None:
        super().__init__()
        self.key = key


class _RoadPiece(Static):
    DEFAULT_CSS = """
    _RoadPiece {
        layer: roads;
        position: absolute;
        width: auto;
        height: auto;
        padding: 0;
    }
    """

    def __init__(self, key: str, text: Text, x: int, y: int, w: int, h: int, *, classes: str = "") -> None:
        super().__init__(text, markup=False, classes=classes)
        self.key = key
        self.styles.offset = (x, y)
        self.styles.width = w
        self.styles.height = h

    def on_click(self, event: events.Click) -> None:
        event.stop()
        self.post_message(RoadClicked(self.key))


class RoadGate(_RoadPiece):
    """One gate: an arrow out of the source frame, a dot on the target frame."""

    def __init__(self, key: str, glyph: str, x: int, y: int, style: str) -> None:
        w = cell_len(glyph)
        super().__init__(key, Text(glyph, style=style), x, y, w, 1, classes="road-gate")
        self.glyph = glyph


def exit_gate(key: str, side: str, x: int, y: int, style: str, plain: bool, edges: set[int] = frozenset()) -> RoadGate:
    """The arrow out of a source building: ▶ in the plain mode; ⏩ (two cells) in the immersion mode.

    ⏩ covers the gate cell and the one the road goes on (⏪: the one before). The terminal cannot draw
    a wide character cut by the edge of another widget (`edges`: x where one starts or ends on this
    row), so it shifts a cell to stay whole, and falls back to ▶ when neither place is."""
    if not plain:
        for at in ((x - 1, x) if side == "left" else (x, x - 1)):
            if at >= 0 and at + 1 not in edges:
                return RoadGate(key, EXIT_EMOJI[side], at, y, style)
    return RoadGate(key, EXIT_GLYPH[side], x, y, style)


class RoadRun(_RoadPiece):
    """A straight run of the selected road's cells under a window."""

    def __init__(self, key: str, cells: list[tuple[int, int, str]], style: str) -> None:
        xs, ys = [c[0] for c in cells], [c[1] for c in cells]
        horizontal = len(set(ys)) == 1
        chars = "".join(c[2] for c in cells) if horizontal else "\n".join(c[2] for c in cells)
        super().__init__(key, Text(chars, style=style), min(xs), min(ys),
                         len(cells) if horizontal else 1, 1 if horizontal else len(cells), classes="road-run")


class RoadLabel(_RoadPiece):
    def __init__(self, key: str, label: str, x: int, y: int, style: str) -> None:
        super().__init__(key, Text(f" {label} ", style=style), x, y, len(label) + 2, 1, classes="road-label")
        self.label = label


def runs(cells: list[tuple[int, int, str]]) -> list[list[tuple[int, int, str]]]:
    """Consecutive cells in one row or one column, in path order."""
    out: list[list[tuple[int, int, str]]] = []
    for c in cells:
        cur = out[-1] if out else None
        if cur is not None and len(cur) >= 1:
            same_row = all(p[1] == c[1] for p in cur)
            same_col = all(p[0] == c[0] for p in cur)
            adjacent = abs(cur[-1][0] - c[0]) + abs(cur[-1][1] - c[1]) == 1
            if adjacent and (same_row or same_col):
                cur.append(c)
                continue
        out.append([c])
    return out
