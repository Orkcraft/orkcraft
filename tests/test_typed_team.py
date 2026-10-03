"""⚔ Agent Team (T1105 stage 7): rounds until consensus, limits, questions, the artifact."""
from __future__ import annotations

from pathlib import Path

import pytest

from orkcraft import scroll as ts
from orkcraft.app import OrkcraftApp
from orkcraft.realm import masonry, pipes
from orkcraft.realm import team as tm
from orkcraft.screens.dialogs import TextPrompt
from orkcraft.screens.typed.team_view import TeamView

SIZE = (200, 46)
TEAM = [tm.Member("Architect"), tm.Member("Critic", "agy", "gemini-3.1-pro-high"), tm.Member("Security")]


class Script:
    """A fake model: answers by who is asked, in order; records every call."""

    def __init__(self, replies: dict[str, list[str]]):
        self.replies, self.calls = {k: list(v) for k, v in replies.items()}, []

    def __call__(self, harness, prompt, model):
        who = "Moderator" if prompt.startswith("You moderate") else prompt.split("You are ", 1)[1].split(" ", 1)[0]
        self.calls.append((who, harness, model))
        return self.replies[who].pop(0), 0.05


def test_members_and_a_first_round_consensus():
    assert [m.role for m in tm.members_of({})] == ["Author", "Critic"]
    assert tm.parse_member("Critic:agy:gemini-3.1-pro-high") == tm.Member("Critic", "agy", "gemini-3.1-pro-high")
    assert tm.parse_member("Bad:gpt") is None and tm.members_of({"members": ["Solo:claude"]})[0].role == "Author"
    s = Script({"Architect": ["# Plan v1"], "Critic": ["AGREE"], "Security": ["**AGREE** — fine"]})
    d = tm.run(tm.new("Plan the API"), TEAM, "claude", 3, 1.0, s)
    assert d.outcome == "agreed" and d.draft == "# Plan v1" and d.round == 1
    assert s.calls == [("Architect", "claude", ""), ("Critic", "agy", "gemini-3.1-pro-high"), ("Security", "claude", "")]
    assert round(d.spent, 2) == 0.15 and "agreed" in tm.artifact_markdown(d, TEAM)


def test_objections_revise_and_the_last_round_decides():
    s = Script({"Architect": ["v1"], "Critic": ["OBJECT: 1. add auth", "AGREE", "OBJECT: still no"],
                "Security": ["AGREE", "OBJECT: rate limits"],
                "Moderator": ["v2 with auth", "v3 final\n## Open points\n- rate limits"]})
    d = tm.run(tm.new("Plan the API"), TEAM, "claude", 2, 0, s)
    assert d.outcome == "no_consensus" and d.round == 2 and d.draft.startswith("v3 final")
    revise = [c for c in s.calls if c[0] == "Moderator"]
    assert len(revise) == 2
    assert [t.kind for t in d.turns] == ["draft", "review", "review", "revise", "review", "review", "decide"]


def test_budget_and_a_question_pause_it():
    s = Script({"Architect": ["v1"], "Critic": ["OBJECT: more"], "Security": ["AGREE"], "Moderator": ["v2"]})
    d = tm.run(tm.new("x"), TEAM, "claude", 5, 0.1, s)
    assert d.outcome == "budget" and len(s.calls) == 2
    s = Script({"Architect": ["v1"], "Critic": ["QUESTION: REST or gRPC?", "AGREE"], "Security": ["AGREE"]})
    d = tm.run(tm.new("x"), TEAM, "claude", 3, 0, s)
    assert d.outcome == "asked" and d.asking == "Critic" and d.question == "REST or gRPC?"
    tm.answer(d, "REST")
    d = tm.run(d, TEAM, "claude", 3, 0, s)
    assert d.outcome == "agreed" and [c[0] for c in s.calls] == ["Architect", "Critic", "Critic", "Security"]
    assert any("REST" in t.text for t in d.turns if t.kind == "answer")


def test_the_operator_outranks_the_topic_and_the_moderator_hears_the_answers():
    d = tm.new("Plan v2.0", "Agree on the release plan")
    tm.answer(d, "ship on Friday")
    review = tm.review_prompt(d, TEAM[1], TEAM)
    assert "Goal (the standing brief): Agree" in review and "Topic (this request): Plan v2.0" in review
    assert tm.PRECEDENCE in review and "- ship on Friday" in review
    revise = tm.revise_prompt(d, ["**Critic:** later"], final=True)
    assert "- ship on Friday" in revise and tm.PRECEDENCE in revise and "Plan v2.0" in revise
    assert tm.PRECEDENCE not in tm.draft_prompt(tm.new("x"), TEAM[0], TEAM)     # nothing to weigh


@pytest.mark.asyncio
async def test_carts_that_arrive_mid_debate_wait_in_line(fake_repo: Path, monkeypatch):
    spec = {"id": "council3", "title": "Council", "icon": "⚔", "orc": {"name": "Warchief"}, "type": "team",
            "config": {"members": ["Planner:claude", "Critic:claude"], "max_rounds": 2, "budget_usd": 1}}
    assert masonry.save_spec(fake_repo, spec) == []
    s = Script({"Planner": ["# A", "# B", "# C"], "Critic": ["QUESTION: when?", "AGREE", "AGREE", "AGREE"]})
    monkeypatch.setattr(TeamView, "runner", staticmethod(s))
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        view = app.desktop.get_window("council3").query_one(TeamView)
        monkeypatch.setattr(app.roads, "emit", lambda payload, meta=None: [])
        view.start("A")
        for _ in range(60):
            await pilot.pause(0.02)
            if view.current and view.current.outcome == "asked" and not view._busy:
                break
        view.receive(None, "x", "B")        # the debate waits on the operator: B and C queue, none is lost
        view.receive(None, "x", "C")
        assert view.waiting == ["B", "C"] and view.mini_status()[-1] == "2 queued"
        view.reply("tomorrow")
        for _ in range(150):
            await pilot.pause(0.02)
            if len(view.history) == 3 and not view._busy:
                break
        assert sorted(d.topic for d in view.history) == ["A", "B", "C"] and view.waiting == []
        assert all(d.outcome == "agreed" for d in view.history)


@pytest.mark.asyncio
async def test_the_team_building_discusses_and_hands_over_the_artifact(fake_repo: Path, monkeypatch):
    spec = {"id": "council2", "title": "Council", "icon": "⚔", "orc": {"name": "Warchief"}, "type": "team",
            "config": {"goal": "Agree on the release plan", "members": ["Planner:claude", "Critic:claude"],
                       "max_rounds": 3, "budget_usd": 1}}
    assert masonry.save_spec(fake_repo, spec) == []
    s = Script({"Planner": ["# Release plan\n1. tag\n2. ship"], "Critic": ["QUESTION: which date?", "AGREE"]})
    monkeypatch.setattr(TeamView, "runner", staticmethod(s))
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    ts.subscribe(app.scroll, "town_hall", "council2", "team.artifact_ready")
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        view = app.desktop.get_window("council2").query_one(TeamView)
        assert view.mini_status() == ["Planner claude", "Critic claude"]
        sent = []
        monkeypatch.setattr(app.roads, "emit", lambda payload, meta=None: sent.append(payload) or [])
        app.deliver_payload("council2", pipes.Payload(pipes.TEXT, "Plan v2.0", "loot", "on_selection_change"), "x", "Plan v2.0")
        for _ in range(60):
            await pilot.pause(0.02)
            if view.current and view.current.outcome == "asked":
                break
        assert view.mini_status()[0] == "🔥 Critic asks"
        assert view.quick_action("team.start")
        await pilot.pause()
        assert isinstance(app.screen, TextPrompt)
        await pilot.press(*"Friday", "enter")
        for _ in range(60):
            await pilot.pause(0.02)
            if view.current.outcome == "agreed" and not view._busy:
                break
        assert view.current.outcome == "agreed"
        [p] = sent
        assert p.kind == "file" and p.mode == "team.artifact_ready" and p.value.startswith("loot/pipes/")
        text = (fake_repo / p.value).read_text()
        assert "# Release plan" in text and "agreed" in text
        assert view.history and view.history[0].id == view.current.id      # kept in .orkcraft/team/
        assert view.query_one("#team-turns").option_count == 1 + len(view.current.turns)
