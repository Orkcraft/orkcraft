"""Unit card and info panel (T1104 stage 2): building stats, handler costs, picking a burning
orc opens its question, spend math, and the orc's chat column (stage 3)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from orkcraft import scroll as ts
from orkcraft.app import OrkcraftApp
from orkcraft.realm import roads, unit_info

SIZE = (200, 50)


def test_handler_spend_math(fake_repo: Path):
    assert unit_info.Spend().text() == "🪙 no data yet"
    log = fake_repo / "spend.jsonl"
    log.write_text("\n".join([
        json.dumps({"cost_usd": 0.05, "tokens": 2000}),
        json.dumps({"cost_usd": 0.15, "tokens": 8000}),
        json.dumps({"cost_usd": None, "tokens": 5000}),
    ]) + "\n")
    s = unit_info.handler_spend(log)
    assert (s.runs, round(s.usd, 2), s.tokens) == (3, 0.2, 15000)
    assert s.text() == "🪙 $0.20 · 🪵 15k tokens · 3 runs"
    assert unit_info.Spend(free=True).text() == "🪙 free · never calls a model"
    assert unit_info.Spend(free=True).add(s).usd == s.usd


@pytest.mark.asyncio
async def test_info_panel_for_a_building_and_an_agent_handler(fake_repo: Path):
    from textual.widgets import Static

    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    ts.add_handler(app.scroll, "town_hall", "Reviewer", kind="agent", harness=[{"role": "review", "harness": "claude"}])
    ts.subscribe(app.scroll, "town_hall", "loot", "on_selection_change", handler="reviewer")
    log = roads.examples_file(fake_repo, "town_hall", "reviewer")
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text(json.dumps({"cost_usd": 0.31, "tokens": 42000}) + "\n")
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        chat_win = app.desktop.get_window("town_hall")
        await pilot.press(str(chat_win.number))
        for _ in range(3):
            await pilot.pause()
        q = lambda sel: str(app.screen.query_one(sel, Static).render())
        assert not app.screen.query_one("#info-body").display and app.screen.query_one("#info-building").display
        assert "Town Hall" in q("#ib-name")
        assert q("#ib-about").strip()
        assert "🪙 $0.31 · 🪵 42k tokens · 1 run" in q("#ib-runs") and "👍 0 👎 0" in q("#ib-runs")
        assert "Listens: ◂" in q("#ib-listens") and "→ " in q("#ib-listens") and "Reviewer" in q("#ib-listens")
        lst = app.screen.query_one("#roster-list")
        lst.focus()
        await pilot.press("2")
        for _ in range(3):
            await pilot.pause()
        assert app.focus_state.mode == "unit"
        assert "Runs as an agent on 📦 Artifacts · selection." in q("#io-about")
        runs = q("#io-runs")
        assert "not deployed" in runs and "🪙 $0.31 · 🪵 42k tokens · 1 run" in runs
        assert str(lst.get_option_at_index(0).prompt).startswith("claude default")  # its 🎒 inventory


@pytest.mark.asyncio
async def test_picking_a_burning_orc_opens_its_question(fake_repo: Path):
    from orkcraft.screens.orders import AlertModal

    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    lead = app.scroll.building("town_hall").garrison.steward   # the scroll marks it waiting: the roster keeps it
    lead.status, lead.orders = "alert", "Ship on Friday?"
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        await pilot.press(str(app.desktop.get_window("town_hall").number))
        await pilot.pause()
        lst = app.screen.query_one("#roster-list")
        lst.focus()
        await pilot.press("1")
        for _ in range(3):
            await pilot.pause()
        assert isinstance(app.screen, AlertModal)                      # the question at once, no menu


# -- the orc's chat column (T1104 stage 3) -------------------------------------------------------

async def _settle(pilot, n: int = 4) -> None:
    for _ in range(n):
        await pilot.pause()


def _with_reviewer(app: OrkcraftApp) -> None:
    ts.add_handler(app.scroll, "town_hall", "Reviewer", kind="agent", harness=[{"role": "review", "harness": "claude"}],
                   orders="review the selected task")
    ts.subscribe(app.scroll, "town_hall", "loot", "on_selection_change", handler="reviewer")


@pytest.mark.asyncio
async def test_orc_chat_rises_alone_and_starts_a_session_with_the_message(fake_repo: Path, monkeypatch):
    from orkcraft.app import ORC_CHAT_PCT
    from orkcraft.screens.orc_chat import OrcChat

    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    _with_reviewer(app)
    calls = []
    monkeypatch.setattr(app, "deploy_resident", lambda orc, first_message="", show_tent=True:
                        calls.append((orc.name, first_message, show_tent)))
    async with app.run_test(size=SIZE) as pilot:
        await _settle(pilot)
        chat = app.screen.query_one(OrcChat)
        await pilot.press(str(app.desktop.get_window("town_hall").number))
        await _settle(pilot)
        assert not chat.display                                         # a building: the commands
        app.set_focus_state("unit", orc_key_val="orc:resident:town_hall/reviewer")
        await _settle(pilot)
        console = app.screen.query_one("#console")
        assert chat.display and chat.region.right == SIZE[0] and chat.region.bottom == console.region.bottom
        assert chat.region.height >= round(ORC_CHAT_PCT * (SIZE[1] - 2) / 100) - 1 > console.region.height
        assert "Reviewer · no live session" in str(chat.query_one("#orc-chat-title").render())
        await pilot.press("slash")
        await pilot.pause()
        assert app.focused is chat.query_one("#orc-chat-input")
        await pilot.press(*"look at T1001", "enter")
        await _settle(pilot)
        assert calls == [("Reviewer", "look at T1001", False)]          # its orders + the message, tent stays


@pytest.mark.asyncio
async def test_orc_chat_mirrors_a_live_session_and_types_into_it(fake_repo: Path):
    from orkcraft.screens.orc_chat import OrcChat

    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=SIZE) as pilot:
        await _settle(pilot)
        key = app.chat.deploy("w", ["sh", "-c", "echo hello-orc; cat"], "claude", "worker")
        for _ in range(40):
            await pilot.pause(0.05)
            if any("hello-orc" in ln for ln in app.chat.terminals[key].text_lines()):
                break
        app.refresh_roster()
        orc = next(o for o in app.roster.orcs if o.ref == key)
        from orkcraft.screens.console import orc_key
        app.set_focus_state("unit", orc_key_val=orc_key(orc))
        await _settle(pilot)
        chat = app.screen.query_one(OrcChat)
        assert chat.display and "live session" in str(chat.query_one("#orc-chat-title").render())
        assert "hello-orc" in str(chat.query_one("#orc-chat-log").render())
        sent = []
        app.chat.terminals[key].write = lambda data: sent.append(data)
        chat.query_one("#orc-chat-input").focus()
        await pilot.press(*"ping", "enter")
        await pilot.pause()
        assert sent == [b"ping\r"]
        app.chat.terminals[key].stop()


@pytest.mark.asyncio
async def test_orc_chat_lists_and_reopens_earlier_sessions(fake_repo: Path, monkeypatch):
    import datetime as dt
    from orkcraft.screens.orc_chat import OrcChat
    from orkcraft.sources import sessions

    past = sessions.Session("claude", "abc123", title="Reviewer · Preview", last=dt.datetime(2026, 9, 30, 9, 15),
                            orcs={"town_hall/reviewer"})
    other = sessions.Session("claude", "zzz", title="someone else", orcs={"loot/quartermaster"})
    monkeypatch.setattr(sessions, "collect_sessions", lambda repo, max_age=0: [past, other])
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    _with_reviewer(app)
    reopened = []
    monkeypatch.setattr(app, "resume_for_orc", lambda orc, s: reopened.append((orc.name, s.id)))
    async with app.run_test(size=SIZE) as pilot:
        await _settle(pilot)
        app.set_focus_state("unit", orc_key_val="orc:resident:town_hall/reviewer")
        await _settle(pilot)
        hist = app.screen.query_one(OrcChat).query_one("#orc-chat-history")
        rows = [str(hist.get_option_at_index(i).prompt) for i in range(hist.option_count)]
        assert rows == ["09-30 09:15  claude  Reviewer · Preview"]
        hist.focus()
        hist.highlighted = 0
        await pilot.press("enter")
        await pilot.pause()
        assert reopened == [("Reviewer", "abc123")]
