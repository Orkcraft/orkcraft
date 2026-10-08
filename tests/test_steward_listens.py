"""The steward listens (docs/design/steward-listens.md stage 1): a road rule — a `steward` handler — is carried
out by its building's steward, on the steward's tool and at its tier for `listen`."""
from __future__ import annotations

import hashlib

import pytest

from orkcraft import scroll as ts
from orkcraft.realm import roads, steward, tiers
from tests.test_road_engine import PRESETS, Rig, node, wait_for

RULE = "Only my boss's mail; make one to-do per letter, with the deadline if it names one."


def ruled(goal: str | None = None, tool: str = "claude", picked: str = "") -> ts.TownScroll:
    scroll = ts.default_scroll(PRESETS)
    b = scroll.building("scrying")
    b.goal = goal
    stew = b.garrison.steward
    stew.role, stew.orders = "keeps the operator's day in order", "Nothing slips past a deadline."
    stew.harness = [{"role": "run", "harness": tool}]
    if picked:
        stew.models = {"listen": picked}
    ts.add_handler(scroll, "scrying", "Boss's mail", kind="steward", orders=RULE, run={"quiet_s": 0})
    ts.subscribe(scroll, "scrying", "forge", "on_selection_change", handler="boss_s_mail")
    return scroll


def recording(calls: list):
    def runner(harness, prompt, repo, env, cancel, model=""):
        calls.append({"harness": harness, "prompt": prompt, "env": env, "model": model})
        return "- [ ] answer the boss", 0.03
    return runner


def test_a_rule_is_a_handler_with_no_tools_of_its_own():
    scroll = ruled()
    rule = scroll.building("scrying").garrison.handler("boss_s_mail")
    assert rule.kind == "steward" and rule.harness == [] and rule.uses_model and rule.on_steward
    assert ts.RUN_DEFAULTS["steward"] == ts.RUN_DEFAULTS["agent"] and rule.avatar == "📜"
    assert ts.validate(scroll.to_dict()) == []
    again = ts.TownScroll.from_dict(scroll.to_dict()).building("scrying").garrison.handler("boss_s_mail")
    assert (again.kind, again.orders, again.harness) == ("steward", RULE, [])


def test_listen_is_work_every_steward_has():
    assert "listen" in steward.uses("forge") and "listen" in steward.uses("barracks")
    assert steward.is_work("forge", "listen") and not steward.is_work("forge", "roads")
    assert [steward.goal_tier("any", "listen", g) for g in ("thrift", "balance", "quality")] == \
        ["laborer", "warrior", "elder"]


def test_a_rule_runs_on_the_stewards_tool_at_its_listen_tier():
    calls: list = []
    scroll = ruled(tool="claude", picked="elder")
    rig = Rig(scroll, recording(calls))
    [cart] = rig.engine.emit(node("T1001"))
    assert cart.status == roads.SENT and cart.detail == "Boss's mail"
    wait_for(lambda: rig.runs)
    [call] = calls
    assert call["harness"] == "claude" and call["model"] == tiers.MODELS["claude"]["elder"]
    assert call["env"]["ORKCRAFT_ORC"] == "scrying/boss_s_mail"           # its runs stay in its own chronicle
    prompt = call["prompt"]
    assert "the steward of the Scrying Spire" in prompt and RULE in prompt
    assert "keeps the operator's day in order" in prompt and "Nothing slips past a deadline." in prompt
    assert rig.outputs == [("scrying", "boss_s_mail", "- [ ] answer the boss")]
    assert rig.runs[0].kind == "steward" and rig.runs[0].cost_usd == pytest.approx(0.03)
    assert roads.read_examples(rig.repo, "scrying", "boss_s_mail")        # kept for the replay


@pytest.mark.parametrize("goal, aim, tier", [("quality", None, "elder"), (None, None, "warrior"),
                                             ("quality", "thrift", "laborer")])
def test_with_nothing_picked_the_goal_in_force_names_the_tier(goal, aim, tier):
    calls: list = []
    rig = Rig(ruled(goal=goal), recording(calls))
    rig.engine._aim = lambda building_id: aim                                # a tight quota runs it as thrift
    rig.engine.emit(node("T1001"))
    wait_for(lambda: rig.runs)
    assert calls[0]["model"] == tiers.MODELS["claude"][tier]


def test_a_building_without_a_steward_falls_back_to_the_main_tool():
    calls: list = []
    scroll = ruled()
    scroll.building("scrying").garrison.steward = None
    rig = Rig(scroll, recording(calls))
    rig.engine.emit(node("T1001"))
    wait_for(lambda: rig.runs)
    assert calls[0]["harness"] == "main" and "the steward of the Scrying Spire" in calls[0]["prompt"]


def test_an_old_agent_handler_keeps_its_own_tools():
    calls: list = []
    scroll = ruled(picked="elder")
    ts.add_handler(scroll, "scrying", "Pair", orders="summarise", run={"quiet_s": 0},
                   harness=[{"role": "write", "harness": "agy"}, {"role": "review", "harness": "claude"}])
    ts.unsubscribe(scroll, "scrying", "forge-selection")
    ts.subscribe(scroll, "scrying", "forge", "on_selection_change", handler="pair")
    rig = Rig(scroll, recording(calls))
    rig.engine.emit(node("T1001"))
    wait_for(lambda: rig.runs)
    assert [c["harness"] for c in calls] == ["agy", "claude"] and all(c["model"] == "" for c in calls)
    assert "You are Pair, a handler ork" in calls[0]["prompt"]


def test_a_hybrid_with_no_tools_escalates_to_the_steward():
    calls: list = []
    scroll = ruled(picked="warrior")
    rig = Rig(scroll, recording(calls))
    src = "import sys\nprint('looked: nothing routine')\nsys.exit(3)\n"
    path = rig.repo / ".orkcraft" / "scripts" / "sorter.py"
    path.parent.mkdir(parents=True)
    path.write_text(src)
    ts.add_handler(scroll, "loot", "Sorter", kind="hybrid", harness=[], orders="Sort what the script cannot.",
                   run={"quiet_s": 0}, script={"path": ".orkcraft/scripts/sorter.py", "reviewed": True,
                                               "sha256": hashlib.sha256(src.encode()).hexdigest()})
    loot = scroll.building("loot")
    loot.garrison.steward.harness = [{"role": "run", "harness": "codex"}]
    ts.subscribe(scroll, "loot", "forge", "on_selection_change", handler="sorter")
    rig.engine.emit(node("T1001"))
    wait_for(lambda: any(r.orc_id == "sorter" for r in rig.runs))
    [call] = [c for c in calls if "Sorter" in c["prompt"]]
    assert call["harness"] == "codex" and "the steward of the Loot Chest" in call["prompt"]
    assert "looked: nothing routine" in call["prompt"]                      # what the script found


def test_a_rules_own_tier_comes_before_the_stewards_listen_and_the_goal():
    """steward-listens.md §7: a rule that needs a heavier model names its own tier; empty follows the steward."""
    calls: list = []
    scroll = ruled(goal="thrift", picked="laborer")
    ts.update_orc(scroll, "scrying", "boss_s_mail", tier="elder")
    rule = ts.TownScroll.from_dict(scroll.to_dict()).building("scrying").garrison.handler("boss_s_mail")
    assert rule.tier == "elder" and ts.validate(scroll.to_dict()) == []
    rig = Rig(scroll, recording(calls))
    rig.engine.emit(node("T1001"))
    wait_for(lambda: rig.runs)
    assert calls[0]["model"] == tiers.MODELS["claude"]["elder"]
    ts.update_orc(scroll, "scrying", "boss_s_mail", tier="")
    assert "tier" not in scroll.building("scrying").garrison.handler("boss_s_mail").to_dict()
    assert roads.steward_steps(scroll.building("scrying"))[0]["tier"] == "laborer"
