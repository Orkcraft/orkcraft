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
    buildings.raise_spec(host.town, buildings.type_spec(host.town, "fields"))
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
    host.command("hut.move", {"id": "town_hall", "x": 0.1, "y": 0.1})     # where a hut stands: not a phone's
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
