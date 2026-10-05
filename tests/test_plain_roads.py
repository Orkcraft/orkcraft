"""Plain roads: a road with no ork at its end goes into any type that takes a cart (catalog.TAKES),
for the events whose payload it acts on (catalog.ACCEPTS) — offered in the GUI's and the TUI's road
dialog alike (core/roads.py `choices`), and delivered to the receiver's worker."""
from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from orkcraft.core import buildings, roads
from orkcraft.gui.host import Host
from orkcraft.realm import catalog, checkpoint, pipes


def _host(repo: Path) -> Host:
    checkpoint.ensure(repo)
    return Host(repo, auto_commit=False)


def _raised(host: Host, type_id: str, **config) -> str:
    spec = buildings.type_spec(host.town, type_id)
    if config:
        spec["config"] = {**(spec.get("config") or {}), **config}
    built = buildings.raise_spec(host.town, spec)
    assert built is not None
    return built.id


def _wait(cond, seconds: float = 10.0) -> None:
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if cond():
            return
        time.sleep(0.02)
    raise AssertionError("never happened")


def _plain(host: Host, src: str, dst: str) -> set[str]:
    return {c["event"] for c in host.command("roads.choices", {"from": src, "to": dst}) if c["handler"] is None}


def test_every_type_that_takes_a_cart_says_what_it_takes():
    assert set(catalog.ACCEPTS) == set(catalog.TAKES)
    assert all(kinds and kinds <= {catalog.TEXT, catalog.FILE, catalog.NODE} for kinds in catalog.ACCEPTS.values())
    assert catalog.accepts({"type": "pit"}) == frozenset() and catalog.accepts(None) == frozenset()
    assert catalog.accepts({"type": "mill"}) == {catalog.TEXT, catalog.FILE}


def test_a_typed_receiver_takes_by_its_kinds():
    try:
        pipes.clear_typed()
        pipes.set_typed("in", ["pit.text", "drop.file"])
        assert pipes.modes_for("in", "post") == [] and not pipes.can_receive("post")
        pipes.set_typed("post", ["signpost.routed"], catalog.accepts({"type": "signpost"}))
        pipes.set_typed("crag", [], catalog.accepts({"type": "crag"}))
        assert pipes.can_receive("post") and pipes.can_receive("crag")
        assert {"pit.text", "drop.file"} <= set(pipes.road_events("in", "post", has_garrison=False))
        assert pipes.road_events("in", "crag", has_garrison=False) == ["pit.text"]     # a number in a text only
        pipes.set_typed("post", ["signpost.routed"])                                    # a redesign takes it away
        assert pipes.modes_for("in", "post") == []
    finally:
        pipes.clear_typed()


TAKERS = ("signpost", "mill", "loot", "catapult", "horn", "barracks", "council", "fields")   # Workshop: the Builder's


@pytest.mark.parametrize("type_id", TAKERS)
def test_the_pit_lays_a_plain_road_into_a_type_that_takes_carts(fake_repo, isolated_layout_file, type_id):
    host = _host(fake_repo)
    pit = _raised(host, "pit")
    dst = _raised(host, type_id)
    plain = _plain(host, pit, dst)
    assert "pit.text" in plain and "pit.link" in plain
    assert ("drop.file" in plain) == (catalog.FILE in catalog.ACCEPTS[type_id])
    assert all(c["label"] for c in host.command("roads.choices", {"from": pit, "to": dst}))
    assert {ev for ev, h, _ in roads.choices(host.town, pit, dst) if h is None} == plain       # the TUI's dialog
    key = host.command("roads.lay", {"from": pit, "to": dst, "event": "pit.text", "handler": None})
    road = next(r for r in host.snapshot()["roads"] if r["id"] == key)
    assert not road.get("handler")
    saved = json.loads(isolated_layout_file.read_text(encoding="utf-8"))
    assert next(b for b in saved["buildings"] if b["id"] == dst)["roads"]


def test_no_plain_road_into_what_takes_nothing(fake_repo, isolated_layout_file):
    host = _host(fake_repo)
    pit, other = _raised(host, "pit"), _raised(host, "pit")
    assert _plain(host, pit, other) == set()
    forge = _raised(host, "forge")
    plain = _plain(host, pit, forge)
    assert {"pit.text", "pit.link"} <= plain and "drop.file" not in plain           # a branch is named in text


def test_a_plain_road_delivers_into_the_signpost_and_on(fake_repo, isolated_layout_file):
    host = _host(fake_repo)
    pit = _raised(host, "pit")
    post = _raised(host, "signpost", rules=["bugs: contains bug", "rest: else"])
    fields = _raised(host, "fields")
    host.command("roads.lay", {"from": pit, "to": post, "event": "pit.text", "handler": None})
    routes = {c["event"] for c in host.command("roads.choices", {"from": post, "to": fields})}
    assert "signpost.routed#bugs" in routes
    host.command("roads.lay", {"from": post, "to": fields, "event": "signpost.routed#bugs", "handler": None})
    assert host.town.emit_typed(pit, "pit.text", "a bug in the login", "login bug")
    signpost = host.town.worker(post)
    _wait(lambda: signpost.log_file.is_file() and "bugs" in signpost.log_file.read_text(encoding="utf-8"))
    board = host.town.worker(fields)
    _wait(lambda: any("bug" in c.title.lower() for c in board.cards))


def test_a_plain_road_delivers_a_dropped_file_into_the_mill(fake_repo, isolated_layout_file):
    host = _host(fake_repo)
    pit = _raised(host, "pit")
    mill = _raised(host, "mill", steps=["lines", "grep: note", "join"])
    host.command("roads.lay", {"from": pit, "to": mill, "event": "drop.file", "handler": None})
    assert host.town.emit_typed(pit, "drop.file", "docs/notes.md", "notes.md")
    worker = host.town.worker(mill)
    _wait(lambda: bool(worker.runs) and worker.runs[0].outcome in ("done", "error"))
    assert worker.runs[0].ok and "first note" in worker.runs[0].result
