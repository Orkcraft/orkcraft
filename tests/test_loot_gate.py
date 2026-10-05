"""📦 The Loot checkpoint: rules, the queue, rework rounds, needs-you, restore."""
from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest

from orkcraft import scroll as ts
from orkcraft.app import OrkcraftApp
from orkcraft.core.workers.barracks import BarracksWorker
from orkcraft.realm import gate, generated, masonry, pipes
from orkcraft.screens.typed.generator_view import GeneratorView

NOW = dt.datetime(2026, 10, 4, 12, 0)
SIZE = (200, 46)


def cart(value="the doc", source="barracks", ref="", trail=(), kind=pipes.TEXT) -> pipes.Payload:
    return pipes.Payload(kind, value, source, "pool.done", "Docs", tuple(trail), ref)


def test_rules_decide_what_waits():
    cheap = (pipes.hop("barracks", "scribe", "agent", 1000, 0.02, outcome="done", now=NOW),)
    dear = (pipes.hop("barracks", "scribe", "agent", 90000, 1.20, outcome="done", now=NOW),)
    assert gate.reasons(cart(trail=cheap), {}) == []
    assert gate.reasons(cart(), {"review": "always"}) and gate.reasons(cart(), {"review": "never", "sources": ["barracks"]}) == []
    assert gate.reasons(cart(), {"sources": ["barracks"]}) == ["from barracks"]
    assert gate.reasons(cart(trail=dear), {"max_cost_usd": 1}) == ["cost $1.20 > $1.00"]
    assert gate.reasons(cart(trail=dear), {"max_tokens": 50000}) == ["90000 tokens > 50000"]
    assert gate.reasons(cart(trail=cheap), {"max_cost_usd": 1, "max_tokens": 50000}) == []
    failed = (pipes.hop("barracks", "scribe", "agent", outcome="error", now=NOW),)
    assert gate.reasons(cart(trail=failed), {}) == ["barracks ended error"]
    assert gate.reasons(cart(trail=failed), {"on_failed": False}) == []
    redone = failed + (pipes.hop("barracks", "scribe", "agent", outcome="done", now=NOW),
                       pipes.hop("fire", "clan", "team", outcome="approved", now=NOW))
    assert gate.reasons(cart(trail=redone), {}) == []          # failed once, redone and approved: clean
    assert gate.reasons(cart("auth/login.py", kind=pipes.FILE), {"paths": ["auth/**"]}) == ["touches auth/login.py"]
    ctx = gate.Context(files=["migrations/0001.sql", "a.py", "b.py"], external=True)
    assert gate.reasons(cart(), {"paths": ["migrations"], "max_files": 2, "external": True}, ctx) == \
        ["touches migrations/0001.sql", "3 files > 2", "leaves the town"]


def test_rework_rounds_end_with_the_person(tmp_path: Path):
    q = gate.Queue(tmp_path / "q")
    item = q.arrive(cart(ref="D-1"), ["from barracks"], NOW)
    assert (item.status, item.ref, item.attempts) == (gate.HELD, "D-1", 0)
    for n in (1, 2, 3):
        assert q.can_rework(item, {}) == (True, "")
        q.rework(item, f"fix {n}", NOW)
        again = q.arrive(cart("better", ref="D-1"), ["back"], NOW)
        assert again is item and (item.status, item.attempts, item.value) == (gate.HELD, n, "better")
    assert q.can_rework(item, {}) == (False, "sent back 3 times")
    assert q.can_rework(item, {"max_rework": 5})[0]
    q.needs_you(item, "no more rounds", NOW)
    assert q.open()[0] is item and item.status == gate.NEEDS_YOU
    assert gate.Queue(tmp_path / "q").get(item.id).notes == ["fix 1", "fix 2", "fix 3", "no more rounds"]  # saved
    q.accept(item, "fixed by hand", NOW)
    assert (item.status, item.value) == (gate.PASSED, "fixed by hand") and q.open() == []
    big = q.arrive(cart(ref="D-2", trail=(pipes.hop("x", tokens=5000, now=NOW),)), ["held"], NOW)
    assert q.can_rework(big, {"rework_tokens": 4000}) == (False, "the chain spent 5000 tokens")
    assert q.arrive(cart(), ["held"], NOW).ref.startswith("loot-")        # no ref: one is given


def test_rejected_files_come_back_and_odd_names_work(fake_repo: Path):
    (fake_repo / "src" / "макет 1.svg").write_text("<svg/>\n")
    (fake_repo / "loot" / "new-report.md").write_text("# kept by Loot\n")
    rv = generated.Review(fake_repo, fake_repo / ".orkcraft" / "generator" / "g")
    assert [g.path for g in rv.files()] == ["src/макет 1.svg"]           # unescaped; Loot's own folder skipped
    assert rv.preview("src/макет 1.svg") == "<svg/>"
    rv.reject("src/макет 1.svg")
    assert not (fake_repo / "src" / "макет 1.svg").exists() and [r["path"] for r in rv.rejected()] == ["src/макет 1.svg"]
    rv.restore("src/макет 1.svg")
    assert (fake_repo / "src" / "макет 1.svg").read_text() == "<svg/>\n" and rv.rejected() == []
    with pytest.raises(ValueError):
        rv.restore("src/макет 1.svg")


@pytest.mark.asyncio
async def test_the_checkpoint_holds_sends_back_and_burns(fake_repo: Path, monkeypatch):
    spec = {"id": "gate", "title": "Docs Gate", "icon": "📦", "orc": {"name": "Quartermaster"}, "type": "loot",
            "config": {"sources": ["barracks"], "max_rework": 2}}
    assert masonry.save_spec(fake_repo, spec) == []
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    for ev in ("loot.passed", "loot.rework", "loot.needs_you"):
        ts.subscribe(app.scroll, "town_hall", "gate", ev)
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        sent, returned = [], []
        monkeypatch.setattr(app.roads, "emit", lambda payload, meta=None: sent.append(payload) or [])
        monkeypatch.setattr(app, "return_for_rework", lambda src, p: returned.append((src, p)) or True)
        view = app.desktop.get_window("gate").query_one(GeneratorView)
        hop = pipes.hop("barracks", "scribe", "agent", 4000, 0.05, outcome="done")

        view.receive(cart("draft", trail=(hop,), ref="D-1"), "Docs", "draft")      # from barracks: held
        [item] = view.queue.open()
        assert item.status == gate.HELD and view.burning() and "gate" in app._loot_burning()
        assert "1 held" in view.mini_status()[0]
        view.receive(cart("ok", source="mill"), "Docs", "ok")                      # passes at once
        assert [p.mode for p in sent] == ["loot.passed"] and sent[0].value == "ok"      # loot.stored: no road

        assert view.rework_item(item, "too vague") == gate.REWORK and not view.burning()
        [(src, back)] = returned
        assert src == "barracks" and back.ref == "D-1" and "too vague" in back.value and back.trail == (hop,)
        view.receive(cart("draft 2", trail=(hop,), ref="D-1"), "Docs", "draft 2")  # the same item comes back
        assert view.queue.open() == [item] and item.attempts == 1 and item.why[0] == "back from rework (round 1)"
        view.rework_item(item, "still vague")
        view.receive(cart("draft 3", ref="D-1"), "Docs", "draft 3")
        assert view.rework_item(item, "no") == gate.NEEDS_YOU and len(returned) == 2   # max_rework 2: stays
        assert view.burning() and sent[-1].mode == "loot.needs_you"

        view.accept_item(item, "fixed by hand")
        assert (sent[-1].mode, sent[-1].value, sent[-1].ref) == ("loot.passed", "fixed by hand", "D-1")
        assert [p.mode for p in sent].count("loot.rework") == 2
        assert not view.burning() and view.stored[0].title == "Docs"


@pytest.mark.asyncio
async def test_rework_goes_back_by_delivery_to_a_building_that_takes_work(fake_repo: Path, monkeypatch):
    for s in ({"id": "camp2", "title": "Camp", "icon": "🏕", "orc": {"name": "Grunts"}, "type": "barracks"},
              {"id": "council2", "title": "Clan Fire", "icon": "🪔", "orc": {"name": "Chieftains"}, "type": "council"},
              {"id": "crag", "title": "Crag", "icon": "🪨", "orc": {"name": "Carver"}, "type": "crag"}):
        assert masonry.save_spec(fake_repo, s) == []
    started = []
    monkeypatch.setattr(BarracksWorker, "receive", lambda self, payload, title, md: started.append((md, payload.ref,
                                                                                                   payload.trail)))
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        hop = pipes.hop("camp2", "grub", "agent", 100, 0.01)
        back = pipes.Payload(pipes.TEXT, "## Sent back\n\nfix it", "gate", "loot.rework", "rework: Docs", (hop,), "D-1")
        assert app.return_for_rework("camp2", back)
        assert [(r, t) for _, r, t in started] == [("D-1", (hop,))]
        assert app.return_for_rework("council2", back) == "camp2"     # a Clan Fire only reviews: back to who wrote it
        alone = pipes.Payload(pipes.TEXT, "fix it", "gate", "loot.rework", "rework: Docs", (), "D-2")
        assert not app.return_for_rework("council2", alone)            # nobody in its trail redoes work
        assert not app.return_for_rework("nowhere", alone)             # no such building
        assert not app.return_for_rework("town_hall", alone)           # not a typed building
        assert not app.return_for_rework("crag", alone)                # takes samples, does not redo work


@pytest.mark.asyncio
async def test_a_rework_finds_the_barracks_past_a_mill(fake_repo: Path, monkeypatch):
    for s in ({"id": "camp2", "title": "Camp", "icon": "🏕", "orc": {"name": "Grunts"}, "type": "barracks"},
              {"id": "grinder", "title": "Mill", "icon": "⚙️", "orc": {"name": "Miller"}, "type": "mill"}):
        assert masonry.save_spec(fake_repo, s) == []
    got = []
    monkeypatch.setattr(BarracksWorker, "receive", lambda self, payload, title, md: got.append(payload.ref))
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        trail = (pipes.hop("camp2", "grub", "agent", 100, 0.01), pipes.hop("grinder", "miller", "script"))
        back = pipes.Payload(pipes.TEXT, "fix it", "gate", "loot.rework", "rework: Docs", trail, "D-1")
        assert app.return_for_rework("grinder", back) == "camp2" and got == ["D-1"]
