"""Camp's town in v3, laid out (js/camp/layout.js, run in Node; docs/design/design-system-v3.md §4): the buildings in
rows by the work's order, a line of track under each row joined into a loop, the lookout in the back wall at the way
in, the catapult at the buffer stop, and a road's carts routed along the lines between its two buildings' stops."""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
LAYOUT = ROOT / "orkcraft" / "gui" / "static" / "js" / "camp" / "layout.js"
MANIFEST = ROOT / "design-system" / "sprites" / "v3" / "manifest.json"

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")


def _run(body: str, tmp_path: Path):
    script = tmp_path / "run.mjs"
    script.write_text(f'import * as C from "{LAYOUT.as_uri()}";\nimport fs from "fs";\n'
                      f'const M = JSON.parse(fs.readFileSync({json.dumps(str(MANIFEST))}, "utf8"));\n'
                      'const SZ = Object.fromEntries(M.sprites.map((r) => [r.file, r.frame || r.size]));\n'
                      'const size = (f) => SZ[f] || null;\n' + body, encoding="utf-8")
    return json.loads(subprocess.run(["node", str(script)], capture_output=True, text=True, check=True, timeout=30).stdout)


TOWN = """
const B = [["pool", "barracks"], ["in", "watchtower"], ["board", "fields"], ["gate", "loot"], ["out", "catapult"],
           ["bench", "lab"], ["ux", "ux_lab"], ["talk", "gramophone"], ["mine", "mine"], ["lone", "forge"]]
  .map(([id, type]) => ({ id, type }));
const R = [["in", "board"], ["board", "pool"], ["pool", "gate"], ["gate", "out"], ["pool", "bench"], ["bench", "ux"],
           ["pool", "talk"], ["talk", "mine"]].map(([from, to], i) => ({ id: "r" + i, from, to }));
"""


def test_the_buildings_stand_in_rows_by_the_works_order_with_the_lookout_and_the_catapult_in_the_wall(tmp_path):
    out = _run(TOWN + """
const L = C.lay(B, R, { b: 1.5, s: 1 }, size);
const order = C.order(B, R).map((b) => b.id);
const rows = {};
for (const p of Object.values(L.buildings).filter((q) => !q.wall)) (rows[p.row] = rows[p.row] || []).push([p.x, p.id]);
for (const r in rows) rows[r] = rows[r].sort((a, c) => a[0] - c[0]).map((x) => x[1]);
console.log(JSON.stringify({ order, rows, lines: L.lines, walls: [L.buildings.in.wall, L.buildings.out.wall],
  T: L.T, feet: Object.fromEntries(Object.values(L.buildings).map((p) => [p.id, [p.feet, p.stop.y]])),
  buffer: L.buffer, outStop: L.buildings.out.stop, tower: L.buildings.in, colL: L.cols.left, wallY: L.wall.y }));
""", tmp_path)
    assert out["order"][:4] == ["in", "board", "pool", "gate"] and out["order"][-1] == "lone"   # the work, then the rest
    assert out["walls"] == ["in", "out"]                                            # the two that face the world
    assert out["rows"]["0"] == ["board", "pool", "gate", "bench"]                    # five a row at most, balanced
    assert out["rows"]["1"] == ["talk", "ux", "mine", "lone"]
    t = out["T"]
    assert len(out["lines"]) == 2 and out["lines"][1] - out["lines"][0] >= t          # as close as the row allows
    stations = ("board", "gate", "mine")                                             # their own track
    for bid, (feet, stop) in out["feet"].items():
        if bid not in ("in", "out"):
            line = out["lines"][0 if bid in out["rows"]["0"] else 1]
            assert stop == line + t / 2                                          # its stop on its row's line
            assert feet <= stop or bid == "pool"                                     # its door above it; the depot on it
    assert out["outStop"] == out["buffer"]                                            # the catapult at the buffer stop
    assert out["tower"]["cx"] == out["colL"] + t / 2 and out["tower"]["feet"] > out["wallY"] - t   # in the wall, at the way in


def test_the_loop_is_track_whose_pieces_join(tmp_path):
    out = _run(TOWN + """
const L = C.lay(B, R, { b: 1.5, s: 1 }, size);
const broken = [];
for (const t of L.tiles.filter((x) => !x.siding)) {
  for (const d of C.exitsOf(t.name, t.rot)) {
    if (!t.next[d] && !(d === "n" && t.y <= 0)) broken.push([t.name, t.x, t.y, d]);   // only the way in runs off the top
  }
}
const names = L.tiles.map((t) => t.name + (t.rot ? "@" + t.rot : ""));
console.log(JSON.stringify({ broken, names, sidings: L.sidings.length }));
""", tmp_path)
    assert out["broken"] == []                                                      # every exit meets its neighbour
    names = out["names"]
    assert "t-e" in names and "corner-ne" in names                                  # the split, the left turn
    assert "corner-sw" in names and "t-n" in names                                  # the right turn, the merge
    assert names.count("stop-e") == 2 and out["sidings"] == 1                       # the buffer; the Task board's siding


def test_a_roads_carts_run_on_the_lines_between_the_stops(tmp_path):
    out = _run(TOWN + """
const L = C.lay(B, R, { b: 1, s: 1 }, size);
const on = (p) => L.tiles.some((t) => !t.siding && p[0] >= t.x && p[0] <= t.x + L.T && p[1] >= t.y && p[1] <= t.y + L.T);
const res = {};
for (const r of R) { const pts = L.route(r.from, r.to); res[r.id] = { pts, on: pts.slice(1).every(on) }; }
res.stops = Object.fromEntries(Object.values(L.buildings).map((p) => [p.id, [p.stop.x, p.stop.y]]));
console.log(JSON.stringify(res));
""", tmp_path)
    for rid in ("r0", "r1", "r2", "r3", "r4", "r5", "r6", "r7"):
        assert out[rid]["pts"] and out[rid]["on"], rid                               # carts only on the lines
    first = out["r0"]["pts"]
    assert first[0][1] < 0 and first[-1] == out["stops"]["board"]                    # in from outside the wall
    cross = out["r6"]["pts"]                                                         # pool (row 0) → talk (row 1)
    assert cross[0] == out["stops"]["pool"] and cross[-1] == out["stops"]["talk"]
    assert all(a[0] == b[0] or a[1] == b[1] for a, b in zip(cross, cross[1:]))      # straight runs, square turns


def test_one_row_has_no_right_column_and_an_empty_town_still_has_its_line(tmp_path):
    out = _run("""
const one = C.lay([{ id: "a", type: "forge" }, { id: "b", type: "lab" }], [], { b: 2, s: 1 }, size);
const none = C.lay([], [], { b: 1, s: 1 }, size);
console.log(JSON.stringify({ right: one.cols.right, lines: one.lines.length, emptyTiles: none.tiles.length,
                             route: one.route("a", "b") }));
""", tmp_path)
    assert out["right"] is None and out["lines"] == 1 and out["emptyTiles"] > 3
    way = out["route"]                                                               # from a's stop east to b's
    assert way and way[0][1] == way[-1][1] and way[-1][0] > way[0][0]
    assert all(b[0] >= a[0] for a, b in zip(way, way[1:]))


def test_a_building_placed_in_office_takes_its_row_and_place_from_there(tmp_path):
    out = _run("""
const B = [{ id: "a", type: "forge", hut: [0.8, 0.1] }, { id: "b", type: "lab", hut: [0.2, 0.9] },
           { id: "c", type: "mill", hut: [0.1, 0.05] }, { id: "d", type: "pit" }, { id: "e", type: "horn", hut: [0.5, 0.95] },
           { id: "f", type: "crag" }];
console.log(JSON.stringify(C.rowsOf(B).map((r) => r.map((b) => b.id))));
""", tmp_path)
    assert out == [["c", "a", "d"], ["b", "e", "f"]]        # by y into rows, by x along them; the unplaced fill in


def test_a_goals_annex_takes_its_room_in_the_row(tmp_path):
    out = _run("""
const B = [{ id: "a", type: "forge" }, { id: "b", type: "lab" }];
const plain = C.lay(B, [], { b: 1, s: 1 }, size), thrift = C.lay([{ ...B[0], goal: "thrift", level: 2 }, B[1]], [], { b: 1, s: 1 }, size);
const a = thrift.buildings.a, b = thrift.buildings.b;
console.log(JSON.stringify({ gap: b.x - plain.buildings.b.x, clear: b.x - (a.x + a.w), g: a.growth, none: plain.buildings.a.growth }));
""", tmp_path)
    assert out["gap"] > 0 and out["clear"] >= 64 + 2                          # the lean-to's width and a step
    assert out["g"] == {"level": 2, "annex": "growth/annex-thrift.png"} and out["none"] == {"level": 0, "annex": ""}


TRAFFIC = ROOT / "orkcraft" / "gui" / "static" / "js" / "camp" / "traffic.js"


def _traffic(body: str, tmp_path: Path):
    script = tmp_path / "t.mjs"
    script.write_text(f'import * as X from "{TRAFFIC.as_uri()}";\n' + body, encoding="utf-8")
    return json.loads(subprocess.run(["node", str(script)], capture_output=True, text=True, check=True, timeout=30).stdout)


def test_a_cart_faces_along_each_straight_run_and_keeps_it_on_a_column(tmp_path):
    out = _traffic("""
const way = [[0, 0], [100, 0], [100, 100], [0, 100]];
console.log(JSON.stringify([50, 150, 250].map((s) => X.pointAt(way, s)).map((p) => [p.x, p.y, p.face])));
""", tmp_path)
    assert out == [[50, 0, 1], [100, 50, 1], [50, 100, -1]]   # east, down the column still east, then west


def test_carts_on_one_line_keep_their_distance_and_never_overtake(tmp_path):
    """§4c rule 7: a fast cart that catches up waits behind the slow one, a cart's length back, and never passes it."""
    out = _traffic("""
const way = [[0, 0], [1000, 0]];
const slow = { id: "slow", pts: way, len: 1000, v: 50, s: 100, rank: 0 };
const fast = { id: "fast", pts: way, len: 1000, v: 400, s: 0, rank: 1 };
const gaps = [], held = [];
for (let k = 0; k < 40; k++) { const h = X.step([slow, fast], 0.1, 60, 8); gaps.push(slow.s - fast.s); if (h.fast) held.push(h.fast); }
const a = { id: "a", pts: way, len: 1000, v: 100, s: 0, rank: 0 }, b = { id: "b", pts: way, len: 1000, v: 100, s: 0, rank: 1 };
X.step([a, b], 0.5, 60, 8);
console.log(JSON.stringify({ min: Math.min(...gaps), last: gaps[gaps.length - 1], held: held[0], ab: [a.s, b.s] }));
""", tmp_path)
    assert out["min"] >= 60 - 1e-6 and abs(out["last"] - 60) < 1e-6         # never nearer than a cart, then behind it
    assert out["held"] == "slow"                                             # the reason in front of it
    assert out["ab"] == [50, 0]                                              # two on one spot: the earlier goes first


def test_a_switch_throws_as_a_cart_that_turns_there_comes_near(tmp_path):
    out = _traffic("""
const c = (s, way) => ({ s, throws: [{ i: 0, way, at: 500 }] });
console.log(JSON.stringify([X.thrown(1, [c(100, "turn")], 160, 32), X.thrown(1, [c(400, "turn")], 160, 32),
                            X.thrown(1, [c(400, "on")], 160, 32), X.thrown(1, [c(600, "turn")], 160, 32)]));
""", tmp_path)
    assert out == [[False], [True], [False], [False]]       # far; near and turning; going on; gone past


def test_a_building_placed_low_opens_a_second_row_in_a_small_town(tmp_path):
    out = _run("""
const two = C.rowsOf([{ id: "a", type: "forge", hut: [0.9, 0.1] }, { id: "b", type: "lab", hut: [0.999, 0.75] }]);
const one = C.rowsOf([{ id: "a", type: "forge" }, { id: "b", type: "lab", hut: [0.999, 0.25] }]);
console.log(JSON.stringify([two.map((r) => r.map((b) => b.id)), one.map((r) => r.map((b) => b.id))]));
""", tmp_path)
    assert out == [[["a"], ["b"]], [["b", "a"]]]


def test_the_persons_home_stands_east_of_the_review_gate_just_above_its_line(tmp_path):
    """design-system-v3.md §4.13: the home beside the gate where the person approves, on the gate's row, its door a
    path above the line like a building's."""
    out = _run(TOWN + """
const L = C.lay(B, R, { b: 1.5, s: 1 }, size, () => false, "homes/lich.png");
const N = C.lay(B.filter((b) => b.type !== "loot"), R, { b: 1.5, s: 1 }, size, () => false, "homes/orc.png");
const bare = C.lay(B, R, { b: 1.5, s: 1 }, size);
console.log(JSON.stringify({ home: L.home, gate: L.buildings.gate, bench: L.buildings.bench, line: L.lines[0],
  path: L.paths.find((p) => p.home), paths: L.paths.length - bare.paths.length, none: C.lay(B, R, { b: 1.5, s: 1 }, size).home, alone: N.home, first: N.lines[0] }));
""", tmp_path)
    h, g, b = out["home"], out["gate"], out["bench"]
    assert h["file"] == "homes/lich.png" and h["row"] == g["row"] == 0
    assert g["x"] + g["w"] <= h["x"] < b["x"]                       # east of the gate, before the next building
    assert h["feet"] < out["line"] and out["line"] - h["feet"] == 24 * 1.5   # a path's length above line 1
    p = out["path"]
    assert out["paths"] == 1 and p["x"] < h["cx"] < p["x"] + p["w"]   # one more path: from its door…
    assert p["y"] < h["feet"] and p["y"] + p["h"] >= out["line"]      # …down to the line
    assert out["none"] is None                                       # no kin known: no home
    assert out["alone"]["row"] == 0 and out["alone"]["feet"] < out["first"]   # no gate: at the first row's end


GRASS = ROOT / "orkcraft" / "gui" / "static" / "js" / "camp" / "grass.js"


def test_an_item_fits_on_grass_only_never_on_track_paths_or_against_a_building(tmp_path):
    """v3-prompts §14 rule 1 (js/camp/grass.js): cells of 16 art px from the camp's corner; a box on a building (or
    one cell from it), a path, a track tile or the palisade does not fit; one in the open grass does; nor on another."""
    out = _run(TOWN + f'import * as G from "{GRASS.as_uri()}";\n' + """
const L = C.lay(B, R, { b: 1.5, s: 1 }, size, () => false, "homes/orc.png");
const walls = G.blockers(L), sz = [40, 48];
const cellOf = (x, y) => G.cellAt(L, x, y);
const at = (x, y) => { const c = cellOf(x, y); return G.fits(L, G.boxAt(L, sz, c.gx, c.gy), walls); };
const pool = L.buildings.pool, t = L.tiles.find((x) => x.name === "straight-h"), p = L.paths[0];
const below = { x: pool.cx, y: L.lines[L.lines.length - 1] + L.T + 140 };
const c = cellOf(below.x, below.y), box = G.boxAt(L, sz, c.gx, c.gy);
console.log(JSON.stringify({
  onBuilding: at(pool.cx, pool.feet - 4), besideBuilding: at(pool.x + pool.w + 8, pool.feet),
  onTrack: at(t.x + L.T / 2, t.y + L.T), onPath: at(p.x + p.w / 2, p.y + p.h), onHome: at(L.home.cx, L.home.feet),
  onWall: at(L.wall.left + 200, L.wall.y), grass: at(below.x, below.y), onItem: G.fits(L, box, walls, [box]),
  snapped: (box.y + box.h - G.grid(L).y) % G.grid(L).c === 0 }));
""", tmp_path)
    assert out == {"onBuilding": False, "besideBuilding": False, "onTrack": False, "onPath": False, "onHome": False,
                   "onWall": False, "grass": True, "onItem": False, "snapped": True}


def test_mission_1s_finale_leaves_along_the_line_to_its_buffer_stop(tmp_path):
    """first-mission.md §9.2: with no Publisher, the passed drill rolls from the Review gate to the line's buffer stop."""
    out = _run("""
const B = [["board", "fields"], ["pool", "barracks"], ["gate", "loot"]].map(([id, type]) => ({ id, type }));
const R = [["board", "pool"], ["pool", "gate"]].map(([from, to], i) => ({ id: "r" + i, from, to }));
const L = C.lay(B, R, { b: 1.5, s: 1 }, size);
console.log(JSON.stringify({ pts: L.routeOut("gate"), gate: [L.buildings.gate.stop.x, L.buildings.gate.stop.y],
                             buffer: [L.buffer.x, L.buffer.y], none: L.routeOut("nowhere") }));
""", tmp_path)
    assert out["pts"][0] == out["gate"] and out["pts"][-1] == out["buffer"] and out["none"] is None


SEND_BACK = TOWN + """
R.push({ id: "back", from: "gate", to: "pool", returns: true }, { id: "brief", from: "mine", to: "pool", returns: true });
"""


def test_every_cart_runs_one_way_round_and_a_send_back_goes_round_again(tmp_path):
    """design-system-v3.md §4c rule 5: east along the lines, down the right column, west along the return line, up the
    left column; the Review gate's send-back to the Agent pool (behind it on its line) goes on, round the return line
    under the lowest row and in again, never back along the line."""
    out = _run(SEND_BACK + """
const L = C.lay(B, R, { b: 1.5, s: 1 }, size);
const T = L.T, mids = L.lines.map((y) => y + T / 2), retMid = L.ret + T / 2;
const bad = [];
for (const r of R) {
  const pts = L.route(r.from, r.to);
  if (!pts) { bad.push([r.id, "no way"]); continue; }
  for (let i = 1; i < pts.length; i++) {
    const [a, b] = [pts[i - 1], pts[i]];
    if (a[1] === b[1] && mids.includes(a[1]) && b[0] < a[0]) bad.push([r.id, "west on a line", a, b]);
    if (a[1] === b[1] && a[1] === retMid && b[0] > a[0]) bad.push([r.id, "east on the return line", a, b]);
    if (a[0] === b[0] && a[0] === L.cols.right + T / 2 && b[1] < a[1]) bad.push([r.id, "up the right column", a, b]);
    if (a[0] === b[0] && a[0] === L.cols.left + T / 2 && b[1] > a[1] && a[1] >= mids[0]) bad.push([r.id, "down the left column", a, b]);
  }
}
const back = L.route("gate", "pool");
console.log(JSON.stringify({ bad, back, retMid, last: L.lines[L.lines.length - 1], ret: L.ret, pool: L.buildings.pool.stop,
  forward: L.route("pool", "gate").some((p) => p[1] === retMid) }));
""", tmp_path)
    assert out["bad"] == []
    assert out["ret"] == out["last"] + 64                                          # under the lowest row, a tile down
    back = out["back"]
    assert any(p[1] == out["retMid"] for p in back)                                # round the return line
    assert back[-1] == [out["pool"]["x"], out["pool"]["y"]]                         # and in again to the pool
    assert out["forward"] is False                                                 # a cart going on never goes round


def test_a_switch_stands_at_every_fork_and_a_route_says_how_each_is_thrown(tmp_path):
    """§4c rule 6: a switch at each fork (into a line from the left column, on to the buffer stop or down to the return
    line); a send-back throws the right one to the return line, a cart going on leaves it still."""
    out = _run(SEND_BACK + """
const L = C.lay(B, R, { b: 1.5, s: 1 }, size);
const forks = L.tiles.filter((t) => t.go && t.go.length > 1).map((t) => t.x + "," + t.y).sort();
const stands = L.switches.map((s) => s.x + "," + s.y).sort();
const name = (i) => (L.switches[i].ret ? "ret" : "left");
const back = L.route("gate", "pool").throws.map((t) => [name(t.i), t.way]);
const on = L.route("pool", "gate").throws.map((t) => [name(t.i), t.way]);
console.log(JSON.stringify({ forks, stands, back, on, n: L.switches.length }));
""", tmp_path)
    assert out["forks"] == out["stands"] and out["n"] == 1 + 1                      # line 2's split, the right switch
    back = out["back"]
    assert ["ret", "turn"] in back                                                 # round again
    assert ["ret", "turn"] not in out["on"]                                          # going on: the right switch still


SERVICE_TOWN = """
const B = [["in", "watchtower"], ["board", "fields"], ["pool", "barracks"], ["gate", "loot"], ["bench", "lab"],
           ["ux", "ux_lab"], ["talk", "gramophone"], ["lone", "forge"], ["wiki", "scrolls"], ["out", "catapult"]]
  .map(([id, type]) => ({ id, type }));
const R = [["in", "board"], ["board", "pool"], ["pool", "gate"], ["gate", "out"], ["pool", "bench"], ["bench", "ux"],
           ["ux", "talk"], ["pool", "wiki"], ["wiki", "pool"], ["talk", "wiki"]].map(([from, to], i) => ({ id: "r" + i, from, to }));
"""


def test_a_service_stands_beside_its_busiest_reader_with_one_short_footpath_and_no_track(tmp_path):
    """design-system-v3.md §4c rule 1 (the back row taken out, the owner): the Wiki, never placed, stands in its busiest
    reader's row next to it (the Agent pool, two roads), with no stop on the line, no path down to it and no cart's
    way; one short footpath (16 art px, narrower than a building's) joins its door to its reader; a reader further away
    (one road) gets no path."""
    out = _run(SERVICE_TOWN + """
const L = C.lay(B, R, { b: 1.5, s: 1 }, size);
const w = L.buildings.wiki, pool = L.buildings.pool, line = L.lines[w.row];
const row = Object.values(L.buildings).filter((p) => p.row === w.row && !p.wall).sort((a, c) => a.x - c.x).map((p) => p.id);
const mine = L.paths.filter((p) => p.x <= w.cx && w.cx <= p.x + p.w && !p.foot);
console.log(JSON.stringify({ w, pool, line, row, down: mine.some((p) => p.y + p.h >= line - 4),
  feet: L.paths.filter((p) => p.service === "wiki"), route: L.route("pool", "wiki"), crossings: L.crossings }));
""", tmp_path)
    w, pool, row = out["w"], out["pool"], out["row"]
    assert w["service"] and w["row"] == pool["row"] and abs(row.index("wiki") - row.index("pool")) == 1   # beside it
    assert out["route"] is None and out["down"] is False                          # no stop, no path to the line
    [foot] = out["feet"]                                                           # one footpath, to the pool only
    assert foot["reader"] == "pool" and foot["w"] == 16 * 1.5 and foot["x"] < w["door"]["x"] < foot["x"] + foot["w"]
    assert foot["y"] <= w["feet"] and foot["y"] + foot["h"] == pool["door"]["y"]   # down to the depot's line
    assert out["crossings"] == []


def test_the_persons_places_win_over_the_neighbours_and_a_placed_service_gets_no_path(tmp_path):
    """§4c rules 1–3: two buildings joined by a road back stand in one row, at most one place apart, when the person
    never placed one of them; a placed one stays where it was put; a Wiki placed in Office keeps its row and gets no
    footpath."""
    out = _run("""
const roads = [{ id: "a", from: "pool", to: "cal" }, { id: "b", from: "cal", to: "pool", returns: true }];
const list = (cal) => [{ id: "board", type: "fields" }, { id: "pool", type: "lake" }, { id: "x", type: "forge" },
  { id: "y", type: "lab" }, { id: "z", type: "mill" }, { id: "q", type: "pit" }, cal, { id: "w", type: "crag" }];
const rowsOf = (L) => { const r = {}; for (const p of Object.values(L.buildings)) (r[p.row] = r[p.row] || []).push([p.x, p.id]);
  return Object.fromEntries(Object.entries(r).map(([k, v]) => [k, v.sort((a, c) => a[0] - c[0]).map((x) => x[1])])); };
const free = rowsOf(C.lay(list({ id: "cal", type: "war_drum" }), roads, { b: 1, s: 1 }, size));
const kept = rowsOf(C.lay(list({ id: "cal", type: "war_drum", hut: [0.9, 0.9] }), roads, { b: 1, s: 1 }, size));
const W = C.lay([{ id: "wiki", type: "scrolls", hut: [0.5, 0.9] }, { id: "pool", type: "forge" }, { id: "y", type: "lab" }],
                [{ id: "r", from: "pool", to: "wiki" }], { b: 1, s: 1 }, size), wiki = W.buildings.wiki;
console.log(JSON.stringify({ free, kept, wiki: [wiki.service, wiki.row, W.paths.filter((p) => p.service).length] }));
""", tmp_path)
    row = next(r for r in out["free"].values() if "pool" in r)
    assert "cal" in row and abs(row.index("cal") - row.index("pool")) <= 2      # neighbours: one place apart at most
    low = out["kept"]["1"]                                                       # the placed one keeps its row;
    assert "cal" in low and "pool" in low and abs(low.index("cal") - low.index("pool")) == 1   # the one never placed joins it
    assert out["wiki"] == [True, 1, 0]                                           # placed: its row, and no footpath


def test_with_no_pocket_track_a_cart_waits_on_its_path_end_and_the_line_stays_clear(tmp_path):
    """§4c rule 7 (the owner): no pocket track; a building's stop is on its line and its waiting cart stands on its
    path's end just above the line, off the track; carts never park there. Stations keep their own track."""
    out = _run(TOWN + """
const L = C.lay(B, R, { b: 1.5, s: 1 }, size);
const p = L.buildings.bench, line = L.lines[p.row];
console.log(JSON.stringify({ pockets: L.tiles.filter((t) => !t.siding && t.y < L.lines[0] && t.x > L.cols.left).length,
  pocketSwitches: L.switches.filter((s) => s.side === "s").length, stop: p.stop.y, wait: p.waitAt.y, line,
  pathFoot: Math.max(...L.paths.filter((q) => q.x < p.cx && p.cx < q.x + q.w).map((q) => q.y + q.h)), parks: !!p.pocket, stations: ["board", "gate", "mine"].map((id) => L.buildings[id].stop.y === L.lines[L.buildings[id].row] + L.T / 2),
  route: L.route("pool", "bench") }));
""", tmp_path)
    assert out["pockets"] == 0 and out["pocketSwitches"] == 0 and all(out["stations"])
    assert out["stop"] == out["line"] + 32 and out["wait"] == out["line"] and out["parks"] is False
    assert out["line"] + 12 <= out["pathFoot"] <= out["line"] + 16                 # its path runs down to the narrow bed
    assert out["route"][-1] == [out["route"][-1][0], out["stop"]]                  # it rolls to its stop on the line


def test_the_agent_pool_is_the_depot_on_its_line_with_three_bays_and_the_track_through_it(tmp_path):
    """design-system-v3.md §4d: the Agent pool's depot stands on its line, its sprite's rails over the line's, no path
    and no pocket; three bays along the through track, in order inside it; a cart for the pool stops at a bay, a cart
    for a building east of it rolls straight through on the line; it takes two of a row's five places."""
    out = _run(TOWN + """
const L = C.lay(B, R, { b: 1.5, s: 1 }, size);
const p = L.buildings.pool, g = L.buildings.gate, rail = L.lines[p.row] + L.T / 2;
const through = L.route("board", "gate");
const rows = C.rowsOf([{ id: "d", type: "barracks" }, ...["a", "b", "c", "e"].map((id) => ({ id, type: "forge" }))]);
console.log(JSON.stringify({ p, rail, gateX: g.cx, toPool: L.route("board", "pool"), through,
  path: L.paths.some((q) => !q.service && q.x <= p.bays[1] && p.bays[1] <= q.x + q.w && q.y + q.h >= p.y),
  rows: rows.map((r) => r.map((b) => b.id)) }));
""", tmp_path)
    p, rail = out["p"], out["rail"]
    assert p["depot"] and p["file"] == "buildings/depot.png"
    assert p["rail"] == rail and p["y"] + round(98 * 1.5) == round(rail)                  # its rails over the line's
    assert p["x"] < p["bays"][0] < p["bays"][1] < p["bays"][2] < p["x"] + p["w"] and len(p["bays"]) == 3
    assert out["path"] is False                                                           # no path
    assert out["toPool"][-1] == [p["bays"][0], rail]                                      # a cart for it: at a bay
    if out["gateX"] > p["x"] + p["w"]:                                                    # one for beyond: through it
        assert any(a[1] == b[1] == rail and a[0] <= p["x"] and b[0] >= p["x"] + p["w"] for a, b in zip(out["through"], out["through"][1:]))
    assert out["rows"] == [["d", "a"], ["b", "c", "e"]]                                  # the depot is two places of six


GROUND = ROOT / "orkcraft" / "gui" / "static" / "js" / "camp" / "ground.js"


def test_the_ground_varies_by_a_fixed_hash_and_the_track_lies_on_a_bed_of_earth(tmp_path):
    """design-system-v3.md §4e: grass and earth tiles chosen by a fixed hash of the cell (the same camp draws the same,
    no row repeats one stamp; ruts only on the bed); under every track tile a narrow band of earth just wider than the
    sleepers (about 1.25× their 32 art px), following its ways out; building paths 24 art px wide."""
    out = _run(TOWN + f'import * as G from "{GROUND.as_uri()}";\n' + """
const L = C.lay(B, R, { b: 1.5, s: 1 }, size);
const row = Array.from({ length: 12 }, (_, x) => G.grassOf(x, 3));
const bed = G.bedOf(L.tiles, L.T), x2 = L.cols.left + 2 * L.T;
const one = bed.filter((c) => c.x === x2 && c.y < L.lines[0] + L.T && c.y + c.h > L.lines[0]);
const covered = new Set(bed.map((c) => Math.floor((c.x + c.w / 2) / L.T) + "," + Math.floor((c.y + c.h / 2) / L.T)));
const paths = Math.min(...Object.keys(Array(400).fill(0)).map((k) => G.earthOf(+k, 7)).map((v) => v.includes("ruts") ? 0 : 1));
console.log(JSON.stringify({ same: G.grassOf(5, 9) === G.grassOf(5, 9) && G.earthOf(2, 4, true) === G.earthOf(2, 4, true),
  kinds: new Set(row).size, one, every: L.tiles.every((t) => bed.some((c) => c.x < t.x + L.T && t.x < c.x + c.w && c.y < t.y + L.T && t.y < c.y + c.h)),
  ruts: Array.from({ length: 400 }, (_, k) => G.earthOf(k, 7, true)).some((v) => v.includes("ruts")), pathsNoRuts: paths,
  pathW: C.PATH_W }));
""", tmp_path)
    assert out["same"] and out["kinds"] >= 3                                       # fixed, and varied along a row
    assert out["every"]                                                              # earth under every tile
    [one] = out["one"]                                                               # a line's straight: one band,
    assert one["along"] == "h" and one["w"] == 64 and one["h"] == 40                # end to end, 40 art px across
    assert 32 < one["h"] <= 1.3 * 32                                                 # just wider than its sleepers
    assert out["ruts"] and out["pathsNoRuts"] == 1                                  # ruts on the bed only
    assert out["pathW"] == 24


def test_plain_grass_dominates_tufts_one_cell_in_eight_flowers_one_in_twenty(tmp_path):
    out = _run(f'import * as G from "{GROUND.as_uri()}";\n' + """
const n = { plain: 0, tufts: 0, flowers: 0 };
for (let x = 0; x < 100; x++) for (let y = 0; y < 100; y++) {
  const v = G.grassOf(x, y); n[v.includes("tufts") ? "tufts" : v.includes("flowers") ? "flowers" : "plain"]++;
}
console.log(JSON.stringify(n));
""", tmp_path)
    assert abs(out["tufts"] / 10000 - 1 / 8) < 0.02 and abs(out["flowers"] / 10000 - 1 / 20) < 0.015
    assert out["plain"] > 0.75 * 10000


def test_the_wilderness_is_thick_outside_the_palisade_and_clear_of_the_camp_and_the_way_in(tmp_path):
    """decisions §17.3: g2's decor thick round the palisade (trees and bushes most), fixed by a hash; none inside the
    camp, none on the way in down to the lookout."""
    out = _run(TOWN + """
const L = C.lay(B, R, { b: 1.5, s: 1 }, size), c = L.camp;
const inside = L.decor.filter((d) => d.x > c.x && d.x < c.x + c.w && d.y > c.y && d.y < c.y + c.h).length;
const way = L.decor.filter((d) => d.x > L.cols.left && d.x < L.cols.left + L.T && d.y < L.wall.y).length;
const again = JSON.stringify(C.lay(B, R, { b: 1.5, s: 1 }, size).decor) === JSON.stringify(L.decor);
const green = L.decor.filter((d) => /pine|tree|bush/.test(d.name)).length;
console.log(JSON.stringify({ n: L.decor.length, inside, way, again, green }));
""", tmp_path)
    assert out["n"] >= 40 and out["inside"] == 0 and out["way"] == 0 and out["again"]
    assert out["green"] > out["n"] / 2                                               # trees and bushes the most
