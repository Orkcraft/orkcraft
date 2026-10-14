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
           ["bench", "lab"], ["ux", "ux_lab"], ["wiki", "scrolls"], ["mine", "mine"], ["lone", "forge"]]
  .map(([id, type]) => ({ id, type }));
const R = [["in", "board"], ["board", "pool"], ["pool", "gate"], ["gate", "out"], ["pool", "bench"], ["bench", "ux"],
           ["pool", "wiki"], ["wiki", "mine"]].map(([from, to], i) => ({ id: "r" + i, from, to }));
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
    assert out["rows"]["1"] == ["wiki", "ux", "mine", "lone"]
    t = out["T"]
    assert len(out["lines"]) == 2 and (out["lines"][1] - out["lines"][0]) % t == 0   # the columns are whole tiles
    for bid, (feet, stop) in out["feet"].items():
        if bid not in ("in", "out"):
            assert stop == out["lines"][0 if bid in out["rows"]["0"] else 1] + t / 2   # each on its own row's line
            assert feet <= stop                                                      # its door above its stop
    assert out["outStop"] == out["buffer"]                                            # the catapult at the buffer stop
    assert out["tower"]["cx"] == out["colL"] + t / 2 and out["tower"]["feet"] > out["wallY"] - t   # in the wall, at the way in


def test_the_loop_is_track_whose_pieces_join(tmp_path):
    out = _run(TOWN + """
const L = C.lay(B, R, { b: 1.5, s: 1 }, size);
const cells = new Map(L.tiles.filter((t) => !t.siding).map((t) => [`${t.x},${t.y}`, C.exitsOf(t.name, t.rot)]));
const T = L.T, step = { n: [0, -T], e: [T, 0], s: [0, T], w: [-T, 0] }, back = { n: "s", e: "w", s: "n", w: "e" };
const broken = [];
for (const [k, ex] of cells) {
  const [x, y] = k.split(",").map(Number);
  for (const d of ex) {
    const n = cells.get(`${x + step[d][0]},${y + step[d][1]}`);
    if (n ? !n.has(back[d]) : y + step[d][1] >= 0) broken.push([k, d]);   // only the way in runs off the top
  }
}
const names = L.tiles.map((t) => t.name + (t.rot ? "@" + t.rot : ""));
console.log(JSON.stringify({ broken, names, sidings: L.sidings.length }));
""", tmp_path)
    assert out["broken"] == []                                                      # every exit meets its neighbour
    names = out["names"]
    assert "t-n@90" in names and "corner-ne" in names                               # the split, the left turn
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
    cross = out["r6"]["pts"]                                                         # pool (row 0) → wiki (row 1)
    assert cross[0] == out["stops"]["pool"] and cross[-1] == out["stops"]["wiki"]
    assert all(a[0] == b[0] or a[1] == b[1] for a, b in zip(cross, cross[1:]))      # straight runs, square turns


def test_one_row_has_no_right_column_and_an_empty_town_still_has_its_line(tmp_path):
    out = _run("""
const one = C.lay([{ id: "a", type: "forge" }, { id: "b", type: "lab" }], [], { b: 2, s: 1 }, size);
const none = C.lay([], [], { b: 1, s: 1 }, size);
console.log(JSON.stringify({ right: one.cols.right, lines: one.lines.length, emptyTiles: none.tiles.length,
                             route: one.route("a", "b") }));
""", tmp_path)
    assert out["right"] is None and out["lines"] == 1 and out["emptyTiles"] > 3
    assert out["route"] and len(out["route"]) == 2                                   # along the one line


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
console.log(JSON.stringify({ gap: thrift.buildings.b.x - plain.buildings.b.x, g: thrift.buildings.a.growth, none: plain.buildings.a.growth }));
""", tmp_path)
    assert out["gap"] == 64 + 2                                               # the lean-to's width and a step
    assert out["g"] == {"level": 2, "annex": "growth/annex-thrift.png"} and out["none"] == {"level": 0, "annex": ""}


def test_a_cart_faces_along_each_straight_run_and_keeps_it_on_a_column(tmp_path):
    script = tmp_path / "f.mjs"
    carts = (Path(__file__).resolve().parents[1] / "orkcraft" / "gui" / "static" / "js" / "camp" / "carts.js")
    # carts.js imports the page's modules: test its pure helper by its source alone
    src = carts.read_text(encoding="utf-8")
    body = src[src.index("export function facings"):src.index("function Rolling")]
    script.write_text(f'import {{ lengthOf }} from "{LAYOUT.as_uri()}";\n{body}\n'
                      'console.log(JSON.stringify([facings([[0,0],[100,0],[100,100],[0,100]]), facings([[0,0],[0,50],[50,50]])]));',
                      encoding="utf-8")
    out = json.loads(subprocess.run(["node", str(script)], capture_output=True, text=True, check=True, timeout=30).stdout)
    assert out[0] == [[0, 1], [2 / 3, -1]]                  # east, down the column still east, then west
    assert out[1] == [[0, 1]]                                # down first: as it comes, then east


def test_a_building_placed_low_opens_a_second_row_in_a_small_town(tmp_path):
    out = _run("""
const two = C.rowsOf([{ id: "a", type: "forge", hut: [0.9, 0.1] }, { id: "b", type: "lab", hut: [0.999, 0.75] }]);
const one = C.rowsOf([{ id: "a", type: "forge" }, { id: "b", type: "lab", hut: [0.999, 0.25] }]);
console.log(JSON.stringify([two.map((r) => r.map((b) => b.id)), one.map((r) => r.map((b) => b.id))]));
""", tmp_path)
    assert out == [[["a"], ["b"]], [["b", "a"]]]


def test_the_persons_home_stands_east_of_the_review_gate_just_above_its_line(tmp_path):
    """design-system-v3.md §4.13: the home beside the gate where the person approves, on the gate's row, no path."""
    out = _run(TOWN + """
const L = C.lay(B, R, { b: 1.5, s: 1 }, size, () => false, "homes/lich.png");
const N = C.lay(B.filter((b) => b.type !== "loot"), R, { b: 1.5, s: 1 }, size, () => false, "homes/orc.png");
console.log(JSON.stringify({ home: L.home, gate: L.buildings.gate, bench: L.buildings.bench, line: L.lines[0],
  paths: L.paths.length, none: C.lay(B, R, { b: 1.5, s: 1 }, size).home, alone: N.home, first: N.lines[0] }));
""", tmp_path)
    h, g, b = out["home"], out["gate"], out["bench"]
    assert h["file"] == "homes/lich.png" and h["row"] == g["row"] == 0
    assert g["x"] + g["w"] <= h["x"] < b["x"]                       # east of the gate, before the next building
    assert h["feet"] < out["line"] and out["line"] - h["feet"] <= 4  # just above line 1
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
