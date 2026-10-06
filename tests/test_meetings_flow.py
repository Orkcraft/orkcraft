"""A mail that asks to meet becomes an event, and the event gets its brief: a Clan Fire that routes names
a time (`WHEN:`), a War Drum adds the event from a cart's `When:` line and asks for its document at once
(`prepare_new`), a Barracks reads its Scroll Dump first (`notes`), and the brief comes back to the event
by a return road — and the demo's Meetings orkspace plays it all (demo/meetings.py)."""
from __future__ import annotations

import datetime as dt
import json
import re
import time
from pathlib import Path

import pytest

from orkcraft import demo
from orkcraft import scroll as ts
from orkcraft.core.town import Town
from orkcraft.core.workers.war_drum import WarDrumWorker
from orkcraft.demo import meetings as mt
from orkcraft.gui import state
from orkcraft.gui.host import Host
from orkcraft.realm import daybook, masonry, pipes, roads
from orkcraft.realm import team as tm

WORDING = re.compile(r"\b[Oo]rcs?\b|[Oo]rchestrat")
DAY = dt.date(2026, 10, 6)


def _wait(cond, seconds: float = 20.0) -> None:
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if cond():
            return
        time.sleep(0.02)
    raise AssertionError("never happened")


# -- a time in words ----------------------------------------------------------------------------------

def test_a_when_line_names_a_time():
    assert daybook.find_when("When: tomorrow 11:00, 30 min\n\nHi", DAY) == (dt.datetime(2026, 10, 7, 11, 0), 30)
    assert daybook.find_when("**WHEN:** 2026-10-08 14:00 · 45 min", DAY) == (dt.datetime(2026, 10, 8, 14, 0), 45)
    assert daybook.find_when("when: today at 9:30", DAY) == (dt.datetime(2026, 10, 6, 9, 30), 30)
    assert daybook.find_when("Can we meet at 11:00?", DAY) is None              # only a When: line counts
    assert daybook.find_when("When: soon", DAY) is None and daybook.find_when("When: 25:00", DAY) is None


def test_the_steward_names_when_and_the_routed_document_carries_it():
    def run(harness, prompt, model):
        if prompt.startswith("You are the steward"):
            return "DECISION: approve\nROUTE: meeting\nTASK: Kickoff\nWHEN: tomorrow 11:00, 30 min\nFree then.", 0.0
        return "APPROVE: fine", 0.0
    seen = []
    d = tm.new("Meet tomorrow?", "Can we meet?")
    tm.run(d, tm.members_of({"members": ["Productivity pulse:claude"]}), tm.Steward(), set(), 1, 1.0,
           lambda h, p, m: seen.append(p) or run(h, p, m), routes=["meeting", "task"])
    assert (d.route, d.task, d.when, d.decision) == ("meeting", "Kickoff", "tomorrow 11:00, 30 min", "Free then.")
    assert "WHEN: <tomorrow 11:00, 30 min>" in seen[-1]
    assert tm.routed_text(d) == "When: tomorrow 11:00, 30 min\n\nCan we meet?"
    d.when = ""
    assert tm.routed_text(d) == "Can we meet?"


# -- the War Drum adds the event and asks for its document --------------------------------------------

@pytest.fixture
def drum(fake_repo: Path, monkeypatch):
    (fake_repo / "cal.ics").write_text("BEGIN:VCALENDAR\r\nEND:VCALENDAR\r\n")
    spec = {"id": "drum", "title": "Calendar", "icon": "🥁", "orc": {"name": "Drummer"}, "type": "war_drum",
            "config": {"ics": "cal.ics", "prepare_new": True, "beats": ["meeting"]}}
    assert masonry.save_spec(fake_repo, spec) == []
    monkeypatch.setattr(WarDrumWorker, "clock", staticmethod(lambda: dt.datetime.combine(DAY, dt.time(9, 0))))
    town = Town(fake_repo)
    for ev in ("calendar.event_added", "calendar.event_upcoming"):
        ts.subscribe(town.scroll, "town_hall", "drum", ev)
    sent: list = []
    monkeypatch.setattr(town.roads, "emit", lambda payload, meta=None: sent.append(payload) or [])
    return town.worker("drum"), sent


def test_a_cart_that_names_a_time_becomes_an_event_whose_brief_is_asked_for_at_once(drum, fake_repo):
    w, sent = drum
    w.refresh()
    cart = pipes.Payload(pipes.TEXT, "When: tomorrow 11:00, 30 min\n\nCan we meet?", "triage", "team.routed",
                         "Kickoff with Alex", route="meeting")
    w.receive(cart, "", "")
    w.receive(cart, "", "")                                             # the same cart twice: one event
    [e] = w.day.events
    assert (e.summary, e.start) == ("Kickoff with Alex", dt.datetime(2026, 10, 7, 11, 0))
    assert "Kickoff with Alex" in (fake_repo / "cal.ics").read_text()
    mid = daybook.meet_id(e)
    assert [p.mode for p in sent] == ["calendar.event_added", "calendar.event_upcoming"]
    up = sent[-1]
    assert up.title == "Kickoff with Alex" and up.ref == f"drum:{mid}" and f"[meet:{mid}]" in up.value
    w.receive(pipes.Payload(pipes.TEXT, "no time here", "x", "pit.text", "Lunch"), "", "")
    assert len(w.day.events) == 1                                       # a cart without a time adds nothing


def test_the_brief_comes_back_under_the_meetings_ref_with_its_link(drum, fake_repo):
    from orkcraft.gui.views import war_drum as view
    w, _ = drum
    start = w.add("Kickoff", "tomorrow 11:00")
    e = next(x for x in w.day.events if x.start == start)
    report = ("**Kickoff** — Grub (claude)\n\nBrief ready: Kickoff\n\nBrief: https://example.com/docs/brief\n\n"
              "## Agenda\n1. Goals")
    w.receive(pipes.Payload(pipes.TEXT, report, "camp", "pool.done", "Kickoff", ref=f"drum:{daybook.meet_id(e)}"),
              "", report)
    doc = w.doc_of(e)
    assert doc["link"] == "https://example.com/docs/brief"
    assert (fake_repo / doc["path"]).read_text().startswith("Brief ready: Kickoff")    # the report, not who did it
    card = view.card(w)
    assert [(b["title"], b["doc"]) for b in card["beats"]] == [("Kickoff", True)] and card["kinds"] == ["meeting"]
    assert view.detail(w)["days"][1]["events"][0]["link"] == "https://example.com/docs/brief"
    assert w.jobs() == [] and w.limits() == []                         # `beats`: a calendar of meetings alone


def test_the_signs_and_the_outcome_a_cart_reads_as():
    road = ts.Road("r", "a", "x.y", label="new-meeting")
    assert state.sign(road) == "new meeting"
    assert state.outcome("**Kickoff** — Grub (claude)\n\n## Brief ready: Kickoff\n\nmore") == "Brief ready: Kickoff"
    assert state.outcome("") == ""


def test_a_return_road_back_to_the_calendar_takes_only_its_own_work():
    flt = {"returns": True}
    assert roads.passes(flt, pipes.Payload(pipes.TEXT, "x", "camp", "pool.done", "t", ref="drum:abc"), {}, "drum")[0]
    assert not roads.passes(flt, pipes.Payload(pipes.TEXT, "x", "camp", "pool.done", "t", ref="board:1"), {}, "drum")[0]


# -- the demo's Meetings ----------------------------------------------------------------------------------

def test_meetings_stands_in_the_dashboard_set_with_signed_roads():
    summary = {s["id"]: s for s in demo.scenario_summary("dashboard")}
    assert summary[mt.ID]["hotkey"] == "F6"
    scroll = demo.make_scroll(demo.SETS["dashboard"])
    assert set(scroll.orkspace(mt.ID).buildings) == {mt.POST, mt.TRIAGE, mt.DRUM, mt.NOTES, mt.CAMP, mt.LOOT}
    drum = scroll.building(mt.DRUM)
    assert {r.label: r.filter for r in drum.roads} == {"new-meeting": {"route": ["meeting"]},
                                                       "the-brief": {"returns": True}}
    assert all("-" in r[3] for r in mt.MEETINGS["roads"][1:])           # each road after the mail wears a sign


def test_what_a_person_reads_of_meetings_says_ork_never_orc():
    texts = [mt.MEETINGS["name"], mt.MEETINGS["story"], json.dumps(mt.TRIAGE_SCRIPT, ensure_ascii=False),
             mt.BRIEF, json.dumps(mt.WIKI_PAGES), json.dumps(mt.SOURCE_NOTES), mt.MAIL["title"], mt.MAIL["body"]]
    texts += [b["title"] + " " + b["summary"] for b in mt.MEETINGS["buildings"]]
    texts += [r[3] for r in mt.MEETINGS["roads"]]
    assert not [t for t in texts if WORDING.search(t)]
    assert [b["title"] for b in mt.MEETINGS["buildings"]] == ["Inbox", "Triage", "Calendar", "Notes",
                                                              "Agents at work", "Results"]


def test_meetings_plays_the_whole_flow(tmp_path: Path):
    from orkcraft.gui.views import loot as loot_view
    from orkcraft.gui.views import scrolls as scrolls_view
    root = demo.build(tmp_path / "dash", set_name="dashboard")
    for kind, bid in (("council", mt.TRIAGE), ("barracks", mt.CAMP)):    # no pauses: the film needs them, a test not
        path = root / ".orkcraft" / kind / bid / "simulated.json"
        script = json.loads(path.read_text(encoding="utf-8"))
        for rules in [script.get("steward", []), script.get("work", [])] + list(script.get("members", {}).values()):
            for rule in rules:
                rule["seconds"] = 0.05
        path.write_text(json.dumps(script), encoding="utf-8")
    host = Host(root, False, root / ".orkcraft.json", demo=True)
    try:
        host.town.call = lambda fn, *a: fn(*a)
        sent: list = []
        emit = host.town.roads.emit
        host.town.roads.emit = lambda payload, meta=None: sent.append(payload) or emit(payload, meta)
        host.command("act", {"id": mt.POST, "act": "simulate", "args": mt.MAIL})
        drum, notes, loot = (host.town.worker(b) for b in (mt.DRUM, mt.NOTES, mt.LOOT))
        _wait(lambda: drum.docs())
        triage = host.town.worker(mt.TRIAGE).current
        assert (triage.route, triage.task, triage.when) == ("meeting", mt.EVENT, mt.WHEN)
        event = next(e for e in drum.day.events if e.summary == mt.EVENT)
        assert (event.start.hour, event.start.minute) == (11, 0) and event.day == dt.date.today() + dt.timedelta(days=1)
        doc = drum.doc_of(event)
        assert doc["link"] == mt.BRIEF_LINK and "## Agenda" in (root / doc["path"]).read_text()
        assert notes.lent["task"] == mt.EVENT and notes.lent["by"] == mt.CAMP
        assert sorted(notes.lent["pages"]) == ["New project: decisions so far", "New project: goals",
                                               "New project: open questions"]   # the project's, not the team's
        assert scrolls_view.card(notes)["lent"]["pages"] == notes.lent["pages"]
        modes = [p.mode for p in sent]
        assert modes.index("team.routed") < modes.index("calendar.event_upcoming") < modes.index("knowledge.chunks") \
            < modes.index("pool.done")
        chunks = next(p for p in sent if p.mode == "knowledge.chunks")
        assert chunks.title == mt.EVENT and chunks.ref.startswith(f"{mt.DRUM}:")      # the task keeps its ref
        assert not any("[meet:" in p.title for p in sent)                              # clean titles all the way
        _wait(lambda: len(loot.stored) == 1)
        assert loot_view.card(loot)["latest"] == mt.BRIEF_TITLE
        assert [x["outcome"] for x in loot_view.detail(loot)["delivered"]] == [mt.BRIEF_TITLE]
    finally:
        host.close()
