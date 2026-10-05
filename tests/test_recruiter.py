"""The Recruiter (T1098 stage 3): prompt → validated handler with a kind and a reason, retries."""
from __future__ import annotations

import json
from pathlib import Path

from orkcraft import scroll as ts
from orkcraft.realm import recruiter

PRESETS = {
    "forge": {"title": "Forge", "icon": "⚒️", "orc": "Smith", "role": "kanban", "category": "core"},
    "loot": {"title": "Loot Chest", "icon": "📦", "orc": "Quartermaster", "role": "files", "category": "core"},
    "scrying": {"title": "Scrying Spire", "icon": "🔮", "orc": "Shaman", "role": "preview", "category": "core"},
    "town_hall": {"title": "War Tent", "icon": "💬", "orc": "Peon", "role": "sessions", "category": "core"},
}
CHAIN_ANSWER = {
    "name": "Scribe", "role": "done-task digest", "kind": "chain",
    "why": "Formatting the finished task's id and title needs no judgment.",
    "chain": [{"op": "template", "md": "✅ {id} {title}"}],
    "roads": [{"from": "forge", "event": "on_selection_change", "filter": {"node_status": ["done"]}}],
}


def scripted(*answers):
    prompts = []

    def runner(prompt):
        prompts.append(prompt)
        a = answers[min(len(prompts) - 1, len(answers) - 1)]
        return (a if isinstance(a, str) else "Here you go:\n```json\n" + json.dumps(a) + "\n```"), 0.03

    return runner, prompts


def test_chain_is_accepted_and_applied(tmp_path: Path):
    scroll = ts.default_scroll(PRESETS)
    runner, prompts = scripted(CHAIN_ANSWER)
    result = recruiter.recruit("show finished tasks as a line", scroll, "scrying", runner=runner)
    assert result.ok and len(prompts) == 1 and result.cost_usd == 0.03
    assert "forge — Forge — on_selection_change, on_task_completed" in prompts[0]
    assert "- scrying" not in prompts[0]                       # the receiver is not a source
    assert "show finished tasks" in prompts[0]
    assert result.orc["kind"] == "chain" and result.orc["why"].startswith("Formatting")
    assert scroll.building("scrying").garrison.handlers == []  # recruit only proposes
    orc = recruiter.apply(scroll, "scrying", result, tmp_path)
    assert orc.id == "scribe" and orc.avatar == "🪧"
    [road] = scroll.building("scrying").roads
    assert (road.source, road.event, road.handler, road.filter) == \
        ("forge", "on_selection_change", "scribe", {"node_status": ["done"]})
    assert ts.validate(scroll.to_dict()) == []


def test_invalid_answers_go_back_with_the_errors():
    scroll = ts.default_scroll(PRESETS)
    bad_road = {**CHAIN_ANSWER, "roads": [{"from": "scrying", "event": "on_selection_change"}]}
    no_why = {**CHAIN_ANSWER, "why": ""}
    runner, prompts = scripted("I think a chain would do.", bad_road, no_why)
    result = recruiter.recruit("digest", scroll, "scrying", runner=runner)
    assert not result.ok and len(result.attempts) == 3 and result.cost_usd == 0.09
    assert result.attempts[0].errors == ["no JSON object in the answer"]
    assert any("own building" in e for e in result.attempts[1].errors)
    assert "no JSON object" in prompts[1] and "own building" in prompts[2]
    assert result.attempts[2].errors == ["why is required: say what a cheaper kind could not do"]
    assert scroll.building("scrying").roads == []


def test_second_attempt_can_fix_it():
    scroll = ts.default_scroll(PRESETS)
    broken = {**CHAIN_ANSWER, "chain": [{"op": "exec", "code": "import os"}]}
    runner, prompts = scripted(broken, CHAIN_ANSWER)
    result = recruiter.recruit("digest", scroll, "scrying", runner=runner)
    assert result.ok and len(result.attempts) == 2 and result.attempts[0].errors


def test_kind_specific_rules():
    scroll = ts.default_scroll(PRESETS)
    cases = [
        ({"kind": "script", "chain": []}, "a script needs script_source"),
        ({"kind": "chain", "script_source": "print(1)"}, "a chain has no script_source"),
        ({"kind": "agent", "chain": [], "orders": "x", "harness": [{"role": "run", "harness": "gpt"}]}, "harness"),
        ({"roads": []}, "give 1-4 roads"),
        ({"roads": [{"from": "forge", "event": "on_selection_change", "filter": {"match": "("}}]}, "bad regex"),
        ({"name": ""}, "needs a name"),
    ]
    for change, needle in cases:
        orc, roads, source, problems = recruiter.check({**CHAIN_ANSWER, **change}, scroll, "scrying")
        assert orc is None and any(needle in p for p in problems), (change, problems)


def test_agent_and_hybrid(tmp_path: Path):
    scroll = ts.default_scroll(PRESETS)
    agent = {"name": "Critic", "role": "reviews reports", "kind": "agent",
             "why": "Judging whether a report is convincing needs a model.", "orders": "Point out gaps.",
             "harness": [{"role": "write", "harness": "agy"}, {"role": "review", "harness": "claude"}],
             "run": {"quiet_s": 10}, "roads": [{"from": "forge", "event": "on_task_completed"}]}
    runner, _ = scripted(agent)
    result = recruiter.recruit("review reports", scroll, "loot", runner=runner)
    orc = recruiter.apply(scroll, "loot", result, tmp_path)
    assert orc.kind == "agent" and orc.run_policy["quiet_s"] == 10 and orc.harness[0]["harness"] == "agy"

    hybrid = {**agent, "name": "Warden", "kind": "hybrid", "script_source": "import sys, json\nprint(len(json.load(sys.stdin)))\n",
              "roads": [{"from": "town_hall", "event": "on_task_completed"}]}
    runner, _ = scripted(hybrid)
    result = recruiter.recruit("count, escalate when odd", scroll, "loot", runner=runner)
    orc = recruiter.apply(scroll, "loot", result, tmp_path)
    assert orc.status == "draft" and orc.script["reviewed"] is False
    path = tmp_path / orc.script["path"]
    assert path.read_text() == hybrid["script_source"] and orc.script["path"] == ".orkcraft/scripts/loot-warden.py"
    import hashlib
    assert orc.script["sha256"] == hashlib.sha256(hybrid["script_source"].encode()).hexdigest()
    assert ts.validate(scroll.to_dict()) == []


def test_runner_failure_is_reported():
    def boom(prompt):
        raise RuntimeError("Claude Code CLI not found")

    result = recruiter.recruit("x", ts.default_scroll(PRESETS), "scrying", runner=boom)
    assert not result.ok and result.error == "Claude Code CLI not found"
    assert recruiter.recruit("x", ts.default_scroll(PRESETS), "ghost").error == "unknown building 'ghost'"


def test_the_recruiter_offers_only_the_harnesses_of_this_machine():
    runner, prompts = scripted(CHAIN_ANSWER)
    recruiter.recruit("digest", ts.default_scroll(PRESETS), "scrying", runner=runner, harnesses=("claude", "codex"))
    assert '"harness":"claude|codex"' in prompts[0] and "a Claude / Codex session" in prompts[0]
    runner, prompts = scripted(CHAIN_ANSWER)
    recruiter.recruit("digest", ts.default_scroll(PRESETS), "scrying", runner=runner)
    assert '"harness":"claude|agy"' in prompts[0]
