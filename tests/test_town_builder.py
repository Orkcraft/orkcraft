"""📜 The Town Builder: an order in words → a checked plan → approved → raised."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from orkcraft.core import runners
from orkcraft.app import OrkcraftApp
from orkcraft.realm import town_builder, town_presets
from orkcraft.screens import onboarding
from orkcraft.screens.town_plan import TownPlanReview

SIZE = (160, 50)

GOOD = {
    "title": "Podcast Town", "summary": "Episodes from notes to release.",
    "buildings": [
        {"key": "inbox", "type": "pit", "title": "Episode Drops", "icon": "🎙", "why": "drop raw notes and links"},
        {"key": "board", "type": "fields", "title": "Episode Board", "icon": "📋", "why": "reads what was pasted"},
        {"key": "notes", "type": "scrolls", "title": "Show Notes", "icon": "📜", "why": "what was said"},
    ],
    "roads": [{"from": "inbox", "event": "pit.text", "to": "board", "why": "a pasted script shows up to read"}],
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
    assert plan.specs[0]["title"] == "Episode Drops" and plan.whys["board"] == "reads what was pasted"
    assert [(r.source, r.event, r.target) for r in plan.roads] == [("inbox", "pit.text", "board")]


def test_a_road_to_lake_opens_in_the_lake_window_and_lake_is_no_building(tmp_path: Path):
    answer = {**GOOD, "roads": [*GOOD["roads"], {"from": "inbox", "event": "pit.link", "to": "lake", "why": "read it"},
                                {"from": "inbox", "event": "mail.received", "to": "lake", "why": "not its event"}]}
    plan, problems = town_builder.check(answer, tmp_path, set())
    assert plan.opens == [("inbox", "pit.link")] and len(plan.roads) == 1
    assert problems == ["roads/2: inbox (pit) does not send 'mail.received'; it sends drop.file, on_selection_change, "
                        "pit.link, pit.text"]
    lake_town = {**GOOD, "buildings": [*GOOD["buildings"], {"key": "view", "type": "lake", "title": "View", "icon": "🌊", "why": "x"}]}
    assert any("type 'lake' is not in the catalog" in p for p in town_builder.check(lake_town, tmp_path, set())[1])


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
    (lambda a: a["roads"].append({"from": "board", "event": "tasks.created", "to": "inbox"}), "does nothing with a cart"),
    (lambda a: a["roads"][0].update(route="urgent"), "only a road from a signpost"),
])
def test_bad_plans_are_refused(tmp_path: Path, change, expect):
    answer = json.loads(json.dumps(GOOD))
    change(answer)
    _, problems = town_builder.check(answer, tmp_path, set())
    assert any(expect in p for p in problems), problems


ROUTED = {
    "title": "Triage", "summary": "Mail sorted to a crew or a log.",
    "buildings": [
        {"key": "tower", "type": "watchtower", "title": "Mail", "icon": "📬", "why": "mail comes in"},
        {"key": "gate", "type": "signpost", "title": "Sorter", "icon": "🚏", "why": "urgent or not",
         "config": {"rules": ["urgent: contains urgent", "rest: else"]}},
        {"key": "crew", "type": "barracks", "title": "Crew", "icon": "🏕", "why": "acts on urgent mail"},
        {"key": "log", "type": "loot", "title": "Log", "icon": "📦", "why": "keeps the rest"},
        {"key": "chime", "type": "horn", "title": "Chime", "icon": "📯", "why": "rings on urgent mail",
         "config": {"sounds": ["gate/signpost.routed: alarm", "*: none"]}},
        {"key": "out", "type": "catapult", "title": "Report", "icon": "🎯", "why": "sends the crew's result",
         "config": {"wait_for": ["crew"]}},
    ],
    "roads": [
        {"from": "tower", "event": "mail.received", "to": "gate"},
        {"from": "gate", "event": "signpost.routed", "route": "urgent", "to": "crew"},
        {"from": "gate", "event": "signpost.routed", "route": "rest", "to": "log"},
        {"from": "gate", "event": "signpost.routed", "route": "urgent", "to": "chime"},
        {"from": "crew", "event": "pool.done", "to": "out"},
    ],
}


def test_roads_from_a_signpost_wait_for_its_routes(tmp_path: Path):
    plan, problems = town_builder.check(ROUTED, tmp_path, set())
    assert problems == []
    assert {(r.target, r.subscription) for r in plan.roads if r.source == "gate"} == {
        ("crew", "signpost.routed#urgent"), ("log", "signpost.routed#rest"), ("chime", "signpost.routed#urgent")}


def test_a_plan_of_old_names_a_totem_and_its_events(tmp_path: Path):
    """A planner (or a template) of before the Signpost still writes `totem` and `totem.routed`."""
    answer = json.loads(json.dumps(ROUTED).replace('"signpost', '"totem'))
    plan, problems = town_builder.check(answer, tmp_path, set())
    assert problems == []
    assert next(s for s in plan.specs if s["id"] == "gate")["type"] == "signpost"
    assert ("crew", "signpost.routed#urgent") in {(r.target, r.subscription) for r in plan.roads}


@pytest.mark.parametrize("change, expect", [
    (lambda a: a["roads"][1].pop("route"), "waits for one of its routes (urgent, rest)"),
    (lambda a: a["roads"][1].update(route="spam"), "not 'spam'"),
    (lambda a: a["buildings"][1].pop("config"), "it has no rules"),
    (lambda a: a["buildings"][5]["config"].update(wait_for=["crew", "ghost"]), "not a key of the plan"),
    (lambda a: a["roads"].pop(), "no road leads from it"),
])
def test_routes_and_waits_are_checked(tmp_path: Path, change, expect):
    answer = json.loads(json.dumps(ROUTED))
    change(answer)
    _, problems = town_builder.check(answer, tmp_path, set())
    assert any(expect in p for p in problems), problems


def test_settings_that_name_buildings_follow_their_ids(tmp_path: Path):
    answer = json.loads(json.dumps(ROUTED))
    answer["buildings"][1]["config"]["rules"].insert(0, "mine: source tower")
    plan, problems = town_builder.check(answer, tmp_path, {"tower", "gate", "crew"})
    assert problems == []
    cfg = {s["id"]: s.get("config") for s in plan.specs}
    assert cfg["out"]["wait_for"] == ["crew_1"]
    assert cfg["chime"]["sounds"] == ["gate_1/signpost.routed: alarm", "*: none"]
    assert cfg["gate_1"]["rules"][0] == "mine: source tower_1"


def test_the_retry_spells_out_the_chosen_types(tmp_path: Path):
    bad = json.loads(json.dumps(ROUTED))
    bad["roads"][1].pop("route")
    run = _runner(bad, ROUTED)
    assert town_builder.plan("triage my mail", tmp_path, set(), run).ok
    assert "rules?" in run.calls[0] and "contains <text>" not in run.calls[0]
    assert "contains <text>" in run.calls[1] and "IMAP server" in run.calls[1]
    assert "takes from a road" in run.calls[0] and "[file]" in run.calls[0]


@pytest.mark.asyncio
async def test_a_raised_signpost_road_waits_for_its_route(fake_repo: Path, monkeypatch):
    monkeypatch.setattr(onboarding, "STEP_PAUSE_S", 0)
    plan, problems = town_builder.check(ROUTED, fake_repo, set())
    assert problems == []
    town_presets.save_order(fake_repo, "triage my mail")
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        app.raise_town_plan(plan)
        await _until(pilot, lambda: town_presets.pending_order(fake_repo) is None, n=200)   # the town stands
        road = app.scroll.building("log").roads[0]
        assert road.source == "gate" and road.filter.get("route") == ["rest"]


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
    monkeypatch.setattr(runners, "BUILD_RUNNER", _runner(GOOD))
    town_presets.save_order(fake_repo, "a town for my podcast")
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        app.build_town_from_order()
        await _until(pilot, lambda: isinstance(app.screen, TownPlanReview))
        body = str(app.screen.query_one("#tp-body Static").render())
        assert "Episode Drops" in body and "a pasted script shows up to read" in body
        app.screen.query_one("#tp-raise").press()
        await _until(pilot, lambda: app.scroll.building("notes") is not None
                     and any(r.source == "inbox" for r in app.scroll.building("board").roads)
                     and town_presets.pending_order(fake_repo) is None)
        assert all(not app.scroll.building(b).demolished for b in ("inbox", "board", "notes"))
        assert not app.order_burning


@pytest.mark.asyncio
async def test_later_keeps_the_order_burning(fake_repo: Path, monkeypatch):
    monkeypatch.setattr(runners, "BUILD_RUNNER", _runner(GOOD))
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
    monkeypatch.setattr(runners, "BUILD_RUNNER", run)
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
