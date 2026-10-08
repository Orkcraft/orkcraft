"""⛏️ The Mine's research, the pure part (realm/research.py, docs/design/mine.md §5): who a run's mind is, which
sources are one text copied, when a finding is confirmed, and the report."""
from __future__ import annotations

import json

from orkcraft.realm import research


def _f(mind: str, claim: str, *urls: str, sub: int = 1, quote: str = "", tool: str = "") -> dict:
    return {"mind": mind, "tool": tool or mind, "sub": sub, "claim": claim, "round": 0, "sure": "",
            "sources": [{"url": u, "title": "", "date": "", "quote": quote} for u in urls]}


def _r(findings: list[dict], groups: list[list[int]], conflicts=()) -> dict:
    r = {"question": "Q?", "plan": [{"q": "first", "answer_if": ""}, {"q": "second", "answer_if": ""}],
         "findings": findings, "groups": [], "conflicts": [], "tools": ["claude", "codex"], "per_tool": {}}
    research.regroup(r, groups, list(conflicts))
    return r


def test_a_mind_is_its_model_s_family_not_its_tool():
    assert research.mind("hermes", "anthropic/claude-sonnet-5") == "anthropic"      # the same mind as Claude Code
    assert research.mind("claude") == research.mind("pi", "claude-haiku-5") == "anthropic"
    assert research.mind("codex") == research.mind("cursor", "gpt-5.5") == "openai"
    assert research.mind("hermes") == "hermes"                                      # not known: its own
    assert research.mind("agy") == research.mind("hermes", "gemini-3-pro") == "google"


def test_sites_and_copies():
    assert research.domain("https://docs.python.org/3/") == "python.org"
    assert research.domain("https://news.bbc.co.uk/a") == "bbc.co.uk"
    assert research.domain("not a url") == ""
    assert research.canonical("https://www.a.com/x/?utm_source=t#top") == research.canonical("http://a.com/x")
    quote = "The yearly plan costs ten times the monthly one, two months are free."
    copied = [{"url": "https://a.com/1", "quote": quote}, {"url": "https://b.com/2", "quote": quote},
              {"url": "https://www.a.com/1/", "quote": ""}, {"url": "https://c.com/3", "quote": "short"}]
    assert [s["url"] for s in research.independent(copied)] == ["https://a.com/1", "https://c.com/3"]


def test_confirmed_needs_two_minds_and_two_sites():
    r = _r([_f("anthropic", "A", "https://a.com/x"), _f("openai", "A again", "https://b.org/y"),
            _f("anthropic", "B", "https://a.com/1"), _f("anthropic", "B too", "https://c.com/2", tool="hermes"),
            _f("openai", "C", "https://a.com/x"), _f("anthropic", "C too", "https://a.com/x")],
           [[0, 1], [2, 3], [4, 5]])
    research.check(r)
    assert [g["state"] for g in r["groups"]] == ["confirmed", "single", "single"]
    # B: Claude Code and Hermes on a Claude model are one mind; C: one page


def test_a_conflict_is_disputed_until_the_person_decides():
    r = _r([_f("anthropic", "It ends in March", "https://a.com"), _f("openai", "It ends in May", "https://b.com")],
           [[0], [1]], [(0, 1)])
    research.check(r)
    assert [g["state"] for g in r["groups"]] == ["disputed", "disputed"] and len(research.disputes(r)) == 1
    r["groups"][0]["decided"], r["groups"][1]["decided"] = "accept", "reject"
    research.check(r)
    assert [g["state"] for g in r["groups"]] == ["decided", "dropped"] and research.disputes(r) == []
    assert research.counts(r) == {"confirmed": 1, "disputed": 0, "single": 0}


def test_answers_are_read_and_a_claim_without_a_source_is_dropped():
    answer = "Here you go:\n```json\n" + json.dumps({"findings": [
        {"sub": 9, "claim": "Has a source", "sources": [{"url": "https://a.com/x", "quote": "q"}], "sure": "high"},
        {"sub": 1, "claim": "Has none", "sources": []},
        {"sub": 1, "claim": "Not a web page", "sources": ["file:///etc/passwd"]}]}) + "\n```"
    found = research.parse_findings(answer, "anthropic", "claude", plan_size=2)
    assert [(f["claim"], f["sub"]) for f in found] == [("Has a source", 2)]
    assert research.parse_plan("nothing useful", "The question") == [{"q": "The question", "answer_if": ""}]
    groups, conflicts = research.parse_groups('{"groups": [[1, 3], [9]], "conflicts": [[0, 1], [0, 0]]}', 3)
    assert groups == [[0, 2], [1]] and conflicts == []          # the empty group goes; a lone finding gets its own
    assert research.parse_groups("no json", 3) is None
    assert research.group_by_rules([_f("a", "The plan is two months free"), _f("b", "the plan is two months free!"),
                                    _f("c", "Something else entirely")]) == [[0, 1], [2]]


def test_a_debate_withdraws_a_side():
    r = _r([_f("anthropic", "March", "https://a.com"), _f("openai", "May", "https://b.com"),
            _f("openai", "March too", "https://c.com")], [[0, 2], [1]], [(0, 1)])
    research.check(r)
    sides = [r["groups"][0], r["groups"][1]]
    research.apply_verdicts(r, sides, [{"claim": 2, "verdict": "withdraw", "why": "", "sources": []}], "openai", "codex", 2)
    research.check(r)
    assert r["groups"][0]["state"] == "confirmed" and r["groups"][1]["state"] == "dropped" and r["conflicts"] == []


def test_the_report_marks_each_finding_and_says_what_changed():
    r = _r([_f("anthropic", "A", "https://a.com/x"), _f("openai", "A", "https://b.org/y"),
            _f("anthropic", "B", "https://c.com", sub=2), _f("openai", "not B", "https://d.com", sub=2)],
           [[0, 1], [2], [3]], [(1, 2)])
    r.update(round=1, cost=1.2, per_tool={"claude": {"mind": "anthropic", "cost": 0.7, "error": ""}})
    research.check(r)
    md = research.report(r)
    assert "✓ A [1] [2]" in md and "## Disputed" in md and "against: not B" in md and "$1.20" in md
    assert "1. [a.com](https://a.com/x)" in md
    old = json.loads(json.dumps(r))
    r["groups"][1]["decided"], r["groups"][2]["decided"] = "accept", "reject"
    research.check(r)
    assert research.changes(old, r) == ["Disputed → Confirmed by you: B"]
    low, high = research.estimate(3, 3)
    assert 0 < low < high
