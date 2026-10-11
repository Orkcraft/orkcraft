"""The Test bench's environments, case sets and what it keeps to spend less (docs/design/improve-buildings.md §5.2,
§7): an environment written once and given to every run, a set's cases written in one light call in an empty folder,
the bare tool's answer kept by what it depends on, and a series that stops when the building is behind."""
from __future__ import annotations

import json

import pytest

from orkcraft.core import bench as core_bench
from orkcraft.gui import lab_runs
from orkcraft.realm import bench, lab_cases, lab_envs
from tests.test_gui_bench import _raised, _road, _until, asked, host  # noqa: F401  (fixtures)


def test_an_environments_files_stay_inside_it():
    text = json.dumps({"name": "Inventory service, small", "files": {
        "README.md": "# Inventory", "src/app.py": "print(1)", "../escape.py": "x", "/etc/passwd": "x", ".git/config": "x"}})
    name, files = lab_envs.parse_env(text)
    assert name == "Inventory service, small" and set(files) == {"README.md", "src/app.py"}
    assert lab_envs.parse_env("no json here") is None
    big = json.dumps({"files": {f"f{i}.txt": "x" * 10 for i in range(lab_envs.FILES_MAX + 5)}})
    assert len(lab_envs.parse_env(big)[1]) == lab_envs.FILES_MAX


def test_a_sets_mean_and_what_it_will_cost():
    cases = [{"id": "a"}, {"id": "b"}, {"id": "c"}]
    results = {"a": {"scheme": {"cost": 0.2, "tokens": 1000}, "bare": {}, "time": -0.2, "tokens": -0.1, "quality": 1.0},
               "b": {"scheme": {"cost": 0.4, "tokens": 3000}, "bare": {}, "time": 0.0, "tokens": -0.3, "quality": 0.0}}
    assert lab_envs.summary_of(cases, results) == {"ran": 2, "time": -0.1, "tokens": -0.2, "quality": 0.5}
    assert lab_envs.estimate(cases, results, 3) == {"cost": 0.9, "tokens": 6000}
    assert lab_envs.estimate(cases, {}, 3) == {}


@pytest.fixture
def writer(monkeypatch):
    """The lab's agent: an environment, then a case set; where and on what model each was asked."""
    asks = []

    def read(tool, prompt, workdir, cancel, model="", *a, **kw):
        asks.append({"prompt": prompt, "workdir": str(workdir), "model": model})
        if "small, self-contained project" in prompt:
            return json.dumps({"name": "Tiny shop", "files": {"README.md": "# Shop", "shop.py": "TOTAL = 0"}}), 0.02, 900, ""
        return json.dumps({"cases": [{"title": f"Bug {n}", "text": f"Fix bug {n}"} for n in range(5)]}), 0.01, 400, ""

    monkeypatch.setattr(lab_runs.jobs, "run_read", read)
    return asks


def test_an_environment_and_a_case_set_are_written_once_and_given_to_the_runs(host, writer):
    lab, pool = _raised(host, "lab"), _raised(host, "barracks", worktrees=False)
    _road(host, pool, lab, "pool.done")
    host.detail(lab)
    act = lambda name, **a: host.command("act", {"id": lab, "act": name, "args": a})
    act("env_add", about="A tiny shop in Python, standard library only")
    w = host.town.worker(lab)
    assert _until(lambda: len(w.envs()) == 2)
    env = w.envs()[1]
    assert env["name"] == "Tiny shop" and w.env_files(env["id"]) == {"README.md": "# Shop", "shop.py": "TOTAL = 0"}
    act("set_add", env=env["id"], about="Fix one failing test", count=3)
    assert _until(lambda: len(w.sets_of(pool)) == 1)
    [cs] = w.sets_of(pool)
    cases = w.cases_in(pool, cs["id"])
    assert len(cases) == 3 and all(c["set"] == cs["id"] for c in cases)       # as many as asked, never more
    assert w.files_for(pool, cases[0]) == w.env_files(env["id"])
    assert all("orkcraft-lab-" in a["workdir"] for a in writer)               # an empty folder: nothing to read round
    assert all(a["model"] not in ("laborer", "warrior", "elder") for a in writer)   # a model's name, never a tier word
    d = host.detail(lab)["data"]
    assert [x["id"] for x in d["sets"]] == [cs["id"]] and d["sets"][0]["summary"]["ran"] == 0
    case = lab_cases.to_case(cases[0], "about", False, "", w.files_for(pool, cases[0]))
    assert case.files["shop.py"] == "TOTAL = 0"
    act("set_remove", set=cs["id"])
    assert w.sets_of(pool) == [] and w.cases_in(pool, cs["id"]) == []


def test_the_bare_answer_is_kept_and_read_back(tmp_path):
    case = bench.Case(id="c1", type="chain", title="t", task="", level="", files={"a.txt": "x"},
                      inputs={"cart": {"text": "hi"}, "goal": "fewer tokens", "judge": True})
    asked_for = []

    def ask(project):
        asked_for.append(project)
        return bench.Side("bare", seconds=3.0, cost=0.1, tokens=500, text="answer")

    lines = []
    first = core_bench._bare(tmp_path, case, tmp_path / "run1", "claude", "laborer", None, False, "run1", lines.append, ask)
    again = core_bench._bare(tmp_path, case, tmp_path / "run2", "claude", "laborer", None, False, "run2", lines.append, ask)
    assert len(asked_for) == 1 and again.kept == "run1" and again.text == first.text == "answer"
    other_goal = bench.Case(**{**case.__dict__, "inputs": {**case.inputs, "goal": "faster"}})
    core_bench._bare(tmp_path, other_goal, tmp_path / "run3", "claude", "laborer", None, False, "run3", lines.append, ask)
    assert len(asked_for) == 1                                                # the goal is the judge's, not the tool's
    core_bench._bare(tmp_path, case, tmp_path / "run4", "claude", "warrior", None, False, "run4", lines.append, ask)
    core_bench._bare(tmp_path, case, tmp_path / "run5", "claude", "laborer", None, True, "run5", lines.append, ask)
    assert len(asked_for) == 3                                                # another tier; asked fresh
    assert "kept from run run1" in bench.render(bench.Report("r", "chain", "c1", bare=again))

    def fails(project):
        return bench.Side("bare", error="boom")
    other = bench.Case(**{**case.__dict__, "id": "c2", "files": {"b.txt": "y"}})
    core_bench._bare(tmp_path, other, tmp_path / "run6", "claude", "", None, False, "run6", lines.append, fails)
    assert bench.kept_bare(tmp_path, bench.bare_key(other, "claude", "")) is None   # an error is asked again


def test_a_series_stops_when_the_building_is_behind_on_its_first_cases(tmp_path, monkeypatch, capsys):
    import subprocess
    from orkcraft import cli
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    cases = [{"id": f"c{n}", "type": "chain", "title": f"Case {n}", "task": "", "level": ""} for n in range(6)]
    (tmp_path / "cases.json").write_text(json.dumps(cases), encoding="utf-8")
    (tmp_path / "chain.json").write_text(json.dumps({"id": "chain:a:b", "first_type": "pit"}), encoding="utf-8")
    ran = []

    def run(root, case, *a, **kw):
        ran.append(case.id)
        r = bench.Report(f"r{len(ran)}", "chain", case.id, building=bench.Side("building", seconds=20, cost=1.0, passed=True),
                         bare=bench.Side("bare", seconds=10, cost=0.5, passed=True))
        return r, tmp_path

    monkeypatch.setattr(core_bench, "run", run)
    code = cli.main(["--repo", str(tmp_path), "bench", "chain", "--cases-file", str(tmp_path / "cases.json"),
                     "--chain-file", str(tmp_path / "chain.json"), "--case", "all", "--stop-behind", "2"])
    assert code == 0 and ran == ["c0", "c1"]
    assert "stopped early" in capsys.readouterr().out
