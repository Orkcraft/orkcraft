"""🔧 The orcs improve the camp themselves in quiet hours, by autonomy; 24 hours of probation."""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import pytest

from orkcraft import autonomy, schedule, scroll as ts, settings
from orkcraft.realm import awake, evolution, metrics, optimize
from tests.test_optimize import ORDERS

SIZE = (180, 50)
SHORT = "Summarise the PR, flag risk, give a verdict."


def _unanswered(root: Path, p, hours: float = 13, around: bool = True) -> None:
    """The proposal was made `hours` ago; the operator was around all that time (or never)."""
    now = dt.datetime.now().replace(microsecond=0)
    p.ts = (now - dt.timedelta(hours=hours)).isoformat(timespec="seconds")
    optimize.save(root, p)
    f = root / awake.FILE
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps({"spans": [[p.ts, now.isoformat()]] if around else []}), encoding="utf-8")


def test_what_each_level_may_apply():
    assert not any(evolution.allowed(k, 0) for k in evolution.LEVEL_FOR)                 # ⛓️ chains
    assert evolution.allowed("shrink", 1) and evolution.allowed("demote", 1) and evolution.allowed("filter", 1)
    assert not evolution.allowed("script", 1) and evolution.allowed("script", 2)       # ⏳ never spends more
    assert not evolution.allowed("enrich", 1) and evolution.allowed("enrich", 2)
    assert not evolution.allowed("new_road", 1) and evolution.allowed("add_building", 2)
    for never in ("remove_road", "remove_building", "note"):
        assert not evolution.allowed(never, 2)


def test_a_buildings_own_autonomy_takes_the_place_of_the_level():
    town = autonomy.Rules(autonomy.CHAINS, 7, 12)
    b = type("B", (), {"autonomy": "clock", "question_wait": None, "rebuild_wait": 6})()
    rules = autonomy.rules_of(b, town.level, town.wait, town.rebuild)
    assert rules == autonomy.Rules(autonomy.CLOCK, 7, 6)                      # its own level and wait, the town's other
    assert autonomy.rules_of(None, autonomy.FREE, 5, 24) == autonomy.Rules(autonomy.FREE, 5, 24)
    chains, clock, free = (autonomy.Rules(n, 7, 12) for n in (0, 1, 2))
    assert not evolution.may_apply("shrink", chains, 100)                       # ⛓️ only proposes
    assert not evolution.may_apply("shrink", clock, 11.9)                       # 🕰 waits the hours you are around…
    assert evolution.may_apply("shrink", clock, 12)                             # …then a cheaper change lands
    assert not evolution.may_apply("script", clock, 100)                        # silence never spends more
    assert evolution.may_apply("script", free, 0)                               # ⛓️‍💥 at once
    for never in ("remove_road", "remove_building", "note"):
        assert not evolution.may_apply(never, free, 100)


def test_only_the_hours_the_operator_is_around_count(tmp_path: Path):
    day = dt.datetime(2026, 10, 6, 9, 0)
    for minute in range(0, 4 * 60 + 1, 1):                                       # 09:00–13:00, noted every minute
        awake.note(tmp_path, day + dt.timedelta(minutes=minute))
    awake.note(tmp_path, day + dt.timedelta(hours=14))                           # the camp closed for an hour
    awake.note(tmp_path, day + dt.timedelta(hours=15))
    spans = json.loads((tmp_path / awake.FILE).read_text())["spans"]
    assert len(spans) == 3
    assert awake.hours_since(tmp_path, day - dt.timedelta(hours=10), day + dt.timedelta(days=1)) == pytest.approx(4)
    assert awake.hours_since(tmp_path, day + dt.timedelta(hours=2), day + dt.timedelta(days=1)) == pytest.approx(2)
    assert awake.hours_since(tmp_path, "nonsense") == 0


def test_the_ledger(tmp_path: Path):
    mine = evolution.record(tmp_path, evolution.Change("b", "shrink", "daily", "shrink orc:x", by="you"))
    theirs = evolution.record(tmp_path, evolution.Change("b", "chain", "steward", "demote x", by="orcs"))
    assert mine.status == "kept" and mine.seen
    assert [c.id for c in evolution.unseen(tmp_path)] == [theirs.id]
    assert [c.id for c in evolution.on_probation(tmp_path)] == [theirs.id]
    theirs.status = "kept"
    evolution.update(tmp_path, theirs)
    evolution.mark_seen(tmp_path)
    assert evolution.unseen(tmp_path) == [] and evolution.load(tmp_path)[1].status == "kept"


def test_probation_reasons(tmp_path: Path):
    old = (dt.datetime.now() - dt.timedelta(hours=2)).isoformat(timespec="seconds")
    c = evolution.Change("b", "shrink", "daily", "shrink", ts=old)
    assert evolution.verdict(tmp_path, c) is None
    now = dt.datetime.now()
    for i in range(3):
        metrics.record_run(tmp_path, "b", "done", 0.01, 10, now=now - dt.timedelta(hours=3, minutes=i))
    for i in range(3):
        metrics.record_run(tmp_path, "b", "error", 0.01, 10, now=now - dt.timedelta(minutes=10 + i))
    assert "3 of 3 runs failed" in evolution.verdict(tmp_path, c)
    c2 = evolution.Change("other", "shrink", "daily", "shrink", ts=old)
    assert evolution.verdict(tmp_path, c2) is None


def _orders_now(app) -> str:
    return app.scroll.building("town_hall").garrison.handler("seer").orders


async def _camp(app, pilot, fake_repo: Path, orders_after: str = SHORT) -> optimize.Proposal:
    await pilot.pause()
    ts.add_handler(app.scroll, "town_hall", "Seer", kind="agent", orders=ORDERS)
    app.desktop.save()
    app.checkpoint("update", "town_hall", "hire Seer")
    p = optimize.Proposal("p1", dt.datetime.now().isoformat(timespec="seconds"), "town_hall", "shrink", "orc:seer",
                          ORDERS, orders_after, "same job, fewer words")
    optimize.save(fake_repo, p)
    return p


async def _until(pilot, cond, n: int = 80) -> None:
    for _ in range(n):
        if cond():
            return
        await pilot.pause(0.05)
    assert cond()


@pytest.fixture
def quiet(monkeypatch):
    monkeypatch.setattr(schedule, "quiet_now", lambda m, now=None: True)


def _machine(level: int) -> None:
    settings.save(settings.MachineSettings(onboarded=True, autonomy=level, quiet=schedule.DEFAULT_QUIET))
