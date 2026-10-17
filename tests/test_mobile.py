"""The mobile API, stage 0 (docs/design/mobile.md): the handshake, the compact snapshot, what a phone
may send and what a push would say."""
from __future__ import annotations

import asyncio
import json
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from orkcraft.core import buildings
from orkcraft.gui import mobile
from orkcraft.gui.host import Host
from orkcraft.gui.server import PROTOCOL, Server
from orkcraft.realm import checkpoint


def _host(repo: Path) -> Host:
    checkpoint.ensure(repo)
    return Host(repo, auto_commit=False)


def test_every_command_a_phone_may_send_is_one_the_host_has(fake_repo):
    host = _host(fake_repo)
    assert set(mobile.COMMANDS) <= set(host.commands)
    hello = host.command("mobile.hello")
    json.dumps(hello)
    assert hello["name"] == "orkcraft" and hello["api"] == mobile.API
    assert "orders.answer" in hello["commands"] and hello["acts"]["pit"] == ["drop", "drop_file"]


def test_a_phone_may_answer_drop_ask_and_halt_but_not_build_or_type(fake_repo, isolated_layout_file):
    host = _host(fake_repo)
    pit = buildings.raise_spec(host.town, buildings.type_spec(host.town, "pit")).id
    may = lambda name, args=None: mobile.allowed(host, name, args)      # noqa: E731
    assert may("orders.answer") and may("halt") and may("mobile.snapshot")
    assert may("act", {"id": pit, "act": "drop"}) and may("act", {"id": "town_hall", "act": "ask"})
    assert not may("act", {"id": pit, "act": "paste"})
    assert not may("act", {"id": "town_hall", "act": "audit"})
    assert not may("act", {"id": "nowhere", "act": "drop"})
    for name in ("town.build", "town.demolish", "term.input", "sessions.new", "hut.move", "roads.lay"):
        assert not may(name, {}), name


def test_the_compact_snapshot_is_small_and_names_its_content(fake_repo, isolated_layout_file):
    host = _host(fake_repo)
    board = buildings.raise_spec(host.town, buildings.type_spec(host.town, "fields")).id
    host.tick()
    full, snap = host.snapshot(), host.command("mobile.snapshot")
    json.dumps(snap)
    assert snap["v"] == mobile.API and snap["project"] == full["project"]
    assert len(json.dumps(snap)) < len(json.dumps(full))
    hall = next(b for b in snap["buildings"] if b["id"] == "town_hall")
    assert set(hall) == {"id", "title", "title_plain", "type", "state", "alert", "quick", "spot",
                         # the v3 camp's (pwa/camp.js): its steward, its growth, its status, its siding
                         "ork_name", "ork_key", "level", "goal", "status", "signal", "todo"} and hall["type"] == "town_hall"
    assert [q["id"] for q in hall["quick"]] == ["hall.audit"]           # Build opens a window of the desktop's: not here
    assert {"gold", "gold_level", "quota", "quota_level", "alerts"} <= set(snap["hud"])
    assert "words" not in snap and "projects" not in snap
    space = next(o for o in snap["orkspaces"] if o["id"] == snap["active_orkspace"])   # the phone picks one by its own
    assert set(space) == {"id", "name", "icon", "biome", "buildings", "questions", "working"} and board in space["buildings"]
    assert all(isinstance(r, list) and len(r) == 2 for r in snap["roads"])   # which feeds which, not what a road carries
    assert host.command("mobile.snapshot", {"since": snap["rev"]}) == {"v": mobile.API, "rev": snap["rev"],
                                                                       "same": True}
    host.command("hut.move", {"id": board, "x": 0.1, "y": 0.1})           # where a hut stands: the phone's camp too
    moved = host.command("mobile.snapshot", {"since": snap["rev"]})
    assert not moved.get("same") and next(b for b in moved["buildings"] if b["id"] == board)["spot"] == [0.1, 0.1]
    assert host.command("mobile.snapshot", {"since": "older"})["buildings"]


def test_a_question_comes_small_with_its_last_lines_and_the_elders_advice():
    full = {"project": "p", "hud": {"alerts": 1}, "buildings": [], "sessions": [{"running": True}, {"running": False}],
            "alerts": [{"id": "term:a", "title": "Proceed?", "context": [str(i) for i in range(12)],
                        "options": [["1", "Yes"], ["2", "No"]], "source": "terminal", "ref": "a", "who": "Grunt",
                        "building": "barracks", "advice": {"key": "1", "why": "safe", "warn": ""}, "waited": 4.0}]}
    snap = mobile.compact(full)
    (a,) = snap["alerts"]
    assert a["context"] == ["9", "10", "11"] and a["options"] == [["1", "Yes"], ["2", "No"]]
    assert a["advice"] == {"key": "1", "why": "safe"} and "ref" not in a
    assert snap["sessions_running"] == 1


def test_a_push_says_a_new_question_once_and_spend_when_it_crosses_a_level():
    def snap(alerts=(), gold="ok", quota="ok"):
        return {"alerts": [{"id": i, "title": f"Q {i}", "who": "Grunt"} for i in alerts],
                "hud": {"gold": "$4.10 / $5.00", "gold_level": gold, "quota": "62 %", "quota_level": quota}}
    assert mobile.news(None, snap(["a"])) == []                        # pairing wakes nobody
    assert mobile.news(snap(), snap(["a"])) == [{"kind": "alert", "id": "a", "title": "Q a", "who": "Grunt"}]
    assert mobile.news(snap(["a"]), snap(["a"])) == []
    assert mobile.news(snap(), snap(gold="warn")) == [{"kind": "gold", "level": "warn", "text": "$4.10 / $5.00"}]
    assert mobile.news(snap(gold="warn"), snap(gold="warn")) == []
    assert [n["kind"] for n in mobile.news(snap(quota="warn"), snap(quota="over"))] == ["quota"]
    assert mobile.news(snap(gold="over"), snap(gold="ok")) == []


@pytest.mark.asyncio
async def test_the_version_handshake_takes_the_token(fake_repo):
    server = Server(_host(fake_repo))
    task = asyncio.create_task(server.run())
    for _ in range(100):
        if server.ready.is_set():
            break
        await asyncio.sleep(0.02)

    def get(path: str, headers: dict | None = None) -> tuple[int, dict]:
        req = urllib.request.Request(f"{server.origin}{path}", headers=headers or {})
        try:
            with urllib.request.urlopen(req, timeout=5) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, {}
    try:
        assert (await asyncio.to_thread(get, "/api/version"))[0] == 403
        assert (await asyncio.to_thread(get, "/api/version?t=guess"))[0] == 403
        status, body = await asyncio.to_thread(get, f"/api/version?t={server.token}")
        assert status == 200 and body == {"name": "orkcraft", "version": body["version"], "protocol": PROTOCOL,
                                          "api": mobile.API}
        status, _ = await asyncio.to_thread(get, "/api/version", {"Authorization": f"Bearer {server.token}"})
        assert status == 200
    finally:
        server.stop()
        await asyncio.wait_for(task, 10)


# -- stage 2: the drop's client id, the Workchief's answers, the notifier ---------------------------

def test_a_drop_with_a_client_id_is_made_once_an_hour(fake_repo, isolated_layout_file):
    import base64
    from orkcraft.core.workers import pit as pit_worker
    host = _host(fake_repo)
    pit = buildings.raise_spec(host.town, buildings.type_spec(host.town, "pit")).id
    drop = lambda args: host.command("act", {"id": pit, "act": "drop", "args": args})      # noqa: E731
    assert drop({"text": "ship on Friday", "client_id": "phone-1"}) == 1
    assert drop({"text": "ship on Friday", "client_id": "phone-1"}) == 1                    # a retry: the same answer…
    assert drop({"text": "ship on Friday"}) == 1                                            # …no id: dropped again
    data = base64.b64encode(b"photo").decode()
    file = lambda: host.command("act", {"id": pit, "act": "drop_file",                      # noqa: E731
                                        "args": {"name": "IMG_1.jpg", "data": data, "client_id": "phone-2"}})
    assert file() == 1 and file() == 1
    assert len(host.detail(pit)["data"]["items"]) == 3
    w = host.town.worker(pit)
    made = []
    assert w.once("x", lambda: made.append(1) or 1, now=0.0) == 1
    assert w.once("x", lambda: made.append(1) or 1, now=pit_worker.CLIENT_ID_S - 1) == 1 and made == [1]
    assert w.once("x", lambda: made.append(1) or 1, now=pit_worker.CLIENT_ID_S + 1) == 1 and made == [1, 1]


def test_the_chat_comes_to_a_phone_as_plain_text(fake_repo, isolated_layout_file):
    host = _host(fake_repo)
    assert mobile.allowed(host, "mobile.chat") and "mobile.chat" in host.commands
    hall = host.town.worker("town_hall")
    hall._say("you", "What should I build?")
    hall._say("warchief", "Build a **Lake**:\n\n- for notes\n- for `links`", card={"kind": "build", "type": "lake"})
    got = host.command("mobile.chat", {"limit": 1})
    json.dumps(got)
    (m,) = got["chat"]
    assert m["who"] == "warchief" and m["text"] == "Build a Lake:\n\n- for notes\n- for links" and m["offer"]
    assert [x["who"] for x in host.command("mobile.chat")["chat"]][-2:] == ["you", "warchief"]
    assert len(host.command("mobile.chat", {"limit": 999})["chat"]) <= mobile.CHAT_MESSAGES


class _Listener:
    def __init__(self):
        self.phones, self.sent = {"open"}, []
        self.on_push = None

    def broadcast(self, msg):
        self.sent.append(msg)


def test_the_notifier_says_each_new_question_once_in_one_line(fake_repo):
    from orkcraft.gui import notify
    host = _host(fake_repo)
    listener = _Listener()
    n = notify.Notifier(host, listener)
    assert listener.on_push == n.after

    def snap(alerts=(), gold="ok"):
        return {"resources": {"gold": "Spend", "quota": "Quota"},
                "alerts": [{"id": i, "title": "Proceed?", "who": "Grunt"} for i in alerts],
                "hud": {"gold": "$4.10 / $5.00", "gold_level": gold, "quota_level": "ok"}}
    n.after(snap(["a"]))
    assert listener.sent == []                                          # the first look wakes nobody
    n.after(snap(["a", "b"], gold="warn"))
    (msg,) = listener.sent
    assert [x["line"] for x in msg["news"]] == ["Grunt asks: Proceed?", "Spend is near its limit: $4.10 / $5.00"]
    n.after(snap(["a", "b"], gold="warn"))
    assert len(listener.sent) == 1
    n.after(None)                                                       # no phone open: the next look is a first look
    n.after(snap(["a", "b", "c"]))
    assert len(listener.sent) == 1


def test_the_notifier_says_an_error_by_its_title_only_and_a_session_that_ended(fake_repo):
    from orkcraft.core import bus
    from orkcraft.gui import notify
    host = _host(fake_repo)
    listener = _Listener()
    notify.Notifier(host, listener)
    host.town.toast("token=sk-secret in /home/me/.env", title="🛣 Roads", severity="error")
    host.town.toast("all good", title="Roads")
    host.town.publish(bus.SESSION, key="new:claude:1", state="exited", code=1)
    lines = [x["line"] for m in listener.sent for x in m["news"]]
    assert lines == ["Something failed: Roads", "A session stopped with an error"]
    assert "secret" not in json.dumps(listener.sent)
    listener.phones = set()
    host.town.toast("again", title="Roads", severity="error")
    assert len(listener.sent) == 2                                      # no phone open: nothing to say it to


def test_a_phone_may_write_on_task_fields_and_nothing_else_there(fake_repo, isolated_layout_file):
    host = _host(fake_repo)
    fields = buildings.raise_spec(host.town, buildings.type_spec(host.town, "fields")).id
    may = lambda act: mobile.allowed(host, "act", {"id": fields, "act": act})      # noqa: E731
    assert may("add")
    for act in ("move", "edit", "delete", "send", "color", "flip"):
        assert not may(act), act


def test_the_widget_is_task_fields_its_to_dos_notes_lanes_and_where_a_card_goes(fake_repo, isolated_layout_file):
    host = _host(fake_repo)
    fields = buildings.raise_spec(host.town, buildings.type_spec(host.town, "fields")).id
    host.command("act", {"id": fields, "act": "add", "args": {"title": "Buy milk", "lane": "mine"}})
    w = mobile.compact(host.snapshot())["widget"]
    assert w["id"] == fields and w["todo_lane"] == "mine" and w["note_lane"]
    assert "Buy milk" in w["todos"]["top"] and w["todos"]["open"] == 1
    assert {ln["id"] for ln in w["lanes"]} >= {"todo", "done"}
    # Where a new task or note goes: the roads that leave the board for it, by the receiving building's title.
    full = {"buildings": [{"id": "f", "type": "fields", "title": "🌾 Task Fields", "card": {"todos": {"open": 0, "count": 0,
            "top": []}, "ideas": None, "lanes": [], "todo_lane": "mine", "note_lane": "ideas"}},
            {"id": "b", "type": "barracks", "title": "🛖 Barracks"}, {"id": "w", "type": "scrolls", "title": "📜 Wiki"}],
            "roads": [{"from": "f", "to": "b", "event": "tasks.created"}, {"from": "f", "to": "w", "event": "notes.created"},
                      {"from": "b", "to": "w", "event": "tasks.created"}]}
    w = mobile.compact(full)["widget"]
    assert w["sends"]["task"] == [{"id": "b", "title": "🛖 Barracks", "title_plain": "Agent pool"}]
    assert [x["title"] for x in w["sends"]["note"]] == ["📜 Wiki"]
    assert mobile.compact({"buildings": [{"id": "p", "type": "pit", "title": "Pit"}]})["widget"] is None


def test_the_roads_come_to_a_phone_as_pairs_of_its_buildings_each_once():
    full = {"buildings": [{"id": "a", "type": "pit", "title": "A"}, {"id": "b", "type": "forge", "title": "B"}],
            "roads": [{"from": "a", "to": "b", "event": "pit.file"}, {"from": "a", "to": "b", "event": "pit.text"},
                      {"from": "clock", "to": "b", "event": "tick"}, {"from": "b", "to": "b", "event": "x"}]}
    assert mobile.compact(full)["roads"] == [["a", "b"]]


def test_a_phone_presses_a_buildings_quick_actions_but_never_one_that_reads_the_computer(fake_repo, isolated_layout_file):
    """A building's quick actions come to the phone as its card has them, each an input the phone may press
    (`building.input`): one that takes text says so, one that reaches out is asked first, and one that reads the
    computer (its clipboard, a path) or only opens a window of the desktop's never comes."""
    host = _host(fake_repo)
    pit = buildings.raise_spec(host.town, buildings.type_spec(host.town, "pit")).id
    cat = buildings.raise_spec(host.town, buildings.type_spec(host.town, "catapult")).id
    host.tick()
    snap = {b["id"]: b for b in host.command("mobile.snapshot")["buildings"]}
    assert snap[pit]["quick"] == []                                              # Paste reads the computer's clipboard
    fire = next(q for q in snap[cat]["quick"] if q["id"] == "catapult.fire")
    assert fire == {"id": "catapult.fire", "label": "Fire", "takes": "", "ask": True}
    may = lambda bid, inp: mobile.allowed(host, "building.input", {"id": bid, "input": inp})      # noqa: E731
    assert may(cat, "catapult.dry_run") and may("town_hall", "hall.audit")
    assert not may(pit, "pit.paste") and not may("town_hall", "hall.build") and not may("nowhere", "hall.audit")
    assert not may(cat, "hall.audit")                                           # another building's action
    assert mobile.guard("building.input", {"id": cat, "input": "catapult.dry_run", "by": "bench"})["by"] == "person"
    assert mobile.quick([{"id": "pool.task", "label": "New task"}]) == [
        {"id": "pool.task", "label": "New task", "takes": "text", "ask": False}]


def test_the_phone_says_once_quietly_when_the_computer_is_on_battery_and_may_sleep(fake_repo, isolated_layout_file):
    host = _host(fake_repo)
    host.away.platform = "darwin"
    host.away.power = lambda: False
    snap = host.command("mobile.snapshot")
    assert snap["portrait"]["sleep"] == "Your Mac is on battery and may sleep."
    host.away.power, host.away._power_at = (lambda: True), -1e9                    # on power again
    again = host.command("mobile.snapshot", {"since": snap["rev"]})
    assert again["portrait"]["sleep"] == "" and again["rev"] != snap["rev"]
    host.away.power, host.away._power_at = (lambda: None), -1e9                    # a desktop that tells nothing
    assert host.command("mobile.snapshot")["portrait"]["sleep"] == ""


def test_the_notifier_says_an_idea_and_a_digest_in_one_line(fake_repo):
    from orkcraft.gui import notify
    n = notify.Notifier(_host(fake_repo), _Listener())
    snap = {"resources": {"gold": "Spend", "quota": "Quota"}}
    assert n.line({"kind": "idea", "slug": "dark", "title": "Dark mode", "state": "plan"}, snap)["line"] \
        == "Dark mode: plan ready"
    assert n.line({"kind": "idea", "slug": "x", "title": "Sync", "state": "asks"}, snap)["line"] \
        == "Sync: the Taskmaster asks you"
    assert n.line({"kind": "digest", "merged": 3, "done": 1, "spent": "$1.20"}, snap)["line"] \
        == "3 merged · 1 done · $1.20"
