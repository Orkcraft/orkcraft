"""🏕 Barracks under load and under failure: several orcs at once, agents that crash or stop,
worktrees that cannot be made, a budget that runs out mid-run."""
from __future__ import annotations

import threading
from pathlib import Path

import pytest

from orkcraft import scroll as ts
from orkcraft.app import OrkcraftApp
from orkcraft.realm import barracks as bk
from orkcraft.realm import masonry, pipes
from orkcraft.screens.typed.pool_view import PoolView

SIZE = (200, 46)


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
            return "ok", self.cost, 100, f"s{len(self.calls)}"
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


async def _open(pilot, app):
    await pilot.pause()
    view = app.desktop.get_window("camp").query_one(PoolView)
    sent = []
    app.roads.emit = lambda payload, meta=None: sent.append(payload) or []
    return view, sent


def _arrive(app, value):
    app.deliver_payload("camp", pipes.Payload(pipes.NODE, value, "loot", "on_selection_change", value), value, value)


def _app(repo: Path, monkeypatch, crew, maker=None, **config) -> OrkcraftApp:
    monkeypatch.setattr(PoolView, "work_runner", staticmethod(crew))
    monkeypatch.setattr(PoolView, "worktree_maker",
                        staticmethod(maker or (lambda r, bid, orc: (r, f"pool/{bid}/{orc.lower()}"))))
    assert masonry.save_spec(repo, spec(**config)) == []
    app = OrkcraftApp(repo_root=repo, auto_commit=False)
    for event in ("pool.assigned", "pool.done", "pool.failed", "pool.idle"):     # emit() sends only what is heard
        ts.subscribe(app.scroll, "town_hall", "camp", event)
    return app


@pytest.mark.asyncio
async def test_three_orcs_work_at_once_and_the_rest_queue(fake_repo: Path, monkeypatch):
    crew = Crew()
    app = _app(fake_repo, monkeypatch, crew)
    async with app.run_test(size=SIZE) as pilot:
        view, sent = await _open(pilot, app)
        for i in range(1, 7):
            _arrive(app, f"T10{i:02d}")
        assert await _until(pilot, lambda: crew.running == 3)
        st = view.state
        assert [o.name for o in st.orcs] == ["Grub", "Mogka", "Thrak"]                 # never a 4th
        assert all(o.status == "working" for o in st.orcs) and len(st.queue) == 3
        assert view.hut_lines([16] * 6)[0] == "active: 3/3"
        assert {c["env"]["ORKCRAFT_ORC"] for c in crew.calls} == {"camp/grub", "camp/mogka", "camp/thrak"}

        for i in range(6):                                                             # finish them as they come
            assert await _until(pilot, lambda: len(crew.calls) > i)
            crew.finish(i)
        assert await _until(pilot, lambda: not st.queue and all(o.status == "idle" for o in st.orcs))
        assert crew.peak == 3 and len(crew.calls) == 6
        assert sum(o.done for o in st.orcs) == 6 and st.stats["claude"] == {"runs": 6, "ok": 6, "cost": 0.6}
        modes = [p.mode for p in sent]
        assert modes.count("pool.assigned") == 6 and modes.count("pool.done") == 6 and modes.count("pool.idle") == 1


@pytest.mark.asyncio
async def test_a_crashing_agent_fails_its_task_only(fake_repo: Path, monkeypatch):
    crew = Crew()
    app = _app(fake_repo, monkeypatch, crew, max_orcs=2)
    async with app.run_test(size=SIZE) as pilot:
        view, sent = await _open(pilot, app)
        runs = []
        app.on_handler_run = runs.append
        for t in ("T2001", "T2002", "T2003"):
            _arrive(app, t)
        assert await _until(pilot, lambda: len(crew.calls) == 2)
        st = view.state

        crew.finish(0, RuntimeError("claude exited with 1: rate limited " + "x" * 500))
        assert await _until(pilot, lambda: len(crew.calls) == 3)                      # Grub takes T2003 anyway
        failed = next(t for t in st.tasks if t.key == "T2001")
        assert failed.status == "failed" and failed.error.startswith("claude exited with 1")
        assert len(failed.error) == 300                                               # cut, not the whole log
        grub = st.orc("Grub")
        assert grub.failed == 1 and grub.done == 0 and st.task(grub.task).key == "T2003"
        assert st.orc("Mogka").status == "working"                                    # the other orc never noticed
        fail = next(p for p in sent if p.mode == "pool.failed")
        assert "rate limited" in fail.value and "Grub" in fail.value
        assert runs[-1].outcome == "error" and "rate limited" in runs[-1].error

        crew.finish(1)
        crew.finish(2)
        assert await _until(pilot, lambda: all(o.status == "idle" for o in st.orcs))
        assert st.stats["claude"]["runs"] == 3 and st.stats["claude"]["ok"] == 2
        assert "✗ T2001 — Grub" in str(view.query_one("#pool-detail").render())

        _arrive(app, "T2001")                                                          # a retry goes back to Grub
        assert await _until(pilot, lambda: len(crew.calls) == 4)
        assert st.orc("Grub").status == "working" and crew.calls[3]["resume"] == "s3"
        crew.finish(3)
        assert await _until(pilot, lambda: st.orc("Grub").status == "idle")


@pytest.mark.asyncio
async def test_closing_the_building_stops_its_orcs(fake_repo: Path, monkeypatch):
    crew = Crew()
    app = _app(fake_repo, monkeypatch, crew, max_orcs=2)
    async with app.run_test(size=SIZE) as pilot:
        view, sent = await _open(pilot, app)
        runs = []
        app.on_handler_run = runs.append
        _arrive(app, "T3001")
        _arrive(app, "T3002")
        assert await _until(pilot, lambda: crew.running == 2)
        st = view.state
        view.on_unmount()                                                              # cancels every running job
        assert await _until(pilot, lambda: crew.running == 0 and all(o.status == "idle" for o in st.orcs))
        assert {t.error for t in st.tasks} == {"stopped"}
        assert runs == []                                                              # a stop is not a failed run
    again = bk.Barracks(fake_repo / ".orkcraft" / "pool" / "camp")
    assert all(o.status == "idle" for o in again.orcs)


@pytest.mark.asyncio
async def test_no_worktree_no_orc_and_the_task_is_not_lost(fake_repo: Path, monkeypatch):
    crew = Crew()
    tries = []

    def maker(repo, bid, orc):
        tries.append(orc)
        if len(tries) == 1:
            raise RuntimeError("fatal: 'pool/camp/grub' is already checked out")
        return repo, f"pool/{bid}/{orc.lower()}"

    app = _app(fake_repo, monkeypatch, crew, maker=maker)
    async with app.run_test(size=SIZE) as pilot:
        view, sent = await _open(pilot, app)
        _arrive(app, "T4001")
        await pilot.pause(0.1)
        st = view.state
        assert st.orcs == [] and crew.calls == []
        assert [t.key for t in st.queue] == ["T4001"]                                  # still waiting, not dropped

        assert view.quick_action("pool.hire")                                          # hiring by hand picks it up
        assert await _until(pilot, lambda: len(crew.calls) == 1)
        assert st.orcs[0].branch and st.task(st.orcs[0].task).key == "T4001"
        crew.finish(0)
        assert await _until(pilot, lambda: st.orcs[0].status == "idle")


@pytest.mark.asyncio
async def test_the_budget_stops_hiring_mid_run(fake_repo: Path, monkeypatch):
    crew = Crew(cost=0.6)
    app = _app(fake_repo, monkeypatch, crew, budget_usd=1.0)
    async with app.run_test(size=SIZE) as pilot:
        view, sent = await _open(pilot, app)
        _arrive(app, "T5001")
        _arrive(app, "T5002")
        assert await _until(pilot, lambda: len(crew.calls) == 2)
        crew.finish(0)
        crew.finish(1)
        st = view.state
        assert await _until(pilot, lambda: st.spent == 1.2)
        _arrive(app, "T5003")
        await pilot.pause(0.1)
        assert len(crew.calls) == 2 and st.queue[-1].decided.startswith("budget:")
        assert st.decisions(1)[0].action == "budget"
