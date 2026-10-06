"""🥁 The War Drum's one timeline: meetings, the town's scheduled runs and ≈ when its limits are reached
(realm/drumbeat.py), in the worker, the GUI's card and detail, and in both looks' words."""
from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest

from orkcraft import scroll as ts
from orkcraft.core.town import Town
from orkcraft.core.workers.war_drum import WarDrumWorker
from orkcraft.gui.views import war_drum as view
from orkcraft.realm import drumbeat, lexicon, masonry, steward
from orkcraft.sources import ics

DAY = dt.date(2026, 10, 2)                      # a Friday
ICS = """BEGIN:VCALENDAR
BEGIN:VEVENT
UID:standup@x
DTSTART:20261002T090000
DTEND:20261002T093000
SUMMARY:Standup
END:VEVENT
BEGIN:VEVENT
UID:ann@x
DTSTART:20261002T140000
DTEND:20261002T143000
SUMMARY:1:1 Ann
END:VEVENT
BEGIN:VEVENT
UID:retro@x
DTSTART:20261002T160000
DTEND:20261002T170000
SUMMARY:Retro
END:VEVENT
END:VCALENDAR
"""


def at(h: int, m: int = 0, day: dt.date = DAY) -> dt.datetime:
    return dt.datetime.combine(day, dt.time(h, m))


# -- the pure parts -----------------------------------------------------------------------------------

def test_next_due_finds_the_next_scheduled_minute():
    assert steward.next_due("daily 05:00", at(9, 10)) == at(5, 0, DAY + dt.timedelta(days=1))
    assert steward.next_due("daily 05:00", at(4, 59)) == at(5, 0)
    assert steward.next_due("*/15 * * * *", at(9, 10)) == at(9, 15)
    assert steward.next_due("weekly mon 09:00", at(9, 10)) == at(9, 0, dt.date(2026, 10, 5))
    assert steward.next_due("0 12 * * *", at(9, 10), dt.timedelta(hours=1)) is None       # not within the hour
    assert steward.next_due("soon", at(9, 10)) is None
    runs, more = drumbeat.next_runs("every 2h", at(9, 10), at(18, 0), cap=3)
    assert runs == [at(10), at(12), at(14)] and more == 2                                   # 16:00, 18:00 left off


def test_a_limit_is_projected_from_the_burn_of_the_last_hour():
    pts = [(at(8, 0), 0.5), (at(9, 0), 1.0), (at(9, 30), 1.5), (at(10, 0), 2.0)]
    lim = drumbeat.project("gold", pts, 5.0, at(10, 0))
    assert lim.rate == pytest.approx(1.0) and lim.at == at(13, 0) and not lim.reached and lim.share == 0.4
    assert drumbeat.project("gold", [(at(9), 1.0), (at(10), 1.0)], 5.0, at(10)).at is None     # flat: not at this rate
    over = drumbeat.project("gold", [(at(9), 4.0), (at(9, 30), 5.2), (at(10), 5.3)], 5.0, at(10))
    assert over.reached and over.at == at(9, 30)
    assert drumbeat.project("gold", pts, 0.0, at(10)).at is None                                # no limit set


def test_samples_are_kept_when_they_move_and_read_back_per_run(tmp_path: Path):
    path = tmp_path / "burn.jsonl"
    assert drumbeat.sample(path, at(9, 0), "r1", 0.5, 20000, "camp/a")
    assert not drumbeat.sample(path, at(9, 1), "r1", 0.5, 20000, "camp/a")       # unchanged, too soon
    assert drumbeat.sample(path, at(9, 30), "r1", 1.0, 50000, "camp/a")
    assert drumbeat.sample(path, at(9, 31), "r2", 0.0, 0, "")                     # a new run starts afresh
    assert [r["spent"] for r in drumbeat.read_samples(path, "r2")] == [0.0]
    rows = [{"_at": at(9, 0), "spent": 0.5, "ctx": 20000, "who": "a"}, {"_at": at(10, 0), "spent": 1.5, "ctx": 60000, "who": "a"}]
    gold, lumber = drumbeat.limits(rows, 5.0, 131072, at(10, 0))
    assert gold.at == at(13, 30) and lumber.at.strftime("%H:%M") == "11:46" and lumber.who == "a"
    assert drumbeat.amount("gold", 2.6) == "$2.60" and drumbeat.amount("lumber", 131072) == "128k"


def test_the_timeline_holds_all_three_kinds_in_time_order():
    events = ics.parse_ics(ICS, "work", DAY, DAY + dt.timedelta(days=7))
    jobs = [drumbeat.Job("post", "Watchtower", "daily 05:00", "watch"), drumbeat.Job("counter", "Workshop", "every 3h", "script")]
    lim = drumbeat.Limit("gold", 2.0, 5.0, 1.0, at(13, 0))
    beats = drumbeat.timeline(events, jobs, [lim], at(9, 10), at(9, 10) + dt.timedelta(days=1))
    assert [(b.kind, b.at.strftime("%H:%M"), b.title) for b in beats[:5]] == [
        ("meeting", "09:00", "Standup"), ("schedule", "12:00", "Workshop"), ("limit", "13:00", "gold"),
        ("meeting", "14:00", "1:1 Ann"), ("schedule", "15:00", "Workshop")]
    standup, limit = beats[0], beats[2]
    assert standup.now and standup.tone == "text" and beats[1].tone == "accent"
    assert limit.approx and limit.tone == "wait" and limit.detail == "$2.00 / $5.00"
    assert any(b.title == "Watchtower" and b.at == at(5, 0, DAY + dt.timedelta(days=1)) for b in beats)
    picked = drumbeat.ahead([b for b in beats if b.kind != "limit"][:2] + [b for b in beats if b.kind == "meeting"][1:], 3)
    assert {b.kind for b in picked} == {"meeting", "schedule"}
    few = drumbeat.ahead(beats, 3)                                          # the Watchtower's run is tomorrow
    assert [b.kind for b in few] == ["meeting", "schedule", "limit"]
    reached = drumbeat.Limit("lumber", 140000, 131072, 0.0, at(8, 0), True)
    late = drumbeat.timeline([], [], [reached], at(9, 10), at(10))
    assert late[0].at == at(9, 10) and late[0].reached and late[0].tone == "error"


# -- the worker and its faces ---------------------------------------------------------------------------

@pytest.fixture
def clock(monkeypatch):
    now = {"now": at(9, 10)}
    monkeypatch.setattr(WarDrumWorker, "clock", staticmethod(lambda: now["now"]))
    return now


def _town(repo: Path) -> Town:
    (repo / "cal.ics").write_text(ICS)
    for spec in ({"id": "drum", "title": "Drum", "icon": "🥁", "orc": {"name": "Drummer"}, "type": "war_drum",
                  "config": {"ics": "cal.ics"}},
                 {"id": "post", "title": "Watchtower", "icon": "🗼", "orc": {"name": "Lookout"}, "type": "watchtower",
                  "config": {"cron": "every 2h"}}):
        assert masonry.save_spec(repo, spec) == []
    town = Town(repo)
    st = town.scroll.building("post").garrison.steward
    ts.update_orc(town.scroll, "post", st.id, trigger={"type": "cron", "expression": "daily 05:00"})
    return town


def test_the_drum_lays_the_towns_schedules_and_limits_over_the_day(fake_repo, clock):
    town = _town(fake_repo)
    town.scroll.budget.gold_session_limit_usd = 5.0
    w = town.worker("drum")
    assert [(j.ref, j.expr, j.what) for j in w.jobs()] == [("post", "every 2h", "watch"), ("stewards", "daily 05:00", "steward")]
    assert w.jobs()[1].title == "Watchtower steward"

    town.snapshot.spent_usd, town.snapshot.context_by_terminal = 1.0, {"camp/a": 40000}
    clock["now"] = at(8, 10)
    assert w.sample_burn()
    town.snapshot.spent_usd, town.snapshot.context_by_terminal = 2.0, {"camp/a": 70000}
    clock["now"] = at(9, 10)
    w.tick()                                                         # the tick samples too
    gold, lumber = w.limits()
    assert gold.at == at(12, 10) and lumber.at.strftime("%H:%M") == "11:12"

    lines = w.hut_lines([24] * 8)
    assert lines == ["[09:00] ▶ Standup", "[10:00] ↻ Watchtower", "[≈11:12] lumber limit", "[12:00] ↻ Watchtower",
                     "[≈12:10] gold limit", "[14:00] 1:1 Ann", "[14:00] ↻ Watchtower", "left today: 2 · ≈ estimate"]
    assert lexicon.office_words("[≈12:10] gold limit") == "[≈12:10] spend limit"            # the Office's words
    assert lexicon.office_words("[≈11:12] lumber limit") == "[≈11:12] context limit"
    assert lexicon.office_words("[06:00] ↻ Watchtower") == "[06:00] ↻ External listeners"
    assert any(ln.startswith("[≈") for ln in w.mini_status())

    card = view.card(w)
    kinds = [b["kind"] for b in card["beats"]]
    assert set(kinds) == {"meeting", "schedule", "limit"} and len(kinds) == view.CARD
    limit = next(b for b in card["beats"] if b["kind"] == "limit")
    assert limit["approx"] and limit["tone"] == "wait" and limit["title"] in ("gold", "lumber")
    assert card["strip"] and all(0 <= m["pos"] <= 1 for m in card["strip"]) and card["hours"] == view.STRIP_H

    data = view.detail(w)
    assert [x["what"] for x in data["limits"]] == ["gold", "lumber"]
    assert data["limits"][0] == {"what": "gold", "value": "$2.00", "limit": "$5.00", "share": 0.4, "rate": "$1.00/h",
                                 "at": "12:10", "day": "", "reached": False, "who": "", "known": True}
    today = data["days"][0]["beats"]
    assert [b["kind"] for b in today].count("schedule") == 7 and {b["kind"] for b in today} == {"schedule", "limit"}
    assert any(b["title"] == "Watchtower steward" for b in data["days"][1]["beats"])        # tomorrow 05:00
    assert data["jobs"][0]["next"]["at"] == "10:00"


def test_the_demo_drum_shows_its_seeded_burn(fake_repo, clock):
    from orkcraft.demo import seeds
    town = _town(fake_repo)
    town.demo = True
    town.scroll.budget.gold_session_limit_usd = 5.0
    seeds.war_drum_burn(fake_repo, at(9, 10), "drum")
    w = town.worker("drum")
    assert not w.sample_burn()                                       # agents never run in the demo
    gold, lumber = w.limits()
    assert gold.at and lumber.at and at(9, 10) < lumber.at < gold.at < at(14, 0)
    assert {b["kind"] for b in view.card(w)["beats"]} == {"meeting", "schedule", "limit"}
