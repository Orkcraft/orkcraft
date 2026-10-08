"""🕳️ The Pit, 🚏 Signpost and ⚙️ The Mill (docs/design/building-views.md §3, track B1): their workers
without an app, and closed, command and full through the GUI's host."""
from __future__ import annotations

import base64
import json
import sys
import time
from pathlib import Path

import pytest

from orkcraft import scroll as ts
from orkcraft.core import buildings, bus
from orkcraft.gui.host import CommandError, Host
from orkcraft.realm import checkpoint, mill


def _host(repo: Path) -> Host:
    checkpoint.ensure(repo)
    return Host(repo, auto_commit=False)


def _raised(host: Host, type_id: str, **config) -> str:
    spec = buildings.type_spec(host.town, type_id)
    if config:
        spec["config"] = {**(spec.get("config") or {}), **config}
    built = buildings.raise_spec(host.town, spec)
    assert built is not None
    host.town.worker(built.id)
    return built.id


def _card(host: Host, bid: str) -> dict:
    snap = host.snapshot()
    json.dumps(snap)
    b = next(b for b in snap["buildings"] if b["id"] == bid)
    assert b["page"] and b["has_worker"]
    return b["card"]


def _wait(cond, seconds: float = 10.0) -> None:
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if cond():
            return
        time.sleep(0.02)
    raise AssertionError("never happened")


def test_mill_trace_and_agent_cost():
    trace: list[dict] = []
    r = mill.run_full(["lines", "grep: b", "replace: x", "trim"], "a\nb", trace=trace)
    assert [t["step"] for t in trace] == ["lines", "grep: b", "replace: x"] and "error" in trace[-1]
    assert '"b"' in trace[1]["out"] and r.error.startswith("step 3")
    spent: list = []
    import orkcraft.realm.roads as roads
    real = roads.run_agent
    roads.run_agent = lambda *a, **kw: ("short", 0.25, 10)
    try:
        assert mill.default_agent(Path("."), None, spent=spent.append)("shorten", "long") == "short"
    finally:
        roads.run_agent = real
    assert spent == [0.25]


def test_the_pit_card_is_a_drop_zone_and_its_window_follows_each_drop(fake_repo, isolated_layout_file):
    host = _host(fake_repo)
    pit_id = _raised(host, "pit")
    loot_id = _raised(host, "loot")
    ts.subscribe(host.town.scroll, loot_id, pit_id, "pit.text")
    assert _card(host, pit_id) == {"n": 0, "last": None, "spent": 0.0}
    assert host.command("act", {"id": pit_id, "act": "drop", "args": {"text": "remember: ship on Friday"}}) == 1
    data = base64.b64encode(b"%PDF-1.4 tiny").decode()
    assert host.command("act", {"id": pit_id, "act": "drop_file",
                                "args": {"name": "../../etc/report.pdf", "data": data}}) == 1
    with pytest.raises(CommandError):
        host.command("act", {"id": pit_id, "act": "drop_file", "args": {"name": "x.bin", "data": "not base64!"}})
    with pytest.raises(CommandError):
        host.command("act", {"id": pit_id, "act": "drop", "args": {"text": "   "}})
    d = host.detail(pit_id)
    assert [p["id"] for p in d["ui"]["panes"][:1]] == ["drop"]
    [pdf, note] = d["data"]["items"]
    assert pdf["kind"] == "doc" and pdf["copied"] and pdf["value"].startswith(".orkcraft/pit/")
    assert pdf["value"].endswith("-report.pdf") and (fake_repo / pdf["value"]).read_bytes() == b"%PDF-1.4 tiny"
    assert note["followed"] and [s["building"] for s in note["stops"]] == [loot_id]    # the text went on to Lake
    assert note["stops"][0]["event"] == "pit.text" and "ship on Friday" in note["stops"][0]["value"]
    assert not pdf["stops"]                                                              # no road takes files
    # a handler further down the chain ran on it: its cost is the drop's
    from orkcraft.realm import pipes, roads
    ref = f"{pit_id}:{note['id']}"
    hop = pipes.hop(loot_id, "keeper", "agent", cost=0.5, outcome="done")
    host.town.publish(bus.RUN, run=roads.HandlerRun(loot_id, "keeper", "agent", "r1", 0.0, trail=(hop,), ref=ref),
                      name="keeper")
    host.town.publish(bus.RUN, run=roads.HandlerRun(loot_id, "keeper", "agent", "r1", 0.0, trail=(hop,), ref=ref),
                      name="keeper")                                                     # the same hop counts once
    note = host.detail(pit_id)["data"]["items"][1]
    assert note["cost"] == 0.5
    c = _card(host, pit_id)
    assert (c["n"], c["last"]["kind"], c["spent"]) == (2, "doc", 0.5)


def test_the_pit_paste_is_its_quick_action(fake_repo, isolated_layout_file, monkeypatch):
    from orkcraft.core.workers.pit import PitWorker
    host = _host(fake_repo)
    pit_id = _raised(host, "pit")
    monkeypatch.setattr(PitWorker, "clipboard_reader", staticmethod(lambda: "https://example.com/spec"))
    assert host.command("building.quick", {"id": pit_id, "action": "pit.paste"}) is True
    [it] = host.detail(pit_id)["data"]["items"]
    assert (it["kind"], it["link"], it["value"]) == ("link", True, "https://example.com/spec")


def test_the_signpost_counts_per_road_out_in_its_colour_and_tests_a_text(fake_repo, isolated_layout_file):
    host = _host(fake_repo)
    post = _raised(host, "signpost", rules=["bugs: matches (?i)traceback|error", "links: contains http", "rest: else"])
    a, b, c = _raised(host, "loot"), _raised(host, "loot"), _raised(host, "loot")
    ts.subscribe(host.town.scroll, a, post, "signpost.routed", {"route": ["bugs"]})
    ts.subscribe(host.town.scroll, b, post, "signpost.routed", {"route": ["links"]})
    ts.subscribe(host.town.scroll, c, post, "signpost.unmatched")
    w = host.town.worker(post)
    from orkcraft.realm.pipes import Payload
    for text in ("Traceback: boom", "ERROR disk", "see http://x", "hello"):
        w.receive(Payload("text", text, "town_hall", "pit.text", text[:10]), text[:10], text)
    card = _card(host, post)
    counts = {r["label"]: (r["count"], r["color"]) for r in card["roads"]}
    assert counts["bugs"][0] == 2 and counts["links"][0] == 1 and counts["no rule"][0] == 0
    assert len({col for _, col in counts.values()}) == 3                       # a colour per road
    assert card["total"] == 4 and card["last"]["route"] == "rest" and card["last"]["title"] == "hello"
    assert set(card["tints"]) == {r["key"] for r in card["roads"]}           # the town paints their starts
    roads = {r["id"] for r in host.snapshot()["roads"]}
    assert set(card["tints"]) <= roads
    d = host.detail(post)["data"]
    assert d["rules"][0].startswith("bugs:") and not d["problems"] and d["routes"] == ["bugs", "links", "rest"]
    assert [h["route"] for h in d["history"]] == ["rest", "links", "bugs", "bugs"]
    assert d["colors"]["bugs"] == counts["bugs"][1] and d["counts"] == {"bugs": 2, "links": 1, "rest": 1}
    got = host.command("act", {"id": post, "act": "test", "args": {"text": "a Traceback here"}})
    assert got == {"route": "bugs", "rule": "bugs: matches (?i)traceback|error", "index": 0}
    assert host.detail(post)["data"]["counts"]["bugs"] == 2                    # a test sends nothing
    w.set_rules(["only: contains zzz"])
    assert host.command("act", {"id": post, "act": "test", "args": {"text": "nothing"}})["route"] == ""
    with pytest.raises(CommandError):
        host.command("act", {"id": post, "act": "test", "args": {"text": ""}})


def test_the_mill_shows_every_step_of_a_run_and_its_steps_are_edited(fake_repo, isolated_layout_file):
    host = _host(fake_repo)
    grinder = _raised(host, "mill", steps=["lines", "grep: ERROR", "count"])
    assert _card(host, grinder)["state"] == "none"
    with pytest.raises(CommandError):                                         # nothing arrived yet
        host.command("act", {"id": grinder, "act": "run", "args": {}})
    w = host.town.worker(grinder)
    from orkcraft.realm.pipes import Payload
    w.receive(Payload("text", "INFO a\nERROR b\nERROR c", "town_hall", "pit.text", "log"), "log", "")
    _wait(lambda: w.runs and not w.running)
    card = _card(host, grinder)
    assert card["state"] == "ok" and card["at"]
    d = host.detail(grinder)["data"]
    run = d["runs"][0]
    assert run["ok"] and [s["step"] for s in run["steps"]] == ["lines", "grep: ERROR", "count"]
    assert "ERROR b" in run["steps"][1]["out"] and "INFO" not in run["steps"][1]["out"]
    assert run["steps"][2]["out"] == '{"count": 2}' and run["input"].startswith("INFO a") and d["failed"] is None
    assert host.command("act", {"id": grinder, "act": "set_steps", "args": {"steps": "trim\n\njson\n"}}) is True
    assert host.town.custom_specs[grinder]["config"]["steps"] == ["trim", "json"]
    with pytest.raises(CommandError):
        host.command("act", {"id": grinder, "act": "set_steps", "args": {"steps": "frobnicate"}})
    assert host.command("building.quick", {"id": grinder, "action": "mill.run"}) is True     # Run, again
    _wait(lambda: len(w.runs) == 2 and not w.running)
    d = host.detail(grinder)["data"]
    assert not d["runs"][0]["ok"] and d["failed"] == 2 and d["runs"][0]["failed"] == 2
    assert "error" in d["runs"][0]["steps"][-1] and _card(host, grinder)["state"] == "failed"
    assert _card(host, grinder)["failed"] == 2 and _card(host, grinder)["runs"] == 2


def test_the_mill_queues_while_it_mills(fake_repo, isolated_layout_file):
    slow = f"script: {sys.executable} -c \"import sys, time; time.sleep(0.3); print(sys.stdin.read())\""
    host = _host(fake_repo)
    grinder = _raised(host, "mill", steps=[slow])
    w = host.town.worker(grinder)
    w.run_steps("one", title="first")
    w.run_steps("two", title="second")
    d = host.detail(grinder)["data"]
    assert d["running"] and d["current"]["title"] == "first" and [q["title"] for q in d["queue"]] == ["second"]
    assert _card(host, grinder) == {"state": "running", "at": d["current"]["started"], "queue": 1, "title": "first",
                                    "steps": 1, "runs": 0}
    _wait(lambda: len(w.runs) == 2 and not w.running)


def test_a_signpost_route_no_road_takes_is_a_stub_on_the_map(fake_repo, isolated_layout_file):
    """A route of the rules with no road out is drawn as a stub to pull a road from; a road for every route takes all."""
    host = _host(fake_repo)
    post = _raised(host, "signpost", rules=["bugs: contains error", "new-meeting: contains invite", "rest: else"])
    a, b = _raised(host, "loot"), _raised(host, "loot")
    ts.subscribe(host.town.scroll, a, post, "signpost.routed", {"route": ["bugs"]})
    ts.subscribe(host.town.scroll, b, post, "signpost.unmatched")
    w = host.town.worker(post)
    assert w.loose_ends() == [{"route": "new-meeting", "name": "new meeting", "event": "signpost.routed#new-meeting"},
                              {"route": "rest", "name": "rest", "event": "signpost.routed#rest"}]
    assert next(x for x in host.snapshot()["buildings"] if x["id"] == post)["loose"] == w.loose_ends()
    assert host.command("roads.lay", {"from": post, "to": b, "event": "signpost.routed#rest", "handler": None})
    assert [x["route"] for x in w.loose_ends()] == ["new-meeting"]
    ts.subscribe(host.town.scroll, a, post, "signpost.routed")                 # every route
    assert w.loose_ends() == []
