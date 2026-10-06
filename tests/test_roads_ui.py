"""Roads on the canvas (T1098 stage 4): planning, gates, the three visibility levels, the road
card, `Y` subscribes the receiver, `U` removes, re-routing."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from textual.widgets import OptionList
from orkcraft import scroll as ts
from orkcraft.app import OrkcraftApp
from orkcraft.realm import chronicles
from orkcraft.screens.road_modal import RoadHandlerModal, SubscribeModal
from orkcraft.widgets.road_layer import EXIT_GLYPH, RoadGate, RoadLabel, RoadRun
from orkcraft.wm import roadmap

SIZE = (200, 50)
KEY = "town_hall:loot-selection"


def _with_scribe(app: OrkcraftApp) -> None:
    ts.add_handler(app.scroll, "town_hall", "Scribe", kind="chain", chain=[{"op": "count"}])
    ts.subscribe(app.scroll, "town_hall", "loot", "on_selection_change", handler="scribe")


async def _settle(pilot, n: int = 3) -> None:
    for _ in range(n):
        await pilot.pause()


def _gates(app: OrkcraftApp, key: str = KEY) -> dict[str, RoadGate]:
    return {("exit" if g.glyph != "●" else "entry"): g for g in app.desktop.query(RoadGate) if g.key == key}


@pytest.mark.asyncio
async def test_road_is_planned_with_gates_and_hits(fake_repo: Path):
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    _with_scribe(app)
    async with app.run_test(size=SIZE) as pilot:
        await _settle(pilot)
        path = app.desktop.road_paths[KEY]
        loot, chat = app.desktop.get_window("loot").geom, app.desktop.get_window("town_hall").geom
        gates = _gates(app)
        assert gates["exit"].styles.offset.x.value == path.exit.x and gates["exit"].styles.offset.y.value == path.exit.y
        assert gates["exit"].glyph in "▶◀▲▼" and gates["entry"].glyph == "●"     # tiles: the one-cell arrow
        # the exit gate is on the Loot frame, the entry gate on the Town Hall frame
        on_frame = lambda g, x, y: (x in (g.x, g.x + g.w - 1) and g.y <= y < g.y + g.h) or \
            (y in (g.y, g.y + g.h - 1) and g.x <= x < g.x + g.w)
        assert on_frame(loot, path.exit.x, path.exit.y) and on_frame(chat, path.entry.x, path.entry.y)
        mid = path.cells[len(path.cells) // 2]
        assert roadmap.hit(app.desktop.road_paths, *mid, include_covered=True) == KEY
        # the tiled default leaves no gaps: the road runs under windows and is drawn only when selected
        assert path.covered and not list(app.desktop.query(RoadRun))
        app.select_road(KEY)
        await _settle(pilot)
        drawn = sum(len(str(r.render()).replace("\n", "")) for r in app.desktop.query(RoadRun))
        assert drawn == len(path.covered)


@pytest.mark.asyncio
async def test_click_a_gate_shows_the_card_esc_back_and_u_removes(fake_repo: Path, isolated_layout_file: Path):
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    _with_scribe(app)
    async with app.run_test(size=SIZE) as pilot:
        await _settle(pilot)
        await pilot.click(_gates(app)["entry"])
        await _settle(pilot)
        assert app.focus_state.mode == "road" and app.focus_state.road_key == KEY
        assert app.desktop.selected_road == KEY
        card = str(app.screen.query_one("#info-body").render())
        assert "Artifacts" in card and "Town Hall" in card and "selection" in card and "Scribe (chain)" in card
        labels = list(app.desktop.query(RoadLabel))
        assert labels and "Scribe · 📦 Artifacts → 🏰 Town Hall" in labels[0].label

        await pilot.press("escape")
        await _settle(pilot)
        assert app.focus_state.mode == "building" and app.focus_state.building_id == "town_hall"
        assert app.desktop.selected_road is None and not list(app.desktop.query(RoadLabel))

        app.select_road(KEY)
        await _settle(pilot)
        await pilot.press("U")
        await _settle(pilot)
        assert app.scroll.building("town_hall").roads == []
        assert KEY not in app.desktop.road_paths and not _gates(app)
        assert app.focus_state.mode == "building"
        assert "road_removed" in [e["type"] for e in chronicles.history(fake_repo, "town_hall")]
        data = json.loads(isolated_layout_file.read_text(encoding="utf-8"))
        assert not next(b for b in data["buildings"] if b["id"] == "town_hall").get("roads")


@pytest.mark.asyncio
async def test_h_changes_the_handler(fake_repo: Path):
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    _with_scribe(app)
    ts.add_handler(app.scroll, "town_hall", "Echo", kind="chain", chain=[{"op": "count"}])
    async with app.run_test(size=SIZE) as pilot:
        await _settle(pilot)
        app.select_road(KEY)
        await _settle(pilot)
        await pilot.press("H")
        await _settle(pilot)
        assert isinstance(app.screen, RoadHandlerModal)
        lst = app.screen.query_one("#road-list", OptionList)
        # Find echo handler option
        echo_idx = next(i for i in range(lst.option_count) if lst.get_option_at_index(i).id == "echo")
        lst.highlighted = echo_idx
        await pilot.press("enter")
        await _settle(pilot)
        assert app.scroll.building("town_hall").roads[0].handler == "echo"
        assert app.focus_state.mode == "road"
        assert "road_changed" in [e["type"] for e in chronicles.history(fake_repo, "town_hall")]


@pytest.mark.asyncio
async def test_y_subscribes_the_receiver(fake_repo: Path):
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=SIZE) as pilot:
        await _settle(pilot)
        chat, loot = app.desktop.get_window("town_hall"), app.desktop.get_window("loot")
        await pilot.press(str(loot.number))
        await _settle(pilot)
        await pilot.press("Y")
        await _settle(pilot)
        await pilot.press(str(chat.number))
        await _settle(pilot)
        assert isinstance(app.screen, SubscribeModal)
        await pilot.press("down")                      # past "💬 Say it in words…": the first event
        await pilot.press("enter")
        await _settle(pilot)
        [road] = app.scroll.building("loot").roads
        assert (road.source, road.event, road.handler) == ("town_hall", "on_task_completed", None)
        assert "road_subscribed" in [e["type"] for e in chronicles.history(fake_repo, "loot")]
        assert f"loot:{road.id}" in app.desktop.road_paths


@pytest.mark.asyncio
async def test_moving_a_window_reroutes(fake_repo: Path):
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    _with_scribe(app)
    async with app.run_test(size=SIZE) as pilot:
        await _settle(pilot)
        before = app.desktop.road_paths[KEY].exit
        loot = app.desktop.get_window("loot")
        app.desktop.focus_window(loot)
        await _settle(pilot)
        for _ in range(4):
            await pilot.press("alt+shift+up")      # shorter: the gate stays centred on its side
        await _settle(pilot)
        after = app.desktop.road_paths[KEY].exit
        assert (after.x, after.y) != (before.x, before.y)
        gate = _gates(app)["exit"]
        assert (gate.styles.offset.x.value, gate.styles.offset.y.value) == (after.x, after.y)


@pytest.mark.asyncio
async def test_visibility_levels(fake_repo: Path):
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    _with_scribe(app)
    async with app.run_test(size=SIZE) as pilot:
        await _settle(pilot)
        # a layout with a gap: Loot on the left, Chat on the right, nothing else raised
        from orkcraft.wm.geometry import Geom
        for w in app.desktop.windows:
            if w.window_id not in ("loot", "town_hall") and not w.hidden:
                w.display = False
        app.desktop.get_window("loot").apply_geom(Geom(0, 0, 50, 30))
        app.desktop.get_window("town_hall").apply_geom(Geom(120, 5, 60, 30))
        await _settle(pilot)
        path = app.desktop.road_paths[KEY]
        gap = [(x, y) for x, y, _ in path.glyphs if (x, y) not in path.covered]
        assert len(gap) >= 60 and not path.covered
        terrain = app.desktop.terrain
        app.desktop.set_active(None)
        await _settle(pilot)
        assert all(terrain.road_cells[c][1] == "faint" for c in gap)
        x, y = gap[0]
        assert terrain.render_line(y).text[x] == terrain.road_cells[(x, y)][0]
        app.desktop.set_active(app.desktop.get_window("loot"))     # a building selected: brighter
        await _settle(pilot)
        assert all(terrain.road_cells[c][1] == "bright" for c in gap)
        style = terrain._road_styles("#000000")
        assert (str(style["faint"].color.triplet.hex), str(style["bright"].color.triplet.hex)) == ("#5c4326", "#a0703c")
        app.select_road(KEY)                                        # the road selected: over the windows
        await _settle(pilot)
        assert list(app.desktop.query(RoadLabel))                  # labelled; no runs: nothing is covered
        assert not list(app.desktop.query(RoadRun))
        # a click on a gap cell selects the road
        app.set_focus_state("neutral")
        await _settle(pilot)
        x, y = gap[len(gap) // 2]
        gap_char = terrain.road_cells[(x, y)][0]
        await pilot.click(app.desktop, offset=(x, y))
        await _settle(pilot)
        assert app.focus_state.mode == "road" and app.focus_state.road_key == KEY
        app.set_focus_state("neutral")
        app.desktop.set_active(None)
        app.scroll.preferences["roads"] = "off"
        app.desktop.replan_roads()
        await _settle(pilot)
        assert terrain.road_cells == {} and _gates(app)                # gates stay
        assert terrain.render_line(y).text[x] != gap_char


@pytest.mark.asyncio
async def test_u_with_several_roads_asks_for_a_selection(fake_repo: Path):
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    ts.subscribe(app.scroll, "town_hall", "loot", "on_selection_change")
    ts.subscribe(app.scroll, "town_hall", "loot", "on_task_completed")
    async with app.run_test(size=SIZE) as pilot:
        await _settle(pilot)
        await pilot.press(str(app.desktop.get_window("town_hall").number))
        await _settle(pilot)
        await pilot.press("U")
        await _settle(pilot)
        assert len(app.scroll.building("town_hall").roads) == 2


@pytest.mark.asyncio
async def test_the_town_in_immersion_shows_the_same_one_cell_exit_arrow(fake_repo: Path, monkeypatch):
    monkeypatch.setattr(ts, "DEFAULT_VIEW", "town")
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    _with_scribe(app)
    async with app.run_test(size=SIZE) as pilot:
        await _settle(pilot)
        assert app.desktop.town_active and not app.desktop.plain
        path, gate = app.desktop.road_paths[KEY], _gates(app)["exit"]
        assert gate.glyph == EXIT_GLYPH[path.exit.side] and gate.styles.offset.x.value == path.exit.x
        assert gate.styles.width.value == 1
