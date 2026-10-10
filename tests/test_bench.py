"""The Test bench (docs/design/test-bench.md): a case's copy of the project, the bare AI tool's side, the building's
side in a town of its own, the report, `orkcraft bench`. AI tools are faked; git and the checks are real."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from orkcraft import cli
from orkcraft.core import bench as building_bench
from orkcraft.core.workers.barracks import BarracksWorker
from orkcraft.realm import bench
from tests.pool_fakes import Steward

SLUGIFY = '''"""Text helpers."""
import re
import unicodedata


def words(text: str) -> list[str]:
    return text.split()


def slugify(text: str) -> str:
    plain = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", plain.lower()).strip("-")
'''


def _git(cwd: Path, *args: str) -> str:
    done = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    assert done.returncode == 0, done.stderr + done.stdout
    return done.stdout.strip()


def _slugify_case(root: Path) -> bench.Case:
    c = bench.case(root, "barracks", "slugify")
    assert c is not None
    c.check = c.check.replace("python -m pytest", f"{sys.executable} -m pytest -p no:cacheprovider")   # this pytest
    return c


def _solve(workdir: Path, commit: bool) -> None:
    (Path(workdir) / "src" / "text.py").write_text(SLUGIFY, encoding="utf-8")
    if commit and _git(workdir, "status", "--porcelain"):
        _git(workdir, "add", "-A")
        _git(workdir, "-c", "user.name=Ork", "-c", "user.email=ork@x", "commit", "-q", "-m", "slugify")


# -- cases ----------------------------------------------------------------------------------------------------

def test_the_shipped_cases_carry_their_project_and_a_check(tmp_path):
    found = bench.cases(tmp_path, "barracks")
    assert [c.id for c in found][:2] == ["slugify", "inventory"]
    assert all(c.files and c.check and c.type == "barracks" and c.reviewed for c in found)
    assert bench.cases(tmp_path, "no-such-type") == []


def test_a_towns_own_case_is_added_and_wins_on_the_same_id(tmp_path):
    folder = tmp_path / bench.BENCH / "barracks"
    folder.mkdir(parents=True)
    (folder / "slugify.json").write_text(json.dumps({"title": "Mine", "task": "Do it", "check": "true"}))
    (folder / "fresh.json").write_text(json.dumps({"title": "New", "task": "Write it", "reviewed": False}))
    (folder / "broken.json").write_text("{not json")
    found = {c.id: c for c in bench.cases(tmp_path, "barracks")}
    assert found["slugify"].title == "Mine" and found["slugify"].files == {}
    assert found["fresh"].reviewed is False and "broken" not in found


# -- the copy of a project ------------------------------------------------------------------------------------

def test_a_cases_project_is_committed_and_has_no_remote(tmp_path):
    c = _slugify_case(tmp_path)
    base = bench.make_project(c, tmp_path, tmp_path / "copy")
    assert base == _git(tmp_path / "copy", "rev-parse", "HEAD")
    assert (tmp_path / "copy" / "tests" / "test_text.py").is_file()
    assert _git(tmp_path / "copy", "remote") == ""
    assert ".orkcraft/" in (tmp_path / "copy" / ".gitignore").read_text()


def test_a_case_without_files_runs_on_a_clone_of_the_town_without_its_origin(fake_repo, tmp_path):
    _git(fake_repo, "remote", "add", "origin", "https://example.invalid/project.git")
    c = bench.Case(id="here", type="barracks", title="Here", task="Change the README")
    bench.make_project(c, fake_repo, tmp_path / "runs" / "copy")
    assert (tmp_path / "runs" / "copy" / "src" / "app.py").is_file()
    assert _git(tmp_path / "runs" / "copy", "remote") == ""


def test_a_case_file_may_not_leave_its_project(tmp_path):
    c = bench.Case(id="out", type="barracks", title="Out", task="x", files={"../escape.txt": "no"})
    with pytest.raises(ValueError):
        bench.make_project(c, tmp_path, tmp_path / "copy")
    assert not (tmp_path / "escape.txt").exists()


# -- the bare side ----------------------------------------------------------------------------------------------

def test_the_bare_tool_gets_only_the_task_and_its_result_is_checked(tmp_path):
    c = _slugify_case(tmp_path)
    bench.make_project(c, tmp_path, tmp_path / "bare")
    seen = []

    def runner(tool, prompt, workdir, cancel, model):
        seen.append((tool, prompt, model))
        _solve(workdir, commit=False)
        return "done", 0.12, 3400, "s1"

    side = bench.bare(c, tmp_path / "bare", "claude", "laborer", runner=runner)
    assert seen == [("claude", c.task, "haiku")]
    assert (side.passed, side.cost, side.tokens, side.error) == (True, 0.12, 3400, "")
    assert side.files == ["src/text.py"] and side.lines > 0


def test_a_bare_result_that_changed_the_tests_does_not_pass(tmp_path):
    c = _slugify_case(tmp_path)
    bench.make_project(c, tmp_path, tmp_path / "bare")

    def runner(tool, prompt, workdir, cancel, model):
        (Path(workdir) / "tests" / "test_text.py").write_text("def test_nothing():\n    pass\n")
        return "done", 0.0, 0, ""

    assert bench.bare(c, tmp_path / "bare", runner=runner).passed is False


def test_a_tool_that_fails_is_said_and_not_checked(tmp_path):
    c = _slugify_case(tmp_path)
    bench.make_project(c, tmp_path, tmp_path / "bare")

    def runner(*_a):
        raise RuntimeError("claude exited 1: not logged in")

    side = bench.bare(c, tmp_path / "bare", runner=runner)
    assert side.error == "claude exited 1: not logged in" and side.passed is None
    assert "did not finish" in bench.render(bench.Report("r", "barracks", "slugify", bare=side))


# -- the building's side ------------------------------------------------------------------------------------------

@pytest.fixture
def faked_pool(monkeypatch):
    def work(harness, prompt, workdir, cancel, model, env, resume):
        _solve(workdir, commit=True)
        return "slugify added", 0.05, 1200, "s1"

    monkeypatch.setattr(BarracksWorker, "work_runner", staticmethod(work))
    monkeypatch.setattr(BarracksWorker, "steward_runner", Steward())
    monkeypatch.setattr(building_bench, "POLL_S", 0.05)


def test_the_building_runs_the_case_in_a_town_of_its_own(tmp_path, faked_pool):
    c = _slugify_case(tmp_path)
    project = tmp_path / "run" / "building"
    base = bench.make_project(c, tmp_path, project)
    side = building_bench.run_building(c, project, base, {}, timeout_s=60)
    assert side.error == "" and side.passed is True, (side.check_tail, side.how)
    assert side.files == ["src/text.py"] and side.orks == 1 and side.tokens == 1200
    assert side.cost >= 0.05 and any(h.startswith("hire") for h in side.how)
    assert any(st["action"] == "hire" and st["who"] != "steward" for st in side.steps)   # the run's clock, a lane each
    assert all(st["t"] >= 0 for st in side.steps)
    assert _git(project, "remote") == ""                         # nothing could go out
    ledger = [json.loads(ln) for ln in (project / ".orkcraft" / "ledger.jsonl").read_text().splitlines()]
    assert ledger[-1]["tokens"] == 1200 and ledger[-1]["cost"] > 0.05   # the pool's run: its tokens, the steward's $
    assert not (tmp_path / ".orkcraft").exists()                 # the town it came from is untouched


def test_the_bench_sets_the_tool_tier_spend_and_check_and_drops_what_points_home():
    c = bench.Case(id="c", type="barracks", title="C", task="T", check="make test")
    config = building_bench.bench_config({"repo": "/home/me/app", "max_orcs": 2, "orders": "be brief"}, c,
                                         "codex", "elder", 1.5)
    assert "repo" not in config and config["max_orcs"] == 2 and config["orders"] == "be brief"
    assert (config["providers"], config["steward"]) == (["codex:elder"], "codex:elder")
    assert (config["test_cmd"], config["budget_usd"], config["worktrees"]) == ("make test", 1.5, True)
    assert "providers" not in building_bench.bench_config({}, c, "main", "", 2.0)


def test_a_run_keeps_both_sides_and_reads_back(tmp_path, faked_pool):
    c = _slugify_case(tmp_path)

    def bare_runner(tool, prompt, workdir, cancel, model):
        return "I could not", 0.02, 500, ""

    report, folder = building_bench.run(tmp_path, c, bare_runner=bare_runner)
    assert folder.parent == tmp_path / bench.RUNS and (folder / "report.json").is_file()
    assert report.building.passed is True and report.bare.passed is False
    kept = bench.runs(tmp_path, "barracks")
    assert [r.id for r in kept] == [report.id] and kept[0].bare.cost == 0.02
    text = bench.render(kept[0], "Agent pool")
    assert "Agent pool" in text and "Bare AI tool" in text and "passed" in text and "failed" in text


# -- orkcraft bench ---------------------------------------------------------------------------------------------

def test_cli_lists_the_cases(fake_repo, capsys):
    assert cli.main(["--repo", str(fake_repo), "bench", "--list"]) == 0
    out = capsys.readouterr().out
    assert "slugify" in out and "inventory" in out


def test_cli_refuses_an_unknown_case_type_or_tier(fake_repo, capsys):
    assert cli.main(["--repo", str(fake_repo), "bench", "--case", "nope"]) == 2
    assert cli.main(["--repo", str(fake_repo), "bench", "mill"]) == 2
    assert cli.main(["--repo", str(fake_repo), "bench", "--tier", "grandmaster"]) == 2
    err = capsys.readouterr().err
    assert "slugify" in err and "barracks, watchtower, fields, war_drum so far" in err and "novice, seasoned or veteran" in err
