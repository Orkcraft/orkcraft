"""The Improve buildings (docs/design/improve-buildings.md): a type whose roads only its setup lays, or none at all,
and the UX bench — which building's look it works on, the AI tool that paints, the pictures it shows."""
from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest

from orkcraft.core import buildings, roads
from orkcraft.gui.host import CommandError, Host
from orkcraft.realm import catalog, checkpoint, lexicon


def _host(repo: Path) -> Host:
    checkpoint.ensure(repo)
    return Host(repo, auto_commit=False)


def _raised(host: Host, type_id: str) -> str:
    built = buildings.raise_spec(host.town, buildings.type_spec(host.town, type_id))
    assert built is not None
    host.refresh_roster()
    return built.id


def _act(host: Host, bid: str, name: str, **args):
    return host.command("act", {"id": bid, "act": name, "args": args})


def test_who_lays_a_types_roads():
    assert catalog.TYPES["ux_lab"].roads == "none" and catalog.TYPES["pit"].roads == "free"
    assert {t.roads for t in catalog.TYPES.values()} <= set(catalog.ROAD_RULES)
    assert catalog.lays_roads("pit") and not catalog.lays_roads("ux_lab") and not catalog.lays_roads("ux_lab", setup=True)
    assert catalog.lays_roads("nope")                                    # an unknown type keeps the old way


def test_the_ux_bench_lays_no_road_and_takes_none(fake_repo, isolated_layout_file):
    host = _host(fake_repo)
    pit, bench = _raised(host, "pit"), _raised(host, "ux_lab")
    assert roads.choices(host.town, pit, bench) == [] and roads.choices(host.town, bench, pit) == []
    assert roads.listenable(host.town, pit, bench) == []
    assert host.command("roads.choices", {"from": pit, "to": bench}) == []
    with pytest.raises(CommandError):
        host.command("roads.lay", {"from": pit, "to": bench, "event": "pit.text", "handler": None})
    assert roads.lay(host.town, bench, pit, "pit.text", None, setup=True) is None
    assert not host.town.scroll.building(bench).roads
    snap = {b["id"]: b for b in host.snapshot()["buildings"]}
    assert snap[bench]["roads"] == "none" and snap[pit]["roads"] == "free"
    assert "roads: none" in catalog.catalog_text([catalog.TYPES["ux_lab"]])


def test_a_setup_only_type_takes_a_road_from_its_setup_alone(fake_repo, isolated_layout_file, monkeypatch):
    monkeypatch.setitem(catalog.TYPES, "loot", dataclasses.replace(catalog.TYPES["loot"], roads="setup"))
    host = _host(fake_repo)
    pit, gate = _raised(host, "pit"), _raised(host, "loot")
    assert roads.choices(host.town, pit, gate) == []
    assert "pit.text" in {ev for ev, h, _ in roads.choices(host.town, pit, gate, setup=True) if h is None}
    assert roads.lay(host.town, gate, pit, "pit.text", None) is None
    assert roads.lay(host.town, gate, pit, "pit.text", None, setup=True) is not None
    assert "only its own setup" in catalog.catalog_text([catalog.TYPES["loot"]])


def test_the_ux_bench_picks_a_building_and_its_image_tool(fake_repo, isolated_layout_file):
    host = _host(fake_repo)
    bench = _raised(host, "ux_lab")
    d = host.detail(bench)["data"]
    assert d["target"] == "" and d["image_tool"] == "agy" and d["tools"][0]["id"] == "agy"
    _act(host, bench, "pick", type="barracks")
    d = host.detail(bench)["data"]
    assert d["target"] == "barracks" and d["title"] == "Barracks" and "dirt" in d["biomes"] and "ice" in d["biomes"]
    card = next(b for b in host.snapshot()["buildings"] if b["id"] == bench)["card"]
    assert card["target"] == "barracks" and card["pictures"] == 2 + len(d["biomes"])
    for bad in ({"type": "ux_lab"}, {"type": "nope"}):
        with pytest.raises(CommandError):
            _act(host, bench, "pick", **bad)
    with pytest.raises(CommandError):
        _act(host, bench, "tool", tool="no-such-tool")
    _act(host, bench, "tool", tool="claude")
    assert host.detail(bench)["data"]["image_tool"] == "claude"


def test_the_improve_buildings_are_named_by_what_they_do():
    assert lexicon.words("Alchemy Tower") == "UX bench" and lexicon.words("Alchemist") == "Designer"
    assert lexicon.words("Mechanic") == "Test bench" and lexicon.words("Alchemist's Lab") == "Test bench"
