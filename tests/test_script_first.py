"""Script-first buildings (docs/design/script-first.md): code does their work, no model is called on their
carts, ticks or schedules, and their ork — the keeper — wakes once on an error spell and once on a 👎."""
from __future__ import annotations

import datetime as dt
import time
from pathlib import Path

import pytest

from orkcraft import scroll as ts
from orkcraft.core import buildings, retros, runners, wakes
from orkcraft.gui import state
from orkcraft.gui.host import Host
from orkcraft.realm import builders, checkpoint, fastpath, roads, script_first


def _host(repo: Path) -> Host:
    checkpoint.ensure(repo)
    return Host(repo, auto_commit=False)


def _raised(host: Host, type_id: str, **config) -> str:
    spec = buildings.type_spec(host.town, type_id) or {      # a Workshop is only made from scratch
        "id": type_id, "type": type_id, "title": "Workshop", "icon": "🛠️", "orc": {"name": "Tinker"}}
    if config:
        spec["config"] = {**(spec.get("config") or {}), **config}
    built = buildings.raise_spec(host.town, spec)
    assert built is not None
    host.town.worker(built.id)
    return built.id


def _wait(cond, seconds: float = 10.0) -> None:
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if cond():
            return
        time.sleep(0.02)
    raise AssertionError("never happened")


@pytest.fixture
def no_model(monkeypatch):
    """Every model seam fails the test when called: a one-shot prompt, an agent, every fake runner."""
    called: list[str] = []

    def refuse(name):
        def runner(*a, **k):
            called.append(name)
            raise AssertionError(f"a model was called: {name}")
        return runner

    monkeypatch.setattr(builders, "ask", refuse("builders.ask"))
    monkeypatch.setattr(roads, "run_agent", refuse("roads.run_agent"))
    for name in [n for n in dir(runners) if n.endswith("_RUNNER")]:
        monkeypatch.setattr(runners, name, refuse(name))
    return called


@pytest.fixture
def keeper_calls(monkeypatch):
    """The keeper's model: counts its calls and answers with no change."""
    calls: list[str] = []

    def runner(prompt, model=None):
        calls.append(prompt)
        return '{"value": null, "why": "", "answer": "Look at the file it reads."}', 0.01
    monkeypatch.setattr(runners, "KEEPER_RUNNER", runner)
    return calls


# -- the rule -----------------------------------------------------------------------------------------------

def test_the_rule_is_the_type_and_its_parts():
    pit = {"id": "drop", "type": "pit"}
    assert script_first.is_script_first(pit) and script_first.thinking(pit) == []
    code = {"id": "m", "type": "mill", "config": {"steps": ["lines", "grep: x", "trim"]}}
    agent = {"id": "m", "type": "mill", "config": {"steps": ["lines", "agent: shorten it"]}}
    fallback = {"id": "m", "type": "mill", "config": {"steps": ["script: wc -l || agent: count them"]}}
    assert script_first.is_script_first(code)
    assert script_first.thinking(agent) == ["agent: step 2"] and not script_first.is_script_first(agent)
    assert script_first.thinking(fallback) == ["agent: step 1"]
    assert script_first.is_script_first({"id": "w", "type": "workshop", "config": {}})
    assert not script_first.is_script_first({"id": "w", "type": "workshop", "config": {"steward_prompt": "decide"}})
    for kind in ("barracks", "council", "scrolls", "watchtower", "fields", "catapult"):
        assert not script_first.is_script_first({"id": "x", "type": kind}), kind


def test_a_handler_that_thinks_keeps_it_working_and_not_script_first(fake_repo):
    host = _host(fake_repo)
    pit = _raised(host, "pit")
    horn = _raised(host, "horn")
    b = host.town.scroll.building(horn)
    assert script_first.is_script_first(host.town.spec_of(horn), b)
    ts.add_handler(host.town.scroll, horn, "Judge", kind="agent", orders="say if it matters")
    ts.subscribe(host.town.scroll, horn, pit, "pit.text", handler="judge")
    assert script_first.thinking(host.town.spec_of(horn), b) == ["agent Judge"]
    assert not script_first.is_script_first(host.town.spec_of(horn), b)


# -- no model on carts, ticks and schedules -------------------------------------------------------------------

def test_script_first_buildings_call_no_model_over_many_carts_and_ticks(fake_repo, no_model):
    host = _host(fake_repo)
    fastpath.save_settings(fake_repo, {**fastpath.settings(fake_repo), "optimize_at": "* * * * *", "weekly_at": ""})
    pit = _raised(host, "pit")
    router = _raised(host, "signpost", rules=["notes: contains release notes"])
    horn = _raised(host, "horn")
    mill = _raised(host, "mill", steps=["lines", "grep: (?i)release", "trim"])
    scroll = host.town.scroll
    ts.subscribe(scroll, router, pit, "pit.text")
    ts.subscribe(scroll, horn, pit, "pit.text")
    ts.subscribe(scroll, horn, router, "signpost.routed")
    ts.subscribe(scroll, mill, router, "signpost.routed", {"route": ["notes"]})
    for bid in (pit, router, horn, mill):
        assert script_first.is_script_first(host.town.spec_of(bid), scroll.building(bid)), bid
        scroll.building(bid).goal = "quality"            # 💎 and never rated: today's retro would look at them
    w = host.town.worker(pit)
    t0 = time.monotonic()
    for i in range(30):
        w.drop(f"release notes for v0.{i}: faster carts" if i % 2 else f"paste {i}")
        host.tick(t0 + i * 61.0)                         # a minute apart: the retro's check comes due every time
    time.sleep(0.3)
    host.tick(t0 + 31 * 61.0)
    assert len(w.items) >= 30
    assert no_model == []
    assert wakes.due(host.town) == []


def test_the_building_retro_skips_script_first_buildings(fake_repo, monkeypatch):
    from orkcraft.realm import feedback
    host = _host(fake_repo)
    fastpath.save_settings(fake_repo, {**fastpath.settings(fake_repo), "optimize_at": "* * * * *"})
    pit = _raised(host, "pit")
    script = _raised(host, "workshop", runtime="python", layout="card", steward_prompt="decide what the script cannot")
    for bid in (pit, script):
        host.town.scroll.building(bid).goal = "quality"
    feedback.dislike(fake_repo, host.town.scroll, pit, "logic", "it sorted my file as text")
    monkeypatch.setattr(runners, "OPTIMIZE_RUNNER", lambda *a, **k: ('{"proposals": []}', 0.0))
    work = retros.daily_job(host.town, dt.datetime.now())
    # the 💎 Drop file here with a 👎 came first before; it has no prompt, so the day's retro went by with nothing.
    # Now it goes to the 💎 Script that thinks (never rated)
    assert work is not None
    from orkcraft.realm import optimize
    assert optimize.leader(fake_repo, None, goals={pit: "quality"}).building == pit   # the leader alone still would


# -- wakes ----------------------------------------------------------------------------------------------------

def _keeper_jobs(host: Host, bid: str) -> list[dict]:
    return [j for j in host.console.jobs.values() if j["building"] == bid and j["kind"] == "keeper"]


def test_an_error_wakes_its_keeper_once_per_spell(fake_repo, keeper_calls):
    host = _host(fake_repo)
    bid = _raised(host, "forest", path="web")
    w = host.town.worker(bid)
    ill = {"now": False}
    w.refresh = lambda: None                      # its own look would read the folder again
    w.status = lambda: "ERROR" if ill["now"] else ""
    w.error = "web/ cannot be read"
    t = [time.monotonic()]

    def tick(n=1):
        for _ in range(n):
            t[0] += wakes.WAKE_CHECK_S + 1
            host.tick(t[0])

    tick(3)
    assert keeper_calls == []
    ill["now"] = True
    tick()
    _wait(lambda: len(keeper_calls) == 1 and _keeper_jobs(host, bid) and _keeper_jobs(host, bid)[0]["state"] == "ready")
    job = _keeper_jobs(host, bid)[0]
    assert job["view"]["woke"] and "web/ cannot be read" in job["view"]["request"]
    assert "web/ cannot be read" in keeper_calls[0]
    host.command("job.drop", {"job": job["id"]})
    tick(5)                                       # still ill: the same spell wakes nobody again
    time.sleep(0.2)
    assert len(keeper_calls) == 1 and _keeper_jobs(host, bid) == []
    assert [e["why"] for e in script_first.wakes(fake_repo, bid)] == ["error"]
    ill["now"] = False
    tick()
    ill["now"] = True
    tick()
    _wait(lambda: len(keeper_calls) == 2)


def test_a_failed_handler_run_is_an_error_too(fake_repo, keeper_calls):
    host = _host(fake_repo)
    pit = _raised(host, "pit")
    horn = _raised(host, "horn")
    ts.add_handler(host.town.scroll, horn, "Picky", kind="chain", chain=[{"op": "limit", "n": 1}])
    ts.subscribe(host.town.scroll, horn, pit, "pit.text", handler="picky")
    assert script_first.is_script_first(host.town.spec_of(horn), host.town.scroll.building(horn))
    run = roads.HandlerRun(horn, "picky", "chain", "r1", time.monotonic())
    run.outcome, run.error = "error", "no field 'title' in the cart"
    host.town.roads.runs.append(run)
    host.tick(time.monotonic() + 100)
    _wait(lambda: len(keeper_calls) == 1)
    assert "picky failed: no field 'title'" in keeper_calls[0]


def test_a_thumbs_down_wakes_its_keeper_once(fake_repo, keeper_calls):
    host = _host(fake_repo)
    bid = _raised(host, "signpost", rules=["notes: contains release notes"])
    t = [time.monotonic()]

    def tick(n=1):
        for _ in range(n):
            t[0] += wakes.WAKE_CHECK_S + 1
            host.tick(t[0])

    buildings.dislike(host.town, bid, "logic", "it sent my notes nowhere")
    tick()
    _wait(lambda: len(keeper_calls) == 1)
    assert "it sent my notes nowhere" in keeper_calls[0] and "👎" in keeper_calls[0]
    _wait(lambda: _keeper_jobs(host, bid) and _keeper_jobs(host, bid)[0]["state"] == "ready")
    buildings.dislike(host.town, bid, "logic", "and again")      # a wake is open: this one waits for it
    tick(3)
    time.sleep(0.2)
    assert len(keeper_calls) == 1
    host.command("job.drop", {"job": _keeper_jobs(host, bid)[0]["id"]})
    tick()
    _wait(lambda: len(keeper_calls) == 2)
    assert "and again" in keeper_calls[1]
    tick(3)
    time.sleep(0.2)
    assert len(keeper_calls) == 2
    assert [e["why"] for e in script_first.wakes(fake_repo, bid)] == ["dislike", "dislike"]


def test_older_thumbs_downs_and_spent_budgets_do_not_wake(fake_repo, keeper_calls):
    from orkcraft.realm import feedback
    checkpoint.ensure(fake_repo)
    host = _host(fake_repo)
    bid = _raised(host, "pit")
    host.close()
    feedback.dislike(fake_repo, host.town.scroll, bid, "logic", "before")
    host = _host(fake_repo)                       # the town opens again: that 👎 is old news
    host.tick(time.monotonic() + 100)
    time.sleep(0.2)
    assert keeper_calls == []
    host.treasury.exhausted = lambda quiet=False: True
    buildings.dislike(host.town, bid, "logic", "after")
    host.tick(time.monotonic() + 200)
    time.sleep(0.2)
    assert keeper_calls == []                    # the budget is spent: the wake waits
    del host.treasury.exhausted
    host.tick(time.monotonic() + 300)
    _wait(lambda: len(keeper_calls) == 1)
    assert "after" in keeper_calls[0] and "before" not in keeper_calls[0]


def test_a_building_that_thinks_never_wakes(fake_repo, keeper_calls):
    host = _host(fake_repo)
    bid = _raised(host, "mill", steps=["agent: shorten it"])
    buildings.dislike(host.town, bid, "logic", "too long")
    host.tick(time.monotonic() + 100)
    time.sleep(0.2)
    assert keeper_calls == [] and wakes.due(host.town) == []


def test_a_road_rule_the_steward_carries_out_thinks_too(fake_repo):
    host = _host(fake_repo)
    pit = _raised(host, "pit")
    horn = _raised(host, "horn")
    ts.add_handler(host.town.scroll, horn, "Loud ones", kind="steward", orders="only what sounds urgent", harness=[])
    ts.subscribe(host.town.scroll, horn, pit, "pit.text", handler="loud_ones")
    b = host.town.scroll.building(horn)
    assert script_first.thinking(host.town.spec_of(horn), b) == ["road rule Loud ones"]
    assert not script_first.is_script_first(host.town.spec_of(horn), b)


# -- yards: no ork lives in a building whose work is code; one visits (docs/design/yards.md §2) -------------

def _seen(host: Host, bid: str) -> dict:
    return next(b for b in host.snapshot()["buildings"] if b["id"] == bid)


def test_why_an_ork_is_in_a_yard():
    yard = {"id": "drop", "yard": True, "alert": None}
    assert state.visit(yard, []) == ""
    assert state.visit(yard, [{"building": "other", "_wake": True}]) == ""
    assert state.visit(yard, [{"building": "drop", "kind": "keeper"}]) == "asked"
    assert state.visit(yard, [{"building": "drop", "kind": "keeper"}, {"building": "drop", "_wake": True}]) == "wake"
    assert state.visit({**yard, "alert": {"id": "a1"}}, []) == "alert"
    assert state.visit({**yard, "yard": False, "alert": {"id": "a1"}}, [{"building": "drop"}]) == ""   # a hut


def test_a_yard_has_no_ork_of_its_own_and_one_visits_on_a_wake(fake_repo, keeper_calls):
    host = _host(fake_repo)
    tree = _raised(host, "forest", path="web")
    board = _raised(host, "fields")
    thinker = _raised(host, "mill", steps=["agent: shorten it"])
    assert _seen(host, tree)["yard"] and _seen(host, tree)["visit"] == ""
    assert not _seen(host, board)["yard"] and not _seen(host, thinker)["yard"]     # their work is a model's

    w = host.town.worker(tree)
    w.refresh = lambda: None
    w.status = lambda: "ERROR"
    w.error = "web/ cannot be read"
    host.tick(time.monotonic() + wakes.WAKE_CHECK_S + 1)
    _wait(lambda: _keeper_jobs(host, tree) and _keeper_jobs(host, tree)[0]["state"] == "ready")
    assert _seen(host, tree)["visit"] == "wake"                     # its proposal waits: the ork is there
    host.command("job.drop", {"job": _keeper_jobs(host, tree)[0]["id"]})
    assert _seen(host, tree)["visit"] == ""                         # closed: it left


def test_a_wake_says_the_buildings_own_error_line_never_its_status_word():
    """Branches & PRs keeps its error on its snapshot: the wake said "it says ERROR" (ui.md U24)."""
    from types import SimpleNamespace as NS
    assert wakes._detail(NS(snap=NS(error="This folder is not a git repository"))) == "This folder is not a git repository"
    assert wakes._detail(NS(last_error="the wiki cannot be read")) == "the wiki cannot be read"
    assert wakes._detail(NS(errors={"intent": "no address set"})) == "no address set"
    assert wakes._detail(NS(mini_status=lambda: ["3 open", "⚠ the token expired"])) == "the token expired"
    assert wakes._detail(NS()) == ""
