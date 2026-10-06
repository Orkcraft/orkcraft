"""Triage by a Clan Fire that routes, and what the Task Fields make of it: the steward names who takes a
message on (`team.routed` with its route), roads wait for one route, a cart for the person becomes one
of their to-dos and one for an agent a task the board sends to a Barracks, whose progress comes back to
the card over return roads — and the demo's Front Desk plays it all (demo/front_desk.py)."""
from __future__ import annotations

import json
import re
import time
from pathlib import Path

import pytest

from orkcraft import demo
from orkcraft import scroll as ts
from orkcraft.core import buildings
from orkcraft.demo import front_desk as fd
from orkcraft.gui.host import Host
from orkcraft.realm import checkpoint, pipes, roads, tasklist
from orkcraft.realm import team as tm

WORDING = re.compile(r"\b[Oo]rcs?\b|[Oo]rchestrat")


def _wait(cond, seconds: float = 20.0) -> None:
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if cond():
            return
        time.sleep(0.02)
    raise AssertionError("never happened")


# -- the clan routes ----------------------------------------------------------------------------------

def _runner(decision: str):
    def run(harness, prompt, model):
        return (decision, 0.0) if prompt.startswith("You are the steward") else ("APPROVE: fine", 0.0)
    return run


def test_the_steward_names_a_route_and_the_prompt_asks_for_one():
    team = tm.members_of({"members": ["Risk analyst:claude", "Tone reader:claude"]})
    seen = []
    d = tm.new("Summary by Friday", "Could someone sum up the feedback?")
    run = _runner("DECISION: approve\nROUTE: agent\nRoutine.")
    tm.run(d, team, tm.Steward("triage"), set(), 1, 1.0, lambda h, p, m: seen.append(p) or run(h, p, m),
           routes=["human", "agent"])
    assert (d.outcome, d.route, d.decision) == ("approved", "agent", "Routine.")
    assert "ROUTE: <one of human, agent>" in seen[-1]
    assert "→ agent" in tm.report_markdown(d, team)


def test_an_approval_without_a_route_goes_to_the_person():
    d = tm.new("A message", "hello")
    tm.run(d, tm.members_of({}), tm.Steward(), set(), 1, 1.0, _runner("DECISION: approve\nLooks fine."),
           routes=["human", "agent"])
    assert d.outcome == "asked" and not d.route and "human, agent" in d.question


def test_a_clan_that_does_not_route_reads_as_before():
    d = tm.new("A plan", "1. ship")
    tm.run(d, tm.members_of({}), tm.Steward(), set(), 1, 1.0, _runner("DECISION: approve\nROUTE: agent\nok"))
    assert d.outcome == "approved" and d.route == ""


def test_routes_are_spelled_as_road_filters_and_parsed_from_the_answer():
    assert tm.routes_of({"routes": ["Human", "an agent", "human"]}) == ["human", "an-agent"]
    assert tm.parse_route("**ROUTE:** human\nyours", ["human", "agent"]) == ("human", "yours")
    assert tm.parse_route("ROUTE: nobody", ["human"])[0] == ""


def test_the_scripted_sandbox_clan_says_its_lines():
    script = {"members": {"Tone reader": [{"match": "review", "say": "APPROVE: stressed"}]},
              "steward": [{"match": "review", "say": "DECISION: approve\nROUTE: human\nyours"}]}
    run = tm.scripted(script)
    d = tm.new("Can we move the review?", "doc")
    tm.run(d, tm.members_of({"members": ["Tone reader:claude", "Other:claude"]}), tm.Steward(), set(), 1, 1.0, run,
           routes=["human", "agent"])
    assert d.route == "human"
    assert [t.text for t in d.reviews()] == ["stressed", "— _(demo — simulated)_"]


# -- roads that wait for a route, return roads ----------------------------------------------------------

def test_a_road_waits_for_its_route_and_a_return_road_for_its_own_work():
    routed = pipes.Payload(pipes.TEXT, "doc", "fire", "team.routed", "Dana: move the review?", route="human")
    assert roads.passes({"route": ["human"]}, routed, {})[0]
    assert not roads.passes({"route": ["agent"]}, routed, {})[0]
    post = pipes.Payload(pipes.TEXT, "x", "post", "signpost.routed", "bugs")         # a Signpost's: by its title
    assert roads.passes({"route": ["bugs"]}, post, {})[0] and not roads.passes({"route": ["rest"]}, post, {})[0]
    back = pipes.Payload(pipes.TEXT, "done", "camp", "pool.done", "t", ref="board:summary")
    assert roads.passes({"returns": True}, back, {}, "board")[0]
    assert roads.passes({"returns": True}, back, {}, "other")[1] == "not its own work"


def test_a_return_road_closes_no_loop_but_a_plain_road_back_does(fake_repo, isolated_layout_file):
    checkpoint.ensure(fake_repo)
    host = Host(fake_repo, auto_commit=False)
    board = buildings.raise_spec(host.town, buildings.type_spec(host.town, "fields")).id
    camp = buildings.raise_spec(host.town, buildings.type_spec(host.town, "barracks")).id
    scroll = host.town.scroll
    ts.subscribe(scroll, camp, board, "tasks.sent")
    ts.subscribe(scroll, board, camp, "pool.done", {"returns": True})
    assert not ts.validate(scroll.to_dict()) if hasattr(scroll, "to_dict") else True
    with pytest.raises(ValueError, match="loop"):
        ts.subscribe(scroll, board, camp, "pool.assigned")


def test_a_clan_that_routes_offers_a_road_per_route(fake_repo, isolated_layout_file):
    checkpoint.ensure(fake_repo)
    host = Host(fake_repo, auto_commit=False)
    spec = buildings.type_spec(host.town, "council")
    spec["config"] = {**(spec.get("config") or {}), "routes": ["human", "agent"]}
    fire = buildings.raise_spec(host.town, spec).id
    board = buildings.raise_spec(host.town, buildings.type_spec(host.town, "fields")).id
    events = {c["event"] for c in host.command("roads.choices", {"from": fire, "to": board})}
    assert {"team.routed#human", "team.routed#agent"} <= events


# -- the board takes it in -------------------------------------------------------------------------------

@pytest.fixture
def board(fake_repo, isolated_layout_file):
    checkpoint.ensure(fake_repo)
    host = Host(fake_repo, auto_commit=False)
    spec = buildings.type_spec(host.town, "fields")
    spec["config"] = {**(spec.get("config") or {}), "path": "BOARD.md", "mine_routes": ["human"]}
    bid = buildings.raise_spec(host.town, spec).id
    yield host, bid, host.town.worker(bid)
    host.close()


def test_a_cart_for_the_person_is_a_to_do_and_one_for_an_agent_a_task(board):
    _host, bid, w = board
    w.receive(pipes.Payload(pipes.TEXT, "Hi, can we move it?", "fire", "team.routed", "Dana: move the review?",
                            route="human"), "", "")
    w.receive(pipes.Payload(pipes.TEXT, "Sum up the feedback", "fire", "team.routed", "Sam: feedback summary",
                            route="agent"), "", "")
    w.receive(pipes.Payload(pipes.TEXT, "no route at all", "pit", "pit.text", "Plain cart"), "", "")
    lanes = {c.title: c.column for c in w.cards}
    assert lanes["Dana: move the review?"] == tasklist.MINE
    assert lanes["Sam: feedback summary"] == "todo" and lanes["Plain cart"] == "todo"
    assert "Dana: move the review?" not in w.seen()          # what a road brought is new to the person


def test_the_work_on_a_card_comes_back_to_it(board):
    _host, bid, w = board
    card = w.add("Feedback summary", "todo")
    ref = f"{bid}:{card.id}"
    w.receive(pipes.Payload(pipes.TEXT, "Grub (claude) ← Feedback summary", "camp", "pool.assigned", "t", ref=ref), "", "")
    assert (w.card(card.id).column, w.card(card.id).body) == ("in_progress", "⚒ Grub (claude) is on it")
    done = "**Feedback summary** — Grub (claude)\n\nShared with the team: https://example.com/tickets/142"
    w.receive(pipes.Payload(pipes.TEXT, done, "camp", "pool.done", "t", ref=ref), "", "")
    assert w.card(card.id).column == "done" and "tickets/142" in w.card(card.id).body
    assert len(w.cards) == 1                                  # no new card for its own work


def test_a_board_that_sends_new_tasks_sends_them_with_their_ref(board, monkeypatch):
    _host, bid, w = board
    sent = []
    monkeypatch.setattr(w, "emit", lambda ev, value, title="", trail=(), ref="", route="": sent.append((ev, ref)))
    w.save_config({"send_new": True})
    card = w.add("Feedback summary", "todo")
    assert ("tasks.sent", f"{bid}:{card.id}") in sent


# -- the demo's Front Desk --------------------------------------------------------------------------------

def test_the_front_desk_stands_in_the_dashboard_set():
    summary = {s["id"]: s for s in demo.scenario_summary("dashboard")}
    assert summary[fd.ID]["hotkey"] == "F5"
    scroll = demo.make_scroll(demo.SETS["dashboard"])
    desk = scroll.orkspace(fd.ID)
    assert set(desk.buildings) == {fd.POST, fd.TRIAGE, fd.BOARD, fd.CAMP, fd.LOOT}
    board = scroll.building(fd.BOARD)
    signs = {r.label: r.filter for r in board.roads if r.source == fd.TRIAGE}
    assert signs == {"task-for-human": {"route": ["human"]}, "task-for-agent": {"route": ["agent"]}}


def test_what_a_person_reads_of_the_front_desk_says_ork_never_orc():
    texts = [fd.FRONT_DESK["name"], fd.FRONT_DESK["story"], json.dumps(fd.TRIAGE_SCRIPT), json.dumps(fd.CAMP_SCRIPT)]
    texts += [b["title"] + " " + b["summary"] for b in fd.FRONT_DESK["buildings"]]
    texts += [r[3] for r in fd.FRONT_DESK["roads"]]
    assert not [t for t in texts if WORDING.search(t)]
    assert [b["title"] for b in fd.FRONT_DESK["buildings"]] == ["Inbox", "Triage", "Tasks", "Agents at work", "Results"]


def test_the_front_desk_plays_the_whole_flow(tmp_path: Path):
    root = demo.build(tmp_path / "dash", set_name="dashboard")
    for kind, bid in (("council", fd.TRIAGE), ("barracks", fd.CAMP)):     # no pauses: the film needs them, a test not
        path = root / ".orkcraft" / kind / bid / "simulated.json"
        script = json.loads(path.read_text(encoding="utf-8"))
        for rules in [script.get("steward", []), script.get("work", [])] + list(script.get("members", {}).values()):
            for rule in rules:
                rule["seconds"] = 0.05
        path.write_text(json.dumps(script), encoding="utf-8")
    host = Host(root, False, root / ".orkcraft.json", demo=True)
    try:
        host.town.call = lambda fn, *a: fn(*a)
        host.command("act", {"id": fd.POST, "act": "simulate", "args": fd.MAIL})
        board, triage = host.town.worker(fd.BOARD), host.town.worker(fd.TRIAGE)
        _wait(lambda: any(c.kind == tasklist.MINE and "Dana" in c.title for c in board.cards))
        assert triage.current.route == "human"
        assert [t.text for t in triage.current.reviews()][1] == "Stressed and apologetic: reply kindly."
        host.command("act", {"id": fd.POST, "act": "simulate", "args": fd.CHAT})
        _wait(lambda: any(c.column == "done" and "Sam" in c.title for c in board.cards))
        done = next(c for c in board.cards if c.column == "done" and "Sam" in c.title)
        assert fd.TICKET in done.body
        loot = host.town.worker(fd.LOOT)
        _wait(lambda: len(loot.stored) > 0)
        assert len(loot.stored) == 1 and len([c for c in board.cards if "Sam" in c.title]) == 1
        assert not any(c.kind == tasklist.TASK and "Dana" in c.title for c in board.cards)
    finally:
        host.close()


def test_only_the_sandbox_makes_messages_up(fake_repo, isolated_layout_file):
    checkpoint.ensure(fake_repo)
    host = Host(fake_repo, auto_commit=False)
    tower = buildings.raise_spec(host.town, buildings.type_spec(host.town, "watchtower")).id
    assert host.town.worker(tower).simulate("mail", "Ann: hi") is None


# -- the Inbox's card previews the newest message ----------------------------------------------------------

def test_the_watchtower_card_previews_the_newest_message(tmp_path: Path):
    from orkcraft.gui.views import watchtower as view
    root = demo.build(tmp_path / "dash", set_name="dashboard")
    host = Host(root, False, root / ".orkcraft.json", demo=True)
    try:
        host.town.call = lambda fn, *a: fn(*a)
        tower = host.town.worker(fd.POST)
        tower.simulate(**fd.MAIL)
        card = view.card(tower)
        assert [s["label"] for s in card["sources"]] == ["gmail", "slack"]
        newest = card["latest"][0]
        assert (newest["from"], newest["fresh"]) == ("Dana Reyes", True)
        assert newest["title"].startswith("Can we move Thursday") and len(card["latest"]) == 1
        lines = tower.hut_lines([16] * 3)                     # the TUI's wide hut: the counters, the preview
        assert lines[0] == "gmail 1 slack 0" and lines[1].startswith("✉ ") and "Dana" in lines[1]
        assert len(lines) == 3 and lines[2].endswith("…") and all(len(x) <= 16 for x in lines)
        assert tower.hut_lines([10] * 4)[:2] == ["gmail    1", "slack    0"]      # a narrow hut: the counters only
    finally:
        host.close()
