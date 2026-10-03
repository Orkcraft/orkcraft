"""🪙 / ⚖️ / 💎 a building's goal: what the retros improve it towards (docs/design/retros-and-goals.md §3)."""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import pytest

from orkcraft import scroll as ts
from orkcraft.realm import evolution, feedback, metrics, optimize
from orkcraft.sources.limits import Limit

ORDERS = "Summarise the pull request for the operator, flag risk, end with a verdict."


def _spend(root: Path, building: str, tokens: int, outcome: str = "done", ago: dt.timedelta = dt.timedelta(hours=1)) -> None:
    metrics.record_run(root, building, outcome, 0.01, tokens, now=dt.datetime.now() - ago)


def test_the_goal_is_kept_in_the_town_scroll(tmp_path: Path):
    presets = {i: {"title": i.upper(), "icon": "🛖", "orc": "Peon", "role": "x", "category": "core"} for i in "abc"}
    s = ts.default_scroll(presets, raised=["a", "b", "c"])
    s.building("a").goal = "quality"
    data = s.to_dict()
    data["buildings"][2]["goal"] = "nonsense"
    assert ts.validate(data)                                          # an unknown goal is caught
    data["buildings"][2].pop("goal")
    assert ts.validate(data) == []
    assert data["buildings"][0]["goal"] == "quality" and "goal" not in data["buildings"][1]
    back = ts.TownScroll.from_dict({**data, "buildings": data["buildings"][:2] + [{**data["buildings"][2], "goal": "x"}]})
    assert [b.aim for b in back.buildings] == ["quality", "balance", "balance"]


def test_a_quality_building_the_operator_disliked_comes_first(tmp_path: Path):
    _spend(tmp_path, "heavy", 9000)
    _spend(tmp_path, "gem", 10)
    goals = {"heavy": "balance", "gem": "quality"}
    assert optimize.leader(tmp_path, goals=goals).building == "heavy"
    feedback.dislike(tmp_path, None, "gem", "logic")
    cand = optimize.leader(tmp_path, goals=goals)
    assert (cand.building, cand.goal) == ("gem", "quality") and "disliked it 1× this week" in cand.reason
    assert cand.actions == ("enrich", "shrink")


def test_a_failing_or_unrated_gem_comes_after_the_heavy_ones(tmp_path: Path):
    _spend(tmp_path, "gem", 10, outcome="error")
    goals = {"gem": "quality"}
    cand = optimize.leader(tmp_path, goals=goals)
    assert cand.building == "gem" and "1 of its runs failed" in cand.reason
    other = tmp_path / "other"
    feedback.record_output(other, "rated", "mill.done", "ok")
    feedback.like(other, "rated")
    assert optimize.leader(other, goals={"rated": "quality"}) is None
    assert "never rated" in optimize.leader(other, goals={"fresh": "quality"}).reason


def test_thrift_ignores_dislikes_and_quality_is_not_made_cheaper(tmp_path: Path):
    _spend(tmp_path, "t", 1000)
    feedback.record_output(tmp_path, "t", "mill.done", "ok")
    feedback.like(tmp_path, "t")
    feedback.dislike(tmp_path, None, "t", "logic")
    assert optimize.leader(tmp_path, goals={"t": "thrift"}) is None          # liked: thrift is content
    assert optimize.leader(tmp_path, goals={"t": "balance"}).building == "t"  # balance hears the 👎


def test_a_tight_camp_lowers_its_heaviest_gems_to_balance(tmp_path: Path):
    _spend(tmp_path, "gem", 24_000, outcome="error")
    limits = [Limit("claude", "", "5h session", 0.05, dt.datetime.now() + dt.timedelta(hours=4))]
    cand = optimize.leader(tmp_path, limits=limits, goals={"gem": "quality"})
    assert (cand.building, cand.goal) == ("gem", "balance") and "shrink" in cand.actions


def test_enrich_is_longer_within_the_ceiling():
    ps = [optimize.Part("orc:seer", "agent", ORDERS)]
    root = Path(".")
    better = ORDERS + " Like this: '3 files, risky: auth.py — verdict: hold'."
    assert optimize.check({"action": "enrich", "target": "orc:seer", "prompt": better}, ps, "x", root) == (better, [])
    assert optimize.check({"action": "enrich", "target": "orc:seer", "prompt": "short"}, ps, "x", root)[1]
    assert "twice" in optimize.check({"action": "enrich", "target": "orc:seer", "prompt": ORDERS * 3}, ps, "x", root)[1][0]
    thrift = optimize.GOAL_ACTIONS["thrift"]
    assert "action: one of" in optimize.check({"action": "enrich", "target": "orc:seer", "prompt": better}, ps, "x",
                                              root, actions=thrift)[1][0]
    assert not evolution.allowed("enrich", 2) and evolution.allowed("enrich", 3)


def test_the_council_hears_the_goal(tmp_path: Path):
    prompts = []
    cand = optimize.Candidate("gem", 10, 0.0, 0, 1, goal="quality")
    better = ORDERS + " Give one example of a good verdict."
    result = optimize.propose(tmp_path, cand, [optimize.Part("orc:seer", "agent", ORDERS)],
                              lambda p: (prompts.append(p) or json.dumps({"action": "enrich", "target": "orc:seer",
                                                                          "prompt": better}), None))
    assert "💎 QUALITY" in prompts[0] and '"enrich"' in prompts[0] and '"chain": only' not in prompts[0]
    assert result.proposal.action == "enrich" and result.proposal.after == better


@pytest.mark.asyncio
async def test_the_goal_button_cycles_and_the_retro_enriches(fake_repo: Path, monkeypatch):
    from orkcraft import app as app_mod
    from orkcraft.app import OrkcraftApp
    from orkcraft.screens.proposal_modal import ProposalModal

    better = ORDERS + " Show the verdict first, then the risky files."
    monkeypatch.setattr(app_mod, "OPTIMIZE_RUNNER", lambda p: (json.dumps(
        {"action": "enrich", "target": "orc:seer", "prompt": better, "why": "clearer"}), 0.003))
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=(180, 50)) as pilot:
        await pilot.pause()
        ts.add_handler(app.scroll, "town_hall", "Seer", kind="agent", orders=ORDERS)
        app.desktop.save()
        app.set_focus_state("building", building_id="town_hall")
        for _ in range(3):
            await pilot.pause()
        assert "Balance" in str(app.screen.query_one("#ib-goal").render())
        await pilot.click("#ib-goal")
        await pilot.pause()
        assert app.scroll.building("town_hall").goal == "quality"
        assert "Quality" in str(app.screen.query_one("#ib-goal").render())
        saved = json.loads(app.desktop.scroll_path.read_text())
        assert next(b for b in saved["buildings"] if b["id"] == "town_hall")["goal"] == "quality"
        feedback.dislike(fake_repo, app.scroll, "town_hall", "logic")
        assert app.optimize_now()
        for _ in range(60):
            await pilot.pause(0.05)
            if isinstance(app.screen, ProposalModal):
                break
        assert isinstance(app.screen, ProposalModal)
        await pilot.press("enter")
        await pilot.pause()
        assert app.scroll.building("town_hall").garrison.handler("seer").orders == better
        assert app.cycle_goal("town_hall") == "thrift" and app.cycle_goal("town_hall") == "balance"
        assert app.scroll.building("town_hall").goal is None
