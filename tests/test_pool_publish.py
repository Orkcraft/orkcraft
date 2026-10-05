"""🏕 Barracks → 📦 Loot: an ork drafts a post for a service, and posts it only after the operator approves."""
from __future__ import annotations

from pathlib import Path

import pytest

from orkcraft import scroll as ts
from orkcraft.app import OrkcraftApp
from orkcraft.core.workers.barracks import BarracksWorker
from orkcraft.realm import barracks as bk
from orkcraft.realm import gate, masonry, pipes
from orkcraft.screens.typed.generator_view import GeneratorView
from orkcraft.screens.typed.pool_view import PoolView
from tests.pool_fakes import FakeGit, Steward

SIZE = (200, 46)
CAMP = {"id": "camp", "title": "Camp", "icon": "🏕", "orc": {"name": "Foreman"}, "type": "barracks",
        "config": {"max_orcs": 1, "providers": ["claude"]}}
GATE = {"id": "gate", "title": "Gate", "icon": "📦", "orc": {"name": "Quartermaster"}, "type": "loot",
        "config": {"review": "never"}}                     # even a gate that waves everything through holds a draft


class Writer:
    """Drafts a Jira bug (round n), or — once approved — 'posts' what it was given."""

    def __init__(self):
        self.prompts = []

    def __call__(self, harness, prompt, workdir, cancel, model, env, resume):
        self.prompts.append(prompt)
        if "## Approved" in prompt:
            return "Posted: APP-42 https://jira.example/browse/APP-42", 0.01, 10, "s1"
        n = len(self.prompts)
        return (f"Wrote the bug report (round {n}).\n\nPUBLISH: Jira, project APP, a new Bug\n\n"
                f"Title: Login fails on Safari\nSteps: open the page (v{n})"), 0.02, 20, "s1"


async def _until(pilot, cond, n=150):
    for _ in range(n):
        if cond():
            return True
        await pilot.pause(0.02)
    return cond()


def test_publish_of_splits_the_draft():
    report, target, draft = bk.publish_of("Did it.\n\n**PUBLISH:** Jira, APP\n\nTitle: X\nBody")
    assert (report, target, draft) == ("Did it.", "Jira, APP", "Title: X\nBody")
    assert bk.publish_of("no draft here") == ("no draft here", "", "")


@pytest.mark.asyncio
async def test_a_draft_waits_in_loot_goes_back_and_is_posted_once_accepted(fake_repo: Path, monkeypatch):
    writer = Writer()
    monkeypatch.setattr(BarracksWorker, "git", FakeGit(commits=0))          # a ticket: nothing committed, the report is the work
    monkeypatch.setattr(BarracksWorker, "steward_runner", Steward())
    monkeypatch.setattr(BarracksWorker, "work_runner", staticmethod(writer))
    monkeypatch.setattr(BarracksWorker, "worktree_maker", staticmethod(lambda repo, bid, orc: (fake_repo, f"pool/{bid}/x")))
    for spec in (CAMP, GATE):
        assert masonry.save_spec(fake_repo, spec) == []
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    for bid, ev in (("camp", "pool.question"), ("camp", "pool.done")):
        ts.subscribe(app.scroll, "town_hall", bid, ev)
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        camp = app.desktop.get_window("camp").query_one(PoolView)
        loot = app.desktop.get_window("gate").query_one(GeneratorView)
        sent = []
        monkeypatch.setattr(app.roads, "emit", lambda payload, meta=None: sent.append(payload) or [])
        questions = lambda: [p for p in sent if p.mode == "pool.question"]      # noqa: E731

        camp.add_task("Jira bug for the Safari login", "file a bug in APP")
        assert await _until(pilot, lambda: len(questions()) == 1)
        [task] = camp.state.asked
        assert (task.target, task.draft.splitlines()[0]) == ("Jira, project APP, a new Bug", "Title: Login fails on Safari")
        assert "Never act outside this repository" in writer.prompts[0]
        q = questions()[0]
        assert "PUBLISH: Jira, project APP" in q.value and "waits for your approval" in q.value
        assert q.ref == task.ref and q.trail[-1].outcome == gate.APPROVAL
        assert len(writer.prompts) == 1                                   # nothing posted yet

        loot.receive(q, q.title, q.value)                                 # held, whatever the rules
        [item] = loot.queue.open()
        assert item.status == gate.HELD and "waits for your approval" in item.why[0]
        assert loot.rework_item(item, "add the browser version") == gate.REWORK
        assert await _until(pilot, lambda: len(questions()) == 2)         # the same ork drafts again
        assert "add the browser version" in writer.prompts[1] and "## Approved" not in writer.prompts[1]
        assert [t.id for t in camp.state.asked] == [task.id]               # the same task, no stray copy

        q2 = questions()[1]
        loot.receive(q2, q2.title, q2.value)
        edited = q2.value.replace("(v2)", "(v2, Safari 18)")
        loot.accept_item(item, edited)
        assert await _until(pilot, lambda: any(p.mode == "pool.done" for p in sent))
        assert "## Approved" in writer.prompts[2] and "Safari 18" in writer.prompts[2]   # your edit goes out
        done = next(p for p in sent if p.mode == "pool.done")
        assert "APP-42" in done.value and "published to Jira" in done.value
        assert task.status == "done" and not task.draft and not camp.state.asked
        assert {"approve", "publish"} <= {d.action for d in camp.state.decisions()}


@pytest.mark.asyncio
async def test_the_fire_approves_or_sends_back_without_a_loot(fake_repo: Path, monkeypatch):
    writer = Writer()
    monkeypatch.setattr(BarracksWorker, "git", FakeGit(commits=0))
    monkeypatch.setattr(BarracksWorker, "steward_runner", Steward())
    monkeypatch.setattr(BarracksWorker, "work_runner", staticmethod(writer))
    monkeypatch.setattr(BarracksWorker, "worktree_maker", staticmethod(lambda repo, bid, orc: (fake_repo, f"pool/{bid}/x")))
    assert masonry.save_spec(fake_repo, CAMP) == []
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        camp = app.desktop.get_window("camp").query_one(PoolView)
        camp.add_task("Jira bug", "file it")
        assert await _until(pilot, lambda: bool(camp.state.asked))
        task = camp.state.asked[0]
        assert "🔥 Foreman asks" in camp.mini_status()[0]
        camp.answer(task.id, None)                                        # Esc: still waits
        assert camp.state.asked == [task]
        camp.answer(task.id, "shorter title")                             # what to change → drafted again
        assert await _until(pilot, lambda: len(writer.prompts) == 2 and bool(camp.state.asked))
        assert "shorter title" in writer.prompts[1]
        camp.answer(task.id, "")                                          # Enter on nothing: publish as is
        assert await _until(pilot, lambda: task.status == "done")
        assert "## Approved" in writer.prompts[2] and "(v2)" in writer.prompts[2]
