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
from orkcraft.realm import checkpoint, idea_merged, idea_secrets, ideas, jobs

BOARD_COMMANDS = {"ideas.board", "ideas.page", "ideas.add", "ideas.say", "ideas.plan", "ideas.start", "ideas.move",
                  "ideas.edit", "ideas.track_add", "ideas.track_set", "ideas.todo", "ideas.drop", "ideas.stop",
                  "ideas.seen", "ideas.revert", "ideas.answer"}


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
    assert board["today"] == {"todos": [], "needs_you": [], "merged": [], "merged_more": 0, "night": None} and board["batch_next"] and board["rev"] > rev
    page = host.command("ideas.page", {"slug": slug})
    assert [s["name"] for s in page["sections"]] == list(ideas.SECTIONS)
    assert page["sections"][0] == {"name": "Gist", "thesis": "Dark mode", "text": "Dark mode\nfor the night",
                                   "shown": True}
    assert all(s["shown"] for s in page["sections"]) and page["questions"] == []
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


def _merged(host, slug, n, cost=0.1):
    idea_merged.add(host.ideas.state_dir, {"idea": slug, "task": f"k{n}", "title": f"Task {n}", "goal": "Goal",
                                           "subject": f"Subject {n}", "commit": f"{n:07x}", "tests": "3 passed",
                                           "cost": cost, "estimate": [0.1, 0.3], "at": "2026-10-17T09:00:00"})


def test_the_board_lists_what_merged_unseen_and_looked_clears_it(host):
    slug = host.command("ideas.add", {"text": "x"})["slug"]
    for n in range(1, 23):
        _merged(host, slug, n)
    today = host.command("ideas.board")["today"]
    assert len(today["merged"]) == 20 and today["merged_more"] == 2 and today["merged"][0]["task"] == "k22"
    line = today["merged"][0]
    assert {k: line[k] for k in ("goal", "subject", "tests", "cost", "estimate", "seen", "reverted", "reverting")} == {
        "goal": "Goal", "subject": "Subject 22", "tests": "3 passed", "cost": 0.1, "estimate": [0.1, 0.3],
        "seen": False, "reverted": False, "reverting": False}
    rev = host.ideas.rev
    assert host.command("ideas.seen", {"idea": slug, "task": "k22"}) == {"ok": True} and host.ideas.rev > rev
    assert host.command("ideas.board")["today"]["merged"][0]["task"] == "k21"
    assert host.command("ideas.seen", {}) == {"ok": True}
    assert host.command("ideas.board")["today"]["merged"] == []


def test_revert_runs_on_its_own_thread_and_a_failure_is_a_toast(host, monkeypatch):
    slug = host.command("ideas.add", {"text": "x"})["slug"]
    with pytest.raises(CommandError, match="Nothing of that task"):
        host.command("ideas.revert", {"idea": slug, "task": "k1"})
    _merged(host, slug, 1)
    done, toasts = [], []

    class Runner:
        def working(self, slug):
            return False

        def reverting(self):
            return set()

        def revert(self, slug, task):
            done.append((slug, task))
            return {"error": "Not reverted, main is as it was: conflicts"}

    host.ideas._runner = Runner()
    host.town.call = lambda fn, *a: fn()
    monkeypatch.setattr(host.town, "toast", lambda text, **kw: toasts.append((text, kw)))
    assert host.command("ideas.revert", {"idea": slug, "task": "k1"}) == {"ok": True}
    for _ in range(200):
        if toasts:
            break
        time.sleep(0.01)
    assert done == [(slug, "k1")] and "conflicts" in toasts[0][0] and toasts[0][1]["severity"] == "error"


def test_answers_through_the_host_and_the_page_carries_questions_and_shown_sections(host, monkeypatch):
    slug = host.command("ideas.add", {"text": "tiny thing"})["slug"]
    ideas.set_meta(host.ideas.root(), slug, size="S")
    ideas.save_questions(host.ideas.state_dir, slug, idea_keeper.parse_questions(
        [{"text": "Which?", "options": ["A", "B"], "recommended": 1, "why": "B is smaller"}, "Name?"]))
    page = host.command("ideas.page", {"slug": slug})
    assert [s["name"] for s in page["sections"] if s["shown"]] == ["Gist", "In", "Out", "Stages"]
    assert page["questions"][0] == {"id": "q1", "text": "Which?", "options": ["A", "B"], "recommended": 1,
                                    "why": "B is smaller", "answer": None}
    said = []
    monkeypatch.setattr(host.ideas.keeper, "say", lambda slug, text, section="": said.append(text))
    assert host.command("ideas.answer", {"slug": slug, "id": "q1", "choice": 1}) == {"ok": True, "left": 1}
    with pytest.raises(CommandError, match="not a number"):
        host.command("ideas.answer", {"slug": slug, "id": "q2", "choice": "1"})
    with pytest.raises(CommandError, match="a choice or a few words"):
        host.command("ideas.answer", {"slug": slug, "id": "q2"})
    assert host.command("ideas.answer", {"slug": slug, "id": "q2", "text": "Zed"}) == {"ok": True, "left": 0}
    assert said == ["My answers to your questions:\nWhich? → B\nName? → Zed"]
    assert host.command("ideas.page", {"slug": slug})["questions"] == []


def test_only_what_blocks_pushes_and_the_rest_waits_for_the_digest(host, monkeypatch):
    import datetime as dt
    slug = host.command("ideas.add", {"text": "phone idea"})["slug"]
    _plan(host, slug)
    before = mobile.phone_snapshot(host)
    ideas.save_state(host.ideas.state_dir, slug, state="done")
    host.ideas.changed(slug)
    done = mobile.phone_snapshot(host)
    assert mobile.news(before, done) == []                                   # done waits for the digest
    ideas.save_state(host.ideas.state_dir, slug, state="working")
    ideas.edit_plan(host.ideas.state_dir, slug, lambda p: p["tasks"][0].update(state="held", note="after 18:00"))
    host.ideas.changed(slug)
    held = mobile.phone_snapshot(host)
    assert mobile.news(done, held) == [{"kind": "idea", "slug": slug, "title": "phone idea", "state": "held"}]
    hour = dt.datetime.now().hour
    host.town.machine.ideas["digest_hours"] = [hour]
    _merged(host, slug, 1, cost=0.5)
    ideas.save_state(host.ideas.state_dir, slug, state="done")
    host.ideas.changed(slug)
    digest = mobile.phone_snapshot(host)
    assert digest["digest"]["merged"] == 1 and digest["digest"]["done"] == 1
    assert mobile.news(held, digest) == [{"kind": "digest", "merged": 1, "done": 1, "spent": "$0.50"}]
    assert mobile.news(digest, mobile.phone_snapshot(host)) == []            # once an hour
    host.town.machine.ideas["digest_hours"] = [(hour + 1) % 24]
    assert mobile.phone_snapshot(host)["digest"] is None


# -- the night gate (spec 32): its two commands, its card on the board, a red night in Needs you -------------------

def _report(host, **fields):
    folder = host.ideas.state_dir / "gate" / "night"
    folder.mkdir(parents=True, exist_ok=True)
    rep = {"date": "2026-10-17", "dev": "abc", "main": "def", "commits": [{"sha": "abc", "subject": "s", "idea": ""}],
           "steps": [{"name": "Full suite", "ok": True, "summary": "4 passed", "failed": []}], "fixed": [],
           "not_fixed": [], "cost": 0.4, "budget": 2.0, "green": True, "started": "2026-10-17T03:00:00",
           "finished": "2026-10-17T03:20:00", "running": False, **fields}
    (folder / "2026-10-17.json").write_text(json.dumps(rep))
    host.ideas.changed("")


def test_the_night_gates_commands_are_the_hosts_and_a_phones(host):
    for name in ("gate.pass_night", "gate.run_night"):
        assert name in host.commands and name in mobile.COMMANDS and mobile.allowed(host, name, {})


def test_the_board_carries_the_night_report_and_a_red_one_needs_you(host):
    assert host.command("ideas.board")["today"]["night"] is None
    _report(host)
    night = host.command("ideas.board")["today"]["night"]
    assert night["green"] and night["count"] == 1 and night["cost"] == 0.4 and night["stale"] is True
    assert host.snapshot()["needs_you"] == 0
    _report(host, green=False, steps=[{"name": "Full suite", "ok": False, "summary": "1 failed", "failed": ["t::x"]}])
    snap = host.snapshot()
    assert snap["needs_you"] == 1 and snap["night"] == {"date": "2026-10-17", "green": False, "running": False,
                                                       "passed": False, "count": 1}
    assert mobile.compact(snap)["night"]["green"] is False


def test_pass_to_main_refuses_a_red_night_and_one_whose_dev_moved(host):
    _report(host, green=False)
    assert "red night" in host.command("gate.pass_night", {"date": "2026-10-17"})["error"]
    _report(host)
    assert host.command("gate.pass_night", {"date": "2026-10-17"})["error"] == "dev moved since the night; run again"
    assert "date" in host.command("gate.pass_night", {})["error"]


def test_run_now_needs_a_dev_branch(host):
    assert "no `dev` branch" in host.command("gate.run_night", {})["error"]
