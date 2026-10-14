"""🥩 The ork slots (core/slots.py, ork-console.md §8): one row per ork at work or asking, waiting first."""
from __future__ import annotations

import threading

from orkcraft.core import slots
from orkcraft.core.workers.barracks import BarracksWorker
from tests.pool_fakes import Steward
from tests.test_asking import BLOCK
from tests.test_gui_pool_clan import _host, _raised, _until


def test_an_asking_ork_is_a_row_with_its_answers_and_the_snapshot_carries_it(fake_repo, monkeypatch):
    monkeypatch.setattr(BarracksWorker, "work_runner", staticmethod(lambda *a: (BLOCK, 0.4, 10, "s1")))
    monkeypatch.setattr(BarracksWorker, "steward_runner", Steward())
    host = _host(fake_repo)
    bid = _raised(host, "barracks", worktrees=False, providers=["claude"])
    w = host.town.worker(bid)
    task = host.command("act", {"id": bid, "act": "task", "args": {"title": "Set up the dev server"}})
    assert _until(lambda: w.state.asked)
    s = host.snapshot()["slots"]
    [row] = [r for r in s["rows"] if r["building_id"] == bid]
    assert s["asks"] >= 1 and row["state"] == "asks" and row["mark"] == "❓" and row["word"] == "Asks"
    assert row["cart"] == "Set up the dev server" and row["stop"] is None and row["spend"] == 0.41   # the ork's run and the steward's look
    assert row["answer"] == {"kind": "pool", "building": bid, "task": task,
                             "question": "Which port should the dev server use?",
                             "questions": [{"text": "Which port should the dev server use?", "options": ["8080", "3000"]}]}
    assert s["rows"][0]["attention"] == 2                                  # waiting first
    host.command("act", {"id": bid, "act": "answer", "args": {"task": task, "text": "3000"}})
    assert _until(lambda: not any(r["building_id"] == bid and r["state"] == "asks"
                                  for r in host.snapshot()["slots"]["rows"]))


def test_a_working_ork_is_a_row_that_stops_softly(fake_repo, monkeypatch):
    gate = threading.Event()

    def work(harness, prompt, workdir, cancel, model, env, resume):
        while not cancel.is_set() and not gate.is_set():
            cancel.wait(0.02)
        if cancel.is_set():
            raise InterruptedError("stopped")
        return "done", 0.0, 0, "s1"

    monkeypatch.setattr(BarracksWorker, "work_runner", staticmethod(work))
    monkeypatch.setattr(BarracksWorker, "steward_runner", Steward())
    host = _host(fake_repo)
    bid = _raised(host, "barracks", worktrees=False)
    w = host.town.worker(bid)
    host.command("act", {"id": bid, "act": "task", "args": {"title": "Long work"}})
    assert _until(lambda: any(r["building_id"] == bid for r in slots.summary(host.town, host.muster)["rows"]))
    s = slots.summary(host.town, host.muster)
    [row] = [r for r in s["rows"] if r["building_id"] == bid]
    assert row["state"] == "thinking" and row["cart"] == "Long work" and s["working"] >= 1 and row["answer"] is None
    assert row["line"].startswith(f"Grub · {w._building_title()} · thinking · on «Long work»")
    assert isinstance(row["since_s"], int)
    assert row["stop"] == {"command": "act", "args": {"id": bid, "act": "stop_ork", "args": {"ork": "Grub"}}}
    assert host.command(row["stop"]["command"], row["stop"]["args"]) is True
    assert _until(lambda: w.state.orcs[0].status == "idle")
    assert not any(r["building_id"] == bid for r in slots.summary(host.town, host.muster)["rows"])
    gate.set()


def test_an_agent_process_no_one_named_is_a_row_too(fake_repo, monkeypatch):
    from orkcraft.realm import halt
    monkeypatch.setattr(halt, "live", lambda: [("mill/miller", True), ("mill/miller", True), ("tests", False)])
    host = _host(fake_repo)
    rows = slots.summary(host.town, host.muster)["rows"]
    assert [(r["name"], r["state"], r["stop"]) for r in rows] == [("Miller", "thinking", None)]


def test_the_console_unfolded_reads_the_answer_in_order_and_the_history_with_cost(fake_repo, monkeypatch):
    """ork-console.md §7, §20: its questions pinned, the gist, its assumptions, the text; its runs with their cost."""
    monkeypatch.setattr(BarracksWorker, "work_runner", staticmethod(lambda *a: (BLOCK, 0.4, 10, "s1")))
    monkeypatch.setattr(BarracksWorker, "steward_runner", Steward())
    host = _host(fake_repo)
    bid = _raised(host, "barracks", worktrees=False, providers=["claude"])
    w = host.town.worker(bid)
    task = host.command("act", {"id": bid, "act": "task", "args": {"title": "Set up the dev server"}})
    assert _until(lambda: w.state.asked)
    key = f"{bid}/grub"
    c = host.command("ork.console", {"key": key})
    assert c["key"] == key and c["row"]["state"] == "asks" and c["role"] == "Grunt · any work"
    assert [s["name"] for s in c["sessions"]] == ["Grub"] and c["sessions"][0]["this"]
    assert c["cart"]["id"] == task and c["cart"]["title"] == "Set up the dev server"
    a = c["answer"]
    assert a["questions"] == [{"text": "Which port should the dev server use?", "options": ["8080", "3000"]}]
    assert (a["gist"], a["gist_from"]) == ("I set up the server.", "last paragraph")
    assert a["assumptions"] == ["The API keeps its v1 paths.", "Tests run with pytest."]
    assert a["text"] == "I set up the server."
    assert c["terminal"]["key"] == f"pool:{bid}/grub" and c["terminal"]["working"] is False
    assert [(h["id"], h["status"], h["cost"]) for h in c["history"]] == [(task, "asked", 0.415)]
    assert host.command("ork.console", {"key": f"{bid}/nobody"}) is None


def test_a_stopped_task_runs_again_or_is_dropped(fake_repo, monkeypatch):
    """§9: stopped work waits for Run again (the session goes on) or Drop."""
    gate = threading.Event()

    def work(harness, prompt, workdir, cancel, model, env, resume):
        while not cancel.is_set() and not gate.is_set():
            cancel.wait(0.02)
        if cancel.is_set():
            raise InterruptedError("stopped")
        return "done", 0.0, 0, "s1"

    monkeypatch.setattr(BarracksWorker, "work_runner", staticmethod(work))
    monkeypatch.setattr(BarracksWorker, "steward_runner", Steward())
    host = _host(fake_repo)
    bid = _raised(host, "barracks", worktrees=False)
    w = host.town.worker(bid)
    task = host.command("act", {"id": bid, "act": "task", "args": {"title": "Long work"}})
    assert _until(lambda: w.state.orcs and w.state.orcs[0].status == "working")
    w.stop_ork("Grub")
    assert _until(lambda: (t := w.state.task(task)) is not None and t.status == "failed")
    c = host.command("ork.console", {"key": f"{bid}/grub"})
    assert c["row"]["state"] == "resting" and c["cart"]["stopped"] is True
    assert c["history"][0]["stopped"] is True
    gate.set()
    assert host.command("act", {"id": bid, "act": "run_again", "args": {"task": task}}) is True
    assert _until(lambda: w.state.task(task).status == "done" or w.state.task(task).status == "reviewing"
                  or w.state.task(task).status == "asked")
    assert not w.drop(task)                                    # it is not stopped any more
