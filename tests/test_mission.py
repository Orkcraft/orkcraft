"""Mission 1, Raise the camp (docs/design/first-mission.md §3): quests 1 to 4, a drill that calls no model."""
from __future__ import annotations

import time
from pathlib import Path

import pytest

from orkcraft.core.mission import Mission
from orkcraft.core.workers.barracks import BarracksWorker
from orkcraft.gui.host import Host
from orkcraft.realm import checkpoint, event_log, growth, items, jobs, mission, mission_work


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
    assert (v["quest"], v["n"], v["of"], v["press"]) == ("board", "1", "4", "Set up the Task board")

    board = m.raise_it()                                                     # quest 1: a drill card on the board
    card = town.worker(board).card(m.state["card"])
    assert card.title.startswith("Drill") and "drill" in card.body.lower() and card.column == "todo"   # on the siding
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
    assert m.view()["press"] == mission.LIFT
    s = m.state
    s.pop("held", None)                                                      # lifted before a tick saw it waiting
    m._save(s)
    emitted = []
    monkeypatch.setattr(type(g), "emit", lambda self, *a, **k: emitted.append(a) or True)
    assert host.command("mission.raise", {}) == gate                         # the barrier lifted: the person's pass
    assert emitted == [] and g.queue.by_ref(m.state["ref"]) is None          # on no road: nothing leaves the town
    monkeypatch.undo()
    assert _until(m.tick) and m.view()["quest"] == "listen"
    f = m.view()["finale"]                                                   # the drill rolls on, free
    assert (f["gate"], f["out"], f["chip"]) == (gate, "", mission.FINALE_CHIP) and 0 <= f["age"] < mission.FINALE_S
    assert host.snapshot()["mission"]["finale"]["gate"] == gate

    v = m.view()                                                             # before quest 4: the hooks, asked once
    assert v["press"] == "" and v["hooks"]["files"][0]["file"] == ".claude/settings.json"
    assert any("Security reviewer" in ln for ln in v["hooks"]["files"][0]["lines"])
    assert "orkline hooks remove" in v["hooks"]["take_back"] and "never blocks" in v["hooks"]["fail_open"]
    assert m.raise_it() == "" and not (fake_repo / ".claude" / "settings.json").exists()   # nothing written unasked
    assert ".claude/settings.json" in host.command("mission.hooks", {"yes": True})
    assert m.view()["hooks"] is None and m.view()["press"] == "Set up External listeners"

    found = [mission_work.Item("FIXME in src/app.py: the greeting is wrong", "src/app.py:1", 0),
             mission_work.Item("TODO in docs/notes.md: more notes", "docs/notes.md:3", 1)]
    monkeypatch.setattr(mission_work, "found", lambda root: ("todo", found))
    tower = m.raise_it()                                                     # quest 4: read only, cards on the board
    assert town.scroll.building(tower) is not None
    assert _until(m.tick) and m.view() == {"finished": True, "says": mission.DONE_SAYS}   # quest 4 was the last
    b = town.worker(board)
    assert [c.title for c in b.cards if c.column == "todo" and c.id != m.state["card"]] == [i.title for i in found]
    assert not b.config.get("send_new")                                      # they wait on the board until sent

    machine = town.machine                                                   # a deed per quest, Mission 1 done
    machine.growth = {"stage": 1, "deeds": {}}
    fresh = growth.settle(town.scroll, fake_repo, machine)                   # stage 2, the first item
    assert {"quest.board", "quest.pool", "quest.gate", "quest.listen", "mission"} <= set(machine.growth["deeds"])
    assert not {"quest.office", "quest.two"} & set(machine.growth["deeds"])
    assert machine.growth["stage"] == 2 and any(n.kind == "stage" for n in fresh)
    assert "first-cart" in items.settle(town.scroll, fake_repo, machine)
    assert items.earned(fake_repo)["first-cart"]["at"] and items.settle(town.scroll, fake_repo, machine) == []   # once
    m.seen_end()
    assert m.view() is None

    got = [(e["event"], e.get("quest")) for e in event_log.read(fake_repo)
           if e["event"].startswith("quest_")]
    assert got == [(f"quest_{x}", q) for q in mission.IDS for x in ("started", "done")]
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
    assert "mission_done" not in m.state                                     # left early: Mission 1 is not done
    host.close()


def test_the_finale_goes_to_the_publisher_and_mission_1_is_done_with_quest_4(fake_repo: Path, no_model):
    """Left at quest 4, Mission 1 is not done; done with it, it is. The finale's cart is launched by the town's
    Publisher when it has one."""
    checkpoint.ensure(fake_repo)
    host = Host(fake_repo, auto_commit=False)
    m = Mission(host.town)
    m.begin()
    out = host.command("town.build", {"type": "catapult"})
    s = m.state
    s.update({"quest": "gate", "done": ["board", "pool"], "built": {"gate": out}})
    m._save(s)
    m._reached = lambda s, q: True                                           # the gate passed (the flow's own test above)
    assert m.tick() and m.state["finale"]["out"] == out
    m._reached = lambda s, q: q != "listen"
    while m.tick():
        pass
    assert m.view()["quest"] == "listen" and "mission_done" not in m.state
    m.leave()
    assert "mission_done" not in m.state and "listen" in m.state["skipped"]
    m.begin()
    s = m.state
    s.update({"quest": "listen", "done": ["board", "pool", "gate"]})
    m._save(s)
    m._reached = lambda s, q: True
    assert m.tick() and m.state["mission_done"] and m.state["finished"]
    machine = host.town.machine
    machine.growth = {"stage": 1, "deeds": {}}
    growth.settle(host.town.scroll, fake_repo, machine)
    assert machine.growth["stage"] == 2 and "first-cart" in items.settle(host.town.scroll, fake_repo, machine)
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


def test_quest_4_reads_github_with_gh_else_the_todo_lines(fake_repo: Path):
    """Read only, no model: the person's notifications first (a review asked first), then their issues, no doubles;
    without GitHub, the tracked TODO and FIXME lines, FIXME first."""
    import json
    import subprocess
    from types import SimpleNamespace
    calls = []

    def gh(cmd, **kw):
        calls.append(cmd)
        if cmd[:2] == ["git", "-C"]:
            return SimpleNamespace(returncode=0, stdout="git@github.com:acme/app.git\n")
        if cmd[:2] == ["gh", "api"]:
            return SimpleNamespace(returncode=0, stdout=json.dumps([
                {"reason": "subscribed", "subject": {"title": "Release notes", "type": "Issue"}},
                {"reason": "review_requested", "subject": {"title": "Fix login", "type": "PullRequest"}}]))
        if "--assignee" in cmd:
            return SimpleNamespace(returncode=0, stdout=json.dumps([{"number": 7, "title": "Fix login", "url": "u"},
                                                                    {"number": 8, "title": "Dark mode", "url": "u8"}]))
        return SimpleNamespace(returncode=0, stdout="[]")
    source, items = mission_work.found(fake_repo, runner=gh, which=lambda b: "/usr/bin/gh")
    assert source == "github" and [i.title for i in items] == ["Fix login", "Dark mode", "Release notes"]
    assert all(c[0] in ("git", "gh") and c[1] in ("-C", "api", "issue") for c in calls)
    assert all(c[2] == "list" for c in calls if c[:2] == ["gh", "issue"])           # read only

    (fake_repo / "src" / "app.py").write_text("print('hello')  # TODO: say it louder\n# FIXME broken greeting\n")
    subprocess.run(["git", "add", "."], cwd=fake_repo, check=True, capture_output=True)
    source, items = mission_work.found(fake_repo, which=lambda b: None)         # no gh, no GitHub origin
    assert source == "todo" and [i.title for i in items] == ["FIXME in src/app.py: broken greeting",
                                                              "TODO in src/app.py: say it louder"]


def test_the_hooks_are_shown_before_they_are_written_and_taken_back_in_settings_or_the_cli(fake_repo: Path, capsys):
    from orkcraft import cli
    from orkcraft.hooks import install as hooks_install
    shown = hooks_install.preview(fake_repo, agy=False)
    assert shown[0]["file"] == ".claude/settings.json" and shown[0]["tool"] == "Claude Code"
    assert not (fake_repo / ".claude").exists()                                 # a preview writes nothing
    checkpoint.ensure(fake_repo)
    host = Host(fake_repo, auto_commit=False)
    assert host.command("town.settings", {})["hooks"] is False
    assert host.command("town.settings.set", {"hooks": True})["hooks"] is True
    assert hooks_install.installed(fake_repo)
    assert host.command("town.settings.set", {"hooks": False})["hooks"] is False
    host.command("town.settings.set", {"hooks": True})
    host.close()
    assert cli.main(["--repo", str(fake_repo), "hooks", "remove", "--no-agy-global"]) == 0
    assert "removed: " in capsys.readouterr().out and not hooks_install.installed(fake_repo)


def test_with_the_plugin_in_quest_4_asks_nothing(fake_repo: Path):
    """distribution.md §3: installing Orkline's Claude Code plugin was the yes to the session log; the Security
    reviewer (the Warder) stays the person's own yes."""
    import json
    import os
    from orkcraft.hooks import install as hooks_install
    home = Path(os.environ["CLAUDE_CONFIG_DIR"])
    home.mkdir(parents=True, exist_ok=True)
    (home / "settings.json").write_text(json.dumps({"enabledPlugins": {hooks_install.PLUGIN_ID: True}}))
    claude = next(f for f in hooks_install.preview(fake_repo, agy=False) if f["tool"] == "Claude Code")
    assert len(claude["lines"]) == 1 and "Security reviewer" in claude["lines"][0]   # the session log is the plugin's
    checkpoint.ensure(fake_repo)
    host = Host(fake_repo, auto_commit=False)
    m = Mission(host.town)
    mission.save(fake_repo, {"on": True, "quest": "listen", "built": {}, "done": []})
    assert m.view()["hooks"] is None and m.view()["press"] == "Set up External listeners"
    host.close()


def test_an_old_state_at_the_office_quest_moves_on_to_listen(fake_repo: Path):
    """Spec 27: Mission 1 lost its Office quest; a state saved at it goes on to quest 4, nothing earned is lost."""
    mission.save(fake_repo, {"on": True, "quest": "office", "office_seen": True, "built": {"board": "b"},
                             "done": ["board", "pool", "gate"], "started": {"gate": "2026-10-01T10:00:00+00:00"}})
    s = mission.load(fake_repo)
    assert (s["on"], s["quest"], s["done"], s["office_seen"]) == (True, "listen", ["board", "pool", "gate"], True)
    assert s["started"]["gate"] and s["started"]["listen"] and s["built"] == {"board": "b"}
    checkpoint.ensure(fake_repo)
    host = Host(fake_repo, auto_commit=False)
    v = Mission(host.town).view()
    assert (v["quest"], v["n"], v["of"]) == ("listen", "4", "4")
    host.close()


def test_an_old_state_at_two_or_with_a_two_key_is_mission_1_done(fake_repo: Path):
    """Spec 27: the old quest 5 left Mission 1; a state at it, or with its key, counts the mission as done, and
    the deeds earned stay."""
    old = ["board", "pool", "gate", "office", "listen"]
    mission.save(fake_repo, {"on": True, "quest": "two", "two": ["b:1", "b:2"], "done": old, "built": {}})
    s = mission.load(fake_repo)
    assert (s["on"], s["quest"], s["finished"]) == (False, "", True) and s["mission_done"]
    assert s["two"] == ["b:1", "b:2"] and s["done"] == old                  # nothing earned is lost
    checkpoint.ensure(fake_repo)
    host = Host(fake_repo, auto_commit=False)
    assert Mission(host.town).view() == {"finished": True, "says": mission.DONE_SAYS}
    machine = host.town.machine
    machine.growth = {"stage": 1, "deeds": {}}
    growth.settle(host.town.scroll, fake_repo, machine)
    assert {"quest.office", "mission"} <= set(machine.growth["deeds"]) and machine.growth["stage"] == 2   # Two faces stays
    host.close()
    mission.save(fake_repo, {"on": False, "quest": "", "two": ["b:1"], "done": old, "skipped": ["two"]})
    assert mission.load(fake_repo)["mission_done"] and "finished" not in mission.load(fake_repo)
