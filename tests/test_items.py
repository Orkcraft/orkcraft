"""Items the person places in the camp (docs/design/v3-prompts.md §14, realm/items.py): item files, the starter set,
what earns the rest (Mission 1, a lean week and month, a portrait stage, a building at III), and placements kept in
the town file."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from orkcraft import scroll as ts
from orkcraft import settings
from orkcraft.realm import growth, items, mission
from orkcraft.scroll import BuildingSpec, Orkspace, TownScroll

RULES = ("start", "mission", "lean_week", "lean_month", "stage", "level")


def _town(*kinds: str) -> TownScroll:
    buildings = [BuildingSpec(k, f"core:{k}", k.title()) for k in ("town_hall", *kinds)]
    return TownScroll("main", [Orkspace("main", "Main", buildings=[b.id for b in buildings])], buildings)


def _machine(role: str = "eng_manager", stage: int = 1) -> settings.MachineSettings:
    m = settings.MachineSettings()
    m.profile, m.growth = {"role": role}, {"stage": stage, "deeds": {}}
    return m


def test_every_item_is_a_file_with_a_sprite_and_each_way_to_earn_one_has_items():
    cat = items.catalog()
    files = sorted(p.stem for p in items.DIR.glob("*.json"))
    assert sorted(cat) == files                                    # every file reads, its sprite found
    assert {i.by for i in cat.values()} == set(RULES)
    starter = {i.id for i in cat.values() if i.by == "start"}
    assert {"tree", "pine", "rock", "rocks", "bush", "logpile"} <= starter      # g2 decor, from day one
    assert {i.kin for i in cat.values() if i.by == "stage"} == set(growth.STAGE_NAMES)   # a class item per kin
    for i in cat.values():
        assert all(i.size) and json.loads((items.DIR / f"{i.id}.json").read_text())["why"]


def test_a_new_town_has_the_starter_set_and_nothing_earned(tmp_path: Path):
    town = _town()
    assert items.settle(town, tmp_path, _machine(), facts={}) == []
    inv = items.inventory(town, tmp_path)
    assert inv and all(r["start"] and r["left"] is None for r in inv)


def test_mission_one_a_lean_week_and_month_a_stage_and_a_building_at_three_earn_items_once(tmp_path: Path):
    town = _town("loot", "forge")
    machine = _machine("eng_manager", stage=1)
    mission.save(tmp_path, {"on": False, "finished": True})
    facts = growth.read_facts(tmp_path, __import__("datetime").datetime.now())
    assert items.settle(town, tmp_path, machine, facts) == ["first-cart"]
    assert items.settle(town, tmp_path, machine, facts) == []                  # once
    got = items.settle(town, tmp_path, machine, {"chapters": 1, "lean": True, "lean_weeks": 4})
    assert sorted(got) == ["lean-month", "lean-week"]
    machine.growth["stage"] = 2
    assert items.settle(town, tmp_path, machine, {}) == ["class-lich"]          # the person's class's item
    town.building("loot").level = 3
    town.building("forge").level = 3
    assert sorted(items.settle(town, tmp_path, machine, {})) == ["level3-loot", "pennant"]
    first = next(r for r in items.inventory(town, tmp_path) if r["id"] == "first-cart")
    assert first["why"].startswith("Earned: Mission 1 finished, ") and first["left"] == 1


def test_mission_ones_own_record_counts_too(tmp_path: Path):
    """The M1 session may call it when the mission ends; earning it again later does nothing."""
    assert items.earn(tmp_path, "first-cart", "Mission 1 finished") is True
    assert items.earn(tmp_path, "first-cart") is False and items.earn(tmp_path, "tree") is False
    assert set(items.earned(tmp_path)) == {"first-cart"}


def test_placed_items_are_kept_in_the_town_file_and_an_earned_one_stands_once(tmp_path: Path):
    town = _town()
    a = items.place(town, tmp_path, "tree", "main", 3, -2)
    items.place(town, tmp_path, "tree", "main", 5, -2)                       # the starter set: as often as liked
    with pytest.raises(ValueError):
        items.place(town, tmp_path, "first-cart", "main", 1, 1)              # not earned yet
    items.earn(tmp_path, "first-cart")
    cart = items.place(town, tmp_path, "first-cart", "main", 1, 1)
    with pytest.raises(ValueError):
        items.place(town, tmp_path, "first-cart", "main", 2, 1)              # earned once, stands once
    assert next(r for r in items.inventory(town, tmp_path) if r["id"] == "first-cart")["left"] == 0
    with pytest.raises(ValueError):
        items.place(town, tmp_path, "tree", "nowhere", 1, 1)
    items.move(town, a["id"], 4, -1)
    path = tmp_path / ".orkcraft.json"
    ts.save(path, town)
    again, problems = ts.load(path, {})
    assert not problems
    assert [(p["item"], p["x"], p["y"]) for p in again.items] == [("tree", 4, -1), ("tree", 5, -2), ("first-cart", 1, 1)]
    items.remove(again, cart["id"])                                           # back to the inventory
    assert items.place(again, tmp_path, "first-cart", "main", 2, 2)["item"] == "first-cart"
