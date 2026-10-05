"""The GUI face without a window: the snapshot, the host's commands and the server's socket."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from websockets.asyncio.client import connect
from websockets.exceptions import InvalidStatus

from orkcraft.core import buildings
from orkcraft.gui import server as srv
from orkcraft.gui.host import CommandError, Host
from orkcraft.gui.server import Server
from orkcraft.realm import checkpoint


def _host(repo: Path) -> Host:
    checkpoint.ensure(repo)
    return Host(repo, auto_commit=False)


def test_the_snapshot_is_plain_data_the_page_draws(fake_repo):
    host = _host(fake_repo)
    built = buildings.raise_spec(host.town, buildings.type_spec(host.town, "fields"))
    host.town.worker(built.id)
    host.tick()
    snap = host.snapshot()
    json.dumps(snap)                                   # it crosses the socket as it is
    assert {"project", "hud", "orkspaces", "buildings", "roads", "look"} <= set(snap)
    ids = {b["id"] for b in snap["buildings"]}
    assert {"town_hall", built.id} <= ids
    fields = next(b for b in snap["buildings"] if b["id"] == built.id)
    assert fields["has_worker"] and fields["type"] == "fields" and len(fields["status_plain"]) <= 3
    assert snap["resources"] == {"quota": "Quota", "gold": "Spend", "lumber": "Context", "supply": "Agents"}
    assert snap["hud"]["supply_max"] == host.town.scroll.budget.supply_max_workers


def test_a_hut_moved_keeps_its_spot_in_the_scroll(fake_repo, isolated_layout_file):
    host = _host(fake_repo)
    changed = []
    host.on_change = lambda: changed.append(1)
    host.command("hut.move", {"id": "town_hall", "x": 0.25, "y": 1.7})
    assert host.town.scroll.building("town_hall").hut == [0.25, 1.0]        # kept inside the room
    assert changed and isolated_layout_file.exists()
    assert json.loads(isolated_layout_file.read_text())                      # saved
    with pytest.raises(CommandError):
        host.command("hut.move", {"id": "nowhere", "x": 0, "y": 0})
    with pytest.raises(CommandError):
        host.command("hut.move", {"id": "town_hall", "x": "left"})
    with pytest.raises(CommandError):
        host.command("rm -rf", {})


def test_halt_all_says_what_it_stopped(fake_repo):
    host = _host(fake_repo)
    toasts = []
    host.on_toast = toasts.append
    assert host.command("halt") == 0
    assert toasts[-1]["title"] == "Halt All" and toasts[-1]["message_plain"] == "Nothing was running"


def test_the_server_never_serves_a_file_outside_its_folders():
    assert srv.resolve("/static/app.js") is not None
    assert srv.resolve("/ds/tokens.css") is not None
    assert srv.resolve("/ds/fonts/titillium-web-latin-400-normal.woff2") is not None
    assert srv.resolve("/static/../server.py") is None
    assert srv.resolve("/ds/../../../pyproject.toml") is None
    assert srv.resolve("/etc/passwd") is None


async def _serving(server: Server):
    task = asyncio.create_task(server.run())
    for _ in range(100):
        if server.ready.is_set():
            return task
        await asyncio.sleep(0.02)
    raise AssertionError("the server did not start")


@pytest.mark.asyncio
async def test_the_socket_takes_only_its_own_page_and_answers_commands(fake_repo):
    server = Server(_host(fake_repo))
    task = await _serving(server)
    ws_url = f"ws://127.0.0.1:{server.port}/ws?t={server.token}"
    try:
        for url, origin in ((ws_url, "http://evil.example"), (ws_url.replace(server.token, "guess"), server.origin)):
            with pytest.raises(InvalidStatus):
                async with connect(url, origin=origin):
                    pass
        async with connect(ws_url, origin=server.origin) as ws:
            first = json.loads(await ws.recv())
            assert first["t"] == "state" and first["state"]["buildings"]
            await ws.send(json.dumps({"t": "cmd", "id": 1, "name": "hut.move",
                                      "args": {"id": "town_hall", "x": 0.5, "y": 0.5}}))
            await ws.send(json.dumps({"t": "cmd", "id": 2, "name": "nope"}))
            got = {}
            while len([m for m in got.values() if m["t"] == "reply"]) < 2 or "state" not in got:
                msg = json.loads(await asyncio.wait_for(ws.recv(), 5))
                got[msg.get("id") if msg["t"] == "reply" else msg["t"]] = msg
            assert got[1]["ok"] and not got[2]["ok"] and "Unknown command" in got[2]["error"]
            hall = next(b for b in got["state"]["state"]["buildings"] if b["id"] == "town_hall")
            assert hall["hut"] == [0.5, 0.5]
    finally:
        server.stop()
        await asyncio.wait_for(task, 10)


@pytest.mark.asyncio
async def test_the_page_and_the_design_system_are_served(fake_repo):
    import urllib.request
    server = Server(_host(fake_repo))
    task = await _serving(server)

    def get(path: str) -> tuple[int, str, bytes]:
        try:
            with urllib.request.urlopen(f"{server.origin}{path}", timeout=5) as r:
                return r.status, r.headers["Content-Type"], r.read()
        except urllib.error.HTTPError as e:
            return e.code, "", b""
    try:
        status, kind, body = await asyncio.to_thread(get, "/")
        assert status == 200 and kind.startswith("text/html") and b"importmap" in body
        status, kind, body = await asyncio.to_thread(get, "/roles.css")
        assert status == 200 and b".ok-font-status" in body
        status, kind, _ = await asyncio.to_thread(get, "/static/vendor/preact.mjs")
        assert status == 200 and kind.startswith("text/javascript")
        status, kind, _ = await asyncio.to_thread(get, "/ds/fonts/almendra-sc-latin-400-normal.woff2")
        assert status == 200 and kind == "font/woff2"
        assert (await asyncio.to_thread(get, "/static/../host.py"))[0] == 404
    finally:
        server.stop()
        await asyncio.wait_for(task, 10)


def test_every_module_the_page_imports_is_there():
    """The import map and the relative imports name files that exist: no build step catches it."""
    import re
    static = srv.STATIC
    index = (static / "index.html").read_text(encoding="utf-8")
    for path in re.findall(r'"(/static/[^"]+)"', index):
        assert (static / path.removeprefix("/static/")).is_file(), path
    for js in static.rglob("*.js"):
        for rel in re.findall(r'from "(\.{1,2}/[^"]+)"', js.read_text(encoding="utf-8")):
            assert (js.parent / rel).resolve().is_file(), f"{js.name} imports {rel}"


def test_the_page_says_ork_never_orc():
    import re
    for path in srv.STATIC.rglob("*"):
        if path.suffix in (".js", ".html", ".css") and "vendor" not in path.parts:
            text = path.read_text(encoding="utf-8")
            visible = re.findall(r">([^<>]*)<", text) + re.findall(r'(?:title|aria-label)="([^"]*)"', text)
            for words in visible:
                assert not re.search(r"\b[Oo]rcs?\b|[Oo]rchestrat", words), (path.name, words)
