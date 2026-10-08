"""Do not disturb (docs/design/portrait.md §4): for the person, not the orks. While it holds the Horn
sounds nothing, the Warchief does not speak first, only error toasts show and pushes wait, but for the
budget spent; nothing stops working. Per machine, in `settings.dnd_until`.

    disturb.choose(machine, "1h", now)    # off | 1h | morning | on
    disturb.holds(machine, now)           # True while it holds
    disturb.choice(machine, now)          # which of the four the menu shows lit
    disturb.label(machine, now)           # "Until 09:00", "On", ""
    disturb.ended(machine, now)           # True once when a timed one ran out (and clears it)

"Until morning" ends where the machine's quiet hours end, else at 9:00.
"""
from __future__ import annotations

import datetime as dt

from orkcraft import schedule

CHOICES = ("off", "1h", "morning", "on")
MORNING = 9 * 60                 # 09:00 when the machine has no quiet hours


def _end(machine) -> dt.datetime | None:
    raw = getattr(machine, "dnd_until", "") or ""
    if raw in ("", "on"):
        return None
    try:
        return dt.datetime.fromisoformat(raw)
    except ValueError:
        return None


def morning(machine, now: dt.datetime) -> dt.datetime:
    """The next end of the quiet hours (else the next 9:00) after `now`."""
    minute = machine.quiet.end if getattr(machine, "quiet", None) is not None else MORNING
    at = now.replace(hour=minute // 60, minute=minute % 60, second=0, microsecond=0)
    return at if at > now else at + dt.timedelta(days=1)


def choose(machine, what: str, now: dt.datetime | None = None) -> None:
    """Set Do not disturb on `machine` (not saved): off, an hour, until morning or until turned off."""
    now = now or dt.datetime.now()
    if what == "on":
        machine.dnd_until = "on"
    elif what == "1h":
        machine.dnd_until = (now + dt.timedelta(hours=1)).replace(microsecond=0).isoformat(timespec="minutes")
    elif what == "morning":
        machine.dnd_until = morning(machine, now).isoformat(timespec="minutes")
    else:
        machine.dnd_until = ""


def holds(machine, now: dt.datetime | None = None) -> bool:
    raw = getattr(machine, "dnd_until", "") or ""
    if raw == "on":
        return True
    end = _end(machine)
    return end is not None and (now or dt.datetime.now()) < end


def ended(machine, now: dt.datetime | None = None) -> bool:
    """A timed Do not disturb that ran out: cleared on `machine` (the caller saves it); True once."""
    end = _end(machine)
    if end is None or (now or dt.datetime.now()) < end:
        if end is None and machine.dnd_until not in ("", "on"):
            machine.dnd_until = ""                # a time that does not read: off
        return False
    machine.dnd_until = ""
    return True


def choice(machine, now: dt.datetime | None = None) -> str:
    """Which of CHOICES it is now: an hour is an hour away at most, morning anything longer."""
    now = now or dt.datetime.now()
    if not holds(machine, now):
        return "off"
    if machine.dnd_until == "on":
        return "on"
    return "1h" if _end(machine) - now <= dt.timedelta(hours=1) else "morning"


def label(machine, now: dt.datetime | None = None) -> str:
    """What the menu says it holds for: "On", "Until 09:00", or "" when off."""
    now = now or dt.datetime.now()
    if not holds(machine, now):
        return ""
    if machine.dnd_until == "on":
        return "On"
    return f"Until {schedule.fmt(_end(machine).hour * 60 + _end(machine).minute)}"
