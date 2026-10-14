"""Mission 1 on Camp v3's stations in a real browser (docs/design/first-mission.md §9): the drill cart stands on the
Task board's siding; quest 3's pass lifts the Review gate's barrier; the finale rolls the passed drill on, "Drill ·
free" above it, along the line (no Publisher) or launched by the Publisher. Screenshots go to docs/design/img/m1/
when ORKCRAFT_SHOTS is set."""
from __future__ import annotations

import datetime as dt
import os
from pathlib import Path

import pytest

pytest.importorskip("playwright.sync_api")

from orkcraft.core.workers.barracks import BarracksWorker  # noqa: E402
from orkcraft.realm import jobs, mission  # noqa: E402
from tests.test_gui_browser import WAIT_MS, camp_look, gui, page  # noqa: E402,F401  (fixtures)
from tests.test_gui_camp_browser import _building, _call, _clear  # noqa: E402

pytestmark = pytest.mark.browser

SHOTS = Path(__file__).resolve().parent.parent / "docs" / "design" / "img" / "m1"


def _shot(pg, name: str) -> None:
    if os.environ.get("ORKCRAFT_SHOTS"):
        SHOTS.mkdir(parents=True, exist_ok=True)
        pg.screenshot(path=str(SHOTS / f"{name}.png"))


@pytest.fixture
def no_model(monkeypatch):
    def refuse(*a, **k):
        raise AssertionError("a model was called in quests 1-3")
    monkeypatch.setattr(jobs, "run_work", refuse)
    monkeypatch.setattr(BarracksWorker, "work_runner", None)
    monkeypatch.setattr(BarracksWorker, "steward_runner", None)


def _src(pg, bid: str) -> str:
    return _building(pg, bid).locator("img").first.get_attribute("src") or ""


def test_the_drill_waits_on_the_siding_the_barrier_lifts_and_the_drill_rolls_on(camp_look, gui, no_model):
    server, _ = gui
    pg = camp_look
    _clear(pg)
    host = server.host
    host.town.call(host.mission.begin)
    log = pg.locator(".gui-warchief__setup", has_text="Mission 1 · quest 1 of 5")
    log.wait_for(state="visible", timeout=WAIT_MS)
    log.get_by_role("button", name="Set up the Task board").click()          # quest 1: the booth, the drill on its siding
    pg.locator(".gui-warchief__setup", has_text="quest 2 of 5").wait_for(state="visible", timeout=WAIT_MS)
    built = lambda: host.mission.mission.state["built"]                     # noqa: E731
    board = built()["board"]
    siding = pg.locator(f'.gui-camp__siding[data-id="{board}"] img')
    siding.first.wait_for(state="attached", timeout=WAIT_MS)
    assert siding.count() == 1 and _src(pg, board).endswith("/buildings/fields.png")
    _shot(pg, "1-siding")

    pg.locator(".gui-warchief__setup").get_by_role("button", name="Set up the Agent pool").click()   # quest 2
    pg.wait_for_function("() => document.querySelector('.gui-warchief__setup') && "
                         "!document.querySelector('.gui-warchief__setup button.primary')", timeout=WAIT_MS)
    w = host.town.worker(built()["pool"])
    for _ in range(100):
        task = next((t for t in w.state.tasks if t.status == "asked"), None)
        if task:
            break
        pg.wait_for_timeout(100)
    assert task is not None
    _call(pg, "act", {"id": w.building_id, "act": "answer", "args": {"task": task.id, "text": "Green"}})
    log = pg.locator(".gui-warchief__setup", has_text="quest 3 of 5")
    log.wait_for(state="visible", timeout=WAIT_MS)
    log.get_by_role("button", name="Set up the Review gate").click()         # quest 3: the drill stops at the barrier
    lift = pg.locator(".gui-warchief__setup").get_by_role("button", name="Lift the barrier")
    lift.wait_for(state="visible", timeout=WAIT_MS)
    gate = built()["gate"]
    pg.wait_for_function(f"() => (document.querySelector('.gui-camp__building[data-id=\"{gate}\"] img') || {{}}).src"
                         f"?.endsWith('/buildings/loot_vault.png')", timeout=WAIT_MS)   # the barrier down
    pg.wait_for_timeout(1500)
    _shot(pg, "2-barrier-down")

    lift.click()                                                              # the person's pass lifts it
    finale = pg.locator(".gui-camp__finale")
    finale.wait_for(state="attached", timeout=WAIT_MS)
    assert finale.get_attribute("data-out") == "line"                         # no Publisher: it leaves along the line
    assert finale.locator(".gui-camp__launch-chip").first.inner_text() == "Drill · free"
    pg.wait_for_function(f"() => document.querySelector('.gui-camp__building[data-id=\"{gate}\"] img')"
                         f".src.endsWith('/buildings/loot_vault-up.png')", timeout=WAIT_MS)   # the barrier up
    log = pg.locator(".gui-warchief__setup", has_text="quest 3½ of 5")
    log.wait_for(state="visible", timeout=WAIT_MS)
    assert mission.FINALE_SAYS in log.inner_text()
    pg.wait_for_timeout(1200)
    _shot(pg, "3-rolls-on")
    assert host.town.worker(gate).queue.by_ref(host.mission.mission.state["ref"]) is None

    log.get_by_role("button", name="Skip the mission").click()
    pg.wait_for_function("() => !document.querySelector('.gui-warchief__setup')", timeout=WAIT_MS)
    _clear(pg)


def test_the_finale_is_launched_by_the_publisher_when_the_town_has_one(camp_look, gui):
    server, _ = gui
    pg = camp_look
    _clear(pg)
    board = _call(pg, "town.build", {"type": "fields"})
    gate = _call(pg, "town.build", {"type": "loot"})
    out = _call(pg, "town.build", {"type": "catapult"})
    pg.keyboard.press("Escape")
    _building(pg, out).wait_for(state="visible", timeout=WAIT_MS)
    at = dt.datetime.now().astimezone().isoformat(timespec="milliseconds")
    mission.save(server.host.town.repo_root, {"on": True, "quest": "office", "done": ["board", "pool", "gate"],
                                              "built": {"board": board, "gate": gate},
                                              "finale": {"at": at, "gate": gate, "out": out}})
    server.host.town.call(server.host.on_change)
    finale = pg.locator('.gui-camp__finale[data-out="publisher"]')
    finale.wait_for(state="attached", timeout=WAIT_MS)
    assert finale.locator(".gui-camp__launch.is-drill .gui-camp__launch-chip").text_content() == "Drill · free"
    pg.wait_for_timeout(1500)
    _shot(pg, "4-publisher")
    pg.locator(".gui-warchief__setup").get_by_role("button", name="Skip the mission").click()
    pg.wait_for_function("() => !document.querySelector('.gui-warchief__setup')", timeout=WAIT_MS)
    _clear(pg)
