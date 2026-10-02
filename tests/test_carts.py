"""Carts and coins (T1098 stage 6): real events travel the roads, statuses, jams, counters, modes."""
from __future__ import annotations

import pytest

from orkcraft import scroll as ts
from orkcraft.app import OrkcraftApp
from orkcraft.realm import roads
from orkcraft.realm.pipes import Payload
from orkcraft.widgets.carts import MAX_MOVING, CartSprite, Coin, Counter
from orkcraft.wm.geometry import Geom

SIZE = (200, 50)
KEY = "loot:town_hall-selection"


def node(nid: str) -> Payload:
    return Payload("node", nid, "town_hall", "on_selection_change", nid)


async def _layout(app, pilot, carts: str = "all"):
    for _ in range(3):
        await pilot.pause()
    for w in app.desktop.windows:
        if w.window_id not in ("town_hall", "loot", "systems") and not w.hidden:
            w.display = False
    app.desktop.get_window("town_hall").apply_geom(Geom(0, 0, 50, 30))
    app.desktop.get_window("loot").apply_geom(Geom(120, 5, 60, 30))
    limits = app.desktop.get_window("systems")
    limits.display = True
    limits.apply_geom(Geom(60, 22, 40, 10))
    app.scroll.preferences["carts"] = carts
    app.desktop.set_active(None)
    for _ in range(3):
        await pilot.pause()
    app.desktop.traffic.clear()      # the start-up selection already sent a few carts
    # deterministic: no 8 fps timer, the tests move the carts with run_ticks()
    if app.desktop._traffic_timer is not None:
        app.desktop._traffic_timer.pause()
    app.desktop.traffic_changed = lambda: None
    await pilot.pause()


def sprites(app):
    return list(app.desktop.query(CartSprite))


def run_ticks(app, n):
    for _ in range(n):
        app.desktop.traffic.tick()


@pytest.mark.asyncio
async def test_a_delivered_cart_travels_and_vanishes(fake_repo):
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    ts.subscribe(app.scroll, "loot", "town_hall", "on_selection_change")
    async with app.run_test(size=SIZE) as pilot:
        await _layout(app, pilot)
        app.roads.emit(node("T1001"))
        await pilot.pause()
        [m] = app.desktop.traffic.moving
        path = app.desktop.road_paths[KEY]
        assert m.status == "delivered" and (m.sprite.styles.offset.x.value, m.sprite.styles.offset.y.value) == path.cells[0]
        run_ticks(app, 5)
        assert 0 < m.pos < len(path.cells) - 1                       # on its way
        run_ticks(app, 20)
        await pilot.pause()
        assert app.desktop.traffic.moving == [] and not sprites(app)


@pytest.mark.asyncio
async def test_filtered_turns_back_held_waits(fake_repo):
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    ts.subscribe(app.scroll, "loot", "town_hall", "on_selection_change", {"node_status": ["done"]})
    ts.add_handler(app.scroll, "systems", "Tally", kind="script", script={"path": ".orkcraft/scripts/tally.py"})
    ts.subscribe(app.scroll, "systems", "town_hall", "on_selection_change", handler="tally")
    async with app.run_test(size=SIZE) as pilot:
        await _layout(app, pilot)
        app.roads.emit(node("T1001"))                              # todo → filtered on the loot road
        await pilot.pause()
        by = {m.key: m for m in app.desktop.traffic.moving}
        filtered, held = by[KEY], by["systems:town_hall-selection"]
        assert (filtered.status, held.status) == ("filtered", "held")
        run_ticks(app, 2)
        assert filtered.back or filtered.pos >= 1
        run_ticks(app, 20)
        assert filtered not in app.desktop.traffic.moving              # came back and vanished
        assert held in app.desktop.traffic.moving and held.waiting == "held"
        assert held.pos == len(app.desktop.road_paths[held.key].cells) - 1   # at the entry gate
        run_ticks(app, 20)
        assert app.desktop.traffic.moving == []


@pytest.mark.asyncio
async def test_too_many_carts_become_a_counter(fake_repo):
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    ts.subscribe(app.scroll, "loot", "town_hall", "on_selection_change")
    async with app.run_test(size=SIZE) as pilot:
        await _layout(app, pilot)
        for i in range(MAX_MOVING + 3):
            app.roads.emit(node(f"T{1000 + i}"))
        await pilot.pause()
        assert len(app.desktop.traffic.moving) == MAX_MOVING
        [counter] = list(app.desktop.query(Counter))
        assert "🛒×3" in str(counter.render())
        run_ticks(app, 60)
        await pilot.pause()
        assert not list(app.desktop.query(Counter)) and not app.desktop.traffic.moving


@pytest.mark.asyncio
async def test_jam_waits_while_the_handler_runs_and_errors_turn_red(fake_repo):
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    ts.add_handler(app.scroll, "loot", "Seer", run={"quiet_s": 3600})
    ts.subscribe(app.scroll, "loot", "town_hall", "on_selection_change", handler="seer")
    async with app.run_test(size=SIZE) as pilot:
        await _layout(app, pilot)
        st = app.roads.state("loot", "seer")
        st.running = True                                             # a run is under way
        app.roads.emit(node("T1001"))
        app.roads.emit(node("T1002"))
        await pilot.pause()
        run_ticks(app, 20)
        await pilot.pause()
        assert all(m.waiting == "jam" for m in app.desktop.traffic.moving) and len(app.desktop.traffic.moving) == 2
        assert "🛒×2" in str(list(app.desktop.query(Counter))[0].render())
        app.on_handler_run(roads.HandlerRun("loot", "seer", "agent", "r", 0, outcome="error",
                                            error="boom", roads=("town_hall-selection",)))
        await pilot.pause()
        assert {m.status for m in app.desktop.traffic.moving} == {"error"}
        st.running = False
        run_ticks(app, 40)
        assert app.desktop.traffic.moving == []


@pytest.mark.asyncio
async def test_modes_and_coins(fake_repo):
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    ts.subscribe(app.scroll, "loot", "town_hall", "on_selection_change")
    async with app.run_test(size=SIZE) as pilot:
        await _layout(app, pilot, carts="selected")
        app.roads.emit(node("T1001"))                                 # nothing selected → no cart
        await pilot.pause()
        assert not app.desktop.traffic.moving
        app.desktop.set_active(app.desktop.get_window("town_hall"))
        await pilot.pause()
        app.roads.emit(node("T1001"))
        await pilot.pause()
        assert len(app.desktop.traffic.moving) == 1
        await pilot.press("alt+c")                                    # selected → all
        assert app.scroll.preferences["carts"] == "all"
        await pilot.press("alt+c")                                    # all → off: carts vanish
        await pilot.pause()
        assert app.scroll.preferences["carts"] == "off" and not sprites(app)
        app.roads.emit(node("T1001"))
        assert not app.desktop.traffic.moving
        app.scroll.preferences["carts"] = "all"
        app.on_handler_run(roads.HandlerRun("loot", "seer", "agent", "r", 0, outcome="done", cost_usd=0.04))
        await pilot.pause()
        assert list(app.desktop.query(Coin))
        run_ticks(app, 20)
        await pilot.pause()
        assert not list(app.desktop.query(Coin))


@pytest.mark.asyncio
async def test_clicking_a_cart_tells_what_it_carries(fake_repo, monkeypatch):
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    ts.subscribe(app.scroll, "loot", "town_hall", "on_selection_change")
    notes = []
    async with app.run_test(size=SIZE) as pilot:
        await _layout(app, pilot)
        monkeypatch.setattr(app, "notify", lambda msg, **kw: notes.append(msg))
        app.roads.emit(node("T1001"))
        await pilot.pause()
        [sprite] = sprites(app)
        await pilot.click(sprite)
        assert any("delivered" in n and "T1001" in n for n in notes)


@pytest.mark.asyncio
async def test_the_real_timer_moves_carts_and_sleeps_when_idle(fake_repo):
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    ts.subscribe(app.scroll, "loot", "town_hall", "on_selection_change")
    async with app.run_test(size=SIZE) as pilot:
        for _ in range(3):
            await pilot.pause()
        for w in app.desktop.windows:
            if w.window_id not in ("town_hall", "loot") and not w.hidden:
                w.display = False
        app.desktop.get_window("town_hall").apply_geom(Geom(0, 0, 50, 30))
        app.desktop.get_window("loot").apply_geom(Geom(120, 5, 60, 30))
        app.scroll.preferences["carts"] = "all"
        for _ in range(3):
            await pilot.pause()
        app.roads.emit(node("T1001"))
        assert app.desktop.traffic.moving
        for _ in range(40):
            await pilot.pause(0.1)
            if not app.desktop.traffic.busy:
                break
        assert not app.desktop.traffic.busy
        await pilot.pause(0.3)
        assert app.desktop._traffic_timer._active.is_set() is False     # paused: no redraws when idle
