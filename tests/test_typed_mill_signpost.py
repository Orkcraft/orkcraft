"""⚙️ The Mill and 🚏 the Signpost (T1107 stage 3): deterministic steps, rule-based routes."""
from __future__ import annotations

import json
import sys


from orkcraft.realm import catalog, mill, roads, signpost
from orkcraft.realm.pipes import Payload

LOG = "INFO start\nERROR db timeout id=17\nINFO ok\nERROR disk full id=42\nERROR db timeout id=17\n"


def test_mill_steps():
    out, err = mill.run(["grep: ERROR", "dedupe", "extract: id = id=(\\d+)", "pick: id", "to_json"], LOG)
    assert not err and json.loads(out) == [{"id": "17"}, {"id": "42"}]
    out, _ = mill.run(["csv", "filter: role eq admin", "template: {name} <{mail}>", "join: , "],
                      "name,mail,role\nAnn,a@x,admin\nBob,b@x,user\nCid,c@x,admin\n")
    assert out == "Ann <a@x>, Cid <c@x>"
    assert mill.run(["json", "count"], '[1, 2, 3]')[0] == '{"count": 3}'
    assert mill.run(["replace: (\\d+) => #\\1", "lower"], "Ticket 42 DONE")[0] == "ticket #42 done"
    assert mill.run(["lines", "drop: INFO", "sort: line desc", "limit: 1", "join"], LOG)[0] == "ERROR disk full id=42"
    script = f"{sys.executable} -c \"import sys; print(sys.stdin.read().count('ERROR'))\""
    assert mill.run([f"script: {script}"], LOG)[0] == "3"
    out, err = mill.run(["grep: ERROR", "json"], LOG)
    assert err.startswith("step 2 (json)") and "ERROR" in out          # the value before the failing step
    assert mill.check(["grep: (", "nonsense"]) and mill.check(["lines", "grep: x"]) == []
    bad = {"id": "m", "title": "M", "icon": "⚙️", "orc": {"name": "Miller"}, "type": "mill", "config": {"steps": ["frobnicate"]}}
    assert any("unknown step" in e for e in catalog.validate(bad))


def test_mill_fixed_edges():
    assert mill.run(["join: → "], "a\nb")[0] == "a→ b"                             # not mangled by unicode_escape
    assert mill.run(['join: " | "'], "a\nb")[0] == "a | b"                         # quotes keep the spaces
    assert mill.run(["join: \\t"], "a\nb")[0] == "a\tb"
    out, err = mill.run(["replace: a"], "banana")
    assert err.startswith("step 1") and "=>" in err and out == "banana"            # no silent delete
    assert mill.run(["replace: a => "], "banana")[0] == "bnn"                       # an empty <with> deletes
    assert mill.run(['replace: , => " - "'], "a,b")[0] == "a - b"
    assert mill.check(["extract: foo", "replace: x", "filter: n gt", "filter: n bigger 2", "limit: x", "sort:"]) \
        and len(mill.check(["extract: foo", "replace: x", "filter: n bigger 2", "limit: x", "sort:"])) == 5
    out, err = mill.run(["lines", "extract: foo"], "abc")
    assert "extract: <field> = <regex>" in err
    out, err = mill.run(["csv", "filter: n bigger 2"], "n\n1\n3")
    assert "filter:" in err


def test_mill_numbers_and_dates():
    csv_text = "n,day\n10,2026-03-01\n9,2026-01-15\n100,2025-12-31\n,2026-02-01\n"
    out, _ = mill.run(["csv", "sort: n", "pick: n", "to_json"], csv_text)
    assert [r["n"] for r in json.loads(out)] == ["9", "10", "100", ""]              # numbers, the empty last
    out, _ = mill.run(["csv", "sort: n desc text", "pick: n", "to_json"], csv_text)
    assert [r["n"] for r in json.loads(out)][:3] == ["9", "100", "10"]              # text when asked
    out, _ = mill.run(["csv", "filter: n gt 9", "count"], csv_text)
    assert out == '{"count": 2}'
    out, _ = mill.run(["csv", "filter: n le 10", "count"], csv_text)
    assert out == '{"count": 2}'
    out, _ = mill.run(["csv", "filter: day ge 2026-01-01", "filter: day lt 2026-03-01", "pick: day", "to_json"], csv_text)
    assert [r["day"] for r in json.loads(out)] == ["2026-01-15", "2026-02-01"]
    out, _ = mill.run(["lines", "sort: n desc", "limit: 2", "pick: n", "to_json"], "\n".join("x" * i for i in range(1, 12)))
    assert [r["n"] for r in json.loads(out)] == [11, 10]


def test_mill_agent_steps_and_flat_map():
    seen = []

    def agent(ask, text):
        seen.append((ask, text))
        return text.upper()

    r = mill.run_full(["grep: ERROR", "agent: shout it", "lines", "pick: line"], LOG, agent=agent)
    assert not r.error and r.agent_steps == 1 and seen[0][0] == "shout it"
    assert mill.items(r.records)[0] == '{"line": "ERROR DB TIMEOUT ID=17"}' and len(r.records) == 3
    assert mill.run_full(["trim"], "a").records is None                            # text: no flat map
    r = mill.run_full([f"script: {sys.executable} -c 'import sys; sys.exit(3)' || agent: count the lines"], "a\nb",
                      agent=lambda ask, text: str(len(text.splitlines())))
    assert not r.error and r.text == "2" and r.agent_steps == 1                     # the script failed, the agent did it
    r = mill.run_full([f"script: {sys.executable} -c 'import sys; sys.exit(3)' || agent: x"], "a",
                      agent=lambda ask, text: (_ for _ in ()).throw(RuntimeError("no claude")))
    assert "the script failed" in r.error and "no claude" in r.error
    assert mill.check(["agent:", "script: make || agent:"]) and mill.check(["agent: fix it", "script: make || agent: do it"]) == []
    assert mill.model_steps(["agent: a", "script: x || agent: b", "script: y", "grep: agent"]) == 2
    assert "## Input\n\nhello" in mill.agent_prompt("do", "hello")


def test_mill_scripts_see_a_clean_environment(monkeypatch):
    monkeypatch.setenv("ORK_SECRET_TOKEN", "s3cret")
    monkeypatch.setenv("ORK_ALLOWED", "yes")
    show = f"script: {sys.executable} -c \"import os; print(os.environ.get('ORK_SECRET_TOKEN'), os.environ.get('ORK_ALLOWED'))\""
    assert mill.run([show], "")[0] == "None None"
    assert mill.run([show], "", env=["ORK_ALLOWED"])[0] == "None yes"


def P(value="", title="", kind="text", source="pit", mode="pit.text"):
    return Payload(kind, value, source, mode, title)


def test_signpost_rules():
    rules, problems = signpost.rules_of(["bugs: matches (?i)traceback|error", "links: kind text", "deploys: env == prod",
                                      "other: else", "BAD RULE: x", "x: frob it"])
    assert [r.route for r in rules] == ["bugs", "links", "deploys", "other"] and len(problems) == 2
    assert signpost.route(rules, P("Traceback (most recent call last)")) == "bugs"
    assert signpost.route(rules, P("https://x", kind="text")) == "links"
    assert signpost.route(rules[2:], P('{"env": "prod"}', kind="file")) == "deploys"
    assert signpost.route(rules[2:3], P('{"env": "dev"}')) is None
    assert signpost.routes(["a: else", "b: kind node", "a: contains x"]) == ["a", "b"]
    assert roads.passes({"route": ["bugs"]}, Payload("text", "x", "t", "signpost.routed", "bugs"), {})[0]
    assert not roads.passes({"route": ["bugs"]}, Payload("text", "x", "t", "signpost.routed", "links"), {})[0]


def test_a_signpost_rule_may_name_a_kind_of_work_and_never_raises_one():
    """docs/design/barracks-flows.md §4: `route, want: condition`. On a cart with no kind the rule's is set; on a
    cart with one, the two give the one whose path may do least."""
    rules, problems = signpost.rules_of(["bugs, change: contains traceback", "mail, Reply: else", "x, frob: else"])
    assert [(r.route, r.want) for r in rules] == [("bugs", "change"), ("mail", "reply")]
    assert problems == ["rule 3: kind of work 'frob': change, reply, doc, routine, know"]
    assert signpost.rules_of(["a: contains x, y"])[0][0] == signpost.Rule("a", "contains", value="x, y")
    bug, plain = P("a Traceback"), P("hello")
    assert signpost.want(signpost.pick(rules, bug), bug) == "change"
    assert signpost.want(signpost.pick(rules, plain), plain) == "reply"
    asked = Payload("text", "a Traceback", "t", "e", "", want="reply")       # came as a reply: never a change
    assert signpost.want(signpost.pick(rules, asked), asked) == "reply"
    doc = Payload("text", "hi", "t", "e", "", want="doc")                    # came as a document: a reply does less
    assert signpost.want(signpost.pick(rules, doc), doc) == "reply"
    assert signpost.want(signpost.pick(signpost.rules_of(["a: else"])[0], doc), doc) == "doc"   # no kind named: kept
    assert signpost.want(None, plain) == ""
