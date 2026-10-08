"""Import calendar (realm/calendar_imports.py): a `.ics` read as RFC 5545 says (repeats, time zones, a moved or
cancelled occurrence), a file taken in, a subscription to an ICS link over a fake HTTP server — kept as a
secret, fetched again on its clock, an event taken out of it removed — and the War Drum's acts in the GUI."""
from __future__ import annotations

import datetime as dt
import http.server
import json
import threading
import time
from pathlib import Path

import pytest

from orkcraft import scroll as ts
from orkcraft.core.workers.war_drum import WarDrumWorker
from orkcraft.gui.host import CommandError, Host
from orkcraft.realm import calendar_imports, checkpoint, daybook, logins, masonry
from orkcraft.sources import ics

pytest.importorskip("recurring_ical_events")       # the `calendar` extra: the dev extra installs it

DAY = dt.date(2026, 10, 26)                         # a Monday: the US is still on summer time, Europe is not

REPEATS = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//test//EN
BEGIN:VTIMEZONE
TZID:America/New_York
BEGIN:DAYLIGHT
TZOFFSETFROM:-0500
TZOFFSETTO:-0400
TZNAME:EDT
DTSTART:19700308T020000
RRULE:FREQ=YEARLY;BYMONTH=3;BYDAY=2SU
END:DAYLIGHT
BEGIN:STANDARD
TZOFFSETFROM:-0400
TZOFFSETTO:-0500
TZNAME:EST
DTSTART:19701101T020000
RRULE:FREQ=YEARLY;BYMONTH=11;BYDAY=1SU
END:STANDARD
END:VTIMEZONE
BEGIN:VEVENT
UID:sync@ny
DTSTART;TZID=America/New_York:20261019T100000
DTEND;TZID=America/New_York:20261019T103000
RRULE:FREQ=WEEKLY;BYDAY=MO
SUMMARY:NY sync
END:VEVENT
BEGIN:VEVENT
UID:standup@x
DTSTART:20261026T080000Z
DURATION:PT15M
RRULE:FREQ=DAILY;COUNT=5
EXDATE:20261028T080000Z
SUMMARY:Standup
END:VEVENT
BEGIN:VEVENT
UID:standup@x
RECURRENCE-ID:20261027T080000Z
DTSTART:20261027T120000Z
DURATION:PT15M
SUMMARY:Standup (moved)
END:VEVENT
BEGIN:VEVENT
UID:standup@x
RECURRENCE-ID:20261029T080000Z
DTSTART:20261029T080000Z
STATUS:CANCELLED
SUMMARY:Standup
END:VEVENT
BEGIN:VEVENT
UID:offsite@x
DTSTART;VALUE=DATE:20261030
DTEND;VALUE=DATE:20261101
SUMMARY:Offsite
END:VEVENT
BEGIN:VEVENT
UID:win@x
DTSTART;TZID=W. Europe Standard Time:20261027T150000
DTEND;TZID=W. Europe Standard Time:20261027T160000
SUMMARY:Review
END:VEVENT
END:VCALENDAR
"""


@pytest.fixture
def berlin(monkeypatch):
    """The town's clock in Berlin: times are shown local."""
    monkeypatch.setenv("TZ", "Europe/Berlin")
    time.tzset()
    yield
    monkeypatch.undo()
    time.tzset()


def test_repeats_time_zones_moved_and_cancelled_occurrences(berlin):
    events = ics.parse_ics(REPEATS, "work", DAY, DAY + dt.timedelta(days=6))
    got = [(e.summary, e.start) for e in events]
    at = lambda d, h, m=0: dt.datetime(2026, 10, d, h, m)
    # NY 10:00 is 15:00 in Berlin on the 26th (EDT, CET); a week later NY is on EST too: 16:00.
    assert ("NY sync", at(26, 15)) in got and ics.parse_ics(REPEATS, "w", dt.date(2026, 11, 2), dt.date(2026, 11, 2))[0].start == \
        dt.datetime(2026, 11, 2, 16)
    standups = [(s, t) for s, t in got if s.startswith("Standup")]
    # 08:00Z is 09:00 CET; the 27th moved to 13:00, the 28th excluded, the 29th cancelled, the 30th as ever.
    assert standups == [("Standup", at(26, 9)), ("Standup (moved)", at(27, 13)), ("Standup", at(30, 9))]
    first = next(e for e in events if e.summary == "Standup")
    assert first.end == at(26, 9, 15) and first.uid == "standup@x"
    offsite = [e for e in events if e.summary == "Offsite"]
    assert len(offsite) == 1 and offsite[0].all_day and offsite[0].day == dt.date(2026, 10, 30)   # on its first day only
    assert ("Review", at(27, 15)) in got                       # a Windows time-zone name, as Outlook writes it
    # each occurrence is its own meeting, the same series the same UID
    a, b = [e for e in events if e.summary.startswith("Standup")][:2]
    assert a.uid == b.uid and daybook.meet_id(a) != daybook.meet_id(b)


def test_without_the_extra_the_plain_parser_still_reads_a_calendar(berlin, monkeypatch):
    monkeypatch.setattr(ics, "recurring_ical_events", None)
    events = ics.parse_ics(REPEATS, "work", DAY, DAY + dt.timedelta(days=6))
    # it reads the series, but repeats it in local time: across a change of summer time the hour may slip —
    # what the extra is for (the test above)
    assert [e.day for e in events if e.summary == "NY sync"] == [DAY]
    assert ics.parse_ics("not a calendar", "x", DAY, DAY) == []


# -- a fake calendar server ---------------------------------------------------------------------------

SECRET = "/calendar/ical/team%40example.com/private-5f1d0c2e9a/basic.ics"


def _one(uid: str, summary: str, day: dt.date, hour: int) -> str:
    return (f"BEGIN:VEVENT\r\nUID:{uid}\r\nDTSTART:{day:%Y%m%d}T{hour:02d}0000\r\n"
            f"DTEND:{day:%Y%m%d}T{hour:02d}3000\r\nSUMMARY:{summary}\r\nEND:VEVENT\r\n")


class Feed:
    """What the server hands out at the secret path; anything else is a 404."""

    def __init__(self) -> None:
        self.body = ""
        self.status = 200
        self.hits = 0


@pytest.fixture
def feed():
    state = Feed()

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):              # noqa: N802 - the stdlib's name
            state.hits += 1
            if self.path != SECRET or state.status != 200:
                self.send_response(404 if self.path != SECRET else state.status)
                self.end_headers()
                return
            data = state.body.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/calendar")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *args):
            pass

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    state.url = f"http://127.0.0.1:{server.server_port}{SECRET}"
    yield state
    server.shutdown()
    server.server_close()


TODAY = dt.date(2026, 10, 2)


def at(h: int, m: int = 0) -> dt.datetime:
    return dt.datetime.combine(TODAY, dt.time(h, m))


@pytest.fixture
def clock(monkeypatch):
    now = {"now": at(9, 0)}
    monkeypatch.setattr(WarDrumWorker, "clock", staticmethod(lambda: now["now"]))
    return now


def _host(repo: Path) -> Host:
    spec = {"id": "drum", "title": "Drum", "icon": "🥁", "orc": {"name": "Drummer"}, "type": "war_drum",
            "config": {"day_starts": "23:59"}}
    assert masonry.save_spec(repo, spec) == []
    checkpoint.ensure(repo)
    return Host(repo, auto_commit=False)


def _everything_written(repo: Path) -> str:
    """Every file of the project, the town scroll and its logs among them."""
    return "\n".join(p.read_text(encoding="utf-8", errors="replace") for p in repo.rglob("*")
                     if p.is_file() and ".git" not in p.parts)


def test_a_subscription_is_a_secret_fetched_again_and_an_event_taken_out_goes(fake_repo, clock, feed, monkeypatch):
    feed.body = "BEGIN:VCALENDAR\r\n" + _one("a@x", "Planning", TODAY, 14) + _one("b@x", "1:1 Ann", TODAY, 16) + "END:VCALENDAR\r\n"
    host = _host(fake_repo)
    w = host.town.worker("drum")
    sent: list = []
    monkeypatch.setattr(host.town.roads, "emit", lambda payload, meta=None: sent.append(payload) or [])
    for ev in ("calendar.event_added", "calendar.event_removed", "calendar.event_upcoming"):
        ts.subscribe(host.town.scroll, "town_hall", "drum", ev)
    act = lambda what, **args: host.command("act", {"id": "drum", "act": what, "args": args})

    got = act("subscribe", url=feed.url, name="Team", every=60)
    assert got == {"id": got["id"], "name": "Team", "kind": "link", "events": 2, "every": 60, "host": "127.0.0.1"}
    entry = w.imports[0]
    assert entry["secret"] == f"keychain:calendar.drum.{got['id']}" and "url" not in entry
    assert logins.resolve(entry["secret"]) == feed.url
    assert [e.summary for e in w.today()] == ["Planning", "1:1 Ann"] and w.today()[0].calendar == "Team"
    # the link is in no file of the project: not the scroll, not the building's state, not a log
    assert "private-5f1d0c2e9a" not in _everything_written(fake_repo)
    data = host.detail("drum")["data"]
    assert "private-5f1d0c2e9a" not in json.dumps(data) and data["imports"][0]["host"] == "127.0.0.1"

    # the calendar changes upstream: Ann is taken out; before its hour nothing is fetched, after it she goes
    feed.body = "BEGIN:VCALENDAR\r\n" + _one("a@x", "Planning", TODAY, 14) + "END:VCALENDAR\r\n"
    hits = feed.hits
    clock["now"] = at(9, 30)
    w.tick()
    assert feed.hits == hits and "1:1 Ann" in [e.summary for e in w.today()]
    clock["now"] = at(10, 1)
    w.tick()
    assert feed.hits == hits + 1 and [e.summary for e in w.today()] == ["Planning"]
    assert [p.title for p in sent if p.mode == "calendar.event_removed"] == ["1:1 Ann"]

    # an imported meeting is a meeting like any other: `meeting soon` two hours before it, tagged
    clock["now"] = at(12, 1)
    w.tick()
    soon = [p for p in sent if p.mode == "calendar.event_upcoming"]
    assert [p.title for p in soon] == ["Planning"] and f"[meet:{daybook.meet_id(w.today()[0])}]" in soon[0].value

    # the link stops working (reset in Google): the last copy stays, why is said — never the link
    feed.status = 404
    toasts: list = []
    monkeypatch.setattr(w, "toast", lambda message, **kw: toasts.append(message))
    clock["now"] = at(13, 5)
    w.tick()
    row = host.detail("drum")["data"]["imports"][0]
    assert [e.summary for e in w.today()] == ["Planning"] and "HTTP 404" in row["error"] and "copy the secret" in row["error"]
    assert len(toasts) == 1 and "private-5f1d0c2e9a" not in toasts[0]
    feed.status = 200
    assert act("import_refresh") == 0 and host.detail("drum")["data"]["imports"][0]["error"] == ""

    # taken out: its events, its copy and its secret go
    assert act("import_remove", id=got["id"]) and w.imports == [] and w.today() == []
    assert logins.resolve(entry["secret"]) == "" and not calendar_imports.copy_of(w.state_dir, got["id"]).exists()
    with pytest.raises(CommandError):
        act("import_remove", id=got["id"])


def test_a_bad_link_is_never_kept_and_its_error_never_holds_it(fake_repo, clock, feed):
    host = _host(fake_repo)
    act = lambda what, **args: host.command("act", {"id": "drum", "act": what, "args": args})
    for url, why in ((feed.url.replace("private", "nosuch"), "HTTP 404"), ("ftp://x/cal.ics", "https://"),
                     ("http://127.0.0.1:9/private-5f1d0c2e9a.ics", "cannot be reached")):
        with pytest.raises(CommandError) as err:
            act("subscribe", url=url)
        assert why in str(err.value) and "private" not in str(err.value) and "nosuch" not in str(err.value)
    feed.body = "<html>Sign in</html>"
    with pytest.raises(CommandError, match="not a calendar"):
        act("subscribe", url=feed.url)
    assert host.town.worker("drum").imports == [] and logins.listed("calendar") == []


def test_a_link_typed_into_the_settings_becomes_a_subscription(fake_repo, clock, feed):
    feed.body = "BEGIN:VCALENDAR\r\n" + _one("a@x", "Planning", TODAY, 14) + "END:VCALENDAR\r\n"
    host = _host(fake_repo)
    w = host.town.worker("drum")
    host.command("act", {"id": "drum", "act": "settings", "args": {"ics": feed.url}})
    assert w.configured == "" and w.imports[0]["kind"] == "link" and [e.summary for e in w.today()] == ["Planning"]
    assert "private-5f1d0c2e9a" not in _everything_written(fake_repo)
    # a town that kept a plain link before shows it by its host alone
    assert w.save_config({"ics": feed.url})
    assert host.detail("drum")["data"]["settings"]["ics"] == "127.0.0.1 (link hidden)"


def test_a_file_is_taken_in_and_read_with_the_calendar(fake_repo, clock):
    (fake_repo / "cal.ics").write_text("BEGIN:VCALENDAR\r\n" + _one("s@x", "Standup", TODAY, 9) + "END:VCALENDAR\r\n")
    host = _host(fake_repo)
    w = host.town.worker("drum")
    assert w.save_config({"ics": "cal.ics"})
    act = lambda what, **args: host.command("act", {"id": "drum", "act": what, "args": args})
    body = "BEGIN:VCALENDAR\r\n" + _one("o@x", "Offsite prep", TODAY, 15) + "END:VCALENDAR\r\n"
    got = act("import_file", name="offsite.ics", text=body)
    assert (got["name"], got["kind"], got["events"]) == ("offsite", "file", 1)
    assert [(e.summary, e.calendar) for e in w.today()] == [("Standup", "calendar"), ("Offsite prep", "offsite")]
    assert w.writable == fake_repo / "cal.ics"                 # new events still go to its own calendar
    for bad in ({"name": "x.ics", "text": ""}, {"name": "x.ics", "text": "hello"}):
        with pytest.raises(CommandError):
            act("import_file", **bad)
    assert len(w.imports) == 1 and calendar_imports.check(body) == 1


def test_how_often_a_link_is_fetched_is_held_to_its_bounds():
    assert calendar_imports.every(1) == 15 and calendar_imports.every(10**6) == 24 * 60
    assert calendar_imports.every("x") == calendar_imports.EVERY == 30
    assert calendar_imports.normal_link(" webcal://p.example/cal.ics ") == "https://p.example/cal.ics"
    assert calendar_imports.host("https://calendar.google.com/calendar/ical/x/private-y/basic.ics") == "calendar.google.com"
