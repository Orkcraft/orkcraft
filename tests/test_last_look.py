"""👀 "Since your last look" (docs/design/audience.md §2a): the look's beats, the digest's words in its order (wins
first), the honest line when nothing changed, the cost while away, the service on a real host, and the page's view."""
from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path
from types import SimpleNamespace

import pytest

from orkcraft.core import last_look as service
from orkcraft.realm import event_log, last_look

NOW = dt.datetime(2026, 10, 14, 18, 20).astimezone()
STATIC = Path(__file__).resolve().parent.parent / "orkcraft" / "gui" / "static"


def _row(event, at=NOW - dt.timedelta(minutes=30), **fields):
    return event_log.line(event, at=at, **fields)


# -- the look ----------------------------------------------------------------------------------------------------

def test_beats_close_together_are_one_look_and_a_gap_begins_another():
    first, ended = last_look.beat(None, NOW)
    assert ended is None and first.start == first.end
    same, ended = last_look.beat(first, NOW + dt.timedelta(seconds=last_look.BEAT_S))
    assert ended is None and same.start == first.start and same.end > first.end
    later = NOW + dt.timedelta(minutes=40)
    new, ended = last_look.beat(same, later)
    assert ended is same and new.start == last_look.iso(later)
    assert last_look.seconds(ended) == last_look.BEAT_S
    assert last_look.away_s(ended, later) == pytest.approx(40 * 60 - last_look.BEAT_S)


def test_the_last_look_is_kept_on_this_machine_only(tmp_path):
    look = last_look.Look(last_look.iso(NOW), last_look.iso(NOW), {"claude · 5h session": 40}, ["q1"])
    assert last_look.save(tmp_path, look) and last_look.load(tmp_path) == look
    assert last_look.path(tmp_path).is_relative_to(tmp_path / ".orkcraft")
    assert not last_look.save(None, look) and last_look.load(None) is None
    last_look.path(tmp_path).write_text("not json", encoding="utf-8")
    assert last_look.load(tmp_path) is None


# -- the digest --------------------------------------------------------------------------------------------------

def test_wins_come_first_then_the_questions_then_the_problems():
    since = NOW.replace(hour=12, minute=40)
    rows = [_row(event_log.BUILT, building="pool", kind="done", title="Fix the login"),
            _row(event_log.BUILT, building="gate", kind="passed", title="Release notes"),
            _row(event_log.BUILT, building="pub", kind="launched", title="PR #42"),
            _row(event_log.CART_MOVED, source="a", target="b", title="x"),
            _row(event_log.CART_MOVED, source="b", target="c", title="x")]
    q = [{"id": "q1", "who": "Grunt", "title": "Which port?", "options": [["1", "8080"]], "building": "pool"}]
    p = [{"id": "pool:t9", "building": "pool", "title": "Docs", "line": "Agent pool: waits 2 h", "waits": "no free slot (2/2)"}]
    d = last_look.digest(since, NOW, rows, q, p, ["#42"])
    assert d["headline"] == ("Since 12:40: 1 launched, 1 through the Review gate, 1 task done, 2 carts moved, "
                             "1 question, 1 problem.")
    assert [b["kind"] for b in d["built"]["items"]] == ["launched", "passed", "done"]
    assert d["built"]["items"][0]["line"] == "Launched: «PR #42»"
    assert d["built"]["summary"] == ("1 launched by the Publisher · 1 through the Review gate · 1 task done · "
                                     "2 carts moved")
    assert d["questions"]["items"][0]["new"] and d["problems"]["items"][0]["waits"] == "no free slot (2/2)"
    assert d["away"] == "5 h 40 min" and d["at"] == "12:40" and not d["empty"]


def test_never_an_endless_list():
    rows = [_row(event_log.BUILT, building="pool", kind="done", title=f"Task {i}") for i in range(7)]
    qs = [{"id": f"q{i}", "title": "?", "options": []} for i in range(5)]
    d = last_look.digest(NOW - dt.timedelta(hours=1), NOW, rows, qs, [], [])
    assert len(d["built"]["items"]) == last_look.SHOWN and d["built"]["more"] == 4
    assert len(d["questions"]["items"]) == last_look.SHOWN and d["questions"]["more"] == 2


def test_honest_when_nothing_changed():
    since = NOW.replace(hour=12, minute=40)
    d = last_look.digest(since, NOW, [], [], [], ["#42"])
    assert d["empty"] and d["headline"] == "Nothing new since 12:40; the orks are on «#42»."
    d = last_look.digest(since, NOW, [], [], [], [])
    assert d["headline"] == "Nothing new since 12:40; the orks rest."
    # A question that stood at the last look is not news, and still said: one tap answers it.
    q = [{"id": "q1", "title": "Which port?", "options": []}]
    d = last_look.digest(since, NOW, [], q, [], ["#42", "Docs"], seen={"q1"})
    assert d["empty"] and not d["questions"]["items"][0]["new"]
    assert d["headline"] == "Nothing new since 12:40; the orks are on «#42» and 1 more; 1 question still waits."


def test_the_cost_is_the_windows_share_used_while_away():
    then = {"claude · 5h session": 30, "claude · weekly": 50, "codex · 5h": 80}
    now = {"claude · 5h session": 42, "claude · weekly": 50, "codex · 5h": 10, "agy · daily": 5}
    d = last_look.digest(NOW - dt.timedelta(hours=1), NOW, [], [], [], [], then, now)
    assert [c["line"] for c in d["cost"]] == ["claude · 5h session: 12 % used while you were away (now 42 %)",
                                              "codex · 5h: the window started again; 10 % used since"]
    assert d["cost_known"]
    assert not last_look.digest(NOW - dt.timedelta(hours=1), NOW, [], [], [], [], {}, now)["cost_known"]


def test_since_when_reads_as_a_person_says_it():
    assert last_look.at_label(NOW - dt.timedelta(days=1), NOW) == "yesterday 18:20"
    assert last_look.at_label(NOW - dt.timedelta(days=3), NOW) == "Oct 11, 18:20"
    assert last_look.away_label(40 * 60) == "40 min" and last_look.away_label(2 * 3600) == "2 h" and last_look.away_label(3 * 86400) == "3 days"


# -- what the town records ----------------------------------------------------------------------------------------

def test_results_and_carts_go_to_the_local_log_and_never_in_the_demo(tmp_path):
    town = SimpleNamespace(demo=False, repo_root=tmp_path)
    service.built(town, "pub", "catapult.sent", "201 https://example.test/posts", "r1")
    service.built(town, "gate", "loot.passed", "✅ Release notes")
    service.built(town, "pool", "pool.failed", "not a result")
    cart = SimpleNamespace(status="delivered", source="a", target="b", payload=SimpleNamespace(title="Mail"))
    service.moved(town, cart)
    service.moved(town, SimpleNamespace(status="filtered", source="a", target="b", payload=cart.payload))
    rows = event_log.read(tmp_path)
    assert [(r["event"], r.get("kind")) for r in rows] == [("result_built", "launched"), ("result_built", "passed"),
                                                           ("cart_moved", None)]
    assert rows[0]["title"] == "https://example.test/posts" and rows[1]["title"] == "Release notes"
    demo = SimpleNamespace(demo=True, repo_root=tmp_path / "demo")
    service.built(demo, "pub", "catapult.sent", "x")
    assert not event_log.path(tmp_path / "demo").exists()


# -- the service on a host ---------------------------------------------------------------------------------------

def test_coming_back_after_a_while_greets_the_person_until_they_go_back(fake_repo, isolated_layout_file):
    from orkcraft.gui.host import Host
    before = dt.datetime.now().astimezone() - dt.timedelta(hours=2)
    last_look.save(fake_repo, last_look.Look(last_look.iso(before - dt.timedelta(minutes=5)), last_look.iso(before)))
    event_log.record(fake_repo, event_log.BUILT, building="pool", kind="done", title="Fix the login")
    host = Host(fake_repo, auto_commit=False)
    assert host.snapshot()["last_look"] is None
    assert host.command("look.beat") is True
    g = host.snapshot()["last_look"]
    assert g["built"]["items"][0]["line"] == "Done: «Fix the login»" and g["headline"].startswith("Since ")
    json.dumps(g)                                            # plain data the page draws
    assert host.command("look.beat") is False                # the same look goes on: no second greeting
    host.command("look.done")
    assert host.snapshot()["last_look"] is None
    looked = [r for r in event_log.read(fake_repo) if r["event"] == event_log.LOOKED]
    assert len(looked) == 1 and looked[0]["seconds"] == 300  # the look before, with how long it lasted
    host.close()


def test_a_short_step_away_is_not_greeted(fake_repo, isolated_layout_file):
    from orkcraft.gui.host import Host
    before = dt.datetime.now().astimezone() - dt.timedelta(minutes=5)
    last_look.save(fake_repo, last_look.Look(last_look.iso(before), last_look.iso(before)))
    host = Host(fake_repo, auto_commit=False)
    assert host.command("look.beat") is False and host.snapshot()["last_look"] is None
    host.close()


# -- the view ------------------------------------------------------------------------------------------------------

def test_the_page_counts_a_look_as_the_town_does():
    src = (STATIC / "js" / "lastlook.js").read_text(encoding="utf-8")
    assert re.search(r"const LOOK_MIN_S = (\d+);", src).group(1) == str(last_look.LOOK_MIN_S)
    assert re.search(r"const BEAT_S = (\d+);", src).group(1) == str(last_look.BEAT_S)
    assert "lastlook.css" in (STATIC / "index.html").read_text(encoding="utf-8")


def test_the_view_says_its_parts_in_order_wins_first():
    src = (STATIC / "js" / "lastlook.js").read_text(encoding="utf-8")
    view = src[src.index("export function LastLook"):]
    order = [view.index(f"<${{{part}}}") for part in ("Built", "Questions", "Problems", "Cost")]
    assert order == sorted(order)
    for words in ("Since your last look", "What was built", "Questions", "Problems", "What it cost",
                  "Back to the camp", "No window used while you were away."):
        assert words in src
    for hook in ("streak", "unread", "badge"):        # no feed hooks (audience.md §2a)
        assert hook not in src.lower()
