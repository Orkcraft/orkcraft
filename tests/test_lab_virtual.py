"""The virtual building (docs/design/improve-buildings.md §5.3): a proposal tried on the Test bench's copy of a
building — its runs stand it, the town's does not change — until Save changes makes it the building's own; code
changes live in the bench's own copy of the package and reach a run through PYTHONPATH only."""
from __future__ import annotations

import json

import pytest

from orkcraft.core import runners
from orkcraft.gui import lab_runs
from orkcraft.gui.host import CommandError
from orkcraft.realm import code_overlay
from tests.test_gui_bench import _raised, _road, _until, asked, host  # noqa: F401  (fixtures)


def _act(h, lab, name, **args):
    return h.command("act", {"id": lab, "act": name, "args": args})


@pytest.fixture
def proposals(monkeypatch):
    """The lab's agent proposes a prompt change and a code change; the keeper writes the prompt one as a config."""
    def read(tool, prompt, workdir, cancel, model="", *a, **kw):
        return json.dumps({"proposals": [
            {"area": "prompt", "title": "Shorter orders", "detail": "Tell the pool to answer in one line",
             "where": "the Agent pool"},
            {"area": "code", "title": "Skip the plan for one-liners", "detail": "d", "where": "core/workers/barracks.py"},
            {"area": "roads", "title": "A road more", "detail": "d"}]}), 0.01, 500, ""

    monkeypatch.setattr(lab_runs.jobs, "run_read", read)


def test_a_proposal_is_tried_on_the_virtual_building_and_saved_for_good(host, proposals, monkeypatch):
    lab, pool = _raised(host, "lab"), _raised(host, "barracks", worktrees=False)
    _road(host, pool, lab, "pool.done")
    host.detail(lab)
    w = host.town.worker(lab)
    w.state["results"][pool] = {"c1": {"scheme": {}, "bare": {}}}
    _act(host, lab, "propose")
    assert _until(lambda: len((w.state["proposals"].get(pool) or {}).get("items") or []) == 3)
    before = dict(host.town.spec_of(pool)["config"])
    config = {**before, "orders": "Answer in one line."}
    monkeypatch.setattr(runners, "KEEPER_RUNNER", lambda prompt: (json.dumps({"value": config, "why": "one line"}), 0.01))
    _act(host, lab, "try", proposal="p0")
    assert _until(lambda: len(w.changes_of(pool)) == 1)
    [ch] = w.changes_of(pool)
    assert ch["building"] == pool and ch["kind"] == "config"
    assert host.town.spec_of(pool)["config"].get("orders") != "Answer in one line."         # the town's is as it was
    assert w.flow_spec(w.subject())["buildings"][0]["config"]["orders"] == "Answer in one line."   # its runs stand it
    view = host.detail(lab)["data"]["virtual"]
    assert view[0]["building"] and any(op == "+" for op, _line in view[0]["diff"])
    with pytest.raises(CommandError, match="Roads change"):
        _act(host, lab, "try", proposal="p2")
    assert _act(host, lab, "save_changes") == {"saved": 1}
    assert host.town.spec_of(pool)["config"]["orders"] == "Answer in one line." and w.changes_of(pool) == []


def test_a_change_taken_back_takes_the_ones_after_it_on_the_same_building(host):
    lab, pool = _raised(host, "lab"), _raised(host, "barracks", worktrees=False)
    _road(host, pool, lab, "pool.done")
    w = host.town.worker(lab)
    base = dict(host.town.spec_of(pool)["config"])
    for n in range(3):
        w.add_change(pool, {"id": f"v{n}", "building": pool, "kind": "config", "after": {**base, "max_orcs": n + 1},
                            "why": f"{n}"})
    assert w.virtual_spec(pool, pool)["config"]["max_orcs"] == 3
    assert w.take_back(pool, "v1")
    assert [c["id"] for c in w.changes_of(pool)] == ["v0"] and w.virtual_spec(pool, pool)["config"]["max_orcs"] == 1


def test_code_is_changed_in_the_benchs_own_copy_and_reaches_its_runs_only(tmp_path):
    pkg = code_overlay.ensure(tmp_path)
    assert (pkg / "__init__.py").is_file() and (pkg / "design" / "system").is_symlink()
    assert code_overlay.changed(tmp_path) == [] and code_overlay.env(tmp_path) == {}
    target = pkg / "realm" / "lab_envs.py"
    target.write_text(target.read_text(encoding="utf-8") + "\n# tried by the bench\n", encoding="utf-8")
    code_overlay.keep(tmp_path, "a comment")
    assert code_overlay.changed(tmp_path) == ["orkcraft/realm/lab_envs.py"]
    assert "+# tried by the bench" in code_overlay.diff(tmp_path)
    assert code_overlay.env(tmp_path) == {"PYTHONPATH": str(code_overlay.root(tmp_path))}
    assert "tried by the bench" not in (code_overlay.package() / "realm" / "lab_envs.py").read_text(encoding="utf-8")
    code_overlay.drop(tmp_path)
    assert not code_overlay.root(tmp_path).exists()


def test_a_code_proposal_is_an_agents_change_in_the_copy(host, proposals, monkeypatch):
    lab, pool = _raised(host, "lab"), _raised(host, "barracks", worktrees=False)
    _road(host, pool, lab, "pool.done")
    host.detail(lab)
    w = host.town.worker(lab)
    _act(host, lab, "propose")
    assert _until(lambda: len((w.state["proposals"].get(pool) or {}).get("items") or []) == 3)
    seen = {}

    def work(tool, prompt, workdir, cancel, model="", *a, **kw):
        seen.update(workdir=workdir, prompt=prompt)
        f = workdir / "orkcraft" / "core" / "workers" / "barracks.py"
        f.write_text(f.read_text(encoding="utf-8") + "\n# one-liners skip the plan\n", encoding="utf-8")
        return "Skipped the plan for one-liners.", 0.05, 900, ""

    monkeypatch.setattr(lab_runs.jobs, "run_work", work)
    _act(host, lab, "try", proposal="p1")
    assert _until(lambda: any(c["kind"] == "code" for c in w.changes_of(pool)))
    assert seen["workdir"] == code_overlay.root(w.state_dir) and "Skip the plan for one-liners" in seen["prompt"]
    [code] = [c for c in host.detail(lab)["data"]["virtual"] if c["kind"] == "code"]
    assert code["files"] == ["orkcraft/core/workers/barracks.py"] and "one-liners skip the plan" in code["diff"]
    _act(host, lab, "take_back", change="code")
    assert w.changes_of(pool) == [] and not code_overlay.root(w.state_dir).exists()
