"""Showcase sandbox (T1099): valid, isolated, alive; agents never call a model in the demo."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from orkcraft import demo, scroll as ts
from orkcraft.demo.scenarios import SCENARIOS
from orkcraft.realm import masonry
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
    [p] = [x for x in report.proposals if x.type == "demote"]        # (and a free "hand": its agent is on the steward's tool)
    assert [f.kind for f in report.findings] == ["repeats", "hand"] and p.ready and p.replay.exact == 6


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
