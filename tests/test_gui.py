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


# -- the buildings' windows (gui/views/) --------------------------------------------------------

def _raised(host: Host, type_id: str, **config) -> str:
    spec = buildings.type_spec(host.town, type_id)
    if config:
        spec["config"] = {**(spec.get("config") or {}), **config}
    built = buildings.raise_spec(host.town, spec)
    assert built is not None
    return built.id


def test_markdown_never_carries_markup_or_script():
    from orkcraft.gui import markdown
    out = markdown.render("# Hi\n\n<script>alert(1)</script>\n\n[x](javascript:alert(1)) <img src=x onerror=y>")
    assert "<h1>Hi</h1>" in out and "<script" not in out and "<img" not in out and 'href="javascript' not in out


def test_a_building_without_a_gui_view_says_what_it_is(fake_repo):
    host = _host(fake_repo)
    d = host.detail("town_hall")
    assert d["data"] is None and d["ui"]["panes"] and host.detail("nowhere") is None
    with pytest.raises(CommandError):
        host.command("act", {"id": "town_hall", "act": "edit"})


def test_task_fields_window_is_the_board_and_its_acts_change_the_file(fake_repo):
    host = _host(fake_repo)
    bid = _raised(host, "fields")
    d = host.detail(bid)
    assert d["type"] == "fields" and [p["id"] for p in d["ui"]["panes"]] == ["board"]
    assert [ln["id"] for ln in d["data"]["lanes"]][:3] == ["todo", "in_progress", "done"]
    card = host.command("act", {"id": bid, "act": "add", "args": {"lane": "todo", "title": " Ship  it ", "body": "now"}})
    assert card and any(c["title"] == "Ship it" for c in host.detail(bid)["data"]["lanes"][0]["cards"])
    host.command("act", {"id": bid, "act": "color", "args": {"card": card}})
    card = host.command("act", {"id": bid, "act": "edit", "args": {"card": card, "title": "Ship it today", "body": ""}})
    host.command("act", {"id": bid, "act": "move", "args": {"card": card, "lane": "done"}})
    done = next(ln for ln in host.detail(bid)["data"]["lanes"] if ln["id"] == "done")["cards"]
    shipped = next(c for c in done if c["id"] == card)
    assert shipped["title"] == "Ship it today" and shipped["color"] == "yellow"      # the colour stays on an edit
    assert "🟨 Ship it today" in (fake_repo / "TASKS.md").read_text(encoding="utf-8")
    host.command("act", {"id": bid, "act": "remove", "args": {"card": card}})
    assert "Ship it today" not in (fake_repo / "TASKS.md").read_text(encoding="utf-8")
    for bad in ({"card": "gone"}, {"card": 7}):
        with pytest.raises(CommandError):
            host.command("act", {"id": bid, "act": "flip", "args": bad})
    with pytest.raises(CommandError):
        host.command("act", {"id": bid, "act": "add", "args": {"title": "   "}})


def test_the_lake_window_shows_markdown_and_edits_the_file_in_place(fake_repo):
    from orkcraft.realm import lake
    host = _host(fake_repo)
    bid = _raised(host, "lake")
    w = host.town.worker(bid)
    w.show(lake.look(fake_repo, "file", str(fake_repo / "docs" / "notes.md"), "notes"))
    view = host.detail(bid)["data"]["view"]
    assert view["kind"] == "markdown" and "<h1>Notes</h1>" in view["html"] and view["editable"]
    assert host.command("act", {"id": bid, "act": "edit"})
    editing = host.detail(bid)["data"]["editing"]
    assert editing["path"] == "docs/notes.md" and editing["text"].startswith("# Notes")
    text = editing["text"] + "- from the window\n"
    host.command("act", {"id": bid, "act": "typed", "args": {"text": text}})
    assert host.detail(bid)["data"]["editing"]["note"] == "● unsaved"
    assert host.command("act", {"id": bid, "act": "done", "args": {"text": text}})
    assert host.detail(bid)["data"]["editing"] is None
    assert (fake_repo / "docs" / "notes.md").read_text(encoding="utf-8").endswith("- from the window\n")


def test_the_lake_never_saves_over_a_change_on_disk_unless_asked(fake_repo):
    from orkcraft.realm import lake
    host = _host(fake_repo)
    bid = _raised(host, "lake")
    path = fake_repo / "docs" / "notes.md"
    host.town.worker(bid).show(lake.look(fake_repo, "file", str(path), "notes"))
    host.command("act", {"id": bid, "act": "edit"})
    path.write_text("# Changed elsewhere\n", encoding="utf-8")
    assert host.command("act", {"id": bid, "act": "save", "args": {"text": "# Mine\n"}}) is False
    assert host.detail(bid)["data"]["editing"]["conflict"]
    assert path.read_text(encoding="utf-8") == "# Changed elsewhere\n"
    assert host.command("act", {"id": bid, "act": "save", "args": {"text": "# Mine\n", "force": True}})
    assert path.read_text(encoding="utf-8") == "# Mine\n"


def test_the_scroll_dump_window_is_its_tree_and_reads_a_page(fake_repo):
    host = _host(fake_repo)
    bid = _raised(host, "scrolls", paths=["docs"], auto_ingest=False)
    host.tick(now=1e9)                                  # its worker looks at the sources
    data = host.detail(bid)["data"]
    assert data["sources"] and any(n["path"] == "docs/notes.md" for b in data["sources"] for n in b["items"])
    assert data["pending"] >= 1 and "to take in" in data["state_plain"]
    page = host.command("act", {"id": bid, "act": "read", "args": {"path": "docs/notes.md"}})
    assert "<h1>Notes</h1>" in page["html"]
    with pytest.raises(CommandError):
        host.command("act", {"id": bid, "act": "add_folder", "args": {"path": "no/such/folder"}})


@pytest.mark.asyncio
async def test_an_open_building_gets_its_state_and_again_when_it_changes(fake_repo):
    host = _host(fake_repo)
    bid = _raised(host, "fields")
    server = Server(host)
    task = await _serving(server)
    try:
        async with connect(f"ws://127.0.0.1:{server.port}/ws?t={server.token}", origin=server.origin) as ws:
            async def until(pred):
                while True:
                    msg = json.loads(await asyncio.wait_for(ws.recv(), 5))
                    if pred(msg):
                        return msg
            await ws.send(json.dumps({"t": "cmd", "id": 1, "name": "watch", "args": {"ids": [bid]}}))
            first = await until(lambda m: m["t"] == "detail")
            assert first["detail"]["id"] == bid and first["detail"]["data"]["lanes"]
            await ws.send(json.dumps({"t": "cmd", "id": 2, "name": "act",
                                      "args": {"id": bid, "act": "add", "args": {"title": "Pushed"}}}))
            again = await until(lambda m: m["t"] == "detail" and any(
                c["title"] == "Pushed" for ln in m["detail"]["data"]["lanes"] for c in ln["cards"]))
            assert again["detail"]["type"] == "fields"
    finally:
        server.stop()
        await asyncio.wait_for(task, 10)


def test_every_road_has_a_town_wide_key(fake_repo):
    """A road's own id is unique only in the building that keeps it; the page plans roads by key."""
    from orkcraft import scroll
    host = _host(fake_repo)
    a, b, c = _raised(host, "fields"), _raised(host, "lake"), _raised(host, "lake")
    ids = [scroll.subscribe(host.town.scroll, b, a, "tasks.created").id,      # each the first in its building
           scroll.subscribe(host.town.scroll, c, a, "tasks.created").id]
    assert ids[0] == ids[1]
    keys = [r["id"] for r in host.snapshot()["roads"]]
    assert len(keys) == len(set(keys))
    assert all(r["id"] == f"{r['to']}:{r['road']}" for r in host.snapshot()["roads"])


# -- sessions and Orders through the host and the socket ------------------------------------------

def _fake_cli(tmp_path, monkeypatch) -> None:
    import stat
    path = tmp_path / "fake-claude"
    path.write_text("#!/bin/sh\nprintf 'Proceed?\\r\\n1. Yes\\r\\n2. No\\r\\n'\nstty -icanon\n"
                    "a=$(dd bs=1 count=1 2>/dev/null)\nprintf 'chose %s\\r\\n' \"$a\"\nsleep 30\n", encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    monkeypatch.setenv("ORKCRAFT_CLAUDE_BIN", str(path))


def test_orders_answer_a_session_question_and_refuse_the_rest(fake_repo, tmp_path, monkeypatch):
    import time
    _fake_cli(tmp_path, monkeypatch)
    host = _host(fake_repo)
    try:
        key = host.command("sessions.new", {"harness": "claude"})
        s = host.sessions.get(key)
        for _ in range(100):
            if "2. No" in "\n".join(s.text_lines()):
                break
            time.sleep(0.05)
        time.sleep(1.1)
        host.tick()
        snap = host.snapshot()
        assert [x["key"] for x in snap["sessions"]] == [key] and snap["sessions"][0]["running"]
        asked = next(a for a in snap["alerts"] if a["ref"] == key)
        assert asked["source"] == "terminal" and asked["options"] == [["1", "Yes"], ["2", "No"]]
        with pytest.raises(CommandError):
            host.command("orders.answer", {"id": asked["id"], "key": "7"})
        assert host.command("orders.answer", {"id": asked["id"], "key": "1"})
        for _ in range(100):
            if any("chose 1" in line for line in s.text_lines()):
                break
            time.sleep(0.05)
        assert any("chose 1" in line for line in s.text_lines())
        with pytest.raises(CommandError):
            host.command("orders.answer", {"id": "term:nobody", "key": "1"})
        with pytest.raises(CommandError):
            host.command("sessions.new", {"harness": "bash"})
        with pytest.raises(CommandError):
            host.command("term.input", {"key": key, "data": 7})
        assert host.command("halt") >= 1                     # Halt All interrupts the session
    finally:
        host.sessions.close()


@pytest.mark.asyncio
async def test_a_terminal_gets_its_session_as_binary_frames(fake_repo, tmp_path, monkeypatch):
    _fake_cli(tmp_path, monkeypatch)
    host = _host(fake_repo)
    server = Server(host)
    task = await _serving(server)
    try:
        async with connect(f"ws://127.0.0.1:{server.port}/ws?t={server.token}", origin=server.origin) as ws:
            async def recv_until(pred):
                while True:
                    msg = await asyncio.wait_for(ws.recv(), 5)
                    if pred(msg):
                        return msg
            await ws.send(json.dumps({"t": "cmd", "id": 1, "name": "sessions.new", "args": {"harness": "claude"}}))
            reply = json.loads(await recv_until(lambda m: isinstance(m, str) and '"reply"' in m))
            key = reply["result"]
            await asyncio.sleep(0.5)
            await ws.send(json.dumps({"t": "cmd", "id": 2, "name": "term.replay", "args": {"key": key}}))
            replay = await recv_until(lambda m: isinstance(m, bytes) and m[0] == 1)
            k = replay[2:2 + replay[1]].decode()
            assert k == key and b"Proceed?" in replay[2 + replay[1]:]
            await ws.send(json.dumps({"t": "cmd", "id": 3, "name": "term.input", "args": {"key": key, "data": "2"}}))
            out = await recv_until(lambda m: isinstance(m, bytes) and m[0] == 0 and b"chose 2" in m)
            assert out[2:2 + out[1]].decode() == key
    finally:
        host.sessions.close()
        server.stop()
        await asyncio.wait_for(task, 10)
