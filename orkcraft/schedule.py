"""The day of the operator: 🌙 quiet hours (design: docs/design/onboarding.md).

    span = Span.parse("23:00", "08:00")      # start + length in minutes; may wrap past midnight
    span.contains(30)                        # 00:30 → True
    quiet_now(machine, now)                  # do-not-disturb: no fires, later no sound, no push
    quiet_started(machine, now)              # when tonight's quiet hours began (None: not quiet)

Times are local and snap to `STEP` minutes (the day bar has one cell per step).
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

DAY = 24 * 60
STEP = 30
DAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


def fmt(minute: int) -> str:
    minute %= DAY
    return f"{minute // 60:02d}:{minute % 60:02d}"


def parse_time(text: str) -> int | None:
    try:
        h, m = (int(x) for x in str(text).strip().split(":"))
    except ValueError:
        return None
    if (h, m) == (24, 0):
        return 0
    return h * 60 + m if 0 <= h < 24 and 0 <= m < 60 else None


def snap(minute: int) -> int:
    return round(minute / STEP) * STEP


@dataclass(frozen=True)
class Span:
    """A stretch of the day: `start` (minute, 0..1439) and `length` (STEP..DAY-STEP); it may wrap
    past midnight. `end` is where it stops, as a minute of the day."""
    start: int
    length: int

    @property
    def end(self) -> int:
        return (self.start + self.length) % DAY

    @classmethod
    def between(cls, start: int, end: int) -> Span | None:
        start, end = snap(start) % DAY, snap(end) % DAY
        length = (end - start) % DAY
        return cls(start, length) if STEP <= length <= DAY - STEP else None

    @classmethod
    def parse(cls, start: str, end: str) -> Span | None:
        a, b = parse_time(start), parse_time(end)
        return cls.between(a, b) if a is not None and b is not None else None

    def contains(self, minute: int) -> bool:
        return (minute - self.start) % DAY < self.length

    def with_start(self, minute: int) -> Span:
        """The start moved, the end kept (never shorter than a step, never the whole day)."""
        return Span.between(minute, self.end) or self

    def with_end(self, minute: int) -> Span:
        return Span.between(self.start, minute) or self

    def shifted(self, by: int) -> Span:
        return Span((self.start + snap(by)) % DAY, self.length)

    def label(self) -> str:
        return f"{fmt(self.start)}–{fmt(self.end)}"

    def to_dict(self) -> dict:
        return {"start": fmt(self.start), "end": fmt(self.end)}

    @classmethod
    def from_dict(cls, data: object) -> Span | None:
        if not isinstance(data, dict):
            return None
        return cls.parse(str(data.get("start", "")), str(data.get("end", "")))


DEFAULT_QUIET = Span(23 * 60, 9 * 60)            # 23:00–08:00


def _minute(now: dt.datetime) -> int:
    return now.hour * 60 + now.minute


def quiet_now(machine, now: dt.datetime | None = None) -> bool:
    now = now or dt.datetime.now()
    return machine.quiet is not None and machine.quiet.contains(_minute(now))


def quiet_started(machine, now: dt.datetime | None = None) -> dt.datetime | None:
    """When the quiet hours that hold now began (yesterday evening for a night past midnight); None
    when it is not quiet."""
    now = now or dt.datetime.now()
    if not quiet_now(machine, now):
        return None
    back = (_minute(now) - machine.quiet.start) % DAY
    return (now - dt.timedelta(minutes=back)).replace(second=0, microsecond=0)


def status(machine, now: dt.datetime | None = None) -> str:
    """The HUD's word on the hour: `🌙 quiet till 08:00`, or ""."""
    now = now or dt.datetime.now()
    return f"🌙 quiet till {fmt(machine.quiet.end)}" if quiet_now(machine, now) else ""
