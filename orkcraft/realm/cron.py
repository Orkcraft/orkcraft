"""Schedules: a 5-field cron, or `daily HH:MM`, `weekly <day> HH:MM`, `hourly` — when one is due and
when it next is. Split out of `realm/steward.py`, which re-exports it.
"""
from __future__ import annotations

import datetime as dt
import re

_DAYS = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}


def _field_matches(spec: str, value: int, lo: int, hi: int) -> bool:
    for part in spec.split(","):
        step = 1
        if "/" in part:
            part, s = part.split("/", 1)
            step = int(s)
        if part == "*":
            a, b = lo, hi
        elif "-" in part:
            a, b = (int(x) for x in part.split("-", 1))
        else:
            a = b = int(part)
        if a <= value <= b and (value - a) % step == 0:
            return True
    return False


def _cron_match(fields: list[str], t: dt.datetime) -> bool:
    minute, hour, dom, month, dow = fields
    cron_dow = (t.weekday() + 1) % 7          # cron: 0 = Sunday
    return (_field_matches(minute, t.minute, 0, 59) and _field_matches(hour, t.hour, 0, 23)
            and _field_matches(dom, t.day, 1, 31) and _field_matches(month, t.month, 1, 12)
            and (_field_matches(dow, cron_dow, 0, 7) or (dow != "*" and cron_dow == 0 and _field_matches(dow, 7, 0, 7))))


def to_cron(expr: str) -> list[str] | None:
    """A 5-field cron, or `daily HH:MM`, `weekly <day> HH:MM`, `hourly` (the processes' form)."""
    e = expr.strip().lower()
    if m := re.fullmatch(r"daily (\d{1,2}):(\d{2})", e):
        return [str(int(m[2])), str(int(m[1])), "*", "*", "*"]
    if m := re.fullmatch(r"weekly (mon|tue|wed|thu|fri|sat|sun) (\d{1,2}):(\d{2})", e):
        return [str(int(m[3])), str(int(m[2])), "*", "*", str((_DAYS[m[1]] + 1) % 7)]
    if e == "hourly":
        return ["0", "*", "*", "*", "*"]
    fields = e.split()
    if len(fields) == 5 and all(re.fullmatch(r"[\d*/,\-]+", f) for f in fields):
        return fields
    return None


def due(expr: str, last: dt.datetime | None, now: dt.datetime) -> bool:
    """Did a scheduled time pass after `last` (or in the last minute, never run before)?"""
    fields = to_cron(expr)
    if fields is None:
        return False
    try:
        t = (last or now - dt.timedelta(minutes=1)).replace(second=0, microsecond=0) + dt.timedelta(minutes=1)
        end = now.replace(second=0, microsecond=0)
        t = max(t, end - dt.timedelta(days=8))
        while t <= end:
            if _cron_match(fields, t):
                return True
            t += dt.timedelta(minutes=1)
    except ValueError:
        return False
    return False


def next_due(expr: str, after: dt.datetime, within: dt.timedelta = dt.timedelta(days=8)) -> dt.datetime | None:
    """The first scheduled minute after `after`, at most `within` later; None when there is none in
    that time or `expr` is not a schedule. Skips whole days and hours that cannot match."""
    fields = to_cron(expr)
    if fields is None:
        return None
    minute, hour, dom, month, dow = fields
    t = after.replace(second=0, microsecond=0) + dt.timedelta(minutes=1)
    end = after + within
    try:
        while t <= end:
            if not _cron_match(["*", "*", dom, month, dow], t):
                t = (t + dt.timedelta(days=1)).replace(hour=0, minute=0)
            elif not _cron_match(["*", hour, dom, month, dow], t):
                t = (t + dt.timedelta(hours=1)).replace(minute=0)
            elif not _field_matches(minute, t.minute, 0, 59):
                t += dt.timedelta(minutes=1)
            else:
                return t
    except ValueError:
        return None
    return None
