"""🕰 The day: 🌙 quiet hours."""
from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest

from orkcraft import schedule, settings
from orkcraft.app import OrkcraftApp
from orkcraft.schedule import Span
from orkcraft.screens.onboarding import DayStep
from orkcraft.widgets.day_bar import DAY_COLOR, QUIET_COLOR, DayBar

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


def test_the_bar_colours_the_quiet_hours():
    bar = DayBar(quiet=Span.parse("17:00", "08:00"))
    assert bar.color_at(12 * 2) == DAY_COLOR                        # 12:00
    assert bar.color_at(17 * 2) == QUIET_COLOR                      # 17:00
    assert bar.color_at(8 * 2) == DAY_COLOR                         # 08:00


@pytest.mark.asyncio
async def test_the_bar_edits_with_keys_and_mouse(fake_repo: Path):
    from textual.app import App

    class _A(App):
        def compose(self):
            yield DayBar(quiet=schedule.DEFAULT_QUIET, id="bar")

    app = _A()
    async with app.run_test(size=(80, 8)) as pilot:
        bar = app.query_one(DayBar)
        bar.focus()
        await pilot.pause()
        assert bar.selected == ("quiet", "start")
        await pilot.press("left")
        assert bar.quiet.label() == "22:30–08:00"
        await pilot.press("tab")                                     # → quiet end
        assert bar.selected == ("quiet", "end")
        await pilot.press("right", "right")
        assert bar.quiet.label() == "22:30–09:00"
        await pilot.press("shift+left")
        assert bar.quiet.label() == "22:00–08:30"
        await pilot.press("delete")                                  # quiet off
        assert bar.quiet is None and bar.edges() == []
        await pilot.mouse_down(DayBar, offset=(1 + 26, 1))           # padding 1 + 13:00
        await pilot.mouse_up(DayBar, offset=(1 + 31, 1))             # through 15:30
        assert bar.quiet.label() == "13:00–16:00"


@pytest.mark.asyncio
async def test_quiet_hours_come_by_the_clock(fake_repo: Path, monkeypatch):
    settings.save(_machine(onboarded=True, quiet=schedule.DEFAULT_QUIET))
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
        assert not desk.quiet and app._hud.resources.hour == ""
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
        assert not hut.has_class("-alert") and "❓" in " ".join(hut.label.text)       # no fire: a ❓ after the name
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
        assert isinstance(step, DayStep) and step.standalone
        assert step.bar.quiet is None
        step.query_one("#ob-quiet").value = True
        await pilot.pause()
        assert step.bar.quiet == schedule.DEFAULT_QUIET
        step.query_one("#ob-save").press()
        await pilot.pause()
        assert settings.load().quiet == schedule.DEFAULT_QUIET
