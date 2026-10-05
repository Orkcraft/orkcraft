"""🔧 Local optimisation (T1108 stage 8): the leader, a checked proposal, applied by one click, Z takes it back."""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import pytest

from orkcraft.realm import checkpoint, feedback, metrics, optimize

NOW = dt.datetime(2026, 10, 2, 6, 20)
ORDERS = ("Read every incoming pull request event carefully. Summarise the change in plain words, list the files "
          "touched, flag anything risky, and finish with a one-line verdict for the operator. Be thorough.")


def _spend(root: Path, building: str, tokens: int, when: dt.datetime = NOW) -> None:
    metrics.record_run(root, building, "done", 0.01, tokens, now=when)


def test_the_leader_is_todays_top_spender_the_operator_is_not_happy_with(tmp_path: Path):
    now = dt.datetime.now()
    assert optimize.leader(tmp_path, now) is None
    _spend(tmp_path, "a", 100, now)
    _spend(tmp_path, "b", 500, now)
    _spend(tmp_path, "a", 9999, now - dt.timedelta(days=1))             # yesterday does not count
    cand = optimize.leader(tmp_path, now)
    assert (cand.building, cand.tokens) == ("b", 500) and "not liked it since its last change" in cand.reason
    assert "83 % of the camp's tokens" in cand.use
    feedback.record_output(tmp_path, "b", "mill.done", "fine")
    feedback.like(tmp_path, "b")
    assert optimize.leader(tmp_path, now).building == "a"                 # liked since its last change: the next
    feedback.record_output(tmp_path, "a", "mill.done", "fine")
    feedback.like(tmp_path, "a")
    assert optimize.leader(tmp_path, now) is None
    feedback.dislike(tmp_path, None, "b", "logic")
    assert "disliked it 1× today" in optimize.leader(tmp_path, now).reason


def test_a_small_spender_is_not_worth_a_retro(tmp_path: Path):
    now = dt.datetime.now()
    _spend(tmp_path, "big", 1000, now)
    _spend(tmp_path, "tiny", 50, now)
    feedback.record_output(tmp_path, "big", "mill.done", "fine")
    feedback.like(tmp_path, "big")
    assert optimize.leader(tmp_path, now) is None                         # tiny is under MIN_SHARE


def test_a_like_before_the_last_change_does_not_count(tmp_path: Path):
    now = dt.datetime.now()
    _spend(tmp_path, "b", 500, now)
    feedback.record_output(tmp_path, "b", "mill.done", "fine")
    feedback.like(tmp_path, "b")
    ref = tmp_path / ".orkcraft/feedback/b/references.jsonl"
    old = json.loads(ref.read_text())
    old["ts"] = "2000-01-01T00:00:00"
    ref.write_text(json.dumps(old) + "\n")
    (tmp_path / ".orkcraft/buildings").mkdir(parents=True)
    (tmp_path / ".orkcraft/buildings/b.json").write_text("{}")
    checkpoint.commit(tmp_path, "update", "b", "changed")                 # changed after the like
    assert optimize.leader(tmp_path, now).building == "b"


def test_run_logs_reach_the_council(tmp_path: Path):
    from orkcraft.realm import workshop
    workshop.log(tmp_path / ".orkcraft/workshop/b", workshop.Run("t", "e", "s", "red green", 0, out="2 words"))
    logs = optimize.run_logs(tmp_path, "b")
    assert logs == ["- in: red green → out: 2 words"]
    prompts = []
    optimize.propose(tmp_path, optimize.Candidate("b", 9, 0.0, 0, 1), [optimize.Part("orc:x", "agent", ORDERS)],
                     lambda p: (prompts.append(p) or "nope", None), attempts=1)
    assert "ITS RECENT RUNS" in prompts[0] and "red green" in prompts[0]


def test_every_change_is_checked(tmp_path: Path):
    ps = [optimize.Part("orc:seer", "agent", ORDERS), optimize.Part("steward", "steward", "say what it is")]
    ok, problems = optimize.check({"action": "shrink", "target": "orc:seer", "prompt": "Summarise the PR; flag risk."}, ps, "x", tmp_path)
    assert ok and not problems
    assert optimize.check({"action": "shrink", "target": "orc:seer", "prompt": ORDERS}, ps, "x", tmp_path)[1]
    chain = [{"op": "template", "md": "{title}"}]
    assert json.loads(optimize.check({"action": "chain", "target": "orc:seer", "chain": chain}, ps, "x", tmp_path)[0]) == chain
    assert optimize.check({"action": "chain", "target": "steward", "chain": chain}, ps, "x", tmp_path)[1]
    assert optimize.check({"action": "script", "target": "steward", "script": "import os\nos.system('sudo ls')\n"},
                          ps, "x", tmp_path)[1]
    mocks = [{"event": "e", "source": "s", "title": "", "value": "hi"}]
    bad = optimize.check({"action": "script", "target": "steward", "script": "import sys\nsys.exit(3)\n"}, ps, "x",
                         tmp_path, mocks=mocks)
    assert bad[1] and "exit 3" in bad[1][0]
    good = optimize.check({"action": "script", "target": "steward", "script": "print('ok')\n"}, ps, "x", tmp_path, mocks=mocks)
    assert good == ("print('ok')\n", [])
    assert optimize.check({"action": "rewrite", "target": "steward"}, ps, "x", tmp_path)[1]


def test_propose_retries_once_with_its_problems(tmp_path: Path):
    prompts = []
    answers = iter([json.dumps({"action": "shrink", "target": "orc:seer", "prompt": ORDERS}),
                    json.dumps({"action": "shrink", "target": "orc:seer", "prompt": "Summarise; flag risk; verdict.",
                                "why": "the same job in a third of the words", "saving": "~60 % input tokens"})])

    def runner(prompt):
        prompts.append(prompt)
        return next(answers), 0.004

    cand = optimize.Candidate("hall", 5000, 0.4, 0, 1)
    result = optimize.propose(tmp_path, cand, [optimize.Part("orc:seer", "agent", ORDERS)], runner)
    assert result.proposal is not None and result.proposal.after == "Summarise; flag risk; verdict."
    assert "5000 tokens" in prompts[0] and "disliked it 1×" in prompts[0] and "REJECTED" in prompts[1]
    optimize.save(tmp_path, result.proposal)
    assert [p.id for p in optimize.pending(tmp_path)] == [result.proposal.id]


@pytest.mark.asyncio
async def test_apply_with_one_click_and_z_takes_it_back(fake_repo: Path, monkeypatch):
    from orkcraft.core import runners
    from orkcraft import scroll as ts
    from orkcraft.app import OrkcraftApp
    from orkcraft.screens.proposal_modal import ProposalModal

    short = "Summarise the PR, flag risk, give a verdict."
    monkeypatch.setattr(runners, "OPTIMIZE_RUNNER", lambda p: (json.dumps(
        {"action": "shrink", "target": "orc:seer", "prompt": short, "why": "same job, fewer words"}), 0.003))
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=(180, 50)) as pilot:
        await pilot.pause()
        ts.add_handler(app.scroll, "town_hall", "Seer", kind="agent", orders=ORDERS)
        app.desktop.save()
        app.checkpoint("update", "town_hall", "hire Seer")
        _spend(fake_repo, "town_hall", 4000, dt.datetime.now())
        assert app.optimize_now()
        for _ in range(60):
            await pilot.pause(0.05)
            if isinstance(app.screen, ProposalModal):
                break
        assert isinstance(app.screen, ProposalModal)
        await pilot.press("enter")
        await pilot.pause()
        seer = app.scroll.building("town_hall").garrison.handler("seer")
        assert seer.orders == short
        p = optimize.proposals(fake_repo)[0]
        assert p.status == "applied" and p.commit
        assert checkpoint.history(fake_repo, "town_hall")[0].message.startswith("auto-improve(town_hall): shrink orc:seer")
        assert app.revert_building("town_hall")
        assert app.scroll.building("town_hall").garrison.handler("seer").orders == ORDERS
        assert not app.apply_proposal(p)                                   # applied once: never twice


def test_a_clan_fires_brief_is_never_a_workshop_steward():
    spec = {"id": "fire", "type": "council", "config": {"steward_prompt": "Let it go when nobody blocks it."}}
    assert [p.id for p in optimize.parts(None, spec, "fire")] == []
    shop = {"id": "shop", "type": "workshop", "config": {"steward_prompt": "Sort what the script hands over."}}
    assert [p.id for p in optimize.parts(None, shop, "shop")] == ["steward"]
