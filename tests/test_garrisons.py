"""Tests for garrisons: persistent orcs, garrison badges, recruiting, deployment and dismissal."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from textual.widgets import Input, OptionList, Static

from orkcraft.app import OrkcraftApp
from orkcraft.realm.orcs import RESIDENT, WORKER, Orc, Trigger, garrison_badge
from orkcraft.screens.console import ClanRoster
from orkcraft.screens.garrison_modal import GarrisonModal
from orkcraft.screens.orders import UnitModal

SIZE = (200, 50)


def garrison_orcs(b: dict) -> list[dict]:
    """Steward first, then handlers — the v3 file layout of a garrison."""
    g = b["garrison"]
    return ([g["steward"]] if g.get("steward") else []) + g.get("handlers", [])


def test_garrison_badge():
    """1. garrison_badge: lead only → 🧌 Smith 🔨 💤; lead + 2 idle → Smith+2;
    one member in alert → ends with 🔥; one busy, none in alert → ⚙."""
    lead = Orc("Smith", "blacksmith", RESIDENT, Trigger(), "idle", lead=True)
    assert garrison_badge([lead]) == "🧌 Smith 🔨 💤"

    m1 = Orc("Coder", "tickets", RESIDENT, Trigger(), "idle")
    m2 = Orc("Tester", "qa", RESIDENT, Trigger(), "idle")
    badge_idle = garrison_badge([lead, m1, m2])
    assert "Smith+2" in badge_idle
    assert badge_idle == "🧌 Smith+2 🔨 💤"

    m1.status = "alert"
    badge_alert = garrison_badge([lead, m1, m2])
    assert badge_alert.endswith("🔥")

    m1.status = "busy"
    badge_busy = garrison_badge([lead, m1, m2])
    assert badge_busy.endswith("⚙")


@pytest.mark.asyncio
async def test_recruit_garrison_member(fake_repo: Path, isolated_layout_file: Path):
    """2. Building state on the Forge → R → modal → name 'Coder', role 'tickets', orders 'take T1001'
    → the scroll file has 2 Forge orcs; the Forge badge contains Chieftain+1; the roster lists
    [1] … Chieftain and [2] … Coder."""
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        await pilot.press("2")
        await pilot.pause()
        assert app.focus_state.mode == "building"
        assert app.focus_state.building_id == "town_hall"

        await pilot.press("R")
        await pilot.pause()
        assert isinstance(app.screen, GarrisonModal)
        modal = app.screen
        modal.query_one("#recruit-name", Input).value = "Coder"
        modal.query_one("#recruit-role", Input).value = "tickets"
        modal.query_one("#recruit-orders", Input).value = "take T1001"
        await pilot.click("#recruit-submit")
        await pilot.pause()

        assert not isinstance(app.screen, GarrisonModal)

        # The scroll file has 2 Forge members
        data = json.loads(isolated_layout_file.read_text(encoding="utf-8"))
        b_chat = next(b for b in data["buildings"] if b["id"] == "town_hall")
        assert len(garrison_orcs(b_chat)) == 2
        member_names = [m["name"] for m in garrison_orcs(b_chat)]
        assert "Chieftain" in member_names and "Coder" in member_names

        # The Forge badge contains Chieftain+1
        chat_win = app.desktop.get_window("town_hall")
        assert "Chieftain+1" in chat_win.badge

        # The roster lists [1] … Chieftain and [2] … Coder
        roster = app.screen.query_one("#clan-roster", ClanRoster)
        roster_list = roster.query_one("#roster-list", OptionList)
        prompts = [str(roster_list.get_option_at_index(i).prompt) for i in range(roster_list.option_count)]
        assert any("[1]" in p and "Chieftain" in p for p in prompts)
        assert any("[2]" in p and "Coder" in p for p in prompts)


@pytest.mark.asyncio
async def test_select_coder_and_edit_trigger(fake_repo: Path, isolated_layout_file: Path):
    """3. Select Coder (2 in Building state) → Unit card shows its orders and not deployed; T →
    UnitModal → saving a cron trigger writes it into Coder's OrcSpec in the scroll file."""
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        await pilot.press("2")
        await pilot.pause()
        await pilot.press("R")
        await pilot.pause()
        modal = app.screen
        modal.query_one("#recruit-name", Input).value = "Coder"
        modal.query_one("#recruit-role", Input).value = "tickets"
        modal.query_one("#recruit-orders", Input).value = "take T1001"
        await pilot.click("#recruit-submit")
        await pilot.pause()

        # Select Coder (2 in Building state)
        roster = app.screen.query_one("#clan-roster", ClanRoster)
        roster_list = roster.query_one("#roster-list", OptionList)
        roster_list.focus()
        await pilot.press("2")
        await pilot.pause()
        assert app.focus_state.mode == "unit"

        # Unit card shows its orders and not deployed
        card_rendered = str(app.screen.query_one("#info-body", Static).render())
        assert "take T1001" in card_rendered
        assert "not deployed" in card_rendered

        # T -> UnitModal -> saving a cron trigger writes it into Coder's OrcSpec in the scroll file
        await pilot.press("T")
        await pilot.pause()
        assert isinstance(app.screen, UnitModal)
        u_modal = app.screen
        u_modal.query_one("#unit-trigger").value = "cron"
        u_modal.query_one("#unit-expr").value = "*/15 * * * *"
        await pilot.click("#unit-save")
        await pilot.pause()

        assert not isinstance(app.screen, UnitModal)
        data = json.loads(isolated_layout_file.read_text(encoding="utf-8"))
        b_chat = next(b for b in data["buildings"] if b["id"] == "town_hall")
        coder_spec = next(m for m in garrison_orcs(b_chat) if m["name"] == "Coder")
        assert coder_spec["trigger"] == {"type": "cron", "expression": "*/15 * * * *"}


@pytest.mark.asyncio
async def test_dismiss_coder_and_keep_smith(fake_repo: Path, isolated_layout_file: Path):
    """4. D on Coder removes it; D on Chieftain notifies and keeps him."""
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        await pilot.press("2")
        await pilot.pause()
        await pilot.press("R")
        await pilot.pause()
        modal = app.screen
        modal.query_one("#recruit-name", Input).value = "Coder"
        modal.query_one("#recruit-role", Input).value = "tickets"
        await pilot.click("#recruit-submit")
        await pilot.pause()

        # Select Coder (2 in Building state)
        roster = app.screen.query_one("#clan-roster", ClanRoster)
        roster_list = roster.query_one("#roster-list", OptionList)
        roster_list.focus()
        await pilot.press("2")
        await pilot.pause()
        assert app.focus_state.mode == "unit"

        # D on Coder removes it and goes back to building state
        await pilot.press("D")
        await pilot.pause()
        assert app.focus_state.mode == "building"
        data = json.loads(isolated_layout_file.read_text(encoding="utf-8"))
        b_chat = next(b for b in data["buildings"] if b["id"] == "town_hall")
        assert len(garrison_orcs(b_chat)) == 1
        assert garrison_orcs(b_chat)[0]["name"] == "Chieftain"

        # Select Chieftain (1 in Building state)
        roster_list.focus()
        await pilot.press("1")
        await pilot.pause()
        assert app.focus_state.mode == "unit"

        # D on Chieftain notifies and keeps him
        await pilot.press("D")
        await pilot.pause()
        data2 = json.loads(isolated_layout_file.read_text(encoding="utf-8"))
        b_chat2 = next(b for b in data2["buildings"] if b["id"] == "town_hall")
        assert len(garrison_orcs(b_chat2)) == 1
        assert garrison_orcs(b_chat2)[0]["name"] == "Chieftain"


@pytest.mark.asyncio
async def test_deploy_coder(fake_repo: Path, monkeypatch: pytest.MonkeyPatch, isolated_layout_file: Path):
    """5. C on Coder with deploy_command replaced as above → app.deployments has one entry, the War Tent has
    that terminal, Coder shows deployed, the Warband group does not list that terminal, roster.active == 1."""
    monkeypatch.setattr("orkcraft.app.deploy_command", lambda harness, prompt: ["cat"])
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        await pilot.press("2")
        await pilot.pause()
        await pilot.press("R")
        await pilot.pause()
        modal = app.screen
        modal.query_one("#recruit-name", Input).value = "Coder"
        modal.query_one("#recruit-role", Input).value = "tickets"
        modal.query_one("#recruit-orders", Input).value = "take T1001"
        await pilot.click("#recruit-submit")
        await pilot.pause()

        # Select Coder
        roster = app.screen.query_one("#clan-roster", ClanRoster)
        roster_list = roster.query_one("#roster-list", OptionList)
        roster_list.focus()
        await pilot.press("2")
        await pilot.pause()
        assert app.focus_state.mode == "unit"

        # C on Coder deploys it
        await pilot.press("C")
        await pilot.pause()

        # app.deployments has one entry
        assert len(app.deployments) == 1
        term_key = next(iter(app.deployments.keys()))

        # the War Tent has that terminal
        assert term_key in app.chat.terminals
        term = app.chat.terminals[term_key]
        assert term.running

        # Coder shows deployed
        await pilot.press("escape")
        await pilot.pause()
        await pilot.press("2")
        await pilot.pause()
        roster_list.focus()
        await pilot.press("2")
        await pilot.pause()
        rendered = str(app.screen.query_one("#info-body", Static).render())
        assert "deployed" in rendered
        assert "not deployed" not in rendered

        # the Warband group does not list that terminal
        warband_workers = [o for o in app.roster.orcs if o.category == WORKER]
        assert not any(o.ref == term_key for o in warband_workers)

        # roster.active == 1
        for _ in range(20):                         # the roster refresh may land a beat later
            if app.roster.active == 1:
                break
            await pilot.pause(0.05)
        assert app.roster.active == 1
        term.stop()


@pytest.mark.asyncio
async def test_open_unit_badge_click_saves_orders_to_scroll(fake_repo: Path, isolated_layout_file: Path):
    """6. open_unit (badge click) on the Forge saves the lead's orders into the scroll (the old
    unit_context assertion of test_orcraft.py, moved to the new source)."""
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        chat = app.desktop.get_window("town_hall")
        r = chat.region
        await pilot.click(None, offset=(r.x + r.width - 4, r.y))
        await pilot.pause()
        assert isinstance(app.screen, UnitModal)
        modal = app.screen
        modal.query_one("#unit-context").value = "watch T1001"
        modal.query_one("#unit-trigger").value = "cron"
        modal.query_one("#unit-expr").value = "*/15 * * * *"
        await pilot.click("#unit-save")
        await pilot.pause()
        assert "🕒" in chat.badge
        data = json.loads(isolated_layout_file.read_text(encoding="utf-8"))
        b_chat = next(b for b in data["buildings"] if b["id"] == "town_hall")
        lead = b_chat["garrison"]["steward"]
        assert lead["trigger"] == {"type": "cron", "expression": "*/15 * * * *"}
        assert lead["orders"] == "watch T1001"


@pytest.mark.asyncio
async def test_recruit_modal_validation(fake_repo: Path):
    """Empty name in GarrisonModal shows error and keeps modal open."""
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        await pilot.press("2")
        await pilot.pause()
        await pilot.press("R")
        await pilot.pause()
        assert isinstance(app.screen, GarrisonModal)
        modal = app.screen
        modal.query_one("#recruit-name", Input).value = ""
        await pilot.click("#recruit-submit")
        await pilot.pause()
        assert isinstance(app.screen, GarrisonModal)
        err = modal.query_one("#recruit-error", Static)
        assert err.display is True
        assert "name" in str(err.render())
        await pilot.press("escape")
        await pilot.pause()
        assert not isinstance(app.screen, GarrisonModal)
