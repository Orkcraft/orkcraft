"""📅 Calendar (T1105 stage 6): now / next from .ics, due events, the morning digest, adding."""
from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest

from orkcraft import scroll as ts
from orkcraft.app import OrkcraftApp
from orkcraft.realm import daybook, masonry
from orkcraft.screens.dialogs import TextPrompt
from orkcraft.screens.typed.calendar_view import CalendarView

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


@pytest.mark.asyncio
async def test_the_calendar_building_ticks_digests_and_adds(fake_repo: Path, monkeypatch):
    (fake_repo / "cal.ics").write_text(ICS)
    spec = {"id": "days", "title": "Days", "icon": "📅", "orc": {"name": "Lookout"}, "type": "calendar",
            "config": {"ics": "cal.ics", "day_starts": "08:30"}}
    assert masonry.save_spec(fake_repo, spec) == []
    clock = {"now": at(8, 0)}
    monkeypatch.setattr(CalendarView, "clock", staticmethod(lambda: clock["now"]))
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    for ev in ("calendar.event_due", "calendar.day_schedule", "calendar.event_added"):
        ts.subscribe(app.scroll, "town_hall", "days", ev)
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        view = app.desktop.get_window("days").query_one(CalendarView)
        assert view.mini_status()[:2] == ["09:00 Standup", "2 left today"]
        sent = []
        monkeypatch.setattr(app.roads, "emit", lambda payload, meta=None: sent.append(payload) or [])
        clock["now"] = at(8, 45)
        view.tick()                                                  # past 08:30: the digest, once
        view.tick()
        assert [p.mode for p in sent] == ["calendar.day_schedule"] and "Standup" in sent[0].value
        clock["now"] = at(9, 1)
        view.tick()
        assert sent[-1].mode == "calendar.event_due" and sent[-1].value.startswith("09:00–10:00 Standup")
        assert view.mini_status()[0] == "▶ Standup"

        assert view.quick_action("calendar.new")
        await pilot.pause()
        assert isinstance(app.screen, TextPrompt)
        await pilot.press(*"Lunch", "enter", *"12:00", "enter", *"60", "enter")
        await pilot.pause()
        assert "SUMMARY:Lunch" in (fake_repo / "cal.ics").read_text()
        assert sent[-1].mode == "calendar.event_added" and "12:00–13:00 Lunch" in sent[-1].value
