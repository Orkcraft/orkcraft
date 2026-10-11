"""What the Test bench's runs mean, in words (realm/explain.py): a sentence a case, where the extra went, what to change."""
from __future__ import annotations

from orkcraft.realm import bench, explain


def _r(n: int, b: tuple, t: tuple, missed: str = "") -> bench.Report:
    building = bench.Side("building", seconds=b[0], tokens=b[1], passed=b[2],
                          checks=[{"name": missed, "ok": False}] if missed else [])
    return bench.Report(f"r{n}", "watchtower", "c", building=building, bare=bench.Side("bare", seconds=t[0], tokens=t[1],
                                                                                         passed=t[2]))


def _calls(steps: list[tuple[str, float, int]], bare: tuple[float, int] = (8.0, 1000)) -> list[dict]:
    return [{"side": "building", "purpose": p, "seconds": s, "prompt_chars": c} for p, s, c in steps] + \
        [{"side": "bare", "purpose": "work", "seconds": bare[0], "prompt_chars": bare[1]}]


def test_as_good_and_about_as_costly_reads_as_one_plain_sentence():
    s = explain.story("Sort the inbox", [_r(0, (10, 1000, True), (10, 1000, True))])
    assert s["status"] == "good" and s["summary"] == "It does as well as the AI tool alone, about as fast and about the same tokens."
    assert s["changes"] == []


def test_worse_than_the_tool_alone_says_what_it_missed_and_to_fix_that_first():
    runs = [_r(n, (10, 1000, n != 1), (10, 1000, True), missed="#5 importance high" if n == 1 else "") for n in range(3)]
    s = explain.story("Sort the inbox", runs)
    assert s["status"] == "bad" and "worse than the AI tool alone (2 of 3 runs, the AI tool 3 of 3)" in s["summary"]
    assert "It missed: #5 importance high." in s["details"]
    assert s["changes"][0]["what"] == "Make it get the result right first" and "#5 importance high" in s["changes"][0]["why"]


def test_extra_steps_and_long_prompts_are_where_the_time_went():
    runs = [_r(0, (20, 3000, True), (10, 1000, True))]
    calls = {"r0": _calls([("sort", 6.0, 1500), ("work", 9.0, 2500), ("review", 4.0, 1000)])}
    s = explain.story("Plan a to-do", runs, calls)
    assert s["status"] == "watch" and "100% slower and 200% more tokens" in s["summary"]
    assert any("3 times where the AI tool alone answers in 1" in d and "sorting what came in" in d for d in s["details"])
    whats = [c["what"] for c in s["changes"]]
    assert "Skip sorting what came in on tasks like this one" in whats and "Shorten what it sends the AI tool" in whats
    together = explain.changes([s, explain.story("Another", runs, calls)],
                               [{"what": "Cache the wiki map", "why": "it is read on every task", "who": "Architect"}])
    assert together[0]["cases"] == ["Plan a to-do", "Another"] and together[-1]["from"] == "Architect"


def test_time_outside_the_ai_tool_is_named():
    s = explain.story("x", [_r(0, (20, 1000, True), (10, 1000, True))], {"r0": _calls([("work", 8.0, 1000)])})
    assert any("12 s of its 20 s go outside the AI tool" in d for d in s["details"])
    assert "Cut the waiting around the AI tool" in [c["what"] for c in s["changes"]]


def test_a_case_that_did_not_run_says_why():
    r = bench.Report("r", "x", "c", building=bench.Side("building", error="agy is not logged in"))
    s = explain.story("x", [r])
    assert s["status"] == "bad" and "agy is not logged in" in s["summary"]
