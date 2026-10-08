"""🛑 Stop all stops every agent the town runs, whoever started it (realm/halt.py is the one list), the HUD
counts them all, and the Wiki's librarian neither comes back by itself after it nor starts without a change."""
from __future__ import annotations

import threading
import time
from pathlib import Path

import pytest

from orkcraft.core import buildings
from orkcraft.core.workers import scrolls
from orkcraft.core.workers.scrolls import ScrollsWorker
from orkcraft.gui import state
from orkcraft.gui.host import Host
from orkcraft.realm import checkpoint, halt, jobs, roads

SLEEP = ["sleep", "30"]


def _until(test, seconds: float = 5.0) -> None:
    end = time.monotonic() + seconds
    while not test():
        if time.monotonic() > end:
            raise AssertionError("never happened")
        time.sleep(0.02)


def test_stop_all_leaves_no_agent_of_any_building_alive(fake_repo: Path, monkeypatch):
    """Each kind of building's agent runs (a real process): the HUD counts every one, Stop all kills every one."""
    monkeypatch.setattr(roads, "_harness_cmd", lambda *a, **k: SLEEP)
    monkeypatch.setattr(jobs, "work_cmd", lambda *a, **k: SLEEP)
    cancel = threading.Event()
    ends: dict[str, BaseException | None] = {}
    by_road = {"barracks": "camp/grunt", "council": "fire/clan", "mill": "grinder/miller", "mine": "pit/digger",
               "gramophone": "horn/voice", "watchtower": "tower/lookout", "fields": "board/taskmaster"}
    by_work = {"scrolls": "dump/librarian", "barracks:work": "camp/grunt-2"}
    calls = {**{k: (lambda who=who: roads.run_agent("claude", "go", fake_repo, {"ORKCRAFT_ORC": who}, cancel))
                for k, who in by_road.items()},
             **{k: (lambda who=who: jobs.run_work("claude", "go", fake_repo, cancel, env={"ORKCRAFT_ORC": who}))
                for k, who in by_work.items()},
             "town_hall": lambda: halt.run(SLEEP, who="claude", agent=True),     # a model call (builders._call)
             "catapult": lambda: halt.run(SLEEP, who="catapult")}                 # a browser, a script, a test

    def run(kind: str, fn) -> None:
        try:
            fn()
            ends[kind] = None
        except BaseException as e:   # noqa: BLE001 — what each one raised is the test's
            ends[kind] = e

    threads = [threading.Thread(target=run, args=(k, fn), daemon=True) for k, fn in calls.items()]
    for t in threads:
        t.start()
    _until(lambda: len(halt.live()) == len(calls))
    assert halt.agents() == len(calls) - 1 and {w for w, _ in halt.live()} >= {"dump/librarian", "fire/clan"}

    checkpoint.ensure(fake_repo)
    host = Host(fake_repo, auto_commit=False)
    hud = state.hud(host.town, host.muster, host.treasury)
    assert hud["agents_working"] == halt.agents() and hud["agents"] >= hud["agents_working"]   # not 0/…

    assert host.command("halt", {}) >= len(calls)
    for t in threads:
        t.join(5)
    assert halt.live() == [] and halt.agents() == 0
    assert all(isinstance(ends[k], InterruptedError) for k in calls), ends     # Halted: never "the model failed"
    assert state.hud(host.town, host.muster, host.treasury)["agents_working"] == 0


class Librarian:
    def __init__(self) -> None:
        self.calls = 0
        self.wait = False

    def __call__(self, harness, prompt, workdir, cancel, model, env, resume):
        self.calls += 1
        if self.wait and cancel.wait(5):
            raise InterruptedError("stopped")
        return "done", 0.01, None, ""


def _wiki(fake_repo: Path, monkeypatch) -> tuple[Host, ScrollsWorker, Librarian]:
    librarian = Librarian()
    monkeypatch.setattr(ScrollsWorker, "work_runner", librarian)
    monkeypatch.setattr(scrolls, "SETTLE_S", 0)
    monkeypatch.setenv("ORKCRAFT_WIKI_AUTO", "1")
    (fake_repo / "docs").mkdir(exist_ok=True)
    (fake_repo / "docs" / "a.md").write_text("# A\n\none\n")
    checkpoint.ensure(fake_repo)
    host = Host(fake_repo, auto_commit=False)
    spec = buildings.type_spec(host.town, "scrolls")
    spec["config"] = {**(spec.get("config") or {}), "sources": ["docs"], "commit": False}
    w = host.town.worker(buildings.raise_spec(host.town, spec).id)
    return host, w, librarian


def _settle(w) -> None:
    _until(lambda: not w.running)


def test_the_wiki_starts_by_itself_only_on_a_real_change(fake_repo: Path, monkeypatch):
    host, w, librarian = _wiki(fake_repo, monkeypatch)
    w.refresh()
    w.refresh()
    assert w.pending and librarian.calls == 0                 # what waited at the first look is the button's
    (fake_repo / "docs" / "a.md").write_text("# A\n\ntwo\n")
    w.refresh()
    _settle(w)
    assert librarian.calls == 1                               # a source changed: taken in by itself
    for _ in range(3):
        w.refresh()
    _settle(w)
    assert librarian.calls == 1                               # nothing changed since: nothing starts


def test_after_stop_all_the_librarian_does_not_come_back_by_itself(fake_repo: Path, monkeypatch):
    host, w, librarian = _wiki(fake_repo, monkeypatch)
    w.refresh()
    librarian.wait = True
    (fake_repo / "docs" / "a.md").write_text("# A\n\ntwo\n")
    w.refresh()
    assert w.running == "ingest" and librarian.calls == 1
    host.command("halt", {})
    _settle(w)
    assert w.log.read()[0].outcome == "interrupted"
    for _ in range(3):
        w.refresh()
    assert not w.running and librarian.calls == 1             # Stop all held: the same sources start nothing
    librarian.wait = False
    (fake_repo / "docs" / "b.md").write_text("# B\n")
    w.refresh()
    _settle(w)
    assert librarian.calls == 2                               # a new change after it does


def test_a_look_at_the_wiki_writes_nothing(fake_repo: Path, monkeypatch):
    """The analysis only reads: no source, no page, no rules file changes while the Wiki looks."""
    host, w, librarian = _wiki(fake_repo, monkeypatch)
    monkeypatch.setattr(scrolls, "SETTLE_S", 3600)

    def files() -> dict[str, float]:
        return {str(p.relative_to(fake_repo)): p.stat().st_mtime_ns for p in fake_repo.rglob("*")
                if p.is_file() and ".git" not in p.parts and ".orkcraft" not in p.parts}

    before = files()
    for _ in range(3):
        w.refresh()
    assert files() == before and librarian.calls == 0


@pytest.fixture(autouse=True)
def _no_live_left():
    yield
    halt.halt_all()
