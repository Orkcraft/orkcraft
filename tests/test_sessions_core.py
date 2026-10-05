"""Sessions without a face (core/sessions.py): a CLI on a PTY, its screen read by the roster, its
questions answered through `Muster.answer`, a garrison ork deployed."""
from __future__ import annotations

import stat
import time
from pathlib import Path

import pytest

from orkcraft.core import bus
from orkcraft.core.roster import Muster
from orkcraft.core.sessions import Sessions
from orkcraft.core.town import Town
from orkcraft.core.treasury import Treasury

ASKS = """#!/bin/sh
printf 'Fake CLI %s\\r\\n' "$*"
printf 'Do you want to run the tests?\\r\\n1. Yes\\r\\n2. No\\r\\n'
stty -icanon                                  # a CLI reads keys as they come, not lines
answer=$(dd bs=1 count=1 2>/dev/null)
printf 'You chose %s\\r\\n' "$answer"
"""


def _cli(tmp_path: Path, monkeypatch) -> Path:
    path = tmp_path / "fake-claude"
    path.write_text(ASKS, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    monkeypatch.setenv("ORKCRAFT_CLAUDE_BIN", str(path))
    return path


def _until(pred, timeout: float = 10.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        got = pred()
        if got:
            return got
        time.sleep(0.05)
    raise AssertionError("timed out")


def test_a_session_runs_its_cli_and_the_roster_reads_its_question(fake_repo, tmp_path, monkeypatch):
    _cli(tmp_path, monkeypatch)
    town = Town(fake_repo)
    sessions, muster = Sessions(town), Muster(town)
    out, events = [], []
    sessions.on_output = lambda key, data: out.append(data)
    town.bus.subscribe(bus.SESSION, lambda e: events.append(e.data["state"]))
    key = sessions.new("claude")
    s = sessions.get(key)
    _until(lambda: "2. No" in "\n".join(s.text_lines()))
    assert s.env["ORKCRAFT_TERMINAL"] == key and s.env["ORKCRAFT_RUN"] == town.run_id
    time.sleep(1.1)                                      # a menu that stays a moment is a question
    muster.rebuild(sessions.infos(), sessions.keys())
    alert = muster.alert(f"term:{key}")
    assert alert is not None and alert.title == "Do you want to run the tests?"
    assert [k for k, _ in alert.options] == ["1", "2"]
    assert not muster.answer(alert, "9", sessions.write)              # not one of its answers
    assert muster.answer(alert, "1", sessions.write)
    _until(lambda: not s.running)
    assert any("You chose 1" in line for line in s.text_lines())
    assert b"You chose 1" in s.replay() and b"".join(out).endswith(s.replay()[-len(out[-1]):])
    assert events == ["opened", "exited"] and s.exit_code == 0
    with pytest.raises(ValueError):
        sessions.new("bash")


def test_a_garrison_ork_is_deployed_with_its_orders_once(fake_repo, tmp_path, monkeypatch):
    _cli(tmp_path, monkeypatch)
    town = Town(fake_repo)
    sessions, muster, treasury = Sessions(town), Muster(town), Treasury(town)
    muster.rebuild([], [])
    ork = next(o for o in muster.roster.orcs if o.building == "town_hall" and o.kind in ("agent", "hybrid"))
    key = sessions.deploy(ork.ref, muster, treasury)
    assert key and muster.deployments[key] == ork.ref
    s = sessions.get(key)
    assert s.ork == ork.ref and s.env["ORKCRAFT_ORC"] == ork.ref
    _until(lambda: "Fake CLI" in "\n".join(s.text_lines()))
    assert f"You are {ork.name}" in "\n".join(s.text_lines()).replace("\n", "")
    assert sessions.deploy(ork.ref, muster, treasury) == key          # its running session, not a second one
    town.scroll.budget.supply_max_workers = 0
    sessions.stop(key)
    _until(lambda: not s.running)
    muster.rebuild(sessions.infos(), sessions.keys())
    assert sessions.deploy(ork.ref, muster, treasury) is None         # no food left
    with pytest.raises(ValueError):
        sessions.deploy("town_hall/nobody", muster, treasury)
