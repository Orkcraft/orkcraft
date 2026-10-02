"""Window manager tests: pure geometry plus Pilot-driven move/resize/snap/persist."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from orkcraft.app import OrkcraftApp
from orkcraft.wm import geometry as geo
from orkcraft.wm.geometry import Geom
from orkcraft import scroll as ts
from orkcraft.realm.buildings import presets, registry

SIZE = (120, 40)


# -- geometry -------------------------------------------------------------------

def test_frac_slots_share_edges():
    left = geo.frac_to_geom(geo.SNAP_SLOTS["left"], 101, 31)
    right = geo.frac_to_geom(geo.SNAP_SLOTS["right"], 101, 31)
    assert left.x == 0 and left.x + left.w == right.x
    assert right.x + right.w == 101
    assert left.h == right.h == 31


def test_clamp_keeps_window_inside_and_min_size():
    g = geo.clamp(Geom(200, -5, 3, 1), 100, 30)
    assert g == Geom(100 - geo.MIN_W, 0, geo.MIN_W, geo.MIN_H)


def test_move_and_resize_are_bounded():
    g = Geom(10, 5, 30, 10)
    assert geo.move(g, 1000, 1000, 100, 30) == Geom(70, 20, 30, 10)
    assert geo.resize(g, -100, -100, 100, 30) == Geom(10, 5, geo.MIN_W, geo.MIN_H)
    assert geo.resize(g, 1000, 1000, 100, 30) == Geom(10, 5, 90, 25)


@pytest.mark.parametrize("n", [1, 2, 3, 4])
def test_tile_covers_desktop_without_overlap(n):
    width, height = 120, 40
    cells = set()
    for frac in geo.tile_fracs(n):
        g = geo.frac_to_geom(frac, width, height)
        rect = {(x, y) for x in range(g.x, g.x + g.w) for y in range(g.y, g.y + g.h)}
        assert not (cells & rect)
        cells |= rect
    assert len(cells) == width * height


def test_persist_roundtrip_and_rejects_garbage(tmp_path: Path):
    pr = presets(registry())
    path = tmp_path / "sub" / ".orkcraft.json"
    s = ts.default_scroll(pr)
    assert ts.save(path, s) == []
    loaded, problems = ts.load(path, pr)
    assert problems == [] and loaded.to_dict()["buildings"] == s.to_dict()["buildings"]
    path.write_text("not json", encoding="utf-8")
    loaded, problems = ts.load(path, pr)
    assert any("invalid-" in p for p in problems)
    path.write_text(json.dumps({"version": 999, "windows": {}}), encoding="utf-8")
    loaded, problems = ts.load(path, pr)
    assert any("invalid-" in p for p in problems)


# -- TUI ------------------------------------------------------------------------

def _win(app: OrkcraftApp, window_id: str):
    w = app.desktop.get_window(window_id)
    assert w is not None
    return w


@pytest.mark.asyncio
async def test_default_layout_and_taskbar(fake_repo: Path):
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        desktop = app.desktop
        assert [w.window_id for w in desktop.by_number()] == [
            "loot", "town_hall", "systems",
        ]
        assert _win(app, "systems").hidden
        assert not _win(app, "loot").hidden
        assert not _win(app, "town_hall").hidden


@pytest.mark.asyncio
async def test_mouse_drag_title_moves_window(fake_repo: Path):
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        w = _win(app, "loot")
        w.apply_geom(Geom(10, 8, 50, 16))                    # room to move up
        await pilot.pause()
        start = w.geom
        # Screen-absolute offsets: widget-relative ones would shift with the window.
        x0, y0 = w.region.x + 5, w.region.y
        await pilot.mouse_down(None, offset=(x0, y0))
        await pilot.hover(None, offset=(x0 + 10, y0 - 4))
        await pilot.mouse_up(None, offset=(x0 + 10, y0 - 4))
        await pilot.pause()
        assert w.geom == Geom(start.x + 10, start.y - 4, start.w, start.h)
        assert w.frac is None
        # The dragged window is raised and active.
        assert app.desktop.windows[-1] is w
        assert app.desktop.active is w


@pytest.mark.asyncio
async def test_mouse_drag_corner_resizes_window(fake_repo: Path):
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        w = _win(app, "town_hall")
        start = w.geom
        corner = (start.w - 1, start.h - 1)
        await pilot.mouse_down(w, offset=corner)
        await pilot.hover(w, offset=(corner[0] - 20, corner[1] - 6))
        await pilot.mouse_up(w, offset=(corner[0] - 20, corner[1] - 6))
        await pilot.pause()
        assert w.geom == Geom(start.x, start.y, start.w - 20, start.h - 6)
        assert w.region.width == start.w - 20


@pytest.mark.asyncio
async def test_window_mode_keys_move_resize_snap(fake_repo: Path):
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        desktop = app.desktop
        width, height = desktop.size.width, desktop.size.height
        w = _win(app, "loot")
        w.apply_geom(Geom(10, 8, 50, 16))
        await pilot.pause()
        await pilot.press("1", "ctrl+w")
        await pilot.pause()
        assert desktop.window_mode and app.focused is desktop

        quarter = geo.frac_to_geom(geo.SNAP_SLOTS["top-left"], width, height)
        start = w.geom
        await pilot.press("right", "right", "up", "shift+right", "shift+up")
        assert w.geom == Geom(start.x + 4, start.y - 1, start.w + 2, start.h - 1)

        await pilot.press("l")
        assert w.geom == geo.frac_to_geom(geo.SNAP_SLOTS["right"], width, height)
        await pilot.press("y")
        assert w.geom == quarter

        await pilot.press("f")
        assert w.geom == Geom(0, 0, width, height) and w.maximized
        await pilot.press("f")
        assert w.geom == quarter and not w.maximized

        # Letters are window-mode keys only: 'l' must not snap outside the mode.
        await pilot.press("escape")
        await pilot.pause()
        assert not desktop.window_mode
        assert desktop.window_of(app.focused) is w
        await pilot.press("l")
        assert w.geom == quarter


@pytest.mark.asyncio
async def test_tile_hide_and_taskbar_toggle(fake_repo: Path):
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        desktop = app.desktop
        await pilot.press("3")  # raise the demolished Systems
        await pilot.pause()
        assert not _win(app, "systems").hidden and desktop.active is _win(app, "systems")

        await pilot.press("ctrl+w", "t")
        visible = [w for w in desktop.by_number() if not w.hidden]
        assert len(visible) == 3
        area = sum(w.geom.w * w.geom.h for w in visible)
        assert area == desktop.size.width * desktop.size.height

        await pilot.press("x")  # demolish the active building (Systems)
        assert _win(app, "systems").hidden
        await pilot.press("escape")

        await pilot.click("#taskbar-systems")
        await pilot.pause()
        assert not _win(app, "systems").hidden and desktop.active is _win(app, "systems")


@pytest.mark.asyncio
async def test_layout_persists_between_runs(fake_repo: Path, isolated_layout_file: Path):
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        await pilot.press("3", "ctrl+w", "l", "down", "down", "x")  # Systems: snap, move, demolish
        await pilot.press("2", "b", "escape")  # focus building 2 (Chat), snap ◱
        systems_geom = _win(app, "systems").geom
        chat_geom = _win(app, "town_hall").geom
    data = json.loads(isolated_layout_file.read_text(encoding="utf-8"))
    assert next(b for b in data["buildings"] if b["id"] == "systems")["demolished"] is True
    assert next(b for b in data["buildings"] if b["id"] == "town_hall")["frac"] == list(geo.SNAP_SLOTS["bottom-left"])

    app2 = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app2.run_test(size=SIZE) as pilot:
        await pilot.pause()
        assert _win(app2, "systems").hidden
        assert _win(app2, "systems").geom == systems_geom
        assert _win(app2, "town_hall").geom == chat_geom
        assert app2.desktop.active is _win(app2, "town_hall")

    app3 = OrkcraftApp(repo_root=fake_repo, auto_commit=False, reset_layout=True)
    async with app3.run_test(size=SIZE) as pilot:
        await pilot.pause()
        assert _win(app3, "town_hall").frac != list(geo.SNAP_SLOTS["bottom-left"])
        assert _win(app3, "town_hall").frac == geo.default_fracs()["town_hall"]


@pytest.mark.asyncio
async def test_snapped_windows_follow_terminal_resize(fake_repo: Path):
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        await pilot.press("2", "ctrl+w", "l", "escape")
        await pilot.resize_terminal(170, 50)
        await pilot.pause()
        width, height = app.desktop.size.width, app.desktop.size.height
        assert width == 170
        half = round(width / 2)
        assert _win(app, "town_hall").geom == Geom(half, 0, width - half, height)
