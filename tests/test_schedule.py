"""🕰 The day: 🌙 quiet hours."""
from __future__ import annotations

import datetime as dt


from orkcraft import schedule, settings
from orkcraft.schedule import Span

SIZE = (160, 50)
MON_10 = dt.datetime(2026, 10, 5, 10, 0)      # a Monday
TUE_0030 = dt.datetime(2026, 10, 6, 0, 30)


def _machine(**kw) -> settings.MachineSettings:
    return settings.MachineSettings(**kw)


def test_spans_wrap_past_midnight():
    q = Span.parse("23:00", "08:00")
    assert q.label() == "23:00–08:00" and q.length == 9 * 60
    assert q.contains(23 * 60) and q.contains(30) and not q.contains(8 * 60) and not q.contains(12 * 60)
    assert Span.parse("09:00", "09:00") is None and Span.parse("25:00", "08:00") is None
    assert Span.from_dict(q.to_dict()) == q


def test_edges_move_by_half_hours_and_never_collapse():
    o = Span.parse("09:00", "18:00")
    assert o.with_start(8 * 60).label() == "08:00–18:00"
    assert o.with_end(17 * 60 + 40).label() == "09:00–17:30"
    assert o.with_end(9 * 60) == o                                   # would be empty: kept
    assert o.shifted(-60).label() == "08:00–17:00"
    assert Span.parse("23:00", "01:00").shifted(60).label() == "00:00–02:00"


def test_quiet_and_the_hud_word():
    m = _machine(quiet=schedule.DEFAULT_QUIET)
    assert schedule.quiet_now(m, TUE_0030) and not schedule.quiet_now(m, MON_10)
    assert schedule.status(m, TUE_0030) == "🌙 quiet till 08:00"
    assert schedule.status(m, MON_10) == ""
    assert schedule.status(_machine(), TUE_0030) == ""
