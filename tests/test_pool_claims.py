"""📍 The Agent pool sees work that collides and remembers its designs (docs/design/barracks-designs.md):
areas in work across tasks and pools, the wait and the flag, `merge-tree` between branches, the design brief
on the task's branch, the plan read against the briefs, a brief kept true by the review."""
from __future__ import annotations

import json
import subprocess
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from orkcraft import autonomy
from orkcraft.core.workers.barracks import BarracksWorker
from orkcraft.realm import barracks as bk
from orkcraft.realm import briefs, claims, jobs, plans
from tests.pool_fakes import FakeGit, Steward
from tests.test_pool_failures import Crew, _app, _open, _until
from tests.test_pool_plans import HARD, _hard, _level, plan, sub

SIZE = (200, 46)
SINGLE = '{"kind": "single", "tier": "warrior", "why": "one go", "touches": %s}'
BRIEF = ("---\norkcraft: brief\ntask: old1\npool: camp\ntouches: [src/export/]\n---\n# Build the export\n\n"
         "## Decisions\n\n- the export streams CSV, never builds it in memory\n")


@pytest.fixture
def steward(monkeypatch):
    def use(**kw) -> Steward:
        s = Steward(**kw)
        monkeypatch.setattr(BarracksWorker, "steward_runner", s)
        return s
    return use


@pytest.fixture
def git(monkeypatch) -> FakeGit:
    g = FakeGit()
    monkeypatch.setattr(BarracksWorker, "git", g)
    return g


def _claim(key, paths, status=claims.WORK, since="2026-10-08T10:00:00", **kw) -> claims.Claim:
    b, _, t = key.partition(":")
    return claims.Claim(key, b, t, kw.pop("title", t), paths, status=status, since=since, **kw)


# -- the rules ---------------------------------------------------------------------------------------

def test_a_claim_never_holds_the_root_or_a_whole_top_folder():
    assert claims.too_wide("") and claims.too_wide(".") and claims.too_wide("src/") and claims.too_wide("./docs")
    assert not claims.too_wide("README.md") and not claims.too_wide("src/export/")
    assert claims.narrow(["src/", "./src/export/", "src/export", "docs/a.md"]) == ["src/export", "docs/a.md"]


def test_overlaps_and_who_waits_for_whom():
    a = _claim("camp:a", ["src/export"], since="2026-10-08T10:00:00")
    b = _claim("camp:b", ["src/export/csv.py"], since="2026-10-08T10:05:00")
    c = _claim("other:c", ["src/import"], since="2026-10-08T09:00:00")
    every = [a, b, c]
    assert [o.key for o in claims.overlaps(every, b)] == ["camp:a"] and claims.overlaps(every, c) == []
    assert claims.holds(every, b) is a and claims.holds(every, a) is None      # only the newer waits
    a.status = claims.REVIEW
    assert claims.holds(every, b) is None                                     # a PR open: no wait


def test_claims_are_kept_per_repository_and_go_stale(tmp_path: Path):
    store = claims.Claims(tmp_path)
    store.put(_claim("camp:a", ["src/x"], since="2026-10-08T10:00:00"))
    kept = store.put(_claim("camp:a", ["src/y"], since="2026-10-09T10:00:00"))
    assert kept.since == "2026-10-08T10:00:00" and store.get("camp:a").paths == ["src/y"]   # when it first claimed
    store.put(_claim("pool2:b", ["src/z"], since=(datetime.now() - timedelta(days=30)).isoformat()))
    assert [c.key for c in store.drop_stale(14)] == ["pool2:b"]
    assert store.release("camp:a") and store.load() == [] and not store.release("camp:a")


def test_the_sort_guesses_the_area_and_the_plan_may_leave_a_design():
    t = plans.parse_triage(SINGLE % '["src/export/", 7]')
    assert t.kind == "single" and t.touches == ["src/export/", "7"]
    assert plans.parse_triage('{"kind": "trivial"}').touches == []
    text = json.dumps({"subtasks": [sub("a")], "design": {"why": "stream it", "decisions": ["CSV", ""],
                                                           "invariants": "never in memory", "x": 1},
                       "conflicts": [{"with": "docs/design/a.md", "why": "it said JSON"}, {"why": "no path"}]})
    design, against = plans.extras(text)
    assert design == {"why": "stream it", "decisions": ["CSV"], "invariants": ["never in memory"]}
    assert against == [{"with": "docs/design/a.md", "why": "it said JSON"}]
    assert plans.extras("SIMPLE") == ({}, [])
    prompt = plans.plan_prompt("Gor", "", "T", "x", "balance", 3, [], designs="## Designs this touches\n\n…", brief=True)
    assert "`design` object" in prompt and "\"conflicts\"" in prompt and "## Designs this touches" in prompt
    assert "`design`" not in plans.plan_prompt("Gor", "", "T", "x", "balance", 3, [])


def test_a_brief_is_written_read_back_and_found(tmp_path: Path):
    subs = [plans.Sub("api", "API", "do it", "warrior", touches=["src/export/api.py"]),
            plans.Sub("ui", "UI", "do it", "laborer", touches=["src/ui/export.js"], after=["api"])]
    text = briefs.render("Build the export", "Make a CSV export\n\nit streams", "t1", "camp", subs,
                         {"why": "people ask for it", "decisions": ["stream CSV"]})
    assert text.startswith("---\norkcraft: brief\ntask: t1\npool: camp\ntouches: [src/export/api.py, src/ui/export.js]")
    assert "## Why\n\npeople ask for it" in text and "- stream CSV" in text and "`ui` UI (laborer)" in text
    assert "> Make a CSV export" in text
    (tmp_path / "docs" / "design").mkdir(parents=True)
    (tmp_path / "docs" / "design" / "build-the-export.md").write_text(text, encoding="utf-8")
    (tmp_path / "docs" / "design" / "plain.md").write_text("# Not a brief\n", encoding="utf-8")
    found = briefs.scan(tmp_path)
    assert [(b.path, b.title, b.touches) for b in found] == [
        ("docs/design/build-the-export.md", "Build the export", ["src/export/api.py", "src/ui/export.js"])]
    assert briefs.relevant(found, ["src/export"], "") == found                      # by its paths
    assert briefs.relevant(found, [], "the csv export streams people") == found     # by its words
    assert briefs.relevant(found, ["src/other"], "nothing alike here at all") == []
    assert briefs.path_for("docs/design", "Build the export", {"docs/design/build-the-export.md"}) == \
        "docs/design/build-the-export-2.md"
    assert briefs.stale(found, ["src/export/api.py"]) == found
    assert briefs.stale(found, ["src/export/api.py", "docs/design/build-the-export.md"]) == []
    assert briefs.confirmed("ACCEPT\nDESIGN: unchanged") and not briefs.confirmed("ACCEPT")
    assert briefs.states(found, ["src/export/api.py"], "ACCEPT") == [
        {"path": "docs/design/build-the-export.md", "state": "not confirmed"}]


def test_git_tells_a_conflict_and_commits_a_file_without_a_checkout(fake_repo: Path):
    g = jobs.TaskGit()
    run = lambda *a: subprocess.run(["git", *a], cwd=fake_repo, check=True, capture_output=True, text=True)  # noqa: E731
    base = g.base_of(fake_repo)
    for name in ("a", "b", "c"):
        run("checkout", "-q", "-b", f"pool/camp/{name}", base)
        path = fake_repo / ("src/app.py" if name != "c" else "src/other.py")
        path.write_text(f"print('{name}')\n", encoding="utf-8")
        run("add", ".")
        run("commit", "-qm", name)
    run("checkout", "-q", base)
    assert g.would_conflict(fake_repo, "pool/camp/a", "pool/camp/b") == ["src/app.py"]
    assert g.would_conflict(fake_repo, "pool/camp/a", "pool/camp/c") == []
    assert g.would_conflict(fake_repo, "pool/camp/a", "no-such-branch") is None
    g.commit_file(fake_repo, "pool/camp/c", "docs/design/x.md", "# X\n", "Design brief: X")
    assert run("show", "pool/camp/c:docs/design/x.md").stdout == "# X\n"
    assert run("show", "pool/camp/c:src/other.py").stdout == "print('c')\n"      # the rest of the tree stays
    assert run("status", "--porcelain").stdout == "" and not (fake_repo / "docs" / "design" / "x.md").exists()


# -- the barracks ---------------------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_a_newer_task_on_an_area_being_built_waits_then_goes_told(fake_repo: Path, monkeypatch, steward, git):
    git.files = ("src/export/api.py",)
    git.pr = "https://github.com/o/r/pull/9"
    steward(sorts=[SINGLE % '["src/export/api.py"]', SINGLE % '["src/export/"]'])
    crew = Crew()
    app = _app(fake_repo, monkeypatch, crew)
    async with app.run_test(size=SIZE) as pilot:
        view, _sent = await _open(pilot, app)
        w = view.worker
        w.new_task("Build the export API", "Stream a CSV from the API, with paging and a header row for the client")
        assert await _until(pilot, lambda: len(crew.calls) == 1)
        w.new_task("Add a CSV header option", "Let the export choose its header row, with tests for the new flag")
        assert await _until(pilot, lambda: any(t.held_since > 0 for t in w.state.queue))
        await pilot.pause(0.1)
        assert len(crew.calls) == 1                                     # it waits: the first builds its area
        st = w.state
        second = st.queue[0]
        assert second.overlaps[0]["title"] == "Build the export API" and second.decided.startswith("overlap: waits")
        assert any(d.action == "overlap" and "waits for “Build the export API”" in d.why for d in st.decisions())
        crew.finish(0)
        assert await _until(pilot, lambda: len(crew.calls) == 2)        # the first is in review: it goes, told
        first = next(t for t in st.tasks if t.title == "Build the export API")
        assert first.status == "done" and claims.Claims(fake_repo).get(f"camp:{first.id}").status == claims.REVIEW
        assert "## Work on the same files" in crew.calls[1]["prompt"] and "pull/9" in crew.calls[1]["prompt"]
        areas = {c.title: c for c in claims.Claims(fake_repo).load()}
        assert areas["Build the export API"].paths == ["src/export/api.py"] and not areas["Build the export API"].guessed
        assert areas["Add a CSV header option"].guessed
        assert w.settle_prs({first.branch: type("PR", (), {"state": "MERGED", "url": git.pr, "labels": ()})()}) == 1
        assert claims.Claims(fake_repo).get(f"camp:{first.id}") is None                # merged: its area is free


@pytest.mark.asyncio
async def test_flag_never_waits_and_a_wait_ends_after_its_minutes(fake_repo: Path, monkeypatch, steward, git):
    steward(sorts=[SINGLE % '["src/export/"]', SINGLE % '["src/export/csv.py"]'])
    crew = Crew()
    app = _app(fake_repo, monkeypatch, crew, claim_wait=1)
    async with app.run_test(size=SIZE) as pilot:
        view, _sent = await _open(pilot, app)
        w = view.worker
        w.new_task("Build the export", "Stream a CSV from the API, with paging and a header row for the client")
        assert await _until(pilot, lambda: len(crew.calls) == 1)
        w.new_task("Fix the CSV quoting", "Quote the fields with commas in them, and test it with a real file")
        assert await _until(pilot, lambda: any(t.held_since > 0 for t in w.state.queue))
        w.state.queue[0].held_since -= 61                              # its minute is up
        assert w.tick_claims()
        assert await _until(pilot, lambda: len(crew.calls) == 2)
        assert any("goes on, flagged" in d.why for d in w.state.decisions())


@pytest.mark.asyncio
async def test_a_plan_leaves_its_design_brief_on_the_branch_and_claims_its_parts(fake_repo: Path, monkeypatch,
                                                                              steward, git):
    text = json.dumps({"subtasks": [sub("api", touches=["src/export/api.py"]), sub("docs", touches=["docs/export.md"])],
                       "design": {"why": "people ask for it", "invariants": ["it streams"]}})
    s = steward(plans=[text])
    crew = Crew()
    app = _app(fake_repo, monkeypatch, crew)
    async with app.run_test(size=SIZE) as pilot:
        view, _sent = await _open(pilot, app)
        _hard(view)
        assert await _until(pilot, lambda: len(crew.calls) == 2)
        st = view.state
        parent = next(t for t in st.tasks if t.plan)
        assert parent.design == "docs/design/build-the-export.md"
        [(branch, path, brief)] = git.committed
        assert (branch, path) == (parent.branch, parent.design)
        assert "## Invariants\n\n- it streams" in brief and HARD.splitlines()[0] in brief
        assert "`design` object" in next(p for p in s.prompts if "PLAN the task" in p)
        assert "## The design brief" in crew.calls[0]["prompt"] and parent.design in crew.calls[0]["prompt"]
        c = claims.Claims(fake_repo).get(f"camp:{parent.id}")
        assert c.paths == ["src/export/api.py", "docs/export.md", parent.design] and c.brief == parent.design
        crew.finish(0)
        crew.finish(1)
        assert await _until(pilot, lambda: parent.status == "done")
        done = claims.Claims(fake_repo).get(f"camp:{parent.id}")          # its branch waits to be merged
        assert done.status == claims.REVIEW and done.paths == ["app.py"] and done.brief == parent.design


@pytest.mark.asyncio
async def test_a_plan_against_a_design_waits_in_chains(fake_repo: Path, monkeypatch, steward, git):
    _level(autonomy.CHAINS, False, monkeypatch)
    (fake_repo / "docs" / "design").mkdir(parents=True)
    (fake_repo / "docs" / "design" / "build-the-export.md").write_text(BRIEF, encoding="utf-8")
    text = json.dumps({"subtasks": [sub("api", touches=["src/export/api.py"]), sub("ui", touches=["src/ui/x.js"])],
                       "conflicts": [{"with": "docs/design/build-the-export.md", "why": "it builds JSON in memory"}]})
    s = steward(sorts=['{"kind": "plan", "touches": ["src/export/"]}'], plans=[text])
    crew = Crew()
    app = _app(fake_repo, monkeypatch, crew)
    async with app.run_test(size=SIZE) as pilot:
        view, sent = await _open(pilot, app)
        _hard(view, "Export as JSON")
        assert await _until(pilot, lambda: view.state.asked)
        task = view.state.asked[0]
        assert task.ask_kind == "conflict" and "it builds JSON in memory" in task.question
        assert "## Designs this touches" in next(p for p in s.prompts if "PLAN the task" in p)
        assert "never builds it in memory" in next(p for p in s.prompts if "PLAN the task" in p)
        assert any(p.mode == "pool.question" for p in sent) and crew.calls == []
        assert not view.worker.tick_asks(now=time.time() + 3600)                   # ⛓️: no timer
        view.worker.answer(task.id, "")
        assert await _until(pilot, lambda: len(crew.calls) == 2)
        assert task.status == "planned" and task.against[0]["with"] == "docs/design/build-the-export.md"


@pytest.mark.asyncio
async def test_unchained_a_plan_against_a_design_goes_on_flagged(fake_repo: Path, monkeypatch, steward, git):
    _level(autonomy.FREE, False, monkeypatch)
    text = json.dumps({"subtasks": [sub("api", touches=["src/a/x.py"]), sub("ui", touches=["src/b/y.js"])],
                       "conflicts": [{"with": "docs/design/x.md", "why": "no"}]})
    steward(plans=[text])
    crew = Crew()
    app = _app(fake_repo, monkeypatch, crew)
    async with app.run_test(size=SIZE) as pilot:
        view, _sent = await _open(pilot, app)
        _hard(view)
        assert await _until(pilot, lambda: len(crew.calls) == 2)
        assert not view.state.asked and any(d.action == "design" and "goes against" in d.why
                                            for d in view.state.decisions())


@pytest.mark.asyncio
async def test_the_review_keeps_a_brief_true(fake_repo: Path, monkeypatch, steward, git):
    (fake_repo / "docs" / "design").mkdir(parents=True)
    (fake_repo / "docs" / "design" / "build-the-export.md").write_text(BRIEF, encoding="utf-8")
    git.files = ("src/export/csv.py",)
    s = steward(sorts=[SINGLE % '["src/export/csv.py"]', SINGLE % '["src/export/csv.py"]'],
                verdicts=["ACCEPT\nDESIGN: unchanged", "ACCEPT"])
    crew = Crew()
    app = _app(fake_repo, monkeypatch, crew)
    async with app.run_test(size=SIZE) as pilot:
        view, _sent = await _open(pilot, app)
        w = view.worker
        w.new_task("Fix the CSV quoting", "Quote the fields with commas in them, and test it with a real file")
        assert await _until(pilot, lambda: len(crew.calls) == 1)
        assert "## Designs this touches" in crew.calls[0]["prompt"]           # the ork reads the brief it meets
        crew.finish(0)
        first = w.state.tasks[0]
        assert await _until(pilot, lambda: first.status == "done")
        review = next(p for p in s.prompts if "## The orc's report" in p)
        assert "`DESIGN: unchanged`" in review and "never builds it in memory" in review
        assert first.designs == [{"path": "docs/design/build-the-export.md", "state": "unchanged"}]
        w.new_task("Speed up the CSV", "Write the rows in batches of a thousand, measure before and after it")
        assert await _until(pilot, lambda: len(crew.calls) == 2)
        crew.finish(1)
        second = next(t for t in w.state.tasks if t.title == "Speed up the CSV")
        assert await _until(pilot, lambda: second.status == "done")
        assert second.designs[0]["state"] == "not confirmed"
        assert any(d.action == "design" and "design not confirmed" in d.why for d in w.state.decisions())


@pytest.mark.asyncio
async def test_the_review_says_when_two_branches_would_conflict(fake_repo: Path, monkeypatch, steward, git):
    git.files = ("src/export/csv.py",)
    s = steward(sorts=[SINGLE % '["src/export/csv.py"]'])
    other = claims.Claim("pool2:old", "pool2", "old", "Rewrite the CSV writer", ["src/export/csv.py"],
                         branch="pool/pool2/old", status=claims.REVIEW, pr="https://github.com/o/r/pull/3",
                         since="2026-10-01T10:00:00")
    claims.Claims(fake_repo).put(other)
    crew = Crew()
    app = _app(fake_repo, monkeypatch, crew)
    async with app.run_test(size=SIZE) as pilot:
        view, _sent = await _open(pilot, app)
        w = view.worker
        w.new_task("Fix the CSV quoting", "Quote the fields with commas in them, and test it with a real file")
        assert await _until(pilot, lambda: len(crew.calls) == 1)               # a PR in review: no wait
        task = w.state.tasks[0]
        git.clashes = {frozenset((task.branch, "pool/pool2/old")): ["src/export/csv.py"]}
        assert "Rewrite the CSV writer" in crew.calls[0]["prompt"]
        crew.finish(0)
        assert await _until(pilot, lambda: task.status == "done")
        review = next(p for p in s.prompts if "## The orc's report" in p)
        assert "they conflict in src/export/csv.py" in review
        assert task.overlaps[0]["conflicts"] == ["src/export/csv.py"]
        assert any("it conflicts in src/export/csv.py" in d.why for d in w.state.decisions())


def test_claims_off_in_the_sandbox_and_by_the_setting(fake_repo: Path, monkeypatch):
    class W:
        simulated, config = True, {}
    assert BarracksWorker.claims_mode.fget(W()) == "off"
    W.simulated, W.config = False, {"claims": "flag"}
    assert BarracksWorker.claims_mode.fget(W()) == "flag"
    W.config = {"claims": "nonsense"}
    assert BarracksWorker.claims_mode.fget(W()) == "wait"
    assert bk.PoolTask("x", "t", "t").overlaps == [] and threading


def test_the_window_shows_the_areas_in_work_and_a_tasks_overlaps(fake_repo: Path):
    from tests.test_gui_pool_clan import _host, _raised
    host = _host(fake_repo)
    bid = _raised(host, "barracks", max_orcs=2)
    claims.Claims(fake_repo).put(claims.Claim("pool2:old", "pool2", "old", "Rewrite the CSV writer",
                                              ["src/export/csv.py"], status=claims.REVIEW,
                                              pr="https://github.com/o/r/pull/3", since=claims.now()))
    w = host.town.worker(bid)
    task = bk.PoolTask("t1", "Fix the CSV quoting", "…", overlaps=[{"key": "pool2:old", "title": "Rewrite the CSV writer",
                                                                     "paths": ["src/export/csv.py"], "status": "review"}])
    w.state.tasks.append(task)
    d = host.detail(bid)["data"]
    [area] = d["areas"]
    assert area["title"] == "Rewrite the CSV writer" and not area["mine"] and area["status"] == "review"
    row = next(t for t in d["tasks"] if t["id"] == "t1")
    assert row["overlaps"][0]["title"] == "Rewrite the CSV writer" and row["overlaps"][0]["conflicts"] == []
    assert row["held"] is False and row["design"] == "" and row["against"] == []
