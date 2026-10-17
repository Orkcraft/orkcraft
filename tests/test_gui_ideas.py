"""The board's host commands (spec 29a §6), the phone's allowlist, its compact snapshot and its news."""
from __future__ import annotations

import json
import sys
import time
import types
from pathlib import Path

import pytest

from orkcraft.core import idea_keeper
from orkcraft.gui import ideas as gui_ideas
from orkcraft.gui import mobile
from orkcraft.gui.host import CommandError, Host
from orkcraft.realm import checkpoint, idea_secrets, ideas, jobs

BOARD_COMMANDS = {"ideas.board", "ideas.page", "ideas.add", "ideas.say", "ideas.plan", "ideas.start", "ideas.move",
                  "ideas.edit", "ideas.track_add", "ideas.track_set", "ideas.todo", "ideas.drop", "ideas.stop",
                  "ideas.review_list", "ideas.diff", "ideas.merge", "ideas.back", "ideas.drop_task",
                  "ideas.stop_task", "ideas.agents", "ideas.task", "ideas.into"}


@pytest.fixture
def host(fake_repo) -> Host:
    checkpoint.ensure(fake_repo)
    h = Host(fake_repo, auto_commit=False)
    yield h
    sys.modules.pop("orkcraft.core.idea_runner", None)


def _wait(host, slug):
    for _ in range(300):
        if not host.ideas.keeper.busy(slug):
            return
        time.sleep(0.01)
    raise AssertionError("the keeper never finished")


def _plan(host, slug, todos=()):
    data = {"idea": slug, "made_at": "2026-10-17T09:00:00", "passed_at": None,
            "estimate": {"tasks": 1, "usd_low": 0.15, "usd_high": 0.45},
            "todos": list(todos),
            "tasks": [{"id": "k1", "title": "Do it", "brief": "b", "tier": "warrior", "after": [], "state": "ready",
                       "branch": "", "commit": "", "session": "", "cost": None, "tokens": None, "started": "",
                       "finished": "", "error": "", "note": ""}]}
    ideas.save_plan(host.ideas.state_dir, slug, data)
    ideas.save_state(host.ideas.state_dir, slug, state="plan")


def test_every_board_command_is_the_hosts_and_a_phones(host):
    assert BOARD_COMMANDS <= set(host.commands)
    assert BOARD_COMMANDS <= set(mobile.COMMANDS)
    assert all(mobile.allowed(host, c, {}) for c in BOARD_COMMANDS)
    assert BOARD_COMMANDS <= set(host.command("mobile.hello")["commands"])


def test_drop_an_idea_and_read_the_board_and_its_page(host):
    rev = host.snapshot()["ideas_rev"]
    slug = host.command("ideas.add", {"text": "Dark mode\nfor the night"})["slug"]
    board = host.command("ideas.board")
    json.dumps(board)
    assert [t["slug"] for t in board["tracks"]] == ["general"] and board["tracks"][0]["count"] == 1
    (i,) = board["ideas"]
    assert i["slug"] == slug and i["state"] == "raw" and i["thesis"] == "Dark mode" and i["track"] == "general"
    assert i["progress"] == {"done": 0, "total": 0} and i["updated"]
    assert set(i) == {"slug", "title", "track", "order", "state", "size", "thesis", "asks", "progress", "updated"}
    assert board["today"] == {"todos": [], "needs_you": []} and board["batch_next"] and board["rev"] > rev
    page = host.command("ideas.page", {"slug": slug})
    assert [s["name"] for s in page["sections"]] == list(ideas.SECTIONS)
    assert page["sections"][0] == {"name": "Gist", "thesis": "Dark mode", "text": "Dark mode\nfor the night"}
    assert page["talk"][0]["who"] == "you" and page["plan"] is None and page["busy"] is False
    assert (Path(host.town.repo_root) / "llm-wiki/general/pages/ideas" / f"{slug}.md").exists()
    with pytest.raises(CommandError, match="gone"):
        host.command("ideas.page", {"slug": "nope"})
    with pytest.raises(CommandError, match="text is missing"):
        host.command("ideas.add", {"text": "  "})


def test_tracks_move_edit_and_drop(host):
    a = host.command("ideas.add", {"text": "alpha"})["slug"]
    b = host.command("ideas.add", {"text": "beta"})["slug"]
    ux = host.command("ideas.track_add", {"title": "UX"})["slug"]
    assert host.command("ideas.track_set", {"slug": ux, "about": "Calm", "criteria": ["fewer clicks"],
                                            "deadline": "2026-12-01"}) == {"ok": True}
    host.command("ideas.move", {"slug": b, "before": a})
    assert [i["slug"] for i in host.command("ideas.board")["ideas"]] == [b, a]
    host.command("ideas.move", {"slug": a, "track": ux})
    t = {t["slug"]: t for t in host.command("ideas.board")["tracks"]}
    assert t[ux]["count"] == 1 and t[ux]["criteria"] == ["fewer clicks"] and t[ux]["deadline"] == "2026-12-01"
    host.command("ideas.edit", {"slug": a, "section": "Risks", "text": "none"})
    assert host.command("ideas.page", {"slug": a})["sections"][4]["text"] == "none"
    with pytest.raises(CommandError, match="no section"):
        host.command("ideas.edit", {"slug": a, "section": "Bogus", "text": "x"})
    with pytest.raises(CommandError, match="deadline"):
        host.command("ideas.track_set", {"slug": ux, "deadline": "tomorrow"})
    host.command("ideas.drop", {"slug": a})
    assert [i["slug"] for i in host.command("ideas.board")["ideas"]] == [b]


def test_say_and_plan_run_the_keeper_in_the_background(host, monkeypatch):
    calls = []

    def run_read(harness, prompt, workdir, cancel, model="", env=None, resume="", timeout_s=0):
        calls.append({"harness": harness, "model": model, "resume": resume})
        if "turn it into" in prompt:
            return json.dumps({"tasks": [{"id": "a", "title": "T", "brief": "B", "tier": "laborer"}]}), 0.1, 10, "s"
        return json.dumps({"reply": "ok", "sections": {"Why": "because"}, "questions": []}), 0.1, 10, "sess-9"

    monkeypatch.setattr(jobs, "run_read", run_read)
    slug = host.command("ideas.add", {"text": "x"})["slug"]
    assert host.command("ideas.say", {"slug": slug, "text": "why?", "section": "Why"}) == {"ok": True}
    _wait(host, slug)
    assert calls[0]["harness"] == "claude" and calls[0]["resume"] == ""
    assert ideas.state(host.ideas.state_dir, slug)["session"] == "sess-9"
    host.command("ideas.say", {"slug": slug, "text": "and?"})
    _wait(host, slug)
    assert calls[1]["resume"] == "sess-9"
    host.command("ideas.plan", {"slug": slug})
    _wait(host, slug)
    page = host.command("ideas.page", {"slug": slug})
    assert page["state"] == "plan" and page["plan"]["tasks"][0]["tier"] == "laborer"
    needs = host.command("ideas.board")["today"]["needs_you"]
    assert needs == [{"idea": slug, "kind": "plan", "title": "x", "text": "Plan ready · 1 tasks"}]
    assert host.snapshot()["needs_you"] == 1


def test_the_demo_runs_no_model(fake_repo):
    checkpoint.ensure(fake_repo)
    host = Host(fake_repo, auto_commit=False, demo=True)
    slug = host.command("ideas.add", {"text": "x"})["slug"]
    assert host.command("ideas.board")["demo"] is True
    with pytest.raises(CommandError, match="demo runs no model"):
        host.command("ideas.say", {"slug": slug, "text": "hi"})
    host.close()


def test_start_without_a_runner_says_so_and_passes_nothing(host, monkeypatch):
    monkeypatch.setitem(sys.modules, "orkcraft.core.idea_runner", None)     # this build has no runner
    slug = host.command("ideas.add", {"text": "x"})["slug"]
    _plan(host, slug)
    with pytest.raises(CommandError, match="runner is not in this build"):
        host.command("ideas.start", {"slug": slug})
    assert ideas.plan(host.ideas.state_dir, slug)["passed_at"] is None


def test_start_passes_the_plan_to_the_runner_and_stop_all_reaches_it(host, monkeypatch):
    seen = []

    class FakeRunner:
        def __init__(self, repo_root, state_dir, settings, bus):
            seen.append(("made", settings.ideas["merge_into"]))
            self.bus = bus

        def start(self, slug):
            seen.append(("start", slug))

        def stop(self, slug):
            seen.append(("stop", slug))

        def tick(self):
            seen.append(("tick",))

        def stop_all(self):
            seen.append(("stop_all",))

    monkeypatch.setitem(sys.modules, "orkcraft.core.idea_runner", types.SimpleNamespace(IdeaRunner=FakeRunner))
    slug = host.command("ideas.add", {"text": "x"})["slug"]
    _plan(host, slug)
    host.command("ideas.start", {"slug": slug})
    assert seen[:2] == [("made", "dev"), ("start", slug)]
    assert ideas.plan(host.ideas.state_dir, slug)["passed_at"]
    assert host.command("ideas.page", {"slug": slug})["state"] == "working"
    host.ideas.tick(1000.0)
    assert ("tick",) in seen
    host.command("ideas.stop", {"slug": slug})
    host.command("halt")
    assert ("stop", slug) in seen and ("stop_all",) in seen


def test_a_secret_todo_is_stored_and_the_plan_says_stored(host):
    slug = host.command("ideas.add", {"text": "x"})["slug"]
    _plan(host, slug, [
        {"id": "t1", "title": "API_KEY", "kind": "secret", "why": "w", "choices": [], "steps": [], "for": ["k1"],
         "done": False, "value": None},
        {"id": "t2", "title": "Which", "kind": "choice", "why": "w", "choices": ["a", "b"], "steps": [], "for": [],
         "done": False, "value": None}])
    today = host.command("ideas.board")["today"]["todos"]
    assert [t["id"] for t in today] == ["t1", "t2"] and "value" not in today[0]
    with pytest.raises(CommandError, match="needs its value"):
        host.command("ideas.todo", {"idea": slug, "id": "t1", "done": True})
    host.command("ideas.todo", {"idea": slug, "id": "t1", "done": True, "value": "sk-secret"})
    plan_text = (host.ideas.state_dir / "ideas" / slug / "plan.json").read_text()
    assert "sk-secret" not in plan_text and json.loads(plan_text)["todos"][0]["value"] == "stored"
    assert idea_secrets.get(host.ideas.state_dir, slug, "t1") == "sk-secret"
    assert json.loads(plan_text)["tasks"][0]["state"] == "ready"
    with pytest.raises(CommandError, match="choices"):
        host.command("ideas.todo", {"idea": slug, "id": "t2", "done": True, "value": "c"})
    host.command("ideas.todo", {"idea": slug, "id": "t2", "done": True, "value": "b"})
    assert host.command("ideas.board")["today"]["todos"] == []
    host.command("ideas.drop", {"slug": slug})
    assert idea_secrets.get(host.ideas.state_dir, slug, "t1") is None


def test_the_snapshot_carries_focus_and_the_phone_hears_an_idea(host, monkeypatch):
    monkeypatch.delenv("ORKCRAFT_FOCUS")                # the machine's default, not the suite's whole town
    snap = host.snapshot()
    assert snap["focus"] == "board" and "ideas_rev" in snap and snap["needs_you"] == 0
    before = mobile.phone_snapshot(host)
    assert before["focus"] == "board" and before["needs_you"] == 0
    slug = host.command("ideas.add", {"text": "phone idea"})["slug"]
    mid = mobile.phone_snapshot(host)
    assert mid["ideas_rev"] > before["ideas_rev"] and mid["rev"] != before["rev"]
    assert mobile.news(before, mid) == []                   # raw: no push
    ideas.save_state(host.ideas.state_dir, slug, state="asks")
    host.ideas.changed(slug)
    after = mobile.phone_snapshot(host)
    assert after["needs_you"] == 1
    assert mobile.news(mid, after) == [{"kind": "idea", "slug": slug, "title": "phone idea", "state": "asks"}]
    assert mobile.news(after, mobile.phone_snapshot(host)) == []          # once


def test_the_focus_is_a_machine_setting(host):
    host.town.machine.focus = ""
    assert host.snapshot()["focus"] == "" and mobile.phone_snapshot(host)["focus"] == ""


def test_the_runner_bus_hops_to_the_hosts_thread(host):
    hops = []
    host.town.call = lambda fn, *a: hops.append(fn)
    gui_ideas._Hop(host.town).publish(idea_keeper.CHANGED, slug="x")
    rev = host.ideas.rev
    assert len(hops) == 1
    hops[0]()
    assert host.ideas.rev == rev + 1


def test_a_lost_reading_shows_as_new(host):
    slug = host.command("ideas.add", {"text": "x"})["slug"]
    ideas.save_state(host.ideas.state_dir, slug, state="reading")     # the host closed while the keeper read
    assert host.command("ideas.page", {"slug": slug})["state"] == "raw"


def test_the_snapshot_writes_nothing_into_a_town_that_has_no_board_yet(host):
    host.snapshot()
    assert not (Path(host.town.repo_root) / "llm-wiki").exists()


# -- spec 33: Review, Agents, the top bar's limits ---------------------------------------------------------

from orkcraft.sources.limits import Limit
import datetime as dt


def _review(host, slug="r", tests=None, state="review", **more):
    """An idea with one task in `state`, as the runner leaves it."""
    ideas.add_idea(host.ideas.root(), "A review idea", "general", host.ideas.state_dir)
    slug = ideas.ideas(host.ideas.root())[-1]["slug"]
    _plan(host, slug)
    ideas.edit_plan(host.ideas.state_dir, slug, lambda p: p["tasks"][0].update(
        state=state, branch=f"idea/{slug}/k1", round=2, finished="2026-10-17T10:00:00", cost=0.42,
        tests=tests or {"passed": 20, "failed": 0, "failing": [], "tail": "20 passed", "green": True},
        diff={"files": 14, "added": 320, "removed": 41}, **more))
    return slug


def test_review_list_has_the_spec_shape_and_the_phones_may_call_it(host):
    empty = host.command("ideas.review_list")
    assert empty == {"into": "dev", "push": False, "results": []}
    slug = _review(host)
    got = host.command("ideas.review_list")
    json.dumps(got)
    (r,) = got["results"]
    assert set(r) == {"idea", "idea_title", "task", "title", "round", "tests", "diff", "cost", "conflict", "finished"}
    assert r["idea"] == slug and r["task"] == "k1" and r["round"] == 2 and r["diff"]["files"] == 14
    assert mobile.allowed(host, "ideas.merge", {"slug": slug, "task": "k1"})


def test_the_snapshot_counts_results_and_the_phone_is_pushed_when_one_arrives(host):
    before = mobile.phone_snapshot(host)
    assert before["review_count"] == 0
    slug = _review(host)
    host.ideas.changed(slug)
    after = mobile.phone_snapshot(host)
    assert after["review_count"] == 1 and after["review_results"] == [{"idea": slug, "task": "k1", "title": "Do it"}]
    assert [n for n in mobile.news(before, after) if n["kind"] == "result"] == [
        {"kind": "result", "slug": slug, "task": "k1", "title": "Do it"}]
    assert mobile.news(after, mobile.phone_snapshot(host)) == []


def test_the_limits_are_the_smallest_remaining_of_each_installed_tools_rows(host, monkeypatch):
    soon = dt.datetime(2026, 10, 17, 18, 0)
    rows = [Limit("claude", "", "session", 0.62, soon), Limit("claude", "", "weekly", 0.9, None),
            Limit("agy", "Pro", "daily", 0.4, soon), Limit("agy", "Flash", "daily", 0.7, soon),
            Limit("codex", "", "", None, None, "not installed"), Limit("limits", "—", "—", None, None, "off")]
    monkeypatch.setattr(host, "limits", lambda: rows)
    got = host.snapshot()["limits"]
    assert [x["provider"] for x in got] == ["claude", "agy"]
    claude = got[0]
    assert claude["name"] == "Claude" and claude["left"] == 0.62
    assert claude["rows"][0] == {"window": "5h", "left": 0.62, "reset": "2026-10-17T18:00"}
    assert claude["rows"][1]["window"] == "week" and got[1]["left"] == 0.4
    assert mobile.phone_snapshot(host)["limits"][0]["left"] == 0.62


def test_agents_shows_the_taskmaster_and_a_chip_per_live_task(host):
    assert host.command("ideas.agents") == {"roles": [
        {"role": "taskmaster", "name": "Taskmaster", "state": "waiting", "waits_on": None, "chips": []},
        {"role": "grunt", "name": "Grunts", "chips": []}], "done_today": []}
    slug = _review(host)
    ideas.save_state(host.ideas.state_dir, slug, state="working")
    other = host.command("ideas.add", {"text": "asking idea"})["slug"]
    ideas.save_state(host.ideas.state_dir, other, state="asks")
    got = host.command("ideas.agents")
    tm, grunts = got["roles"]
    assert tm["state"] == "waiting" and tm["waits_on"]["idea"] == other and "asking idea" in tm["waits_on"]["text"]
    assert tm["chips"] == [{"idea": other, "title": "asking idea", "state": "waiting"}]
    (chip,) = grunts["chips"]
    assert chip["state"] == "review" and chip["task"] == "k1" and chip["idea"] == slug and chip["tier"] == "warrior"
    ideas.edit_plan(host.ideas.state_dir, slug, lambda p: p["tasks"][0].update(
        state="merged", finished=dt.datetime.now().isoformat(timespec="seconds")))
    got = host.command("ideas.agents")
    assert got["roles"][1]["chips"] == [] and got["done_today"] == [{"idea": slug, "task": "k1", "title": "Do it"}]


def test_task_returns_its_fields_idea_title_and_log(host):
    slug = _review(host)
    got = host.command("ideas.task", {"slug": slug, "task": "k1"})
    assert got["id"] == "k1" and got["idea_title"] == "A review idea" and got["log"] == "" and got["round"] == 2
    with pytest.raises(CommandError, match="gone"):
        host.command("ideas.task", {"slug": slug, "task": "zz"})


def test_the_answers_at_review_reach_the_runner_and_its_refusals_are_plain_words(host, monkeypatch):
    seen = []

    class FakeRunner:
        def __init__(self, *a):
            pass

        def merge(self, slug, tid):
            seen.append(("merge", slug, tid))
            return "abc123"

        def back(self, slug, tid, why):
            seen.append(("back", slug, tid, why))

        def drop_task(self, slug, tid):
            seen.append(("drop", slug, tid))

        def stop_task(self, slug, tid):
            seen.append(("stop", slug, tid))

        def log(self, slug, tid):
            return "the log"

    monkeypatch.setitem(sys.modules, "orkcraft.core.idea_runner", types.SimpleNamespace(IdeaRunner=FakeRunner))
    slug = _review(host)
    a = {"slug": slug, "task": "k1"}
    assert host.command("ideas.merge", a) == {"ok": True, "commit": "abc123"}
    assert host.command("ideas.back", {**a, "why": "rename it"}) == {"ok": True}
    assert host.command("ideas.drop_task", a) == {"ok": True} and host.command("ideas.stop_task", a) == {"ok": True}
    assert seen == [("merge", slug, "k1"), ("back", slug, "k1", "rename it"), ("drop", slug, "k1"),
                    ("stop", slug, "k1")]
    assert host.command("ideas.task", a)["log"] == "the log"
    with pytest.raises(CommandError, match="why is missing"):
        host.command("ideas.back", a)

    class Refusing(FakeRunner):
        def merge(self, slug, tid):
            raise type("RunnerError", (Exception,), {})("Its tests are red: send it back")

    host.ideas._runner = Refusing()
    with pytest.raises(CommandError, match="tests are red"):
        host.command("ideas.merge", a)


def test_into_sets_the_branch_made_when_missing_and_the_push_switch(host):
    import subprocess
    root = Path(host.town.repo_root)
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=root, check=True)
    subprocess.run(["git", "-c", "user.name=T", "-c", "user.email=t@x", "commit", "-q", "--allow-empty", "-m", "start"],
                   cwd=root, check=True)
    assert host.command("ideas.into", {"branch": "next"}) == {"ok": True}
    assert host.command("ideas.review_list")["into"] == "next"
    assert subprocess.run(["git", "rev-parse", "--verify", "next"], cwd=root, capture_output=True).returncode == 0
    host.command("ideas.into", {"push": True})
    assert host.command("ideas.review_list")["push"] is True and host.command("ideas.review_list")["into"] == "next"
    with pytest.raises(CommandError):
        host.command("ideas.into", {"branch": "bad name"})
    with pytest.raises(CommandError, match="branch is missing"):
        host.command("ideas.into", {})
