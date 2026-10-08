"""Rally pipes as roads: `Y` on the receiver, selection routing, frame indicators and reports."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from textual.widgets import Input, OptionList

from orkcraft import scroll
from orkcraft.app import OrkcraftApp
from orkcraft.screens.console import ClanRoster

SIZE = (200, 50)


@pytest.mark.asyncio
async def test_clear_rally_point(fake_repo: Path, isolated_layout_file: Path):
    """U on the receiver removes its road."""
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    scroll.subscribe(app.scroll, "loot", "town_hall", "on_task_completed")
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        loot_win = app.desktop.get_window("loot")
        chat_win = app.desktop.get_window("town_hall")
        assert loot_win is not None and chat_win is not None
        await pilot.press(str(loot_win.number))
        await pilot.pause()
        assert app.focus_state.mode == "building"

        await pilot.press("U")
        await pilot.pause()

        assert app.scroll.rally_of("town_hall") is None
        data = json.loads(isolated_layout_file.read_text(encoding="utf-8"))
        assert all(not b.get("roads") for b in data["buildings"])


@pytest.mark.asyncio
async def test_task_completed_pipe(fake_repo: Path, monkeypatch: pytest.MonkeyPatch):
    """Task completed: recruit + deploy a Chat orc with deploy_command replaced by
    echo done-marker, Chat -> Loot on_task_completed set via scroll.subscribe ->
    after exit a file in loot/pipes/ contains done-marker."""
    monkeypatch.setattr("orkcraft.sources.sessions.deploy_command", lambda harness, prompt: ["sh", "-c", "echo done-marker"])
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    scroll.subscribe(app.scroll, "loot", "town_hall", "on_task_completed")

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

        roster = app.screen.query_one("#clan-roster", ClanRoster)
        roster_list = roster.query_one("#roster-list", OptionList)
        roster_list.focus()
        await pilot.press("2")
        await pilot.pause()
        assert app.focus_state.mode == "unit"

        await pilot.press("C")

        pipe_dir = fake_repo / "loot" / "pipes"
        for _ in range(40):
            await pilot.pause(0.1)
            if pipe_dir.exists() and list(pipe_dir.glob("*.md")):
                break

        assert pipe_dir.exists()
        pipe_files = list(pipe_dir.glob("*.md"))
        assert len(pipe_files) >= 1
        content = pipe_files[0].read_text(encoding="utf-8")
        assert "done-marker" in content
