"""🎯 The Catapult in the GUI (docs/design/building-views.md §3): its card, its detail and every act,
through the host, with no window."""
from __future__ import annotations

import io
import json
import time
from pathlib import Path

import pytest

from orkcraft.core import buildings
from orkcraft.core.workers.catapult import CatapultWorker
from orkcraft.gui.host import CommandError, Host
from orkcraft.realm import catapult_web as cw, checkpoint, pipes

SCHEMA = {"type": "object", "required": ["notes", "version"],
          "properties": {"version": {"type": "object", "required": ["tag"], "properties": {"tag": {"type": "string"}}}}}


class Net:
    def __init__(self) -> None:
        self.requests = []

    def __call__(self, req, timeout=None):
        self.requests.append(req)
        return _Resp(io.BytesIO(b'{"id": 7}'))


class _Resp:
    def __init__(self, f) -> None:
        self.f, self.status = f, 201

    def __enter__(self):
        return self

    def __exit__(self, *a) -> None:
        pass

    def read(self, *a):
        return self.f.read(*a)

    def getcode(self) -> int:
        return 201


def wait(cond, seconds: float = 10.0) -> None:
    end = time.monotonic() + seconds
    while not cond():
        assert time.monotonic() < end, "timed out"
        time.sleep(0.02)


@pytest.fixture
def catapult(fake_repo: Path, monkeypatch):
    (fake_repo / "release.schema.json").write_text(json.dumps(SCHEMA))
    net = Net()
    monkeypatch.setattr(CatapultWorker, "opener", staticmethod(net))
    checkpoint.ensure(fake_repo)
    host = Host(fake_repo, auto_commit=False)
    spec = buildings.type_spec(host.town, "catapult")
    spec["config"] = {**(spec.get("config") or {}), "url": "https://api.example.com/releases",
                      "schema": "release.schema.json", "wait_for": ["notes", "version"]}
    built = buildings.raise_spec(host.town, spec)
    return host, built.id, host.town.worker(built.id), net


def act(host: Host, bid: str, name: str, **args):
    return host.command("act", {"id": bid, "act": name, "args": args})


def card(host: Host, bid: str) -> dict:
    return next(b for b in host.snapshot()["buildings"] if b["id"] == bid)["card"]


def test_it_waits_checks_and_fires(catapult):
    host, bid, w, net = catapult
    c = card(host, bid)
    assert (c["line"], c["tone"], c["browser"]) == ("wait 0/2", "muted", False)
    assert c["target"] == "POST api.example.com/releases" and (c["loaded"], c["waits"], c["last"]) == (0, 2, None)
    w.receive(pipes.Payload(pipes.TEXT, "notes for v0.2", "notes", "mill.done", "notes"), "", "")
    assert card(host, bid)["line"] == "wait 1/2"
    d = host.detail(bid)["data"]
    assert d["wait_for"] == [{"source": "notes", "loaded": True}, {"source": "version", "loaded": False}]
    assert any("version" in p for p in d["problems"])                  # the schema check, before a shot
    w.receive(pipes.Payload(pipes.TEXT, '{"tag": "v0.2.0"}', "version", "mill.done", "v"), "", "")
    wait(lambda: not w.firing and w.shots)
    c = card(host, bid)
    assert len(net.requests) == 1 and (c["line"], c["tone"], c["browser"]) == ("✓ 201", "ok", False)
    assert c["last"]["mark"] == "✓ 201" and c["last"]["tone"] == "ok"
    s = host.detail(bid)["data"]["shots"][0]
    assert s["ok"] and s["status"] == 201 and "v0.2.0" in s["body"] and s["screens"] == []


def test_confirm_is_a_setting_and_a_shot_waits_for_the_yes(catapult):
    host, bid, w, net = catapult
    assert act(host, bid, "confirm", on=True) is True and host.detail(bid)["data"]["confirm"]
    w.receive(pipes.Payload(pipes.TEXT, "n", "notes", "mill.done", "n"), "", "")
    w.receive(pipes.Payload(pipes.TEXT, '{"tag": "v1"}', "version", "mill.done", "v"), "", "")
    d = host.detail(bid)["data"]
    assert d["asking"]["title"].startswith("Send to https://api.example.com") and not net.requests
    assert card(host, bid)["tone"] == "fire"
    act(host, bid, "answer", yes=False)
    assert not net.requests and not w.firing and host.detail(bid)["data"]["asking"] is None
    with pytest.raises(CommandError):
        act(host, bid, "answer", yes=True)                              # nothing waits now
    assert act(host, bid, "dry_run") is False                           # a declined shot is gone: nothing to show
    assert act(host, bid, "confirm", on=False) is False


def test_browser_acts_refuse_outside_browser_mode_and_pictures_are_its_own(catapult, fake_repo: Path):
    host, bid, w, net = catapult
    for name in ("scout", "login", "map", "finish"):
        with pytest.raises(CommandError):
            act(host, bid, name)
    pic = w.state_dir / "screens" / "x-1-event.png"
    pic.parent.mkdir(parents=True)
    pic.write_bytes(b"\x89PNG\r\n\x1a\nfake")
    w._screens("2026-10-05T10:00:00", [("event", pic)])
    rel = str(pic.relative_to(fake_repo))
    assert act(host, bid, "picture", path=rel).startswith("data:image/png;base64,")
    with pytest.raises(CommandError):
        act(host, bid, "picture", path="README.md")                     # only a picture it kept


def test_a_browser_catapult_lists_its_forms(fake_repo: Path):
    checkpoint.ensure(fake_repo)
    host = Host(fake_repo, auto_commit=False)
    spec = buildings.type_spec(host.town, "catapult")
    spec["config"] = {**(spec.get("config") or {}), "mode": "browser",
                      "forms": ["event = https://play.example.com/events/new | the new-event form"]}
    bid = buildings.raise_spec(host.town, spec).id
    w = host.town.worker(bid)
    cw.save_map(w.fdir("event"), {"url": "https://play.example.com/events/new", "submit": "Save",
                                  "fields": [{"label": "Event name", "selector": "#name", "kind": "text"}]})
    w.receive(pipes.Payload(pipes.TEXT, '{"name": "Halloween"}', "pit", "pit.text", "x"), "", "")
    f = host.detail(bid)["data"]["forms"][0]
    assert f["name"] == "event" and f["scouted"] and f["submit"] == "Save"
    assert card(host, bid)["browser"]


def test_the_worker_registers_itself():
    from orkcraft.core import workers
    assert workers.registry()["catapult"] is CatapultWorker
