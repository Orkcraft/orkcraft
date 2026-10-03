"""🕰 The day: 🌙 quiet hours, 👔 office hours, and Shift turning Office on and off by itself."""
from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest

from orkcraft import schedule, settings
from orkcraft.app import OrkcraftApp
from orkcraft.schedule import Span
from orkcraft.screens.onboarding import ModeStep
from orkcraft.widgets.day_bar import DAY_COLOR, OFFICE_COLOR, QUIET_COLOR, DayBar

SIZE = (160, 50)
MON_10 = dt.datetime(2026, 10, 5, 10, 0)      # a Monday
SAT_10 = dt.datetime(2026, 10, 10, 10, 0)
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
    o = schedule.DEFAULT_OFFICE
    assert o.with_start(8 * 60).label() == "08:00–18:00"
    assert o.with_end(17 * 60 + 40).label() == "09:00–17:30"
    assert o.with_end(9 * 60) == o                                   # would be empty: kept
    assert o.shifted(-60).label() == "08:00–17:00"
    assert Span.parse("23:00", "01:00").shifted(60).label() == "00:00–02:00"


def test_shift_is_office_on_weekdays_in_office_hours():
    m = _machine(mode="shift")
    assert schedule.plain_now(m, MON_10) and not schedule.plain_now(m, SAT_10)
    assert not schedule.plain_now(m, MON_10.replace(hour=19))
    assert schedule.plain_now(_machine(mode="office"), SAT_10)
    assert not schedule.plain_now(_machine(mode="camp"), MON_10)


def test_a_night_shift_belongs_to_the_day_it_started():
    m = _machine(mode="shift", office=Span.parse("22:00", "02:00"), office_days=(0,))
    assert schedule.office_now(m, TUE_0030)                         # Monday's shift, past midnight
    assert not schedule.office_now(m, dt.datetime(2026, 10, 7, 0, 30))


def test_quiet_and_the_hud_word():
    m = _machine(mode="shift", quiet=schedule.DEFAULT_QUIET)
    assert schedule.quiet_now(m, TUE_0030) and not schedule.quiet_now(m, MON_10)
    assert schedule.status(m, TUE_0030) == "🌙 quiet till 08:00"
    assert schedule.status(m, MON_10) == "👔 office till 18:00"
    assert schedule.status(_machine(mode="camp"), MON_10) == ""


def test_the_bar_colours_quiet_over_office():
    bar = DayBar(quiet=Span.parse("17:00", "08:00"), office=schedule.DEFAULT_OFFICE)
    assert bar.color_at(12 * 2) == OFFICE_COLOR                     # 12:00
    assert bar.color_at(17 * 2) == QUIET_COLOR                      # 17:00: both, quiet wins
    assert bar.color_at(8 * 2) == DAY_COLOR                         # 08:00
    bar.set_show_office(False)
    assert bar.color_at(12 * 2) == DAY_COLOR


@pytest.mark.asyncio
async def test_the_bar_edits_with_keys_and_mouse(fake_repo: Path):
    from textual.app import App

    class _A(App):
        def compose(self):
            yield DayBar(quiet=schedule.DEFAULT_QUIET, office=schedule.DEFAULT_OFFICE, id="bar")

    app = _A()
    async with app.run_test(size=(80, 8)) as pilot:
        bar = app.query_one(DayBar)
        bar.focus()
        await pilot.pause()
        assert bar.selected == ("quiet", "start")
        await pilot.press("left")
        assert bar.quiet.label() == "22:30–08:00"
        await pilot.press("tab", "tab", "tab")                       # → office end
        assert bar.selected == ("office", "end")
        await pilot.press("right", "right")
        assert bar.office.label() == "09:00–19:00"
        await pilot.press("shift+left")
        assert bar.office.label() == "08:30–18:30"
        await pilot.press("shift+tab", "shift+tab", "delete")        # quiet off
        assert bar.quiet is None and bar.edges() == [("office", "start"), ("office", "end")]
        await pilot.mouse_down(DayBar, offset=(1 + 26, 1))           # padding 1 + 13:00
        await pilot.mouse_up(DayBar, offset=(1 + 31, 1))             # through 15:30
        assert bar.office.label() == "13:00–16:00"


@pytest.mark.asyncio
async def test_shift_switches_the_town_by_the_clock(fake_repo: Path, monkeypatch):
    settings.save(_machine(mode="shift", onboarded=True, quiet=schedule.DEFAULT_QUIET))
    clock = {"now": MON_10}
    real = schedule.dt.datetime

    class _Clock(real):
        @classmethod
        def now(cls, tz=None):
            return clock["now"]

    monkeypatch.setattr(schedule.dt, "datetime", _Clock)
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        desk = app.desktop
        assert desk.plain and not desk.quiet
        assert app._hud.resources.hour == "👔 office till 18:00"
        clock["now"] = MON_10.replace(hour=20)
        app.tick_schedule()
        await pilot.pause()
        assert not desk.plain and all(not h.plain for h in desk.huts.values())
        clock["now"] = TUE_0030
        app.tick_schedule()
        await pilot.pause()
        assert desk.quiet and all(h.quiet for h in desk.huts.values())
        assert app._hud.resources.hour == "🌙 quiet till 08:00"


@pytest.mark.asyncio
async def test_quiet_hours_put_out_the_fires(fake_repo: Path, monkeypatch):
    from orkcraft import scroll
    from orkcraft.realm.buildings import TOWN_HALL
    monkeypatch.setattr(scroll, "DEFAULT_VIEW", "town")
    settings.save(_machine(onboarded=True, quiet=Span.parse("00:00", "23:30")))
    monkeypatch.setattr(schedule, "quiet_now", lambda m, now=None: True)
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        app.desktop.apply_schedule()
        hut = app.desktop.huts[TOWN_HALL]
        hut.set_badge("🧌 Smith 🔥")
        assert not hut.has_class("-alert") and "❓" in hut._badge_shown() and "🔥" not in hut._badge_shown()
        app.desktop.flicker_fires()
        assert not hut.has_class("-flame")
        monkeypatch.setattr(schedule, "quiet_now", lambda m, now=None: False)
        app.desktop.apply_schedule()
        assert hut.has_class("-alert")


@pytest.mark.asyncio
async def test_your_day_from_f10(fake_repo: Path):
    settings.save(_machine(onboarded=True))
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        app.open_day()
        await pilot.pause()
        step = app.screen
        assert isinstance(step, ModeStep) and step.standalone
        assert not step.bar.show_office and step.bar.quiet is None
        step.pick("shift")
        step.query_one("#ob-quiet").value = True
        await pilot.pause()
        assert step.bar.show_office and step.bar.quiet == schedule.DEFAULT_QUIET
        step.query_one("#ob-save").press()
        await pilot.pause()
        m = settings.load()
        assert m.mode == "shift" and m.quiet == schedule.DEFAULT_QUIET and m.office == schedule.DEFAULT_OFFICE
