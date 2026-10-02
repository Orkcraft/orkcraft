"""Pure window geometry: snap slots, tiling, clamping. No Textual imports."""
from __future__ import annotations

import math
from dataclasses import dataclass

MIN_W = 16
MIN_H = 4

# A fractional rect (fx, fy, fw, fh) in 0..1 of the desktop. Windows that sit in a
# fractional slot are re-laid out when the terminal is resized; free-floating
# windows (frac=None) keep their cell geometry and are only clamped.
Frac = tuple[float, float, float, float]

SNAP_SLOTS: dict[str, Frac] = {
    "left": (0.0, 0.0, 0.5, 1.0),
    "right": (0.5, 0.0, 0.5, 1.0),
    "top": (0.0, 0.0, 1.0, 0.5),
    "bottom": (0.0, 0.5, 1.0, 0.5),
    "top-left": (0.0, 0.0, 0.5, 0.5),
    "top-right": (0.5, 0.0, 0.5, 0.5),
    "bottom-left": (0.0, 0.5, 0.5, 0.5),
    "bottom-right": (0.5, 0.5, 0.5, 0.5),
    "max": (0.0, 0.0, 1.0, 1.0),
    "center": (0.15, 0.1, 0.7, 0.8),
}


@dataclass(frozen=True)
class Geom:
    """Window rectangle in desktop cells."""
    x: int
    y: int
    w: int
    h: int

    def to_dict(self) -> dict[str, int]:
        return {"x": self.x, "y": self.y, "w": self.w, "h": self.h}


def frac_to_geom(frac: Frac, width: int, height: int) -> Geom:
    """Convert a fractional rect to cells; neighbouring slots share edges exactly."""
    fx, fy, fw, fh = frac
    x1, y1 = round(fx * width), round(fy * height)
    x2, y2 = round((fx + fw) * width), round((fy + fh) * height)
    return clamp(Geom(x1, y1, x2 - x1, y2 - y1), width, height)


def clamp(g: Geom, width: int, height: int) -> Geom:
    """Keep a window inside the desktop and not smaller than the minimum size."""
    w = max(min(g.w, width), min(MIN_W, width))
    h = max(min(g.h, height), min(MIN_H, height))
    x = min(max(g.x, 0), max(width - w, 0))
    y = min(max(g.y, 0), max(height - h, 0))
    return Geom(x, y, w, h)


def move(g: Geom, dx: int, dy: int, width: int, height: int) -> Geom:
    return clamp(Geom(g.x + dx, g.y + dy, g.w, g.h), width, height)


def resize(g: Geom, dw: int, dh: int, width: int, height: int) -> Geom:
    """Grow/shrink from the bottom-right corner; the top-left corner stays put."""
    w = min(max(g.w + dw, MIN_W), max(width - g.x, MIN_W))
    h = min(max(g.h + dh, MIN_H), max(height - g.y, MIN_H))
    return clamp(Geom(g.x, g.y, w, h), width, height)


def tile_fracs(n: int) -> list[Frac]:
    """Grid tiling for n windows: ceil(sqrt(n)) columns, the last row stretches."""
    if n <= 0:
        return []
    cols = math.ceil(math.sqrt(n))
    rows = math.ceil(n / cols)
    fracs: list[Frac] = []
    for i in range(n):
        r, c = divmod(i, cols)
        in_row = cols if r < rows - 1 else n - cols * (rows - 1)
        fracs.append((c / in_row, r / rows, 1 / in_row, 1 / rows))
    return fracs


def default_fracs() -> dict[str, Frac | None]:
    """Starting base (tiles): Artifacts on the left, the Town Hall on the right."""
    return {
        "loot": (0.0, 0.0, 0.5, 1.0),
        "town_hall": (0.5, 0.0, 0.5, 1.0),
        "systems": None,
    }


# -- town view: huts on the map, one building expanded over it -----------------------------

TOWN_SLOT: Frac = (0.1, 0.06, 0.8, 0.88)   # where the expanded building opens
HUT_GAP_X = 4                               # room for a road between neighbouring huts
HUT_GAP_Y = 2


def hut_shelves(width: int, height: int, sizes: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Spots for huts of different sizes, in order: rows are filled left to right (a row ends when
    the next hut would not fit with its gap), every row is spread over the width and the rows over
    the height, a small hut sits in the middle of its row. Parallel to `sizes`."""
    rows: list[list[int]] = [[]]
    used = [0]
    for i, (w, _) in enumerate(sizes):
        need = w + (HUT_GAP_X if rows[-1] else 0)
        if rows[-1] and used[-1] + need > width:
            rows.append([])
            used.append(0)
            need = w
        rows[-1].append(i)
        used[-1] += need
    rows = [r for r in rows if r]
    heights = [max(sizes[i][1] for i in r) for r in rows]
    gap_y = max(height - sum(heights), 0) / max(len(rows), 1)
    spots: list[tuple[int, int]] = [(0, 0)] * len(sizes)
    y = gap_y / 2
    for r, rh in zip(rows, heights):
        gap_x = max(width - sum(sizes[i][0] for i in r), 0) / len(r)
        x = gap_x / 2
        for i in r:
            w, h = sizes[i]
            spots[i] = (min(max(round(x), 0), max(width - w, 0)),
                        min(max(round(y + (rh - h) / 2), 0), max(height - h, 0)))
            x += w + gap_x
        y += rh + gap_y
    return spots


def first_free(width: int, height: int, w: int, h: int, taken: list[Geom], step: int = 2) -> Geom | None:
    """The first spot (reading order) where a w×h hut fits without touching any of `taken`."""
    for y in range(0, max(height - h, 0) + 1, step):
        for x in range(0, max(width - w, 0) + 1, step):
            g = Geom(x, y, w, h)
            if not any(overlaps(g, t, 1, 0) for t in taken):
                return g
    return None


def hut_to_frac(x: int, y: int, width: int, height: int, w: int, h: int) -> tuple[float, float]:
    """A hut spot as fractions of the room it can move in (stays inside on resize)."""
    fx = x / (width - w) if width > w else 0.0
    fy = y / (height - h) if height > h else 0.0
    return round(min(max(fx, 0.0), 1.0), 4), round(min(max(fy, 0.0), 1.0), 4)


def hut_from_frac(fx: float, fy: float, width: int, height: int, w: int, h: int) -> Geom:
    return Geom(round(fx * max(width - w, 0)), round(fy * max(height - h, 0)), w, h)


def overlaps(a: Geom, b: Geom, gap_x: int = 0, gap_y: int = 0) -> bool:
    return (a.x < b.x + b.w + gap_x and b.x < a.x + a.w + gap_x
            and a.y < b.y + b.h + gap_y and b.y < a.y + a.h + gap_y)
