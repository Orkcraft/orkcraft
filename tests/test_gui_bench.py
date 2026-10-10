"""The Test bench (gui/bench.py, core/workers/lab.py, docs/design/test-bench.md): a building whose roads in say what it
tests, reviews on a first open,
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
    assert s["pools"] == [{"id": pool, "title": host.town.scroll.building(pool).title, "road": False}]
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


def test_the_window_gives_each_run_and_the_summary_as_text_to_copy(host):
    bid = _raised(host, "barracks", worktrees=False)
    side = bench.Side("building", seconds=10, cost=0.2, passed=True)
    bench.Report("r9", "barracks", "slugify", at="2026-10-10T12:00:00", building=side,
                 bare=bench.Side("bare", seconds=8, cost=0.1, passed=False)).save(host.town.repo_root / bench.RUNS / "r9")
    s = host.command("bench.open", {"id": bid})
    assert s["runs"][0]["copy"].startswith("Test bench: slugify") and "## Bare AI tool" in s["runs"][0]["copy"]
    assert "slugify" in s["against_copy"] and "against the bare AI tool" in s["against_copy"]


def test_a_kept_run_reads_back_with_its_steps(tmp_path):
    side = bench.Side("building", steps=[{"t": 1.0, "who": "Grub", "action": "hire", "why": "first"}])
    bench.Report("r1", "barracks", "slugify", building=side, orders_changed=True).save(tmp_path / bench.RUNS / "r1")
    kept = bench.runs(tmp_path, "barracks")[0]
    assert kept.building.steps[0]["who"] == "Grub" and kept.orders_changed is True


def test_a_series_runs_every_case_or_every_case_of_a_level(host, monkeypatch):
    bid = _raised(host, "barracks", worktrees=False)
    s = host.command("bench.open", {"id": bid})
    _settled(host, bid)
    assert s["levels"] == {"simple": 5, "medium": 5, "parallel": 5} and s["against"] == []
    seen = []
    real = subprocess.Popen

    def popen(argv, **kw):
        seen.append(argv)
        return real(["sh", "-c", f'echo "{bench.DONE}r"'], **kw)

    monkeypatch.setattr(gui_bench.subprocess, "Popen", popen)
    with pytest.raises(CommandError, match="No such level"):
        host.command("bench.run", {"id": bid, "case": "level:hard"})
    s = host.command("bench.run", {"id": bid, "case": "level:parallel"})
    assert seen[-1][seen[-1].index("bench") + 1:seen[-1].index("bench") + 4] == ["barracks", "--level", "parallel"]
    assert s["job"]["label"] == "every parallel case (5)"
    assert _until(lambda: host.bench.jobs["barracks"].done)
    s = host.command("bench.run", {"id": bid, "case": "all"})
    assert "--case" in seen[-1] and seen[-1][seen[-1].index("--case") + 1] == "all"
    assert s["job"]["label"] == "every case (15)"


# -- the Test bench is a building -------------------------------------------------------------------------------

def _road(h: Host, source: str, target: str, event: str) -> None:
    from orkcraft import scroll as ts
    ts.subscribe(h.town.scroll, target, source, event)


def test_the_test_bench_tests_the_buildings_whose_road_comes_in(host):
    from orkcraft.gui.views import lab as view
    lab = _raised(host, "lab")
    w = host.town.worker(lab)
    assert w.subjects() == [] and view.card(w)["subject"] is None
    assert "pull a road" in w.mini_status()[0].lower()
    pool = _raised(host, "barracks", worktrees=False)
    tower = _raised(host, "watchtower")
    _road(host, pool, lab, "pool.done")
    _road(host, tower, lab, "mail.received")
    assert [s["id"] for s in w.subjects()] == [pool, tower] and w.subject()["id"] == pool
    assert all(s["can_run"] for s in w.subjects()) and w.subjects()[1]["word"] == "External listeners"
    host.command("act", {"id": lab, "act": "pick", "args": {"id": tower}})
    assert host.detail(lab)["data"]["subject"] == tower
    with pytest.raises(CommandError, match="does not come into"):
        host.command("act", {"id": lab, "act": "pick", "args": {"id": "nope"}})


def test_a_run_says_its_report_and_what_the_building_missed_down_the_test_benchs_roads(host, monkeypatch):
    sent = []
    monkeypatch.setattr(host.town, "emit_typed", lambda b, ev, value, title="", *a, **k: sent.append((b, ev, title, value)) or True)
    lab, pool = _raised(host, "lab"), _raised(host, "barracks", worktrees=False)
    _road(host, pool, lab, "pool.done")
    side = bench.Side("building", seconds=5, passed=False, checks=[{"name": "#2 left out", "ok": False, "detail": "kept"}])
    bench.Report("r5", "barracks", "slugify", at="2026-10-10T12:00:00", building=side,
                 bare=bench.Side("bare", passed=True)).save(host.town.repo_root / bench.RUNS / "r5")
    job = gui_bench.Job("run", "barracks", "Add a slugify helper", subject=pool)
    host.bench._reported(job, "r5")
    host.bench._reported(job, "r5")                                            # said once
    events = [(b, ev) for b, ev, _t, _v in sent]
    assert events == [(lab, "lab.report"), (lab, "lab.missed")]
    assert "## Bare AI tool" in sent[0][3] and "#2 left out — kept" in sent[1][3]
    assert host.town.worker(lab).last[pool]["case"] == "slugify"
    assert "slugify" in host.town.worker(lab).mini_status()[1]


def test_make_tasks_may_send_the_findings_down_the_test_benchs_roads(host, monkeypatch):
    lab, pool, tower = _raised(host, "lab"), _raised(host, "barracks", worktrees=False, plan=False), _raised(host, "watchtower")
    _road(host, tower, lab, "mail.received")
    _road(host, lab, pool, "lab.finding")
    s = host.command("bench.open", {"id": tower, "lab": lab})
    _settled(host, tower)
    s = host.command("bench.state", {"id": tower, "lab": lab})
    assert s["roads"] == [{"id": pool, "title": host.town.title_of(pool)}] and s["pools"][0]["road"] is True
    done = host.command("bench.tasks", {"id": tower, "lab": lab, "pool": gui_bench.ROADS,
                                        "picks": ["ux:product_manager:0"]})
    assert done["made"] == 1
    assert _until(lambda: any(t.title.endswith("Say what a tier costs")
                              for t in host.town.worker(pool).state.tasks + host.town.worker(pool).state.queue))


def test_the_quick_action_runs_the_first_case_of_the_building_it_tests(host, monkeypatch):
    lab, pool = _raised(host, "lab", tool="agy", max_spend=0.5), _raised(host, "barracks", worktrees=False)
    with pytest.raises(CommandError, match="Pull a road"):
        host.command("act", {"id": lab, "act": "lab.run"})
    _road(host, pool, lab, "pool.done")
    host.detail(lab)                                                            # its window drawn: the bench given
    seen = {}
    monkeypatch.setattr(host.bench, "run", lambda args: seen.update(args) or {})
    assert host.command("act", {"id": lab, "act": "lab.run"}) == "slugify"
    assert (seen["id"], seen["tool"], seen["max_spend"], seen["lab"]) == (pool, "agy", 0.5, lab)
