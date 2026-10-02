"""Road geometry on the canvas (T1098 stage 4 contract): gates, routing around windows, glyphs, hits."""
from __future__ import annotations

from orkcraft.wm import roadmap as rm
from orkcraft.wm.geometry import Geom


def test_facing_sides():
    a = Geom(0, 0, 40, 10)
    assert rm.facing_side(a, Geom(60, 0, 20, 10)) == "right"
    assert rm.facing_side(a, Geom(0, 20, 40, 10)) == "bottom"
    assert rm.facing_side(Geom(60, 0, 20, 10), a) == "left"
    assert rm.facing_side(a, Geom(45, 30, 20, 5)) == "bottom"      # far below, a little right
    assert rm.facing_side(a, Geom(90, 12, 20, 5)) == "right"       # far right, a little below


def test_straight_road_between_side_by_side_windows():
    geoms = {"forge": Geom(0, 0, 40, 12), "scrying": Geom(60, 0, 40, 12)}
    p = rm.plan(geoms, [("r", "forge", "scrying")], 120, 30)["r"]
    assert (p.exit.side, p.entry.side) == ("right", "left")
    assert p.exit.x == 39 and p.entry.x == 60 and p.exit.y == p.entry.y
    assert p.cells[0] == (40, p.exit.y) and p.cells[-1] == (59, p.entry.y)
    assert len(p.cells) == 20 and not p.covered
    assert {g for _, _, g in p.glyphs} == {"─"}


def test_road_goes_around_a_window_in_between():
    geoms = {"a": Geom(0, 10, 20, 10), "wall": Geom(30, 5, 20, 20), "b": Geom(60, 10, 20, 10)}
    p = rm.plan(geoms, [("r", "a", "b")], 100, 40)["r"]
    assert not p.covered                                   # there is a gap above / below the wall
    assert any(y < 5 or y >= 25 for _, y in p.cells)
    chars = {g for _, _, g in p.glyphs}
    assert chars <= {"─", "│", "┌", "┐", "└", "┘"} and len(chars) > 2
    # consecutive cells are neighbours
    assert all(abs(a[0] - b[0]) + abs(a[1] - b[1]) == 1 for a, b in zip(p.cells, p.cells[1:]))


def test_crosses_a_window_only_when_no_gap_exists():
    geoms = {"a": Geom(0, 0, 20, 30), "wall": Geom(25, 0, 10, 30), "b": Geom(40, 0, 20, 30)}
    p = rm.plan(geoms, [("r", "a", "b")], 60, 30)["r"]
    assert p.covered and all(25 <= x < 35 for x, _ in p.covered)
    assert rm.hit({"r": p}, *next(iter(p.covered))) is None             # hidden under the window
    assert rm.hit({"r": p}, *next(iter(p.covered)), include_covered=True) == "r"


def test_several_gates_on_one_side_are_spread_and_hits_find_them():
    geoms = {"forge": Geom(0, 0, 30, 20), "s1": Geom(50, 0, 20, 8), "s2": Geom(50, 12, 20, 8)}
    roads = [("up", "forge", "s1"), ("down", "forge", "s2")]
    paths = rm.plan(geoms, roads, 100, 30)
    up, down = paths["up"], paths["down"]
    assert up.exit.side == down.exit.side == "right" and up.exit.y < down.exit.y   # ordered, no crossing
    assert rm.hit(paths, up.exit.x, up.exit.y) == "up"
    assert rm.hit(paths, *down.cells[len(down.cells) // 2]) == "down"
    assert rm.hit(paths, 90, 29) is None


def test_roads_off_canvas_are_skipped_and_plan_is_deterministic():
    geoms = {"a": Geom(0, 0, 20, 10), "b": Geom(40, 0, 20, 10)}
    roads = [("r", "a", "b"), ("gone", "a", "elsewhere")]
    one, two = rm.plan(geoms, roads, 80, 20), rm.plan(geoms, roads, 80, 20)
    assert set(one) == {"r"} and one["r"].cells == two["r"].cells
    assert rm.plan(geoms, roads, 0, 0) == {}


def test_touching_windows_get_a_short_road():
    geoms = {"a": Geom(0, 0, 20, 10), "b": Geom(20, 0, 20, 10)}
    p = rm.plan(geoms, [("r", "a", "b")], 40, 10)["r"]
    assert p.cells and len(p.glyphs) == len(p.cells)
