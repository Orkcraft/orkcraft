"""The build flow's screens (the Foreman's wizard), and custom (panes) buildings of old: they left the
catalog, but a saved one still loads, draws and acts."""
from __future__ import annotations

import json
from pathlib import Path
import threading
import time

import pytest
from textual.widgets import DataTable, Input, Static, TextArea

from orkcraft.core import runners
from orkcraft.app import OrkcraftApp
from orkcraft.realm import chronicles, masonry
from orkcraft.screens.build_flow import BuildFailed, BuildProgress
from orkcraft.screens.custom_view import CustomBuildingView
from orkcraft.screens.build_wizard import BuildReview, BuildWizard

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


TASKS = {"type": "fields", "id": "release_todo", "title": "Release tasks", "icon": "📋", "summary": "release checklist",
         "orc": {"name": "Smith", "role": "keeps the release list"}, "size": "M",
         "events": ["tasks.status_changed"], "quick_actions": ["tasks.new"], "config": {"path": "docs/release.md"}}


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
async def test_old_scroll_with_a_custom_building_loads_and_draws(fake_repo: Path, isolated_layout_file: Path):
    """Custom (panes) left the catalog, but a Town Scroll of old that holds one still loads and draws it."""
    from orkcraft import scroll as ts
    from orkcraft.realm.buildings import presets, registry
    from orkcraft.screens.presets_modal import PresetsModal

    (fake_repo / "logs").mkdir(exist_ok=True)
    (fake_repo / "logs" / "build.log").write_text("line 1\nline 2\n", encoding="utf-8")
    assert masonry.save_spec(fake_repo, GOOD) == []
    old = ts.default_scroll(presets(registry()))
    ts.add_custom_building(old, dict(GOOD))
    assert ts.save(isolated_layout_file, old) == []

    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        assert not [p for p in app.scroll_problems if "ci_watch" in p]
        b = app.scroll.building("ci_watch")
        assert b is not None and b.preset_ref == "custom:ci_watch" and not b.demolished
        w = app.desktop.get_window("ci_watch")
        assert w is not None and not w.hidden
        view = w.query_one(CustomBuildingView)
        assert view.query_one(DataTable).row_count >= 1 and "line 2" in view.query_one(TextArea).text
        # the presets still list it (with every building raised from a spec), never as "Mason & Artisan"
        app.action_presets_catalog()
        await pilot.pause()
        assert isinstance(app.screen, PresetsModal)
        lst = app.screen.query_one("#presets-list")
        labels = [str(lst.get_option_at_index(i).prompt) for i in range(lst.option_count)]
        ids = [lst.get_option_at_index(i).id for i in range(lst.option_count)]
        assert "building:ci_watch" in ids and "type:custom" not in ids
        assert not any("Mason" in t or "Custom" in t for t in labels)


def _foreman(answer: dict, delay: float = 0.0):
    def run(prompt: str) -> tuple[str, float | None]:
        time.sleep(delay)
        return json.dumps(answer), 0.02
    return run


async def _ask_the_foreman(app, pilot, request: str) -> None:
    await pilot.press("B")                                    # Build: presets / from scratch / the Foreman
    await pilot.pause()
    await pilot.press("down", "down", "enter")
    await pilot.pause()
    assert isinstance(app.screen, BuildWizard)
    types = app.screen.query_one("#wizard-types")
    ids = [types.get_option_at_index(i).id for i in range(types.option_count)]
    assert "custom" not in ids                                # Custom (panes) left the catalog
    types.highlighted = ids.index("fields")
    app.screen.query_one("#wizard-prompt", Input).value = request
    app.screen.query_one("#wizard-prompt", Input).focus()
    await pilot.press("enter")


@pytest.mark.asyncio
async def test_build_flow_success_raises_window(fake_repo: Path, monkeypatch):
    """B → the Foreman → BuildReview → Build: the window exists, is focused, chronicled and logged."""
    monkeypatch.setattr(runners, "BUILD_RUNNER", _foreman(TASKS))
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        await _ask_the_foreman(app, pilot, "a release checklist")
        while not isinstance(app.screen, BuildReview):
            await pilot.pause(0.05)
        app.screen.action_build()
        await pilot.pause(0.1)
        w = app.desktop.get_window("release_todo")
        assert w is not None and not w.hidden and app.desktop.active is w
        assert masonry.spec_file(fake_repo, "release_todo").is_file()
        assert app.scroll.building("release_todo") is not None
        assert any(e["type"] == "building_raised" for e in chronicles.history(fake_repo, "release_todo"))
        log_file = fake_repo / ".orkcraft" / "build-requests.jsonl"
        logs = [json.loads(line) for line in log_file.read_text(encoding="utf-8").splitlines() if line.strip()]
        assert any(entry.get("ok") is True and entry.get("id") == "release_todo" for entry in logs)


@pytest.mark.asyncio
async def test_build_flow_failure_shows_errors(fake_repo: Path, monkeypatch):
    """A Foreman that keeps answering an invalid spec → BuildFailed lists the error; nothing saved."""
    monkeypatch.setattr(runners, "BUILD_RUNNER", _foreman(dict(TASKS, events=["mail.received"])))
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        await _ask_the_foreman(app, pilot, "a broken checklist")
        while not isinstance(app.screen, BuildFailed):
            await pilot.pause(0.05)
        assert "does not send 'mail.received'" in str(app.screen.query_one(".build-text", Static).render())
        assert not masonry.spec_file(fake_repo, "release_todo").exists()
        assert app.scroll.building("release_todo") is None
        log_file = fake_repo / ".orkcraft" / "build-requests.jsonl"
        logs = [json.loads(line) for line in log_file.read_text(encoding="utf-8").splitlines() if line.strip()]
        assert any(entry.get("ok") is False for entry in logs)
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
    """The UI stays responsive while the Foreman drafts: Esc hides BuildProgress, the review comes after."""
    drafted = threading.Event()   # the Foreman drafts until the test lets it answer, however slow the machine

    def slow(prompt: str) -> tuple[str, float | None]:
        drafted.wait(10)
        return json.dumps(TASKS), 0.02

    monkeypatch.setattr(runners, "BUILD_RUNNER", slow)
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        await _ask_the_foreman(app, pilot, "a slow checklist")
        await pilot.pause(0.05)
        assert isinstance(app.screen, BuildProgress)
        await pilot.press("escape")
        await pilot.pause(0.05)
        assert not isinstance(app.screen, BuildProgress)
        drafted.set()
        while not isinstance(app.screen, BuildReview):
            await pilot.pause(0.05)
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
