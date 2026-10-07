"""Every building's work runs on its steward's model (docs/design/steward-at-work.md §2): a model call that
makes a building's results goes through `Worker.steward_runner` / `steward_pick` (realm/steward.py `pick`),
so the tier picked for it, the building's own setting, its goal and a tight quota all reach it.

A building whose worker calls a model on its own breaks this. The buildings in `steward.NOT_YET` are being
reworked and are marked as expected to fail: until their model calls go through their steward, the
building is not done — and its mark comes off with that change (the test then passes)."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from orkcraft.realm import catalog, steward

ROOT = Path(__file__).resolve().parent.parent / "orkcraft"
CALL = re.compile(r"builders\.(?:main_runner_of|main_runner|claude_runner|runner_on|ask|runner_for)\b"
                  r"|fastpath\.light_runner|roads\.run_agent|jobs\.run_work|default_agent\(")
# Model calls in a worker that are not its steward's work, and why.
NOT_WORK = {
    ("core/workers/barracks.py", "jobs.run_work"): "its orks: their tiers come from the goal (realm/plans.py GOALS)",
    ("core/workers/barracks.py", "roads.run_agent"): "its steward's call, on the model steward.pick names (_steward)",
    ("core/workers/council.py", "roads.run_agent"): "its members, and its moderator on steward_pick's model",
    ("core/workers/council_setup.py", "fastpath.light_runner"): "setting up its clan: upkeep, not its work",
    ("core/workers/mill.py", "default_agent("): "its agent steps on steward_pick's model",
}
EXTRA = {"catapult": ["realm/catapult_web/*.py"]}


def _files(type_id: str) -> list[Path]:
    globs = [f"core/workers/{type_id}.py", f"core/workers/{type_id}_*.py", *EXTRA.get(type_id, [])]
    return sorted({p for g in globs for p in ROOT.glob(g)})


def _own_calls(type_id: str) -> list[str]:
    """Its worker's model calls that skip its steward: `file:line  code`."""
    out = []
    for path in _files(type_id):
        rel = path.relative_to(ROOT).as_posix()
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            code = line.split("#", 1)[0]
            for m in CALL.finditer(code):
                if (rel, m.group(0)) not in NOT_WORK:
                    out.append(f"{rel}:{n}  {line.strip()}")
    return out


def _case(type_id: str):
    if type_id in steward.NOT_YET:
        return pytest.param(type_id, marks=pytest.mark.xfail(
            reason=f"{steward.NOT_YET[type_id]}: not on its steward yet — the building is not done without it"))
    return type_id


@pytest.mark.parametrize("type_id", [_case(t) for t in sorted(catalog.TYPES)])
def test_a_building_s_work_runs_on_its_steward(type_id: str):
    assert _own_calls(type_id) == [], (
        f"{type_id}: call its model through Worker.steward_runner / steward_pick, with a line in "
        f"realm/steward.py WORK (or say in NOT_WORK here why the call is not its work)")


def test_the_lists_name_real_things():
    assert set(steward.NOT_YET) <= set(catalog.TYPES)
    for type_id, work in steward.WORK.items():
        assert type_id in catalog.TYPES and set(work) <= set(steward.TYPE_USES[type_id])
        assert all(set(by_goal) == {"thrift", "balance", "quality"} for by_goal in work.values())
    for (rel, _call), _why in NOT_WORK.items():
        assert (ROOT / rel).is_file()


def test_the_buildings_think_on_their_steward_s_model_by_their_goal(fake_repo, monkeypatch):
    """Task Fields' plan, the Watchtower's judge, the Mill's agent steps and the Review board's moderator: the
    goal moves them, a tight quota runs them as 🪙, their own setting wins."""
    from orkcraft.realm import checkpoint
    from orkcraft.core import buildings
    from orkcraft.core.workers import Worker
    from orkcraft.gui.host import Host
    checkpoint.ensure(fake_repo)
    host = Host(fake_repo, auto_commit=False)
    town = host.town
    monkeypatch.setattr(Worker, "quota", lambda self: None)
    seen = {}
    for type_id, use in (("fields", "plan"), ("watchtower", "judge"), ("mill", "agent"), ("council", "decide")):
        bid = buildings.raise_spec(town, buildings.type_spec(town, type_id)).id
        w = town.worker(bid)
        bs = town.scroll.building(bid)
        tiers_by_goal = []
        for goal in ("thrift", "balance", "quality"):
            bs.goal = None if goal == "balance" else goal
            tiers_by_goal.append(w.steward_pick(use).tier)
        seen[type_id] = tiers_by_goal
        assert tiers_by_goal == [steward.goal_tier(type_id, use, g) for g in ("thrift", "balance", "quality")]
        assert w.steward_pick(use, "opus").by == "setting"                 # its own setting wins over the goal
    assert seen["fields"] == ["laborer", "laborer", "warrior"]
    fields = next(w for w in town.workers.values() if w.TYPE == "fields")
    monkeypatch.setattr(type(fields), "quota", lambda self: type("Camp", (), {"tight": True})())
    town.scroll.building(fields.building_id).goal = "quality"
    assert fields.steward_pick("plan").tier == "laborer"                  # tight: 🪙 thrift


def test_the_warchief_and_the_town_planner_think_on_the_town_hall_s_steward(fake_repo, monkeypatch):
    from orkcraft.core.workers import Worker
    from orkcraft.gui.host import Host
    from orkcraft.realm import builders, checkpoint
    checkpoint.ensure(fake_repo)
    town = Host(fake_repo, auto_commit=False).town
    monkeypatch.setattr(Worker, "quota", lambda self: None)
    calls = []
    monkeypatch.setattr(builders, "ask", lambda tool, prompt, model=None: calls.append((tool, model)) or ("ok", 0.0))
    hall, tool = town.worker("town_hall"), builders.main_tool(town.machine)
    hall.steward_runner("answer")("p")                                    # ⚖️: the main tool's own model, as before
    town.scroll.building("town_hall").goal = "quality"
    hall.steward_runner("answer")("p")
    hall.steward_runner("build")("p")
    town.scroll.building("town_hall").goal = "thrift"
    hall.steward_runner("build")("p")
    assert calls == [(tool, None), (tool, "elder"), (tool, "elder"), (tool, "warrior")]
