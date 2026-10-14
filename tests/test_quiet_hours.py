"""Quiet working hours (docs/design/audience.md §2a, backlog W2): the person's working hours in Settings; while they
hold an ork's question raises no toast and no push, each held one is counted into the local event log, the orks are
told to assume and mark unless a wrong guess costs more than a day, and when the day ends one line says what waits.
Outside them, as before."""
from __future__ import annotations

import datetime as dt

import pytest

from orkcraft import schedule, settings
from orkcraft.core.workers.barracks import BarracksWorker
from orkcraft.gui.host import CommandError
from orkcraft.realm import asking, event_log
from orkcraft.schedule import Span
from tests.pool_fakes import Steward
from tests.test_gui_pool_clan import _host, _raised

NOON = dt.datetime(2026, 10, 14, 12, 0)


def _around_now() -> Span:
    """Working hours that hold now, whatever the hour the test runs at."""
    now = dt.datetime.now()
    minute = now.hour * 60 + now.minute
    return Span.between(minute - 60, minute + 180)


def _away_from_now() -> Span:
    now = dt.datetime.now()
    minute = now.hour * 60 + now.minute
    return Span.between(minute + 120, minute + 240)


def test_working_hours_hold_between_start_and_end_and_say_when_they_end():
    m = settings.MachineSettings()
    assert not schedule.at_work(m, NOON) and schedule.work_ends(m, NOON) is None        # not set: never at work
    m.work = schedule.DEFAULT_WORK
    assert m.work.label() == "10:00–19:00"
    assert schedule.at_work(m, NOON) and schedule.work_ends(m, NOON) == NOON.replace(hour=19)
    assert not schedule.at_work(m, NOON.replace(hour=9, minute=59)) and not schedule.at_work(m, NOON.replace(hour=19))
    m.work = Span.parse("22:00", "06:00")                                              # a night shift, past midnight
    late = NOON.replace(hour=23)
    assert schedule.at_work(m, late) and schedule.work_ends(m, late) == dt.datetime(2026, 10, 15, 6, 0)


def test_the_working_hours_are_kept_per_machine_and_the_shift_look_follows_them(tmp_path):
    file = tmp_path / "settings.json"
    settings.save(settings.MachineSettings(work=Span.parse("08:30", "17:30")), file)
    back = settings.load(file)
    assert back.work == Span.parse("08:30", "17:30") and settings.load(tmp_path / "none.json").work is None
    back.look = "shift"
    assert settings.look_now(back, NOON.replace(hour=8, minute=45)) == "office"     # 09:00–17:00 would say camp
    assert settings.look_now(back, NOON.replace(hour=17, minute=45)) == "camp"
    assert settings.shift(settings.MachineSettings()).label() == "09:00–17:00"         # not set: the old shift


def test_at_work_the_rule_says_assume_and_mark_unless_a_wrong_guess_costs_a_day():
    plain, working = asking.rule("Ugluk"), asking.rule("Ugluk", "19:00")
    assert "at work" not in plain
    assert "at work until 19:00" in working and "more than a day" in working and "```asks" in working
    assert working.endswith(plain.split("\n\n", 1)[1])                                  # the rest as before


def test_a_pool_ork_is_told_the_hours_only_while_they_hold(fake_repo, monkeypatch):
    monkeypatch.setattr(BarracksWorker, "steward_runner", Steward())
    host = _host(fake_repo)
    w = host.town.worker(_raised(host, "barracks", worktrees=False))
    assert "at work until" not in w.ask_rule("claude") and "at work until" not in w.ask_rule("codex")
    host.town.machine.work = _around_now()
    until = schedule.fmt(host.town.machine.work.end)
    assert f"at work until {until}" in w.ask_rule("claude") and f"at work until {until}" in w.ask_rule("codex")


def test_at_work_a_question_raises_no_toast_and_no_push_and_each_is_counted(fake_repo):
    host = _host(fake_repo)
    you = host.you
    question = {"title": "🔥 Ugluk asks", "severity": "information", "kind": "question"}
    assert not you.hold_toast(dict(question)) and not you.hold_push({"kind": "alert", "title": "Which port?"})
    host.town.machine.work = _around_now()
    assert you.hold_toast(dict(question)) and you.hold_push({"kind": "alert", "title": "Which port?"})
    assert not you.hold_toast({"title": "Saved", "severity": "information"})          # other toasts show as before
    assert not you.hold_toast({**question, "severity": "error"})                      # an error always shows
    assert not you.hold_push({"kind": "exited", "line": "Grunt finished"})
    held = [r for r in event_log.read(fake_repo) if r["event"] == event_log.HELD_AT_WORK]
    assert [r["how"] for r in held] == ["toast", "push"] and held[1]["title"] == "Which port?"
    assert host.snapshot()["portrait"]["work"] == {"set": True, "on": True, "held": 2,
                                                   **host.town.machine.work.to_dict()}


def test_when_the_working_day_ends_one_line_says_what_was_held(fake_repo):
    host = _host(fake_repo)
    news = []
    host.you.on_news = news.append
    host.town.machine.work = _around_now()
    host.you.tick()
    host.you.hold_push({"kind": "alert", "title": "Which port?"})
    host.town.machine.work = _away_from_now()                                          # the day is over
    host.you.tick()
    assert host.you.summary["text"].startswith("Your working day is over:") and news[-1]["kind"] == "dnd"
    assert host.snapshot()["portrait"]["work"]["held"] == 0


def test_a_quiet_day_with_nothing_held_says_nothing(fake_repo):
    host = _host(fake_repo)
    host.town.machine.work = _around_now()
    host.you.tick()
    host.town.machine.work = _away_from_now()
    host.you.tick()
    assert host.you.summary is None


def test_the_working_hours_are_set_and_turned_off_from_the_page(fake_repo):
    host = _host(fake_repo)
    snap = host.command("you.work", {"start": "09:30", "end": "18:00"})
    assert snap["work"]["set"] and (snap["work"]["start"], snap["work"]["end"]) == ("09:30", "18:00")
    assert settings.load().work == Span.parse("09:30", "18:00")
    with pytest.raises(CommandError):
        host.command("you.work", {"start": "09:30", "end": "09:30"})
    snap = host.command("you.work", {"on": False})
    assert not snap["work"]["set"] and (snap["work"]["start"], snap["work"]["end"]) == ("10:00", "19:00")
    assert settings.load().work is None
