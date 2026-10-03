"""📜 The Town Builder: an order in words → a checked plan → approved → raised."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from orkcraft import app as app_mod
from orkcraft.app import OrkcraftApp
from orkcraft.realm import town_builder, town_presets
from orkcraft.screens import onboarding
from orkcraft.screens.town_plan import TownPlanReview

SIZE = (160, 50)

GOOD = {
    "title": "Podcast Town", "summary": "Episodes from notes to release.",
    "buildings": [
        {"key": "inbox", "type": "pit", "title": "Episode Drops", "icon": "🎙", "why": "drop raw notes and links"},
        {"key": "board", "type": "fields", "title": "Episode Board", "icon": "📋", "why": "one task per episode"},
        {"key": "notes", "type": "scrolls", "title": "Show Notes", "icon": "📜", "why": "what was said"},
    ],
    "roads": [{"from": "inbox", "event": "pit.text", "to": "board", "why": "a pasted idea becomes a task"}],
}


def _runner(*answers):
    calls = []

    def run(prompt: str, model: str | None = None):
        calls.append(prompt)
        a = answers[min(len(calls) - 1, len(answers) - 1)]
        return (a if isinstance(a, str) else json.dumps(a)), 0.01

    run.calls = calls
    return run


def test_a_good_plan_passes(tmp_path: Path):
    plan, problems = town_builder.check(GOOD, tmp_path, set())
    assert problems == []
    assert [s["id"] for s in plan.specs] == ["inbox", "board", "notes"]
    assert plan.specs[0]["title"] == "Episode Drops" and plan.whys["board"] == "one task per episode"
    assert [(r.source, r.event, r.target) for r in plan.roads] == [("inbox", "pit.text", "board")]


def test_taken_ids_get_a_number(tmp_path: Path):
    plan, problems = town_builder.check(GOOD, tmp_path, {"inbox", "board"})
    assert problems == [] and [s["id"] for s in plan.specs][:2] == ["inbox_1", "board_1"]
    assert plan.roads[0].source == "inbox_1" and plan.roads[0].target == "board_1"


@pytest.mark.parametrize("change, expect", [
    (lambda a: a["buildings"].append({"key": "hall", "type": "town_hall"}), "not in the catalog"),
    (lambda a: a["buildings"].append({"key": "lab", "type": "workshop"}), "not in the catalog"),
    (lambda a: a["roads"].append({"from": "inbox", "event": "git.commit", "to": "board"}), "does not send"),
    (lambda a: a["roads"].append({"from": "inbox", "event": "pit.text", "to": "nowhere"}), "must be keys"),
    (lambda a: a["buildings"].append({"key": "inbox", "type": "pit"}), "must be unique"),
    (lambda a: a.update(buildings=a["buildings"][:1], roads=[]), "at least two"),
    (lambda a: a["buildings"][0].update(config={"rm": "-rf"}), "inbox"),
])
def test_bad_plans_are_refused(tmp_path: Path, change, expect):
    answer = json.loads(json.dumps(GOOD))
    change(answer)
    _, problems = town_builder.check(answer, tmp_path, set())
    assert any(expect in p for p in problems), problems


def test_a_refused_plan_goes_back_with_its_problems(tmp_path: Path):
    bad = json.loads(json.dumps(GOOD))
    bad["roads"][0]["event"] = "git.commit"
    run = _runner("sure, here you go", bad, GOOD)
    plan = town_builder.plan("a town for my podcast", tmp_path, set(), run)
    assert plan.ok and len(plan.attempts) == 3 and plan.cost_usd == pytest.approx(0.03)
    assert "no JSON object" in run.calls[1] and "does not send" in run.calls[2]
    assert "a town for my podcast" in run.calls[0] and "- pit (" in run.calls[0]


def test_the_operator_note_reaches_the_planner(tmp_path: Path):
    run = _runner(GOOD)
    town_builder.plan("a town", tmp_path, set(), run, feedback="no notes building please")
    assert "no notes building please" in run.calls[0]


def test_a_cli_failure_is_an_error_not_a_crash(tmp_path: Path):
    def boom(prompt, model=None):
        raise RuntimeError("Claude Code CLI not found (claude)")
    plan = town_builder.plan("a town", tmp_path, set(), boom)
    assert not plan.ok and "not found" in plan.error


def test_no_plan_after_every_attempt(tmp_path: Path):
    plan = town_builder.plan("a town", tmp_path, set(), _runner("nope"))
    assert not plan.ok and len(plan.attempts) == town_builder.MAX_ATTEMPTS and "no plan passed" in plan.error


def test_a_raised_order_is_no_longer_pending(tmp_path: Path):
    town_presets.save_order(tmp_path, "a town")
    town_presets.close_order(tmp_path, "Podcast Town")
    assert town_presets.pending_order(tmp_path) is None
    assert json.loads((tmp_path / town_presets.ORDER).read_text())["town"] == "Podcast Town"


async def _until(pilot, cond, n: int = 80) -> None:
    for _ in range(n):
        if cond():
            return
        await pilot.pause(0.05)
    assert cond()


@pytest.mark.asyncio
async def test_plan_review_and_raise(fake_repo: Path, monkeypatch):
    monkeypatch.setattr(onboarding, "STEP_PAUSE_S", 0)
    monkeypatch.setattr(app_mod, "BUILD_RUNNER", _runner(GOOD))
    town_presets.save_order(fake_repo, "a town for my podcast")
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        app.build_town_from_order()
        await _until(pilot, lambda: isinstance(app.screen, TownPlanReview))
        body = str(app.screen.query_one("#tp-body Static").render())
        assert "Episode Drops" in body and "a pasted idea becomes a task" in body
        app.screen.query_one("#tp-raise").press()
        await _until(pilot, lambda: app.scroll.building("notes") is not None
                     and any(r.source == "inbox" for r in app.scroll.building("board").roads)
                     and town_presets.pending_order(fake_repo) is None)
        assert all(not app.scroll.building(b).demolished for b in ("inbox", "board", "notes"))
        assert not app.order_burning


@pytest.mark.asyncio
async def test_later_keeps_the_order_burning(fake_repo: Path, monkeypatch):
    monkeypatch.setattr(app_mod, "BUILD_RUNNER", _runner(GOOD))
    town_presets.save_order(fake_repo, "a town for my podcast")
    town_presets.mark_order_seen(fake_repo)
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        assert not app.order_burning
        app.build_town_from_order()
        await _until(pilot, lambda: isinstance(app.screen, TownPlanReview))
        app.screen.query_one("#tp-later").press()
        await _until(pilot, lambda: app.order_burning)
        assert app.scroll.building("inbox") is None and town_presets.pending_order(fake_repo) is not None


@pytest.mark.asyncio
async def test_ask_again_sends_the_note(fake_repo: Path, monkeypatch):
    run = _runner(GOOD)
    monkeypatch.setattr(app_mod, "BUILD_RUNNER", run)
    town_presets.save_order(fake_repo, "a town for my podcast")
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        app.build_town_from_order()
        await _until(pilot, lambda: isinstance(app.screen, TownPlanReview))
        app.screen.query_one("#tp-note").value = "skip the notes"
        app.screen.query_one("#tp-again").press()
        await _until(pilot, lambda: len(run.calls) == 2 and isinstance(app.screen, TownPlanReview))
        assert "skip the notes" in run.calls[1]
