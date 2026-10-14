"""The Elders improve the town at night (docs/design/improve-buildings.md §8): the Mechanic tries a proposal on the
virtual building, runs the cases again and keeps it by the autonomy; the Alchemist lays a type's cards out. The model
calls and the runs are fakes here."""
from __future__ import annotations

import json

import pytest

from orkcraft import autonomy
from orkcraft.core import runners
from orkcraft.gui import improve_night, lab_runs
from orkcraft.realm import card_docs, evolution
from tests.test_gui_bench import _raised, _road, _until, asked, host  # noqa: F401  (fixtures)

pytestmark = pytest.mark.usefixtures("night_on")     # the night's work, on as a person turns it on


def test_better_is_the_goals_metric_moved_with_no_loss_of_quality():
    before = {"tokens": -0.10, "time": 0.0, "quality": 0.5}
    assert improve_night.better(before, {"tokens": -0.30, "time": 0.0, "quality": 0.5}, "tokens") == (True, True)
    assert improve_night.better(before, {"tokens": -0.30, "time": 0.0, "quality": 0.0}, "tokens") == (False, False)
    assert improve_night.better(before, {"tokens": -0.11, "quality": 0.5}, "tokens") == (False, False)   # within noise
    assert improve_night.better(before, {"tokens": 0.2, "quality": 1.0}, "quality") == (True, False)


def _night(host, monkeypatch, level: int, tokens_after: float):
    """A Test bench on an Agent pool that ran its two cases by day; the night's model and runs are fakes."""
    lab, pool = _raised(host, "lab"), _raised(host, "barracks", worktrees=False)
    _road(host, pool, lab, "pool.done")
    host.detail(lab)
    w = host.town.worker(lab)
    w.set_goal("Spend fewer tokens than the bare tool")
    w.add_cases(pool, [{"id": "c1", "title": "Bug 1", "text": "Fix bug 1"}, {"id": "c2", "title": "Bug 2", "text": "Fix 2"}])
    day = {"scheme": {"cost": 0.1, "tokens": 900}, "bare": {}, "at": "2026-10-11T12:00:00", "tokens": -0.1,
           "time": 0.0, "quality": 0.0}
    w.state["results"][pool] = {"c1": dict(day), "c2": dict(day)}
    monkeypatch.setattr(lab_runs.jobs, "run_read", lambda *a, **k: (json.dumps({"proposals": [
        {"area": "prompt", "title": "Shorter orders", "detail": "one line", "where": "Agent pool"}]}), 0.01, 100, ""))
    config = {**host.town.spec_of(pool)["config"], "orders": "Answer in one line."}
    monkeypatch.setattr(runners, "KEEPER_RUNNER", lambda prompt: (json.dumps({"value": config, "why": "one line"}), 0.01))

    def run(self, w_, s, case_ids=None, then_propose=False, then=None):
        w_.state["results"][s["id"]] = {c: {**day, "tokens": tokens_after, "at": "2026-10-12T03:00:00"} for c in case_ids}
        host.town.call(then)

    monkeypatch.setattr(lab_runs.LabRuns, "run", run)
    host.town.machine.autonomy = level
    host.nightly.improve.tick(quiet=True, now=1e9)
    assert _until(lambda: not host.nightly.improve.busy)
    return w, pool, host.nightly.improve.morning()


def test_unchained_the_mechanic_saves_what_is_better_on_probation(host, monkeypatch):
    w, pool, said = _night(host, monkeypatch, autonomy.FREE, tokens_after=-0.4)
    assert host.town.spec_of(pool)["config"]["orders"] == "Answer in one line." and w.changes_of(pool) == []
    assert any(c.building == pool and c.by == "orcs" and c.status == "probation" for c in evolution.load(host.town.repo_root))
    assert len(said) == 1 and "saved" in said[0] and said[0].startswith("Mechanic: ")


def test_in_chains_a_better_change_waits_on_the_virtual_building(host, monkeypatch):
    w, pool, said = _night(host, monkeypatch, autonomy.CHAINS, tokens_after=-0.4)
    assert host.town.spec_of(pool)["config"].get("orders") != "Answer in one line."
    assert len(w.changes_of(pool)) == 1 and "waits on the virtual building" in said[0]


def test_a_change_that_is_not_better_is_taken_back(host, monkeypatch):
    w, pool, said = _night(host, monkeypatch, autonomy.FREE, tokens_after=-0.05)
    assert w.changes_of(pool) == [] and "not better" in said[0]
    assert host.town.spec_of(pool)["config"].get("orders") != "Answer in one line."


def test_a_bench_the_night_cannot_afford_is_left_for_another(host, monkeypatch):
    from orkcraft.realm import fastpath
    lab, pool = _raised(host, "lab"), _raised(host, "barracks", worktrees=False)
    _road(host, pool, lab, "pool.done")
    host.detail(lab)
    w = host.town.worker(lab)
    w.set_goal("fewer tokens")
    w.add_cases(pool, [{"id": "c1", "title": "Bug", "text": "Fix"}])
    w.state["results"][pool] = {"c1": {"scheme": {"cost": 5.0, "tokens": 1}, "bare": {}, "tokens": 0.0}}
    fastpath.save_settings(host.town.repo_root, {"improve_per_night_usd": 1.0})
    host.nightly.improve.tick(quiet=True, now=1e9)
    assert not host.nightly.improve.busy and "another night" in host.nightly.improve.morning()[0]


@pytest.mark.parametrize("level,applied", [(autonomy.FREE, True), (autonomy.CLOCK, False)])
def test_the_alchemist_lays_a_types_cards_out(host, monkeypatch, level, applied):
    bench, _pool = _raised(host, "ux_lab"), _raised(host, "barracks", worktrees=False)
    host.command("act", {"id": bench, "act": "pick", "args": {"type": "barracks"}})
    doc = card_docs.default("barracks")
    doc["sizes"]["s"]["parts"] = [{"id": "big"}]
    monkeypatch.setattr(runners, "STEWARD_RUNNER", lambda prompt: (json.dumps(doc), 0.01))
    host.town.machine.autonomy = level
    host.nightly.improve.tick(quiet=True, now=1e9)
    assert _until(lambda: not host.nightly.improve.busy)
    said = host.nightly.improve.morning()
    assert said and said[0].startswith("Alchemist: ")
    assert (card_docs.load("barracks") == doc) is applied
    assert (host.town.worker(bench).card is not None) is (not applied)


def test_the_night_proposes_from_what_was_found_and_works_on_the_worst_bench_first(host, monkeypatch):
    from orkcraft.core import buildings as core_buildings
    from orkcraft.core import delivery
    from orkcraft.realm import lab_cases, pipes
    quiet_lab, quiet_pool = _raised(host, "lab"), _raised(host, "barracks", worktrees=False)
    _road(host, quiet_pool, quiet_lab, "pool.done")
    lab, pool = _raised(host, "lab"), _raised(host, "barracks", worktrees=False)
    _road(host, pool, lab, "pool.done")
    delivery.deliver(host.town, pool, pipes.Payload(pipes.TEXT, "Write a slugify with tests", "pit", "push"))
    core_buildings.dislike(host.town, pool, "logic", "no tests written")
    host.detail(lab)                                                    # it takes the 👎 in
    order = [b.id for b in host.nightly.improve._in_order(host.bench) if b.id in (lab, quiet_lab)]
    assert order == [lab, quiet_lab]                                   # the one with something wrong first
    seen = []
    monkeypatch.setattr(lab_runs.jobs, "run_read", lambda tool, prompt, *a, **k: (seen.append(prompt) or
                                                                                  '{"proposals": []}', 0.0, 0, ""))
    w = host.town.worker(lab)
    host.bench.lab.propose(w, w.subject())
    assert _until(lambda: seen)
    assert "The person disliked it — 👎" in seen[0] and "no tests written" in seen[0]
    assert lab_cases.DEFAULT_GOAL in seen[0]                           # no goal written: the default one
