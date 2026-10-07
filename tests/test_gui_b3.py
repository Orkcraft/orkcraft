"""Task Fields, File Forest and Scroll Dump three ways in the GUI (docs/design/building-views.md §3):
the closed card, what the Command Card and the full window draw, and their acts."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from orkcraft.core import buildings
from orkcraft.gui.host import CommandError, Host
from orkcraft.realm import checkpoint
from orkcraft import scroll as ts


def _host(repo: Path) -> Host:
    checkpoint.ensure(repo)
    return Host(repo, auto_commit=False)


def _raised(host: Host, type_id: str, **config) -> str:
    spec = buildings.type_spec(host.town, type_id)
    if config:
        spec["config"] = {**(spec.get("config") or {}), **config}
    built = buildings.raise_spec(host.town, spec)
    assert built is not None
    host.town.worker(built.id)                         # as the host does for a building it raised
    return built.id


def _card(host: Host, bid: str):
    host.tick()
    snap = host.snapshot()
    json.dumps(snap)
    return next(b for b in snap["buildings"] if b["id"] == bid)["card"]


def test_task_fields_adds_a_folder_of_notes_that_stays_on_the_board(fake_repo):
    host = _host(fake_repo)
    bid = _raised(host, "fields")
    assert host.command("act", {"id": bid, "act": "add_lane", "args": {"name": " For  the sync "}}) == "for-the-sync"
    lanes = host.detail(bid)["data"]["lanes"]
    assert [(ln["id"], ln["label"], ln["kind"]) for ln in lanes][-1] == ("for-the-sync", "For the sync", "note")
    assert "## For the sync" in (fake_repo / "TASKS.md").read_text(encoding="utf-8")
    host.town.worker(bid).refresh()                    # read again from the file: the empty lane is still there
    assert any(ln["id"] == "for-the-sync" for ln in host.detail(bid)["data"]["lanes"])
    # a card dragged onto the folded lane (the Command Card) moves there
    card = host.command("act", {"id": bid, "act": "add", "args": {"lane": "todo", "title": "Agenda"}})
    assert host.command("act", {"id": bid, "act": "move", "args": {"card": card, "lane": "for-the-sync"}})
    sync = next(ln for ln in host.detail(bid)["data"]["lanes"] if ln["id"] == "for-the-sync")
    assert [c["title"] for c in sync["cards"]] == ["Agenda"]
    assert host.command("act", {"id": bid, "act": "add_lane", "args": {"name": "Done"}}) == ""   # a status lane's name
    with pytest.raises(CommandError):
        host.command("act", {"id": bid, "act": "add_lane", "args": {"name": "  "}})


def test_task_fields_folder_board_gets_a_folder(fake_repo):
    (fake_repo / "tasks").mkdir()
    host = _host(fake_repo)
    bid = _raised(host, "fields", path="tasks")
    assert host.command("act", {"id": bid, "act": "add_lane", "args": {"name": "Ideas"}}) == "ideas"
    assert (fake_repo / "tasks" / "ideas").is_dir()
    assert any(ln["id"] == "ideas" for ln in host.detail(bid)["data"]["lanes"])


def test_file_forest_closed_command_and_full(fake_repo):
    (fake_repo / "src" / "logo.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 32)
    host = _host(fake_repo)
    bid = _raised(host, "forest", path="src")
    ts.subscribe(host.town.scroll, "town_hall", bid, "files.selected")
    assert _card(host, bid) == {"folder": "./src", "changed": 1, "picked": "", "error": "", "files": ["logo.png"]}   # logo.png is new
    data = host.detail(bid)["data"]
    assert data["folder"] == "./src" and data["changed"] == 1
    assert data["changes"] == [{"path": "src/logo.png", "name": "logo.png", "status": "??"}]   # listed over the tree
    rows = {r["name"]: r for r in data["top"]}
    assert rows["app.py"]["status"] == "" and rows["logo.png"]["status"] == "??" and rows["logo.png"]["media"] == "image"
    # a click picks the target, Send sends it down its roads
    sent = []
    host.town.roads.emit = lambda payload, meta=None: sent.append(payload) or []
    assert host.command("act", {"id": bid, "act": "pick", "args": {"path": "src/app.py"}}) == "src/app.py"
    assert not sent and _card(host, bid)["picked"] == "app.py"
    host.command("act", {"id": bid, "act": "send"})
    assert [(p.mode, p.value) for p in sent] == [("files.selected", "src/app.py")]
    # folders open in place; nothing outside its folder
    (fake_repo / "src" / "lib").mkdir()
    (fake_repo / "src" / "lib" / "util.py").write_text("x = 1\n")
    host.town.worker(bid).refresh()
    lib = next(r for r in host.detail(bid)["data"]["top"] if r["name"] == "lib")
    assert lib["dir"] and lib["status"] == "M"
    assert [r["path"] for r in host.command("act", {"id": bid, "act": "list", "args": {"path": "src/lib"}})] == ["src/lib/util.py"]
    for act, args in (("list", {"path": "docs"}), ("pick", {"path": "README.md"}), ("thumb", {"path": "../x.png"})):
        with pytest.raises(CommandError):
            host.command("act", {"id": bid, "act": act, "args": args})
    assert host.command("act", {"id": bid, "act": "thumb", "args": {"path": "src/logo.png"}}).startswith("data:image/png;base64,")
    assert host.command("act", {"id": bid, "act": "thumb", "args": {"path": "src/app.py"}}) == ""


def test_file_forest_opens_its_folder_in_the_os(fake_repo, monkeypatch):
    from orkcraft.core.workers.forest import ForestWorker
    opened = []
    monkeypatch.setattr(ForestWorker, "opener", staticmethod(opened.append))
    host = _host(fake_repo)
    bid = _raised(host, "forest", path="src")
    host.command("act", {"id": bid, "act": "open"})
    assert opened[0][-1] == str((fake_repo / "src").resolve())


def test_scroll_dump_closed_is_pages_and_pending_and_command_the_last_pages(fake_repo):
    host = _host(fake_repo)
    bid = _raised(host, "scrolls", paths=["docs"], auto_ingest=False)
    host.tick(now=1e9)
    card = _card(host, bid)
    assert set(card) == {"pages", "pending", "running", "error", "lent", "last", "discuss"} and card["lent"] is None and card["last"] is None and card["pages"] == 0 and card["pending"] >= 1
    root = fake_repo / "llm-wiki" / "general" / "pages"
    root.mkdir(parents=True)
    (root / "old.md").write_text("# Old\n")
    (root / "new.md").write_text("# New\n")
    import os
    os.utime(root / "old.md", (1_000_000, 1_000_000))
    host.town.worker(bid).refresh()
    recent = host.detail(bid)["data"]["recent"]
    assert [p["title"] for p in recent][:2] == ["New", "Old"] and recent[0]["path"].endswith("pages/new.md")
    assert _card(host, bid)["pages"] == 2


def _written(host: Host, bid: str, lane: str, title: str, wait: float = 5.0):
    import time
    end = time.monotonic() + wait
    while time.monotonic() < end:
        cards = next((ln["cards"] for ln in host.detail(bid)["data"]["lanes"] if ln["id"] == lane), [])
        found = next((c for c in cards if c["title"] == title), None)
        if found:
            return found
        time.sleep(0.02)
    raise AssertionError(f"no card {title!r} in {lane}")


def test_task_fields_card_is_written_as_one_text_and_a_light_model_names_it(fake_repo, monkeypatch):
    from orkcraft.core import runners
    asked = []
    monkeypatch.setattr(runners, "FASTPATH_RUNNER", lambda prompt: (asked.append(prompt), ('"Fix the login."', 0.001))[1])
    host = _host(fake_repo)
    bid = _raised(host, "fields")
    # a short line is its own title: no model
    card = host.command("act", {"id": bid, "act": "add", "args": {"lane": "todo", "text": " Ship  it "}})
    assert card and not asked and _written(host, bid, "todo", "Ship it")["body"] == ""
    # a longer text is the card's text; the model names it, the card shows up once named
    long = "the login page hangs on submit\nwhen the password has a quote in it"
    assert host.command("act", {"id": bid, "act": "add", "args": {"lane": "todo", "text": long}}) == ""
    named = _written(host, bid, "todo", "Fix the login")
    assert named["body"] == long and len(asked) == 1 and long in asked[0]
    # an edit keeps the title and changes its text; a title-only card's short line renames it
    host.command("act", {"id": bid, "act": "edit", "args": {"card": named["id"], "text": "only the quote"}})
    assert _written(host, bid, "todo", "Fix the login")["body"] == "only the quote"
    host.command("act", {"id": bid, "act": "edit", "args": {"card": card, "text": "Ship it today"}})
    assert _written(host, bid, "todo", "Ship it today")["body"] == ""
    with pytest.raises(CommandError):
        host.command("act", {"id": bid, "act": "add", "args": {"lane": "todo", "text": "   "}})


def test_task_fields_card_without_a_model_is_named_by_its_first_words(fake_repo, monkeypatch):
    from orkcraft.core import runners

    def down(prompt):
        raise RuntimeError("no model")
    monkeypatch.setattr(runners, "FASTPATH_RUNNER", down)
    host = _host(fake_repo)
    bid = _raised(host, "fields")
    lane = "ideas"                                     # a lane of notes: its first note makes it
    host.command("act", {"id": bid, "act": "add", "args": {"lane": lane, "text": "maybe cache the triage per ticket, it repeats"}})
    note = _written(host, bid, lane, "Maybe cache the triage")
    assert note["kind"] == "note" and note["body"].startswith("maybe cache")
