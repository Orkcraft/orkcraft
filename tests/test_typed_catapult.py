"""🎯 The Catapult (T1107 stage 9): fan-in, schema check, send, dry run, confirm, never in the demo."""
from __future__ import annotations

import io
import json
import urllib.error
from pathlib import Path

import pytest

from orkcraft import scroll as ts
from orkcraft.app import OrkcraftApp
from orkcraft.realm import audit, catapult as cp, masonry, pipes
from orkcraft.screens.dialogs import Confirm
from orkcraft.screens.typed.catapult_view import CatapultView

SCHEMA = {"type": "object", "required": ["notes", "version"],
          "properties": {"notes": {"type": "string"}, "version": {"type": "object", "required": ["tag"],
                                                                         "properties": {"tag": {"type": "string"}}}}}


class Answer(io.BytesIO):
    status = 201

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class Net:
    def __init__(self, status=201):
        self.requests, self.status = [], status

    def __call__(self, req, timeout=None):
        self.requests.append(req)
        if self.status >= 400:
            raise urllib.error.HTTPError(req.full_url, self.status, "nope", {}, io.BytesIO(b"bad token"))
        a = Answer(b'{"id": 7}')
        a.status = self.status
        return a


def test_load_check_and_fire(tmp_path: Path):
    load = cp.Load(tmp_path)
    load.put("notes", "release notes")
    assert not load.ready(["notes", "version"]) and load.missing(["notes", "version"]) == ["version"]
    load.put("version", '{"tag": "v0.2.0"}')
    assert load.ready(["notes", "version"])
    body = load.body(["notes", "version"])
    assert body == {"notes": "release notes", "version": {"tag": "v0.2.0"}}
    (tmp_path / "s.json").write_text(json.dumps(SCHEMA))
    assert cp.check(body, tmp_path / "s.json") == []
    assert cp.check({"notes": 1}, tmp_path / "s.json")
    net = Net()
    shot = cp.fire("https://api.example.com/releases", "POST", body, "t0k", net)
    req = net.requests[0]
    assert shot.ok and shot.status == 201 and req.get_header("Authorization") == "Bearer t0k"
    assert json.loads(req.data) == body and "t0k" not in shot.body
    bad = cp.fire("https://api.example.com/releases", "POST", body, "", Net(401))
    assert not bad.ok and bad.status == 401 and bad.answer == "bad token"
    assert "http or https" in cp.fire("file:///etc/passwd", "POST", body).error
    single = cp.Load(tmp_path / "one")
    single.put("pit", '{"a": 1}')
    assert single.body([]) == {"a": 1}


@pytest.mark.asyncio
async def test_the_catapult_waits_for_both_roads_then_fires(fake_repo: Path, monkeypatch):
    (fake_repo / "release.schema.json").write_text(json.dumps(SCHEMA))
    spec = {"id": "launcher", "title": "Catapult", "icon": "🎯", "orc": {"name": "Loader"}, "type": "catapult",
            "config": {"url": "https://api.example.com/releases", "schema": "release.schema.json",
                       "wait_for": ["notes", "version"], "token_env": "T_API"}}
    assert masonry.save_spec(fake_repo, spec) == []
    monkeypatch.setenv("T_API", "s3cret")
    net = Net()
    monkeypatch.setattr(CatapultView, "opener", staticmethod(net))
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    ts.subscribe(app.scroll, "town_hall", "launcher", "catapult.sent")
    async with app.run_test(size=(200, 46)) as pilot:
        await pilot.pause()
        view = app.desktop.get_window("launcher").query_one(CatapultView)
        sent = []
        monkeypatch.setattr(app.roads, "emit", lambda payload, meta=None: sent.append(payload) or [])
        app.deliver_payload("launcher", pipes.Payload(pipes.TEXT, "notes for v0.2", "notes", "mill.done", "notes"))
        assert view.mini_status() == ["waits for version"] and not net.requests
        app.deliver_payload("launcher", pipes.Payload(pipes.TEXT, '{"tag": "v0.2.0"}', "version", "mill.done", "v"))
        for _ in range(40):
            await pilot.pause(0.05)
            if sent:
                break
        assert len(net.requests) == 1 and [p.mode for p in sent] == ["catapult.sent"]   # no question asked
        assert view.mini_status() == ["waits for notes, version", "✓ 201"]    # unloaded after the shot
        app.deliver_payload("launcher", pipes.Payload(pipes.TEXT, '{"tag": 3}', "version", "mill.done", "v"))
        view.quick_action("catapult.dry_run")                          # the schema stops it first
        assert "'notes' is a required property" in view.shots[0].error and len(net.requests) == 1
        app.deliver_payload("launcher", pipes.Payload(pipes.TEXT, "n", "notes", "mill.done", "n"))
        assert len(net.requests) == 1 and "tag" in view.shots[0].error    # loaded but invalid: not sent
        app.deliver_payload("launcher", pipes.Payload(pipes.TEXT, '{"tag": "v0.2.1"}', "version", "mill.done", "v"))
        for _ in range(40):
            await pilot.pause(0.05)
            if len(net.requests) == 2:
                break
        assert len(net.requests) == 2
        app.desktop.focus_window(app.desktop.get_window("launcher"))
        await pilot.pause()
        await pilot.press("c")
        await pilot.pause()
        app.deliver_payload("launcher", pipes.Payload(pipes.TEXT, "notes", "notes", "mill.done", "n"))
        app.deliver_payload("launcher", pipes.Payload(pipes.TEXT, '{"tag": "v0.2.1"}', "version", "mill.done", "v"))
        await pilot.pause()
        assert isinstance(app.screen, Confirm)                           # confirm on: asked first
        await pilot.press("n")
        await pilot.pause()
        assert len(net.requests) == 2
    assert audit._security(fake_repo, {"x": {"id": "x", "type": "catapult", "config": {"url": "https://a"}}})


@pytest.mark.asyncio
async def test_the_demo_never_sends(fake_repo: Path, monkeypatch):
    spec = {"id": "launcher", "title": "Catapult", "icon": "🎯", "orc": {"name": "Loader"}, "type": "catapult",
            "config": {"url": "https://api.example.com/x"}}
    assert masonry.save_spec(fake_repo, spec) == []
    net = Net()
    monkeypatch.setattr(CatapultView, "opener", staticmethod(net))
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False, demo=True)
    async with app.run_test(size=(200, 46)) as pilot:
        await pilot.pause()
        view = app.desktop.get_window("launcher").query_one(CatapultView)
        app.deliver_payload("launcher", pipes.Payload(pipes.TEXT, '{"a": 1}', "pit", "pit.text", "x"))
        await pilot.pause()
        assert not net.requests and view.shots[0].dry
