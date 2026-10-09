"""📅 Calendar (T1105 stage 6): now / next from .ics, due events, the morning digest, adding."""
from __future__ import annotations

import datetime as dt
from pathlib import Path


from orkcraft.realm import daybook

SIZE = (200, 46)
DAY = dt.date(2026, 10, 2)
ICS = """BEGIN:VCALENDAR
BEGIN:VEVENT
DTSTART:20261002T090000
DTEND:20261002T100000
SUMMARY:Standup
END:VEVENT
BEGIN:VEVENT
DTSTART:20261002T140000
DTEND:20261002T150000
SUMMARY:Review
LOCATION:Room 2
END:VEVENT
BEGIN:VEVENT
DTSTART;VALUE=DATE:20261003
SUMMARY:Holiday
END:VEVENT
END:VCALENDAR
"""


def at(h: int, m: int = 0, day: dt.date = DAY) -> dt.datetime:
    return dt.datetime.combine(day, dt.time(h, m))


def test_now_next_due_digest_and_changes(tmp_path: Path):
    f = tmp_path / "cal.ics"
    f.write_text(ICS)
    day = daybook.load(daybook.sources(tmp_path, "cal.ics", tmp_path / "own.ics"), DAY)
    assert [e.summary for e in day.events] == ["Standup", "Review", "Holiday"]
    cur, nxt, left = daybook.now_and_next(day.events, at(9, 30))
    assert cur.summary == "Standup" and nxt.summary == "Review" and left == 1
    assert [e.summary for e in daybook.due(day.events, at(13, 59), at(14, 0))] == ["Review"]
    assert daybook.line(day.events[1]) == "14:00–15:00 Review @ Room 2"
    assert "2 events" in daybook.digest(day.events, DAY) and "- 09:00–10:00 Standup" in daybook.digest(day.events, DAY)
    daybook.add_event(f, "Lunch, with Ann", at(12), 45)
    again = daybook.load(daybook.sources(tmp_path, "cal.ics", tmp_path / "own.ics"), DAY)
    assert [(e, x.summary) for e, x in daybook.changes(day.events, again.events)] == [("calendar.event_added",
                                                                                      "Lunch, with Ann")]
    assert daybook.parse_when("tomorrow 9:15", DAY) == at(9, 15, DAY + dt.timedelta(days=1))
    assert daybook.parse_when("2026-10-05 14:00", DAY) == at(14, 0, dt.date(2026, 10, 5))
    url = daybook.sources(tmp_path, "https://example.com/c.ics", tmp_path / "own.ics")
    assert url[0].url and daybook.writable(tmp_path, "https://example.com/c.ics", tmp_path / "own.ics") == tmp_path / "own.ics"


# -- documents for meetings: [meet:<id>] -----------------------------------------------------------

MEETINGS = """BEGIN:VCALENDAR
BEGIN:VEVENT
UID:one-on-one-ann@example.com
DTSTART:20261002T140000
DTEND:20261002T143000
SUMMARY:1:1 Ann
END:VEVENT
BEGIN:VEVENT
DTSTART:20261002T160000
DTEND:20261002T170000
SUMMARY:Retro
END:VEVENT
END:VCALENDAR
"""


def test_uids_are_parsed_or_a_stable_hash(tmp_path: Path):
    from orkcraft.sources import ics
    events = ics.parse_ics(MEETINGS, "work", DAY, DAY)
    assert events[0].uid == "one-on-one-ann@example.com"
    fallback = events[1].uid
    assert fallback and fallback != events[0].uid
    assert ics.parse_ics(MEETINGS, "work", DAY, DAY)[1].uid == fallback               # stable
    assert ics.parse_ics(MEETINGS.replace("Retro", "Retro 2"), "work", DAY, DAY)[1].uid != fallback
    weekly = MEETINGS.replace("SUMMARY:1:1 Ann", "SUMMARY:1:1 Ann\nRRULE:FREQ=DAILY;COUNT=2")
    a, b = [e for e in ics.parse_ics(weekly, "work", DAY, DAY + dt.timedelta(days=1)) if e.summary == "1:1 Ann"]
    assert a.uid == b.uid and daybook.meet_id(a) != daybook.meet_id(b)            # each occurrence its own
    tag = f"[meet:{daybook.meet_id(a)}]"
    assert daybook.meet_tag(f"**1:1 Ann {tag}** — done") == daybook.meet_id(a) and daybook.meet_tag("none") == ""
    assert daybook.parse_lead("30m") == dt.timedelta(minutes=30) and daybook.parse_lead("24h") == dt.timedelta(days=1)
    assert daybook.parse_lead("") == daybook.parse_lead("soon") == dt.timedelta(hours=2)


def test_barracks_keeps_the_meeting_tag_in_the_task_title(monkeypatch):
    from orkcraft.core.workers.barracks import BarracksWorker
    from orkcraft.realm import pipes
    got = []
    monkeypatch.setattr(BarracksWorker, "add_task", lambda self, title, text, key="", **kw: got.append(title))
    view = BarracksWorker.__new__(BarracksWorker)
    tag = "[meet:0123456789ab]"
    view.receive(pipes.Payload(pipes.TEXT, f"14:00 1:1 Ann (Fri 02) {tag}", "signpost", "signpost.routed", "1on1"), "", "")
    view.receive(pipes.Payload(pipes.TEXT, "x", "drum", "calendar.event_upcoming", "A" * 90 + " " + tag), "", "")
    view.receive(pipes.Payload(pipes.TEXT, "plain", "pit", "pit.text", "plain"), "", "")
    assert got[0] == f"1on1 {tag}" and got[1].endswith(tag) and len(got[1]) <= 80 and got[2] == "plain"
