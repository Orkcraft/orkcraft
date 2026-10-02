"""Roads v2 (T1108 stage 6): a road with a rule — chain or script for a deterministic rule, then the Council."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from orkcraft import app as app_mod
from orkcraft.app import OrkcraftApp
from orkcraft.realm import fastpath, recruiter

CHAIN = {"name": "Crier", "role": "done digest", "kind": "chain", "why": "a template is enough",
         "chain": [{"op": "template", "md": "✅ {id} — {title}"}],
         "roads": [{"from": "loot", "event": "on_selection_change"}]}
AGENT = dict(CHAIN, kind="agent", chain=[], orders="format it", harness=[{"role": "run", "harness": "claude"}],
             why="judgement")


def test_a_deterministic_rule_never_gets_an_agent(fake_repo: Path):
    scroll = OrkcraftApp(repo_root=fake_repo, auto_commit=False).scroll
    prompts, answers = [], iter([json.dumps(AGENT), json.dumps(dict(CHAIN, roads=[{"from": "loot", "event": "on_task_completed"}])),
                                 json.dumps(CHAIN)])

    def runner(prompt):
        prompts.append(prompt)
        return next(answers), 0.01

    result = recruiter.recruit("only done tasks, as a checklist line", scroll, "town_hall", runner,
                               road=("loot", "on_selection_change"))
    assert result.ok and result.orc["kind"] == "chain" and len(prompts) == 3
    assert "ROADS WITH A RULE" in prompts[0] and '{"from": "loot", "event": "on_selection_change"}' in prompts[0]
    assert "deterministic" in prompts[1] and "exactly these roads: from loot on on_selection_change" in prompts[2]
    agent_ok = recruiter.recruit("summarise what changed", scroll, "town_hall", lambda p: (json.dumps(AGENT), 0.0),
                                 road=("loot", "on_selection_change"))
    assert agent_ok.ok and agent_ok.orc["kind"] == "agent"                  # judgement: an agent may do it
    assert recruiter.needs_judgement("резюмируй письмо") and not recruiter.needs_judgement("count the lines")


@pytest.mark.asyncio
async def test_a_road_with_a_rule_goes_past_the_council(fake_repo: Path, monkeypatch):
    from textual.widgets import SelectionList, TextArea

    from orkcraft.screens.orc_flow import RecruitPreview
    from orkcraft.screens.road_rule_modal import RoadRuleModal

    prompts = []
    monkeypatch.setattr(app_mod, "RECRUIT_RUNNER", lambda p: (prompts.append(p) or json.dumps(CHAIN), 0.01))
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=(200, 50)) as pilot:
        await pilot.pause()
        assert [h for _, h, _ in app._rule_choices("loot", "town_hall")] == [app_mod.RULE]
        app.road_with_rule("town_hall", "loot")
        await pilot.pause()
        modal = app.screen
        assert isinstance(modal, RoadRuleModal)
        assert list(modal.query_one("#rule-events", SelectionList).selected) == ["on_selection_change"]
        await pilot.press("ctrl+s")                                        # no prompt yet: stays
        await pilot.pause()
        assert app.screen is modal and "what to do" in str(modal.query_one("#rule-errors").render())
        modal.query_one("#rule-prompt", TextArea).text = "only done tasks, as a checklist line"
        await pilot.press("ctrl+s")
        for _ in range(60):
            await pilot.pause(0.05)
            if isinstance(app.screen, RecruitPreview):
                break
        assert isinstance(app.screen, RecruitPreview) and "ROADS WITH A RULE" in prompts[0]

        # declined: back to the dialog, the prompt emptied, the events kept, the reason shown
        await pilot.press("escape")
        await pilot.pause()
        again = app.screen
        assert isinstance(again, RoadRuleModal) and again is not modal
        assert again.query_one("#rule-prompt", TextArea).text == "" and "declined" in str(again.query_one("#rule-errors").render())
        again.query_one("#rule-prompt", TextArea).text = "only done tasks, as a checklist line"
        await pilot.press("ctrl+s")
        for _ in range(60):
            await pilot.pause(0.05)
            if isinstance(app.screen, RecruitPreview):
                break
        await pilot.press("enter")
        for _ in range(20):
            await pilot.pause(0.05)
        hall = app.scroll.building("town_hall")
        crier = hall.garrison.handler("crier")
        assert crier is not None and crier.kind == "chain"
        assert [(r.source, r.handler) for r in hall.roads] == [("loot", "crier")]
        assert fastpath.recent(fake_repo)[0]["kind"] == "agent"             # the Council saw it


def test_several_events_make_several_roads(fake_repo: Path):
    scroll = OrkcraftApp(repo_root=fake_repo, auto_commit=False).scroll
    two = dict(CHAIN, roads=[{"from": "loot", "event": "on_selection_change"}, {"from": "loot", "event": "on_task_completed"}])
    wanted = [("loot", "on_selection_change"), ("loot", "on_task_completed")]
    ok = recruiter.recruit("list them", scroll, "town_hall", lambda p: (json.dumps(two), 0.0), road=wanted)
    assert ok.ok and len(ok.roads) == 2
    short = recruiter.recruit("list them", scroll, "town_hall", lambda p: (json.dumps(CHAIN), 0.0), road=wanted,
                              max_attempts=1)
    assert not short.ok and "exactly these roads" in short.attempts[-1].errors[0]


@pytest.mark.asyncio
async def test_a_hired_script_is_reviewed_and_runs(fake_repo: Path, monkeypatch):
    from orkcraft.realm import roads
    from orkcraft.screens.orc_flow import RecruitPreview

    script = dict(CHAIN, name="Lister", kind="script", chain=[], why="needs a loop",
                  script_source="import json, sys\nprint(len(json.load(sys.stdin)))\n")
    monkeypatch.setattr(app_mod, "RECRUIT_RUNNER", lambda p: (json.dumps(script), 0.01))
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=(200, 50)) as pilot:
        await pilot.pause()
        app.recruit_from_prompt("town_hall", "count what arrives", road=("loot", "on_selection_change"))
        for _ in range(60):
            await pilot.pause(0.05)
            if isinstance(app.screen, RecruitPreview):
                break
        await pilot.press("enter")
        for _ in range(10):
            await pilot.pause(0.05)
        orc = app.scroll.building("town_hall").garrison.handler("lister")
        assert orc.script["reviewed"] is True and orc.status == "idle"
        assert roads.script_problem(orc, fake_repo) == ""


@pytest.mark.asyncio
async def test_a_click_picks_the_source_of_a_road(fake_repo: Path, monkeypatch):
    from orkcraft import scroll as ts
    from orkcraft.screens.road_modal import SubscribeModal

    monkeypatch.setattr(ts, "DEFAULT_VIEW", "town")
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=(200, 50)) as pilot:
        for _ in range(4):
            await pilot.pause()
        app.desktop.enter_rally_mode("town_hall")
        await pilot.pause()
        await pilot.click("#hut-loot")
        await pilot.pause()
        assert not app.desktop.rally_mode, [n.message for n in app._notifications]
        assert isinstance(app.screen, SubscribeModal), [n.message for n in app._notifications]
        labels = [str(app.screen.query_one("OptionList").get_option_at_index(i).prompt)
                  for i in range(app.screen.query_one("OptionList").option_count)]
        assert any("Listen with a prompt" in x for x in labels)
