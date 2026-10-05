"""Orc looks and visual badges (T1104 stage 1): lead / resident / worker, harness pairs,
the Roster by roads, and the Recruiter preview (stage 4)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from textual.widgets import Input, OptionList

from orkcraft.core import runners
from orkcraft import scroll as ts
from orkcraft.app import OrkcraftApp
from orkcraft.realm import chronicles, looks, roads, steward
from orkcraft.realm.orcs import RESIDENT, Orc, garrison_badge
from orkcraft.screens.garrison_modal import GarrisonModal
from orkcraft.screens.orc_flow import RecruitFailed, RecruitPreview, StewardView

SIZE = (200, 50)


def test_scheme_parts_and_badges():
    pair = [{"role": "write", "harness": "agy"}, {"role": "review", "harness": "claude"}]
    styles = [st for _, st in looks.scheme_parts(pair)]
    assert styles[0] == looks.HARNESS_STYLE["agy"] and styles[-1] == looks.HARNESS_STYLE["claude"]
    assert looks.scheme_long(pair) == "write: agy → review: claude"
    lead = Orc("Chieftain", "kanban", RESIDENT, lead=True, harness=[{"role": "run", "harness": "claude"}])
    scribe = Orc("Scribe", "digest", RESIDENT, kind="chain")
    assert garrison_badge([lead, scribe]) == "🧌 Chieftain+1 ✻ 🔨 💤"
    assert scribe.badge == "🪧 Scribe 🔨 💤"


def _scribe(app):
    ts.add_handler(app.scroll, "town_hall", "Scribe", kind="chain", chain=[{"op": "count"}], why="counting is enough")
    ts.subscribe(app.scroll, "town_hall", "loot", "on_selection_change", handler="scribe")


async def _settle(pilot, n=3):
    for _ in range(n):
        await pilot.pause()


@pytest.mark.asyncio
async def test_roster_by_roads_and_unit_card(fake_repo: Path):
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    _scribe(app)
    async with app.run_test(size=SIZE) as pilot:
        await _settle(pilot)
        chat = app.desktop.get_window("town_hall")
        await pilot.press(str(chat.number))
        await _settle(pilot)
        app.refresh_roster()
        await _settle(pilot)
        assert "🧌 Chieftain+1 ✻" in chat.badge
        lst = app.screen.query_one("#roster-list", OptionList)
        rows = [str(lst.get_option_at_index(i).prompt) for i in range(lst.option_count)]
        assert rows[0] == "[1] ★ Chieftain ✻ 💤" and rows[1] == "[2] Scribe 🪧 💤"
        assert len(rows) == 2
        lst.focus()
        await pilot.press("2")                       # the 2nd orc, not the 2nd row
        await _settle(pilot)
        assert app.focus_state.mode == "unit" and app.focus_state.orc_key.endswith("town_hall/scribe")
        about = str(app.screen.query_one("#io-about").render())
        assert "free chain (no model) on 📦 Artifacts · selection" in about and "Counting is enough." in about
        assert "🪙 free · never calls a model" in str(app.screen.query_one("#io-runs").render())
        assert str(lst.get_option_at_index(0).prompt).startswith("🪧 no model")     # its 🎒 inventory


GOOD = {"name": "Crier", "role": "done digest", "kind": "chain", "why": "a template is enough",
        "chain": [{"op": "template", "md": "✅ {id} — {title}"}],
        "roads": [{"from": "loot", "event": "on_selection_change", "filter": {"node_status": ["done"]}}]}


@pytest.mark.asyncio
async def test_r_asks_the_recruiter(fake_repo: Path, monkeypatch):
    monkeypatch.setattr(runners, "RECRUIT_RUNNER", lambda prompt: (json.dumps(GOOD), 0.05))
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=SIZE) as pilot:
        await _settle(pilot)
        await pilot.press(str(app.desktop.get_window("town_hall").number))
        await _settle(pilot)
        await pilot.press("R")
        await _settle(pilot)
        assert isinstance(app.screen, GarrisonModal)
        app.screen.query_one("#recruit-prompt", Input).value = "show finished tasks"
        await pilot.click("#recruit-ask")
        for _ in range(30):
            await pilot.pause(0.05)
            if isinstance(app.screen, RecruitPreview):
                break
        assert isinstance(app.screen, RecruitPreview)
        await pilot.press("enter")
        await _settle(pilot)
        chat = app.scroll.building("town_hall")
        crier = chat.garrison.handler("crier")
        assert crier.kind == "chain" and [r.handler for r in chat.roads] == ["crier"]
        assert "town_hall:loot-selection" in app.desktop.road_paths
        assert "orc_recruited" in [e["type"] for e in chronicles.history(fake_repo, "town_hall")]


@pytest.mark.asyncio
async def test_recruiter_failure_is_shown(fake_repo: Path, monkeypatch):
    monkeypatch.setattr(runners, "RECRUIT_RUNNER", lambda prompt: ("no idea", None))
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=SIZE) as pilot:
        await _settle(pilot)
        app.recruit_from_prompt("town_hall", "anything")
        for _ in range(30):
            await pilot.pause(0.05)
            if isinstance(app.screen, RecruitFailed):
                break
        assert isinstance(app.screen, RecruitFailed)
        assert app.scroll.building("town_hall").garrison.handlers == []


def _examples(repo: Path) -> None:
    path = roads.examples_file(repo, "town_hall", "seer")
    path.parent.mkdir(parents=True)
    titles = ["Ship login", "Plan the auth migration", "Fix calendar", "Docs", "Cache warmup", "CI"]
    with path.open("w") as f:
        for i, t in enumerate(titles):
            f.write(json.dumps({"inputs": [{"id": f"T10{i}0", "title": t}], "output": f"✅ T10{i}0 — {t}"}) + "\n")


DEMOTE = {"proposals": [{"type": "demote", "orc": "seer", "why": "always id and title",
                         "chain": [{"op": "template", "md": "✅ {id} — {title}"}]}]}


@pytest.mark.asyncio
async def test_w_watches_and_applies_a_ready_demotion(fake_repo: Path, monkeypatch):
    monkeypatch.setattr(runners, "STEWARD_RUNNER", lambda prompt: (json.dumps(DEMOTE), 0.05))
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    ts.add_handler(app.scroll, "town_hall", "Seer", orders="one line")
    ts.subscribe(app.scroll, "town_hall", "loot", "on_selection_change", handler="seer")
    _examples(fake_repo)
    async with app.run_test(size=SIZE) as pilot:
        await _settle(pilot)
        await pilot.press(str(app.desktop.get_window("town_hall").number))
        await _settle(pilot)
        app.refresh_roster()
        lst = app.screen.query_one("#roster-list", OptionList)
        lst.focus()
        await pilot.press("1")
        await _settle(pilot)
        assert app.focus_state.orc_key.endswith("town_hall/chieftain")
        await pilot.press("W")
        for _ in range(40):
            await pilot.pause(0.05)
            if isinstance(app.screen, StewardView):
                break
        assert isinstance(app.screen, StewardView)
        await _settle(pilot)
        await pilot.press("enter")
        await _settle(pilot)
        seer = app.scroll.building("town_hall").garrison.handler("seer")
        assert seer.kind == "chain" and seer.chain == DEMOTE["proposals"][0]["chain"]
        types = [e["type"] for e in chronicles.history(fake_repo, "town_hall")]
        assert "steward_report" in types and "proposal_applied" in types


@pytest.mark.asyncio
async def test_scheduled_steward_runs_in_the_background(fake_repo: Path, monkeypatch):
    calls = []
    monkeypatch.setattr(runners, "STEWARD_RUNNER", lambda prompt: calls.append(1) or (json.dumps(DEMOTE), 0.05))
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    ts.add_handler(app.scroll, "town_hall", "Seer", orders="one line")
    ts.subscribe(app.scroll, "town_hall", "loot", "on_selection_change", handler="seer")
    ts.update_orc(app.scroll, "town_hall", "chieftain", trigger={"type": "cron", "expression": "* * * * *"})
    _examples(fake_repo)
    async with app.run_test(size=SIZE) as pilot:
        await _settle(pilot)
        app.check_stewards()
        for _ in range(40):
            await pilot.pause(0.05)
            if steward.load_report(fake_repo, "town_hall"):
                break
        assert steward.load_report(fake_repo, "town_hall") is not None
        assert len(calls) == 1


def test_a_scroll_saved_with_the_old_moai_loads_with_the_signpost():
    from orkcraft.scroll import OrcSpec
    assert OrcSpec("a", "A", avatar="🗿", kind="chain").avatar == "🪧"
    assert OrcSpec("b", "B", avatar="🗿🧌", kind="hybrid").avatar == "🪧🧌"
    assert OrcSpec("c", "C").avatar == "🧌"
