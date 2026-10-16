"""Spec 26: five buildings are offered at the first start; the others stay hidden but keep working where they stand."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from orkcraft import scroll as ts
from orkcraft import settings
from orkcraft.core.workers import town_hall
from orkcraft.gui import builder
from orkcraft.realm import catalog, intents, town_builder

FIVE = {"fields", "barracks", "loot", "watchtower", "scrolls"}
HIDDEN_OFF = catalog.SYSTEM_TYPES | catalog.SCRATCH_TYPES | catalog.RETIRED_TYPES


def _allow_all(monkeypatch) -> None:
    file = settings.path()
    file.write_text(json.dumps({"catalog.all_types": True}), encoding="utf-8")


def test_build_dialog_lists_the_five_and_the_landscape():
    ids = {t["id"] for t in builder.catalog_types()}
    assert ids == FIVE | (catalog.LANDSCAPE - HIDDEN_OFF)


def test_workchief_planner_lists_the_five_and_the_landscape():
    assert {t.id for t in town_hall.buildable()} == FIVE | (catalog.LANDSCAPE - HIDDEN_OFF)
    assert {t.id for t in town_builder.offered_types()} == FIVE | (catalog.LANDSCAPE - HIDDEN_OFF)


def test_every_punk_ork_preset_raises_only_offered_types_and_no_dangling_road():
    for it in intents.INTENTS:
        plan = intents.offered_plan(it.plan)
        keys = {b["key"] for b in plan["buildings"]}
        every = {b["key"] for b in it.plan["buildings"]}
        assert all(catalog.offered(b["type"], {}) for b in plan["buildings"]), it.id
        assert all(r[e] in keys or r[e] not in every for r in plan["roads"] for e in ("from", "to")), it.id
    # and some preset really lost a building, or the filter proves nothing
    assert any(len(intents.offered_plan(i.plan)["buildings"]) < len(i.plan["buildings"]) for i in intents.INTENTS)


def test_all_types_setting_brings_everything_back(monkeypatch):
    before_dialog = {t["id"] for t in builder.catalog_types()}
    _allow_all(monkeypatch)
    all_ids = {t["id"] for t in builder.catalog_types()}
    assert before_dialog < all_ids
    assert all_ids == {t.id for t in catalog.TYPES.values() if t.id not in HIDDEN_OFF | {catalog.DEFAULT_TYPE}
                       and t.id != "lake"}
    assert {t.id for t in town_hall.buildable()} == {t.id for t in catalog.TYPES.values() if t.id not in
                                                      catalog.SYSTEM_TYPES | catalog.SCRATCH_TYPES | catalog.RETIRED_TYPES}
    for it in intents.INTENTS:
        assert intents.offered_plan(it.plan) == it.plan


def test_nested_all_types_setting_also_counts():
    assert catalog.offered("lab", {"catalog": {"all_types": True}})
    assert not catalog.offered("lab", {"catalog": {"all_types": "yes"}})
    assert not catalog.offered("council", {})
    assert catalog.offered("tasks", {})     # an old id is its camp building


def test_scroll_with_a_lab_and_a_council_loads_and_keeps_them(tmp_path: Path):
    presets = {"lab": {"title": "Test bench", "icon": "🧪", "orc": "Mechanic", "role": "x", "category": "core"},
               "council": {"title": "Review board", "icon": "🪔", "orc": "Elder", "role": "x", "category": "core"}}
    scroll = ts.default_scroll(presets, raised=["lab", "council"])
    path = tmp_path / ".orkcraft.json"
    assert ts.save(path, scroll) == []
    loaded, problems = ts.load(path, presets)
    assert problems == []
    assert loaded.building("lab") is not None and not loaded.building("lab").demolished
    assert loaded.building("council") is not None and not loaded.building("council").demolished
