"""The phone as the console (docs/design/mobile.md §11; audience.md §2a; cut-list.md §3a): since your last look on
the phone, an Agent pool ork's questions with their context, an idea dropped into the Task board's Ideas lane, the 🥩
list, the buildings where the person put them. What the host sends a phone and what it lets a phone do."""
from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path

from orkcraft.core import buildings
from orkcraft.gui import mobile
from orkcraft.gui.host import Host
from orkcraft.realm import barracks as bk
from orkcraft.realm import checkpoint, event_log, last_look

PWA = Path(__file__).resolve().parents[1] / "orkcraft" / "gui" / "static" / "pwa"


def _host(repo: Path) -> Host:
    checkpoint.ensure(repo)
    return Host(repo, auto_commit=False)


# -- since your last look, the phone's face -------------------------------------------------------------------------

def test_a_look_on_the_phone_greets_the_phone_not_the_desktop(fake_repo, isolated_layout_file):
    before = dt.datetime.now().astimezone() - dt.timedelta(hours=2)
    last_look.save(fake_repo, last_look.Look(last_look.iso(before - dt.timedelta(minutes=5)), last_look.iso(before)))
    event_log.record(fake_repo, event_log.BUILT, building="pool", kind="done", title="Fix the login")
    host = _host(fake_repo)
    assert mobile.phone_snapshot(host)["last_look"] is None
    assert host.command("mobile.beat") is True
    g = host.command("mobile.snapshot")["last_look"]
    assert g["headline"].startswith("Since ") and g["built"]["items"][0]["line"] == "Done: «Fix the login»"
    assert set(g["questions"]) == {"count", "new"}             # the questions themselves stand in Answers
    json.dumps(g)
    assert host.snapshot()["last_look"] is None                 # the desktop was not the face looked at
    assert host.command("look.beat") is False                   # one person, one look: the desktop goes on with it
    host.command("mobile.look_done")
    assert host.command("mobile.snapshot")["last_look"] is None
    host.close()


def test_the_phone_counts_a_look_as_the_town_does():
    src = (PWA / "look.js").read_text(encoding="utf-8")
    assert re.search(r"const LOOK_MIN_S = (\d+);", src).group(1) == str(last_look.LOOK_MIN_S)
    assert re.search(r"const BEAT_S = (\d+);", src).group(1) == str(last_look.BEAT_S)


def test_the_digest_comes_to_a_phone_small():
    d = last_look.digest(dt.datetime(2026, 10, 14, 12, 40).astimezone(), dt.datetime(2026, 10, 14, 18, 20).astimezone(),
                         [{"event": event_log.BUILT, "kind": "launched", "title": "v0.4", "building": "cat"}],
                         [{"id": "q", "title": "Proceed?"}], [{"id": "p", "title": "Mail", "line": "waits 40 min",
                                                               "waits": "you: open it", "building": "w"}], ["#42"])
    got = mobile._last_look(d)
    assert got["built"]["items"] == [{"line": "Launched: «v0.4»", "kind": "launched", "building": "cat"}]
    assert got["questions"] == {"count": 1, "new": 1} and got["problems"]["items"][0]["waits"] == "you: open it"
    assert mobile._last_look(None) is None


# -- the camp, the 🥩 list, an Agent pool's questions ------------------------------------------------------------------

def _full():
    pool_row = {"key": "pool/grunt", "name": "Grunt", "state": "asks", "mark": "❓", "word": "Asks", "line": "Grunt asks",
                "building_id": "pool", "since_s": 600, "spend": 0.4, "tool": "claude", "cart": "Dark mode",
                "assumptions": 2, "wait": {"line": "waits for your answer · Gorza decides it at 19:00"}, "stop": None,
                "answer": {"kind": "pool", "building": "pool", "task": "t1", "question": "",
                           "questions": [{"text": "System or switch?", "options": ["System", "Switch"]}]}}
    working = {"key": "pool/mason", "name": "Mason", "state": "thinking", "mark": "💭", "word": "Thinking", "line": "…",
               "building_id": "pool", "since_s": 30, "spend": 0.1, "tool": "claude", "answer": None,
               "stop": {"command": "act", "args": {"id": "pool", "act": "stop_ork", "args": {"ork": "Mason"}}}}
    roster = {"key": "w1", "name": "Peon", "state": "thinking", "line": "…", "building_id": "", "answer": None,
              "stop": {"command": "term.interrupt", "args": {"key": "w1"}}}
    return {"buildings": [{"id": "pool", "type": "barracks", "title": "🛖 Barracks", "hut": [0.123, 0.456]},
                          {"id": "f", "type": "fields", "title": "🌾 Task Fields",
                           "card": {"note_lane": "ideas", "notes": [{"id": "ideas", "label": "Ideas"}]}}],
            "slots": {"working": 2, "limit": 4, "asks": 1, "fire": 0, "rows": [pool_row, working, roster]}}


def test_the_phone_gets_the_buildings_spots_the_orks_at_work_and_the_pools_questions():
    snap = mobile.compact(_full())
    assert snap["buildings"][0]["spot"] == [0.12, 0.46] and snap["buildings"][1]["spot"] is None
    rows = snap["slots"]["rows"]
    assert [r["stop"] for r in rows] == [None, {"id": "pool", "ork": "Mason"}, None]   # never a terminal's interrupt
    assert rows[0]["asks"] and snap["slots"]["asks"] == 1
    q, = snap["pool_questions"]
    assert q["id"] == "pool:pool:t1" and q["cart"] == "Dark mode" and q["assumptions"] == 2
    assert q["wait"].endswith("decides it at 19:00") and q["questions"] == [{"text": "System or switch?",
                                                                            "options": ["System", "Switch"]}]
    assert snap["ideas"] == {"id": "f", "lane": "ideas", "label": "Ideas", "title": "🌾 Task Fields",
                             "title_plain": "Task board"}


def _asked(host, kind: str = "question", draft: str = "") -> tuple[str, str]:
    pool = buildings.raise_spec(host.town, buildings.type_spec(host.town, "barracks")).id
    host._attach(pool, host.town.worker(pool))
    w = host.town.worker(pool)
    task = bk.PoolTask(id="t1", title="Dark mode", text="", status="asked", orc="Grunt", ask_kind=kind, draft=draft,
                       question="System or switch?")
    w.state.tasks.append(task)
    return pool, task.id


def test_a_phone_answers_an_orks_own_question_never_a_drafts_yes(fake_repo, isolated_layout_file):
    host = _host(fake_repo)
    pool, task = _asked(host)
    answer = {"id": pool, "act": "answer", "args": {"task": task, "text": "System"}}
    assert mobile.allowed(host, "act", answer)
    assert mobile.allowed(host, "act", {"id": pool, "act": "stop_ork", "args": {"ork": "Grunt"}})
    assert not mobile.allowed(host, "act", {**answer, "args": {"task": "nope", "text": "x"}})
    assert not mobile.allowed(host, "act", {"id": pool, "act": "new_task", "args": {"title": "x"}})
    host.town.worker(pool).state.tasks[-1].draft = "A post for the blog"      # its yes posts outside the camp
    assert not mobile.allowed(host, "act", answer)
    host.town.worker(pool).state.tasks[-1].draft, host.town.worker(pool).state.tasks[-1].ask_kind = "", "conflict"
    assert not mobile.allowed(host, "act", answer)
    assert {"mobile.beat", "mobile.look_done"} <= set(host.commands)
    host.close()


def test_an_idea_sent_twice_after_a_lost_reply_lands_once(fake_repo, isolated_layout_file):
    host = _host(fake_repo)
    board = buildings.raise_spec(host.town, buildings.type_spec(host.town, "fields")).id
    host._attach(board, host.town.worker(board))
    lane = host.town.worker(board).note_lanes()[0]
    idea = {"id": board, "act": "add", "args": {"text": "A recap in one line", "lane": lane, "client_id": "abc123"}}
    assert mobile.allowed(host, "act", idea)
    first = host.command("act", idea)
    assert host.command("act", idea) == first
    w = host.town.worker(board)
    assert sum(1 for c in w.cards if c.column == lane) == 1
    host.command("act", {**idea, "args": {**idea["args"], "client_id": "other"}})
    assert sum(1 for c in w.cards if c.column == lane) == 2
    host.close()


def test_no_question_wakes_the_phone_in_the_working_hours(fake_repo, isolated_layout_file):
    host = _host(fake_repo)
    host.you.at_work = lambda: True
    assert host.you.hold_push({"kind": "alert", "title": "Proceed?"})
    host.close()
