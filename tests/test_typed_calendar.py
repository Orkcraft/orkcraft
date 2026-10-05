"""📅 Calendar (T1105 stage 6): now / next from .ics, due events, the morning digest, adding."""
from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest

from orkcraft import scroll as ts
from orkcraft.app import OrkcraftApp
from orkcraft.realm import daybook, masonry
from orkcraft.screens.dialogs import TextPrompt
from orkcraft.core.workers.war_drum import WarDrumWorker
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
    monkeypatch.setattr(WarDrumWorker, "clock", staticmethod(lambda: clock["now"]))
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


async def _calendar_app(repo: Path, monkeypatch, clock: dict, lake: bool = False, lead: str = "2h"):
    (repo / "cal.ics").write_text(MEETINGS)
    spec = {"id": "days", "title": "Days", "icon": "🥁", "orc": {"name": "Drummer"}, "type": "war_drum",
            "config": {"ics": "cal.ics", "lead": lead}}
    assert masonry.save_spec(repo, spec) == []
    if lake:
        assert masonry.save_spec(repo, {"id": "insight", "title": "Lake", "icon": "🌊", "orc": {"name": "Seer"},
                                        "type": "lake"}) == []
    monkeypatch.setattr(WarDrumWorker, "clock", staticmethod(lambda: clock["now"]))
    app = OrkcraftApp(repo_root=repo, auto_commit=False)
    if not ts.has_outgoing(app.scroll, "days", "calendar.event_upcoming"):        # a restart keeps the road
        ts.subscribe(app.scroll, "town_hall", "days", "calendar.event_upcoming")
    return app


@pytest.mark.asyncio
async def test_upcoming_goes_once_lead_before_and_not_again_after_a_restart(fake_repo: Path, monkeypatch):
    clock = {"now": at(11, 0)}
    app = await _calendar_app(fake_repo, monkeypatch, clock)
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        view = app.desktop.get_window("days").query_one(CalendarView)
        sent = []
        monkeypatch.setattr(app.roads, "emit", lambda payload, meta=None: sent.append(payload) or [])
        clock["now"] = at(11, 59)
        view.tick()
        assert not [p for p in sent if p.mode == "calendar.event_upcoming"]       # 2h before 14:00 is 12:00
        clock["now"] = at(12, 0)
        view.tick()
        clock["now"] = at(12, 1)
        view.tick()
        ups = [p for p in sent if p.mode == "calendar.event_upcoming"]
        mid = daybook.meet_id(view.day.events[0])
        assert len(ups) == 1 and ups[0].title == f"1:1 Ann [meet:{mid}]"
        assert f"[meet:{mid}]" in ups[0].value and ups[0].value.startswith("14:00–14:30 1:1 Ann")

    clock["now"] = at(11, 30)                                       # a restart, its window covering 12:00 again
    app = await _calendar_app(fake_repo, monkeypatch, clock)
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        view = app.desktop.get_window("days").query_one(CalendarView)
        sent = []
        monkeypatch.setattr(app.roads, "emit", lambda payload, meta=None: sent.append(payload) or [])
        clock["now"] = at(14, 1)
        view.tick()
        ups = [p for p in sent if p.mode == "calendar.event_upcoming"]
        assert [p.title.split(" [")[0] for p in ups] == ["Retro"]               # 1:1 Ann went already

        assert view.quick_action("calendar.prepare")                         # 📄 on the selected meeting
        assert [p.mode for p in sent][-1] == "calendar.event_upcoming" and sent[-1].title.startswith("Retro")


@pytest.mark.asyncio
async def test_a_tagged_cart_is_the_meetings_document_and_enter_opens_it(fake_repo: Path, monkeypatch):
    from orkcraft.realm import pipes
    from orkcraft.screens.typed.lake_view import LakeView
    clock = {"now": at(9, 0)}
    app = await _calendar_app(fake_repo, monkeypatch, clock, lake=True)
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        view = app.desktop.get_window("days").query_one(CalendarView)
        ann, retro = view.day.events
        mid = daybook.meet_id(ann)
        assert not any("📄" in ln for ln in view.hut_lines([24] * 8))
        before = list(view.query_one("#cal-today").options)

        lake = app.desktop.get_window("insight").query_one(LakeView)
        shown = []
        monkeypatch.setattr(lake, "show_value", lambda kind, value, title="": shown.append((kind, value, title)))
        today = view.query_one("#cal-today")
        today.highlighted = 1                                                   # the Retro: no document
        today.action_select()
        await pilot.pause()
        assert shown == [] and [str(o.prompt) for o in today.options] == [str(o.prompt) for o in before]

        # what a Barracks sends back once its orc is done (the Signpost had renamed the cart to its route)
        done = f"**1on1 [meet:{mid}]** — Grunt (claude)\n\n# 1:1 with Ann\n\n- her goals\n\n_branch:_ `pool/b/grunt`"
        app.deliver_payload("days", pipes.Payload(pipes.TEXT, done, "barracks", "pool.done", f"1on1 [meet:{mid}]"))
        await pilot.pause()
        docs = view.docs()
        assert list(docs) == [mid] and (fake_repo / docs[mid]["path"]).read_text().count("# 1:1 with Ann") == 1
        assert "[14:00] 📄 1:1 Ann" in view.hut_lines([24] * 8) and "[16:00] Retro" in view.hut_lines([24] * 8)
        assert "📄" in str(today.options[0].prompt) and "📄" not in str(today.options[1].prompt)
        assert view.mini_status()[0] == "14:00 📄 1:1 Ann"

        today.highlighted = 0
        today.action_select()
        await pilot.pause()
        assert shown == [("file", docs[mid]["path"], "📄 1:1 Ann")]

        # a result that names a file in the repository: that file is the document
        app.deliver_payload("days", pipes.Payload(pipes.TEXT, f"wrote `docs/notes.md` [meet:{mid}]", "barracks",
                                                  "pool.done", "1on1"))
        assert view.docs()[mid]["path"] == "docs/notes.md"


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
