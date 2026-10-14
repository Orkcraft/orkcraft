"""Mission 1, Raise the camp (docs/design/first-mission.md §3): quests 1 to 3½, a drill that calls no model."""
from __future__ import annotations

import time
from pathlib import Path

import pytest

from orkcraft.core.mission import Mission
from orkcraft.core.workers.barracks import BarracksWorker
from orkcraft.gui.host import Host
from orkcraft.realm import checkpoint, event_log, jobs, mission


def _until(check, timeout: float = 8.0) -> bool:
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if check():
            return True
        time.sleep(0.05)
    return check()


@pytest.fixture
def no_model(monkeypatch):
    """Any model call fails the test: the drill runs by its script."""
    def refuse(*a, **k):
        raise AssertionError("a model was called in quests 1-3")
    monkeypatch.setattr(jobs, "run_work", refuse)
    monkeypatch.setattr(BarracksWorker, "work_runner", None)
    monkeypatch.setattr(BarracksWorker, "steward_runner", None)


def test_the_camp_is_raised_quest_by_quest_with_a_drill_and_no_model(fake_repo: Path, no_model, monkeypatch):
    checkpoint.ensure(fake_repo)
    host = Host(fake_repo, auto_commit=False)
    town = host.town
    m = Mission(town)
    assert m.view() is None
    m.begin()
    v = m.view()
    assert (v["quest"], v["n"], v["of"], v["press"]) == ("board", 1, 4, "Set up the Task board")

    board = m.raise_it()                                                     # quest 1: a drill card on the board
    card = town.worker(board).card(m.state["card"])
    assert card.title.startswith("Drill") and "drill" in card.body.lower()
    assert m.raise_it() == ""                                                # raised once
    assert m.tick() and m.view()["quest"] == "pool"

    pool = m.raise_it()                                                      # quest 2: an ork asks, the person answers
    w = town.worker(pool)
    assert w.simulated and not w.uses_git
    assert _until(lambda: any(t.status == "asked" for t in w.state.tasks)), [t.status for t in w.state.tasks]
    task = next(t for t in w.state.tasks if t.status == "asked")
    assert mission.DRILL_QUESTION in task.question and not m.tick()
    host.command("act", {"id": pool, "act": "answer", "args": {"task": task.id, "text": "Green"}})
    assert _until(m.tick) and m.view()["quest"] == "gate"                   # the first win
    assert _until(lambda: w.state.task(task.id).status == "done")
    assert _until(lambda: not m.tick() and not (w.state_dir / "drill.json").exists())   # real work again: no script

    gate = m.raise_it()                                                      # quest 3: the result waits at the gate
    g = town.worker(gate)
    assert _until(lambda: g.queue.by_ref(m.state["ref"]) is not None)
    item = g.queue.by_ref(m.state["ref"])
    assert "Drill" in (item.title or item.value) and not m.tick()
    host.command("act", {"id": gate, "act": "accept", "args": {"item": item.id}})
    assert _until(m.tick) and m.view()["quest"] == "office"

    host.command("you.look", {"look": "office"})                             # quest 3½: Office, then Camp
    assert not m.tick()
    host.command("you.look", {"look": "camp"})
    assert m.tick() and m.view() == {"finished": True, "says": mission.DONE_SAYS}
    m.seen_end()
    assert m.view() is None

    got = [(e["event"], e.get("quest")) for e in event_log.read(fake_repo)
           if e["event"].startswith("quest_")]
    assert got == [("quest_started", "board"), ("quest_done", "board"), ("quest_started", "pool"),
                   ("quest_done", "pool"), ("quest_started", "gate"), ("quest_done", "gate"),
                   ("quest_started", "office"), ("quest_done", "office")]
    assert all(isinstance(e.get("seconds"), (int, float)) for e in event_log.read(fake_repo) if e["event"] == "quest_done")
    host.close()


def test_the_mission_is_left_at_any_quest_and_the_town_stays(fake_repo: Path, no_model):
    checkpoint.ensure(fake_repo)
    host = Host(fake_repo, auto_commit=False)
    m = Mission(host.town)
    m.begin()
    board = m.raise_it()
    m.tick()
    m.leave()
    assert m.view() is None and not m.on() and host.town.scroll.building(board) is not None
    assert [(e["event"], e.get("quest")) for e in event_log.read(fake_repo) if e["event"] == "quest_skipped"] \
        == [("quest_skipped", "pool")]
    assert m.raise_it() == "" and not m.tick()
    host.close()


def test_the_onboarding_offers_the_mission_and_it_starts_when_the_town_opens(fake_repo: Path, monkeypatch, no_model):
    """first-mission.md §3: the town step's first choice; the quest log comes once the town is opened."""
    monkeypatch.setenv("ORKCRAFT_ONBOARDING", "1")
    from orkcraft.gui import onboarding
    from orkcraft.gui.host import CommandError
    checkpoint.ensure(fake_repo)
    host = Host(fake_repo, auto_commit=False)
    host.onboarding._finder.join(5)
    host.command("onboarding.tools", {"next": True})
    host.command("onboarding.role", {"role": "marketing"})
    o = host.command("onboarding.town", {"mission": True})
    assert o["raising"]["title"] == "Your camp" and host.snapshot()["mission"] is None
    now = 1000.0
    for _ in range(30):
        now += onboarding.RAISE_STEP_S
        host.tick(now)
    host.command("onboarding.close", {})
    m = host.snapshot()["mission"]
    assert m["quest"] == "board" and m["press"] == "Set up the Task board"
    board = host.command("mission.raise", {})
    assert host.town.scroll.building(board) is not None
    with pytest.raises(CommandError):
        host.command("mission.raise", {})                                   # once
    host.tick()
    assert host.snapshot()["mission"]["quest"] == "pool"
    host.command("mission.leave", {})
    assert host.snapshot()["mission"] is None
    host.close()
