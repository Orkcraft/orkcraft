"""A day's findings go to the Test bench and are measured there (gui/day_try.py; docs/design/improve-buildings.md §13).
The keeper's model and the runs are fakes."""
from __future__ import annotations

import json

from orkcraft.core import runners
from orkcraft.gui import day_try, lab_runs
from orkcraft.realm import day_review
from tests.test_gui_bench import _raised, _road, _until, asked, host  # noqa: F401  (fixtures)

DAY = "2026-10-11"


def _town(host):
    lab, pool = _raised(host, "lab"), _raised(host, "barracks", worktrees=False)
    _road(host, pool, lab, "pool.done")
    host.detail(lab)
    w = host.town.worker(lab)
    review = day_review.Review(DAY, findings=[
        day_review.Finding("mechanic", pool, "the wiki goes whole into every call", "27k tokens", "prompt",
                           "send the wiki once", ["H4"]),
        day_review.Finding("farseer", "tower", "spam was kept", "sorted by hand", "rule", "drop spam", ["H1"]),
        day_review.Finding("mechanic", pool, "two roads where one would do", "", "road", "drop one", ["H5"]),
    ])
    day_review.save(host.town.repo_root, review)
    return w, pool


def test_each_finding_says_where_it_can_be_tried_and_the_night_hands_them_over(host, monkeypatch):
    w, pool = _town(host)
    rows = day_try.findings(host, DAY)
    assert [(r["n"], r["bench"], r["can"]) for r in rows] == [
        (0, w.title, ""), (1, "", "No Test bench tests it: raise one (Build → Test bench) and pick it"),
        (2, "", "Roads change on the map, not on a Test bench")]
    assert rows[0]["who"] == "the Mechanic" and rows[0]["title"] == host.town.title_of(pool)
    assert day_try.hand(host, DAY) == 1
    [p] = w.state["proposals"][pool]["items"]
    assert (p["id"], p["area"], p["title"]) == (f"d{DAY}-0", "prompt", "the wiki goes whole into every call")
    assert p["from"] == f"Mechanic, in the logs of {DAY} (H4)" and p["detail"] == "send the wiki once — 27k tokens"
    w.set_proposals(pool, [{"id": "p0", "area": "code", "title": "Cache the plan", "detail": "", "where": "",
                            "effect": ""}])                       # the Mechanic writes its own again: the day's stays first
    assert [x["id"] for x in w.state["proposals"][pool]["items"]] == [f"d{DAY}-0", "p0"]


def test_a_finding_is_tried_on_the_virtual_building_and_the_cases_run(host, monkeypatch):
    w, pool = _town(host)
    w.add_cases(pool, [{"id": "c1", "title": "Bug 1", "text": "Fix bug 1"}])
    config = {**host.town.spec_of(pool)["config"], "orders": "Send the wiki once."}
    monkeypatch.setattr(runners, "KEEPER_RUNNER", lambda prompt: (json.dumps({"value": config, "why": "once"}), 0.01))
    ran = []
    monkeypatch.setattr(lab_runs.LabRuns, "run", lambda self, w_, s, case_ids=None, **k: ran.append(case_ids))
    said = day_try.attempt(host, DAY, 0)
    assert said.startswith(f"{w.title} is trying it on the virtual") and "runs its 1 case" in said
    assert _until(lambda: ran == [["c1"]])
    [change] = w.changes_of(pool)
    assert change["proposal"] == f"d{DAY}-0" and host.town.spec_of(pool)["config"].get("orders") != "Send the wiki once."
    assert day_review.load(host.town.repo_root, DAY).findings[0].tried
    assert host.command("improve.try", {"day": DAY, "n": 1}) == {
        "error": "No Test bench tests it: raise one (Build → Test bench) and pick it"}
    assert host.command("improve.findings", {"day": DAY})["findings"][0]["tried"]


def test_the_nights_reading_goes_to_the_test_bench_and_the_morning_says_so(host):
    w, pool = _town(host)
    host.day_review._handed(day_review.load(host.town.repo_root, DAY))
    [line] = host.day_review.morning()
    assert line.startswith(f"The Mechanic and the Farseer read {DAY}")
    assert line.endswith("; 1 went to the Test bench to be tried — Improve goes through them")
    assert w.state["proposals"][pool]["items"][0]["id"] == f"d{DAY}-0"
