"""Subscribed calendars (Google Calendar "secret address in iCal format" or any ICS).

Config: `~/.config/orkcraft/calendars.json` (`$ORKCRAFT_CALENDARS_FILE`):

    [{"name": "Personal", "url": "https://calendar.google.com/calendar/ical/…/basic.ics"},
     {"name": "Local", "path": "~/cal/export.ics"}]

Feeds are cached in `~/.cache/orkcraft/ics/` and refetched after `CACHE_TTL_S`; a
failed fetch falls back to the cache.

Parsing: with the `calendar` extra (`icalendar` + `recurring-ical-events`) every RRULE, RDATE, EXDATE,
a moved or cancelled occurrence (RECURRENCE-ID), VTIMEZONE and Windows time-zone names are read as
RFC 5545 says. Without it, the standard library alone: VEVENT with UID/DTSTART/DTEND/SUMMARY/LOCATION,
TZID via zoneinfo, RRULE DAILY/WEEKLY/MONTHLY/YEARLY with INTERVAL/COUNT/UNTIL/BYDAY, EXDATE,
STATUS:CANCELLED. Either way an event without a UID gets a stable hash of calendar, summary and start,
times are local and naive, and an event shows on the day it starts.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re
import time
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

from orkcraft.env import getenv

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover
    ZoneInfo = None  # type: ignore[assignment]

try:                    # the `calendar` extra: `pip install 'orkcraft[calendar]'`
    import icalendar                                    # type: ignore[import-not-found]
    import recurring_ical_events                        # type: ignore[import-not-found]
except ImportError:     # pragma: no cover - depends on the machine
    icalendar = recurring_ical_events = None

CACHE_TTL_S = 15 * 60
FETCH_TIMEOUT_S = 10
MAX_OCCURRENCES = 2000
_WEEKDAYS = {"MO": 0, "TU": 1, "WE": 2, "TH": 3, "FR": 4, "SA": 5, "SU": 6}


@dataclass(frozen=True)
class CalendarEvent:
    calendar: str
    summary: str
    start: dt.datetime | dt.date
    end: dt.datetime | dt.date | None = None
    location: str = ""
    uid: str = ""
    # What a meeting's brief needs beyond its title: who comes, and what its invitation says. Not part of what
    # makes an event the same one (a changed agenda is not a moved meeting).
    description: str = field(default="", compare=False)
    attendees: tuple[str, ...] = field(default=(), compare=False)

    @property
    def all_day(self) -> bool:
        return not isinstance(self.start, dt.datetime)

    @property
    def day(self) -> dt.date:
        return self.start.date() if isinstance(self.start, dt.datetime) else self.start


@dataclass
class CalendarSource:
    name: str
    url: str | None = None
    path: str | None = None
    google: str | None = None      # a Google sign-in (`keychain:google-…`): its primary calendar, by the API


# -- config & fetching -----------------------------------------------------------

def calendars_file() -> Path:
    env = getenv("CALENDARS_FILE")
    if env:
        return Path(env).expanduser()
    base = os.environ.get("XDG_CONFIG_HOME", "").strip() or str(Path.home() / ".config")
    return Path(base) / "orkcraft" / "calendars.json"


def cache_dir() -> Path:
    base = os.environ.get("XDG_CACHE_HOME", "").strip() or str(Path.home() / ".cache")
    return Path(base) / "orkcraft" / "ics"


def load_sources(path: Path | None = None) -> list[CalendarSource]:
    path = path or calendars_file()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    if isinstance(data, dict):
        data = data.get("calendars", [])
    out = []
    for i, item in enumerate(data if isinstance(data, list) else []):
        if isinstance(item, dict) and (item.get("url") or item.get("path")):
            out.append(CalendarSource(str(item.get("name") or f"calendar {i + 1}"), item.get("url"), item.get("path")))
    return out


def read_source(src: CalendarSource, now: float | None = None) -> tuple[str, str | None]:
    """ICS text and an error note (text may come from the cache when fetching fails)."""
    if src.path:
        try:
            return Path(src.path).expanduser().read_text(encoding="utf-8", errors="replace"), None
        except OSError as e:
            return "", f"{src.name}: {e}"
    assert src.url
    now = now or time.time()
    cached = cache_dir() / (hashlib.sha256(src.url.encode()).hexdigest()[:24] + ".ics")
    if cached.exists() and now - cached.stat().st_mtime < CACHE_TTL_S:
        return cached.read_text(encoding="utf-8", errors="replace"), None
    try:
        req = urllib.request.Request(src.url, headers={"User-Agent": "orkcraft"})
        with urllib.request.urlopen(req, timeout=FETCH_TIMEOUT_S) as resp:
            text = resp.read().decode("utf-8", errors="replace")
        cached.parent.mkdir(parents=True, exist_ok=True)
        cached.write_text(text, encoding="utf-8")
        return text, None
    except Exception as e:  # network errors of every kind
        if cached.exists():
            return cached.read_text(encoding="utf-8", errors="replace"), f"{src.name}: offline, cached copy"
        return "", f"{src.name}: {e}"


def load_events(start: dt.date, end: dt.date, sources: list[CalendarSource] | None = None) -> tuple[list[CalendarEvent], list[str]]:
    sources = load_sources() if sources is None else sources
    events: list[CalendarEvent] = []
    errors: list[str] = []
    for src in sources:
        if src.google:
            got, err = read_google(src, start, end)
            events += got
            if err:
                errors.append(err)
            continue
        text, err = read_source(src)
        if err:
            errors.append(err)
        if text:
            events += parse_ics(text, src.name, start, end)
    events.sort(key=lambda e: (e.day, not e.all_day, e.start if isinstance(e.start, dt.datetime) else dt.datetime.min))
    return events, errors


# -- a Google calendar (realm/google.py, docs/design/google-account.md) ---------------------------------

GOOGLE_TTL_S = 5 * 60


def google_cache(ref: str) -> Path:
    return cache_dir() / ("google-" + hashlib.sha256(ref.encode()).hexdigest()[:24] + ".json")


def forget_google(ref: str) -> None:
    """An event was just added: the next load asks Google again."""
    try:
        google_cache(ref).unlink()
    except OSError:
        pass


def _google_time(value: dict) -> dt.datetime | dt.date | None:
    if value.get("dateTime"):
        when = dt.datetime.fromisoformat(str(value["dateTime"]).replace("Z", "+00:00"))
        return when.astimezone().replace(tzinfo=None) if when.tzinfo else when
    if value.get("date"):
        return dt.date.fromisoformat(str(value["date"]))
    return None


def google_events(items: list[dict], calendar: str) -> list[CalendarEvent]:
    out = []
    for it in items:
        if it.get("status") == "cancelled":
            continue
        try:
            start, end = _google_time(it.get("start") or {}), _google_time(it.get("end") or {})
        except (TypeError, ValueError):
            continue
        if start is None:
            continue
        out.append(CalendarEvent(calendar, str(it.get("summary") or "(no title)"), start, end,
                                 str(it.get("location") or ""), str(it.get("iCalUID") or it.get("id") or "")))
    return out


def read_google(src: CalendarSource, start: dt.date, end: dt.date,
                now: float | None = None) -> tuple[list[CalendarEvent], str | None]:
    """The events of a Google calendar, from a cache younger than `GOOGLE_TTL_S` or from Google; offline, the cache."""
    from orkcraft.realm import google
    assert src.google
    now = now or time.time()
    cached = google_cache(src.google)
    try:
        held = json.loads(cached.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        held = None
    fits = isinstance(held, dict) and held.get("window") == [start.isoformat(), end.isoformat()]
    if fits and now - float(held.get("at") or 0) < GOOGLE_TTL_S:
        return google_events(held.get("items") or [], src.name), None
    try:
        items = google.calendar_events(src.google, start, end)
    except google.GoogleError as e:
        if fits:
            return google_events(held.get("items") or [], src.name), f"{src.name}: {e} (the last copy shows)"
        return [], f"{src.name}: {e}"
    try:
        cached.parent.mkdir(parents=True, exist_ok=True)
        cached.write_text(json.dumps({"at": now, "window": [start.isoformat(), end.isoformat()], "items": items}),
                          encoding="utf-8")
    except OSError:
        pass
    return google_events(items, src.name), None


# -- parsing -----------------------------------------------------------------------

def _unfold(text: str) -> list[str]:
    lines: list[str] = []
    for raw in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if raw[:1] in (" ", "\t") and lines:
            lines[-1] += raw[1:]
        else:
            lines.append(raw)
    return lines


def _unescape(v: str) -> str:
    return v.replace("\\n", " ").replace("\\N", " ").replace("\\,", ",").replace("\\;", ";").replace("\\\\", "\\")


def _split(line: str) -> tuple[str, dict[str, str], str]:
    head, _, value = line.partition(":")
    name, *params = head.split(";")
    return name.upper(), {k.upper(): v for k, _, v in (p.partition("=") for p in params)}, value


def _parse_dt(value: str, params: dict[str, str]) -> dt.datetime | dt.date:
    value = value.strip()
    if params.get("VALUE") == "DATE" or len(value) == 8:
        return dt.date(int(value[:4]), int(value[4:6]), int(value[6:8]))
    base = dt.datetime.strptime(value[:15], "%Y%m%dT%H%M%S")
    if value.endswith("Z"):
        return base.replace(tzinfo=dt.timezone.utc).astimezone().replace(tzinfo=None)
    tzid = params.get("TZID")
    if tzid and ZoneInfo is not None:
        try:
            return base.replace(tzinfo=ZoneInfo(tzid)).astimezone().replace(tzinfo=None)
        except Exception:
            pass
    return base


def _day(v: dt.datetime | dt.date) -> dt.date:
    return v.date() if isinstance(v, dt.datetime) else v


def _add_months(d: dt.datetime | dt.date, months: int) -> dt.datetime | dt.date | None:
    y, m = divmod(d.month - 1 + months, 12)
    try:
        return d.replace(year=d.year + y, month=m + 1)
    except ValueError:
        return None  # e.g. the 31st in a shorter month: RFC 5545 skips it


def _expand(start, rule: dict[str, str], win_start: dt.date, win_end: dt.date, exdates: set) -> list:
    freq = rule.get("FREQ", "")
    interval = max(int(rule.get("INTERVAL", "1") or 1), 1)
    count = int(rule["COUNT"]) if rule.get("COUNT", "").isdigit() else None
    until = _day(_parse_dt(rule["UNTIL"], {})) if rule.get("UNTIL") else None
    byday = [_WEEKDAYS[d[-2:]] for d in rule.get("BYDAY", "").split(",") if d[-2:] in _WEEKDAYS]
    out: list = []
    produced = 0
    step = 0
    while produced < MAX_OCCURRENCES:
        if freq == "DAILY":
            cands = [start + dt.timedelta(days=step * interval)]
        elif freq == "WEEKLY":
            week0 = start - dt.timedelta(days=_day(start).weekday())
            week = week0 + dt.timedelta(weeks=step * interval)
            days = byday or [_day(start).weekday()]
            cands = sorted(week + dt.timedelta(days=d) for d in days)
            cands = [c for c in cands if _day(c) >= _day(start)]
        elif freq == "MONTHLY":
            cands = [c for c in [_add_months(start, step * interval)] if c]
        elif freq == "YEARLY":
            cands = [c for c in [_add_months(start, 12 * step * interval)] if c]
        else:
            return [start] if win_start <= _day(start) <= win_end else []
        for c in cands:
            d = _day(c)
            if (until and d > until) or (count is not None and produced >= count):
                return out
            produced += 1
            if d > win_end:
                return out
            if d >= win_start and c not in exdates:
                out.append(c)
        step += 1
    return out


def parse_ics(text: str, calendar: str, win_start: dt.date, win_end: dt.date) -> list[CalendarEvent]:
    """The events of `text` that start from `win_start` to `win_end`, each occurrence of a recurring one
    on its own; by the `calendar` extra when it is installed, else by the standard library."""
    if icalendar is not None and recurring_ical_events is not None:
        try:
            return _parse_rfc(text, calendar, win_start, win_end)
        except Exception:               # a calendar the library will not read: the plain parser tries
            pass
    return parse_plain(text, calendar, win_start, win_end)


def _local(v):
    """A time as the town keeps it: local and naive (a date stays a date, a floating time as written)."""
    if isinstance(v, dt.datetime) and v.tzinfo is not None:
        return v.astimezone().replace(tzinfo=None)
    return v


def _text(v) -> str:
    return " ".join(str(v).split()) if v is not None else ""


DESCRIPTION_CHARS = 2000


def _who(value: str, cn: str = "") -> str:
    """An attendee as a person reads it: the name it carries, else its address without `mailto:`."""
    name = cn.strip().strip('"')
    return name or re.sub(r"(?i)^mailto:", "", value.strip())


def _description(v) -> str:
    return "\n".join(ln.rstrip() for ln in str(v or "").strip().splitlines())[:DESCRIPTION_CHARS]


def _parse_rfc(text: str, calendar: str, win_start: dt.date, win_end: dt.date) -> list[CalendarEvent]:
    cal = icalendar.Calendar.from_ical(text)
    found = recurring_ical_events.of(cal, skip_bad_series=True).between(win_start, win_end + dt.timedelta(days=1))
    events: list[CalendarEvent] = []
    for comp in found:
        if comp.name != "VEVENT" or str(comp.get("STATUS", "")).upper() == "CANCELLED" or "DTSTART" not in comp:
            continue
        start = _local(comp.decoded("DTSTART"))
        if not win_start <= _day(start) <= win_end:
            continue                    # a multi-day event shows on its first day only
        end = _local(comp.decoded("DTEND")) if "DTEND" in comp else None
        if end is not None and (type(end) is not type(start) or end == start):
            end = None                  # none written (the library makes it the start): as the plain parser
        summary = _text(comp.get("SUMMARY")) or "(no title)"
        uid = _text(comp.get("UID"))
        if not uid:
            seed = f"{calendar}|{summary}|{start.isoformat()}"
            uid = hashlib.sha256(seed.encode()).hexdigest()[:16] + "@hash"
        found_who = comp.get("ATTENDEE") or []
        who = tuple(_who(str(a), str(getattr(a, "params", {}).get("CN", "")))
                    for a in (found_who if isinstance(found_who, list) else [found_who]))
        events.append(CalendarEvent(calendar, summary, start, end, _text(comp.get("LOCATION")), uid,
                                    _description(comp.get("DESCRIPTION")), tuple(w for w in who if w)))
    events.sort(key=lambda e: (e.day, not e.all_day, e.start if isinstance(e.start, dt.datetime) else dt.datetime.min))
    return events


def parse_plain(text: str, calendar: str, win_start: dt.date, win_end: dt.date) -> list[CalendarEvent]:
    """`parse_ics` by the standard library alone (the subset the module's doc names)."""
    events: list[CalendarEvent] = []
    cur: dict | None = None
    for line in _unfold(text):
        if line == "BEGIN:VEVENT":
            cur = {"exdates": set(), "ATTENDEE": []}
            continue
        if line == "END:VEVENT" and cur is not None:
            events += _materialise(cur, calendar, win_start, win_end)
            cur = None
            continue
        if cur is None or ":" not in line:
            continue
        name, params, value = _split(line)
        try:
            if name in ("DTSTART", "DTEND"):
                cur[name] = _parse_dt(value, params)
            elif name == "EXDATE":
                cur["exdates"].update(_parse_dt(v, params) for v in value.split(","))
            elif name == "RRULE":
                cur["RRULE"] = {k.upper(): v for k, _, v in (p.partition("=") for p in value.split(";"))}
            elif name == "UID":
                cur["UID"] = value.strip()
            elif name in ("SUMMARY", "LOCATION", "STATUS"):
                cur[name] = _unescape(value)
            elif name == "DESCRIPTION":
                cur[name] = value.replace("\\n", "\n").replace("\\N", "\n").replace("\\,", ",") \
                    .replace("\\;", ";").replace("\\\\", "\\")
            elif name == "ATTENDEE":
                cur["ATTENDEE"].append(_who(value, params.get("CN", "")))
        except ValueError:
            continue
    return events


def _materialise(ev: dict, calendar: str, win_start: dt.date, win_end: dt.date) -> list[CalendarEvent]:
    start = ev.get("DTSTART")
    if start is None or ev.get("STATUS", "").upper() == "CANCELLED":
        return []
    end = ev.get("DTEND")
    duration = (end - start) if end is not None and type(end) is type(start) else None
    if "RRULE" in ev:
        starts = _expand(start, ev["RRULE"], win_start, win_end, ev["exdates"])
    else:
        # A multi-day event shows on its first day only.
        starts = [start] if win_start <= _day(start) <= win_end else []
    summary = ev.get("SUMMARY", "(no title)")
    if not ev.get("UID"):
        seed = f"{calendar}|{summary}|{start.isoformat()}"
        ev["UID"] = hashlib.sha256(seed.encode()).hexdigest()[:16] + "@hash"
    return [
        CalendarEvent(calendar, summary, s, s + duration if duration else None, ev.get("LOCATION", ""), ev["UID"],
                      _description(ev.get("DESCRIPTION")), tuple(w for w in ev.get("ATTENDEE", []) if w))
        for s in starts
    ]
