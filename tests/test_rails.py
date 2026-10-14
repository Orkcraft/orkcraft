"""Camp's roads as rail track and carts as mine carts (docs/design/color-pass.md §6d, design-system-v2.md §4d–4e,
town-readability.md §3): the track's autotiles chosen by neighbours (js/rails.js, run in Node), and what the snapshot
says of each cart: its load, its short ref, its state and whether it stands at its road's stop (gui/state.py)."""
from __future__ import annotations

import json
import shutil
import subprocess
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from orkcraft.gui import state
from orkcraft.realm import pipes, roads
from orkcraft.realm.orcs import Alert

JS = Path(__file__).resolve().parents[1] / "orkcraft" / "gui" / "static" / "js"


def _node(body: str, tmp_path: Path):
    script = tmp_path / "run.mjs"
    script.write_text(f'import {{ lay, tileOf }} from "{(JS / "rails.js").as_uri()}";\n'
                      f'import {{ plan, TRACK_CELL }} from "{(JS / "roads.js").as_uri()}";\n{body}', encoding="utf-8")
    return json.loads(subprocess.run(["node", str(script)], capture_output=True, text=True, check=True, timeout=30).stdout)


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_the_track_is_tiled_by_its_neighbours_a_switch_where_exits_split_and_a_merge_where_roads_join(tmp_path):
    out = _node("""
const rects = { a: { x: 40, y: 200, w: 120, h: 64 }, b: { x: 400, y: 80, w: 120, h: 64 },
                c: { x: 400, y: 320, w: 120, h: 64 }, d: { x: 760, y: 200, w: 120, h: 64 } };
const roads = [{ id: "ab", from: "a", to: "b" }, { id: "ac", from: "a", to: "c" },
               { id: "bd", from: "b", to: "d" }, { id: "cd", from: "c", to: "d" }];
const camp = plan(rects, roads, 1000, 500, rects, { bundle: true }), office = plan(rects, roads, 1000, 500, rects);
const tiles = plan(rects, roads, 1000, 500, rects, { bundle: true, cell: TRACK_CELL });
const big = { cell: tiles[0].cell, junctions: lay(tiles).junctions.map((j) => j.tile).sort(),
  stops: Object.values(lay(tiles).pieces).map((ps) => ps.filter((x) => x.stop).length) };
const t = lay(camp);
const steps = camp.every((p) => p.cells.every((c, i) => !i || Math.abs(c[0] - p.cells[i - 1][0]) + Math.abs(c[1] - p.cells[i - 1][1]) === 1));
console.log(JSON.stringify({ big, junctions: t.junctions.map((j) => j.tile), stops: t.stops.map((x) => [x.road, x.dir]),
  tiles: [...new Set(t.tiles.map((x) => x.tile))], steps, exits: office.map((p) => p.exit.join()),
  campExits: camp.map((p) => p.exit.join()),
  kinds: [tileOf(new Set("ew"), new Set("w"), new Set("e")), tileOf(new Set("nesw"), new Set("ws"), new Set("en")),
          tileOf(new Set("new"), new Set("w"), new Set("en")), tileOf(new Set("nes"), new Set("ns"), new Set("e")),
          tileOf(new Set("esw"), new Set("es"), new Set("ws")), tileOf(new Set("nw"), new Set("n"), new Set("w"))] }));
""", tmp_path)
    assert out["steps"]                                           # every cell next to the one before
    assert out["big"] == {"cell": 32, "junctions": ["merge-e", "switch-e"], "stops": [1, 1, 1, 1]}   # a v2 tile a cell
    assert sorted(out["junctions"]) == ["merge-e", "switch-e"]    # a's two exits split, d's two entries join
    assert [r for r, _ in out["stops"]] == ["ab", "ac", "bd"] and {d for _, d in out["stops"]} == {"e"}
    assert {"straight-h", "straight-v"} <= set(out["tiles"]) and any(t.startswith("corner-") for t in out["tiles"])
    assert len(set(out["exits"])) == 4 and len(set(out["campExits"])) == 3   # Office: a gate a road; Camp: shared
    assert out["kinds"] == ["straight-h", "cross", "switch-e", "merge-e", "t-s", "corner-nw"]


def _town(*carts, specs=None):
    return SimpleNamespace(roads=SimpleNamespace(carts=list(carts)), custom_specs=specs or {})


def _cart(status, at, ref="", road="r1", target="b", want="", kind=pipes.TEXT, value="x", title="Fix the login form"):
    p = pipes.Payload(kind=kind, value=value, source="a", mode="on_done", title=title, ref=ref, want=want)
    return roads.Cart(road_id=road, source="a", target=target, status=status, payload=p, at=at)


def _muster(alerts=(), asking=()):
    orcs = [SimpleNamespace(alert=Alert(id=f"o{i}", title="?"), building=b) for i, b in enumerate(asking)]
    return SimpleNamespace(roster=SimpleNamespace(alerts=list(alerts), orcs=orcs))


def test_a_carts_load_says_its_kind_never_its_text():
    assert state.load_of(pipes.Payload("text", "x", "a", "m", want=pipes.CHANGE)) == "code"
    assert state.load_of(pipes.Payload("text", "x", "a", "m", want=pipes.REPLY)) == "message"
    assert state.load_of(pipes.Payload("text", "write code please", "a", "m")) == "doc"
    assert state.load_of(pipes.Payload("text", "x", "a", "m"), "watchtower") == "message"
    assert state.load_of(pipes.Payload("file", "src/app.py", "a", "m")) == "code"
    assert state.load_of(pipes.Payload("file", "docs/a.md", "a", "m")) == "doc"
    assert state.load_of(pipes.Payload("file", "art/logo.png", "a", "m")) == "asset"
    assert [state.short_ref(r) for r in ("42", "#42", "tasks/todo/42-login.md", "agent:x", "")] == ["#42"] * 3 + ["", ""]


def test_a_stopped_cart_stands_at_its_stop_and_a_moving_one_leaves_the_snapshot():
    now = time.monotonic()
    town = _town(_cart("sent", now - 100, ref="1"), _cart("held", now - 100, ref="2"), _cart("error", now - 50, ref="3"),
                 _cart("filtered", now - 1, ref="4"), _cart("held", now - 5000, ref="5"))
    out = {c["ref"]: c for c in state.carts(town, now)}
    assert set(out) == {"#2", "#3", "#4"}                     # a moving cart long gone; a stopped one an hour at most
    assert (out["#2"]["state"], out["#2"]["stands"]) == ("held", True)
    assert (out["#3"]["state"], out["#3"]["stands"]) == ("stuck", True)
    assert (out["#4"]["state"], out["#4"]["stands"]) == ("back", False)
    assert out["#2"]["load"] == "doc" and out["#2"]["title"] == "Fix the login form"


def test_a_cart_waits_for_the_person_by_its_question_and_a_newer_cart_of_its_ref_takes_its_place():
    now = time.monotonic()
    town = _town(_cart("sent", now - 300, ref="7"), _cart("delivered", now - 200, ref="8", road="r2", target="c"),
                 _cart("held", now - 100, ref="9"), _cart("sent", now - 20, ref="9"))
    out = state.carts(town, now, muster=_muster(alerts=[Alert(id="q", title="Which?", ref="7")], asking=["c"]))
    standing = {c["ref"]: c["state"] for c in out if c["stands"]}
    assert standing == {"#7": "ask", "#8": "ask"}             # by the question's ref; the latest into a building that asks
    assert not any(c["ref"] == "#9" for c in out)             # the held one went on: its newer cart has left, and is gone


def test_a_roads_stop_keeps_a_pile_of_a_few_carts():
    now = time.monotonic()
    town = _town(*[_cart("held", now - 30 + i, ref=str(i)) for i in range(state.STANDING_PER_ROAD + 4)])   # newest last
    out = state.carts(town, now)
    assert len(out) == state.STANDING_PER_ROAD and all(c["stands"] for c in out)
    assert [c["ref"] for c in out] == [f"#{i}" for i in range(4, state.STANDING_PER_ROAD + 4)]   # the newest, oldest first
