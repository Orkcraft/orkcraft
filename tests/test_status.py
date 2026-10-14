"""● One status (realm/status.py, core/workers/barracks_status.py; ork-console.md §5, §19; cart-waybill.md §4)."""
from __future__ import annotations

import datetime as dt
import time

from orkcraft.core.workers.barracks import BarracksWorker
from orkcraft.realm import barracks as bk
from orkcraft.realm import status
from tests.pool_fakes import Steward
from tests.test_asking import BLOCK
from tests.test_gui_pool_clan import _host, _raised, _until


def test_every_state_has_a_shape_and_a_word_never_colour_alone():
    for camp, office, _ in status.ORK_STATES.values():
        assert camp and office and camp != office
    assert all(camp and office for camp, office in status.BUILDING_STATES.values())


def test_an_orks_line_names_its_building_and_its_cart():
    s = status.OrkStatus("Grunt", status.TOOL, "Agent pool", "pytest", "Fix the login")
    assert s.line() == "Grunt · Agent pool · running pytest · on «Fix the login»"
    done = status.OrkStatus("Grunt", status.READY, assumptions=2)
    assert done.mark("office") == "Done · 2 assumptions" and done.mark("camp") == "📜 + 2"
    assert status.OrkStatus("Grunt", status.ASKS).attention == 2 and status.OrkStatus("Grunt").mark() == "Zz"


def test_a_wait_says_until_when_and_how_to_skip_it():
    now = time.time()
    w = status.timer(240, skip=status.Skip("start", "Start now", {"task": "t1"}), now=now)
    assert w.line == "starts on its own in 4 min"
    d = w.as_dict(now)
    assert d["in_s"] == 240 and d["skip"] == {"act": "start", "label": "Start now", "args": {"task": "t1"}}
    later = dt.datetime(2026, 10, 14, 9, 0).timestamp()
    assert status.when(3 * 3600, later) == "at 12:00" and status.when(20 * 3600, later).startswith("on Oct 15")
    assert status.when(10) == "in under a minute"


def test_a_building_burns_for_what_blocks_it_and_smoulders_when_stopped():
    assert status.building_state(False, asks_blocking=True) == status.BURNING
    assert status.building_state(False, error=True) == status.BURNING
    assert status.building_state(True, stopped=True) == status.SMOULDERING
    assert status.building_state(True) == status.WORKING and status.building_state(False) == status.IDLE


def test_the_pools_orks_and_tasks_say_their_status(fake_repo, monkeypatch):
    monkeypatch.setattr(BarracksWorker, "work_runner", staticmethod(lambda *a: (BLOCK, 0.1, 10, "s1")))
    monkeypatch.setattr(BarracksWorker, "steward_runner", Steward())
    host = _host(fake_repo)
    bid = _raised(host, "barracks", worktrees=False, providers=["claude"], max_orcs=1)
    w = host.town.worker(bid)
    task = host.command("act", {"id": bid, "act": "task", "args": {"title": "Set up the dev server"}})
    assert _until(lambda: w.state.asked)
    d = host.detail(bid)["data"]
    ork = d["orks"][0]["one_status"]
    assert ork["state"] == "asks" and ork["cart"] == "Set up the dev server" and ork["assumptions"] == 2
    assert ork["line"].startswith(f"Grub · {w._building_title()} · asks you · on «Set up the dev server»")
    asked = d["asked"][0]
    assert asked["wait"]["why"] == "answer" and asked["wait"]["line"].startswith("waits for your answer")
    assert asked["wait"]["skip"]["act"] == "answer" and asked["wait"]["skip"]["args"] == {"task": task}
    assert d["state"] in ("burning", "idle")

    w.state.paused = True
    queued = bk.PoolTask("q1", "Later", "later", status="queued")
    assert w.task_wait(queued).as_dict()["skip"] == {"act": "pause", "label": "Resume", "args": {}}
    w.state.paused = False
    assert w.task_wait(bk.PoolTask("q2", "x", "x", status="queued", wait_for="Grub")).line.startswith("waits for Grub")
    assert w.task_wait(bk.PoolTask("q3", "x", "x", status="planning")).why == "steward"
    assert w.task_wait(bk.PoolTask("q4", "x", "x", status="done")) is None
    first = bk.PoolTask("p1", "Make the schema", "", status="queued", parent="P", sub="a")
    second = bk.PoolTask("p2", "Fill it", "", status="blocked", parent="P", sub="b", after=["a"])
    w.state.queue += [first, second]
    got = w.task_wait(second)
    assert got.line == "after «Make the schema»" and got.skip.act == "open" and got.skip.args == {"task": "p1"}


def test_a_question_with_a_timer_says_when_the_steward_decides(fake_repo, monkeypatch):
    monkeypatch.setattr(BarracksWorker, "steward_runner", Steward())
    host = _host(fake_repo)
    w = host.town.worker(_raised(host, "barracks", worktrees=False))
    monkeypatch.setattr(BarracksWorker, "_ask_minutes", lambda self: 10.0)
    now = time.time()
    t = bk.PoolTask("a1", "x", "x", status="asked", ask_kind="question", waits_since=now - 6 * 60)
    got = w.task_wait(t, now)
    assert got.line == f"waits for your answer · {w.keeper} decides it in 4 min" and round(got.until - now) == 240
