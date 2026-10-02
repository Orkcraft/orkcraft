"""Orkcraft core: HUD, roster and passive ❓ alerts, pins, unit orders, viewports, War Horn."""
from __future__ import annotations

import json
import stat
from pathlib import Path

import pytest

from orkcraft.app import OrkcraftApp
from orkcraft.realm.orcs import clarification_text, detect_prompt
from orkcraft.screens.console import Console
from orkcraft.screens.orders import AlertModal, AwaitingOrdersModal, UnitModal
from orkcraft.widgets.hud import Hud
from orkcraft.widgets.terminal import Terminal
from textual.widgets import OptionList

SIZE = (200, 50)


# -- pure -------------------------------------------------------------------------------------

def test_detect_prompt_finds_numbered_menu_at_the_bottom():
    screen = [
        "╭──────────────────────────────╮",
        "│ Do you want to make this edit to app.py?",
        "│ ❯ 1. Yes",
        "│   2. Yes, and don't ask again this session",
        "│   3. No, and tell Claude what to do differently",
        "╰──────────────────────────────╯",
        "",
    ]
    question, options = detect_prompt([l.strip("│ ") for l in screen])
    assert "Do you want to make this edit" in question
    assert [k for k, _ in options] == ["1", "2", "3"]
    assert options[1][1].startswith("Yes, and don't ask")


def test_detect_prompt_finds_bracketed_menu():
    screen = [
        "Analyzing changes...",
        "Should we apply this patch?",
        "[1] Apply patch",
        "[2] Discard patch",
    ]
    res = detect_prompt(screen)
    assert res is not None
    question, options = res
    assert "Should we apply this patch" in question
    assert options == [("1", "Apply patch"), ("2", "Discard patch")]


def test_detect_prompt_finds_yes_no_prompts():
    # Prompt on same line
    screen1 = ["Building artifact...", "Do you want to run `git push`? [y/N]"]
    res1 = detect_prompt(screen1)
    assert res1 is not None
    q1, opts1 = res1
    assert "Do you want to run `git push`" in q1
    assert opts1 == [("y", "Yes"), ("n", "No")]

    # Prompt on separate line
    screen2 = ["Delete directory /tmp/scratch?", "[y/N]"]
    res2 = detect_prompt(screen2)
    assert res2 is not None
    q2, opts2 = res2
    assert "Delete directory /tmp/scratch" in q2
    assert opts2 == [("y", "Yes"), ("n", "No")]


def test_detect_prompt_ignores_plain_output_and_broken_numbering():
    assert detect_prompt(["1. only one option", "some output"]) is None
    assert detect_prompt(["1. a", "3. c"]) is None
    assert detect_prompt(["hello", "world"]) is None


def test_clarification_text_skips_comments_and_empty_sections():
    body = "## Clarification Needed\n\n<!-- open items -->\n\n## Result\n"
    assert clarification_text(body) == ""
    body = "## Clarification Needed\n\n- Which terminal?\n\n## Agent Report\n"
    assert clarification_text(body) == "- Which terminal?"


# -- helpers ------------------------------------------------------------------------------------

def _ask(app: OrkcraftApp, building_id: str = "loot", question: str = "Ship on Friday or Monday?") -> None:
    """The building's steward waits for orders: a scroll marks it `alert` (Warder does the same)."""
    lead = app.scroll.building(building_id).garrison.steward
    lead.status, lead.orders = "alert", question


async def _wait_for(pilot, predicate, tries: int = 60):
    for _ in range(tries):
        if predicate():
            return True
        await pilot.pause(0.05)
    return predicate()


# -- TUI --------------------------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_hud_base_and_badges(fake_repo: Path):
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        hud = str(app.screen.query_one("#hud", Hud).render())
        assert "Orkcraft" in hud and "Menu (F10) · 📯 READY" in hud and "🥩 0/5" in hud
        assert app.screen.query_one("#console", Console).display  # Full RTS at 200 cols
        loot = app.desktop.get_window("loot")
        assert "🧌 Quartermaster" in str(loot.border_title) and loot._badge_cells > 0
        names = {o.name for o in app.roster.orcs}
        assert {"Quartermaster", "Chieftain", "Mason", "Artisan"} <= names   # systems (Engineer) starts demolished: gone at the first roster tick


@pytest.mark.asyncio
async def test_a_waiting_orc_is_a_passive_alert(fake_repo: Path):
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    _ask(app)
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        assert [a.id for a in app.roster.alerts] == ["spec:loot/quartermaster"]
        assert app.roster.by_building("loot").status == "alert"
        assert "🔥 1 awaiting orders" in str(app.screen.query_one("#hud", Hud).render())
        assert not isinstance(app.screen, AlertModal)  # never opens by itself

        await pilot.press("exclamation_mark")
        await pilot.pause()
        assert isinstance(app.screen, AlertModal)
        await pilot.press("1")  # acknowledge
        await pilot.pause()
        assert app.roster.alerts == []


@pytest.mark.asyncio
async def test_badge_click_opens_unit_orders_and_saves_them(fake_repo: Path, isolated_layout_file: Path):
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        loot = app.desktop.get_window("loot")
        r = loot.region
        await pilot.click(None, offset=(r.x + r.width - 4, r.y))  # on the [ 🧌 Quartermaster … ] badge
        await pilot.pause()
        assert isinstance(app.screen, UnitModal)
        modal = app.screen
        modal.query_one("#unit-context").value = "watch T1001"
        modal.query_one("#unit-trigger").value = "cron"
        modal.query_one("#unit-expr").value = "*/15 * * * *"
        await pilot.click("#unit-save")
        await pilot.pause()
        quartermaster = app.roster.by_building("loot")
        assert quartermaster is not None and quartermaster.trigger.type == "cron" and quartermaster.task == "watch T1001"
        assert "🕒" in loot.badge
    data = json.loads(isolated_layout_file.read_text(encoding="utf-8"))
    b_loot = next(b for b in data["buildings"] if b["id"] == "loot")
    lead = b_loot["garrison"]["steward"]
    assert lead["trigger"] == {"type": "cron", "expression": "*/15 * * * *"}
    assert lead["orders"] == "watch T1001"


@pytest.mark.asyncio
async def test_pin_locks_the_slot_and_survives_restarts(fake_repo: Path, isolated_layout_file: Path):
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        forge = app.desktop.get_window("loot")
        start = forge.geom
        await pilot.press("alt+l")  # move right
        moved = forge.geom
        assert moved.x == start.x + 2
        await pilot.press("alt+b")  # pin
        assert forge.pinned and "📌" in str(forge.border_title)
        await pilot.press("alt+l", "alt+shift+l")
        assert forge.geom == moved  # pinned: neither moves nor resizes
        await pilot.press("ctrl+w", "t", "escape")  # tiling leaves pinned windows alone
        assert forge.geom == moved
    assert next(b for b in json.loads(isolated_layout_file.read_text(encoding="utf-8"))["buildings"] if b["id"] == "loot")["pinned"] is True

    app2 = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app2.run_test(size=SIZE) as pilot:
        await pilot.pause()
        forge2 = app2.desktop.get_window("loot")
        assert forge2.pinned and forge2.geom == moved


@pytest.mark.asyncio
@pytest.mark.parametrize("width,mode,console_display,single", [
    (200, "full", True, False),
    (120, "compact", True, False),
    (90, "minimal", False, True),
])
async def test_viewport_modes(fake_repo: Path, width, mode, console_display, single):
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=(width, 45)) as pilot:
        await pilot.pause()
        assert app.mode == mode
        assert app.screen.query_one("#console", Console).display is console_display
        assert app.desktop.single is single
        if single:
            active = app.desktop.active
            assert active.region.width == app.desktop.size.width
            others = [w for w in app.desktop.windows if w is not active and not w.hidden]
            assert all(w.styles.visibility == "hidden" for w in others)
            await pilot.press("tab")
            assert app.desktop.active is not active
        if mode == "minimal":
            await pilot.press("ctrl+b")
            assert app.screen.query_one("#console", Console).display


@pytest.fixture
def menu_cli(tmp_path: Path, monkeypatch) -> Path:
    """A stand-in CLI that asks a numbered question and echoes the answer."""
    script = tmp_path / "fake-claude"
    script.write_text(
        "#!/bin/bash\n"
        "trap 'echo INTERRUPTED' INT\n"
        "echo 'Do you want to proceed?'\necho '❯ 1. Yes'\necho '  2. No'\n"
        "read -n 1 answer\necho \"answer:$answer\"\n"
        "while true; do sleep 0.1; done\n"
    )
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("ORKCRAFT_CLAUDE_BIN", str(script))
    monkeypatch.setenv("ORKCRAFT_CLAUDE_HOME", str(tmp_path / "claude"))
    monkeypatch.setenv("ORKCRAFT_AGY_HOME", str(tmp_path / "agy"))
    return script


@pytest.mark.asyncio
async def test_worker_menu_becomes_alert_answer_goes_to_cli_and_war_horn_interrupts(fake_repo: Path, menu_cli: Path):
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        await pilot.press("plus")  # spawn an orc: new session in the War Tent
        term = app.screen.query_one(Terminal)
        assert await _wait_for(pilot, lambda: any("2. No" in l for l in term.text_lines()))
        assert await _wait_for(pilot, lambda: any(a.source == "terminal" for a in app.roster.alerts), tries=80)
        assert app.roster.active == 1
        assert "🥩 1/5" in str(app.screen.query_one("#hud", Hud).render())

        await pilot.press("f12", "exclamation_mark")  # leave the terminal, open the ❓
        await pilot.pause()
        assert isinstance(app.screen, AlertModal)
        await pilot.press("1")
        assert await _wait_for(pilot, lambda: any("answer:1" in l for l in term.text_lines()))

        await pilot.press("f12", "ctrl+p")  # War Horn
        assert await _wait_for(pilot, lambda: any("INTERRUPTED" in l for l in term.text_lines()))
        assert "SOUNDED" in str(app.screen.query_one("#hud", Hud).render())
        assert app.is_running
        term.stop()


@pytest.mark.asyncio
async def test_hud_click_opens_awaiting_orders_modal(fake_repo: Path):
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    _ask(app, "loot")
    _ask(app, "town_hall", "Option A or B?")   # systems starts demolished: its alert left at the first roster tick
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        assert len(app.roster.alerts) == 2
        hud = app.screen.query_one("#hud", Hud)
        assert "🔥 2 awaiting orders" in str(hud.render())
        astart, aend = hud._alerts_span
        assert astart > 0 and aend > astart

        # Click the HUD awaiting orders segment
        await pilot.click(Hud, offset=((astart + aend) // 2, 0))
        assert await _wait_for(pilot, lambda: isinstance(app.screen, AwaitingOrdersModal))
        assert len(app.screen.alerts) == 2
        orders_list = app.screen.query_one("#orders-list", OptionList)
        assert orders_list.option_count == 2

        # Answer first alert (1: acknowledge)
        await pilot.press("1")
        assert await _wait_for(pilot, lambda: len(getattr(app.screen, "alerts", [])) == 1)
        assert isinstance(app.screen, AwaitingOrdersModal)

        # Answer second alert (1: acknowledge)
        await pilot.press("1")
        assert await _wait_for(pilot, lambda: not isinstance(app.screen, AwaitingOrdersModal))
        assert app.roster.alerts == []
