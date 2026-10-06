"""Showcase sandbox (T1099): valid, isolated, alive; agents never call a model in the demo."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from orkcraft import demo, scroll as ts
from orkcraft.demo.scenarios import SCENARIOS
from orkcraft.realm import masonry, roads
from orkcraft.realm.pipes import Payload


def test_sandbox_is_valid_and_complete(tmp_path: Path):
    root = demo.build(tmp_path / "demo")
    scroll, problems = ts.load(root / ".orkcraft.json", {})
    assert problems == [] and [o.hotkey for o in scroll.orkspaces] == [f"F{i}" for i in range(1, 9)]
    specs, spec_problems = masonry.load_specs(root)
    assert len(specs) == 32 and spec_problems == []
    for sc in SCENARIOS:
        placed = scroll.buildings_in(sc["id"])
        assert len(placed) == 4 and all(b.frac for b in placed)
        labels = [r.label for b in placed for r in b.roads]
        assert labels == [r[3] for r in sc["roads"]] or sorted(labels) == sorted(r[3] for r in sc["roads"])
        assert any(h.kind == "chain" for b in placed for h in b.garrison.handlers)
        assert any(h.uses_model for b in placed for h in b.garrison.handlers)
        assert all(b.garrison.steward for b in placed)
        for spec in sc["buildings"]:
            for entry in spec["data"]:
                from orkcraft.demo.graph import Graph
                data = masonry.fetch(entry["source"], entry.get("params"), root, Graph(root))
                assert not data.error and (data.rows or data.text), (spec["id"], entry)
    assert len(json.loads((root / demo.SAMPLES).read_text())) == 10


def test_build_refuses_a_foreign_folder_and_keeps_an_existing_demo(tmp_path: Path):
    foreign = tmp_path / "work"
    foreign.mkdir()
    (foreign / "notes.md").write_text("mine")
    with pytest.raises(ValueError, match="not an orkcraft demo"):
        demo.build(foreign)
    root = demo.build(tmp_path / "demo")
    (root / "extra.md").write_text("x")
    assert demo.build(root) == root and (root / "extra.md").exists()        # kept
    assert demo.build(root, reset=True) == root and not (root / "extra.md").exists()


@pytest.mark.asyncio
async def test_the_demo_app_is_alive_and_agents_stay_idle(tmp_path: Path, monkeypatch):
    from orkcraft.app import OrkcraftApp
    from orkcraft.screens.custom_view import CustomBuildingView

    root = demo.build(tmp_path / "demo")
    calls = []
    monkeypatch.setattr(roads, "run_agent", lambda *a: calls.append(a) or ("x", 1.0))
    app = OrkcraftApp(repo_root=root, auto_commit=False, layout_file=root / ".orkcraft.json", demo=True)
    async with app.run_test(size=(200, 52)) as pilot:
        for _ in range(5):
            await pilot.pause()
        assert app.scroll.active_orkspace.name == "Feat-OAuth"
        spire = app.desktop.get_window("oauth_spire").query_one(CustomBuildingView)
        assert "Reviewer" in str(spire._incoming[0].render())                   # prepared agent result
        app.roads.emit(Payload("text", "1 failing", "oauth_forge", "on_task_completed", "Smith · done"))
        app.roads.emit(Payload("node", "T2101", "oauth_forge", "on_selection_change", "T2101"))
        for _ in range(3):
            await pilot.pause()
        lab = app.desktop.get_window("oauth_lab").query_one(CustomBuildingView)
        assert "pytest --lf" in lab._incoming[1].source                          # the chain ran for real
        app.roads.tick(app.roads._clock() + 3600)
        await pilot.pause()
        assert calls == [] and any(r.outcome == "no_gold" for r in app.roads.runs)   # no model in the demo
        await pilot.press("f8")
        for _ in range(3):
            await pilot.pause()
        assert app.scroll.active_orkspace.name == "Solo-SaaS"
        assert app.worktree_marks["solo_saas"] == "⎇ feat/stripe-billing"


def test_cli_builds_the_demo(tmp_path: Path, monkeypatch):
    from orkcraft import cli
    ran = []
    monkeypatch.setattr(cli.OrkcraftApp, "run", lambda self: ran.append(self))
    assert cli.main(["--demo", str(tmp_path / "d"), "tui"]) == 0
    assert ran and ran[0].demo and ran[0].repo_root == (tmp_path / "d").resolve()


def test_managers_set_is_separate_and_wired(tmp_path: Path):
    root = demo.build(tmp_path / "m", set_name="managers")
    scroll, problems = ts.load(root / ".orkcraft.json", {})
    assert problems == [] and [o.name for o in scroll.orkspaces] == ["1on1-Prep"]
    note = scroll.building("em_note")
    assert sorted((r.source, r.label, r.handler) for r in note.roads) == [
        ("em_calendar", "on_meeting", "agenda"), ("em_jira", "on_jira_activity", "agenda"), ("em_mail", "on_mail", "agenda")]
    assert note.frac == [0.0, 0.0, 0.56, 1.0]                              # the note left, sources right
    from orkcraft.demo.graph import Graph
    g = Graph(root)
    lists = {tag: [r.id for r in masonry.fetch("graph_nodes", {"tag": tag}, root, g).rows]
             for tag in ("one_on_one_cal", "one_on_one_mail", "one_on_one_jira")}
    assert [len(v) for v in lists.values()] == [3, 3, 4]
    # the Agenda chain reruns with the latest of all three roads
    from orkcraft.realm import roads as rd
    outs = []
    engine = rd.Engine(lambda: scroll, root, deliver=lambda *a: None, on_output=lambda t, o, ti, md, *_: outs.append(md),
                       meta=lambda p: {"title": g.get_entity(p.value).title, "status": g.get_entity(p.value).status})
    for src, nid in (("em_calendar", "T3101"), ("em_mail", "T3112"), ("em_jira", "T3122")):
        engine.emit(Payload("node", nid, src, "on_selection_change"))
    assert outs[-1].count("\n") == 2 and "1on1 with Alex Kim" in outs[-1] and "PAY-431" in outs[-1]


def test_feature_shots_pass_the_real_checks(tmp_path: Path):
    """The scripted answers of the feature shots go through the real validators, no model."""
    from orkcraft.demo import features as ft
    from orkcraft.realm import recruiter, steward
    root = demo.build(tmp_path / "demo")
    scroll, _ = ts.load(root / ".orkcraft.json", {})
    rec = recruiter.recruit("done tasks as one line", scroll, "oauth_spire", runner=ft.runner_of([ft.RECRUITER_ANSWER]))
    assert rec.ok and rec.orc["kind"] == "chain" and len(rec.attempts) == 1
    assert masonry.validate_spec(ft.ARTISAN_ANSWER, root, {s.id for s in scroll.buildings}) == []
    ft.seed_steward_examples(root)
    report = steward.watch(root, scroll, "dc_loot", sessions=[], runner=ft.runner_of([ft.STEWARD_PROPOSAL]))
    [p] = report.proposals
    assert [f.kind for f in report.findings] == ["repeats"] and p.ready and p.replay.exact == 6


@pytest.mark.asyncio
async def test_dashboard_set_typed_buildings_and_no_agent_runs(tmp_path: Path, monkeypatch):
    import subprocess
    from orkcraft.app import OrkcraftApp
    from orkcraft.realm import jobs
    from orkcraft.screens.typed.generator_view import GeneratorView
    from orkcraft.screens.typed.git_view import GitView
    from orkcraft.screens.typed.pool_view import PoolView
    from orkcraft.screens.typed.tasks_view import TasksView
    from orkcraft.screens.typed.team_view import TeamView

    root = demo.build(tmp_path / "dash", set_name="dashboard")
    scroll, problems = ts.load(root / ".orkcraft.json", {})
    assert problems == [] and [o.name for o in scroll.orkspaces] == ["My Day", "Agent Yard", "Gates", "Library",
                                                                 "Front Desk", "Meetings"]
    specs, spec_problems = masonry.load_specs(root)
    assert spec_problems == [] and len(specs) == 35 and all(s.get("type") for s in specs)
    from orkcraft.realm import catalog
    # every type the catalog builds; Lake is the town's window, not a building
    assert {s["type"] for s in specs} == set(catalog.TYPES) - {"town_hall", "custom", "lake"}
    branches = subprocess.run(["git", "branch", "--format=%(refname:short)"], cwd=root, capture_output=True,
                              text=True).stdout.split()
    assert sorted(branches) == ["docs/barracks", "feature/login", "feature/pricing-page", "fix/parser", "main"]

    calls = []
    monkeypatch.setattr(roads, "run_agent", lambda *a, **k: calls.append(a) or ("x", 1.0, None))
    monkeypatch.setattr(jobs, "run_work", lambda *a, **k: calls.append(a) or ("x", 1.0, None, ""))
    app = OrkcraftApp(repo_root=root, auto_commit=False, layout_file=root / ".orkcraft.json", demo=True)
    async with app.run_test(size=(200, 52)) as pilot:
        for _ in range(5):
            await pilot.pause()
        assert app.desktop.get_window("todo").query_one(TasksView).mini_status()[0] == "To Do 3"
        await pilot.press("f2")
        for _ in range(10):
            await pilot.pause(0.05)
        git = app.desktop.get_window("branches").query_one(GitView)
        assert git.snap is not None and {b.name for b in git.snap.branches} == {
            "main", "feature/login", "fix/parser", "feature/pricing-page", "docs/barracks"}
        gen = app.desktop.get_window("outputs").query_one(GeneratorView)
        assert {g.path for g in gen.rows} == {"docs/release-notes.md", "src/billing.py", "web/index.html",
                                              "web/styles.css", "web/pricing.html"}
        team = app.desktop.get_window("council").query_one(TeamView)
        seeded = [d for d in team.history if d.title == "v0.2 release plan"]          # the Barracks' resumed work
        assert [(d.outcome, d.cycle) for d in seeded] == [("approved", 2), ("rework", 1)]   # may be reviewed since
        camp = app.desktop.get_window("camp").query_one(PoolView)
        assert [o.name for o in camp.state.orcs] == ["Grub", "Mogka", "Snaga"]
        camp.add_task("Write the changelog", "Write the changelog for v0.2")     # simulated work, no model
        for _ in range(60):
            await pilot.pause(0.05)
            if all(o.status == "idle" for o in camp.state.orcs) and not camp.state.queue:
                break
        assert calls == []
        assert any("demo — simulated" in t.result for t in camp.state.tasks)


def test_dashboard_seeds_the_t1108_pipeline(tmp_path):
    from orkcraft import demo
    from orkcraft.realm import fastpath, feedback, optimize, weekly, workshop

    root = demo.build(tmp_path / "dash", set_name="dashboard")
    assert workshop.load_script(root, "counter", "python").startswith("import json")
    runs = workshop.sandbox(workshop.load_script(root, "counter", "python"), "python",
                            workshop.load_blueprint(root, "counter")["mocks"])
    assert [r.outcome for r in runs] == ["done", "escalated"]
    assert {r["decision"] for r in fastpath.recent(root)} == {"approved", "rejected", "overridden"}
    assert feedback.incidents(root)[0].blamed == {"days": 1.0} and feedback.scores(root)["counter"]["likes"] == 1
    assert optimize.pending(root)[0].building == "camp"
    assert [i.applicable for i in weekly.latest(root).items] == [True, True, False]


@pytest.mark.asyncio
async def test_the_library_scene(tmp_path: Path, monkeypatch):
    """F4: three seeded wikis, one code change not taken in yet, tasks passing through the Code Wiki."""
    from orkcraft.app import OrkcraftApp
    from orkcraft.realm import jobs, pipes, wiki
    from orkcraft.screens.typed.knowledge_view import KnowledgeView

    root = demo.build(tmp_path / "dash", set_name="dashboard")
    for topic in ("codebase", "team", "design"):
        assert (root / "llm-wiki" / topic / "WIKI.md").is_file()
    calls = []
    monkeypatch.setattr(jobs, "run_work", lambda *a, **k: calls.append(a) or ("x", 1.0, None, ""))
    app = OrkcraftApp(repo_root=root, auto_commit=False, layout_file=root / ".orkcraft.json", demo=True)
    async with app.run_test(size=(200, 52)) as pilot:
        await pilot.press("f4")
        for _ in range(10):
            await pilot.pause(0.05)
        code = app.desktop.get_window("code_wiki").query_one(KnowledgeView)
        team = app.desktop.get_window("team_wiki").query_one(KnowledgeView)
        design = app.desktop.get_window("design_wiki").query_one(KnowledgeView)
        assert code.pending.changed == ["src/billing.py"] and code.pending.new == ["docs/release-notes.md"]
        assert not team.pending and not design.pending and design.status() == "FRESH"
        assert wiki.page_count(code.pages) == 5 and code.manual == {"pages/decisions/prices-in-billing.md"}
        assert team.manual == {"pages/onboarding/first-day.md"}
        assert code.hut_lines([16])[0] == "codebase: 5 pages" and "lint: 1" in code.hut_lines([16])
        sent = []
        monkeypatch.setattr(app.roads, "emit", lambda payload, meta=None: sent.append(payload) or [])
        app.deliver_payload("code_wiki", pipes.Payload(pipes.TEXT, "Add yearly billing", "lib_tasks", "tasks.created",
                                                       "Add yearly billing"), "Add yearly billing", "Add yearly billing")
        assert sent[-1].mode == "knowledge.chunks" and "pages/modules/index.md" in sent[-1].value
        assert code.ingest() and code.running == "ingest"                 # simulated: no model
        for _ in range(60):
            await pilot.pause(0.05)
            if not code.running:
                break
        assert calls == [] and not code.pending
