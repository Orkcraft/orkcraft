"""🏕 Barracks under load and under failure: several orcs at once, agents that crash or stop,
worktrees that cannot be made, a budget that runs out mid-run."""
from __future__ import annotations

import threading
from pathlib import Path

import pytest

from orkcraft.core.workers.barracks import BarracksWorker
from orkcraft.realm import barracks as bk
from orkcraft.realm import pipes
from tests.pool_fakes import FakeGit, Steward

SIZE = (200, 46)


@pytest.fixture(autouse=True)
def fake_git_and_steward(monkeypatch):
    monkeypatch.setattr(BarracksWorker, "git", FakeGit())
    monkeypatch.setattr(BarracksWorker, "steward_runner", Steward())


def spec(**config) -> dict:
    return {"id": "camp", "title": "Camp", "icon": "🏕", "orc": {"name": "Foreman"}, "type": "barracks",
            "config": {"max_orcs": 3, "providers": ["claude"], **config}}


class Crew:
    """A fake harness: each run blocks until the test finishes it — with a result or an error."""

    def __init__(self, cost: float = 0.1):
        self.calls, self.cost = [], cost
        self.lock = threading.Lock()
        self.running = self.peak = 0

    def __call__(self, harness, prompt, workdir, cancel, model, env, resume):
        call = {"prompt": prompt, "workdir": workdir, "resume": resume, "env": env,
                "gate": threading.Event(), "error": None}
        with self.lock:
            self.calls.append(call)
            self.running += 1
            self.peak = max(self.peak, self.running)
        try:
            while not call["gate"].wait(0.02):
                if cancel.is_set():
                    raise InterruptedError("stopped")
            if call["error"] is not None:
                raise call["error"]
            return "ok", self.cost, 100, resume or f"s{len(self.calls)}"   # a resumed session keeps its id
        finally:
            with self.lock:
                self.running -= 1

    def finish(self, i: int, error: Exception | None = None) -> None:
        self.calls[i]["error"] = error
        self.calls[i]["gate"].set()


async def _until(pilot, cond, n=150):
    for _ in range(n):
        if cond():
            return True
        await pilot.pause(0.02)
    return cond()


def _arrive(app, value):
    app.deliver_payload("camp", pipes.Payload(pipes.NODE, value, "loot", "on_selection_change", value), value, value)


# -- context reuse -----------------------------------------------------------------------------------


def test_the_foreman_prefers_the_orc_that_knows_the_work():
    f = bk.Foreman({"max_orcs": 3})
    grub = bk.PoolOrc("Grub", "claude", recent=["Add the login page — form and validation"])
    mogka = bk.PoolOrc("Mogka", "claude", recent=["Parser: tokenizer for quoted strings — done"])
    t = bk.PoolTask("t", "Parser: handle escapes in quoted strings", "the tokenizer drops backslashes")
    d = f.decide(t, [grub, mogka], [], 0.0)
    assert (d.action, d.orc) == ("reuse", "Mogka") and "knows this work" in d.why
    assert f.decide(bk.PoolTask("u", "Bump the version", "x"), [grub, mogka], [], 0.0).orc == "Grub"   # no fit → first
    queue = [bk.PoolTask("a", "Bump the version", "x"), t]
    assert f.next_for(mogka, queue).id == t.id and f.next_for(grub, queue).id == "a"
    far = [bk.PoolTask(str(i), f"chore {i}", "x") for i in range(bk.LOOKAHEAD)] + [t]
    assert f.next_for(mogka, far).id == "0"                                    # no jumping the whole queue
    mogka.session, mogka.session_tasks = "s1", 4
    assert f.can_resume(mogka)
    mogka.session_tasks = f.session_tasks
    assert not f.can_resume(mogka)                                             # rolled over
    assert not f.can_resume(bk.PoolOrc("Snaga", "agy", session="x"))          # agy cannot resume


# -- the steward: questions, reviews, reworks, the PR -------------------------------------------------


class Asker(Crew):
    """A crew whose run ends with the text the test gives (a QUESTION, a report)."""

    def finish_with(self, i: int, text: str) -> None:
        self.calls[i]["text"] = text
        self.calls[i]["gate"].set()

    def __call__(self, harness, prompt, workdir, cancel, model, env, resume):
        text, cost, tokens, session = super().__call__(harness, prompt, workdir, cancel, model, env, resume)
        return self.calls[-1].get("text", text), cost, tokens, session


def _calls_done(crew, n):
    return lambda: len(crew.calls) >= n


def test_code_is_always_external():
    assert bk.scope_rule(["src/app.py", "README.md"], meeting=True) == bk.EXTERNAL
    assert bk.scope_rule(["docs/a.md"], meeting=True) == bk.LOCAL
    assert bk.scope_rule(["docs/a.md"], meeting=False) == ""
    assert bk.scope_of("ACCEPT\nscope: Local") == bk.LOCAL and bk.scope_of("ACCEPT") == bk.EXTERNAL
    assert bk.changed_files("diff --git a/x.md b/y.md\n+1\ndiff --git a/z.py b/z.py\n") == ["x.md", "y.md", "z.py"]


# -- the real git ------------------------------------------------------------------------------------


def _git(cwd: Path, *args: str) -> str:
    import subprocess
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True).stdout.strip()


def test_task_git_cuts_reuses_and_publishes_branches(fake_repo: Path, tmp_path: Path, monkeypatch):
    from orkcraft.realm import jobs
    import shutil
    origin = tmp_path / "origin.git"
    _git(tmp_path, "init", "--bare", str(origin))
    base = _git(fake_repo, "rev-parse", "--abbrev-ref", "HEAD")
    _git(fake_repo, "remote", "add", "origin", str(origin))
    _git(fake_repo, "push", "-u", "origin", base)
    git = jobs.TaskGit()
    assert git.base_of(fake_repo) == base and git.base_of(fake_repo, "develop") == "develop"
    wt, _ = jobs.add_worktree(fake_repo, "camp", "Grub")

    git.prepare(wt, "pool/camp/t1", base)
    assert _git(wt, "branch", "--show-current") == "pool/camp/t1"
    assert git.diff(wt, base, "pool/camp/t1") == (0, "")
    (wt / "feature.py").write_text("x = 1\n")
    _git(wt, "add", ".")
    _git(wt, "commit", "-m", "feature")
    commits, diff = git.diff(wt, base, "pool/camp/t1")
    assert commits == 1 and "+x = 1" in diff
    (wt / "scratch.txt").write_text("left behind")                                    # leftovers get stashed

    git.prepare(wt, "pool/camp/t2", base)                                             # another task, fresh from base
    assert not (wt / "feature.py").exists() and not (wt / "scratch.txt").exists()
    git.prepare(wt, "pool/camp/t1", base)                                             # its follow-up: same branch
    assert (wt / "feature.py").exists()

    monkeypatch.setattr(shutil, "which", lambda name: None)                           # no gh here
    url, note = git.publish(wt, "pool/camp/t1", base, "Feature", "body")
    assert url == "" and note == "pushed; no gh to open the pull request"
    assert "pool/camp/t1" in _git(origin, "branch", "--list", "pool/camp/t1")

    _git(fake_repo, "merge", "--ff-only", "pool/camp/t1")                             # merged upstream …
    _git(fake_repo, "push", "origin", base)
    git.prepare(wt, "pool/camp/t1", base)                                             # … so a new follow-up starts anew
    assert git.diff(wt, base, "pool/camp/t1")[0] == 0

    ok, out = git.test(wt, "python -c \"import sys; print('boom'); sys.exit(1)\"", threading.Event())
    assert not ok and "boom" in out
    assert git.test(wt, "python -c \"print('fine')\"", threading.Event())[0]
