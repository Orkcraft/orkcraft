"""🥁 War Drum in the core and in the GUI: the worker without a face, its card, detail and acts."""
from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest

from orkcraft import scroll as ts
from orkcraft.core.town import Town
from orkcraft.core.workers.war_drum import WarDrumWorker
from orkcraft.design import ui
from orkcraft.gui.host import CommandError, Host
from orkcraft.realm import checkpoint, daybook, masonry, pipes

DAY = dt.date(2026, 10, 2)
ICS = """BEGIN:VCALENDAR
BEGIN:VEVENT
UID:standup@x
DTSTART:20261002T090000
DTEND:20261002T093000
SUMMARY:Standup
END:VEVENT
BEGIN:VEVENT
UID:ann@x
DTSTART:20261002T140000
DTEND:20261002T143000
SUMMARY:1:1 Ann
LOCATION:Room 2
END:VEVENT
BEGIN:VEVENT
DTSTART:20261002T160000
DTEND:20261002T170000
SUMMARY:Retro
END:VEVENT
BEGIN:VEVENT
DTSTART:20261002T173000
DTEND:20261002T180000
SUMMARY:Wrap-up
END:VEVENT
BEGIN:VEVENT
DTSTART:20261003T100000
DTEND:20261003T110000
SUMMARY:Planning
END:VEVENT
END:VCALENDAR
"""


def at(h: int, m: int = 0) -> dt.datetime:
    return dt.datetime.combine(DAY, dt.time(h, m))


@pytest.fixture
def clock(monkeypatch):
    now = {"now": at(9, 10)}
    monkeypatch.setattr(WarDrumWorker, "clock", staticmethod(lambda: now["now"]))
    return now


def _drum(repo: Path) -> None:
    (repo / "cal.ics").write_text(ICS)
    spec = {"id": "drum", "title": "Drum", "icon": "🥁", "orc": {"name": "Drummer"}, "type": "war_drum",
            "config": {"ics": "cal.ics", "day_starts": "08:00"}}
    assert masonry.save_spec(repo, spec) == []


def test_the_drum_worker_keeps_the_day_without_a_face(fake_repo, clock, monkeypatch):
    _drum(fake_repo)
    town = Town(fake_repo)
    for ev in ("calendar.event_due", "calendar.day_schedule", "calendar.event_upcoming", "calendar.event_added"):
        ts.subscribe(town.scroll, "town_hall", "drum", ev)
    sent: list = []
    monkeypatch.setattr(town.roads, "emit", lambda payload, meta=None: sent.append(payload) or [])
    w = town.worker("drum")
    assert isinstance(w, WarDrumWorker) and [e.summary for e in w.today()] == ["Standup", "1:1 Ann", "Retro", "Wrap-up"]
    w.tick()
    assert [p.mode for p in sent] == ["calendar.day_schedule"] and w.mini_status()[0] == "▶ Standup"
    clock["now"] = at(12, 0)
    w.tick()
    assert sent[-1].mode == "calendar.event_upcoming" and sent[-1].title == "1:1 Ann" \
        and sent[-1].ref == f"drum:{daybook.meet_id(w.today()[1])}" and "[meet:" in sent[-1].value
    assert w.prepare() == "" and sent[-1].title.startswith("1:1 Ann")              # the next meeting, at once
    start = w.add("Lunch", "12:30", 45)
    assert start == at(12, 30) and sent[-1].mode == "calendar.event_added" and "Lunch" in (fake_repo / "cal.ics").read_text()
    ann = w.event(daybook.meet_id(w.today()[2]))                    # Lunch now comes before Ann
    assert ann.summary == "1:1 Ann" and w.open_doc(ann) is None
    w.receive(pipes.Payload(pipes.TEXT, "# Notes for Ann", "pool", "pool.done", f"x [meet:{daybook.meet_id(ann)}]"),
              "", "# Notes for Ann")
    doc = w.open_doc(ann)
    assert doc["title"] == "📄 1:1 Ann" and not doc["sent"] and (fake_repo / doc["path"]).read_text() == "# Notes for Ann"


def _host(repo: Path) -> Host:
    checkpoint.ensure(repo)
    return Host(repo, auto_commit=False)


def test_the_drum_in_the_gui_card_detail_and_acts(fake_repo, clock):
    _drum(fake_repo)
    host = _host(fake_repo)
    w = host.town.worker("drum")
    hut = next(b for b in host.snapshot()["buildings"] if b["id"] == "drum")
    card = hut["card"]
    assert hut["page"] and [(b["kind"], b["at"], b["title"], b["now"], b["doc"]) for b in card["beats"]] == [
        ("meeting", "09:00", "Standup", True, False), ("meeting", "14:00", "1:1 Ann", False, False),
        ("meeting", "16:00", "Retro", False, False), ("meeting", "17:30", "Wrap-up", False, False),
        ("meeting", "10:00", "Planning", False, False)]                  # tomorrow's too
    assert card["left"] == 3 and card["now"] == "09:10" and not card["error"]
    d = host.detail("drum")
    assert [leaf.pane["id"] for leaf in ui.leaves(d["ui"])] == ["head", "week", "day", "settings"]   # a meeting opens over the agenda
    data = d["data"]
    assert data["left"] == 3 and len(data["days"]) == 7 and data["days"][1]["events"][0]["title"] == "Planning"
    standup, ann = data["days"][0]["events"][:2]
    assert standup["now"] and data["current"] == standup["id"] and data["next"] == ann["id"]
    assert (ann["start"], ann["end"], ann["location"], ann["from_min"], ann["doc"]) == ("14:00", "14:30", "Room 2", 840, "")

    act = lambda name, **args: host.command("act", {"id": "drum", "act": name, "args": args})
    with pytest.raises(CommandError):
        act("doc", id=ann["id"])                                        # no document yet
    with pytest.raises(CommandError):
        act("prepare", id=ann["id"])                                    # no road carries `meeting soon`
    ts.subscribe(host.town.scroll, "town_hall", "drum", "calendar.event_upcoming")
    assert act("prepare", id=ann["id"]).startswith("14:00–14:30 1:1 Ann")
    host.town.deliver("drum", pipes.Payload(pipes.TEXT, "# Ann", "pool", "pool.done", f"[meet:{ann['id']}]"), "", "# Ann")
    doc = act("doc", id=ann["id"])
    assert doc["path"].endswith(f"{ann['id']}.md") and host.detail("drum")["data"]["days"][0]["events"][1]["doc"]
    assert next(b for b in host.snapshot()["buildings"] if b["id"] == "drum")["card"]["beats"][1]["doc"]

    assert act("add", title="Lunch", when="12:30", minutes=30) == "Fri 02 12:30"
    assert "Lunch" in [e["title"] for e in host.detail("drum")["data"]["days"][0]["events"]]
    for bad in ({"title": " ", "when": "12:00"}, {"title": "x", "when": "someday"}, {"title": "x", "when": "12:00", "minutes": 0}):
        with pytest.raises(CommandError):
            act("add", **bad)
    assert act("settings", day_starts="07:30", lead="1h30m") and w.lead == dt.timedelta(minutes=90)
    for bad in ({"day_starts": "7"}, {"lead": "soon"}):
        with pytest.raises(CommandError):
            act("settings", **bad)
    with pytest.raises(CommandError):
        act("doc", id="nope")
