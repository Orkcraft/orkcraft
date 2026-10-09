"""🛠 From scratch (T1108 stage 5): interview → script-first blueprint → Council + sandbox → approval."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from orkcraft.realm import blueprint, fastpath, workshop

COUNT = """import json, sys
cart = json.load(sys.stdin)
words = cart["value"].split()
if not words:
    sys.exit(3)
print(json.dumps({"words": len(words), "first": words[0]}))
sys.exit(4 if len(words) > 5 else 0)
"""
BP = {"id": "word_count", "title": "Word Count", "icon": "🔢", "summary": "counts the words of a paste",
      "runtime": "python", "script": COUNT, "steward_prompt": "", "steward_why": "",
      "mocks": [{"event": "pit.text", "source": "pit", "title": "", "value": "one two three"},
                {"event": "pit.text", "source": "pit", "title": "", "value": "a b c d e f g"}]}
INTERVIEW = {"purpose": "count the words of what I paste into the pit", "layout": "card",
             "inputs": ["pit:pit.text"], "events": ["workshop.done", "workshop.failed", "workshop.alert"]}


def test_the_sandbox_runs_the_contract_in_a_bare_folder():
    runs = workshop.sandbox(COUNT, "python", BP["mocks"] + [workshop.cart("pit.text", "pit", "")])
    assert [r.outcome for r in runs] == ["done", "alert", "escalated"]
    assert json.loads(runs[0].out) == {"words": 3, "first": "one"}
    env = workshop.sandbox("import os, json; print(json.dumps(sorted(os.environ)))", "python", [workshop.cart("e", "s", "")])
    assert not [k for k in json.loads(env[0].out) if k.startswith("ORKCRAFT_")]
    bash = workshop.sandbox('read -r line; echo "got ${#line}"; exit 1', "bash", [workshop.cart("e", "s", "x")])
    assert bash[0].outcome == "failed" and bash[0].out.startswith("got")
    assert workshop.check_syntax("def x(:", "python") and workshop.check_syntax("if then fi", "bash")
    assert workshop.check_syntax(COUNT, "python") == ""
    assert workshop.shape('[{"a": 1}]')[0] == "rows" and workshop.shape('{"a": 1}')[0] == "card"
    assert workshop.shape("plain")[0] == "text"


def test_the_sandbox_stops_a_slow_script(monkeypatch):
    monkeypatch.setattr(workshop, "SANDBOX_TIMEOUT_S", 1)
    r = workshop.sandbox("import time; time.sleep(5)", "python", [workshop.cart("e", "s", "")])[0]
    assert r.code == -1 and "no answer" in r.err


def test_the_builder_retries_with_its_problems_and_the_operators_note():
    prompts = []
    answers = iter(["no json here", json.dumps(dict(BP, steward_prompt="summarise it")), json.dumps(BP)])

    def runner(prompt):
        prompts.append(prompt)
        return next(answers), 0.01

    result = blueprint.build(INTERVIEW, {"pit"}, runner, feedback="count lines too")
    assert result.ok and len(result.attempts) == 3 and result.cost_usd == pytest.approx(0.03)
    assert "ONE JSON object" in prompts[1] and "steward_why" in prompts[2] and "count lines too" in prompts[0]
    bp = result.blueprint
    assert bp["layout"] == "card" and bp["inputs"] == ["pit:pit.text"] and len(bp["mocks"]) == 2
    spec = blueprint.to_spec(bp)
    assert spec["type"] == "workshop" and spec["config"] == {"runtime": "python", "layout": "card",
                                                              "inputs": ["pit:pit.text"]}
    assert blueprint.problems(dict(BP, id="pit"), {"pit"}) == ["id: pit is taken — pick another"]
    failed = blueprint.build(INTERVIEW, set(), lambda p: (_ for _ in ()).throw(RuntimeError("no claude")))
    assert not failed.ok and "no claude" in failed.error


def test_the_council_blocks_a_dangerous_script_before_the_sandbox(tmp_path: Path):
    spec = blueprint.to_spec(blueprint.normalise(dict(BP, script="import os\nos.system('sudo rm -rf /')\n"), INTERVIEW))
    v = fastpath.review(fastpath.Subject("building", "word_count", spec, "import os\nos.system('sudo rm -rf /')\n"), tmp_path)
    assert v.blocked and any("sudo" in n.text for n in v.notes)


async def _wait(pilot, cond, n: int = 80) -> bool:
    for _ in range(n):
        await pilot.pause(0.05)
        if cond():
            return True
    return False


READY = {"ready": True, "purpose": "Count the words of every paste; alert on long ones.",
         "views": [{"name": "Counter card", "layout": "card", "preview": "words 12\nfirst release"},
                   {"name": "Run log", "layout": "log", "preview": "✓ 05:01 12 words"},
                   {"name": "Word table", "layout": "table", "preview": "| word | n |"}],
         "inputs": ["pit:pit.text"], "events": ["workshop.done", "workshop.alert"]}


def test_the_builder_asks_then_offers_three_views():
    answers = iter([json.dumps({"questions": ["Which pastes?", "Alert when?"]}),
                    json.dumps(dict(READY, views=READY["views"][:2])),           # two views: rejected
                    json.dumps(READY)])
    prompts = []

    def runner(p):
        prompts.append(p)
        return next(answers), 0.001

    sources = [("pit:pit.text", "The Pit → text pasted")]
    first = blueprint.talk([("builder", "What?"), ("operator", "count words")], sources, runner)
    assert first.questions == ["Which pastes?", "Alert when?"] and not first.ready
    assert "operator: count words" in prompts[0] and "pit:pit.text" in prompts[0]
    second = blueprint.talk([("operator", "all of them; over 400 words")], sources, runner)
    assert second.ready and [v["layout"] for v in second.views] == ["card", "log", "table"]
    assert "exactly three" in prompts[2]
    iv = blueprint.interview_from(second, 2, ["pit:pit.text"], ["workshop.done"], [("operator", "x")])
    assert iv["layout"] == "table" and "Word table" in iv["purpose"] and iv["history"] == [("operator", "x")]
    bad = blueprint.talk([], sources, lambda p: (json.dumps(dict(READY, inputs=["mail:x"])), 0.0))
    assert bad.error and "inputs" in bad.error
