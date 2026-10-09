"""The steward (T1098 stage 7): schedule, free metrics and findings, escalation, replayed demotions."""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import pytest

from orkcraft import scroll as ts
from orkcraft.realm import chronicles, cron, roads, steward
from orkcraft.realm.pipes import Payload

PRESETS = {
    "forge": {"title": "Forge", "icon": "⚒️", "orc": "Smith", "role": "kanban", "category": "core"},
    "scrying": {"title": "Scrying Spire", "icon": "🔮", "orc": "Shaman", "role": "preview", "category": "core"},
    "loot": {"title": "Loot Chest", "icon": "📦", "orc": "Quartermaster", "role": "files", "category": "core"},
}
NOW = dt.datetime(2026, 9, 30, 5, 30)


def test_schedule_forms():
    assert cron.to_cron("daily 05:00") == ["0", "5", "*", "*", "*"]
    assert cron.to_cron("weekly mon 05:15") == ["15", "5", "*", "*", "1"]
    assert cron.to_cron("rm -rf /") is None and cron.to_cron("on-demand") is None
    assert cron.due("daily 05:00", NOW - dt.timedelta(days=1), NOW)            # 05:00 passed since
    assert not cron.due("daily 05:00", NOW.replace(hour=5, minute=1), NOW)       # already ran today
    assert cron.due("*/15 * * * *", NOW - dt.timedelta(minutes=16), NOW)
    assert not cron.due("0 6 * * *", NOW - dt.timedelta(hours=1), NOW)
    assert cron.due("30 5 * * 3", NOW - dt.timedelta(minutes=5), NOW)             # 2026-09-30 is a Wednesday
    assert not cron.due("daily 05:30", None, NOW.replace(minute=40))             # never run: only the last minute


def test_similarity_masks_the_inputs():
    titles = ["Ship login", "Plan the migration of the auth service", "Fix the flaky calendar test"]
    ins = [[{"id": f"T10{i}0", "title": t}] for i, t in enumerate(titles)]
    outs = [f"✅ T10{i}0 — {t}" for i, t in enumerate(titles)]
    assert steward.output_similarity(outs, ins) == 1.0
    assert steward.output_similarity(outs) < 0.7                       # without the inputs the titles dominate
    varied = ["Risky: the migration lacks a rollback.", "LGTM.", "| file | issue |\n| a.py | race |"]
    assert steward.output_similarity(varied, ins) < 0.4


def _rig(tmp_path: Path, answers: list[str] | None = None, similar: bool = True):
    scroll = ts.default_scroll(PRESETS)
    ts.add_handler(scroll, "scrying", "Seer", orders="one line per task",      # a tool the steward lacks
                   harness=[{"role": "run", "harness": "agy"}])
    ts.subscribe(scroll, "scrying", "forge", "on_selection_change", handler="seer")
    path = roads.examples_file(tmp_path, "scrying", "seer")
    path.parent.mkdir(parents=True)
    with path.open("w") as f:
        for i in range(6):
            nid = f"T10{i:02d}"
            varied = ["Risky: the migration lacks a rollback.", "## Review\n- tests missing\n- naming ok",
                      "LGTM.", "Blocked on credentials; ask the operator before retrying anything here.",
                      "| file | issue |\n|---|---|\n| a.py | race |", "Nothing to add."]
            out = f"✅ {nid} — {['Ship login', 'Plan the auth migration', 'Fix calendar', 'Docs', 'Cache warmup', 'CI'][i]}" if similar else varied[i]
            f.write(json.dumps({"inputs": [{"road": "forge-selection", "id": nid, "title": ['Ship login', 'Plan the auth migration', 'Fix calendar', 'Docs', 'Cache warmup', 'CI'][i], "kind": "node",
                                            "value": nid}], "output": out}) + "\n")
    prompts = []

    def runner(prompt):
        prompts.append(prompt)
        return (answers or ['{"proposals": [{"type": "note", "text": "ok", "why": "w"}]}'])[min(len(prompts), len(answers or [1])) - 1], 0.04

    return scroll, runner, prompts


def test_repeating_agent_is_found_and_demoted_after_replay(tmp_path: Path):
    demote = {"proposals": [{"type": "demote", "orc": "seer", "why": "Every answer is the id and title.",
                             "chain": [{"op": "template", "md": "✅ {id} — {title}"}]}]}
    scroll, runner, prompts = _rig(tmp_path, [json.dumps(demote)])
    report = steward.watch(tmp_path, scroll, "scrying", sessions=[], runner=runner, now=NOW)
    kinds = [f.kind for f in report.findings]
    assert "repeats" in kinds and report.escalated and report.attempts == 1
    assert "seer: input" in prompts[0] and "[repeats]" in prompts[0]
    [p] = report.proposals
    assert p.type == "demote" and p.replay.exact == 6 and p.replay.score == 1.0 and p.ready
    assert scroll.building("scrying").garrison.handler("seer").kind == "agent"     # proposals only
    what = steward.apply_proposal(scroll, "scrying", p)
    seer = scroll.building("scrying").garrison.handler("seer")
    assert what == "Seer demoted to a chain" and seer.kind == "chain" and seer.harness == [] and seer.avatar == "🪧"
    assert scroll.building("scrying").roads_of("seer")                             # keeps its roads
    assert ts.validate(scroll.to_dict()) == []
    saved = steward.load_report(tmp_path, "scrying") if steward.save_report(tmp_path, report) else None
    assert saved["proposals"][0]["replay"]["exact"] == 6


def test_a_chain_that_disagrees_is_not_ready(tmp_path: Path):
    demote = {"proposals": [{"type": "demote", "orc": "seer", "why": "w", "chain": [{"op": "count"}]}]}
    scroll, runner, _ = _rig(tmp_path, [json.dumps(demote)])
    [p] = steward.watch(tmp_path, scroll, "scrying", sessions=[], runner=runner, now=NOW).proposals
    assert p.replay.score < steward.READY_SCORE and not p.ready and p.replay.samples


def test_no_findings_no_model(tmp_path: Path):
    scroll, runner, prompts = _rig(tmp_path, similar=False)
    ts.subscribe(scroll, "loot", "forge", "on_task_completed")
    carts = [roads.Cart("forge-task", "forge", "loot", "delivered", Payload("text", "x", "forge", "on_task_completed"))]
    report = steward.watch(tmp_path, scroll, "scrying", sessions=[], runner=runner, now=NOW,
                           carts=carts, runs=[roads.HandlerRun("scrying", "seer", "agent", "r", 0, outcome="done")])
    assert report.findings == [] and not report.escalated and prompts == []


def test_findings_errors_jams_filters_spend_unused(tmp_path: Path):
    scroll, runner, _ = _rig(tmp_path, similar=False)
    runs = [roads.HandlerRun("scrying", "seer", "agent", str(i), 0, outcome=o)
            for i, o in enumerate(["error"] * 4 + ["interrupted"] * 3 + ["done"])]
    carts = [roads.Cart("forge-selection", "forge", "scrying", "filtered", Payload("node", "T1", "forge", "on_selection_change"))] * 24
    class S:  # a session of the Seer that spent $6
        orcs, last, transcript = {"scrying/seer"}, NOW, "t"
    import orkcraft.realm.steward_metrics as st
    orig = st._session_cost
    st._session_cost = lambda t: 6.0
    try:
        m = steward.collect(tmp_path, scroll, "scrying", carts=carts, runs=runs, sessions=[S()], now=NOW)
    finally:
        st._session_cost = orig
    kinds = {f.kind for f in steward.findings(m, scroll)}
    assert {"handler_errors", "jam", "noisy_filter", "spend"} <= kinds
    assert m.spend_usd == {"seer": 6.0} and m.carts_in == {"forge-selection": {"filtered": 24}}
    quiet = steward.collect(tmp_path, scroll, "loot", sessions=[], now=NOW)
    assert [f.kind for f in steward.findings(quiet, scroll)] == ["unused"]


def test_invalid_proposals_go_back_and_budget_stops_escalation(tmp_path: Path):
    bad = json.dumps({"proposals": [{"type": "new_road", "from": "scrying", "event": "on_selection_change", "why": "w"}]})
    worse = "no idea"
    good = json.dumps({"proposals": [{"type": "set_run", "orc": "seer", "run": {"quiet_s": 60}, "why": "slow down"}]})
    scroll, runner, prompts = _rig(tmp_path, [worse, bad, good])
    report = steward.watch(tmp_path, scroll, "scrying", sessions=[], runner=runner, now=NOW)
    assert report.attempts == 3 and report.cost_usd == pytest.approx(0.12)
    assert "own building" in prompts[2] and report.proposals[0].type == "set_run"
    steward.apply_proposal(scroll, "scrying", report.proposals[0])
    assert scroll.building("scrying").garrison.handler("seer").run_policy["quiet_s"] == 60

    scroll2, runner2, prompts2 = _rig(tmp_path / "b")
    report2 = steward.watch(tmp_path / "b", scroll2, "scrying", sessions=[], runner=runner2, budget_ok=False, now=NOW)
    assert report2.findings and not report2.escalated and prompts2 == [] and "budget" in report2.error


def test_chronicle_events_exist():
    assert chronicles.describe({"type": "steward_report", "findings": 2, "proposals": 1})[1] == \
        "steward: 2 finding(s), 1 proposal(s)"
    assert chronicles.describe({"type": "proposal_applied", "what": "Seer demoted to a chain"})[1] == \
        "applied: Seer demoted to a chain"


def test_a_steward_runs_each_task_on_its_own_tier(monkeypatch, tmp_path):
    """`OrcSpec.models`: a tier per task (watch, redesign, keeper, the type's own); the scroll keeps it,
    the model call takes it, an unset task runs on the default, a test's fake runner stays as it is."""
    import threading
    from orkcraft.core.workers.barracks import BarracksWorker, RunOutcome
    from orkcraft.realm import builders
    presets = {"a": {"title": "A", "icon": "🛖", "orc": "Peon", "role": "x", "category": "core"}}
    s = ts.default_scroll(presets, raised=["a"])
    b = s.building("a")
    b.garrison.steward = ts.OrcSpec("keeper", "Grunts")
    assert steward.set_models(b, {"watch": "laborer", "review": "elder", "keeper": "", "nonsense": "elder"}) == \
        {"watch": "laborer", "review": "elder"}
    back = ts.TownScroll.from_dict(s.to_dict()).building("a")
    assert back.garrison.steward.models == {"watch": "laborer", "review": "elder"} and ts.validate(s.to_dict()) == []
    assert steward.model_for(back, "watch") == "haiku" and steward.model_for(back, "redesign") == ""
    calls = []
    monkeypatch.setattr(builders, "ask", lambda tool, prompt, model=None: calls.append((tool, model)) or ("{}", None))
    monkeypatch.setattr(builders, "main_tool", lambda machine=None: "agy")
    steward.runner_for(back, "watch")("p")                          # main: the machine's main tool
    steward.runner_for(back, "redesign")("p")
    back.garrison.steward.harness = [{"role": "run", "harness": "claude"}]
    steward.runner_for(back, "watch")("p")                          # its own tool: the one its step names
    assert calls == [("agy", "laborer"), ("agy", None), ("claude", "laborer")]
    fake = lambda prompt: ("{}", None)                               # noqa: E731
    assert steward.runner_for(back, "watch", fake) is fake
    assert "answer" in steward.uses("barracks") and "answer" not in steward.uses("forge")

    seen = []

    class Pool:                                                      # the Barracks' steward: its review on its tier
        steward_runner = staticmethod(lambda h, p, w, c, m: seen.append((h, m)) or ("ACCEPT", 0.0))
        config = {"steward": "claude:warrior"}
        building_id, simulated, TYPE, aim_now = "a", False, "barracks", "balance"

        class town:
            scroll = s
    BarracksWorker._steward(Pool(), "review it", tmp_path, threading.Event(), RunOutcome(), use="review")
    BarracksWorker._steward(Pool(), "answer it", tmp_path, threading.Event(), RunOutcome(), use="answer")
    assert seen == [("claude", "opus"), ("claude", "sonnet")]      # review: elder; answer: its setting's
    Pool.config = {"steward": "claude"}                              # its tool, no model of its own
    BarracksWorker._steward(Pool(), "the whole", tmp_path, threading.Event(), RunOutcome(), use="final")
    Pool.aim_now = "thrift"                                          # a tight quota runs it as 🪙
    BarracksWorker._steward(Pool(), "the whole", tmp_path, threading.Event(), RunOutcome(), use="final")
    assert seen[2:] == [("claude", "opus"), ("claude", "sonnet")]   # no setting: the goal's tier


def test_the_steward_s_work_follows_its_own_tier_and_its_upkeep_does_not():
    """One order for every building (docs/design/steward-at-work.md §2): a tier set closer to the work, the
    one picked for the task, the building's own setting, its steward's tier for its work, the default. A steward
    with no tier of its own has the one its goal gave it before (docs/design/warchief-line-and-cards.md §7)."""
    presets = {"a": {"title": "A", "icon": "🛖", "orc": "Peon", "role": "x", "category": "core"}}
    b = ts.default_scroll(presets, raised=["a"]).building("a")
    b.garrison.steward = ts.OrcSpec("keeper", "Grunts")
    assert steward.is_work("workshop", "escalate") and not steward.is_work("workshop", "watch")
    pick = lambda use, **k: steward.pick(b, use, "claude", type_id="workshop", **k)          # noqa: E731
    assert pick("escalate") == steward.Pick("", "", "default")                       # ⚖️ balance: the default
    b.goal = "quality"
    assert steward.level_of(b) == "elder"                                             # none of its own: the goal's
    assert pick("escalate") == steward.Pick("opus", "elder", "level")
    assert pick("escalate", goal="thrift") == steward.Pick("sonnet", "warrior", "level")  # tight: the light column
    assert pick("escalate", tight=True).tier == "warrior"
    b.garrison.steward.tier = "laborer"                                               # its own tier: the goal is not asked
    assert steward.level_of(b) == "laborer"
    assert pick("escalate") == steward.Pick("sonnet", "warrior", "level")
    b.garrison.steward.tier = "elder"
    b.goal = "thrift"                                                                 # a thrifty goal is not a tight quota
    assert pick("escalate", goal="thrift") == steward.Pick("opus", "elder", "level")
    assert pick("watch").by == "default"                                              # upkeep: no goal
    assert pick("escalate", setting="haiku") == steward.Pick("haiku", "", "setting")
    steward.set_models(b, {"escalate": "laborer"})
    assert pick("escalate", setting="haiku").by == "picked"
    assert pick("escalate", own="elder") == steward.Pick("opus", "elder", "own")
