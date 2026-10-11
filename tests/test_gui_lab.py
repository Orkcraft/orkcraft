"""The Test bench building's own window (gui/views/lab.py, gui/lab_runs.py, docs/design/test-bench.md §10): a goal,
the cases written from it or by hand, a run of them against the bare AI tool, and what to change for the goal."""
from __future__ import annotations

import json
import subprocess

import pytest

from orkcraft.gui import lab_runs
from orkcraft.gui.host import CommandError
from orkcraft.realm import bench, lab_cases
from tests.test_gui_bench import _chain, _raised, _road, _until, asked, host  # noqa: F401  (fixtures)


@pytest.fixture
def agent(monkeypatch):
    """The lab's agent: it writes two cases, then proposes."""
    prompts = []

    def read(tool, prompt, workdir, cancel, model="", *a, **kw):
        prompts.append((tool, prompt))
        if "You plan the test cases" in prompt:
            return json.dumps({"cases": [{"title": "CSV parser", "text": "Write a CSV parser", "expect": ["csv"]},
                                         {"title": "Research", "text": "Compare three vector DBs"}]}), 0.01, 500, ""
        return json.dumps({"proposals": [{"area": "prompt", "title": "Shorter steward rules", "detail": "d"}]}), 0.01, 500, ""

    monkeypatch.setattr(lab_runs.jobs, "run_read", read)
    return prompts


def _act(h, lab, name, **args):
    return h.command("act", {"id": lab, "act": name, "args": args})


def test_the_goal_writes_the_cases_and_they_stay_with_the_building(host, agent):
    lab, pool = _raised(host, "lab"), _raised(host, "barracks", worktrees=False)
    _road(host, pool, lab, "pool.done")
    host.detail(lab)
    with pytest.raises(CommandError, match="goal"):
        _act(host, lab, "generate")
    _act(host, lab, "goal", goal="Spend fewer tokens than the bare tool")
    _act(host, lab, "generate")
    w = host.town.worker(lab)
    assert _until(lambda: len(w.cases_of(pool)) == 2)
    d = host.detail(lab)["data"]
    assert d["metric"] == "tokens" and [c["title"] for c in d["cases"]] == ["CSV parser", "Research"]
    assert d["cases"][0]["entry"] == pool and "fewer tokens" in agent[0][1]
    cid = _act(host, lab, "add", title="Hard topic", text="Explain CRDTs", expect="merge, conflict")
    assert w.cases_of(pool)[-1]["expect"] == ["merge", "conflict"]
    _act(host, lab, "remove", case=cid)
    _act(host, lab, "settings", bare_tool="main", bare_tier="laborer", judge=False, max_spend="0.5")
    with pytest.raises(CommandError, match="No such tier"):
        _act(host, lab, "settings", tier="legend")
    kept = lab_cases.load(w.state_dir)                      # until the building is demolished
    assert kept["goal"].startswith("Spend fewer") and len(kept["cases"][pool]) == 2
    assert kept["settings"]["bare_tier"] == "laborer" and kept["settings"]["max_spend"] == 0.5 and not kept["settings"]["judge"]


def test_run_all_runs_its_cases_against_the_bare_tool_and_keeps_each_result(host, agent, monkeypatch):
    lab, pool = _raised(host, "lab"), _raised(host, "barracks", worktrees=False)
    _road(host, pool, lab, "pool.done")
    host.detail(lab)
    w = host.town.worker(lab)
    w.add_cases(pool, [lab_cases.new_case("One", "Write a slugify", pool), lab_cases.new_case("Two", "Sum a list", pool)])
    _act(host, lab, "settings", tool="main", tier="warrior", bare_tier="laborer")
    one = w.cases_of(pool)[0]["id"]
    r = bench.Report(id="r-lab", type="chain", case=one, tool="main", at="2026-10-10T10:00:00",
                     building=bench.Side("building", seconds=50, tokens=600, passed=True),
                     bare=bench.Side("bare", seconds=40, tokens=1000, passed=True))
    monkeypatch.setattr(bench, "runs", lambda root, type_id=None: [r])
    seen = {}
    real = subprocess.Popen

    def popen(argv, **kw):
        seen["argv"] = argv
        return real(["sh", "-c", f'echo "the scheme works…"; echo "{bench.DONE}r-lab"'], **kw)

    monkeypatch.setattr(lab_runs.subprocess, "Popen", popen)
    _act(host, lab, "run_all")
    argv = seen["argv"]
    assert argv[argv.index("bench") + 1] == "chain" and argv[argv.index("--case") + 1] == "all"
    assert argv[argv.index("--tier") + 1] == "seasoned" and argv[argv.index("--bare-tier") + 1] == "novice"
    spec = json.loads(open(argv[argv.index("--chain-file") + 1]).read())
    assert spec["first"] == pool and "pool.done" in spec["back_events"]
    cases = json.loads(open(argv[argv.index("--cases-file") + 1]).read())
    assert [c["title"] for c in cases] == ["One", "Two"] and cases[0]["inputs"]["entry"] == pool
    assert argv[argv.index("--repeat") + 1] == "3"                          # its medians, by default
    assert _until(lambda: w.results_of(pool).get(one))
    assert not w.state["proposals"].get(pool)                               # nothing proposed by itself
    _act(host, lab, "propose")
    assert _until(lambda: w.state["proposals"].get(pool))
    row = w.results_of(pool)[one]
    assert row["tokens"] == -0.4 and row["time"] == 0.25
    d = host.detail(lab)["data"]
    assert d["summary"]["cases"] == 1 and d["job"]["lines"] == ["the scheme works…"]
    assert [p["title"] for p in d["proposals"]["items"]] == ["Shorter steward rules"]
    assert "tokens -40%" in agent[-1][1]                                     # the proposals read the last tests
    made = _act(host, lab, "tasks", picks=["p0"], pool=pool)
    assert made == 1


def test_a_chains_cases_may_go_into_any_of_its_buildings_that_takes_one(host):
    lab, board, pool, _desk = _chain(host)
    w = host.town.worker(lab)
    [s] = w.subjects()
    ids = [e["id"] for e in w.entries(s)]
    assert ids[0] == board
    with pytest.raises(CommandError, match="way in"):
        _act(host, lab, "add", text="x", entry="nope")


def test_the_latest_runs_are_one_table_a_text_to_copy_and_a_zip_with_every_call(host, asked):
    import io
    import zipfile
    from orkcraft.realm import call_log
    lab, pool = _raised(host, "lab"), _raised(host, "barracks", worktrees=False)
    _road(host, pool, lab, "pool.done")
    host.detail(lab)
    for n, (b, t) in enumerate(((60, 50), (40, 50), (50, 50))):
        r = bench.Report(id=f"2026101{n}-000000-chain-one", type="chain", case="one", at=f"2026-10-1{n}T10:00:00",
                         subject=pool, series="s1", building=bench.Side("building", seconds=b, tokens=900, passed=True),
                         bare=bench.Side("bare", seconds=t, tokens=1000, passed=True))
        folder = host.town.repo_root / bench.RUNS / r.id
        r.save(folder)
        with call_log.kept(folder / "calls", "building"):
            call_log.record({"ORKCRAFT_ORC": f"{pool}/Grub"}, "work", "claude", "", "the task", "{}", "", 0, 3.0)
    d = host.detail(lab)["data"]
    assert d["report"]["runs"] == 3 and d["report"]["cases"] == 1 and "Runs" in d["report"]["text"]
    assert "3/3 passed / 3/3 passed" in d["report"]["text"] and d["recs"][0]["type"] == "barracks"
    text = _act(host, lab, "export")
    assert "# Test bench" in text and "Model calls" in text and "## Recommendations" in text
    _act(host, lab, "recommend")                                     # the tech review reads these runs
    assert _until(lambda: not host.detail(lab)["data"]["recs"][0]["running"])
    assert "## The last Test bench runs" in asked[-1] and "3/3 passed" in asked[-1]
    assert host.detail(lab)["data"]["recs"][0]["findings"]
    name, data = host.bench.lab.pack(lab)
    files = zipfile.ZipFile(io.BytesIO(data)).namelist()
    assert name.endswith(".zip") and "README.md" in files
    assert sum(f.startswith("runs/") and "/calls/building-001-Grub.json" in f for f in files) == 3
    assert host.bench.lab.pack("nobody") is None
