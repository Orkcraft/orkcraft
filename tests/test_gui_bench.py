"""The Test bench's window (gui/bench.py, docs/design/test-bench.md): behind ORKCRAFT_BENCH, reviews on a first open,
a run in a process of its own, written cases, Make tasks. AI tools are faked."""
from __future__ import annotations

import json
import subprocess
import time

import pytest

from orkcraft.core import buildings
from orkcraft.core.workers.barracks import BarracksWorker
from orkcraft.gui import bench as gui_bench
from orkcraft.gui.host import CommandError, Host
from orkcraft.realm import bench, bench_review, checkpoint
from tests.pool_fakes import Steward

ANSWER = {
    "aha": {"moment": "a test task comes back as a pull request", "script": ["build it", "give it a task"],
            "measure": "minutes to the first accepted task", "time_to_it": "5 minutes"},
    "findings": [{"title": "Say what a tier costs", "detail": "The setup names tiers, not prices.",
                  "severity": "high", "where": "Info"},
                 {"title": "", "detail": "no title: dropped"},
                 {"title": "Name the steward", "severity": "odd"}],
}


def _until(cond, seconds: float = 15.0) -> bool:
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if cond():
            return True
        time.sleep(0.02)
    return cond()


@pytest.fixture
def asked(monkeypatch):
    """Every reviewer's and case writer's AI tool call, answered from a script."""
    calls = []

    def read(tool, prompt, workdir, cancel, model="", *a, **kw):
        calls.append(prompt)
        if "You write a test case" in prompt:
            case = {"id": "Merge Two", "title": "Merge two lists", "task": "Write merge(a, b)",
                    "files": {"m.py": ""}, "check": "true"}
            return "Here it is:\n" + json.dumps(case), 0.03, 900, ""
        return json.dumps(ANSWER), 0.02, 700, ""

    monkeypatch.setattr(bench_review.jobs, "run_read", read)
    return calls


@pytest.fixture
def host(fake_repo, isolated_layout_file, monkeypatch, asked):
    monkeypatch.setenv("ORKCRAFT_BENCH", "1")
    monkeypatch.setattr(BarracksWorker, "work_runner", staticmethod(
        lambda harness, prompt, workdir, cancel, model, env, resume: ("done", 0.0, 0, "")))
    monkeypatch.setattr(BarracksWorker, "steward_runner", Steward())
    checkpoint.ensure(fake_repo)
    h = Host(fake_repo, auto_commit=False)
    yield h
    h.close()


def _raised(h: Host, type_id: str, **config) -> str:
    spec = buildings.type_spec(h.town, type_id)
    spec["config"] = {**(spec.get("config") or {}), **config}
    built = buildings.raise_spec(h.town, spec)
    h.town.worker(built.id)
    return built.id


def _settled(h: Host, bid: str) -> dict:
    assert _until(lambda: not h.bench.reviewing), "the reviews never ended"
    return h.command("bench.state", {"id": bid})


# -- the flag -------------------------------------------------------------------------------------------------

def test_the_bench_is_off_without_its_flag(host, monkeypatch):
    bid = _raised(host, "barracks", worktrees=False)
    assert host.snapshot()["bench"] is True
    monkeypatch.delenv("ORKCRAFT_BENCH")
    assert host.snapshot()["bench"] is False
    with pytest.raises(CommandError, match="ORKCRAFT_BENCH=1"):
        host.command("bench.open", {"id": bid})


# -- reviews --------------------------------------------------------------------------------------------------

def test_a_first_open_reviews_the_three_tabs_once(host, asked):
    bid = _raised(host, "barracks", worktrees=False)
    first = host.command("bench.open", {"id": bid})
    assert first["can_run"] and first["word"] == "Agent pool" and [c["id"] for c in first["cases"]][:1] == ["slugify"]
    s = _settled(host, bid)
    assert len(asked) == 7                                       # 3 tech, 2 ux, 2 product
    pm = next(r for r in s["reviews"]["product"]["roles"] if r["id"] == "product_manager")
    assert pm["status"] == "done" and pm["aha"]["moment"].startswith("a test task")
    assert [f["title"] for f in pm["findings"]] == ["Say what a tier costs", "Name the steward"]
    assert [f["severity"] for f in pm["findings"]] == ["high", "medium"]
    assert pm["findings"][0]["id"] == "product:product_manager:0" and pm["cost"] == 0.02
    host.command("bench.open", {"id": bid})                      # kept: nothing starts again by itself
    assert not host.bench.reviewing and len(asked) == 7
    host.command("bench.review", {"id": bid, "tab": "ux"})      # …only Review again
    _settled(host, bid)
    assert len(asked) == 9


def test_a_reviewer_reads_the_buildings_own_code_and_the_tech_one_the_last_run(tmp_path):
    p = bench_review.prompt(tmp_path, "barracks", "tech", "ai_researcher")
    assert "Agent pool" in p and "core/workers/barracks.py" in p and "No Test bench run yet" in p
    assert "AI researcher" in p and '"aha"' not in p
    assert '"aha"' in bench_review.prompt(tmp_path, "barracks", "product", "architect")


def test_an_answer_that_is_not_json_fails_the_role_and_says_so(host, monkeypatch):
    monkeypatch.setattr(bench_review.jobs, "run_read", lambda *a, **kw: ("I could not read it", 0.0, 0, ""))
    bid = _raised(host, "barracks", worktrees=False)
    host.command("bench.review", {"id": bid, "tab": "ux"})
    role = _settled(host, bid)["reviews"]["ux"]["roles"][0]
    assert role["status"] == "failed" and "I could not read it" in role["error"]


# -- Make tasks -----------------------------------------------------------------------------------------------

def test_ticked_findings_become_tasks_of_the_picked_agent_pool(host):
    pool = _raised(host, "barracks", worktrees=False, plan=False)
    other = _raised(host, "watchtower")
    host.command("bench.open", {"id": other})
    s = _settled(host, other)
    assert s["pools"] == [{"id": pool, "title": host.town.scroll.building(pool).title}]
    with pytest.raises(CommandError, match="Tick"):
        host.command("bench.tasks", {"id": other, "picks": [], "pool": pool})
    with pytest.raises(CommandError, match="Agent pool"):
        host.command("bench.tasks", {"id": other, "picks": ["ux:product_manager:0"], "pool": other})
    done = host.command("bench.tasks", {"id": other, "picks": ["ux:product_manager:0", "product:architect:1"], "pool": pool})
    assert done["made"] == 2
    st = host.town.worker(pool).state
    titles = [t.title for t in st.tasks + st.queue]
    assert "External listeners: Say what a tier costs" in titles and "External listeners: Name the steward" in titles
    task = next(t for t in st.tasks + st.queue if t.title.endswith("tier costs"))
    assert "Product manager (ux review)" in task.text and "Where: Info" in task.text


# -- cases ----------------------------------------------------------------------------------------------------

def test_a_written_case_counts_only_once_it_is_read(host):
    bid = _raised(host, "barracks", worktrees=False)
    host.command("bench.open", {"id": bid})
    _settled(host, bid)
    host.command("bench.case.write", {"id": bid, "brief": "two lists"})
    assert _until(lambda: host.bench.jobs["barracks"].done)
    s = host.command("bench.state", {"id": bid})
    assert s["job"]["result"] == "merge-two" and s["job"]["error"] == ""
    case = next(c for c in s["cases"] if c["id"] == "merge-two")
    assert case["reviewed"] is False and case["own"] is True
    with pytest.raises(CommandError, match="Pick a case"):
        host.command("bench.run", {"id": bid, "case": "nope"})
    s = host.command("bench.case.read", {"id": bid, "case": "merge-two"})
    assert next(c for c in s["cases"] if c["id"] == "merge-two")["reviewed"] is True
    with pytest.raises(CommandError):
        host.command("bench.case.read", {"id": bid, "case": "slugify"})   # a shipped case is not the town's to mark


# -- a run ----------------------------------------------------------------------------------------------------

def test_a_run_is_orkcraft_bench_in_a_process_of_its_own(host, monkeypatch):
    bid = _raised(host, "barracks", worktrees=False, orders="be brief")
    host.command("bench.open", {"id": bid})
    _settled(host, bid)
    seen = {}
    real = subprocess.Popen

    def popen(argv, **kw):
        seen["argv"] = argv
        script = f'echo "the building works on the case…"; echo "+0:01 hire: Grub"; echo "{bench.DONE}20261010-run"'
        return real(["sh", "-c", script], **kw)

    monkeypatch.setattr(gui_bench.subprocess, "Popen", popen)
    with pytest.raises(CommandError, match="No such tier"):
        host.command("bench.run", {"id": bid, "case": "slugify", "tier": "legend"})
    host.command("bench.run", {"id": bid, "case": "slugify", "tool": "main", "tier": "warrior", "max_spend": 1,
                               "only": "building", "orders": "be thorough"})
    argv = seen["argv"]
    assert argv[argv.index("bench") + 1:argv.index("bench") + 4] == ["barracks", "--case", "slugify"]
    assert argv[argv.index("--tier") + 1] == "seasoned" and argv[argv.index("--max-spend") + 1] == "1.0"
    assert argv[argv.index("--only") + 1] == "building"
    assert open(argv[argv.index("--orders") + 1]).read() == "be thorough"
    assert _until(lambda: host.bench.jobs["barracks"].done)
    job = host.command("bench.state", {"id": bid})["job"]
    assert job["result"] == "20261010-run" and job["lines"][-1] == "+0:01 hire: Grub" and job["error"] == ""


def test_a_type_the_bench_cannot_run_yet_is_said(host):
    bid = _raised(host, "mill")
    s = host.command("bench.open", {"id": bid})
    assert s["can_run"] is False
    assert "External listeners" in s["runs_for"] and "Calendar" in s["runs_for"]
    with pytest.raises(CommandError, match="later"):
        host.command("bench.run", {"id": bid, "case": "slugify"})


def test_a_kept_run_reads_back_with_its_steps(tmp_path):
    side = bench.Side("building", steps=[{"t": 1.0, "who": "Grub", "action": "hire", "why": "first"}])
    bench.Report("r1", "barracks", "slugify", building=side, orders_changed=True).save(tmp_path / bench.RUNS / "r1")
    kept = bench.runs(tmp_path, "barracks")[0]
    assert kept.building.steps[0]["who"] == "Grub" and kept.orders_changed is True
