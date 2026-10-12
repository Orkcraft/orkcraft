"""The Test bench building's own work (realm/lab_cases.py, docs/design/test-bench.md §10): a goal, its cases, what
the last test of each said against the bare AI tool, and what to change."""
from __future__ import annotations

import json

from orkcraft.realm import bench, lab_cases


def test_the_goal_says_which_metric_leads():
    assert lab_cases.metric_of("Spend fewer tokens than the bare tool") == "tokens"
    assert lab_cases.metric_of("уменьшить расход токенов") == "tokens"
    assert lab_cases.metric_of("Answer faster") == "time"
    assert lab_cases.metric_of("Better code reviews") == "quality"
    assert lab_cases.metric_of("") == "quality"


def test_the_state_is_kept_and_an_old_one_gains_new_settings(tmp_path):
    state = lab_cases.load(tmp_path)
    assert state == lab_cases.blank()
    state["goal"] = "fewer tokens"
    state["cases"]["b1"] = [lab_cases.new_case("Parse CSV", "Write a CSV parser", "b1", ["csv"])]
    lab_cases.save(tmp_path, state)
    (tmp_path / lab_cases.FILE).write_text(json.dumps({**state, "settings": {"tool": "agy"}}), encoding="utf-8")
    back = lab_cases.load(tmp_path)
    assert back["goal"] == "fewer tokens" and back["cases"]["b1"][0]["title"] == "Parse CSV"
    assert back["settings"]["tool"] == "agy" and back["settings"]["judge"] is True


def test_the_agents_cases_go_in_where_the_scheme_takes_them():
    entries = [{"id": "b1", "title": "Pool", "word": "Agent pool", "takes": "a task"},
               {"id": "b2", "title": "Board", "word": "Review board", "takes": "a topic"}]
    prompt = lab_cases.case_prompt("fewer tokens", "the Pool", entries, ["Old one"])
    assert "fewer tokens" in prompt and "`b2`" in prompt and "Old one" in prompt
    text = "Sure:\n" + json.dumps({"cases": [
        {"title": "Code", "entry": "b2", "text": "Write a parser", "expect": ["parse", ["csv", "comma"]], "why": "x"},
        {"title": "Elsewhere", "entry": "nope", "text": "Research X"},
        {"title": "Empty", "text": "  "}]})
    cases = lab_cases.parse_cases(text, entries)
    assert [(c["title"], c["entry"], c["source"]) for c in cases] == [("Code", "b2", "generated"), ("Elsewhere", "b1", "generated")]
    assert cases[0]["expect"] == ["parse", ["csv", "comma"]]
    case = lab_cases.to_case(cases[0], "the Pool", True, "fewer tokens")
    assert case.type == "chain" and case.inputs["entry"] == "b2" and case.inputs["judge"] is True
    assert case.inputs["cart"] == {"title": "Code", "text": "Write a parser"}


def test_a_run_reads_as_the_scheme_against_the_bare_tool():
    r = bench.Report(id="r1", type="chain", case="c1", tool="main", at="2026-10-10T10:00:00",
                     building=bench.Side("building", seconds=80, tokens=800, cost=0.08, passed=True, score=8),
                     bare=bench.Side("bare", seconds=100, tokens=1000, cost=0.1, passed=True, score=6))
    row = lab_cases.result_of(r)
    assert (row["time"], row["tokens"], row["quality"]) == (-0.2, -0.2, 2.0)
    worse = lab_cases.result_of(bench.Report(id="r2", type="chain", case="c2", tool="main", at="",
                                             building=bench.Side("building", seconds=10, tokens=3000, passed=False),
                                             bare=bench.Side("bare", seconds=10, tokens=1000, passed=True)))
    assert worse["tokens"] == 2.0 and worse["quality"] == -2.0
    s = lab_cases.summary({"c1": row, "c2": worse}, "tokens")
    assert s == {"cases": 2, "ahead": 1, "metric": "tokens", "mean": 0.9}
    assert lab_cases.summary({}, "time") == {"cases": 0}
    assert "tokens -20%" in lab_cases.result_line({"title": "One"}, row)


def test_the_judge_and_the_proposals_read_their_answers():
    assert lab_cases.parse_judge('{"a": 12, "b": 4.5, "why": "A is complete"}') == {"a": 10.0, "b": 4.5, "why": "A is complete"}
    assert lab_cases.parse_judge("no idea") == {}
    items = lab_cases.parse_proposals(json.dumps({"proposals": [
        {"area": "roads", "title": "Drop the Review board", "detail": "It doubles the tokens"},
        {"area": "magic", "title": "Shorter steward prompt"}, {"title": ""}]}))
    assert [(p["id"], p["area"], p["title"]) for p in items] == [("p0", "roads", "Drop the Review board"),
                                                                 ("p1", "code", "Shorter steward prompt")]


def test_the_blind_judge_scores_each_side_whatever_order_it_saw_them_in():
    from orkcraft.core import bench as core_bench
    case = lab_cases.to_case(lab_cases.new_case("T", "Write a haiku"), "x", True, "quality")
    for _ in range(6):                                     # the order is a coin: either way each side gets its own
        r = bench.Report(id="r", type="chain", case=case.id, tool="main", at="",
                         building=bench.Side("building", text="GOOD"), bare=bench.Side("bare", text="BAD"))

        def judge(prompt):
            first_good = prompt.index("GOOD") < prompt.index("BAD")
            return json.dumps({"a": 9 if first_good else 3, "b": 3 if first_good else 9})

        core_bench._judge(case, r, judge)
        assert (r.building.score, r.bare.score) == (9.0, 3.0)
    alone = bench.Report(id="r", type="chain", case=case.id, tool="main", at="", building=bench.Side("building"))
    core_bench._judge(case, alone, lambda p: '{"a": 1, "b": 1}')
    assert alone.building.score is None
