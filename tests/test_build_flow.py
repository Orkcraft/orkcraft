"""Tests for custom building build flow (Mason & Artisan) and UI integration."""
from __future__ import annotations

import json
from pathlib import Path
import time

import pytest
from textual.widgets import DataTable, Input, Static, TextArea

from orkcraft.core import runners
from orkcraft.app import OrkcraftApp
from orkcraft.realm import builders, chronicles, masonry
from orkcraft.screens.build_flow import BuildFailed, BuildPreview, BuildProgress
from orkcraft.screens.custom_view import CustomBuildingView
from orkcraft.screens.build_wizard import BuildWizard

SIZE = (140, 40)

GOOD = {
    "id": "ci_watch",
    "title": "CI Watch",
    "icon": "🛠",
    "summary": "failing builds",
    "orc": {"name": "Tinker", "role": "watches the build log"},
    "data": [
        {"name": "commits", "source": "git_log", "params": {"limit": 20}},
        {"name": "log", "source": "file_tail", "params": {"path": "logs/build.log", "lines": 10}},
    ],
    "layout": {
        "direction": "horizontal",
        "panes": [
            {"widget": "table", "data": "commits", "title": "Commits", "ratio": 2, "columns": ["title", "meta", "when"]},
            {"widget": "log", "data": "log"},
        ],
    },
    "actions": [{"key": "E", "label": "Refresh", "action": "building:refresh"}],
}


def _mason_answer(spec: dict) -> str:
    return json.dumps({k: v for k, v in spec.items() if k not in ("layout", "actions")})


@pytest.mark.asyncio
async def test_saved_spec_is_window_at_start(fake_repo: Path):
    """1. A spec saved with masonry.save_spec before start is a window at start."""
    (fake_repo / "logs").mkdir(exist_ok=True)
    (fake_repo / "logs" / "build.log").write_text("\n".join(f"line {i}" for i in range(1, 101)), encoding="utf-8")
    errs = masonry.save_spec(fake_repo, GOOD)
    assert errs == []

    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()

        # In the scroll
        b_spec = app.scroll.building("ci_watch")
        assert b_spec is not None
        assert "ci_watch" in app.scroll.active_orkspace.buildings

        # Window exists on desktop
        w = app.desktop.get_window("ci_watch")
        assert w is not None
        assert not w.hidden
        assert b_spec.preset_ref == "custom:ci_watch" and not b_spec.demolished   # not a "legacy" preset

        # In the taskbar
        taskbar_item = app.screen.query_one("#taskbar-ci_watch")
        assert taskbar_item is not None

        # Table pane lists commits from fake_repo
        custom_view = w.query_one(CustomBuildingView)
        dt = custom_view.query_one(DataTable)
        assert dt.row_count >= 1

        # Log pane shows the tail of the log
        ta = custom_view.query_one(TextArea)
        assert "line 100" in ta.text
        assert "line 91" in ta.text


@pytest.mark.asyncio
async def test_build_flow_success_raises_window(fake_repo: Path, monkeypatch):
    """2. B -> prompt -> fake runner -> BuildPreview -> Enter -> window exists and is focused."""
    (fake_repo / "logs").mkdir(exist_ok=True)
    (fake_repo / "logs" / "build.log").write_text("build ok\n", encoding="utf-8")

    def fake_runner(prompt: str) -> tuple[str, float | None]:
        if prompt.startswith("You are Mason"):
            return (_mason_answer(GOOD), 0.02)
        return (json.dumps(GOOD), 0.03)

    monkeypatch.setattr(runners, "BUILD_RUNNER", fake_runner)

    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()

        # Open the build wizard
        await pilot.press("B")                      # Build: from presets / new (T1103)
        await pilot.pause()
        await pilot.press("down", "down", "enter")          # → the Foreman (from scratch is second)
        await pilot.pause()
        assert isinstance(app.screen, BuildWizard)              # the wizard (T1105): panes = the custom type
        types = app.screen.query_one("#wizard-types")
        types.highlighted = [types.get_option_at_index(i).id for i in range(types.option_count)].index("custom")
        app.screen.query_one("#wizard-prompt", Input).value = "watch CI failures"
        app.screen.query_one("#wizard-prompt", Input).focus()
        await pilot.press("enter")

        # Wait for worker to finish and BuildPreview to appear
        while not isinstance(app.screen, BuildPreview):
            await pilot.pause(0.05)

        assert isinstance(app.screen, BuildPreview)
        assert app.screen.spec["id"] == "ci_watch"

        # Press Enter to confirm raising
        await pilot.press("enter")
        await pilot.pause(0.1)

        # Window exists, is focused and active
        w = app.desktop.get_window("ci_watch")
        assert w is not None
        assert not w.hidden
        assert app.desktop.active is w

        # Spec file exists
        spec_path = masonry.spec_file(fake_repo, "ci_watch")
        assert spec_path.is_file()

        # Scroll has the building
        assert app.scroll.building("ci_watch") is not None

        # Chronicle has building_raised
        events = chronicles.history(fake_repo, "ci_watch")
        assert any(e["type"] == "building_raised" for e in events)

        # Build request logged in .orkcraft/build-requests.jsonl
        log_file = fake_repo / ".orkcraft" / "build-requests.jsonl"
        assert log_file.is_file()
        logs = [json.loads(line) for line in log_file.read_text(encoding="utf-8").splitlines() if line.strip()]
        assert any(entry.get("ok") is True and entry.get("id") == "ci_watch" for entry in logs)


@pytest.mark.asyncio
async def test_build_flow_failure_shows_errors(fake_repo: Path, monkeypatch):
    """3. A runner that keeps answering an invalid spec -> BuildFailed lists the error; nothing saved."""
    bad_spec = json.loads(json.dumps(GOOD))
    bad_spec["data"][1]["params"]["path"] = "../../outside.txt"

    def bad_runner(prompt: str) -> tuple[str, float | None]:
        if prompt.startswith("You are Mason"):
            return (_mason_answer(bad_spec), 0.01)
        return (json.dumps(bad_spec), 0.01)

    monkeypatch.setattr(runners, "BUILD_RUNNER", bad_runner)

    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()

        await pilot.press("B")                      # Build: from presets / new (T1103)
        await pilot.pause()
        await pilot.press("down", "down", "enter")          # → the Foreman (from scratch is second)
        await pilot.pause()
        assert isinstance(app.screen, BuildWizard)              # the wizard (T1105): panes = the custom type
        types = app.screen.query_one("#wizard-types")
        types.highlighted = [types.get_option_at_index(i).id for i in range(types.option_count)].index("custom")
        app.screen.query_one("#wizard-prompt", Input).value = "broken build"
        app.screen.query_one("#wizard-prompt", Input).focus()
        await pilot.press("enter")

        # Wait for worker to finish and BuildFailed to appear
        while not isinstance(app.screen, BuildFailed):
            await pilot.pause(0.05)

        assert isinstance(app.screen, BuildFailed)
        # Error text mentions outside the repository
        failed_errors = app.screen.query_one(".build-text", Static)
        assert "outside the repository" in str(failed_errors.render())

        # Nothing is saved
        assert not masonry.spec_file(fake_repo, "ci_watch").exists()
        assert app.scroll.building("ci_watch") is None

        # Build request logged with failure
        log_file = fake_repo / ".orkcraft" / "build-requests.jsonl"
        assert log_file.is_file()
        logs = [json.loads(line) for line in log_file.read_text(encoding="utf-8").splitlines() if line.strip()]
        assert any(entry.get("ok") is False for entry in logs)

        # Close
        await pilot.press("escape")
        await pilot.pause()
        assert not isinstance(app.screen, BuildFailed)


@pytest.mark.asyncio
async def test_custom_action_building_refresh_and_inactive_elsewhere(fake_repo: Path):
    """4. Custom action: Building state on custom building triggers refresh; inactive elsewhere."""
    (fake_repo / "logs").mkdir(exist_ok=True)
    (fake_repo / "logs" / "build.log").write_text("log\n", encoding="utf-8")
    spec = dict(GOOD, actions=[{"key": "E", "label": "Refresh", "action": "building:refresh"}])
    masonry.save_spec(fake_repo, spec)

    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()

        # Focus ci_watch window
        w = app.desktop.get_window("ci_watch")
        app.desktop.focus_window(w)
        app.set_focus_state("building", building_id="ci_watch")
        await pilot.pause()

        # Press E to trigger custom building action
        await pilot.press("E")
        await pilot.pause()

        # Focus another building (e.g. chat)
        chat_w = app.desktop.get_window("town_hall")
        app.desktop.focus_window(chat_w)
        app.set_focus_state("building", building_id="town_hall")
        await pilot.pause()

        # Press E in chat: action is inactive
        await pilot.press("E")
        await pilot.pause()


@pytest.mark.asyncio
async def test_ui_stays_responsive_while_building(fake_repo: Path, monkeypatch):
    """5. The UI stays responsive while building: app processes key press before build finishes."""
    (fake_repo / "logs").mkdir(exist_ok=True)
    (fake_repo / "logs" / "build.log").write_text("ok\n", encoding="utf-8")

    def slow_runner(prompt: str) -> tuple[str, float | None]:
        time.sleep(0.5)
        if prompt.startswith("You are Mason"):
            return (_mason_answer(GOOD), 0.01)
        return (json.dumps(GOOD), 0.01)

    monkeypatch.setattr(runners, "BUILD_RUNNER", slow_runner)

    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()

        await pilot.press("B")                      # Build: from presets / new (T1103)
        await pilot.pause()
        await pilot.press("down", "down", "enter")          # → the Foreman (from scratch is second)
        await pilot.pause()
        assert isinstance(app.screen, BuildWizard)              # the wizard (T1105): panes = the custom type
        types = app.screen.query_one("#wizard-types")
        types.highlighted = [types.get_option_at_index(i).id for i in range(types.option_count)].index("custom")
        app.screen.query_one("#wizard-prompt", Input).value = "slow build"
        app.screen.query_one("#wizard-prompt", Input).focus()
        await pilot.press("enter")
        await pilot.pause(0.05)

        # BuildProgress is showing
        assert isinstance(app.screen, BuildProgress)

        # UI is responsive: pressing Esc hides BuildProgress while build continues in background
        await pilot.press("escape")
        await pilot.pause(0.05)
        assert not isinstance(app.screen, BuildProgress)

        # Wait for the background worker to finish and push BuildPreview
        while not isinstance(app.screen, BuildPreview):
            await pilot.pause(0.05)

        assert isinstance(app.screen, BuildPreview)
        await pilot.press("escape")
        await pilot.pause()


@pytest.mark.asyncio
async def test_id_remembered_by_the_scroll_is_taken(fake_repo: Path):
    """Review of stage 11: a stale scroll entry (its spec file deleted) must not crash a new build."""
    from orkcraft import scroll as ts

    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        ts.add_custom_building(app.scroll, {"id": "ci_watch", "title": "Old", "icon": "x", "orc": {"name": "Old"}})
        assert "ci_watch" in app._taken_building_ids()
        assert masonry.validate_spec(GOOD, fake_repo, app._taken_building_ids())   # refused, not crashed
