"""Mission 1, Raise the camp (docs/design/first-mission.md §3): quests 1 to 3½, a drill that calls no model."""
from __future__ import annotations

import time
from pathlib import Path

import pytest

from orkcraft.core.mission import Mission
from orkcraft.core.workers.barracks import BarracksWorker
from orkcraft.gui.host import Host
from orkcraft.realm import checkpoint, event_log, jobs, mission, mission_work
from tests.pool_fakes import FakeGit, Steward


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
    assert (v["quest"], v["n"], v["of"], v["press"]) == ("board", "1", "5", "Set up the Task board")

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
    assert m.tick() and m.view()["quest"] == "listen"

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
    assert _until(m.tick) and m.view()["quest"] == "two"
    b = town.worker(board)
    assert [c.title for c in b.cards if c.column == "todo" and c.id != m.state["card"]] == [i.title for i in found]
    assert not b.config.get("send_new")                                      # they wait on the board until sent

    v = m.view()                                                             # quest 5: its price first
    assert v["press"] == "Send two cards" and "$2.00" in v["cost"] and "Claude Code" in v["cost"]
    runs = []
    monkeypatch.setattr(BarracksWorker, "work_runner", staticmethod(
        lambda harness, prompt, workdir, cancel, model, env, resume: (runs.append(prompt) or "done it", 0.05, 100, "")))
    monkeypatch.setattr(BarracksWorker, "steward_runner", Steward())
    monkeypatch.setattr(BarracksWorker, "git", FakeGit())
    assert m.raise_it() == pool and w.config["max_orcs"] == 2 and w.config["worktrees"] is True
    assert w.config["budget_usd"] == 2.0 and m.raise_it() == ""             # sent once
    assert _until(lambda: m.tick(), timeout=15), (m.state, [t.status for t in w.state.tasks])
    assert len(runs) == 2 and "budget_usd" not in w.config                    # the mission's budget ends with it
    assert all(g.queue.by_ref(ref) is not None for ref in m.state["two"])  # both wait for the person
    assert m.view() == {"finished": True, "says": mission.DONE_SAYS}
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


def test_with_the_plugin_in_quest_4_asks_nothing_and_quest_5_still_asks_for_the_security_reviewer(fake_repo: Path):
    """distribution.md §3: installing Orkline's Claude Code plugin was the yes to the session log; the Security
    reviewer (the Warder) stays the person's own yes, asked before quest 5."""
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
    mission.save(fake_repo, {"on": True, "quest": "two", "built": {}, "done": []})
    assert m.view()["hooks"] is not None                                    # quest 5: the Warder, asked
    host.close()
