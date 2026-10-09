"""🏕 Barracks (T1105 stage 5): the foreman's rules, its learning, worktrees, parallel work."""
from __future__ import annotations

import subprocess
import threading
from pathlib import Path

import pytest

from orkcraft.core.workers.barracks import BarracksWorker
from orkcraft.realm import barracks as bk
from orkcraft.realm import jobs
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


def test_a_task_without_a_title_is_named_by_its_first_words():
    from orkcraft.core.workers.barracks import title_from
    assert title_from("fix the login page: it hangs on Safari") == "Fix the login page"
    assert title_from("  Ship it.\n") == "Ship it"
    assert title_from("") == "Task"
