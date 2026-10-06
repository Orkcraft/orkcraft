"""Tests for Town Scroll runtime and Orkspaces (§1, §2, §3, §11 of T1093)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from textual.widgets import Input, OptionList, RadioButton, RadioSet, Static

from orkcraft import scroll as ts
from orkcraft.app import OrkcraftApp
from orkcraft.realm.buildings import presets, registry
from orkcraft.screens.console import WarMap
from orkcraft.screens.orkspace_modal import OrkspaceModal
from orkcraft.screens.presets_modal import PresetsModal
from orkcraft.widgets.hud import Hud
from orkcraft.widgets.terminal import Terminal
from orkcraft.wm.geometry import Geom

SIZE = (200, 50)


@pytest.mark.asyncio
async def test_first_start_writes_valid_v3_scroll(fake_repo: Path, isolated_layout_file: Path):
    """1. First start writes a valid v3 scroll (scroll.validate(json) == []) with main_camp on F1."""
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        assert isolated_layout_file.exists()
        data = json.loads(isolated_layout_file.read_text(encoding="utf-8"))
        assert ts.validate(data) == []
        assert data["version"] == "0.3.0"
        assert data["active_orkspace_id"] == "main_camp"
        assert len(data["orkspaces"]) >= 1
        main_camp = data["orkspaces"][0]
        assert main_camp["id"] == "main_camp"
        assert main_camp["hotkey"] == "F1"
        assert "main_camp" in [o["id"] for o in data["orkspaces"]]


@pytest.mark.asyncio
async def test_v1_layout_migrated_on_start(fake_repo: Path, isolated_layout_file: Path):
    """2. A v1 layout file ({"version": 1, "windows": {...}}) is migrated on start: pins and hidden flags survive."""
    v1_data = {
        "version": 1,
        "windows": {
            "loot": {
                "x": 10, "y": 2, "w": 50, "h": 20,
                "pinned": True, "hidden": False,
            },
            "systems": {
                "x": 0, "y": 0, "w": 30, "h": 10,
                "pinned": False, "hidden": True,
            },
        },
        "active": "loot",
        "order": ["systems", "loot"],
    }
    isolated_layout_file.write_text(json.dumps(v1_data), encoding="utf-8")
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        chat_win = app.desktop.get_window("loot")
        limits_win = app.desktop.get_window("systems")
        assert chat_win.pinned is True
        assert chat_win.hidden is False
        assert limits_win.pinned is False
        assert limits_win.hidden is True
        data = json.loads(isolated_layout_file.read_text(encoding="utf-8"))
        assert ts.validate(data) == []
        b_chat = next(b for b in data["buildings"] if b["id"] == "loot")
        b_limits = next(b for b in data["buildings"] if b["id"] == "systems")
        assert b_chat["pinned"] is True
        assert b_chat["demolished"] is False
        assert b_limits["pinned"] is False
        assert b_limits["demolished"] is True


@pytest.mark.asyncio
async def test_new_orkspace_modal_and_switching(fake_repo: Path, isolated_layout_file: Path):
    """3. N → modal → name 'Lab', biome ice → second orkspace on F2 active, empty canvas, biome-ice; F1 brings Main Camp back; F2 again."""
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        await pilot.press("N")
        await pilot.pause()
        assert isinstance(app.screen, OrkspaceModal)
        modal = app.screen
        modal.query_one("#orkspace-name", Input).value = "Lab"
        modal.query_one("#biome-ice", RadioButton).value = True
        await pilot.click("#create-btn")
        await pilot.pause()

        assert not isinstance(app.screen, OrkspaceModal)
        assert app.desktop.scroll.active_orkspace.name == "Lab"
        assert app.desktop.scroll.active_orkspace.hotkey == "F2"
        assert app.desktop.biome == "ice"
        assert app.desktop.has_class("biome-ice")
        # A fresh canvas: only the Town Hall, which stands on every canvas
        assert [w.window_id for w in app.desktop.windows if app.desktop.in_view(w) and not w.hidden] == ["town_hall"]

        # F1 brings Main Camp back
        await pilot.press("f1")
        await pilot.pause()
        assert app.desktop.scroll.active_orkspace_id == "main_camp"
        assert app.desktop.biome == "forest"
        assert app.desktop.has_class("biome-forest")
        assert len([w for w in app.desktop.windows if app.desktop.in_view(w) and not w.hidden]) > 0

        # F2 again keeps its empty canvas
        await pilot.press("f2")
        await pilot.pause()
        assert app.desktop.scroll.active_orkspace.name == "Lab"
        assert app.desktop.biome == "ice"
        assert [w.window_id for w in app.desktop.windows if app.desktop.in_view(w) and not w.hidden] == ["town_hall"]


@pytest.mark.asyncio
async def test_moving_window_persists_across_orkspace_switches_and_restarts(fake_repo: Path, isolated_layout_file: Path):
    """4. Moving a window in Main Camp, switching to F2 and back restores geometry; scroll file after restart has same bounds/frac."""
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        # Add second orkspace
        ts.new_orkspace(app.scroll, "Lab", "ice")

        chat = app.desktop.get_window("loot")
        await pilot.press("1")  # focus loot
        await pilot.press("alt+l", "alt+j")
        await pilot.pause()
        saved_geom = chat.geom
        saved_frac = chat.frac

        # Switch to F2: chat is hidden (away)
        await pilot.press("f2")
        await pilot.pause()
        assert chat.display is False

        # Switch back to F1: chat restored
        await pilot.press("f1")
        await pilot.pause()
        assert chat.display is True
        assert chat.geom == saved_geom
        assert chat.frac == saved_frac

    data = json.loads(isolated_layout_file.read_text(encoding="utf-8"))
    b_chat = next(b for b in data["buildings"] if b["id"] == "loot")
    assert b_chat["bounds"] == {"x": saved_geom.x, "y": saved_geom.y, "width": saved_geom.w, "height": saved_geom.h}
    # `to_dict` drops a None frac; a stored frac comes back as a list.
    assert b_chat.get("frac") == (list(saved_frac) if saved_frac is not None else None)

    # Restart app: geometry survives
    app2 = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app2.run_test(size=SIZE) as pilot2:
        await pilot2.pause()
        chat2 = app2.desktop.get_window("loot")
        assert chat2.geom == saved_geom
        assert chat2.frac == saved_frac


@pytest.mark.asyncio
async def test_presets_modal_moves_building_to_orkspace(fake_repo: Path, isolated_layout_file: Path):
    """5. In F2, P → choose Forge → moves to F2, visible; in F1 it is gone from taskbar and cycle."""
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        ts.new_orkspace(app.scroll, "Lab", "ice")
        app.desktop.switch_orkspace("lab")
        await pilot.pause()

        # In F2, press P to open PresetsModal
        await pilot.press("escape")
        await pilot.press("P")
        await pilot.pause()
        assert isinstance(app.screen, PresetsModal)

        # Choose Chat
        lst = app.screen.query_one("#presets-list", OptionList)
        chat_idx = None
        for i in range(lst.option_count):
            opt = lst.get_option_at_index(i)
            if opt.id == "building:loot":
                chat_idx = i
                break
        assert chat_idx is not None
        lst.highlighted = chat_idx
        await pilot.press("enter")
        await pilot.pause()

        assert not isinstance(app.screen, PresetsModal)
        assert app.scroll.orkspace_of("loot").id == "lab"
        chat = app.desktop.get_window("loot")
        assert app.desktop.in_view(chat) is True
        assert chat.display is True
        assert chat.hidden is False

        # Switch to F1: Chat is gone from F1's taskbar and cycle
        await pilot.press("f1")
        await pilot.pause()
        assert app.desktop.in_view(chat) is False
        assert chat.display is False
        tb_chat = app.screen.query_one("#taskbar-loot")
        assert tb_chat.display is False

        # Cycling windows in F1 never touches chat
        for _ in range(15):
            app.desktop.cycle(1)
            assert app.desktop.active is not chat


@pytest.mark.asyncio
async def test_warmap_lists_orkspaces_and_deletes_empty(fake_repo: Path, isolated_layout_file: Path):
    """6. War Map lists both orkspaces; d removes an empty one, refuses on Main Camp with a notify."""
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        ts.new_orkspace(app.scroll, "Lab", "ice")
        app._console.refresh_state(app.focus_state, app.roster)
        await pilot.pause()

        warmap = app.screen.query_one(WarMap)
        opt_list = warmap.query_one("#warmap-list", OptionList)
        assert opt_list.option_count == 2
        assert "Main Camp" in str(opt_list.get_option_at_index(0).prompt)
        assert "Lab" in str(opt_list.get_option_at_index(1).prompt)

        # Highlight Main Camp and try 'd' -> refused
        opt_list.highlighted = 0
        warmap.action_delete_orkspace()
        await pilot.pause()
        assert len(app.scroll.orkspaces) == 2

        # Highlight Lab and press 'd' -> deleted
        opt_list.highlighted = 1
        warmap.action_delete_orkspace()
        await pilot.pause()
        assert len(app.scroll.orkspaces) == 1
        assert app.scroll.orkspaces[0].id == "main_camp"
        assert opt_list.option_count == 1


@pytest.mark.asyncio
async def test_widget_identity_preserved_across_orkspace_switch(fake_repo: Path, isolated_layout_file: Path):
    """7. Chat / War Tent widget identity (Terminal instance) is preserved across an F1 → F2 → F1 round trip (not recreated)."""
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        ts.new_orkspace(app.scroll, "Lab", "ice")
        chat_win = app.desktop.get_window("town_hall")
        # No PTY in tests: the War Tent's ChatView (which owns the terminals) stands in.
        chat_view = app.chat

        # Switch to F2 and back to F1
        await pilot.press("f2")
        await pilot.pause()
        assert chat_win.display is True         # the Town Hall stands on every canvas

        await pilot.press("f1")
        await pilot.pause()
        chat_win_after = app.desktop.get_window("town_hall")
        assert chat_win_after is chat_win
        assert app.chat is chat_view and chat_view.is_attached


@pytest.mark.asyncio
async def test_hud_shows_budget_from_scroll(fake_repo: Path, isolated_layout_file: Path):
    """8. HUD shows the budget from the scroll (gold_session_limit_usd: 5.0 → $— / $5.00)."""
    building_presets = presets(registry())
    s = ts.default_scroll(building_presets)
    s.budget.gold_session_limit_usd = 5.0
    s.budget.lumber_context_limit_tokens = 65536
    s.budget.supply_max_workers = 7
    ts.save(isolated_layout_file, s)

    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        hud_str = str(app.screen.query_one("#hud", Hud).render())
        assert "$— / $5.00" in hud_str
        assert "— / 64k" in hud_str  # 65536 tokens = 64k
        assert "🥩 0/" in hud_str  # working / all agents; the cap no longer shows


@pytest.mark.asyncio
async def test_window_numbering_per_orkspace(fake_repo: Path, isolated_layout_file: Path):
    """Windows are numbered consecutively starting from 1 in each orkspace."""
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        # In F1 (Main Camp), active buildings start at 1
        main_wins = [w for w in app.desktop.windows if app.desktop.in_view(w)]
        assert sorted(w.number for w in main_wins) == list(range(1, len(main_wins) + 1))

        # Create Lab and move limits and systems into it
        lab = ts.new_orkspace(app.scroll, "Lab", "ice")
        ts.move_building(app.scroll, "loot", lab.id)
        ts.move_building(app.scroll, "systems", lab.id)

        # Switch to F2 (Lab)
        await pilot.press("f2")
        await pilot.pause()
        limits = app.desktop.get_window("loot")
        systems = app.desktop.get_window("systems")
        assert limits.number == 1
        assert systems.number == 2
        assert "1 ·" in str(limits.border_title)
        assert "2 ·" in str(systems.border_title)

        # Pressing '1' in Lab focuses limits
        await pilot.press("1")
        await pilot.pause()
        assert app.desktop.active is limits

        # Switch back to F1 (Main Camp): windows are numbered starting at 1 again
        await pilot.press("f1")
        await pilot.pause()
        f1_wins = [w for w in app.desktop.windows if app.desktop.in_view(w)]
        assert sorted(w.number for w in f1_wins) == list(range(1, len(f1_wins) + 1))
        assert limits.number > len(f1_wins)


@pytest.mark.asyncio
async def test_warmap_stays_visible_when_building_or_unit_focused(fake_repo: Path, isolated_layout_file: Path):
    """War Map option list always remains visible with all orkspaces regardless of focus state."""
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        warmap = app.screen.query_one(WarMap)
        opt_list = warmap.query_one("#warmap-list", OptionList)
        assert opt_list.display is True
        assert opt_list.option_count >= 1

        # Focus building 1
        await pilot.press("1")
        await pilot.pause()
        assert app.focus_state.mode == "building"
        assert opt_list.display is True
        assert opt_list.option_count >= 1

        # Focus an orc in clan roster
        roster_list = app.screen.query_one("#roster-list", OptionList)
        roster_list.focus()
        await pilot.press("1")
        await pilot.pause()
        assert app.focus_state.mode == "unit"
        assert opt_list.display is True
        assert opt_list.option_count >= 1

