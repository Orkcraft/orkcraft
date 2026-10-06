"""The night in the GUI (gui/nightly.py, core/retros.py): the retros' proposals answered in the Town Hall,
the orks' own changes in quiet hours by each building's autonomy, probation, the morning's list."""
from __future__ import annotations

import datetime as dt
import time
from pathlib import Path

import pytest

from orkcraft import schedule, scroll as ts, settings
from orkcraft.core import bus, retros
from orkcraft.gui.host import Host
from orkcraft.realm import checkpoint, evolution, feedback, optimize, weekly
from tests.test_optimize import ORDERS

SHORT = "Summarise the PR, flag risk, give a verdict."


def _host(repo: Path, level: int = 1) -> Host:
    settings.save(settings.MachineSettings(onboarded=True, autonomy=level, quiet=schedule.DEFAULT_QUIET))
    checkpoint.ensure(repo)
    return Host(repo, auto_commit=False)


def _proposal(host: Host, repo: Path, hours_ago: float = 0.0) -> optimize.Proposal:
    ts.add_handler(host.town.scroll, "town_hall", "Seer", kind="agent", orders=ORDERS)
    host.town.save()
    host.town.checkpoint("update", "town_hall", "hire Seer")
    p = optimize.Proposal("p1", (dt.datetime.now() - dt.timedelta(hours=hours_ago)).isoformat(timespec="seconds"),
                          "town_hall", "shrink", "orc:seer", ORDERS, SHORT, "same job, fewer words")
    optimize.save(repo, p)
    return p


def _orders(host: Host) -> str:
    return host.town.scroll.building("town_hall").garrison.handler("seer").orders


def _until(cond, n: int = 150) -> None:
    for _ in range(n):
        if cond():
            return
        time.sleep(0.02)
    assert cond()


@pytest.fixture
def quiet(monkeypatch):
    monkeypatch.setattr(schedule, "quiet_now", lambda m, now=None: True)


def test_an_unchained_building_gets_its_proposal_applied_in_quiet_hours(fake_repo: Path, quiet):
    host = _host(fake_repo)                                       # 📜 the town's level applies nothing
    _proposal(host, fake_repo)
    host.town.scroll.building("town_hall").autonomy = "free"
    toasts = []
    host.town.bus.subscribe(bus.TOAST, lambda **k: toasts.append(k))
    host._night()
    _until(lambda: _orders(host) == SHORT and evolution.load(fake_repo) and not host.night.evolve_busy)
    [change] = evolution.load(fake_repo)
    assert change.by == "orcs" and change.status == "probation" and change.sha
    assert optimize.proposals(fake_repo)[0].status == "applied"
    assert not any("applied" in t["message"] for t in toasts)     # hushed: the morning's list tells
    words = retros.morning_words(host.town)
    assert "shrink orc:seer" in words and retros.morning_words(host.town) == ""     # seen once


def test_a_building_in_chains_keeps_its_proposal_waiting(fake_repo: Path, quiet):
    host = _host(fake_repo, level=3)
    _proposal(host, fake_repo)
    host.town.scroll.building("town_hall").autonomy = "chains"
    host._night()
    time.sleep(0.3)
    assert _orders(host) == ORDERS and optimize.pending(fake_repo)


def test_the_town_hall_applies_or_dismisses_a_proposal(fake_repo: Path):
    host = _host(fake_repo)
    p = _proposal(host, fake_repo)
    hall = host.town.worker("town_hall")
    assert next(r for r in hall.hall()["proposals"] if r["id"] == "p1")["status"] == "pending"
    host.command("act", {"id": "town_hall", "act": "proposal", "args": {"id": p.id, "choice": "dismiss"}})
    assert optimize.pending(fake_repo) == [] and _orders(host) == ORDERS
    p2 = optimize.Proposal("p2", p.ts, "town_hall", "shrink", "orc:seer", ORDERS, SHORT, "fewer words")
    optimize.save(fake_repo, p2)
    host.command("act", {"id": "town_hall", "act": "proposal", "args": {"id": "p2", "choice": "apply"}})
    assert _orders(host) == SHORT and evolution.load(fake_repo)[0].by == "you"


def test_a_declined_weekly_item_is_never_applied_by_the_orks(fake_repo: Path, quiet):
    host = _host(fake_repo, level=3)
    _proposal(host, fake_repo)
    optimize.save(fake_repo, optimize.Proposal("p1", dt.datetime.now().isoformat(), "town_hall", "shrink", "orc:seer",
                                               ORDERS, SHORT, "x", status="dismissed"))
    report = weekly.Report(dt.datetime.now().isoformat(timespec="seconds"), "a week",
                           [weekly.Item(1, "shorter Seer", "fewer words", "shrink", "town_hall", {"target": "orc:seer"},
                                        after=SHORT, before=ORDERS)])
    weekly.save(fake_repo, report)
    assert [c["key"] for c in host.night.candidates(3)] == [f"w{report.ts[:10]}-1"]
    host.command("act", {"id": "town_hall", "act": "weekly", "args": {"n": 1, "choice": "decline"}})
    assert host.night.candidates(3) == [] and weekly.latest(fake_repo).declined == [1]
    assert host.town.worker("town_hall").hall()["weekly"]["rows"] == []


def test_probation_takes_a_disliked_change_back(fake_repo: Path, quiet):
    host = _host(fake_repo)
    p = _proposal(host, fake_repo)
    from orkcraft.core import buildings as core_buildings
    assert core_buildings.apply_proposal(host.town, p, by="orcs") and _orders(host) == SHORT
    feedback.dislike(fake_repo, host.town.scroll, "town_hall", "logic", "worse")
    reverted = retros.probation(host.town)
    assert [c.key for c in reverted] == ["p1"] and _orders(host) == ORDERS
    assert evolution.load(fake_repo)[0].status == "reverted"
