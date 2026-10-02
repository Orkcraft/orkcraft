"""Where roads run on the canvas: gates on window frames and orthogonal paths between them.
Pure geometry, no Textual (T1098 stage 4 draws it).

    paths = plan({"forge": Geom(0, 0, 40, 12), "scrying": Geom(60, 0, 40, 12)},
                 [("forge-task", "forge", "scrying")], width=120, height=40)
    p = paths["forge-task"]
    p.exit, p.entry          # Gate: the frame cell, the side it faces
    p.cells                  # the path, from just outside the exit gate to just outside the entry gate
    p.covered                # cells of the path under some window (drawn only when the road is selected)
    p.glyphs                 # (x, y, box char) for every cell of the path
    hit(paths, x, y)         # the road under a cell (path or gate), for clicks

Gates sit on the side of the source frame that faces the target (and vice versa); several gates
on one side are spread evenly. Paths are A* on the cell grid: a step costs 1 on free terrain and
`WINDOW_COST` under a window, and each turn costs `TURN_COST`. So roads prefer the gaps between
windows and cross windows only when no gap exists. `plan` is deterministic: recompute it only
when the layout or the roads change.
"""
from __future__ import annotations

import heapq
from dataclasses import dataclass, field

from orkcraft.wm.geometry import Geom

WINDOW_COST = 40
TURN_COST = 3
SIDES = ("left", "right", "top", "bottom")
_STEP = {"left": (-1, 0), "right": (1, 0), "top": (0, -1), "bottom": (0, 1)}
_GLYPH = {
    frozenset({"left", "right"}): "─", frozenset({"top", "bottom"}): "│",
    frozenset({"right", "bottom"}): "┌", frozenset({"left", "bottom"}): "┐",
    frozenset({"right", "top"}): "└", frozenset({"left", "top"}): "┘",
}
Cell = tuple[int, int]


@dataclass(frozen=True)
class Gate:
    road_id: str
    building_id: str
    role: str        # exit | entry
    side: str        # left | right | top | bottom
    x: int
    y: int

    @property
    def outside(self) -> Cell:
        dx, dy = _STEP[self.side]
        return self.x + dx, self.y + dy


@dataclass
class RoadPath:
    road_id: str
    source: str
    target: str
    exit: Gate
    entry: Gate
    cells: list[Cell] = field(default_factory=list)
    covered: frozenset[Cell] = frozenset()
    glyphs: list[tuple[int, int, str]] = field(default_factory=list)


def facing_side(a: Geom, b: Geom) -> str:
    """The side of `a` that faces `b`."""
    if b.x >= a.x + a.w:
        horizontal = "right"
    elif b.x + b.w <= a.x:
        horizontal = "left"
    else:
        horizontal = ""
    if b.y >= a.y + a.h:
        vertical = "bottom"
    elif b.y + b.h <= a.y:
        vertical = "top"
    else:
        vertical = ""
    if horizontal and vertical:   # diagonal: the axis with the larger gap
        gap_x = (b.x - (a.x + a.w)) if horizontal == "right" else (a.x - (b.x + b.w))
        gap_y = (b.y - (a.y + a.h)) if vertical == "bottom" else (a.y - (b.y + b.h))
        return horizontal if gap_x * 2 >= gap_y * 5 else vertical   # a cell is ~2.5× taller than wide
    if horizontal or vertical:
        return horizontal or vertical
    acx, acy, bcx, bcy = a.x + a.w / 2, a.y + a.h / 2, b.x + b.w / 2, b.y + b.h / 2
    if abs(bcx - acx) * 2 >= abs(bcy - acy) * 5:
        return "right" if bcx >= acx else "left"
    return "bottom" if bcy >= acy else "top"


def _gate_cell(g: Geom, side: str, i: int, k: int) -> Cell:
    if side in ("left", "right"):
        span = max(g.h - 2, 1)
        y = g.y + 1 + (span * (i + 1)) // (k + 1)
        return (g.x if side == "left" else g.x + g.w - 1), min(y, g.y + g.h - 2 if g.h > 2 else g.y)
    span = max(g.w - 2, 1)
    x = g.x + 1 + (span * (i + 1)) // (k + 1)
    return min(x, g.x + g.w - 2 if g.w > 2 else g.x), (g.y if side == "top" else g.y + g.h - 1)


def gates(geoms: dict[str, Geom], roads: list[tuple[str, str, str]],
          anchors: dict[str, Geom] | None = None) -> dict[str, tuple[Gate, Gate]]:
    """road id → (exit gate on the source, entry gate on the target), spread along each side.
    `anchors` (optional) is the part of a geom the gates sit on, e.g. a hut's silhouette."""
    anchors = anchors or {}
    slots: dict[tuple[str, str], list[tuple[str, str, float]]] = {}
    for road_id, src, dst in roads:
        if src not in geoms or dst not in geoms:
            continue
        a, b = anchors.get(src, geoms[src]), anchors.get(dst, geoms[dst])
        for bid, role, me, other in ((src, "exit", a, b), (dst, "entry", b, a)):
            side = facing_side(me, other)
            # order gates along the side by where the other end lies, so roads do not cross at the frame
            key = other.y + other.h / 2 if side in ("left", "right") else other.x + other.w / 2
            slots.setdefault((bid, side), []).append((road_id, role, key))
    out: dict[str, dict[str, Gate]] = {}
    for (bid, side), items in slots.items():
        items.sort(key=lambda t: (t[2], t[0], t[1]))
        for i, (road_id, role, _) in enumerate(items):
            x, y = _gate_cell(anchors.get(bid, geoms[bid]), side, i, len(items))
            out.setdefault(road_id, {})[role] = Gate(road_id, bid, role, side, x, y)
    return {rid: (g["exit"], g["entry"]) for rid, g in out.items() if "exit" in g and "entry" in g}


def _under(geoms: dict[str, Geom], width: int, height: int) -> list[list[bool]]:
    grid = [[False] * width for _ in range(height)]
    for g in geoms.values():
        for y in range(max(g.y, 0), min(g.y + g.h, height)):
            row = grid[y]
            for x in range(max(g.x, 0), min(g.x + g.w, width)):
                row[x] = True
    return grid


def _clamp(c: Cell, width: int, height: int) -> Cell:
    return min(max(c[0], 0), width - 1), min(max(c[1], 0), height - 1)


def route(start: Cell, end: Cell, under: list[list[bool]], width: int, height: int) -> list[Cell]:
    """Cheapest orthogonal path from `start` to `end` (both included)."""
    if start == end:
        return [start]
    sx, sy = start
    ex, ey = end
    best: dict[tuple[int, int, int], int] = {}
    came: dict[tuple[int, int, int], tuple[int, int, int] | None] = {}
    heap: list[tuple[int, int, int, int, int]] = []
    dirs = ((1, 0), (-1, 0), (0, 1), (0, -1))
    for d in range(4):
        best[(sx, sy, d)] = 0
        came[(sx, sy, d)] = None
        heapq.heappush(heap, (abs(ex - sx) + abs(ey - sy), 0, sx, sy, d))
    while heap:
        _, cost, x, y, d = heapq.heappop(heap)
        if cost > best.get((x, y, d), 1 << 60):
            continue
        if (x, y) == end:
            path, node = [], (x, y, d)
            while node is not None:
                path.append((node[0], node[1]))
                node = came[node]
            path.reverse()
            out = [path[0]]
            for c in path[1:]:
                if c != out[-1]:
                    out.append(c)
            return out
        for nd, (dx, dy) in enumerate(dirs):
            nx, ny = x + dx, y + dy
            if not (0 <= nx < width and 0 <= ny < height):
                continue
            step = (WINDOW_COST if under[ny][nx] else 1) + (TURN_COST if nd != d else 0)
            nc = cost + step
            key = (nx, ny, nd)
            if nc < best.get(key, 1 << 60):
                best[key] = nc
                came[key] = (x, y, d)
                heapq.heappush(heap, (nc + abs(ex - nx) + abs(ey - ny), nc, nx, ny, nd))
    return [start, end]


def _dir(a: Cell, b: Cell) -> str:
    dx, dy = b[0] - a[0], b[1] - a[1]
    return "right" if dx > 0 else "left" if dx < 0 else "bottom" if dy > 0 else "top"


_OPPOSITE = {"left": "right", "right": "left", "top": "bottom", "bottom": "top"}


def glyphs(cells: list[Cell], exit_side: str, entry_side: str) -> list[tuple[int, int, str]]:
    """Box-drawing characters along a path; the ends point at their gates."""
    out = []
    for i, c in enumerate(cells):
        ends = set()
        ends.add(_dir(c, cells[i - 1]) if i > 0 else _OPPOSITE[exit_side])
        ends.add(_dir(c, cells[i + 1]) if i < len(cells) - 1 else _OPPOSITE[entry_side])
        if len(ends) == 1:           # a one-cell path between facing gates
            ends.add(_OPPOSITE[next(iter(ends))])
        out.append((c[0], c[1], _GLYPH.get(frozenset(ends), "┼")))
    return out


def plan(geoms: dict[str, Geom], roads: list[tuple[str, str, str]], width: int, height: int,
         anchors: dict[str, Geom] | None = None) -> dict[str, RoadPath]:
    """Every drawable road (both ends on this canvas): gates, path, covered cells and glyphs."""
    if width <= 0 or height <= 0:
        return {}
    under = _under(geoms, width, height)
    out = {}
    all_gates = gates(geoms, roads, anchors)
    for road_id, src, dst in roads:
        if road_id not in all_gates:
            continue
        exit_gate, entry_gate = all_gates[road_id]
        start = _clamp(exit_gate.outside, width, height)
        end = _clamp(entry_gate.outside, width, height)
        cells = route(start, end, under, width, height)
        covered = frozenset(c for c in cells if under[c[1]][c[0]])
        out[road_id] = RoadPath(road_id, src, dst, exit_gate, entry_gate, cells, covered,
                                glyphs(cells, exit_gate.side, entry_gate.side))
    return out


def hit(paths: dict[str, RoadPath], x: int, y: int, include_covered: bool = False) -> str | None:
    """The road whose gate or visible path cell is at (x, y); gates win over paths."""
    for p in paths.values():
        if (p.exit.x, p.exit.y) == (x, y) or (p.entry.x, p.entry.y) == (x, y):
            return p.road_id
    for p in paths.values():
        if (x, y) in p.cells and (include_covered or (x, y) not in p.covered):
            return p.road_id
    return None
