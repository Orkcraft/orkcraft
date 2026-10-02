"""Textual Pilot integration tests for orkcraft interactive UI."""
from pathlib import Path
import json
import pytest

from textual.widgets import Static

from orkcraft.app import OrkcraftApp


@pytest.mark.asyncio
async def test_toggle_commit_setting(fake_repo: Path):
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.config.auto_commit is True

        # Press 'c' to toggle
        await pilot.press("c")
        await pilot.pause()
        assert app.config.auto_commit is False

        # Press 'c' again to re-enable
        await pilot.press("c")
        await pilot.pause()
        assert app.config.auto_commit is True


@pytest.mark.asyncio
async def test_limits_window(fake_repo: Path):
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=(160, 50)) as pilot:
        await pilot.pause()
        body = app.screen.query_one("#limits-body", Static)
        app.desktop.focus_window(app.desktop.get_window("systems"))
        await pilot.pause()
        assert app.desktop.active is app.desktop.get_window("systems")
        assert "disabled (ORKCRAFT_LIMITS=0)" in str(body.render())
        await pilot.press("u")
        await pilot.pause()
        assert "updated" in str(body.render())


@pytest.mark.asyncio
async def test_systems_window_shows_stage_scheme(fake_repo: Path):
    pipes = fake_repo / "studio" / "pipelines"
    pipes.mkdir(parents=True)
    (pipes / "one.json").write_text(json.dumps({
        "name": "one", "steps": [{"id": "a", "agent": "writer", "outputs": ["x"]}],
    }), encoding="utf-8")
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=(160, 50)) as pilot:
        await pilot.pause()
        app.desktop.focus_window(app.desktop.get_window("systems"))
        await pilot.press("down")
        await pilot.pause()
        scheme = str(app.screen.query_one("#systems-scheme", Static).render())
        assert "wave 1" in scheme and "writer" in scheme
