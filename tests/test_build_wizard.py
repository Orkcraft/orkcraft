"""The build wizard (T1105 stage 3): type → description → Foreman's prefilled spec → review → raise."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from textual.widgets import Input, OptionList, Select, SelectionList

import orkcraft.app as app_module
from orkcraft.app import OrkcraftApp
from orkcraft.realm import builders, catalog, masonry, pipes
from orkcraft.screens.build_flow import BuildFailed, BuildPreview
from orkcraft.screens.build_wizard import BuildReview, BuildWizard

SIZE = (160, 50)

TASKS = {"type": "fields", "id": "release_todo", "title": "Release tasks", "icon": "📋", "summary": "release checklist",
         "orc": {"name": "Smith", "role": "keeps the release list"}, "size": "M",
         "events": ["tasks.status_changed", "tasks.created"], "quick_actions": ["tasks.new"],
         "config": {"path": "docs/release.md"}}


def runner_of(*answers):
    queue = list(answers)
    prompts: list[str] = []

    def run(prompt: str):
        prompts.append(prompt)
        a = queue.pop(0) if len(queue) > 1 else queue[0]
        return (a if isinstance(a, str) else json.dumps(a)), 0.01
    run.prompts = prompts
    return run


# -- the Foreman --------------------------------------------------------------------------------------

def test_the_foreman_knows_the_roofs_and_a_wrong_one_is_refused(fake_repo: Path):
    run = runner_of(dict(TASKS, roof="tower"), dict(TASKS, roof="pagoda"))
    result = builders.propose("a release checklist", fake_repo, "tasks", runner=run)
    assert "gable, thatch, tiles" in run.prompts[0]
    assert result.spec["roof"] == "pagoda" and "roof: no 'tower'" in run.prompts[1]


def test_propose_prefills_a_checked_spec(fake_repo: Path):
    run = runner_of(TASKS)
    r = builders.propose("a release checklist", fake_repo, "tasks", runner=run)
    assert r.ok and r.spec["type"] == "fields" and len(r.attempts) == 1 and r.cost_usd == 0.01
    assert "Its type is fixed: fields." in run.prompts[0] and "tasks.status_changed" in run.prompts[0]
    assert "mail.received" not in run.prompts[0]                      # only the chosen type's catalog


def test_propose_retries_with_feedback_and_the_pick_wins(fake_repo: Path):
    bad = {**TASKS, "events": ["mail.received"], "type": "watchtower"}      # wrong type and a foreign event
    run = runner_of(bad, TASKS)
    r = builders.propose("a release checklist", fake_repo, "tasks", runner=run)
    assert r.ok and len(r.attempts) == 2
    assert "REJECTED" in run.prompts[1] and "does not send 'mail.received'" in run.prompts[1]


def test_auto_type_and_custom_goes_to_mason(fake_repo: Path):
    run = runner_of(TASKS)
    r = builders.propose("a release checklist", fake_repo, None, runner=run)
    assert r.ok and "Pick the type" in run.prompts[0] and "mail.received" in run.prompts[0]
    mason = {"id": "ci", "title": "CI", "icon": "🛠", "summary": "x", "orc": {"name": "Tinker"},
             "data": [{"name": "c", "source": "git_log"}]}
    artisan = {**mason, "layout": {"direction": "vertical", "panes": [{"widget": "list", "data": "c"}]}}
    run2 = runner_of({"type": "custom"}, mason, artisan)
    r2 = builders.propose("recent commits", fake_repo, None, runner=run2)
    assert r2.ok and "layout" in r2.spec and run2.prompts[1].startswith("You are Mason")


def test_propose_reports_cli_failure(fake_repo: Path):
    def boom(prompt):
        raise RuntimeError("Claude Code CLI not found")
    r = builders.propose("x", fake_repo, "tasks", runner=boom)
    assert not r.ok and "not found" in r.error


# -- the screens --------------------------------------------------------------------------------------

async def _settle(pilot, n: int = 4) -> None:
    for _ in range(n):
        await pilot.pause()


async def _until(pilot, cond, tries: int = 80) -> bool:
    for _ in range(tries):
        await pilot.pause(0.05)
        if cond():
            return True
    return False


async def _open_wizard(app, pilot) -> None:
    await pilot.press("B")
    await _settle(pilot)
    await pilot.press("down", "down", "enter")                                  # the Foreman (from scratch is second)
    await _settle(pilot)
    assert isinstance(app.screen, BuildWizard)


@pytest.mark.asyncio
async def test_wizard_review_and_raise(fake_repo: Path, monkeypatch):
    monkeypatch.setattr(app_module, "BUILD_RUNNER", runner_of(TASKS))
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=SIZE) as pilot:
        await _settle(pilot)
        await _open_wizard(app, pilot)
        types = app.screen.query_one("#wizard-types", OptionList)
        ids = [types.get_option_at_index(i).id for i in range(types.option_count)]
        assert ids[0] == "auto" and {"watchtower", "fields", "barracks", "custom"} <= set(ids)
        types.highlighted = ids.index("fields")
        await pilot.press("enter")                                      # to the description
        await _settle(pilot)
        app.screen.query_one("#wizard-prompt", Input).value = "a release checklist"
        await pilot.press("enter")
        assert await _until(pilot, lambda: isinstance(app.screen, BuildReview))
        review = app.screen
        assert review.query_one("#review-title", Input).value == "Release tasks"
        assert review.query_one("#cfg-path", Input).value == "docs/release.md"
        # change: only the status event, a new title; a camp building has its own silhouette, so no
        # size or roof to pick (T1108 visuals) — the preview is that silhouette with the new name above
        assert not review.query("#review-size") and not review.query("#review-roof")
        review.query_one("#review-events", SelectionList).deselect("tasks.created")
        review.query_one("#review-title", Input).value = "Release"
        await _settle(pilot)
        hut = review.query_one("#review-preview").children[0]
        assert hut.sil.id == "fields" and hut.label.lines[-1] == "RELEASE" and "📋" in hut.label.head
        btn = review.query_one("#review-build")
        assert btn.region.height and btn.region.bottom <= SIZE[1]           # the button is on screen
        await pilot.click("#review-build")
        await _settle(pilot)
        assert not isinstance(app.screen, BuildReview)
        w = app.desktop.get_window("release_todo")
        assert w is not None and app.focus_state.building_id == "release_todo"
    saved = json.loads(masonry.spec_file(fake_repo, "release_todo").read_text())
    assert saved["title"] == "Release" and saved["events"] == ["tasks.status_changed"]
    assert "roof" not in saved                                          # the camp building's own silhouette has none
    assert pipes.TYPED["release_todo"] == ("tasks.status_changed",)


@pytest.mark.asyncio
async def test_review_keeps_problems_on_screen(fake_repo: Path, monkeypatch):
    mail = {"type": "mail", "id": "inbox", "title": "Inbox", "icon": "📨", "orc": {"name": "Raven"},
            "config": {"host": "imap.example.com", "user_env": "U", "password_env": "P"}}
    monkeypatch.setattr(app_module, "BUILD_RUNNER", runner_of(mail))
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=SIZE) as pilot:
        await _settle(pilot)
        await _open_wizard(app, pilot)
        app.screen.query_one("#wizard-prompt", Input).value = "watch my inbox"
        app.screen.query_one("#wizard-prompt", Input).focus()
        await pilot.press("enter")                                      # auto type
        assert await _until(pilot, lambda: isinstance(app.screen, BuildReview))
        review = app.screen
        review.query_one("#cfg-port", Input).value = "many"              # not an int
        btn = review.query_one("#review-build")
        assert btn.region.height and btn.region.bottom <= SIZE[1]           # visible even with many settings
        await pilot.click("#review-build")
        await _settle(pilot)
        assert isinstance(app.screen, BuildReview)
        errors = str(review.query_one("#review-errors").render())
        assert "port: not a int" in errors
        review.query_one("#cfg-port", Input).value = ""
        review.query_one("#cfg-webhook_port", Input).value = "80"        # below the allowed range
        await pilot.press("ctrl+s")
        await _settle(pilot)
        assert "webhook_port must be between 1024 and 65535" in str(review.query_one("#review-errors").render())
        # quick actions: never more than two
        qa = review.query_one("#review-actions", SelectionList)
        qa.select_all()
        await _settle(pilot)
        assert len(qa.selected) <= catalog.MAX_QUICK_ACTIONS


@pytest.mark.asyncio
async def test_wizard_failure_and_custom_paths(fake_repo: Path, monkeypatch):
    monkeypatch.setattr(app_module, "BUILD_RUNNER", runner_of("no json here"))
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=SIZE) as pilot:
        await _settle(pilot)
        await _open_wizard(app, pilot)
        app.screen.query_one("#wizard-prompt", Input).value = "something"
        app.screen.query_one("#wizard-prompt", Input).focus()
        await pilot.press("enter")
        assert await _until(pilot, lambda: isinstance(app.screen, BuildFailed))
