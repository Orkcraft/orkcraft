"""👻 Ghost placement (T1108 stage 4): arrows or the mouse, Enter or a click builds, Esc cancels."""
from __future__ import annotations

from pathlib import Path

import pytest

from orkcraft import scroll as ts
from orkcraft.app import OrkcraftApp
from orkcraft.widgets.ghost import Ghost
from orkcraft.wm.desktop import Desktop
from orkcraft.wm import geometry as geo

SIZE = (180, 50)


@pytest.fixture(autouse=True)
def town(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ts, "DEFAULT_VIEW", "town")


async def _settle(pilot, n: int = 4) -> None:
    for _ in range(n):
        await pilot.pause()


@pytest.mark.asyncio
async def test_arrows_walk_the_ghost_and_enter_builds_there(fake_repo: Path):
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=SIZE) as pilot:
        await _settle(pilot)
        spec = app._type_spec("crag")
        assert not app.place_and_raise(spec)
        await _settle(pilot)
        ghost = app.desktop.ghost
        assert isinstance(ghost, Ghost) and app.focused is ghost and "crag" not in app.custom_specs
        assert "░" in str(ghost.render())
        start = ghost.geom
        free = not ghost.blocked
        await pilot.press("left", "shift+up")
        await _settle(pilot)
        moved = ghost.geom
        assert (moved.x, moved.y) == (max(start.x - 1, 0), max(start.y - 3, 0))
        if ghost.blocked or not free:                       # keep the test independent of the layout
            ghost.taken = []
            ghost.place(moved)
        await pilot.press("enter")
        await _settle(pilot)
        assert app.desktop.ghost is None and "crag" in app.custom_specs
        w, h = app.desktop.hut_room
        expected = list(geo.hut_to_frac(moved.x, moved.y, w, h, moved.w, moved.h))
        assert app.scroll.building("crag").hut == expected
        hut = app.desktop.huts["crag"]
        assert (hut.geom.x, hut.geom.y) == (moved.x, moved.y)


@pytest.mark.asyncio
async def test_esc_builds_nothing_and_a_taken_spot_does_not_settle(fake_repo: Path):
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=SIZE) as pilot:
        await _settle(pilot)
        app.place_and_raise(app._type_spec("pit"))
        await _settle(pilot)
        await pilot.press("escape")
        await _settle(pilot)
        assert app.desktop.ghost is None and "pit" not in app.custom_specs

        app.place_and_raise(app._type_spec("pit"))
        await _settle(pilot)
        ghost = app.desktop.ghost
        other = next(h for h in app.desktop.huts.values() if h.display)
        ghost.place(geo.Geom(other.geom.x, other.geom.y, ghost.geom.w, ghost.geom.h))
        assert ghost.blocked and ghost.has_class("-blocked")
        await pilot.press("enter")
        await _settle(pilot)
        assert app.desktop.ghost is ghost and "pit" not in app.custom_specs     # it will not settle on a hut
        ghost.taken = []
        ghost.place(ghost.geom)
        await pilot.click(Desktop, offset=(ghost.geom.x + ghost.geom.w // 2, ghost.geom.y + ghost.geom.h // 2))
        await _settle(pilot)
        assert app.desktop.ghost is None and "pit" in app.custom_specs


@pytest.mark.asyncio
async def test_without_a_town_the_building_rises_at_once(fake_repo: Path, monkeypatch):
    monkeypatch.setattr(ts, "DEFAULT_VIEW", "tiles")
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=SIZE) as pilot:
        await _settle(pilot)
        assert app.place_and_raise(app._type_spec("pit")) and app.desktop.ghost is None
