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
    act(host, bid, "answer", yes=False)                                 # Later: put off, not lost
    d = host.detail(bid)["data"]
    assert not net.requests and not w.firing and d["asking"] is None
    assert '"v1"' in d["held"] and d["queued"] == 1 and card(host, bid)["line"] == "put off"
    with pytest.raises(CommandError):
        act(host, bid, "answer", yes=True)                              # nothing waits now
    assert act(host, bid, "resume") is True                             # Resume asks again
    assert host.detail(bid)["data"]["asking"] and not net.requests
    act(host, bid, "answer", yes=False, drop=True)                      # Drop: it is let go
    d = host.detail(bid)["data"]
    assert not net.requests and d["held"] == "" and d["queued"] == 0 and d["asking"] is None
    assert act(host, bid, "dry_run") is False                           # nothing is left to show
    assert act(host, bid, "confirm", on=False) is False


def test_a_shot_put_off_holds_the_queue_until_resume_or_drop(catapult):
    host, bid, w, net = catapult
    act(host, bid, "confirm", on=True)
    for tag in ("v1", "v2"):
        w.receive(pipes.Payload(pipes.TEXT, "n", "notes", "mill.done", "n"), "", "")
        w.receive(pipes.Payload(pipes.TEXT, json.dumps({"tag": tag}), "version", "mill.done", "v"), "", "")
    act(host, bid, "answer", yes=False)
    assert host.detail(bid)["data"]["asking"] is None and len(w.queue) == 2   # v2 waits behind v1
    assert card(host, bid)["line"] == "put off +1"
    act(host, bid, "drop", what="next")                                 # v1 goes, v2 asks
    assert '"v2"' in host.detail(bid)["data"]["asking"]["text"] and len(w.queue) == 0
    act(host, bid, "answer", yes=True)
    wait(lambda: not w.firing and net.requests)
    assert len(net.requests) == 1 and b'"v2"' in net.requests[0].data


def test_resume_goes_on_after_stop_all_and_fires_nothing_loaded(catapult):
    host, bid, w, net = catapult
    w.halt()
    w.receive(pipes.Payload(pipes.TEXT, "n", "notes", "mill.done", "n"), "", "")
    assert card(host, bid)["line"] == "stopped" and host.detail(bid)["data"]["paused"]
    assert act(host, bid, "resume") is True
    assert not net.requests and w.load.items == {"notes": "n"}         # the half load stays loaded
    with pytest.raises(CommandError):
        act(host, bid, "resume")                                        # it is not stopped now


def test_a_dry_run_that_fails_the_check_fails_nothing_downstream(catapult, monkeypatch):
    host, bid, w, _ = catapult
    sent = []
    monkeypatch.setattr(w, "emit", lambda event, *a, **k: sent.append(event) or True)
    w.receive(pipes.Payload(pipes.TEXT, "n", "notes", "mill.done", "n"), "", "")
    assert act(host, bid, "dry_run") is False
    s = host.detail(bid)["data"]["shots"][0]
    assert s["dry"] and not s["ok"] and "version" in s["error"]
    assert sent == [] and w.failed is None and card(host, bid)["last"]["mark"] == "✗ dry run"


def test_drop_lets_go_of_the_failed_shot_and_the_load(catapult):
    host, bid, w, net = catapult
    w.receive(pipes.Payload(pipes.TEXT, "n", "notes", "mill.done", "n"), "", "")
    act(host, bid, "fire")                                              # half a load: it fails the schema
    assert host.detail(bid)["data"]["failed"]
    assert act(host, bid, "drop", what="failed") is True and not host.detail(bid)["data"]["failed"]
    with pytest.raises(CommandError):
        act(host, bid, "drop", what="failed")                           # nothing failed now
    w.receive(pipes.Payload(pipes.TEXT, "n2", "notes", "mill.done", "n"), "", "")
    assert act(host, bid, "drop", what="load") is True and host.detail(bid)["data"]["loaded"] == []
    with pytest.raises(CommandError):
        act(host, bid, "drop", what="everything")
    assert not net.requests


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
