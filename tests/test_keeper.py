"""The keeper of a building (core/keeper.py, docs/design/building-views.md §2): plain words in, the building's
rules or settings out — checked against its type, taken by the person, taken back by Revert."""
from __future__ import annotations

import datetime as dt
import json

import pytest

from orkcraft.core import buildings, keeper, runners
from orkcraft.core.town import Town
from orkcraft.gui.host import CommandError, Host
from orkcraft.realm import checkpoint, chronicles, watch, workshop


def _answers(*answers, cost=0.01):
    """A fake model: each call takes the next answer; the prompts it saw are kept on it."""
    left = list(answers)

    def run(prompt: str):
        run.prompts.append(prompt)
        a = left.pop(0)
        return (a if isinstance(a, str) else json.dumps(a)), cost
    run.prompts = []
    return run


def _signpost(town: Town):
    return buildings.raise_spec(town, buildings.type_spec(town, "signpost"))


def test_the_signpost_keeper_writes_rules_checked_by_the_type(fake_repo, isolated_layout_file):
    town = Town(fake_repo)
    built = _signpost(town)
    spec = town.custom_specs[built.id]
    run = _answers({"value": ["bugs contains crash"], "why": "x"},                    # not a rule: sent back
                   {"value": ["bugs: contains crash", "rest: else"], "why": "crashes to bugs", "answer": "done"})
    p = keeper.ask(fake_repo, spec, town.scroll, built.id, "crashes go to bugs, the rest elsewhere", runner=run)
    assert p.error == "" and p.kind == "rules" and p.attempts == 2 and p.cost_usd == pytest.approx(0.02)
    assert "REJECTED" in run.prompts[1] and "contains <text>" in run.prompts[0]        # its language, its problems
    assert p.changes and p.diff(keeper.subject_of(spec)) == [["+", "bugs: contains crash"], ["+", "rest: else"]]
    assert keeper.apply(town, built.id, p, "crashes go to bugs") == []
    assert town.custom_specs[built.id]["config"]["rules"] == ["bugs: contains crash", "rest: else"]
    saved = json.loads((fake_repo / ".orkcraft" / "buildings" / f"{built.id}.json").read_text())
    assert saved["config"]["rules"] == ["bugs: contains crash", "rest: else"]
    assert any("keeper" in str(e.get("what")) for e in chronicles.history(fake_repo, built.id))


def test_a_keeper_never_gets_past_the_contract(fake_repo, isolated_layout_file):
    town = Town(fake_repo)
    horn = buildings.raise_spec(town, buildings.type_spec(town, "horn"))
    spec = town.custom_specs[horn.id]
    assert keeper.subject_of(spec).kind == "config"
    bad = {"value": {"volume": "loud", "nonsense": 1}, "why": "louder"}
    p = keeper.ask(fake_repo, spec, town.scroll, horn.id, "louder", runner=_answers(bad, bad, bad))
    assert not p.changes and p.attempts == keeper.MAX_ATTEMPTS and "config" in p.error
    p.after = {"nonsense": 1}                       # a proposal changed after the check is checked again
    assert keeper.apply(town, horn.id, p) and "nonsense" not in (town.custom_specs[horn.id].get("config") or {})


def test_on_a_selection_the_keeper_answers_and_may_change_nothing(fake_repo, isolated_layout_file):
    town = Town(fake_repo)
    built = _signpost(town)
    run = _answers({"value": None, "answer": "This line routes **crashes**."})
    sel = keeper.selection_of({"text": "bugs: contains crash", "path": "docs/notes.md", "lines": [3, 3]})
    p = keeper.ask(fake_repo, town.custom_specs[built.id], town.scroll, built.id, "what does it do?",
                   selection=sel, runner=run)
    assert p.error == "" and not p.changes and "crashes" in p.answer
    assert "docs/notes.md, lines 3–3" in run.prompts[0] and "bugs: contains crash" in run.prompts[0]
    assert keeper.selection_of({"text": "  "}) is None and keeper.selection_of("a line") == {"text": "a line"}


def test_no_budget_no_model_call(fake_repo, isolated_layout_file):
    town = Town(fake_repo)
    built = _signpost(town)
    run = _answers()
    p = keeper.ask(fake_repo, town.custom_specs[built.id], town.scroll, built.id, "x", runner=run, budget_ok=False)
    assert "budget" in p.error and run.prompts == []


def test_a_type_registers_what_its_keeper_writes(fake_repo, isolated_layout_file, monkeypatch):
    town = Town(fake_repo)
    horn = buildings.raise_spec(town, buildings.type_spec(town, "horn"))
    subject = keeper.Subject("quiet", "the quiet hours", lambda spec: "HH:MM-HH:MM",
                             read=lambda spec: (spec.get("config") or {}).get("quiet", ""),
                             write=lambda spec, v: {**spec, "config": {**(spec.get("config") or {}), "quiet": v}},
                             shape=lambda v: None if isinstance(v, str) else "a string", lines=lambda v: [v] if v else [])
    monkeypatch.setitem(keeper.SUBJECTS, "horn", subject)
    p = keeper.ask(fake_repo, town.custom_specs[horn.id], town.scroll, horn.id, "quiet at night",
                   runner=_answers({"value": "22:00-08:00", "why": "nights"}))
    assert p.kind == "quiet" and keeper.apply(town, horn.id, p) == []
    assert town.custom_specs[horn.id]["config"]["quiet"] == "22:00-08:00"


def _wait(host, jid):
    import time
    for _ in range(100):
        job = host.console.jobs.get(jid)
        if job is None or job["state"] != "running":
            return job
        time.sleep(0.05)
    raise AssertionError("the keeper is still writing")


def test_keeper_ask_runs_as_a_job_and_revert_takes_it_back(fake_repo, isolated_layout_file, monkeypatch):
    checkpoint.ensure(fake_repo)
    host = Host(fake_repo, auto_commit=False)
    built = _signpost(host.town)
    host.town.checkpoint("build", built.id, "raised")
    monkeypatch.setattr(runners, "KEEPER_RUNNER",
                        _answers({"value": ["bugs: contains crash"], "why": "crashes to bugs", "answer": "Done."}))
    jid = host.command("keeper.ask", {"id": built.id, "request": "crashes to bugs",
                                      "selection": {"text": "a crash report", "path": "README.md"}})
    job = _wait(host, jid)
    assert job["state"] == "ready" and job["kind"] == "keeper"
    v = host.snapshot()["jobs"][0]["view"]
    json.dumps(v)                                   # it crosses the socket as it is
    assert v["diff"] == [["+", "bugs: contains crash"]] and "<p>Done.</p>" in v["answer"]
    assert v["selection"] == {"text": "a crash report", "path": "README.md"}
    assert host.command("job.accept", {"job": jid}) == "rules" and jid not in host.console.jobs
    assert host.town.custom_specs[built.id]["config"]["rules"] == ["bugs: contains crash"]
    assert host.command("building.revert", {"id": built.id})
    assert not (host.town.custom_specs[built.id].get("config") or {}).get("rules")


def test_keeper_ask_says_why_it_will_not(fake_repo, isolated_layout_file, monkeypatch):
    host = Host(fake_repo, auto_commit=False)
    built = _signpost(host.town)
    with pytest.raises(CommandError):
        host.command("keeper.ask", {"id": built.id, "request": ""})               # nothing asked
    with pytest.raises(CommandError):
        host.command("keeper.ask", {"id": "town_hall", "request": "route bugs"})  # no settings to keep
    host.town.demo = True
    monkeypatch.setattr(runners, "KEEPER_RUNNER", None)
    with pytest.raises(CommandError, match="demo"):                               # never a real model in the demo
        host.command("keeper.ask", {"id": built.id, "request": "route bugs"})
    monkeypatch.setattr(runners, "KEEPER_RUNNER", _answers({"value": None, "answer": "Nothing to do."}))
    job = _wait(host, host.command("keeper.ask", {"id": built.id, "request": "anything?"}))
    assert job["view"]["diff"] == []
    with pytest.raises(CommandError):
        host.command("job.accept", {"job": job["id"]})                            # nothing to apply


OLD_SCRIPT = "import json, sys\nprint(len(json.load(sys.stdin)['value']))\n"
NEW_SCRIPT = "import json, sys\nprint(len(json.load(sys.stdin)['value'].split()))\n"


def _workshop(town: Town):
    workshop.save_script(town.repo_root, "counter", "python", OLD_SCRIPT)
    return buildings.raise_spec(town, {"id": "counter", "type": "workshop", "title": "Counter", "icon": "🛠️",
                                       "summary": "counts a cart", "orc": {"name": "Tinker", "role": "keeps the script"},
                                       "config": {"runtime": "python", "layout": "log", "schedule": "hourly"}})


def test_the_workshop_keeper_writes_its_script_and_schedule(fake_repo, isolated_layout_file):
    town = Town(fake_repo)
    built = _workshop(town)
    spec = town.custom_specs[built.id]
    subject = keeper.subject_of(spec)
    assert subject.kind == "script and schedule"
    run = _answers({"value": {"schedule": "every 15m", "script": "def x(:"}, "why": "x"},          # broken: back
                   {"value": {"schedule": "sometimes", "script": NEW_SCRIPT}, "why": "x"},       # not a schedule: back
                   {"value": {"schedule": "every 15m", "script": NEW_SCRIPT}, "why": "count words, every 15 minutes",
                    "answer": "Done."})
    p = keeper.ask(fake_repo, spec, town.scroll, built.id, "count words, not characters, every 15 minutes", runner=run)
    assert p.error == "" and p.attempts == 3 and p.kind == "script and schedule"
    assert p.before == {"schedule": "hourly", "script": OLD_SCRIPT}                  # the script from its file
    assert "Tinker" in run.prompts[0] and "workshop.alert" in run.prompts[0] and "split()" not in run.prompts[0]
    assert "script: line 1" in run.prompts[1] and "config: schedule" in run.prompts[2]
    diff = p.diff(subject)
    assert ["-", "schedule: hourly"] in diff and ["+", "schedule: every 15m"] in diff
    assert ["+", "  " + NEW_SCRIPT.splitlines()[1]] in diff and [" ", "script:"] in diff
    assert keeper.apply(town, built.id, p, "count words") == []
    w = town.worker(built.id)                       # the worker takes both at once: the spec and the file
    assert w.schedule == "every 15m" and w.source() == NEW_SCRIPT
    assert town.custom_specs[built.id]["config"] == {"runtime": "python", "layout": "log", "schedule": "every 15m"}
    saved = json.loads((fake_repo / ".orkcraft" / "buildings" / f"{built.id}.json").read_text())
    assert saved["config"]["schedule"] == "every 15m"
    start = dt.datetime(2026, 1, 1, 12, 0)
    assert watch.cron_due(w.schedule, start, start + dt.timedelta(minutes=16))
    assert not watch.cron_due(w.schedule, start, start + dt.timedelta(minutes=5))


def test_the_workshop_keeper_may_clear_the_schedule_and_revert_takes_the_script_back(fake_repo, isolated_layout_file,
                                                                                    monkeypatch):
    checkpoint.ensure(fake_repo)
    host = Host(fake_repo, auto_commit=False)
    built = _workshop(host.town)
    host.town.checkpoint("build", built.id, "raised")
    monkeypatch.setattr(runners, "KEEPER_RUNNER", _answers(
        {"value": {"schedule": "", "script": NEW_SCRIPT}, "why": "only on carts, words", "answer": "Done."}))
    job = _wait(host, host.command("keeper.ask", {"id": built.id, "request": "words, and only when a cart comes"}))
    assert job["state"] == "ready" and ["-", "schedule: hourly"] in job["view"]["diff"]
    assert host.command("job.accept", {"job": job["id"]}) == "script and schedule"
    assert "schedule" not in host.town.custom_specs[built.id]["config"]
    assert host.town.worker(built.id).schedule == "" and workshop.load_script(fake_repo, built.id, "python") == NEW_SCRIPT
    assert host.command("building.revert", {"id": built.id})
    assert host.town.custom_specs[built.id]["config"]["schedule"] == "hourly"
    assert workshop.load_script(fake_repo, built.id, "python") == OLD_SCRIPT
