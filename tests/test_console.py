"""Tests for the RTS console, focus state machine, command card, HUD and presets modal."""
from __future__ import annotations

from pathlib import Path

import pytest
from textual.widgets import OptionList, Static

from orkcraft.app import OrkcraftApp
from orkcraft.screens.console import ClanRoster, CommandCard, Console, WarMap
from orkcraft.screens.presets_modal import PresetsModal
from orkcraft.widgets.hud import Hud

SIZE = (200, 50)


@pytest.mark.asyncio
async def test_console_columns_and_no_base(fake_repo: Path):
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        console = app.screen.query_one("#console", Console)
        assert console.display is True
        warmap = console.query_one(WarMap)
        roster = console.query_one(ClanRoster)
        cmd_card = console.query_one(CommandCard)
        assert warmap is not None and roster is not None and cmd_card is not None
        assert len(app.screen.query("#base")) == 0


@pytest.mark.asyncio
async def test_escape_neutral_state_command_card_and_check_action(fake_repo: Path):
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()
        assert app.focus_state.mode == "neutral"

        cmd_card = app.screen.query_one("#command-card", CommandCard)
        actions_list = cmd_card.query_one("#command-actions", OptionList)
        options = [str(actions_list.get_option_at_index(i).prompt) for i in range(actions_list.option_count)]
        combined = " ".join(options)
        assert "[B]" in combined and "[P]" in combined and "[S]" in combined and "[T]" in combined
        assert app.check_action("command_card", ("B",)) is True
        assert app.check_action("command_card", ("Y",)) is False


@pytest.mark.asyncio
async def test_clicking_window_enters_building_state(fake_repo: Path):
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        win = app.desktop.get_window("town_hall")
        r = win.region
        await pilot.click(None, offset=(r.x + 5, r.y))
        await pilot.pause()
        assert app.focus_state.mode == "building"
        assert app.focus_state.building_id == "town_hall"

        # Roster lists only its garrison
        roster = app.screen.query_one("#clan-roster", ClanRoster)
        roster_list = roster.query_one("#roster-list", OptionList)
        prompts = [str(roster_list.get_option_at_index(i).prompt) for i in range(roster_list.option_count)]
        assert any("Warchief" in p for p in prompts)
        assert not any("Quartermaster" in p for p in prompts)

        # Y and L notify without raising
        await pilot.press("Y")
        await pilot.pause()
        await pilot.press("L")
        await pilot.pause()

        # P toggles pin
        pinned_before = win.pinned
        await pilot.press("P")
        await pilot.pause()
        assert win.pinned != pinned_before


@pytest.mark.asyncio
async def test_choosing_orc_opens_its_inventory_and_escape_steps_back(fake_repo: Path):
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        await pilot.press("2")
        await pilot.pause()
        assert app.focus_state.mode == "building"

        roster = app.screen.query_one("#clan-roster", ClanRoster)
        roster_list = roster.query_one("#roster-list", OptionList)
        roster_list.focus()
        await pilot.press("1")
        await pilot.pause()
        assert app.focus_state.mode == "unit"
        assert app.focus_state.orc_key is not None

        assert app.screen.query_one("#info-orc").display               # Info: the orc's name, about, runs
        assert "Warchief" in str(app.screen.query_one("#io-name", Static).render())
        assert not app.screen.query_one("#io-dismiss").display           # a steward is never dismissed
        assert "INVENTORY" in str(roster.query_one("#roster-title", Static).render())
        assert roster_list.get_option_at_index(0).id == "inv:model"
        assert not app.screen.query_one("#command-card").display         # the orc's chat commands it

        await pilot.press("escape")
        await pilot.pause()
        assert app.focus_state.mode == "building"                        # back to its building
        await pilot.press("escape")
        await pilot.pause()
        assert app.focus_state.mode == "neutral"


@pytest.mark.asyncio
async def test_presets_modal_in_neutral_raises_building(fake_repo: Path):
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()
        assert app.focus_state.mode == "neutral"

        systems = app.desktop.get_window("systems")
        assert systems.hidden is True

        await pilot.press("P")
        await pilot.pause()
        assert isinstance(app.screen, PresetsModal)

        lst = app.screen.query_one("#presets-list", OptionList)
        sys_idx = None
        for i in range(lst.option_count):
            opt = lst.get_option_at_index(i)
            if opt.id == "building:systems":
                sys_idx = i
                break
        assert sys_idx is not None
        lst.highlighted = sys_idx
        await pilot.press("enter")
        await pilot.pause()

        assert not isinstance(app.screen, PresetsModal)
        assert systems.hidden is False
        assert app.focus_state.mode == "building"
        assert app.focus_state.building_id == "systems"


@pytest.mark.asyncio
async def test_hud_contents(fake_repo: Path):
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        hud_str = str(app.screen.query_one("#hud", Hud).render())
        assert "Menu (F10)" in hud_str
        assert "$— / $20.00" in hud_str
        assert "— / 128k" in hud_str


@pytest.mark.asyncio
async def test_viewport_90_cols_hides_console_and_ctrl_b_toggles(fake_repo: Path):
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=(90, 45)) as pilot:
        await pilot.pause()
        console = app.screen.query_one("#console", Console)
        assert console.display is False
        await pilot.press("ctrl+b")
        await pilot.pause()
        assert console.display is True


@pytest.mark.asyncio
async def test_console_sits_above_footer_and_keeps_bracket_labels(fake_repo: Path):
    """Review of stage 4: the console overlapped the Footer; Rich markup ate `[F1]` / `[Esc]`."""
    from textual.widgets import Footer

    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        console = app.screen.query_one("#console", Console)
        footer = app.screen.query_one(Footer)
        assert console.region.bottom <= footer.region.y
        assert "[F1]" in str(app.screen.query_one("#warmap-content", Static).render())
        assert "[Esc]" in str(app.screen.query_one("#command-footer", Static).render())


@pytest.mark.asyncio
async def test_space_on_roster_orc_row_does_not_halt_everything(fake_repo: Path):
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    blown: list[str] = []
    app.action_halt = lambda source="": blown.append(source)  # type: ignore[method-assign]
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()
        roster_list = app.screen.query_one("#roster-list", OptionList)
        orc_row = next(
            i for i in range(roster_list.option_count)
            if (roster_list.get_option_at_index(i).id or "").startswith("orc:")
        )
        roster_list.highlighted = orc_row
        await pilot.press("space")
        await pilot.pause()
        assert blown == []


@pytest.mark.asyncio
async def test_console_height_is_smaller_resizable_and_remembered(fake_repo: Path, isolated_layout_file: Path):
    import json

    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=(200, 50)) as pilot:
        await pilot.pause()
        console = app.screen.query_one("#console", Console)
        assert console.height_pct == 15 and console.region.height == 7       # 15 % of the 48 free rows (was 33, then 22 %)
        await pilot.press("escape", "alt+equals_sign", "alt+equals_sign")
        await pilot.pause()
        assert console.height_pct == 21
        # drag the top edge up to row 25: the console then spans rows 25..48 (24 of the 48 free rows)
        top = console.region.y
        await pilot.mouse_down(None, offset=(10, top))
        await pilot.hover(None, offset=(10, 25))
        await pilot.mouse_up(None, offset=(10, 25))
        await pilot.pause()
        assert console.height_pct == 50 and console.region.y == 25
        for _ in range(30):
            await pilot.press("alt+minus")
        assert console.height_pct == 10                                      # clamped
    data = json.loads(isolated_layout_file.read_text(encoding="utf-8"))
    assert data["preferences"]["console_height_pct"] == 10
    app2 = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app2.run_test(size=(200, 50)) as pilot:
        await pilot.pause()
        assert app2.screen.query_one("#console", Console).height_pct == 10


@pytest.mark.asyncio
async def test_a_question_in_the_garrison_opens_and_the_building_stays_selected(fake_repo: Path, monkeypatch):
    from orkcraft.realm.orcs import Alert
    from orkcraft.screens.orders import AlertModal

    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        alert = Alert("alt-1", "Which branch?", options=[("1", "main")])

        def ask(roster) -> None:
            orc = next(o for o in roster.orcs if o.building == "town_hall")
            orc.status, orc.alert = "alert", alert

        rebuild = app.muster.rebuild                 # the question stays while the roster is rebuilt each second
        monkeypatch.setattr(app.muster, "rebuild", lambda *a, **k: ask(r := rebuild(*a, **k)) or r)
        ask(app.roster)
        app.set_focus_state("building", building_id="town_hall")
        await pilot.pause()
        lst = app.screen.query_one("#roster-list", OptionList)
        row = lambda: str(lst.get_option_at_index(0).prompt)
        for _ in range(40):                       # the roster redraws on its own beat: a busy machine is slower
            if row().startswith("[1] ❓ "):
                break
            await pilot.pause(0.05)
        assert row().startswith("[1] ❓ ")
        lst.focus()
        await pilot.press("1")
        await pilot.pause()
        assert isinstance(app.screen, AlertModal)
        assert app.focus_state.mode == "building" and app.focus_state.building_id == "town_hall"
        await pilot.press("escape")
        for _ in range(40):
            await pilot.pause(0.05)
            if "❓" not in row():
                break
        assert "❓" not in row()
