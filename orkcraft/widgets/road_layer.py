"""What of a road is drawn over the windows: gates on the frames and the selected road.

The gap cells of roads are drawn by the Terrain; everything here lives on the desktop's `roads`
layer, above the windows, as small absolutely positioned widgets — never a full-screen overlay,
so the windows stay visible and clickable.
"""
from __future__ import annotations

from rich.text import Text
from textual import events
from textual.message import Message
from textual.widgets import Static

from orkcraft.scroll import road_key, split_key  # noqa: F401 (the canvas's keys are the scroll's)

# Roads are dirt paths: shades of brown, lighter the more attention they get (faint → selected).
ROAD_FAINT = "#5c4326"
ROAD_BRIGHT = "#a0703c"
ROAD_SELECTED = "#d9a066"
EXIT_GLYPH = {"right": "▶", "left": "◀", "top": "▲", "bottom": "▼"}
ENTRY_GLYPH = "●"


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
        super().__init__(key, Text(glyph, style=style), x, y, 1, 1, classes="road-gate")
        self.glyph = glyph


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
