"""👎 → a case (realm/regressions.py): what came into a building, what it made and what the person said, kept as a
test case its Test bench takes in."""
from __future__ import annotations

from orkcraft.core import buildings as core_buildings
from orkcraft.core import delivery
from orkcraft.realm import pipes, regressions
from tests.test_gui_bench import _raised, _road, asked, host  # noqa: F401  (fixtures)


def test_a_dislike_keeps_what_came_in_as_a_case_of_the_building(tmp_path):
    assert regressions.from_dislike(tmp_path, "pool", "wrong") is None          # nothing came in: nothing to run
    regressions.record_input(tmp_path, "pool", pipes.TEXT, "Fix the CSV export: it gives a 500", "tower", "CSV export")
    assert regressions.from_dislike(tmp_path, "pool", "it blamed the user", kind="inputs") is None   # the suppliers'
    case = regressions.from_dislike(tmp_path, "pool", "it changed the tests instead", output="I edited test_export.py")
    assert case["text"] == "Fix the CSV export: it gives a 500" and case["entry"] == "pool" and case["source"] == "dislike"
    assert case["title"].startswith("👎 ") and "it changed the tests instead" in case["title"]
    assert "What it made then: I edited test_export.py" in case["why"]
    assert regressions.cases(tmp_path, "pool") == [case]


def test_a_test_bench_takes_in_the_dislikes_of_what_it_tests_once(host):
    lab, pool = _raised(host, "lab"), _raised(host, "barracks", worktrees=False)
    _road(host, pool, lab, "pool.done")
    payload = pipes.Payload(pipes.TEXT, "Write a slugify with tests", "pit", "push", title="slugify")
    delivery.deliver(host.town, pool, payload)
    core_buildings.dislike(host.town, pool, "logic", "no tests written")
    d = host.detail(lab)["data"]
    mine = [c for c in d["cases"] if c["source"] == "dislike"]
    assert len(mine) == 1 and mine[0]["text"] == "Write a slugify with tests" and "no tests written" in mine[0]["why"]
    assert len([c for c in host.detail(lab)["data"]["cases"] if c["source"] == "dislike"]) == 1     # once
