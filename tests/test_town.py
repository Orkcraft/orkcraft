"""Town view (T1102): every building a hut on the map, one expanded at a time over it."""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from orkcraft import scroll as ts
from orkcraft.app import OrkcraftApp
from orkcraft.realm import buildings, huts, masonry
from orkcraft.realm.masonry import Data, Row
from orkcraft.widgets.hut import Hut, footprint
from orkcraft.wm import geometry as geo
from orkcraft.wm.geometry import Geom

SIZE = (200, 50)


@pytest.fixture
def town(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ts, "DEFAULT_VIEW", "town")


async def _settle(pilot, n: int = 4) -> None:
    for _ in range(n):
        await pilot.pause()


def _shown(app: OrkcraftApp) -> list[str]:
    return [w.window_id for w in app.desktop.windows if app.desktop.in_view(w) and not w.hidden and w.visible]


def _hut_geoms(app: OrkcraftApp) -> dict[str, Geom]:
    return {bid: h.geom for bid, h in app.desktop.huts.items() if h.display}


# -- the art library and the `mini` block ----------------------------------------------------------

def test_art_library_fits_the_hut():
    assert len(huts.ART) >= 10
    for name, (lines, use) in huts.ART.items():
        assert len(lines) == huts.ART_H and use, name
        assert all(len(ln) <= huts.ART_W and ln.isascii() for ln in lines), name
    assert set(huts.BUILTIN_ART.values()) <= set(huts.ART)
    assert huts.art_for("nope") == huts.art(huts.DEFAULT_ART)
    assert huts.art_for("x", {"mini": {"art": "rookery"}}) == huts.art("rookery")


def test_mini_templates_render_from_fetched_data(tmp_path: Path):
    rows = Data("list", rows=[Row("Fix login", id="T1", status="in-progress"), Row("Docs", id="T2", status="todo"),
                              Row("Tests", id="T3", status="todo")])
    assert huts.render_line("{count} open · {title}", rows) == "3 open · Fix login"
    assert huts.render_line("{count} todo · next {id}", rows, {"status": "todo"}) == "2 todo · next T2"
    assert huts.render_line("{title}", rows, {"status": "done"}) == huts.EMPTY
    log = Data("text", text="collected 12\n\n12 passed in 3s\n")
    assert huts.render_line("{last}", log) == "12 passed in 3s"
    assert huts.render_line("{count} lines", log) == "2 lines"
    md = Data("text", text="```diff\n+x\n```\n## PR · `auth` **fix**\nbody line\n")
    assert huts.render_line("{heading}", md) == "PR · auth fix" and huts.render_line("{last}", md) == "body line"
    (tmp_path / "a").write_text("x")
    assert huts.render_line("{count} files", Data("tree", path=tmp_path)) == "1 files"
    assert huts.render_line("{last}", Data("text", error="no file")).startswith("⚠")

    spec = {"mini": {"art": "forge", "lines": [{"data": "tasks", "template": "⚙ {count}", "where": {"status": "todo"}},
                                               {"data": "log", "template": "{last}"}]}}
    assert huts.custom_status(spec, {"tasks": rows, "log": log}) == ["⚙ 2", "12 passed in 3s"]
    # no `mini`: what the first data entry holds
    assert huts.custom_status({}, {"tasks": rows}) == ["3 rows · Fix login"]
    assert huts.custom_status({}, {"log": log}) == ["12 passed in 3s"]


def _spec(**mini) -> dict:
    return {"id": "ci_watch", "title": "CI Watch", "icon": "🛠", "orc": {"name": "Tinker"},
            "data": [{"name": "open", "source": "graph_nodes", "params": {"status": "todo"}},
                     {"name": "log", "source": "file_tail", "params": {"path": "README.md", "lines": 5}}],
            "layout": {"direction": "vertical", "panes": [{"widget": "list", "data": "open"},
                                                          {"widget": "log", "data": "log"}]},
            **({"mini": mini} if mini else {})}


def test_mini_is_checked_with_the_spec(fake_repo: Path):
    ok = _spec(art="workshop", lines=[{"data": "open", "template": "{count} open · {title}", "where": {"status": "todo"}},
                                      {"data": "log", "template": "{last}"}])
    assert masonry.validate_spec(ok, fake_repo) == []
    assert masonry.validate_spec(_spec(), fake_repo) == []          # optional
    bad = masonry.validate_spec(_spec(art="castle"), fake_repo)
    assert bad and "art" in bad[0]
    errors = masonry.validate_spec(_spec(lines=[{"data": "nope", "template": "{count}"},
                                                {"data": "log", "template": "{title}"}]), fake_repo)
    assert any("no data named 'nope'" in e for e in errors)
    assert any("{title} is not available for text data" in e for e in errors)
    errors = masonry.validate_spec(_spec(lines=[{"data": "log", "template": "{last}", "where": {"status": "x"}}]), fake_repo)
    assert any("where only applies to list data" in e for e in errors)
    errors = masonry.validate_spec(_spec(lines=[{"data": "open", "template": "{count}", "where": {"colour": "x"}}]), fake_repo)
    assert any("unknown field 'colour'" in e for e in errors)
    assert masonry.validate_spec(_spec(lines=[{"data": "open", "template": "{count}"}] * 3), fake_repo) == []
    assert masonry.validate_spec(_spec(lines=[{"data": "open", "template": "{count}"}] * 4), fake_repo)  # at most three


# -- geometry and the scroll -------------------------------------------------------------------------

HUT_W, HUT_H = 18, 12


def test_hut_spot_survives_a_resize():
    fx, fy = geo.hut_to_frac(120, 20, 200, 50, HUT_W, HUT_H)
    assert geo.hut_from_frac(fx, fy, 200, 50, HUT_W, HUT_H) == Geom(120, 20, HUT_W, HUT_H)
    g = geo.hut_from_frac(fx, fy, 120, 30, HUT_W, HUT_H)
    assert g.x + HUT_W <= 120 and g.y + HUT_H <= 30


def test_scroll_keeps_view_and_hut_spots(tmp_path: Path, town):
    presets = buildings.presets(buildings.registry())
    s = ts.load(tmp_path / "s.json", presets)[0]
    assert s.preferences["view"] == "town"
    s.buildings[0].hut = [0.25, 0.5]
    s.preferences["view"] = "tiles"
    assert ts.save(tmp_path / "s.json", s) == []
    back = ts.load(tmp_path / "s.json", presets)[0]
    assert back.buildings[0].hut == [0.25, 0.5] and back.preferences["view"] == "tiles"
    data = json.loads((tmp_path / "s.json").read_text())
    data["buildings"][0]["hut"] = [2, 0]
    (tmp_path / "s.json").write_text(json.dumps(data))
    assert ts.load(tmp_path / "s.json", presets)[1]                 # out of range: refused


# -- the town on the canvas ------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_town_starts_collapsed_and_opens_one_building(fake_repo: Path, town):
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=SIZE) as pilot:
        await _settle(pilot)
        desk = app.desktop
        assert desk.town_active and desk.active is None and _shown(app) == []   # no auto-focused building
        built = [w.window_id for w in desk.windows if desk.in_view(w) and not w.hidden]
        assert sorted(_hut_geoms(app)) == sorted(built)
        spots = _hut_geoms(app)
        assert all(not geo.overlaps(a, b) for i, a in enumerate(spots.values()) for b in list(spots.values())[i + 1:])

        loot = desk.get_window("loot")
        await pilot.press(str(loot.number))
        await _settle(pilot)
        assert desk.active is loot and _shown(app) == ["loot"] and loot.has_class("-town-open")
        g = geo.frac_to_geom(geo.TOWN_SLOT, desk.dims[0], desk.dims[1] - desk.open_reserve)   # clear of the console
        assert (loot.styles.offset.x.value, loot.styles.offset.y.value) == (g.x, g.y)
        assert desk.huts["loot"].has_class("-expanded")
        assert _hut_geoms(app) == spots                              # opening never moves a hut

        chat = desk.get_window("town_hall")
        await pilot.press(str(chat.number))
        await _settle(pilot)
        assert _shown(app) == ["town_hall"] and not desk.huts["loot"].has_class("-expanded")

        await pilot.press("escape")
        await _settle(pilot)
        assert desk.active is None and _shown(app) == [] and _hut_geoms(app) == spots


@pytest.mark.asyncio
async def test_click_opens_click_again_or_canvas_closes(fake_repo: Path, town):
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=SIZE) as pilot:
        await _settle(pilot)
        desk = app.desktop
        await pilot.click(desk.huts["loot"])
        await _settle(pilot)
        assert _shown(app) == ["loot"] and app.focus_state.building_id == "loot"
        desk.post_message(Hut.Clicked(desk.huts["loot"]))          # the hut is under the window now
        await _settle(pilot)
        assert _shown(app) == [] and app.focus_state.mode == "neutral"
        await pilot.click(desk.huts["town_hall"])
        await _settle(pilot)
        assert _shown(app) == ["town_hall"]
        assert len(app.screen_stack) == 1        # the click opened the building, not a card inside it
        await pilot.click(desk, offset=(1, 1))                           # the map outside the window
        await _settle(pilot)
        assert _shown(app) == []


@pytest.mark.asyncio
async def test_roads_join_huts_and_stay_put(fake_repo: Path, town):
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    ts.add_handler(app.scroll, "town_hall", "Scribe", kind="chain", chain=[{"op": "count"}])
    ts.subscribe(app.scroll, "town_hall", "loot", "on_selection_change", handler="scribe")
    async with app.run_test(size=SIZE) as pilot:
        await _settle(pilot)
        desk = app.desktop
        path = desk.road_paths["town_hall:loot-selection"]
        on_frame = lambda g, x, y: (x in (g.x, g.x + g.w - 1) and g.y <= y < g.y + g.h) or \
            (y in (g.y, g.y + g.h - 1) and g.x <= x < g.x + g.w)
        assert on_frame(desk.huts["loot"].geom, path.exit.x, path.exit.y)
        assert on_frame(desk.huts["town_hall"].geom, path.entry.x, path.entry.y)
        await pilot.press(str(desk.get_window("loot").number))
        await _settle(pilot)
        assert desk.road_paths["town_hall:loot-selection"].cells == path.cells
        app.desktop.traffic.flash_coin("town_hall")                         # the coin lands on the hut
        coin = app.desktop.traffic.coins["town_hall"][1]
        hut = desk.huts["town_hall"].geom
        assert hut.x <= coin.styles.offset.x.value < hut.x + hut.w


@pytest.mark.asyncio
async def test_status_lines_badges_and_demolish(fake_repo: Path, town):
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=SIZE) as pilot:
        await _settle(pilot)
        desk = app.desktop
        desk.refresh_huts()
        await _settle(pilot)
        loot = desk.huts["loot"]
        assert all(h.status for h in desk.huts.values() if h.display), {b: h.status for b, h in desk.huts.items()}
        assert loot.badge and "ARTIFACTS" in loot.label.lines[-1]
        assert loot.sil.id == "loot" and (loot.geom.w, loot.geom.h) == footprint(loot.sil, loot.label, len(loot.actions))

        desk.hide(desk.get_window("loot"))
        await _settle(pilot)
        assert not desk.huts["loot"].display and "loot" not in desk.road_paths


@pytest.mark.asyncio
async def test_no_dragging_or_snapping_while_in_town(fake_repo: Path, town):
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=SIZE) as pilot:
        await _settle(pilot)
        desk = app.desktop
        loot = desk.get_window("loot")
        stored = (loot.geom, loot.frac)
        await pilot.press(str(loot.number))
        await _settle(pilot)
        desk.snap(loot, "left")
        desk.move_by(loot, 3, 1)
        await pilot.mouse_down(loot, offset=(5, 0))
        await pilot.hover(loot, offset=(15, 4))
        await pilot.mouse_up(loot, offset=(15, 4))
        await _settle(pilot)
        assert (loot.geom, loot.frac) == stored


@pytest.mark.asyncio
async def test_alt_v_switches_to_tiles_and_back(fake_repo: Path, town, isolated_layout_file: Path):
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=SIZE) as pilot:
        await _settle(pilot)
        desk = app.desktop
        built = sorted(_hut_geoms(app))
        await pilot.press("alt+v")
        await _settle(pilot)
        assert not desk.town and sorted(_shown(app)) == built and not _hut_geoms(app)
        assert all(not w.has_class("-town-open") for w in desk.windows)
        assert json.loads(isolated_layout_file.read_text())["preferences"]["view"] == "tiles"
        await pilot.press("alt+v")
        await _settle(pilot)
        assert desk.town and sorted(_hut_geoms(app)) == built
        assert len(_shown(app)) <= 1


@pytest.mark.asyncio
async def test_hut_spots_persist(fake_repo: Path, town, isolated_layout_file: Path):
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=SIZE) as pilot:
        await _settle(pilot)
        hut = app.desktop.huts["loot"]
        start = hut.geom
        await pilot.mouse_down(hut, offset=(3, 3))
        await pilot.hover(app.desktop, offset=(hut.geom.x + 3 - 6, hut.geom.y + 3 + 2))   # drag, not click
        before = hut.geom
        assert before != start                                          # the hut followed the mouse
        await pilot.mouse_up(app.desktop, offset=(hut.geom.x + 3, hut.geom.y + 3))
        await _settle(pilot)
        assert app.desktop.active is None                               # a drag does not open it
        spot = hut.geom
        assert spot == before
        frac = list(geo.hut_to_frac(spot.x, spot.y, *app.desktop.hut_room, spot.w, spot.h))
    data = json.loads(isolated_layout_file.read_text())
    stored = next(b for b in data["buildings"] if b["id"] == "loot")["hut"]
    assert stored == frac

    again = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with again.run_test(size=SIZE) as pilot:
        await _settle(pilot)
        assert again.desktop.huts["loot"].geom == spot


@pytest.mark.asyncio
async def test_minimal_mode_shows_one_window_not_huts(fake_repo: Path, town):
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=(90, 40)) as pilot:
        await _settle(pilot)
        assert app.desktop.single and not app.desktop.town_active and not _hut_geoms(app)


# -- the calm console (T1103) ---------------------------------------------------------------------

@pytest.mark.asyncio
async def test_calm_town_shows_the_war_map_and_the_town_hall(fake_repo: Path, town):
    from orkcraft.app import WARMAP_FLOAT_W
    from orkcraft.screens.console import Console

    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=SIZE) as pilot:
        await _settle(pilot)
        console = app.screen.query_one("#console", Console)
        desk = app.desktop
        assert console.has_class("-floating") and console.has_class("-calm")
        assert console.region.width == WARMAP_FLOAT_W and console.region.bottom == SIZE[1] - 1
        assert not console.query_one("#clan-roster").display or not console.query_one("#clan-roster").region.width
        assert not app.screen.query(BUILD_BUTTON_QUERY)                # the Town Hall took its place
        hall = desk.huts["town_hall"]
        assert hall.fixed and hall.geom.x + hall.geom.w == desk.size.width   # pinned bottom right
        assert "Preset" in str(hall.render()) and "New" in str(hall.render())   # T1108: two ways to build
        assert not app.screen.query_one("#taskbar").display
        assert desk.size.height == SIZE[1] - 2                       # the town has the whole height
        spots = _hut_geoms(app)
        assert all(g.y + g.h <= desk.size.height - desk.hut_reserve for g in spots.values())

        await pilot.press(str(desk.get_window("loot").number))        # a selection: the full console
        await _settle(pilot)
        assert not console.has_class("-calm") and console.region.width == SIZE[0]
        assert console.query_one("#clan-roster").region.width > 0
        loot = desk.get_window("loot")
        assert loot.region.bottom <= console.region.y                 # the open building stays clear
        assert _hut_geoms(app) == spots                                # and the town did not move

        await pilot.press("escape")
        await _settle(pilot)
        assert console.has_class("-calm") and _hut_geoms(app) == spots


BUILD_BUTTON_QUERY = "BuildButton"


@pytest.mark.asyncio
async def test_town_hall_builds_from_a_preset_or_from_scratch_and_audits_from_f10(fake_repo: Path, town):
    from orkcraft.screens.build_wizard import BuildWizard
    from orkcraft.screens.presets_modal import PresetsModal

    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=SIZE) as pilot:
        await _settle(pilot)
        hall = app.desktop.huts["town_hall"]
        spot = hall.geom
        assert [aid for _, _, aid in hall._buttons] == ["hall.preset", "hall.scratch"]   # T1108: two ways to build
        bx = next(x0 for x0, _, aid in hall._buttons if aid == "hall.preset")
        await pilot.click(hall, offset=(bx, hall.geom.h - 1))     # 📜 Preset on the hut
        await _settle(pilot)
        assert isinstance(app.screen, PresetsModal)
        await pilot.press("escape")
        await _settle(pilot)
        nx = next(x0 for x0, _, aid in hall._buttons if aid == "hall.scratch")
        await pilot.click(hall, offset=(nx, hall.geom.h - 1))     # 🛠 New on the hut
        await _settle(pilot)
        from orkcraft.screens.builder_interview import BuilderChat
        assert isinstance(app.screen, BuilderChat)
        await pilot.press("escape")
        await _settle(pilot)
        await pilot.press("B")                                         # the key opens the whole menu
        await _settle(pilot)
        assert "Build" in str(app.screen.query_one("#road-title").render())
        await pilot.press("down", "down", "enter")                     # the Foreman (from scratch is second)
        await _settle(pilot)
        assert isinstance(app.screen, BuildWizard)
        await pilot.press("escape")
        await _settle(pilot)

        await pilot.press("f10")
        await _settle(pilot)
        await pilot.press("9")                                         # 🔍 Audit the camp
        await _settle(pilot)
        assert (fake_repo / ".orkcraft" / "audit" / "latest.json").exists()
        assert hall.geom == spot                                       # the hall never moves


@pytest.mark.asyncio
async def test_a_waiting_orc_sets_its_hut_on_fire(fake_repo: Path, town):
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=SIZE) as pilot:
        await _settle(pilot)
        from orkcraft.realm.orcs import Alert, garrison_badge
        alert = Alert("alt-1", "Clarification needed")
        app.roster.alerts.append(alert)
        for o in app.roster.orcs:
            if o.building == "town_hall":
                o.status = "alert"
                o.alert = alert
        for w in app.desktop.windows:
            w.set_badge(garrison_badge(app.roster.garrison(w.window_id)))
            if (hut := app.desktop.huts.get(w.window_id)) is not None:
                hut.set_badge(w.badge)
        app._console.refresh_state(app.focus_state, app.roster)
        app.desktop.refresh_huts()
        await _settle(pilot)
        hut = app.desktop.huts["town_hall"]
        assert hut.has_class("-alert") and "🔥" in hut.label.head
        flame = hut.has_class("-flame")
        app.desktop.flicker_fires()
        assert hut.has_class("-flame") != flame                        # it flickers
        assert not app.desktop.huts["loot"].has_class("-alert")
        rows = app.screen.query_one("#warmap-list")
        assert "🔥" in str(rows.get_option_at_index(0).prompt)         # seen from any canvas


@pytest.mark.asyncio
async def test_tiles_keep_the_docked_console(fake_repo: Path):
    from orkcraft.screens.console import Console

    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)          # tests default to tiles
    async with app.run_test(size=SIZE) as pilot:
        await _settle(pilot)
        console = app.screen.query_one("#console", Console)
        assert not console.has_class("-floating") and console.region.width == SIZE[0]
        assert app.screen.query_one("#taskbar").display


@pytest.mark.asyncio
async def test_orc_chat_keeps_the_town_still_and_the_open_building_clear(fake_repo: Path, town):
    from orkcraft.screens.orc_chat import OrcChat

    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=SIZE) as pilot:
        await _settle(pilot)
        spots = _hut_geoms(app)
        chat_win = app.desktop.get_window("town_hall")
        await pilot.press(str(chat_win.number))
        await _settle(pilot)
        app.set_focus_state("unit", orc_key_val="orc:resident:town_hall/chieftain")
        await _settle(pilot)
        chat = app.screen.query_one(OrcChat)
        assert chat.display and chat_win.region.right <= chat.region.x       # the window steps aside
        assert _hut_geoms(app) == spots                                  # the town did not move
