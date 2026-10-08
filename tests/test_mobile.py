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
    assert set(hall) == {"id", "title", "title_plain", "type", "state", "alert"} and hall["type"] == "town_hall"
    assert {"gold", "gold_level", "quota", "quota_level", "alerts"} <= set(snap["hud"])
    assert "roads" not in snap and "words" not in snap and "orkspaces" not in snap
    assert host.command("mobile.snapshot", {"since": snap["rev"]}) == {"v": mobile.API, "rev": snap["rev"],
                                                                       "same": True}
    host.command("hut.move", {"id": board, "x": 0.1, "y": 0.1})           # where a hut stands: not a phone's
    assert host.command("mobile.snapshot", {"since": snap["rev"]})["same"]
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


# -- stage 2: the drop's client id, the Warchief's answers, the notifier ---------------------------

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
    assert [x["line"] for x in msg["news"]] == ["Worker asks: Proceed?", "Spend is near its limit: $4.10 / $5.00"]
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
