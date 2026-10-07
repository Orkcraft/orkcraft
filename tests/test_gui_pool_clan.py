"""🏕 Barracks and 🪔 Clan Fire in the GUI: their closed cards, what their windows draw and their acts,
each one the worker's (core/workers/barracks.py, core/workers/council.py)."""
from __future__ import annotations

import stat
import time
from pathlib import Path

import pytest

from orkcraft.core import buildings
from orkcraft.core.workers.barracks import BarracksWorker
from orkcraft.core.workers.council import CouncilWorker
from orkcraft.gui.host import CommandError, Host
from orkcraft.realm import checkpoint
from tests.pool_fakes import Steward


def _host(repo: Path) -> Host:
    checkpoint.ensure(repo)
    return Host(repo, auto_commit=False)


def _raised(host: Host, type_id: str, **config) -> str:
    spec = buildings.type_spec(host.town, type_id)
    spec["config"] = {**(spec.get("config") or {}), **config}
    built = buildings.raise_spec(host.town, spec)
    assert built is not None
    host.town.worker(built.id)                  # as Build does: it works from the start
    return built.id


def _until(cond, seconds: float = 5.0) -> bool:
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if cond():
            return True
        time.sleep(0.02)
    return cond()


def _card(host: Host, bid: str) -> dict:
    return next(b for b in host.snapshot()["buildings"] if b["id"] == bid)


def test_barracks_closed_command_and_full(fake_repo, monkeypatch):
    runs = []

    def work(harness, prompt, workdir, cancel, model, env, resume):
        runs.append(prompt)
        return ("QUESTION: which database?" if len(runs) == 1 else "done: the changelog"), 0.25, 100, "s1"

    monkeypatch.setattr(BarracksWorker, "work_runner", staticmethod(work))
    monkeypatch.setattr(BarracksWorker, "steward_runner", Steward())        # it cannot answer: the person is asked
    host = _host(fake_repo)
    bid = _raised(host, "barracks", worktrees=False, max_orcs=2)
    b = _card(host, bid)
    assert b["page"] and b["card"] == {"asks": "", "active": 0, "max": 2, "queue": 0, "done": 0, "failed": 0,
                                       "spent": "$0.00", "paused": False, "working": [], "last": None}
    assert host.command("info", {"id": bid})["quick"] == []      # its preview draws them

    task = host.command("act", {"id": bid, "act": "task", "args": {"title": " Write  the changelog ", "brief": "for v0.2"}})
    w = host.town.worker(bid)
    assert _until(lambda: w.state.asked)
    card = _card(host, bid)["card"]
    assert card["asks"] == w.keeper and card["active"] == 0
    d = host.detail(bid)["data"]
    asked = d["asked"][0]
    assert asked["id"] == task and asked["lane"] == "review" and "which database?" in asked["question"]
    assert d["orks"][0]["name"] == "Grub" and d["orks"][0]["asks"] and d["orks"][0]["terminal"] == f"pool:{bid}/grub"
    assert [ln["id"] for ln in d["lanes"]] == ["queue", "work", "review", "done", "failed"]

    rule = host.command("act", {"id": bid, "act": "answer", "args": {"text": "Postgres"}})
    assert rule == "- which database? → Postgres"
    assert host.command("act", {"id": bid, "act": "add_rule", "args": {"rule": rule}})
    assert _until(lambda: any(t.status == "done" for t in w.state.tasks))
    d = host.detail(bid)["data"]
    done = next(t for t in d["tasks"] if t["id"] == task)
    assert done["lane"] == "done" and done["title"] == "Write the changelog" and done["report"] == "done: the changelog"
    assert done["qa"] == [{"q": "which database?", "a": "Postgres", "who": "operator"}] and done["cost"]
    assert d["rules"] == [rule] and d["decisions"]
    assert _card(host, bid)["card"]["done"] == 1
    with pytest.raises(CommandError, match="no branch"):
        host.command("act", {"id": bid, "act": "diff", "args": {"task": task}})
    with pytest.raises(CommandError, match="answered already"):
        host.command("act", {"id": bid, "act": "answer", "args": {"text": "again"}})

    assert host.command("act", {"id": bid, "act": "pause"}) is True
    assert _card(host, bid)["card"]["paused"] and host.command("act", {"id": bid, "act": "pause"}) is False


def test_an_ork_of_the_barracks_opens_its_terminal(fake_repo, tmp_path, monkeypatch):
    cli = tmp_path / "fake-claude"
    cli.write_text("#!/bin/sh\necho \"resumed $*\"\nsleep 30\n", encoding="utf-8")
    cli.chmod(cli.stat().st_mode | stat.S_IXUSR)
    monkeypatch.setenv("ORKCRAFT_CLAUDE_BIN", str(cli))
    monkeypatch.setattr(BarracksWorker, "work_runner", staticmethod(lambda *a: ("ok", 0.0, 0, "sess-42")))
    monkeypatch.setattr(BarracksWorker, "steward_runner", Steward())
    host = _host(fake_repo)
    bid = _raised(host, "barracks", worktrees=False)
    w = host.town.worker(bid)
    with pytest.raises(CommandError, match="No such ork"):
        host.command("act", {"id": bid, "act": "terminal", "args": {"ork": "Nobody"}})
    host.command("act", {"id": bid, "act": "task", "args": {"title": "fix it"}})
    assert _until(lambda: w.state.orcs and w.state.orcs[0].status == "idle" and w.state.orcs[0].session)
    try:
        key = host.command("act", {"id": bid, "act": "terminal", "args": {"ork": "Grub"}})
        s = host.sessions.get(key)
        assert key == f"pool:{bid}/grub" and s.running and s.command[1:] == ["--resume", "sess-42"]
        assert s.env["ORKCRAFT_ORC"] == f"{bid}/grub"
        assert host.command("act", {"id": bid, "act": "terminal", "args": {"ork": "Grub"}}) == key   # the same one
        assert any(x["key"] == key for x in host.snapshot()["sessions"])
    finally:
        host.sessions.close()


class Script:
    """Members and the steward answer from their lists, in turn."""

    def __init__(self, replies: dict[str, list[str]]):
        self.replies = replies

    def __call__(self, harness, prompt, model):
        who = "Steward" if prompt.startswith("You are the steward") else next(r for r in self.replies
                                                                             if prompt.startswith(f"You are {r} "))
        return self.replies[who].pop(0), 0.1


def test_clan_fire_closed_command_and_full(fake_repo, monkeypatch):
    s = Script({"Planner": ["APPROVE fine", "APPROVE"], "Steward": ["DECISION: ask\nShip on Friday?", "DECISION: approve\nyes", "DECISION: approve\nok"]})
    monkeypatch.setattr(CouncilWorker, "runner", staticmethod(s))
    host = _host(fake_repo)
    bid = _raised(host, "council", members=["Planner:claude"], veto=["Planner"], max_cycles=3)
    assert _card(host, bid)["card"] == {"state": "none", "queued": 0, "triage": False, "of": 1, "set_up": True,
                                        "phase": "", "exits": []}
    assert host.command("info", {"id": bid})["quick"] == []

    assert host.command("act", {"id": bid, "act": "review", "args": {"text": "# Launch plan\n\nShip it."}}) == "started"
    w = host.town.worker(bid)
    assert _until(lambda: w.current is not None and w.current.outcome == "asked")
    card = _card(host, bid)["card"]
    assert card["state"] == "asked" and card["cycle"] == 1 and card["max"] == 3 and card["ok"] == 1 and card["no"] == 0
    d = host.detail(bid)["data"]
    assert d["members"] == [{"role": "Planner", "label": "claude", "tier": "", "veto": True, "verdict": "approve", "says": "fine",
                             "brief": d["members"][0]["brief"], "briefed": False}]
    r = d["current"]
    assert r["title"] == "Launch plan" and r["question"].startswith("Ship on Friday?") and "<h1>Launch plan</h1>" in r["doc_html"]
    assert [t["role"] for t in r["turns"]] == ["Planner", "Steward"] and r["doc_path"].endswith(".md")

    assert host.command("act", {"id": bid, "act": "review", "args": {"text": "another doc"}}) == "queued"
    assert _card(host, bid)["card"]["queued"] == 1
    assert host.command("act", {"id": bid, "act": "answer", "args": {"text": "yes, Friday"}})
    assert _until(lambda: [x.outcome for x in w.history] == ["approved", "approved"] and not w.busy)
    with pytest.raises(CommandError, match="asks nothing"):
        host.command("act", {"id": bid, "act": "answer", "args": {"text": "?"}})
    past = next(x for x in w.history if x.title == "Launch plan")
    shown = host.command("act", {"id": bid, "act": "show", "args": {"review": past.id}})
    assert shown["outcome"] == "approved" and "Launch plan" in shown["report"] and shown["turns"][-1]["verdict"] == "approve"

    assert host.command("act", {"id": bid, "act": "add_member", "args": {"role": "Security", "harness": "claude"}}) == "Security"
    with pytest.raises(CommandError, match="already"):
        host.command("act", {"id": bid, "act": "add_member", "args": {"role": "security"}})
    with pytest.raises(CommandError):
        host.command("act", {"id": bid, "act": "add_member", "args": {"role": "Legal", "harness": "gpt-9000"}})
    assert [m["role"] for m in host.detail(bid)["data"]["members"]] == ["Planner", "Security"]


def test_clan_fire_shows_the_cycles_of_the_document_sent_back(fake_repo):
    import os

    from orkcraft.realm import team as tm
    host = _host(fake_repo)
    bid = _raised(host, "council", members=["Planner:claude"])
    w = host.town.worker(bid)
    for n, (cycle, outcome) in enumerate(((1, "approved"), (1, "rework"), (2, "rework"), (3, "running"))):
        d = tm.new("Plan", f"take {n}", "", cycle)
        d.outcome = outcome
        path = tm.save(w.state_dir, d)
        os.utime(path, (1_000_000 + n, 1_000_000 + n))             # newest last on disk, as they were written
    w.current = None
    w.refresh()
    d = host.detail(bid)["data"]
    assert d["current"]["cycle"] == 3 and [c["cycle"] for c in d["cycles"]] == [1, 2]    # not the approved one
    assert [h["outcome"] for h in d["history"]] == ["rework", "rework", "approved"]


def test_closing_the_window_does_not_leave_the_barracks_paused(fake_repo):
    """Closing the window stops the orks, but only 🛑 Halt All or ⏸ pauses the barracks: a task written
    after the next launch is taken up, not parked as `paused`."""
    host = _host(fake_repo)
    bid = _raised(host, "barracks", worktrees=False)
    host.close()
    assert not host.town.worker(bid).state.paused
    again = _host(fake_repo)
    assert not again.town.worker(bid).state.paused
    host.command("act", {"id": bid, "act": "pause"})
    host.close()
    assert _host(fake_repo).town.worker(bid).state.paused            # the operator's own ⏸ is kept
