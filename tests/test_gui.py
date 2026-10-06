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
    pit = buildings.raise_spec(host.town, buildings.type_spec(host.town, "pit")).id
    host.command("hut.move", {"id": pit, "x": 0.25, "y": 1.7})
    assert host.town.scroll.building(pit).hut == [0.25, 1.0]                 # kept inside the room
    assert changed and isolated_layout_file.exists()
    assert json.loads(isolated_layout_file.read_text())                      # saved
    with pytest.raises(CommandError):
        host.command("hut.move", {"id": "nowhere", "x": 0, "y": 0})
    with pytest.raises(CommandError):
        host.command("hut.move", {"id": pit, "x": "left"})
    with pytest.raises(CommandError, match="corner"):                        # the Hall stands in its corner
        host.command("hut.move", {"id": "town_hall", "x": 0.1, "y": 0.1})
    with pytest.raises(CommandError):
        host.command("rm -rf", {})


def test_a_new_orkspace_is_named_and_the_town_goes_to_it(fake_repo, isolated_layout_file):
    host = _host(fake_repo)
    before = len(host.town.scroll.orkspaces)
    oid = host.command("orkspace.new", {"name": "Billing"})
    assert len(host.town.scroll.orkspaces) == before + 1
    assert host.town.scroll.active_orkspace_id == oid and host.snapshot()["active_orkspace"] == oid
    assert host.command("orkspace.new", {"name": "Billing"}) != oid             # a second of the name gets its own id
    with pytest.raises(CommandError):
        host.command("orkspace.new", {"name": ""})


def test_the_war_map_lands_get_biomes_names_and_go(fake_repo, isolated_layout_file):
    """docs/design/war-map.md: a camp's old default spreads once, a new land takes a free biome, the right
    click renames, changes the biome, removes an empty land; the snapshot says what each land shows."""
    host = _host(fake_repo)
    first = host.town.scroll.orkspaces[0]
    assert first.biome == "dirt" and host.town.scroll.meta.get("biomes")    # the old "forest" spread once
    oid = host.command("orkspace.new", {"name": "Billing"})
    assert host.town.scroll.orkspace(oid).biome == "forest"                  # the first biome nobody has
    host.command("orkspace.biome", {"id": oid, "biome": "lava"})
    host.command("orkspace.rename", {"id": oid, "name": "Payments"})
    land = next(o for o in host.snapshot()["orkspaces"] if o["id"] == oid)
    assert land["biome"] == "lava" and land["name"] == "Payments" and land["count"] == 0 and land["working"] == 0
    with pytest.raises(CommandError):
        host.command("orkspace.biome", {"id": oid, "biome": "desert"})
    with pytest.raises(CommandError):
        host.command("orkspace.rename", {"id": oid, "name": "  "})
    host.command("orkspace.remove", {"id": oid})
    assert host.town.scroll.orkspace(oid) is None
    with pytest.raises(CommandError, match="last"):
        host.command("orkspace.remove", {"id": first.id})


def test_the_snapshot_carries_growth_and_a_buildings_level(fake_repo, isolated_layout_file):
    """docs/design/growth.md: the news, the operator's mascot and deeds, a hut's level and goal for its flag."""
    host = _host(fake_repo)
    pit = buildings.raise_spec(host.town, buildings.type_spec(host.town, "pit")).id
    host.town.scroll.building(pit).level = 2
    host.tick()
    snap = host.snapshot()
    you = snap["growth"]["you"]
    assert you["stage"] >= 1 and you["kin"] and you["name"] and len(you["deeds"]) == 8
    assert next(d for d in you["deeds"] if d["id"] == "town")["done"]          # a building beside the Hall
    hut = next(b for b in snap["buildings"] if b["id"] == pit)
    assert hut["level"] == 2 and hut["goal"] == "balance"
    assert host.command("info", {"id": pit})["level_mark"] == "⚖️ II"
    host.growth._news = [{"id": "n1", "text": "x"}]
    host.command("growth.seen", {"id": "n1"})
    assert host.snapshot()["growth"]["news"] == []


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
    host = _host(fake_repo)
    pit = buildings.raise_spec(host.town, buildings.type_spec(host.town, "pit")).id
    server = Server(host)
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
                                      "args": {"id": pit, "x": 0.5, "y": 0.5}}))
            await ws.send(json.dumps({"t": "cmd", "id": 2, "name": "nope"}))
            got = {}
            while len([m for m in got.values() if m["t"] == "reply"]) < 2 or "state" not in got:
                msg = json.loads(await asyncio.wait_for(ws.recv(), 5))
                got[msg.get("id") if msg["t"] == "reply" else msg["t"]] = msg
            assert got[1]["ok"] and not got[2]["ok"] and "Unknown command" in got[2]["error"]
            moved = next(b for b in got["state"]["state"]["buildings"] if b["id"] == pit)
            assert moved["hut"] == [0.5, 0.5]
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
    loot = host.town.scroll.building("loot")
    loot.demolished = False                     # a built-in with no worker and no view of its own yet
    d = host.detail("loot")
    assert d["data"] is None and d["ui"]["panes"] and host.detail("nowhere") is None
    with pytest.raises(CommandError):
        host.command("act", {"id": "loot", "act": "edit"})
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
    host = _host(fake_repo)
    tab = host.command("lake.open", {"kind": "file", "value": "docs/notes.md", "from": "town_hall"})
    doc = host.command("lake.doc", {"tab": tab})
    view = doc["view"]
    assert view["kind"] == "markdown" and "<h1>Notes</h1>" in view["html"] and view["editable"]
    assert doc["from"] == "town_hall" and doc["path"] == "docs/notes.md" and doc["editing"] is None
    assert host.command("lake.open", {"kind": "file", "value": str(fake_repo / "docs" / "notes.md")}) == tab   # one tab a file
    assert host.command("lake.act", {"tab": tab, "act": "edit"})
    editing = host.command("lake.doc", {"tab": tab})["editing"]
    assert editing["path"] == "docs/notes.md" and editing["text"].startswith("# Notes") and editing["markdown"]
    text = editing["text"] + "- from the window\n"
    host.command("lake.act", {"tab": tab, "act": "typed", "args": {"text": text}})
    assert host.command("lake.doc", {"tab": tab})["editing"]["note"] == "● unsaved"
    assert host.snapshot()["lake"]["tabs"][0]["note"] == "● unsaved"
    assert host.command("lake.act", {"tab": tab, "act": "autosave", "args": {"text": text}})
    assert (fake_repo / "docs" / "notes.md").read_text(encoding="utf-8").endswith("- from the window\n")
    assert host.command("lake.act", {"tab": tab, "act": "done", "args": {"text": text}})
    doc = host.command("lake.doc", {"tab": tab})
    assert doc["editing"] is None and "from the window" in doc["view"]["html"]
    assert host.command("lake.close", {"tab": tab}) and host.snapshot()["lake"]["tabs"] == []
    with pytest.raises(CommandError):
        host.command("lake.doc", {"tab": tab})


def test_the_lake_never_saves_over_a_change_on_disk_unless_asked(fake_repo):
    host = _host(fake_repo)
    path = fake_repo / "src" / "app.py"
    tab = host.command("lake.open", {"kind": "file", "value": "src/app.py"})
    editing = host.command("lake.doc", {"tab": tab})["editing"]          # code opens in its editor
    assert editing and editing["text"] == "print('hello')\n" and not editing["markdown"]
    path.write_text("print('elsewhere')\n", encoding="utf-8")
    assert host.command("lake.act", {"tab": tab, "act": "save", "args": {"text": "print('mine')\n"}}) is False
    assert host.command("lake.doc", {"tab": tab})["editing"]["conflict"]
    assert host.command("lake.close", {"tab": tab, "text": "print('mine')\n"}) is False     # nothing is lost
    assert path.read_text(encoding="utf-8") == "print('elsewhere')\n"
    assert host.command("lake.act", {"tab": tab, "act": "save", "args": {"text": "print('mine')\n", "force": True}})
    assert path.read_text(encoding="utf-8") == "print('mine')\n"
    assert host.command("lake.close", {"tab": tab})


def test_the_lake_shows_pictures_pdfs_pages_and_text(fake_repo):
    import base64
    host = _host(fake_repo)
    png = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==")
    (fake_repo / "docs" / "dot.png").write_bytes(png)
    (fake_repo / "docs" / "paper.pdf").write_bytes(b"%PDF-1.4\n%%EOF\n")
    pic = host.command("lake.doc", {"tab": host.command("lake.open", {"kind": "file", "value": "docs/dot.png"})})
    assert pic["view"]["kind"] == "image" and base64.b64decode(pic["view"]["media"]["data"]) == png
    assert pic["view"]["media"]["type"] == "image/png" and not pic["view"]["editable"]
    pdf = host.command("lake.doc", {"tab": host.command("lake.open", {"kind": "file", "value": "docs/paper.pdf"})})
    assert pdf["view"]["kind"] == "pdf" and pdf["view"]["media"]["type"] == "application/pdf"
    page = host.command("lake.doc", {"tab": host.command("lake.open", {"kind": "text", "value": " https://example.com/x "})})
    assert page["view"]["kind"] == "web" and page["url"] == "https://example.com/x"      # never fetched: the page shows it
    note = host.command("lake.doc", {"tab": host.command("lake.open", {"kind": "text", "value": "# Plan\n\n- one",
                                                                        "title": "plan"})})
    assert note["view"]["kind"] == "markdown" and not note["view"]["editable"]
    json.dumps(host.snapshot())
    with pytest.raises(CommandError):
        host.command("lake.open", {"kind": "file", "value": "/etc/passwd"})            # the project's own files only
    with pytest.raises(CommandError):
        host.command("lake.open", {"kind": "file", "value": "docs/../../outside.md"})
    with pytest.raises(CommandError):
        host.command("lake.open", {"kind": "branch", "value": "main"})
    with pytest.raises(CommandError):
        host.command("lake.act", {"tab": "t1", "act": "rm"})


def test_an_old_scroll_s_lake_leaves_the_map_and_its_road_opens_in_lake(fake_repo, isolated_layout_file):
    """A Town Scroll from before: a Lake building with a road into it from Task Fields and one out of it."""
    from orkcraft import scroll
    from orkcraft.core.town import Town
    checkpoint.ensure(fake_repo)
    old = Town(fake_repo, auto_commit=False)
    src = buildings.raise_spec(old, buildings.type_spec(old, "fields")).id
    lake = buildings.raise_spec(old, buildings.type_spec(old, "lake")).id
    after = buildings.raise_spec(old, buildings.type_spec(old, "fields")).id
    scroll.subscribe(old.scroll, lake, src, "tasks.created")
    scroll.subscribe(old.scroll, after, lake, "lake.viewed")
    assert old.save()
    saved = json.loads(isolated_layout_file.read_text(encoding="utf-8"))
    assert not next(b for b in saved["buildings"] if b["id"] == lake).get("demolished")

    host = _host(fake_repo)                                          # the GUI opens the old scroll
    bs = host.town.scroll.building(lake)
    assert bs.demolished and lake not in {b["id"] for b in host.snapshot()["buildings"]}
    assert not bs.roads and not host.town.scroll.building(after).roads
    assert host.town.scroll.building(src).open_in_lake == ["tasks.created"]
    saved = json.loads(isolated_layout_file.read_text(encoding="utf-8"))   # kept so
    assert next(b for b in saved["buildings"] if b["id"] == lake).get("demolished")
    assert not any(r["to"] == lake or r["from"] == lake for r in host.snapshot()["roads"])

    host.town.emit_typed(src, "tasks.created", "# Ship it\n\n- today", "Ship it")
    tabs = host.snapshot()["lake"]["tabs"]
    assert [(t["title"], t["from"]) for t in tabs] == [("Ship it", src)]
    assert _host(fake_repo).town.scroll.building(lake).demolished          # and stays off the map


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
    a, b, c = _raised(host, "fields"), _raised(host, "fields"), _raised(host, "fields")
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


def test_the_elders_advise_in_quiet_hours_and_the_person_follows(fake_repo, monkeypatch):
    import json as _json
    import time
    from orkcraft import schedule, settings
    from orkcraft.core import runners
    from orkcraft.realm.orcs import Alert
    settings.save(settings.MachineSettings(onboarded=True, autonomy=0, quiet=schedule.DEFAULT_QUIET))
    monkeypatch.setattr(schedule, "quiet_now", lambda m, now=None: True)
    monkeypatch.setattr(runners, "ELDERS_RUNNER", lambda prompt, model=None: (_json.dumps({"answer": "1", "why": "runs the tests"}), 0.001))
    host = _host(fake_repo)
    alert = Alert(id="term:t1", title="Do you want to proceed?", context=["Bash command", "  pytest -q"],
                  options=[("1", "Yes"), ("3", "No, and tell Claude what to do differently (esc)")],
                  source="terminal", ref="t1")
    host.muster.rebuild = lambda *a, **k: host.muster.roster      # the question stays on the board
    host.muster.roster.alerts = [alert]
    sent = []
    host.sessions.write = lambda key, data: sent.append((key, data)) or True
    host._night()
    for _ in range(100):
        if host.night.advice_for(alert) is not None:
            break
        time.sleep(0.02)
    assert sent == []                                              # advice only: the person answers
    asked = next(a for a in host.snapshot()["alerts"] if a["id"] == "term:t1")
    assert asked["advice"] == {"key": "1", "why": "runs the tests", "warn": ""}
    assert host.command("orders.follow", {"id": "term:t1"})
    assert sent == [("t1", b"1")]


# -- changing the town (gui/builder.py) -----------------------------------------------------------

def test_a_building_is_raised_from_the_catalog_and_demolished(fake_repo, isolated_layout_file):
    host = _host(fake_repo)
    types = host.command("town.catalog")
    assert {"fields", "scrolls"} <= {t["id"] for t in types}
    assert not {"town_hall", "workshop", "custom", "lake"} & {t["id"] for t in types}   # never offered
    with pytest.raises(CommandError):
        host.command("town.build", {"type": "lake"})                               # the town's window
    named = host.command("town.build", {"type": "fields", "prompt": "What should I build? sort my inbox into tasks"})
    assert next(b for b in host.snapshot()["buildings"] if b["id"] == named)["title"] == "Sort inbox into tasks"
    bid = host.command("town.build", {"type": "fields"})
    assert bid in {b["id"] for b in host.snapshot()["buildings"]} and host.town.workers.get(bid) is not None
    assert bid in host.town.scroll.active_orkspace.buildings
    with pytest.raises(CommandError):
        host.command("town.build", {"type": "town_hall"})
    with pytest.raises(CommandError):
        host.command("town.demolish", {"id": "town_hall"})                         # it always stands
    assert host.command("town.demolish", {"id": bid})
    assert bid not in {b["id"] for b in host.snapshot()["buildings"]}
    assert host.town.scroll.building(bid).demolished
    saved = json.loads(isolated_layout_file.read_text(encoding="utf-8"))
    assert next(b for b in saved["buildings"] if b["id"] == bid).get("demolished")
    with pytest.raises(CommandError):
        host.command("town.demolish", {"id": bid})                                 # already down


def test_a_road_is_laid_from_its_choices_and_taken_up(fake_repo, isolated_layout_file):
    host = _host(fake_repo)
    src = host.command("town.build", {"type": "signpost"})
    dst = host.command("town.build", {"type": "fields"})
    host.town.custom_specs[src]["config"] = {"rules": ["view: *"]}
    choices = host.command("roads.choices", {"from": src, "to": dst})
    assert choices and all(c["label"] for c in choices)
    with pytest.raises(CommandError):
        host.command("roads.lay", {"from": src, "to": dst, "event": "tasks.created"})  # not one it may carry
    key = host.command("roads.lay", {"from": src, "to": dst, "event": choices[0]["event"],
                                     "handler": choices[0]["handler"]})
    assert key in {r["id"] for r in host.snapshot()["roads"]}
    saved = json.loads(isolated_layout_file.read_text(encoding="utf-8"))
    assert next(b for b in saved["buildings"] if b["id"] == dst)["roads"]
    assert host.command("roads.remove", {"key": key})
    assert key not in {r["id"] for r in host.snapshot()["roads"]}
    with pytest.raises(CommandError):
        host.command("roads.remove", {"key": key})


def test_a_type_registers_itself_by_its_files():
    """A worker, its GUI view and its page module are found by their names: porting a type touches
    no shared list (docs/design/gui-migration.md, "Porting a building type")."""
    from orkcraft.core import workers
    from orkcraft.gui import views
    found = workers.registry()
    assert {"lake", "fields", "scrolls"} <= set(found)
    for type_id in found:
        assert views.of(type_id) is not None, f"{type_id}: a worker without gui/views/{type_id}.py"
    for path in (srv.STATIC.parent / "views").glob("*.py"):
        if path.stem != "__init__":
            assert path.stem in found, f"gui/views/{path.name} without a worker"
            assert (srv.STATIC / "js" / "buildings" / f"{path.stem}.js").is_file(), f"no js/buildings/{path.stem}.js"
    assert views.of("no_such_type") is None and views.of("../server") is None


def test_the_gui_has_one_look_office(fake_repo):
    assert _host(fake_repo).snapshot()["look"] == "office"          # the phone still reads it (docs/design/mobile.md)
    from orkcraft import cli
    with pytest.raises(SystemExit):
        cli.main(["gui", "--look", "camp"])                         # no Camp to ask for


def test_the_console_info_of_a_building_and_its_orks(fake_repo, isolated_layout_file):
    """What the TUI's console says (screens/console/), as data: Info, the listens, the Inventory."""
    host = _host(fake_repo)
    host.tick()
    hall = host.command("info", {"id": "town_hall"})
    json.dumps(hall)
    assert hall["about"] and hall["goal"] == "balance" and hall["pinned"] is False
    assert {"runs", "ok", "failed", "results"} <= set(hall["week"])
    assert [q["id"] for q in hall["quick"]] == ["hall.build", "hall.audit"]       # Build in one, and Audit
    lead = next(o for o in host.muster.roster.garrison("town_hall") if o.lead)
    ork = host.command("info", {"id": "town_hall", "ork": lead.ref})
    json.dumps(ork)
    assert ork["name"] == lead.name and ork["lead"] and isinstance(ork["tools"], list)
    with pytest.raises(CommandError):
        host.command("ork.dismiss", {"id": "town_hall", "ork": lead.ref})      # a steward stays
    assert host.command("history", {"id": "town_hall"}) == {"events": [], "runs": []}


def test_a_pinned_building_keeps_its_place(fake_repo, isolated_layout_file):
    host = _host(fake_repo)
    pit = buildings.raise_spec(host.town, buildings.type_spec(host.town, "pit")).id
    assert host.command("building.pin", {"id": pit}) is True
    assert next(b for b in host.snapshot()["buildings"] if b["id"] == pit)["pinned"]
    with pytest.raises(CommandError):
        host.command("hut.move", {"id": pit, "x": 0.5, "y": 0.5})
    assert host.command("history", {"id": pit})["events"][0]["text"] == "pinned"
    assert host.command("building.pin", {"id": pit}) is False
    host.command("hut.move", {"id": pit, "x": 0.5, "y": 0.5})
    assert host.command("building.goal", {"id": "town_hall"}) == "quality"


def _wait(host, jid, states=("ready", "verdict", "failed")):
    import time
    for _ in range(100):
        job = host.console.jobs.get(jid)
        if job is None or job["state"] in states:
            return job
        time.sleep(0.05)
    raise AssertionError(f"job {jid} still {host.console.jobs[jid]['state']}")


def test_the_console_recruits_by_hand_and_sets_orders_and_model(fake_repo, isolated_layout_file):
    host = _host(fake_repo)
    ref = host.command("building.recruit", {"id": "town_hall", "name": "Coder", "role": "tickets", "tier": "laborer"})
    assert ref == "town_hall/coder"
    ork = host.command("info", {"id": "town_hall", "ork": ref})
    assert ork["uses_model"] and ork["steps"][0]["tier"] == "laborer" and ork["triggers"]
    host.command("ork.orders", {"id": "town_hall", "ork": ref, "orders": "watch T1",
                                "trigger": {"type": "cron", "expression": "*/15 * * * *"}})
    member = host.town.scroll.building("town_hall").garrison.orc("coder")
    assert member.orders == "watch T1" and member.trigger == {"type": "cron", "expression": "*/15 * * * *"}
    host.command("ork.model", {"id": "town_hall", "ork": ref, "steps": [{"harness": "claude", "tier": "elder"}]})
    assert host.command("info", {"id": "town_hall", "ork": ref})["steps"][0]["tier"] == "elder"
    with pytest.raises(CommandError):
        host.command("ork.orders", {"id": "town_hall", "ork": ref, "trigger": {"type": "whenever"}})
    host.command("ork.dismiss", {"id": "town_hall", "ork": ref})
    assert host.town.scroll.building("town_hall").garrison.orc("coder") is None


def test_the_recruiter_and_the_council_run_as_jobs(fake_repo, isolated_layout_file, monkeypatch):
    from orkcraft.core import runners
    good = {"name": "Crier", "role": "done digest", "kind": "chain", "why": "a template is enough",
            "chain": [{"op": "template", "md": "done {id}"}],
            "roads": [{"from": "loot", "event": "on_selection_change", "filter": {"node_status": ["done"]}}]}
    monkeypatch.setattr(runners, "RECRUIT_RUNNER", lambda prompt: (json.dumps(good), 0.05))
    monkeypatch.setattr(runners, "FASTPATH_RUNNER", None)
    host = _host(fake_repo)
    host.town.demo = True                            # the Council by its rules only
    jid = host.command("building.recruit_ask", {"id": "town_hall", "prompt": "show finished tasks"})
    assert host.snapshot()["jobs"][0]["id"] == jid
    job = _wait(host, jid)
    assert job["state"] == "ready" and job["view"]["name"] == "Crier" and job["view"]["roads"]
    host.command("job.accept", {"job": jid})
    job = _wait(host, jid)
    if job is not None and job["state"] == "verdict":       # notes only: the person hires anyway
        host.command("job.accept", {"job": jid})
    assert host.town.scroll.building("town_hall").garrison.handler("crier") is not None
    assert jid not in host.console.jobs
    key = next(r["key"] for r in host.command("info", {"id": "town_hall"})["listens"])
    assert host.command("road.handlers", {"key": key})["current"] == "crier"


def test_a_redesign_runs_as_a_job_and_its_layout_is_taken(fake_repo, isolated_layout_file, monkeypatch):
    from orkcraft.core import runners
    from orkcraft.design import ui
    host = _host(fake_repo)
    built = buildings.raise_spec(host.town, buildings.type_spec(host.town, "lake"))
    good = ui.default("lake")
    good["panes"][1]["size"] = 5
    monkeypatch.setattr(runners, "STEWARD_RUNNER",
                        lambda p: (json.dumps({"proposals": [{"type": "ui", "ui": good, "why": "a bigger page"}]}), 0.01))
    jid = host.command("building.redesign", {"id": built.id, "request": "a bigger page"})
    job = _wait(host, jid)
    assert job["state"] == "ready" and job["view"]["proposals"][0]["ready"]
    host.command("job.accept", {"job": jid, "index": 0})
    assert host.town.scroll.building(built.id).ui == good
    assert host.command("building.redesign", {"id": built.id, "request": "default"}) is None
    with pytest.raises(CommandError):
        host.command("ork.report", {"id": built.id})            # not watched yet


def test_a_type_draws_its_closed_card_from_its_view(fake_repo, isolated_layout_file):
    """docs/design/building-views.md §4: `card(worker)` goes in every snapshot; a type with a page says so."""
    host = _host(fake_repo)
    built = buildings.raise_spec(host.town, buildings.type_spec(host.town, "fields"))
    host.town.worker(built.id)
    snap = host.snapshot()
    fields = next(b for b in snap["buildings"] if b["id"] == built.id)
    assert fields["page"] and fields["card"]["error"] == "" and fields["card"]["lanes"]
    assert {"label", "count", "new"} <= set(fields["card"]["lanes"][0])
    hall = next(b for b in snap["buildings"] if b["id"] == "town_hall")
    assert hall["page"] and hall["card"] == {"news": [], "warchief": "Warchief"}     # nothing happens: Build, Ask


def test_lake_open_and_keeper_ask_are_there_for_every_type(fake_repo, isolated_layout_file):
    host = _host(fake_repo)
    with pytest.raises(CommandError):                 # nothing to open
        host.command("lake.open", {"kind": "file", "value": ""})
    tab = host.command("lake.open", {"kind": "file", "value": "README.md", "title": "readme"})
    assert [t["id"] for t in host.snapshot()["lake"]["tabs"]] == [tab]          # no Lake building needed
    with pytest.raises(CommandError):                 # the Town Hall keeps no settings (tests/test_keeper.py)
        host.command("keeper.ask", {"id": "town_hall", "request": "route bugs to the Forge"})


def test_the_town_hall_is_the_town_s_way_in(fake_repo, isolated_layout_file, monkeypatch):
    """docs/design/building-views.md §3: closed — Build and Ask me anything, or what happens; command —
    the Warchief's chat, the sessions, the audit, spend and quotas; full — Hall, Sessions, Limits."""
    import time

    from orkcraft.core import runners

    monkeypatch.setattr(runners, "WARCHIEF_RUNNER", lambda prompt: ("Raise a **Task Fields**.\nBUILD: fields", 0.0))
    host = _host(fake_repo)
    hall = next(b for b in host.snapshot()["buildings"] if b["id"] == "town_hall")
    assert hall["page"] and hall["has_worker"] and hall["card"]["news"] == []
    d = host.detail("town_hall")
    json.dumps(d)
    data = d["data"]
    assert data["warchief"] == "Warchief" and data["chat"] == [] and data["thinking"] is False
    assert {"agents", "audit", "proposals", "elders", "reviews", "board"} <= set(data["hall"])
    assert data["spend"]["level"] == "ok" and isinstance(data["limits"], list)
    with pytest.raises(CommandError):
        host.command("act", {"id": "town_hall", "act": "ask", "args": {"text": "  "}})
    host.command("act", {"id": "town_hall", "act": "ask", "args": {"text": "Where do my tasks go?"}})
    for _ in range(300):
        chat = host.detail("town_hall")["data"]["chat"]
        if len(chat) == 2:
            break
        time.sleep(0.01)
    you, chief = chat
    assert you["text"] == "Where do my tasks go?" and "<strong>Task Fields</strong>" in chief["html"]
    card = chief["card"]
    assert card["kind"] == "build" and card["type_title"] == "Task Fields" and "BUILD" not in chief["html"]
    assert card["state"] in ("ready", "done")                                # done at once when the town is unchained
    if card["state"] == "ready":
        host.command("act", {"id": "town_hall", "act": "card", "args": {"card": card["id"], "choice": "build"}})
    card = host.detail("town_hall")["data"]["chat"][-1]["card"]
    assert card["state"] == "done" and card["made"] == ["Task Fields"]
    host.command("act", {"id": "town_hall", "act": "card", "args": {"card": card["id"], "choice": "undo"}})
    with pytest.raises(CommandError):                                        # once undone, nothing more to do
        host.command("act", {"id": "town_hall", "act": "card", "args": {"card": card["id"], "choice": "undo"}})
    summary = host.command("act", {"id": "town_hall", "act": "audit"})
    assert "Warder" in summary and host.detail("town_hall")["data"]["hall"]["audit"]["ts"]
    host.command("act", {"id": "town_hall", "act": "limits"})
    for _ in range(300):
        if host.detail("town_hall")["data"]["limits"]:
            break
        time.sleep(0.01)
    assert "disabled" in host.detail("town_hall")["data"]["limits"][0]["error"]     # ORKCRAFT_LIMITS=0
    host.command("act", {"id": "town_hall", "act": "forget"})
    assert host.detail("town_hall")["data"]["chat"] == []
    types = host.command("town.catalog")
    assert types[0]["intent"].startswith("Take in") and all(t["intent"] for t in types)



def test_the_town_hall_limits_show_codex_beside_claude_and_agy(fake_repo, isolated_layout_file, codex_limits):
    """⏳ Limits in the GUI: a Codex row per window, with its plan; an API-key Codex says so in one row."""
    import time

    def read() -> list[dict]:
        host.command("act", {"id": "town_hall", "act": "limits"})
        for _ in range(300):
            data = host.detail("town_hall")["data"]
            if not data["reading_limits"] and data["limits"]:
                return data["limits"]
            time.sleep(0.01)
        raise AssertionError("the limits were never read")

    codex_limits()
    host = _host(fake_repo)
    limits = read()
    assert [x["provider"] for x in limits] == ["claude", "agy", "codex", "codex", "codex"]
    five, week, astra = limits[2:]
    assert (five["what"], five["remaining"], five["note"], five["error"]) == ("5h", 0.62, "plus · credits 120", "")
    assert week["what"] == "weekly" and astra["what"] == "gpt-6-astra 5h"
    assert "codex 10% left" in host.town.worker("town_hall").lowest()
    codex_limits(billing="api")
    codex = [x for x in read() if x["provider"] == "codex"]
    assert codex == [{"provider": "codex", "what": "", "remaining": None, "error": "API key — no plan windows",
                      "note": "", "reset": ""}]

def test_a_tally_crag_charts_busy_orks_and_quotas_through_the_host(fake_repo, isolated_layout_file, monkeypatch):
    """core/workers/crag.py `probe`: the GUI host hands it the roster's busy orks, every Barracks'
    working orks and the quotas the Town Hall read, as the TUI's view does."""
    from types import SimpleNamespace

    from orkcraft.realm import metrics
    from orkcraft.realm.roster import Roster
    from orkcraft.sources.limits import Limit

    host = _host(fake_repo)
    bid = host.command("town.build", {"type": "crag"})
    host.tick()
    w = host.town.worker(bid)
    assert w.probe is not None
    monkeypatch.setattr(Roster, "active", property(lambda self: 2))
    barracks = SimpleNamespace(TYPE="barracks", state=SimpleNamespace(
        orcs=[SimpleNamespace(status="working"), SimpleNamespace(status="idle")]))
    monkeypatch.setitem(host.town.workers, "barracks_x", barracks)
    host.town.worker("town_hall").limits = [Limit("claude", "", "5h session", 0.25, None),
                                            Limit("agy", "pro", "weekly", None, None, "no answer")]
    assert w.probe() == {"orcs": 3, "limits": [("claude 5h session", 75.0)]}
    w.save_config({"charts": [metrics.chart_line(metrics.Chart("orcs", orientation="horizontal")),
                              metrics.chart_line(metrics.Chart("limits", orientation="horizontal"))]})
    w.tick()
    orcs, limits = host.detail(bid)["data"]["charts"]
    assert orcs["source"] == "orcs" and orcs["now"] == 3
    assert limits["source"] == "limits" and ["claude 5h session", 75.0] in limits["parts"]


def test_the_task_board_card_counts_the_note_folders_too(fake_repo, isolated_layout_file):
    """Closed: the status lanes' counters, then the note folders with theirs (building-views.md §3)."""
    host = _host(fake_repo)
    built = buildings.raise_spec(host.town, buildings.type_spec(host.town, "fields"))
    w = host.town.worker(built.id)
    w.add("Should we drop IE?", "notes")
    card = next(b for b in host.snapshot()["buildings"] if b["id"] == built.id)["card"]
    assert [l["label"] for l in card["lanes"]][:3] == ["To Do", "In Progress", "Done"]
    assert any(n["count"] == 1 for n in card["notes"])


def test_the_hud_quota_shows_what_the_town_hall_read(fake_repo, isolated_layout_file):
    """The HUD's quota is the used share of each subscription's tightest window the Town Hall read,
    not a dash, as the TUI's `_quota_text`."""
    from orkcraft.sources.limits import Limit

    host = _host(fake_repo)
    for t, c in host.town.machine.tools.items():
        c.enabled, c.billing = t in ("claude", "agy"), "subscription"
    host.town.worker("town_hall").limits = [Limit("claude", "", "5h session", 0.25, None),
                                            Limit("claude", "", "weekly", 0.6, None),
                                            Limit("agy", "pro", "weekly", None, None, "no answer")]
    assert host.snapshot()["hud"]["quota"] == "claude 75% · agy —"


def test_the_hud_counts_working_agents_of_all_the_keepers_too(fake_repo, isolated_layout_file):
    """Agents: the orks at work of every ork in the town; a new building's keeper counts at once."""
    host = _host(fake_repo)
    host.tick()
    before = host.snapshot()["hud"]
    host.command("town.build", {"type": "crag"})
    host.tick()
    after = host.snapshot()["hud"]
    assert after["agents"] == before["agents"] + 1
    assert after["agents_working"] == 0
