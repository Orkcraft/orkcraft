"""Tests for the System Menu [F10], KeysCheatSheet, and graceful quit."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from textual.widgets import OptionList

from orkcraft.app import ACTIVE_COMMAND_KEYS, OrkcraftApp
from orkcraft.screens.console import ClanRoster
from orkcraft.screens.system_menu import (
    KEY_GROUPS,
    KeysCheatSheet,
    QuitConfirm,
    SystemMenu,
)
from orkcraft.widgets.hud import Hud

SIZE = (200, 50)


async def _wait_for(pilot, predicate, tries: int = 60):
    for _ in range(tries):
        if predicate():
            return True
        await pilot.pause(0.05)
    return predicate()


@pytest.mark.asyncio
async def test_f10_opens_system_menu_escape_closes_and_hud_click_opens(fake_repo: Path):
    """1. F10 opens SystemMenu with six rows; escape closes; the HUD segment click opens it too."""
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()

        # F10 opens SystemMenu with six rows
        await pilot.press("f10")
        await pilot.pause()
        assert isinstance(app.screen, SystemMenu)
        menu_list = app.screen.query_one("#system-menu-list", OptionList)
        assert menu_list.option_count == 14                # + 🔍 Audit, 🧹 Clean up, 🔧 Self-improvement, 🗓 Weekly, ⚙ Settings (T1108), 🧭 Onboarding

        # F10 while open closes it
        await pilot.press("f10")
        await pilot.pause()
        assert not isinstance(app.screen, SystemMenu)

        # F10 opens again, and escape closes
        await pilot.press("f10")
        await pilot.pause()
        assert isinstance(app.screen, SystemMenu)
        await pilot.press("escape")
        await pilot.pause()
        assert not isinstance(app.screen, SystemMenu)

        # HUD segment click opens it too
        hud = app.screen.query_one("#hud", Hud)
        r = hud.region
        await pilot.click(None, offset=(r.x + hud._menu_span[0] + 3, r.y))   # the Menu · War Horn segment
        await pilot.pause()
        assert isinstance(app.screen, SystemMenu)
        await pilot.press("escape")
        await pilot.pause()
        assert not isinstance(app.screen, SystemMenu)


@pytest.mark.asyncio
async def test_f10_6_toggles_terrain(fake_repo: Path):
    """2. F10 → 6 toggles the terrain (desktop solid_black flips)."""
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        initial = app.desktop.solid_black

        await pilot.press("f10")
        await pilot.pause()
        assert isinstance(app.screen, SystemMenu)

        await pilot.press("6")
        await pilot.pause()
        assert not isinstance(app.screen, SystemMenu)
        assert app.desktop.solid_black != initial

        # Toggle back
        await pilot.press("f10", "6")
        await pilot.pause()
        assert app.desktop.solid_black == initial


@pytest.mark.asyncio
async def test_f10_2_captures_screenshot_without_menu(fake_repo: Path):
    """3. F10 → 2 writes one .svg under <fake_repo>/loot/screenshots/; SVG has no menu."""
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        screenshots_dir = fake_repo / "loot" / "screenshots"

        await pilot.press("f10")
        await pilot.pause()
        assert isinstance(app.screen, SystemMenu)

        await pilot.press("2")
        assert await _wait_for(pilot, lambda: len(list(screenshots_dir.glob("*.svg"))) == 1, tries=40)
        svgs = list(screenshots_dir.glob("*.svg"))
        assert len(svgs) == 1
        svg_content = svgs[0].read_text(encoding="utf-8")
        assert "SYSTEM & CLAN OPERATIONS" not in svg_content


@pytest.mark.asyncio
async def test_f10_5_saves_town_scroll(fake_repo: Path, isolated_layout_file: Path):
    """4. F10 → 5 saves: the Town Scroll file exists afterwards."""
    isolated_layout_file.unlink(missing_ok=True)
    assert not isolated_layout_file.exists()

    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False, layout_file=isolated_layout_file)
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()

        # Ensure file does not exist before manual save
        isolated_layout_file.unlink(missing_ok=True)

        await pilot.press("f10")
        await pilot.pause()
        assert isinstance(app.screen, SystemMenu)

        await pilot.press("7")
        await pilot.pause()
        assert not isinstance(app.screen, SystemMenu)
        assert isolated_layout_file.exists()
        data = json.loads(isolated_layout_file.read_text(encoding="utf-8"))
        assert "buildings" in data


@pytest.mark.asyncio
async def test_f10_3_opens_keys_cheat_sheet(fake_repo: Path):
    """5. F10 → 3 opens KeysCheatSheet; text contains every capital Command Card key and F1, F9, F10, alt+t."""
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()

        await pilot.press("f10")
        await pilot.pause()
        assert isinstance(app.screen, SystemMenu)

        await pilot.press("3")
        await pilot.pause()
        assert isinstance(app.screen, KeysCheatSheet)
        sheet = app.screen
        text = sheet.text

        # All capital command card keys from ACTIVE_COMMAND_KEYS
        all_capital_keys = set().union(*ACTIVE_COMMAND_KEYS.values())
        for key in all_capital_keys:
            assert key in text, f"Missing Command Card key {key} in KeysCheatSheet"

        # Explicit keys required by spec
        for key in ("F1", "F9", "F10", "alt+t"):
            assert key in text, f"Missing key {key} in KeysCheatSheet"

        # Esc closes
        await pilot.press("escape")
        await pilot.pause()
        assert not isinstance(app.screen, KeysCheatSheet)

        # '?' closes when opened via show_help
        await pilot.press("question_mark")
        await pilot.pause()
        assert isinstance(app.screen, KeysCheatSheet)
        await pilot.press("q")
        await pilot.pause()
        assert not isinstance(app.screen, KeysCheatSheet)


@pytest.mark.asyncio
async def test_graceful_quit_no_running_terminal(fake_repo: Path, isolated_layout_file: Path):
    """6a. q with no running terminal exits (app.return_code set / app no longer running)."""
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False, layout_file=isolated_layout_file)
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        await pilot.press("q")
        await pilot.pause()
        assert not app.is_running
        assert app.return_code is not None


@pytest.mark.asyncio
async def test_graceful_quit_with_running_terminal(fake_repo: Path, isolated_layout_file: Path, monkeypatch: pytest.MonkeyPatch):
    """6b. with running terminal, q shows QuitConfirm; n stays; q then y exits and terminal stops."""
    monkeypatch.setattr("orkcraft.app.deploy_command", lambda harness, prompt: ["cat"])
    monkeypatch.setattr("orkcraft.sources.sessions.deploy_command", lambda harness, prompt: ["cat"])

    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False, layout_file=isolated_layout_file)
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()

        # Select building 2 (Forge), focus roster, pick resident orc, deploy with 'C'
        await pilot.press("2")
        await pilot.pause()
        assert app.focus_state.mode == "building"

        roster = app.screen.query_one("#clan-roster", ClanRoster)
        roster_list = roster.query_one("#roster-list", OptionList)
        roster_list.focus()
        await pilot.press("1")
        await pilot.pause()
        assert app.focus_state.mode == "unit"

        await pilot.press("C")
        await pilot.pause(0.2)
        assert await _wait_for(pilot, lambda: any(t.running for t in app.chat.terminals.values()), tries=40)
        running_terms = [t for t in app.chat.terminals.values() if t.running]
        assert len(running_terms) > 0

        # Leave terminal so 'q' goes to app
        await pilot.press("f12")
        await pilot.pause()

        # Press 'q' -> QuitConfirm modal appears
        await pilot.press("q")
        await pilot.pause()
        assert isinstance(app.screen, QuitConfirm)
        assert app.is_running

        # Press 'n' -> stays, modal dismissed
        await pilot.press("n")
        await pilot.pause()
        assert not isinstance(app.screen, QuitConfirm)
        assert app.is_running

        # Press 'q' then 'y' -> exits and stops running terminal
        await pilot.press("q")
        await pilot.pause()
        assert isinstance(app.screen, QuitConfirm)

        await pilot.press("y")
        await pilot.pause(0.2)
        await _wait_for(pilot, lambda: not app.is_running, tries=40)
        assert not app.is_running
        await _wait_for(pilot, lambda: not any(t.running for t in running_terms), tries=40)
        assert not any(t.running for t in running_terms)
