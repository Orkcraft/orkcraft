"""The Barracks' shipped Test bench cases hold: each check fails on the case as given and passes on a known
solution (tests/bench_solutions/<case>/, copied into its `src/`), and each case is sorted on the path its level says."""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from orkcraft.realm import bench, plans

SOLUTIONS = Path(__file__).parent / "bench_solutions"
CASES = bench.cases(Path("/nonexistent"), "barracks")


def test_every_case_has_a_level_and_a_solution():
    assert {c.level for c in CASES} == {"simple", "medium", "parallel"}
    assert sorted(c.id for c in CASES) == sorted(p.name for p in SOLUTIONS.iterdir() if p.is_dir())
    assert min(sum(c.level == lvl for c in CASES) for lvl in ("simple", "medium", "parallel")) >= 5


@pytest.mark.parametrize("case", CASES, ids=[c.id for c in CASES])
def test_the_level_is_the_path_the_rules_give(case):
    short = plans.clearly_simple(case.title, case.task)
    assert short == (case.level == "simple")
    if case.level == "parallel":
        assert len(plans.STEP.findall(case.task)) >= 3


@pytest.mark.parametrize("case", CASES, ids=[c.id for c in CASES])
def test_the_check_fails_as_given_and_passes_on_a_solution(case, tmp_path):
    project = tmp_path / case.id
    bench.make_project(case, tmp_path, project)
    assert bench.check(case, project)[0] is False
    for f in (SOLUTIONS / case.id).glob("*.py"):
        shutil.copy(f, project / "src" / f.name)
    passed, tail = bench.check(case, project)
    assert passed, tail
