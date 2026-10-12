"""Improve reads a day: hotspots found by code, the Mechanic and the Farseer read them, a finding needs its proof
(realm/hotspots.py, realm/day_review.py, gui/day_review.py; docs/design/improve-buildings.md §13)."""
from __future__ import annotations

import datetime as dt
import json
import time

import pytest

from orkcraft.design import agents
from orkcraft.realm import call_log, day_review, fastpath, hotspots

TODAY = dt.date.today().isoformat()
TITLES = {"pool": "Agent pool", "tower": "External listeners"}


@pytest.fixture(autouse=True)
def no_day_log():
    call_log.keep_days(None)
    yield
    call_log.keep_days(None)


def _call(root, building, prompt, tokens, code=0, who="Grub"):
    call_log.keep_days(root)
    call_log.record({"ORKCRAFT_ORC": f"{building}/{who}"}, "work", "agy", "flash", prompt, "the answer", "", code, 3.0,
                    None, tokens)
    call_log.keep_days(None)


def _day(root):
    context = "The wiki, sent whole every time. " * 60                    # an opening longer than REPEAT_HEAD
    for n in range(3):
        _call(root, "pool", context + f"card {n}", 9_000)
    _call(root, "pool", "a light one", 100)
    _call(root, "tower", "sort the mail", 40_000)
    _call(root, "tower", "it broke", 200, code=1, who="Lookout")


DECISIONS = {("pool", TODAY): [{"at": f"{TODAY}T10:00:00", "action": "follow-up", "orc": "Grub", "why": "tests red"},
                               {"at": f"{TODAY}T10:05:00", "action": "hire", "orc": "Zug", "why": "more work"}]}
DISLIKES = {("tower", TODAY): [{"note": "it kept the spam", "output": "spam: keep"}]}


def _decisions(b, d):
    return DECISIONS.get((b, d), [])


def _dislikes(b, d):
    return DISLIKES.get((b, d), [])


def test_code_finds_the_days_hotspots_with_the_calls_they_rest_on(tmp_path):
    _day(tmp_path)
    spots = hotspots.find(tmp_path, TODAY, TITLES, _decisions, _dislikes)
    assert [(h.id, h.kind, h.building) for h in spots] == [
        ("H1", "dislike", "tower"), ("H2", "failed", "tower"), ("H3", "rework", "pool"), ("H4", "repeated", "pool"),
        ("H5", "costly", "tower"), ("H6", "costly", "pool"), ("H7", "costly", "pool"), ("H8", "costly", "pool")]
    assert "it kept the spam" in spots[0].said and "spam: keep" in spots[0].excerpt
    assert spots[2].said == "Agent pool sent work back or again 1 time" and "tests red" in spots[2].excerpt
    assert spots[3].said.startswith("Agent pool sent the same opening of a prompt 3 times (27,000 tokens")
    assert spots[4].calls == ["tower/calls/001-Grub.json"] and "PROMPT:\nsort the mail" in spots[4].excerpt
    digest = hotspots.digest(spots)
    assert "### H5 · costly · External listeners (`tower`)" in digest and "40,000 tokens" in digest


def test_a_long_prompt_is_cut_in_the_middle_and_the_digest_stops_when_full(tmp_path, monkeypatch):
    _call(tmp_path, "pool", "A" * 5000 + "THE END", 9_000)
    [spot] = hotspots.find(tmp_path, TODAY, TITLES, _decisions, lambda b, d: [])[-1:]
    assert "characters …]" in spot.excerpt and "THE END" in spot.excerpt and len(spot.excerpt) < 3000
    monkeypatch.setattr(hotspots, "DIGEST_MAX", 10)
    assert hotspots.digest([spot, spot]).startswith("[2 more hotspots left out")


def _answer(findings):
    return json.dumps({"findings": findings})


def test_the_mechanic_and_the_farseer_read_the_day_and_a_finding_needs_its_proof(tmp_path):
    _day(tmp_path)
    asked = {}

    def ask(who, prompt):
        asked[who] = prompt
        if who == "mechanic":
            return _answer([
                {"hotspots": ["H4"], "building": "pool", "what": "the wiki goes whole into every card's call",
                 "why": "27k tokens", "change": {"kind": "prompt", "what": "send the wiki once, then the cards"}},
                {"hotspots": ["H99"], "building": "pool", "what": "a guess", "change": {"kind": "tier", "what": "x"}},
                {"hotspots": [], "building": "pool", "what": "no proof", "change": {"kind": "tier", "what": "x"}},
            ]), 0.01
        return _answer([{"hotspots": ["H1"], "building": "tower", "what": "spam was kept", "why": "the person "
                         "sorted it by hand", "change": {"kind": "magic", "what": "a rule: drop what the spam "
                                                                                  "folder would"}}]), 0.02

    review = day_review.run(tmp_path, TODAY, ask, TITLES, _decisions, _dislikes)
    assert agents.persona("mechanic") in asked["mechanic"] and agents.persona("farseer") in asked["farseer"]
    assert "### H4 · repeated" in asked["farseer"]
    assert [(f.who, f.building, f.kind, f.hotspots) for f in review.findings] == [
        ("mechanic", "pool", "prompt", ["H4"]), ("farseer", "tower", "rule", ["H1"])]       # an unknown kind: a rule
    assert review.cost == 0.03 and review.said == f"{TODAY}: 8 hotspots, 2 changes offered"
    kept = day_review.load(tmp_path, TODAY)
    assert kept is not None and kept.findings == review.findings
    text = day_review.warchief_text(review, TITLES)
    assert "@Agent pool — the Mechanic: the wiki goes whole" in text and "[H1]" in text and "apply or skip" in text


def test_a_councillor_that_fails_is_said_and_a_quiet_day_asks_no_model(tmp_path):
    _day(tmp_path)

    def ask(who, prompt):
        if who == "farseer":
            raise RuntimeError("agy is not logged in")
        return _answer([]), None

    review = day_review.run(tmp_path, TODAY, ask, TITLES, _decisions, _dislikes)
    assert review.findings == [] and review.errors == ["the Farseer: agy is not logged in"]
    quiet = day_review.run(tmp_path, "2026-01-02", lambda w, p: pytest.fail("no model on a quiet day"), TITLES,
                           _decisions, _dislikes)
    assert quiet.hotspots == [] and quiet.said == "2026-01-02: nothing in the logs worth a look"


def test_the_farseer_sits_on_the_council():
    assert "farseer" in fastpath.ROLE_IDS and "farseer" in agents.NAMES
    assert agents.brief("farseer").startswith("You are the Farseer, the Elders' product manager")


def test_improve_reads_a_day_and_hands_the_findings_to_the_warchief(fake_repo, isolated_layout_file, monkeypatch):
    from orkcraft.gui.host import Host
    from orkcraft.realm import checkpoint
    checkpoint.ensure(fake_repo)
    host = Host(fake_repo, auto_commit=False)
    asked = []
    try:
        _day(fake_repo)
        monkeypatch.setattr(host.day_review, "_ask", lambda who, prompt: (_answer([
            {"hotspots": ["H2"], "building": "tower", "what": f"{who}: it broke", "change": {"kind": "step",
                                                                                           "what": "retry once"}}]), 0))
        monkeypatch.setattr(host.town, "call", lambda fn, *a: fn(*a))
        hall = host.town.workers["town_hall"]
        monkeypatch.setattr(hall, "ask", lambda text, about: asked.append((text, about)))
        snap = host.snapshot()["improve"]
        assert snap["running"] == "" and snap["days"] == [{"day": TODAY, "read": "", "changes": 0}]
        assert snap["update"]["at"] and snap["update"]["key"] == ""
        said = host.command("warchief.improve", {"day": TODAY})["said"]
        assert said == f"The Mechanic and the Farseer are reading {TODAY}"
        for _ in range(500):
            if asked:
                break
            time.sleep(0.01)
        [(text, _about)] = asked
        assert "the Mechanic: mechanic: it broke" in text and "the Farseer: farseer: it broke" in text
        assert host.day_review.state()["days"][0]["read"].endswith("2 changes offered")
        again = host.command("warchief.improve", {"day": TODAY})["said"]           # read before: no new reading
        assert again.endswith("2 changes offered") and len(asked) == 2
        with pytest.raises(Exception, match="No logs kept"):
            host.command("warchief.improve", {"day": "2020-01-01"})
    finally:
        host.close()


def test_the_night_reads_the_day_that_ended_and_its_logs_wait_for_it(fake_repo, isolated_layout_file, monkeypatch):
    from orkcraft.gui.host import Host
    from orkcraft.realm import checkpoint
    checkpoint.ensure(fake_repo)
    host = Host(fake_repo, auto_commit=False)
    try:
        r = host.day_review
        started = []
        monkeypatch.setattr("threading.Thread.start", lambda self: started.append(self.name))
        yesterday = (dt.date.today() - dt.timedelta(days=1))
        folder = call_log.day_folder(fake_repo, yesterday.isoformat(), "pool")
        folder.mkdir(parents=True)
        (folder / call_log.LINES).write_text("{}\n")
        evening = dt.datetime.combine(yesterday, dt.time(23, 0))
        r.tick(True, when=evening)                                                    # the day has not ended
        assert started == []
        host.day_logs.cleared = ""
        host.day_logs.tick(dt.date.today())                                           # the morning's clearing
        assert folder.is_dir()                                                        # kept: the Elders read it first
        r.tick(False, when=evening + dt.timedelta(hours=3))                           # not quiet
        assert started == []
        r.tick(True, when=evening + dt.timedelta(hours=3))
        assert started == ["day-review"] and r.running == yesterday.isoformat()
        r.running = ""
        r.tick(True, when=evening + dt.timedelta(hours=4))                            # once a night
        assert started == ["day-review"]
    finally:
        host.close()


def test_a_span_reads_only_the_calls_inside_it(tmp_path):
    """Since the last update: the logs from the moment the code changed up to now, never the hours before."""
    _call(tmp_path, "tower", "before the update", 40_000)
    folder = call_log.day_folder(tmp_path, TODAY, "tower")
    lines = [json.loads(x) for x in (folder / call_log.LINES).read_text().splitlines()]
    lines[0]["at"] = f"{TODAY}T00:00:00"
    (folder / call_log.LINES).write_text("".join(json.dumps(x) + "\n" for x in lines))
    _call(tmp_path, "tower", "after the update", 30_000)
    since = dt.datetime.now().replace(second=0, microsecond=0)                   # the update: a moment ago
    key = day_review.span_key(since, dt.datetime.now())
    assert day_review.bounds(key)[0] == since.isoformat() and day_review.bounds(key)[2] == [TODAY]
    assert day_review.label(key).startswith(f"{TODAY} {since:%H:%M}–")
    spots = hotspots.find(tmp_path, key, TITLES, _decisions, _dislikes)
    assert [h.said for h in spots if h.kind == "costly"] == ["a costly call of External listeners: 30,000 tokens"]
    assert len(hotspots.find(tmp_path, TODAY, TITLES, _decisions, _dislikes)) == 3       # the whole day: both, a 👎
    review = day_review.run(tmp_path, key, lambda w, p: (_answer([]), 0), TITLES, _decisions, lambda b, d: [])
    assert review.said.startswith(f"{TODAY} {since:%H:%M}–") and day_review.load(tmp_path, key) is not None


def test_a_span_runs_past_midnight():
    key = day_review.span_key(dt.datetime(2026, 10, 11, 22, 30), dt.datetime(2026, 10, 12, 1, 5))
    assert day_review.bounds(key) == ("2026-10-11T22:30:00", "2026-10-12T01:05:59", ["2026-10-11", "2026-10-12"])
    assert day_review.label(key) == "2026-10-11 22:30–2026-10-12 01:05"
    with pytest.raises(ValueError):
        day_review.bounds(day_review.span_key(dt.datetime(2026, 10, 12), dt.datetime(2026, 10, 11)))


def test_the_code_running_now_is_kept_with_when_it_started(tmp_path, monkeypatch):
    from orkcraft.core import running
    path = tmp_path / "running.json"
    monkeypatch.setattr(running, "code", lambda: "0.2.9+abc")
    first = running.mark(dt.datetime(2026, 10, 12, 9, 0), path)
    assert running.mark(dt.datetime(2026, 10, 12, 15, 0), path) == first          # the same code: the first start
    monkeypatch.setattr(running, "code", lambda: "0.2.9+def")                     # a git pull
    assert running.mark(dt.datetime(2026, 10, 12, 15, 0), path)["since"] == "2026-10-12T15:00:00"
    assert running.since(path) == dt.datetime(2026, 10, 12, 15, 0)


def test_improve_reads_the_logs_since_the_last_update(fake_repo, isolated_layout_file, monkeypatch):
    from orkcraft.gui.host import Host
    from orkcraft.realm import checkpoint
    checkpoint.ensure(fake_repo)
    host = Host(fake_repo, auto_commit=False)
    try:
        with pytest.raises(Exception, match="No logs kept since the last update"):
            host.command("warchief.improve", {"since_update": True})
        _day(fake_repo)
        started = []
        monkeypatch.setattr(host.day_review, "start", lambda key, **kw: started.append(key) or "reading")
        assert host.command("warchief.improve", {"since_update": True})["said"] == "reading"
        [key] = started
        assert day_review.is_span(key) and day_review.bounds(key)[2][-1] == TODAY
    finally:
        host.close()
