"""Code over thinking (docs/design/steward-listens.md §2a, stage 4): the steward turns its own road rules into
code — a chain replayed at once, a script or a hybrid replayed only once reviewed — keeps the rule's words as
the way back, and hands an agent on its own tool to itself."""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

from orkcraft import scroll as ts
from orkcraft.realm import roads, steward

PRESETS = {
    "forge": {"title": "Forge", "icon": "⚒️", "orc": "Smith", "role": "kanban", "category": "core"},
    "scrying": {"title": "Scrying Spire", "icon": "🔮", "orc": "Shaman", "role": "preview", "category": "core"},
}
NOW = dt.datetime(2026, 10, 7, 5, 30)
TITLES = ["Ship login", "Plan the auth migration", "Fix calendar", "Docs", "Cache warmup", "CI"]
RULE = "One line per finished task: its id and title."


def ruled(tmp_path: Path, cost: float = 0.05) -> ts.TownScroll:
    scroll = ts.default_scroll(PRESETS)
    ts.add_handler(scroll, "scrying", "Digest", kind="steward", orders=RULE)
    ts.subscribe(scroll, "scrying", "forge", "on_selection_change", handler="digest")
    path = roads.examples_file(tmp_path, "scrying", "digest")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        for i, title in enumerate(TITLES):
            nid = f"T10{i:02d}"
            f.write(json.dumps({"ts": (NOW - dt.timedelta(days=1)).isoformat(), "cost_usd": cost,
                                "inputs": [{"road": "forge-selection", "id": nid, "title": title, "value": nid}],
                                "output": f"✅ {nid} — {title}"}) + "\n")
    return scroll


def answering(*answers):
    prompts: list[str] = []

    def runner(prompt):
        prompts.append(prompt)
        return json.dumps(answers[min(len(prompts), len(answers)) - 1]), 0.02
    return runner, prompts


def test_a_rule_that_answers_alike_is_found_with_its_spend_and_made_a_chain(tmp_path: Path):
    scroll = ruled(tmp_path)
    runner, prompts = answering({"proposals": [{"type": "demote", "orc": "digest", "why": "a template does it",
                                                "chain": [{"op": "template", "md": "✅ {id} — {title}"}]}]})
    report = steward.watch(tmp_path, scroll, "scrying", sessions=[], runner=runner, now=NOW)
    [repeat] = [f for f in report.findings if f.kind == "repeats"]
    assert "a road rule" in repeat.summary and "$0.30/week" in repeat.summary
    assert "digest: 6 runs, $0.30" in prompts[0] and "Code over thinking" in prompts[0]
    [p] = report.proposals
    assert p.ready and p.replay.score == 1.0
    assert p.to_dict()["replay"]["ready"] is True                    # the night self-applies only a ready chain
    assert steward.apply_proposal(scroll, "scrying", p) == "Digest demoted to a chain"
    digest = scroll.building("scrying").garrison.handler("digest")
    assert digest.kind == "chain" and digest.orders == RULE and not digest.uses_model    # the words stay: the way back
    assert ts.validate(scroll.to_dict()) == []


def test_code_that_keeps_failing_goes_back_to_its_rule_without_a_model(tmp_path: Path):
    scroll = ruled(tmp_path)
    ts.update_orc(scroll, "scrying", "digest", kind="chain", chain=[{"op": "count"}])
    runs = [roads.HandlerRun("scrying", "digest", "chain", str(i), 0.0, outcome="error") for i in range(4)]
    asked: list[str] = []
    report = steward.watch(tmp_path, scroll, "scrying", runs=runs, sessions=[], now=NOW,
                           runner=lambda p: (asked.append(p), ("{}", None))[1])
    assert [f.kind for f in report.findings if f.kind == "code_failing"] == ["code_failing"]
    back = next(p for p in report.proposals if p.type == "rule")
    steward.apply_proposal(scroll, "scrying", back)
    digest = scroll.building("scrying").garrison.handler("digest")
    assert (digest.kind, digest.chain, digest.orders) == ("steward", [], RULE)


def test_an_agent_on_the_stewards_own_tool_is_proposed_to_hand_over_for_free(tmp_path: Path):
    scroll = ts.default_scroll(PRESETS)
    ts.add_handler(scroll, "scrying", "Mailman", orders="Summarise each letter.")      # one step, the main tool
    ts.add_handler(scroll, "scrying", "Pair", orders="Write, then review.",
                   harness=[{"role": "write", "harness": "agy"}, {"role": "review", "harness": "claude"}])
    asked: list[str] = []
    report = steward.watch(tmp_path, scroll, "scrying", sessions=[], now=NOW,
                           runner=lambda p: (asked.append(p), ("{}", None))[1])
    assert [f.orc_id for f in report.findings if f.kind == "hand"] == ["mailman"]       # a pipeline keeps its tools
    [hand] = [p for p in report.proposals if p.type == "hand"]
    assert report.errors                                    # the model's answer was refused: the free move stays
    assert steward.apply_proposal(scroll, "scrying", hand) == "Mailman handed to the steward as a road rule"
    assert scroll.building("scrying").garrison.handler("mailman").kind == "steward"


def test_a_script_is_never_run_before_review_then_replayed(tmp_path: Path):
    scroll = ruled(tmp_path)
    source = ("import json, sys\nfor r in json.load(sys.stdin):\n"
              "    print(f\"✅ {r['id']} — {r['title']}\")\n")
    runner, _ = answering({"proposals": [{"type": "demote", "orc": "digest", "why": "string work", "script": source}]})
    report = steward.watch(tmp_path, scroll, "scrying", sessions=[], runner=runner, now=NOW)
    [p] = report.proposals
    assert p.replay is None and p.ready and p.data["reviewed"] is False             # not run yet
    rep = steward.replay_script(source, roads.read_examples(tmp_path, "scrying", "digest"), tmp_path)
    assert rep.ready and rep.exact == 6
    what = steward.apply_proposal(scroll, "scrying", {**p.to_dict(), "reviewed": True})
    digest = scroll.building("scrying").garrison.handler("digest")
    assert what == "Digest turned into a script" and digest.kind == "script" and digest.script["reviewed"] is True
    assert digest.script["path"] == steward.script_path("scrying", "digest") and digest.orders == RULE
    bad, _ = answering({"proposals": [{"type": "demote", "orc": "digest", "why": "w", "script": "def (:"}]})
    assert "does not parse" in " ".join(steward.watch(tmp_path, ruled(tmp_path), "scrying", sessions=[],
                                                      runner=bad, now=NOW, max_attempts=1).errors)


def test_a_hybrids_replay_leaves_out_what_it_hands_to_the_steward(tmp_path: Path):
    ruled(tmp_path)
    source = ("import json, sys\nr = json.load(sys.stdin)[0]\n"
              "if r['title'] == 'Docs':\n    sys.exit(3)\nprint(f\"✅ {r['id']} — {r['title']}\")\n")
    rep = steward.replay_script(source, roads.read_examples(tmp_path, "scrying", "digest"), tmp_path, hybrid=True)
    assert (rep.escalated, rep.total, rep.exact) == (1, 5, 5) and rep.ready
    all_out = "import sys\nsys.exit(3)\n"
    assert not steward.replay_script(all_out, roads.read_examples(tmp_path, "scrying", "digest"), tmp_path,
                                     hybrid=True).ready
