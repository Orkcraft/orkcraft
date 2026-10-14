"""! ⏳ An ork's own error and an ork held for a limit (realm/status.py, core/workers/barracks_limits.py, core/slots.py;
ork-console.md §5, §19; town-readability.md §4; town-time.md §4)."""
from __future__ import annotations

import datetime as dt
import time

from orkcraft.core.workers.barracks import BarracksWorker
from orkcraft.realm import status, tool_errors
from orkcraft.sources.limits import Limit
from tests.pool_fakes import Steward
from tests.test_gui_pool_clan import _card, _host, _raised, _until

LIMIT_SAID = "You've hit your usage limit. Try again later."


def _limit(remaining: float, reset: dt.datetime) -> Limit:
    return Limit("claude", "", "5h", remaining, reset)


# -- the words ------------------------------------------------------------------------------------------------------

def test_an_error_and_a_hold_have_a_mark_a_word_and_say_what():
    err = status.OrkStatus("Grub", status.ERROR, "Agent pool", cart="Fix the login", error="claude exited with 1: boom")
    assert err.mark() == "!" and err.mark("office") == "Error" and err.attention == 2
    assert err.line() == "Grub · Agent pool · error: claude exited with 1: boom · on «Fix the login»"
    assert err.as_dict()["error"] == "claude exited with 1: boom"
    long = status.OrkStatus("Grub", status.ERROR, error="x" * 200)
    assert len(long.doing()) < 100 and long.as_dict()["error"] == "x" * 200      # the line short, the reason whole
    held = status.OrkStatus("Grub", status.HELD)
    assert held.mark() == "⏳" and held.mark("office") == "Held for a limit" and held.doing() == "held for a limit"


def test_a_held_wait_says_until_when_and_who_held_it():
    now = dt.datetime(2026, 10, 14, 9, 0).timestamp()
    skip = status.Skip("run_anyway", "Run anyway", {"task": "t1"})
    w = status.held("Claude Code", now + 5 * 3600, status.BY_TOOL, skip, now)
    assert w.why == status.LIMIT and w.line == "held: Claude Code hit its usage limit · it resets at 14:00"
    assert w.as_dict(now)["in_s"] == 5 * 3600 and w.as_dict(now)["skip"]["label"] == "Run anyway"
    town = status.held("Claude Code", now + 5 * 3600, status.BY_TOWN, now=now)
    assert town.line == "held by the Treasurer until the 14:00 reset: Claude Code's window is nearly spent"
    unknown = status.held("Claude Code", None, now=now)
    assert unknown.until == now + status.UNKNOWN_RESET_S and "when it resets is not known" in unknown.line


def test_the_reset_comes_from_the_quota_readers():
    now = dt.datetime(2026, 10, 14, 9, 0)
    five, week = now + dt.timedelta(hours=5), now + dt.timedelta(days=3)
    limits = [_limit(0.0, five), _limit(0.4, week), Limit("codex", "", "5h", 0.0, now + dt.timedelta(hours=1))]
    assert status.reset_of(limits, "claude", now.timestamp()) == five.timestamp()
    assert status.reset_of(limits, "claude", now.timestamp(), below=1.0) == week.timestamp()   # all must come back
    assert status.reset_of([_limit(0.0, now - dt.timedelta(hours=1))], "claude", now.timestamp()) is None   # stale
    assert status.reset_of(limits, "agy", now.timestamp()) is None


# -- in the Agent pool --------------------------------------------------------------------------------------------

def _pool(fake_repo, monkeypatch, runner, **config):
    monkeypatch.setattr(BarracksWorker, "work_runner", staticmethod(runner))
    monkeypatch.setattr(BarracksWorker, "steward_runner", Steward())
    host = _host(fake_repo)
    bid = _raised(host, "barracks", worktrees=False, providers=["claude"], max_orcs=1, **config)
    return host, bid, host.town.worker(bid)


def _row(host, bid) -> dict | None:
    return next((r for r in host.snapshot()["slots"]["rows"] if r["building_id"] == bid), None)


def test_an_orks_failed_run_is_its_own_error_and_its_building_does_not_burn(fake_repo, monkeypatch):
    def broken(*a):
        raise tool_errors.ToolError("claude", "segfault in the tool", code=139)

    host, bid, w = _pool(fake_repo, monkeypatch, broken)
    host.command("act", {"id": bid, "act": "task", "args": {"title": "Fix the login"}})
    assert _until(lambda: (r := _row(host, bid)) is not None and r["state"] == status.ERROR)   # after its one retry
    row = _row(host, bid)
    assert row["mark"] == "!" and row["cart"] == "Fix the login" and "segfault in the tool" in row["error"]
    assert row["clear"]["args"] == {"id": bid, "act": "clear_error", "args": {"ork": row["name"]}} and row["stop"] is None
    s = host.snapshot()
    assert s["slots"]["errors"] == 1 and s["slots"]["working"] == 0
    assert w.building_status() != status.BURNING                   # the ork's `!`, not the building's 🔥
    assert _card(host, bid)["signal"] == {"kind": "error", "key": row["key"], "name": row["name"], "line": row["line"]}
    host.command("act", {"id": bid, "act": "clear_error", "args": {"ork": row["name"]}})
    assert _row(host, bid) is None and _card(host, bid)["signal"] is None


def test_a_tool_at_its_limit_holds_the_work_until_the_reset_and_run_anyway_runs_it(fake_repo, monkeypatch):
    calls = []
    reset = (dt.datetime.now() + dt.timedelta(hours=2)).replace(microsecond=0)

    def runner(*a):
        calls.append(a)
        if len(calls) == 1:                   # the quota readers see what the tool says: its window is spent
            host.town.limits = [_limit(0.0, reset)]
            raise tool_errors.ToolError("claude", LIMIT_SAID, code=1)
        return "done", 0.1, 10, "s1"

    host, bid, w = _pool(fake_repo, monkeypatch, runner)
    task = host.command("act", {"id": bid, "act": "task", "args": {"title": "Fix the login"}})
    assert _until(lambda: (r := _row(host, bid)) is not None and r["state"] == status.HELD)
    row = _row(host, bid)
    assert len(calls) == 1                                         # held, not retried at once
    assert row["mark"] == "⏳" and row["cart"] == "Fix the login" and row["stop"] is None
    assert row["wait"]["why"] == status.LIMIT and row["wait"]["until"] == reset.timestamp()
    assert 7000 < row["wait"]["in_s"] <= 7200
    assert row["wait"]["line"].startswith("held: Claude Code hit its usage limit · it resets ")
    assert row["wait"]["skip"] == {"act": "run_anyway", "label": "Run anyway", "args": {"task": task}}
    s = host.snapshot()
    assert s["slots"]["held"] == 1 and s["slots"]["working"] == 0 and _card(host, bid)["signal"]["kind"] == "held"
    w.tick()                                                       # the reset has not come: it stays held
    assert len(calls) == 1 and w.state.orcs[0].failed == 0 and not w.state.orcs[0].error
    host.command("act", {"id": bid, "act": "run_anyway", "args": {"task": task}})
    assert _until(lambda: w.state.task(task).status == "done")
    assert len(calls) == 2 and _row(host, bid) is None


def test_a_limit_with_no_reset_read_is_tried_again_and_says_so(fake_repo, monkeypatch):
    def runner(*a):
        raise tool_errors.ToolError("claude", LIMIT_SAID, code=1)

    host, bid, _w = _pool(fake_repo, monkeypatch, runner)
    host.command("act", {"id": bid, "act": "task", "args": {"title": "Fix the login"}})
    assert _until(lambda: (r := _row(host, bid)) is not None and r["state"] == status.HELD)
    wait = _row(host, bid)["wait"]
    assert "when it resets is not known, tried again in 15 min" in wait["line"]
    assert abs(wait["until"] - (time.time() + status.UNKNOWN_RESET_S)) < 30


def test_the_town_holds_new_work_when_the_window_is_nearly_spent(fake_repo, monkeypatch):
    calls = []
    host, bid, w = _pool(fake_repo, monkeypatch, lambda *a: (calls.append(a), ("done", 0.1, 10, "s1"))[1])
    reset = (dt.datetime.now() + dt.timedelta(minutes=40)).replace(microsecond=0)
    host.town.limits = [_limit(0.03, reset)]
    task = host.command("act", {"id": bid, "act": "task", "args": {"title": "Fix the login"}})
    assert _until(lambda: (r := _row(host, bid)) is not None and r["state"] == status.HELD)
    row = _row(host, bid)
    assert not calls and row["wait"]["until"] == reset.timestamp() and row["wait"]["in_s"] <= 2400
    assert row["wait"]["line"] == (f"held by the Treasurer until the {reset:%H:%M} reset: "
                                   "Claude Code's window is nearly spent")
    host.command("act", {"id": bid, "act": "run_anyway", "args": {"task": task}})   # the window still read as spent
    assert _until(lambda: w.state.task(task).status == "done") and len(calls) == 1
