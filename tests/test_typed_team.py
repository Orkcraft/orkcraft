"""🪔 Clan Fire: each role reviews, the steward decides; veto, cycles, the operator, briefs, the loop."""
from __future__ import annotations

from pathlib import Path

import pytest

from orkcraft import scroll as ts
from orkcraft.app import OrkcraftApp
from orkcraft.realm import masonry, pipes, roads
from orkcraft.realm import team as tm
from orkcraft.screens.dialogs import TextPrompt
from orkcraft.screens.typed.team_view import TeamView

SIZE = (200, 46)
TEAM = [tm.Member("PM"), tm.Member("Architect", "agy", "gemini-3.1-pro-high"), tm.Member("Security")]
STEWARD = tm.Steward("Let it go when nobody blocks it.")


class Script:
    """A fake model: answers by who is asked, in order; records every call and prompt."""

    def __init__(self, replies: dict[str, list[str]]):
        self.replies, self.calls, self.prompts = {k: list(v) for k, v in replies.items()}, [], []

    def __call__(self, harness, prompt, model):
        who = "Steward" if prompt.startswith("You are the steward") else prompt.split("You are ", 1)[1].split(" in a", 1)[0]
        self.calls.append((who, harness, model))
        self.prompts.append((who, prompt))
        return self.replies[who].pop(0), 0.05


def test_members_verdicts_and_decisions_parse():
    assert [m.role for m in tm.members_of({})] == ["Product manager", "Architect"]
    assert tm.parse_member("Critic:agy:gemini-3.1-pro-high") == tm.Member("Critic", "agy", "gemini-3.1-pro-high")
    assert tm.parse_member("Bad:gpt") is None
    assert tm.parse_verdict("**APPROVE** — fine, one note") == ("approve", "— fine, one note")
    assert tm.parse_verdict("CHANGES: 1. add auth") == ("changes", "1. add auth")
    assert tm.parse_verdict("veto: leaks secrets")[0] == "veto"
    assert tm.parse_verdict("I think it is fine") == ("changes", "I think it is fine")     # no verdict: not a pass
    assert tm.parse_decision("DECISION: rework\n1. fix") == ("rework", "1. fix")
    assert tm.parse_decision("Looks good")[0] == "ask"                                     # no decision: ask


def test_all_approve_and_the_steward_lets_it_go():
    s = Script({"PM": ["APPROVE"], "Architect": ["APPROVE — notes"], "Security": ["APPROVE"],
                "Steward": ["DECISION: approve\nNobody blocks it."]})
    d = tm.run(tm.new("PRD", "# PRD\nbuild it"), TEAM, STEWARD, {"security"}, 3, 1.0, s)
    assert d.outcome == "approved" and d.decision == "Nobody blocks it."
    assert [c[0] for c in s.calls] == ["PM", "Architect", "Security", "Steward"]
    assert s.calls[1] == ("Architect", "agy", "gemini-3.1-pro-high") and round(d.spent, 2) == 0.2
    steward_prompt = s.prompts[-1][1]
    assert "Let it go when nobody blocks it." in steward_prompt and "### Architect — APPROVE" in steward_prompt
    assert "Roles with a veto: security" in steward_prompt
    assert tm.DATA_RULE in s.prompts[0][1] and "build it" in s.prompts[1][1]     # agy gets the text inline


def test_a_veto_blocks_approval_and_only_veto_roles_have_one():
    s = Script({"PM": ["VETO: wrong market"], "Architect": ["APPROVE"], "Security": ["VETO: no auth"],
                "Steward": ["DECISION: approve\nship it anyway"]})
    d = tm.run(tm.new("PRD", "x"), TEAM, STEWARD, {"security"}, 3, 0, s)
    pm, _, sec = d.reviews()
    assert pm.verdict == "changes" and "without one" in pm.note and sec.verdict == "veto"
    decide = d.turns[-1]
    assert d.outcome == "rework" and decide.verdict == "rework" and decide.note == "vetoed by Security"
    out = tm.rework_markdown(d, 3)
    assert "cycle 1 of 3" in out and "**Security — veto:** no auth" in out and out.rstrip().endswith("x")


def test_the_cycle_limit_hands_it_to_the_operator_whose_answer_wins():
    s = Script({"PM": ["CHANGES: more"], "Architect": ["APPROVE"], "Security": ["APPROVE"],
                "Steward": ["DECISION: rework\n1. more", "DECISION: approve\nthe operator said so"]})
    d = tm.run(tm.new("PRD", "x", cycle=3), TEAM, STEWARD, set(), 3, 0, s)
    assert d.outcome == "asked" and "cycle 3 of 3" in d.question and d.turns[-1].note.startswith("sent back 2")
    tm.answer(d, "ship it as it is")
    d = tm.run(d, TEAM, STEWARD, set(), 3, 0, s)
    assert d.outcome == "approved" and [c[0] for c in s.calls] == ["PM", "Architect", "Security", "Steward", "Steward"]
    last = s.prompts[-1][1]
    assert "- ship it as it is" in last and "outrank your brief" in last


def test_duplicate_roles_both_review_budget_stops_and_cycles_count_per_title():
    twins = [tm.Member("Critic"), tm.Member("Critic")]
    s = Script({"Critic": ["APPROVE", "CHANGES: no"], "Steward": ["DECISION: rework\nno"]})
    d = tm.run(tm.new("t", "x"), twins, STEWARD, set(), 3, 0, s)
    assert [t.verdict for t in d.reviews()] == ["approve", "changes"]
    s = Script({"PM": ["APPROVE"], "Architect": ["APPROVE"]})
    assert tm.run(tm.new("t", "x"), TEAM, STEWARD, set(), 3, 0.1, s).outcome == "budget" and len(s.calls) == 2
    a, r1, r2, other = (tm.new("PRD", "x") for _ in range(4))
    a.outcome, r1.outcome, r2.outcome, other.outcome, other.title = "approved", "rework", "rework", "rework", "Other"
    assert tm.cycle_of([r2, other, r1, a], "PRD") == 3 and tm.cycle_of([a, r1], "PRD") == 1


def test_old_councils_load_with_the_clan_fire_icon():
    from orkcraft.realm import catalog
    assert catalog.migrate({"type": "team", "icon": "🔥"}) == {"type": "council", "icon": "🪔"}
    assert catalog.migrate({"type": "council", "icon": "⚔"})["icon"] == "⚔"          # a chosen icon stays
    assert catalog.type_of({"type": "campfire"}).title == "Clan Fire"


def test_briefs_are_files_claude_reads_and_agy_gets_inline():
    d = tm.new("PRD", "body", "docs/prd.md")
    claude = tm.review_prompt(d, TEAM[0], TEAM, "roles/pm.md", "know the market")
    assert "`roles/pm.md`" in claude and "`docs/prd.md`" in claude and "know the market" not in claude
    agy = tm.review_prompt(d, TEAM[1], TEAM, "roles/architect.md", "know the stack", inline=True)
    assert "know the stack" in agy and "<document>\nbody\n</document>" in agy
    st = tm.Steward("short rule", brief="long knowledge", brief_path="steward.md")
    claude = tm.decide_prompt(d, st, set(), 3)
    assert "short rule" in claude and "`steward.md`" in claude and "long knowledge" not in claude
    agy = tm.decide_prompt(d, st, set(), 3, inline=True)
    assert "short rule" in agy and "long knowledge" in agy
    assert "WebSearch,WebFetch" in roads._harness_cmd("claude", "hi", Path("."), web=True)[6]
    assert "WebFetch" not in roads._harness_cmd("claude", "hi", Path("."))[6]


@pytest.mark.asyncio
async def test_the_clan_fire_reviews_a_barracks_result_and_sends_it_back(fake_repo: Path, monkeypatch):
    spec = {"id": "fire", "title": "Clan Fire", "icon": "🪔", "orc": {"name": "Chieftain"}, "type": "council",
            "config": {"steward_prompt": "Ask me before anything ships.", "members": ["Planner:claude", "Security:claude"],
                       "veto": ["Security"], "max_cycles": 2, "budget_usd": 1}}
    assert masonry.save_spec(fake_repo, spec) == []
    s = Script({"Planner": ["APPROVE", "APPROVE"], "Security": ["VETO: unsigned", "APPROVE"],
                "Steward": ["DECISION: approve\nfine", "DECISION: ask\nShip on Friday?", "DECISION: approve\nyes"]})
    monkeypatch.setattr(TeamView, "runner", staticmethod(s))
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    for event in ("team.artifact_ready", "team.approved", "team.rework"):
        ts.subscribe(app.scroll, "town_hall", "fire", event)
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        view = app.desktop.get_window("fire").query_one(TeamView)
        assert view.mini_status() == ["Planner claude", "Security ⛔ claude"]
        brief = view.role_file("Security")
        assert brief.is_file() and view.steward_file.is_file() and view.brief_of(tm.Member("Security")) == ("", "")
        brief.write_text("# Security\n\nEvery release is signed.\n", encoding="utf-8")
        sent = []
        monkeypatch.setattr(app.roads, "emit", lambda payload, meta=None: sent.append(payload) or [])

        async def settle(pred) -> None:
            for _ in range(80):
                await pilot.pause(0.02)
                if pred():
                    return

        app.deliver_payload("fire", pipes.Payload(pipes.TEXT, "# Release plan\n1. tag", "camp", "pool.done",
                                                  "Release plan"), "Release plan", "# Release plan\n1. tag")
        await settle(lambda: view.current and view.current.finished and not view._busy)
        d = view.current
        assert d.outcome == "rework" and d.title == "Release plan" and d.cycle == 1
        assert any("Every release is signed." not in p and "roles/security.md" in p for w, p in s.prompts if w == "Security")
        assert any("Ask me before anything ships." in p for w, p in s.prompts if w == "Steward")
        modes = [p.mode for p in sent]
        assert modes == ["team.artifact_ready", "team.rework"]
        assert "cycle 1 of 2" in sent[1].value and sent[1].title == "Release plan"
        assert (fake_repo / d.doc_path).read_text() == "# Release plan\n1. tag"     # read from disk by Claude

        sent.clear()                                         # the Barracks sends the revised plan back
        app.deliver_payload("fire", pipes.Payload(pipes.TEXT, "# Release plan\n1. sign\n2. tag", "camp",
                                                  "pool.done", "Release plan"), "Release plan",
                            "# Release plan\n1. sign\n2. tag")
        await settle(lambda: view.current is not d and view.current.outcome == "asked" and not view._busy)
        assert view.current.cycle == 2 and view.mini_status()[0] == "🔥 the steward asks"
        app.deliver_payload("fire", pipes.Payload(pipes.TEXT, "another doc", "camp", "pool.done", "Other"),
                            "Other", "another doc")
        assert [w[0] for w in view.waiting] == ["Other"] and view.mini_status()[-1] == "1 queued"
        s.replies["Planner"].append("APPROVE")
        s.replies["Security"].append("APPROVE")
        s.replies["Steward"].append("DECISION: approve\nok")
        assert view.quick_action("team.start")
        await pilot.pause()
        assert isinstance(app.screen, TextPrompt)
        await pilot.press(*"yes", "enter")
        await settle(lambda: len(view.history) == 3 and not view._busy)
        assert sorted(h.outcome for h in view.history) == ["approved", "approved", "rework"]
        approved = [p for p in sent if p.mode == "team.approved"]
        assert [p.value for p in approved] == ["# Release plan\n1. sign\n2. tag", "another doc"]
        report = (fake_repo / [p for p in sent if p.mode == "team.artifact_ready"][0].value).read_text()
        assert "> **Operator:** yes" in report and "Security — approve" in report
