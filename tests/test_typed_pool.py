"""🏕 Barracks (T1105 stage 5): the foreman's rules, its learning, worktrees, parallel work."""
from __future__ import annotations

import subprocess
import threading
from pathlib import Path

import pytest

from orkcraft import scroll as ts
from orkcraft.app import OrkcraftApp
from orkcraft.core.workers.barracks import BarracksWorker
from orkcraft.realm import barracks as bk
from orkcraft.realm import jobs, masonry, pipes
from orkcraft.screens.typed.pool_view import PoolView
from tests.pool_fakes import FakeGit, Steward

SIZE = (200, 46)
SPEC = {"id": "camp", "title": "Camp", "icon": "🏕", "orc": {"name": "Foreman"}, "type": "pool",
        "config": {"max_orcs": 2, "providers": ["claude", "agy"]}}


@pytest.fixture(autouse=True)
def fake_git_and_steward(monkeypatch):
    monkeypatch.setattr(BarracksWorker, "git", FakeGit())
    monkeypatch.setattr(BarracksWorker, "steward_runner", Steward())


def task(title: str, text: str = "", key: str = "") -> bk.PoolTask:
    return bk.PoolTask(title, title, text or title, key or bk.task_key("text", text or title, title))


def test_follow_up_reuse_hire_queue():
    f = bk.Foreman({"max_orcs": 2})
    grub = bk.PoolOrc("Grub", "claude", status="working", keys=["T1001"], done=1, last="2026-10-01T10:00:00")
    orcs = [grub]
    d = f.decide(task("T1001: fix the review"), orcs, [], 0.0)
    assert (d.action, d.orc) == ("wait", "Grub") and "T1001 was Grub's" in d.why
    d = f.decide(task("Add a login page"), orcs, [], 0.0)
    assert d.action == "hire" and d.orc == "Mogka"
    orcs.append(bk.PoolOrc("Mogka", "agy", status="working"))
    assert f.decide(task("Another thing"), orcs, [], 0.0).action == "queue"
    grub.status = "idle"
    assert (f.decide(task("уточнение: и тесты"), orcs, [], 0.0).action,
            f.decide(task("уточнение: и тесты"), orcs, [], 0.0).orc) == ("follow-up", "Grub")
    waiting = [bk.PoolTask("x", "x", "x", wait_for="Grub")]
    assert f.decide(task("Brand new"), orcs, waiting, 0.0).action == "queue"   # Grub is spoken for
    assert f.decide(task("Brand new"), orcs, [], 0.0).action == "reuse"
    assert bk.Foreman({"budget_usd": 1}).decide(task("x"), [], [], 1.5).action == "budget"
    assert f.decide(task("x"), orcs, [], 0.0, paused=True).action == "paused"
    assert f.next_for(grub, [bk.PoolTask("a", "a", "a"), bk.PoolTask("b", "b", "b", wait_for="Grub")]).id == "b"


def test_the_foreman_picks_and_learns_models():
    f = bk.Foreman({"providers": ["claude", "agy"]})
    h, m, why = f.choose_model(task("Write the README docs"))
    assert (h, m) == ("agy", bk.AGY_DOCS) and "docs" in why
    assert f.choose_model(task("Fix the parser bug"))[:2] == ("claude", "")
    claude = bk.PoolOrc("Grub", "claude")
    for _ in range(4):
        f.learn(claude, False, 0.5)                    # claude keeps failing on this town's tasks
    assert f.choose_model(task("Fix the parser bug"))[0] == "agy"
    only = bk.Foreman({"providers": ["agy:gemini-3.1-pro-high", "bogus"]})
    assert only.choose_model(task("code"))[:2] == ("agy", "gemini-3.1-pro-high")
    assert bk.task_key("node", "T1042") == "T1042" and bk.task_key("text", "see ABC-12 please") == "ABC-12"


def test_state_survives_a_restart_and_puts_work_back(tmp_path: Path):
    st = bk.Barracks(tmp_path)
    st.orcs = [bk.PoolOrc("Grub", "claude", status="working", task="t1")]
    st.tasks = [bk.PoolTask("t1", "Do it", "Do it", status="working", orc="Grub")]
    st.save()
    again = bk.Barracks(tmp_path)
    assert again.orcs[0].status == "idle" and again.queue[0].id == "t1" and again.queue[0].wait_for == "Grub"


def test_each_orc_gets_its_worktree(fake_repo: Path):
    path, branch = jobs.add_worktree(fake_repo, "camp", "Grub")
    assert branch == "" and (path / "README.md").exists()                     # detached: branches are the tasks'
    assert path == fake_repo / ".orkcraft" / "worktrees" / "pool-camp-grub"     # where orkspaces keep theirs
    assert jobs.add_worktree(fake_repo, "camp", "Grub") == (path, branch)      # reused
    listed = subprocess.run(["git", "worktree", "list"], cwd=fake_repo, capture_output=True, text=True).stdout
    assert "pool-camp-grub" in listed and "detached" in listed
    assert jobs.work_cmd("claude", "p", path, "sonnet", "sess-1")[-4:] == ["--model", "sonnet", "--resume", "sess-1"]
    assert "--add-dir" in jobs.work_cmd("agy", "p", path)


class Crew:
    """A fake harness: each run blocks until the test lets it finish."""

    def __init__(self):
        self.calls, self.gates = [], {}

    def __call__(self, harness, prompt, workdir, cancel, model, env, resume):
        gate, n = threading.Event(), len(self.calls) + 1
        self.calls.append({"harness": harness, "prompt": prompt, "workdir": workdir, "resume": resume,
                           "gate": gate})
        while not gate.wait(0.02):
            if cancel.is_set():
                raise InterruptedError("stopped")
        return f"done: {prompt.split('## Task', 1)[1].splitlines()[0]}", 0.1, 100, f"s{n}"


async def _until(pilot, cond, n=100):
    for _ in range(n):
        if cond():
            return True
        await pilot.pause(0.02)
    return cond()


@pytest.mark.asyncio
async def test_tasks_run_in_parallel_and_follow_ups_wait_for_their_orc(fake_repo: Path, monkeypatch):
    crew = Crew()
    monkeypatch.setattr(BarracksWorker, "work_runner", staticmethod(crew))
    made = []
    monkeypatch.setattr(BarracksWorker, "worktree_maker",
                        staticmethod(lambda repo, bid, orc: made.append(orc) or (fake_repo, f"pool/{bid}/{orc.lower()}")))
    assert masonry.save_spec(fake_repo, SPEC) == []
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    ts.subscribe(app.scroll, "town_hall", "camp", "pool.done")
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        view = app.desktop.get_window("camp").query_one(PoolView)
        assert view.mini_status() == ["no orks yet", "waiting for tasks"]
        sent = []
        monkeypatch.setattr(app.roads, "emit", lambda payload, meta=None: sent.append(payload) or [])

        def arrive(value, kind=pipes.NODE):
            app.deliver_payload("camp", pipes.Payload(kind, value, "loot", "on_selection_change", value), value, value)

        arrive("T1001")
        arrive("T1002")
        arrive("T1003")                                                  # 2 orcs max → queued
        assert await _until(pilot, lambda: len(crew.calls) == 2)
        st = view.state
        assert [o.name for o in st.orcs] == ["Grub", "Mogka"] and made == ["Grub", "Mogka"]
        assert [t.key for t in st.queue] == ["T1003"]
        arrive("T1001")                                                  # Grub's ticket: waits for Grub
        assert st.queue[-1].wait_for == "Grub"
        assert "queue 2" in view.mini_status()[-1]

        crew.calls[0]["gate"].set()                                      # Grub finishes T1001 …
        assert await _until(pilot, lambda: len(crew.calls) == 3)
        assert crew.calls[2]["resume"] == "s1"                          # … and resumes its session
        assert "follow-up" in crew.calls[2]["prompt"]
        assert [p.mode for p in sent].count("pool.done") == 1
        assert "pool/camp/t1001" in next(p.value for p in sent if p.mode == "pool.done")   # the task's branch
        assert "## Files on `pool/camp/t1001`" in next(p.value for p in sent if p.mode == "pool.done")

        crew.calls[1]["gate"].set()                                      # Mogka frees → takes T1003
        assert await _until(pilot, lambda: len(crew.calls) == 4)
        assert st.orc("Mogka").task and st.task(st.orc("Mogka").task).key == "T1003"
        for c in crew.calls[2:]:
            c["gate"].set()
        assert await _until(pilot, lambda: all(o.status == "idle" for o in st.orcs) and not st.queue)
        assert sum(o.done for o in st.orcs) == 4 and st.stats["claude"]["runs"] + st.stats.get(
            f"agy:{bk.AGY_CODE}", {"runs": 0})["runs"] == 4
        decisions = [d.action for d in st.decisions()]
        assert {"hire", "queue", "wait", "follow-up", "reuse"} <= set(decisions)

        assert view.quick_action("pool.pause") and st.paused
        arrive("T1009")
        assert st.queue[-1].key == "T1009" and len(crew.calls) == 4      # paused: nothing starts
        assert view.quick_action("pool.pause") and not st.paused
        assert await _until(pilot, lambda: len(crew.calls) == 5)
        crew.calls[4]["gate"].set()
        assert await _until(pilot, lambda: all(o.status == "idle" for o in st.orcs))


@pytest.mark.asyncio
async def test_new_task_is_written_to_the_barracks_directly(fake_repo: Path, monkeypatch):
    from orkcraft.screens.dialogs import TextPrompt
    crew = Crew()
    monkeypatch.setattr(BarracksWorker, "work_runner", staticmethod(crew))
    monkeypatch.setattr(BarracksWorker, "worktree_maker",
                        staticmethod(lambda repo, bid, orc: (fake_repo, f"pool/{bid}/{orc.lower()}")))
    assert masonry.save_spec(fake_repo, SPEC) == []
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        view = app.desktop.get_window("camp").query_one(PoolView)
        assert view.quick_action("pool.task")
        await pilot.pause()
        assert isinstance(app.screen, TextPrompt) and "New task" in app.screen.prompt_heading
        await pilot.press(*"Add a login page", "enter", *"email and password", "enter")
        assert await _until(pilot, lambda: len(crew.calls) == 1)
        t = view.state.task(view.state.orcs[0].task)
        assert (t.title, t.text) == ("Add a login page", "email and password")
        assert "Add a login page" in crew.calls[0]["prompt"]
        crew.calls[0]["gate"].set()
        assert await _until(pilot, lambda: all(o.status == "idle" for o in view.state.orcs))

        assert view.new_task(None) is None and view.new_task(" \t ") is None     # Esc or nothing typed
        only = view.new_task("Rename the README title\t")                         # no brief: the title is it
        assert (only.title, only.text) == ("Rename the README title", "Rename the README title")
