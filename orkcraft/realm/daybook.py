"""The Calendar building's day: events from `.ics`, what is now, what is next.

`ics` in the building's settings is a path (in or outside the repository) or an http(s) URL; with
none, the calendars of `~/.config/orkcraft/calendars.json` are read. Events added from the
building go to the `ics` file when it is a local one, else to the building's own `local.ics` —
a URL calendar is never written. Parsing is `sources/ics.py`.

A meeting is named on the roads by a short id, `meet_id` (its UID and start, so each occurrence of
a recurring meeting has its own), carried as a `[meet:<id>]` tag that `meet_tag` finds again in
whatever comes back, and as the cart's `ref` (`<building>:<id>`) that a return road follows home.

A cart that names a time in a `When:` line (`When: tomorrow 11:00, 30 min` — what a Clan Fire that
routes writes when its steward says `WHEN:`) is an event to add: `find_when` reads it.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import re
import uuid
from dataclasses import dataclass
from pathlib import Path

from orkcraft.sources import ics

WEEK_DAYS = 7
DEFAULT_LEAD = dt.timedelta(hours=2)
_LEAD = re.compile(r"(\d+)\s*([dhm])")
_MEET = re.compile(r"\[meet:([0-9a-f]{6,32})\]")
_WHEN_LINE = re.compile(r"^[\s*#_>`-]*when\b[\s*_`]*:[\s*_`]*(.+?)[\s*_`.]*$", re.I | re.M)
_WHEN = re.compile(r"(tomorrow|today|\d{4}-\d{2}-\d{2})?[\s,]*(?:at\s+)?(\d{1,2}:\d{2})"
                   r"(?:[\s,·;-]+(\d{1,4})\s*(?:min|minutes|m)\b)?", re.I)


@dataclass
class Day:
    events: list[ics.CalendarEvent]
    errors: list[str]


def sources(repo_root: Path, configured: str, own: Path, google: str = "") -> list[ics.CalendarSource]:
    out = [ics.CalendarSource("Google Calendar", google=google)] if google else []
    if configured.startswith(("http://", "https://")):
        out.append(ics.CalendarSource("calendar", url=configured))
    elif configured:
        p = Path(configured).expanduser()
        out.append(ics.CalendarSource("calendar", path=str(p if p.is_absolute() else repo_root / p)))
    elif not google:
        out += ics.load_sources()
    if own.exists() and all(s.path != str(own) for s in out):
        out.append(ics.CalendarSource("local", path=str(own)))
    return out


def writable(repo_root: Path, configured: str, own: Path) -> Path:
    if configured and not configured.startswith(("http://", "https://")):
        p = Path(configured).expanduser()
        return p if p.is_absolute() else repo_root / p
    return own


def load(srcs: list[ics.CalendarSource], today: dt.date, days: int = WEEK_DAYS) -> Day:
    events, errors = ics.load_events(today, today + dt.timedelta(days=days - 1), srcs)
    return Day(events, errors)


def _end(e: ics.CalendarEvent) -> dt.datetime | None:
    if isinstance(e.end, dt.datetime):
        return e.end
    if isinstance(e.start, dt.datetime):
        return e.start + dt.timedelta(minutes=30)
    return None


def now_and_next(events: list[ics.CalendarEvent], now: dt.datetime) -> tuple[ics.CalendarEvent | None,
                                                                              ics.CalendarEvent | None, int]:
    """The event under way, the next one today, and how many are still ahead today."""
    timed = [e for e in events if isinstance(e.start, dt.datetime) and e.day == now.date()]
    current = next((e for e in timed if e.start <= now < (_end(e) or e.start)), None)
    ahead = [e for e in timed if e.start > now]
    return current, (ahead[0] if ahead else None), len(ahead)


def due(events: list[ics.CalendarEvent], since: dt.datetime, now: dt.datetime) -> list[ics.CalendarEvent]:
    """Timed events that started in (since, now]."""
    return [e for e in events if isinstance(e.start, dt.datetime) and since < e.start <= now]


def upcoming(events: list[ics.CalendarEvent], since: dt.datetime, now: dt.datetime,
             lead: dt.timedelta) -> list[ics.CalendarEvent]:
    """Timed events whose `start - lead` fell in (since, now]."""
    return [e for e in events if isinstance(e.start, dt.datetime) and since < e.start - lead <= now]


def parse_lead(value: str) -> dt.timedelta:
    """`2h`, `24h`, `30m`, `1d`, `1h30m` → a timedelta; empty or unreadable → 2 hours."""
    parts = _LEAD.findall((value or "").strip().lower())
    if not parts or _LEAD.sub("", value.strip().lower()).strip():
        return DEFAULT_LEAD
    unit = {"d": "days", "h": "hours", "m": "minutes"}
    return sum((dt.timedelta(**{unit[u]: int(n)}) for n, u in parts), dt.timedelta())


def meet_id(e: ics.CalendarEvent) -> str:
    """A short, stable id of one occurrence of a meeting."""
    start = e.start.isoformat()
    return hashlib.sha256(f"{e.uid or e.calendar + '|' + e.summary}|{start}".encode()).hexdigest()[:12]


def meet_tag(text: str) -> str:
    """The meeting id in a `[meet:<id>]` tag of `text`, or ""."""
    m = _MEET.search(text or "")
    return m.group(1) if m else ""


def key(e: ics.CalendarEvent) -> str:
    return f"{e.start.isoformat()}|{e.summary}"


def changes(before: list[ics.CalendarEvent] | None, after: list[ics.CalendarEvent]) -> list[tuple[str, ics.CalendarEvent]]:
    if before is None:
        return []
    old, new = {key(e): e for e in before}, {key(e): e for e in after}
    return [("calendar.event_added", new[k]) for k in new if k not in old] + \
        [("calendar.event_removed", old[k]) for k in old if k not in new]


def when(e: ics.CalendarEvent) -> str:
    if not isinstance(e.start, dt.datetime):
        return "all day"
    end = _end(e)
    return e.start.strftime("%H:%M") + (f"–{end.strftime('%H:%M')}" if end and end.date() == e.start.date() else "")


def line(e: ics.CalendarEvent) -> str:
    return f"{when(e)} {e.summary}" + (f" @ {e.location}" if e.location else "")


def digest(events: list[ics.CalendarEvent], day: dt.date) -> str:
    today = [e for e in events if e.day == day]
    if not today:
        return f"**{day:%A %d %B}** — nothing in the calendar."
    return f"**{day:%A %d %B}** — {len(today)} event{'s' if len(today) != 1 else ''}\n\n" + \
        "\n".join(f"- {line(e)}" for e in today)


def parse_day_starts(value: str) -> dt.time:
    try:
        h, m = (value or "08:00").split(":")
        return dt.time(int(h), int(m))
    except ValueError:
        return dt.time(8, 0)


def add_event(path: Path, summary: str, start: dt.datetime, minutes: int = 30, location: str = "") -> None:
    """Append one VEVENT (floating local time) to `path`, creating the calendar when needed."""
    summary = " ".join(summary.split())
    if not summary:
        raise ValueError("an event needs a title")
    esc = lambda s: s.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    end = start + dt.timedelta(minutes=max(1, minutes))
    lines = ["BEGIN:VEVENT", f"UID:{uuid.uuid4()}@orkcraft", f"DTSTAMP:{stamp}",
             f"DTSTART:{start:%Y%m%dT%H%M%S}", f"DTEND:{end:%Y%m%dT%H%M%S}", f"SUMMARY:{esc(summary)}"]
    if location:
        lines.append(f"LOCATION:{esc(location)}")
    lines.append("END:VEVENT")
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        text = ""
    if "END:VCALENDAR" in text:
        i = text.rindex("END:VCALENDAR")
        text = text[:i] + "\r\n".join(lines) + "\r\n" + text[i:]
    else:
        text = "\r\n".join(["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//orkcraft//calendar//EN", *lines,
                            "END:VCALENDAR"]) + "\r\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def parse_when(text: str, today: dt.date) -> dt.datetime:
    """`14:30`, `tomorrow 9:00`, `2026-10-05 14:00` → a datetime."""
    t = text.strip().lower()
    day = today
    if t.startswith("tomorrow"):
        day, t = today + dt.timedelta(days=1), t[len("tomorrow"):].strip()
    elif len(t) >= 10 and t[4] == "-" and t[7] == "-":
        day, t = dt.date.fromisoformat(t[:10]), t[10:].strip()
    h, _, m = (t or "09:00").partition(":")
    return dt.datetime.combine(day, dt.time(int(h), int(m or 0)))


def find_when(text: str, today: dt.date) -> tuple[dt.datetime, int] | None:
    """The time a cart names in a `When:` line — `tomorrow 11:00, 30 min`, `2026-10-08 14:00`,
    `today 9:30` — as (start, minutes; 30 when it says none), or None when it names none."""
    line = _WHEN_LINE.search(text or "")
    m = _WHEN.search(line.group(1)) if line else None
    if not m:
        return None
    day = (m.group(1) or "").lower()
    try:
        start = parse_when(f"{'' if day == 'today' else day} {m.group(2)}".strip(), today)
    except ValueError:
        return None
    minutes = int(m.group(3) or 30)
    return start, min(max(minutes, 5), 24 * 60)
