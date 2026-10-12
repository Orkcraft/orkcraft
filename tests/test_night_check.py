"""The Mechanic's night check (gui/night_check.py) and the history it is read against (realm/check_history.py)."""
from __future__ import annotations

import datetime as dt

import pytest

from orkcraft.gui.host import Host
from orkcraft.realm import check, check_history, checkpoint, fastpath


def _data(green: bool, **cases) -> dict:
    return {"green": green, "idle": {"calls": 0},
            "scenarios": [{"id": "mail", "cases": [{"case": cid, **c} for cid, c in cases.items()]}]}


def test_a_case_is_said_worse_or_better_than_last_time_past_the_noise(tmp_path):
    check_history.add(tmp_path, "20261010-020000", _data(
        True, a={"runs": 3, "building": 3, "seconds": 10, "tokens": 1000},
        b={"runs": 3, "building": 2, "seconds": 10, "tokens": 1000},
        c={"runs": 3, "building": 3, "seconds": 10, "tokens": 1000}))
    check_history.add(tmp_path, "20261011-020000", _data(
        False, a={"runs": 3, "building": 2, "seconds": 13, "tokens": 1100},     # fewer passed, slower
        b={"runs": 3, "building": 3, "seconds": 7, "tokens": 1000},             # more passed, faster
        c={"runs": 3, "building": 3, "seconds": 11, "tokens": 1050}))           # noise
    moved = check_history.since(tmp_path, "20261011-020000")
    assert [(m["case"], m["dir"]) for m in moved] == [("mail/a", "worse"), ("mail/b", "better")]
    assert moved[0]["said"] == "passed 2/3 runs, was 3/3, time +30% since " + moved[0]["at"][:10]
    assert check_history.since(tmp_path, "20261010-020000") == []          # nothing before the first


def test_a_night_is_its_evenings_date():
    assert check_history.night_key(dt.datetime(2026, 10, 13, 2, 0)) == "2026-10-12"
    assert check_history.night_key(dt.datetime(2026, 10, 12, 23, 0)) == "2026-10-12"


@pytest.fixture
def host(fake_repo, isolated_layout_file):
    checkpoint.ensure(fake_repo)
    h = Host(fake_repo, auto_commit=False)
    yield h
    h.close()


class _Job:
    def __init__(self):
        self.done, self.error = False, ""


def test_the_night_checks_once_in_turn_and_says_it_in_the_morning(host, monkeypatch):
    night, started = host.nightly.check, []
    friday = dt.datetime(2026, 10, 16, 2, 0)                    # the night of Thursday the 15th
    job = _Job()

    def start(scenarios):
        started.append(list(scenarios))
        host.bench.jobs["check"] = job

    monkeypatch.setattr(host.bench.check, "start", start)
    night.tick(True, now=1000, when=friday)
    assert started == []                                        # no Test bench: no Mechanic, no night check
    host.command("town.build", {"type": "lab"})
    night.tick(False, now=2000, when=friday)
    assert started == []                                        # not in the quiet hours
    night.tick(True, now=3000, when=friday)
    assert started == [["mail", "todos"]] and night.busy
    improved = []
    monkeypatch.setattr(host.nightly.improve, "tick", lambda *a, **k: improved.append(1))
    host.nightly.tick(True)
    assert improved == []                                       # the night's improvements wait for the check
    job.done = True
    monkeypatch.setattr(host.bench.check, "last", lambda: {
        "green": False, "told": {"scenarios": [{"title": "Mail sorted", "stories": [1]}]},
        "since": [{"case": "mail/on-call", "dir": "worse", "said": "time +40% since 2026-10-14"}]})
    night.tick(True, now=4000, when=friday)
    assert not night.busy
    night.tick(True, now=5000, when=friday)
    assert started == [["mail", "todos"]]                       # once a night
    [line] = night.morning()
    assert line.startswith("The Mechanic checked Mail sorted: red; worse than before: mail/on-call (time +40%")
    night.tick(True, now=6000, when=friday + dt.timedelta(days=1))
    assert started[-1] == ["board", "pictures"]                 # the next ones in turn
    assert night.tonight(dt.datetime(2026, 10, 18, 2, 0)) == [s.id for s in check.SCENARIOS if s.type]   # Saturday's
    fastpath.save_settings(host.town.repo_root, {"check_nightly": False})
    job.done = True
    night.tick(True, now=7000, when=friday + dt.timedelta(days=2))
    night.tick(True, now=8000, when=friday + dt.timedelta(days=2))
    assert len(started) == 2                                    # turned off
