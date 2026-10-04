"""Town Scroll: schema, defaults, v1 / v2 migration, validation, chronicles (roads: test_roads.py)."""
from __future__ import annotations

import json
from pathlib import Path

from orkcraft import scroll as ts

PRESETS = {
    "farm": {"title": "Farm / Burrow", "icon": "🛖", "orc": "Peon", "role": "inbox", "category": "core"},
    "forge": {"title": "Forge", "icon": "⚒️", "orc": "Smith", "role": "kanban", "category": "core"},
    "scrying": {"title": "Scrying Spire", "icon": "🔮", "orc": "Shaman", "role": "preview", "category": "core"},
    "limits": {"title": "Treasury (Limits)", "icon": "🏛️", "orc": "Treasurer", "role": "quota", "category": "migrated"},
}

SPEC_V2 = {  # §11 of the Orkcraft v0.2 spec (a v2 scroll)
    "$schema": "https://orkcraft.dev/schemas/town-scroll.v2.json", "version": "0.2.0",
    "meta": {"project_name": "orkcraft", "tagline": "Work vs Humans", "updated_at": "2026-09-29T10:15:00Z"},
    "budget": {"gold_session_limit_usd": 20.0, "lumber_context_limit_tokens": 131072, "supply_max_workers": 5},
    "active_orkspace_id": "feat_auth",
    "orkspaces": [
        {"id": "main_camp", "name": "Main Camp", "icon": "🏰", "hotkey": "F1", "biome": "forest",
         "git": {"enabled": True, "mode": "root", "path": "./", "branch": "main"}, "buildings": []},
        {"id": "feat_auth", "name": "Auth Core", "icon": "⛺", "hotkey": "F2", "biome": "void",
         "git": {"enabled": True, "mode": "worktree", "path": "./.orkcraft/worktrees/feat-auth",
                 "branch": "feat/oauth-provider"},
         "buildings": ["forge_kanban", "scrying_preview"]},
        {"id": "scratch_lab", "name": "Scratch Lab", "icon": "🧊", "hotkey": "F3", "biome": "ice",
         "git": {"enabled": False}, "buildings": []},
    ],
    "buildings": [
        {"id": "forge_kanban", "preset_ref": "core:forge", "title": "Forge", "icon": "⚒️", "pinned": True,
         "bounds": {"x": 2, "y": 2, "width": 78, "height": 18}, "min_size": {"cols": 50, "rows": 12},
         "rally_point": {"target_building_id": "scrying_preview", "pipe_mode": "on_task_completed",
                         "transform": "render_diff"},
         "chronicles": {"enabled": True, "log_file": ".orkcraft/history/buildings/forge.events.jsonl"},
         "actions": [{"key": "N", "label": "➕ New Task Card", "action": "forge:create_card"},
                     {"key": "L", "label": "📜 Building Chronicles", "action": "core:open_chronicles"}],
         "garrison": {"lead_orc_id": "smith", "members": [
             {"id": "smith", "name": "Smith", "role": "Lead Architect", "avatar": "🧌", "status": "busy",
              "trigger": {"type": "on_demand"}},
             {"id": "coder_1", "name": "Coder-1", "role": "Worker", "status": "busy",
              "trigger": {"type": "event", "source": "forge:task_ready"}},
             {"id": "tester", "name": "Tester", "role": "QA Engineer", "status": "alert",
              "trigger": {"type": "webhook", "endpoint": "localhost:9099/ci"}},
         ]}},
        {"id": "scrying_preview", "preset_ref": "core:scrying_spire", "title": "Scrying Spire", "icon": "🔮",
         "pinned": False, "bounds": {"x": 82, "y": 2, "width": 70, "height": 18},
         "min_size": {"cols": 40, "rows": 10}, "chronicles": {"enabled": False},
         "actions": [{"key": "W", "label": "Toggle Wrap", "action": "spire:toggle_wrap"}],
         "garrison": {"lead_orc_id": "shaman", "members": [
             {"id": "shaman", "name": "Shaman", "role": "Diff Inspector", "avatar": "🧌", "status": "idle",
              "trigger": {"type": "pipe"}}]}},
    ],
}


def _copy(data: dict) -> dict:
    return json.loads(json.dumps(data))


def test_v2_spec_example_migrates_without_losses_and_roundtrips():
    assert ts.validate_v2(SPEC_V2) == []
    data = ts.migrate_v2(SPEC_V2)
    assert data["version"] == ts.VERSION and ts.validate(data) == []
    scroll = ts.TownScroll.from_dict(data)
    assert scroll.active_orkspace.name == "Auth Core"
    forge = scroll.building("forge_kanban")
    # the lead becomes the steward, the other members agent handlers without roads
    assert forge.garrison.steward.name == "Smith" and forge.garrison.lead.name == "Smith"
    assert [m.id for m in forge.garrison.handlers] == ["coder_1", "tester"]
    tester = forge.garrison.handler("tester")
    assert (tester.role, tester.status, tester.trigger) == \
        ("QA Engineer", "alert", {"type": "webhook", "endpoint": "localhost:9099/ci"})
    assert tester.kind == "agent" and tester.harness == ts.DEFAULT_HARNESS
    assert len(forge.garrison.members) == 3 and not forge.roads
    # the rally point becomes a plain road held by its target
    spire = scroll.building("scrying_preview")
    [road] = spire.roads
    assert (road.source, road.event, road.handler, road.transform) == \
        ("forge_kanban", "on_task_completed", None, "render_diff")
    rp = scroll.rally_of("forge_kanban")
    assert (rp.target_building_id, rp.pipe_mode) == ("scrying_preview", "on_task_completed")
    assert forge.actions == SPEC_V2["buildings"][0]["actions"] and forge.min_size == {"cols": 50, "rows": 12}
    assert [b.id for b in scroll.buildings_in("feat_auth")] == ["forge_kanban", "scrying_preview"]
    assert scroll.orkspace_of("scrying_preview").biome == "void"
    again = scroll.to_dict()
    assert ts.validate(again) == []
    assert ts.TownScroll.from_dict(again).to_dict()["buildings"] == again["buildings"]


def test_v2_file_is_migrated_on_load(tmp_path: Path):
    path = tmp_path / ".orkcraft.json"
    path.write_text(json.dumps(SPEC_V2), encoding="utf-8")
    scroll, problems = ts.load(path, PRESETS)
    assert problems == ["migrated .orkcraft.json (v2) to Town Scroll v3: rally points are now roads"]
    assert scroll.building("scrying_preview").roads[0].source == "forge_kanban"
    assert ts.save(path, scroll) == []
    again, problems = ts.load(path, PRESETS)
    assert problems == [] and json.loads(path.read_text())["version"] == "0.3.0"


def test_invalid_v2_is_set_aside_not_migrated(tmp_path: Path):
    bad = _copy(SPEC_V2)
    bad["buildings"][0]["rally_point"]["target_building_id"] = "ghost"
    path = tmp_path / ".orkcraft.json"
    path.write_text(json.dumps(bad), encoding="utf-8")
    scroll, problems = ts.load(path, PRESETS)
    assert "rally target 'ghost'" in problems[0] and "kept the unreadable scroll" in problems[-1]
    assert scroll.building("forge") is not None   # the default scroll


def test_cross_references_are_checked():
    bad = _copy(SPEC_V2)
    bad["active_orkspace_id"] = "nowhere"
    bad["orkspaces"][0]["buildings"] = ["forge_kanban"]  # also in feat_auth
    bad["buildings"][0]["rally_point"]["target_building_id"] = "ghost"
    bad["buildings"][1]["garrison"]["lead_orc_id"] = "nobody"
    problems = "\n".join(ts.validate_v2(bad))
    assert "not an orkspace" in problems
    assert "in two orkspaces" in problems
    assert "rally target 'ghost'" in problems
    assert "lead ork 'nobody'" in problems

    schema_bad = ts.migrate_v2(SPEC_V2)
    schema_bad["orkspaces"][2]["biome"] = "desert"
    assert any("biome" in p for p in ts.validate(schema_bad))
    v3_bad = ts.migrate_v2(SPEC_V2)
    v3_bad["active_orkspace_id"] = "nowhere"
    assert any("not an orkspace" in p for p in ts.validate(v3_bad))


def test_default_scroll_is_valid_and_saves(tmp_path: Path):
    scroll = ts.default_scroll(PRESETS, raised=["forge", "scrying"])
    assert ts.validate(scroll.to_dict()) == []
    assert scroll.building("farm").demolished and not scroll.building("forge").demolished
    assert scroll.building("limits").preset_ref == "legacy:limits"
    assert scroll.building("forge").garrison.lead.name == "Smith"
    path = tmp_path / ".orkcraft.json"
    assert ts.save(path, scroll) == []
    loaded, problems = ts.load(path, PRESETS)
    assert problems == [] and loaded.to_dict()["buildings"] == scroll.to_dict()["buildings"]


def test_save_refuses_an_invalid_scroll(tmp_path: Path):
    scroll = ts.default_scroll(PRESETS)
    scroll.orkspaces[0].biome = "lava"
    path = tmp_path / ".orkcraft.json"
    assert ts.save(path, scroll) and not path.exists()


def test_v1_layout_migrates_without_losses(tmp_path: Path):
    legacy = tmp_path / ".orcraft.json"
    legacy.write_text(json.dumps({
        "version": 1,
        "windows": {
            "forge": {"x": 10, "y": 0, "w": 60, "h": 40, "frac": None, "hidden": False, "pinned": True,
                      "unit": {"trigger": {"type": "cron", "expression": "*/15 * * * *"}, "context": "watch T1001"}},
            "farm": {"x": 0, "y": 0, "w": 30, "h": 10, "frac": [0.0, 0.0, 0.5, 0.5], "hidden": True, "pinned": False},
        },
        "order": ["farm", "forge"], "active": "forge", "preview_linked": False,
    }), encoding="utf-8")
    scroll, problems = ts.load(tmp_path / ".orkcraft.json", PRESETS, legacy=[legacy])
    assert problems == ["migrated .orcraft.json (v1) to Town Scroll v3"]
    forge = scroll.building("forge")
    assert forge.pinned and forge.bounds == {"x": 10, "y": 0, "width": 60, "height": 40}
    assert forge.garrison.lead.trigger == {"type": "cron", "expression": "*/15 * * * *"}
    assert forge.garrison.lead.orders == "watch T1001"
    assert scroll.building("farm").demolished and scroll.building("farm").frac == [0.0, 0.0, 0.5, 0.5]
    assert scroll.building("scrying").demolished  # not in the v1 file
    camp = scroll.active_orkspace
    assert camp.window_order == ["farm", "forge"] and camp.active_building == "forge"
    assert scroll.preferences["preview_linked"] is False
    assert ts.validate(scroll.to_dict()) == []


def test_unreadable_scroll_is_set_aside_not_overwritten(tmp_path: Path):
    path = tmp_path / ".orkcraft.json"
    path.write_text("{ not json", encoding="utf-8")
    scroll, problems = ts.load(path, PRESETS)
    assert scroll.orkspaces[0].id == "main_camp"
    assert any("invalid-" in p for p in problems)
    assert path.read_text(encoding="utf-8") == "{ not json"
    assert list(tmp_path.glob(".orkcraft.json.invalid-*"))


def test_building_chronicles_append_and_read(tmp_path: Path):
    ts.append_event(tmp_path, "forge", {"type": "card_moved", "id": "T1001", "to": "done", "by": "operator"})
    ts.append_event(tmp_path, "forge", {"type": "alert", "orc": "tester"})
    with ts.events_file(tmp_path, "forge").open("a", encoding="utf-8") as f:
        f.write("garbage\n")
    events = ts.read_events(tmp_path, "forge")
    assert [e["type"] for e in events] == ["card_moved", "alert"]
    assert events[0]["building"] == "forge" and "ts" in events[0]


def test_registry_presets_build_a_valid_default():
    from orkcraft.realm.buildings import presets, registry

    scroll = ts.default_scroll(presets(registry()))
    assert ts.validate(scroll.to_dict()) == []
    assert scroll.building("town_hall").preset_ref == "core:town_hall"
    assert scroll.building("loot").preset_ref == "core:loot"


def test_ensure_presets_adds_new_registry_buildings_demolished():
    scroll = ts.default_scroll({k: v for k, v in PRESETS.items() if k != "limits"})
    assert ts.ensure_presets(scroll, PRESETS) == ["limits"]
    assert scroll.building("limits").demolished is True
    assert "limits" in scroll.orkspaces[0].buildings
    assert ts.ensure_presets(scroll, PRESETS) == []
    assert ts.validate(scroll.to_dict()) == []


def test_new_orkspace_gets_unique_id_and_free_hotkey():
    scroll = ts.default_scroll(PRESETS)
    a = ts.new_orkspace(scroll, "Auth Core", "void")
    b = ts.new_orkspace(scroll, "Auth Core", "ice")
    c = ts.new_orkspace(scroll, "  Лаборатория ", "forest")
    assert (a.id, a.hotkey, a.buildings) == ("auth_core", "F2", [])
    assert (b.id, b.hotkey) == ("auth_core_2", "F3")
    assert c.id == "camp" and c.hotkey == "F4"
    assert ts.orkspace_by_hotkey(scroll, "f3") is b
    assert ts.validate(scroll.to_dict()) == []
    for bad in (("", "forest"), ("X", "desert")):
        try:
            ts.new_orkspace(scroll, *bad)
        except ValueError:
            pass
        else:
            raise AssertionError(f"{bad} accepted")
    for i in range(4):
        ts.new_orkspace(scroll, f"camp {i}")
    assert len(scroll.orkspaces) == ts.MAX_ORKSPACES
    try:
        ts.new_orkspace(scroll, "ninth")
    except ValueError:
        pass
    else:
        raise AssertionError("a ninth orkspace was accepted")


def test_move_building_keeps_one_home_and_raises_it():
    scroll = ts.default_scroll(PRESETS)
    camp = scroll.orkspaces[0]
    camp.window_order, camp.active_building = ["farm", "forge"], "forge"
    scroll.building("forge").demolished = True
    lab = ts.new_orkspace(scroll, "Lab", "ice")
    ts.move_building(scroll, "forge", lab.id)
    assert "forge" not in camp.buildings and "forge" not in camp.window_order
    assert camp.active_building is None
    assert lab.buildings == ["forge"] and scroll.building("forge").demolished is False
    assert scroll.orkspace_of("forge") is lab
    assert ts.validate(scroll.to_dict()) == []


def test_remove_orkspace_only_when_empty_and_not_last():
    scroll = ts.default_scroll(PRESETS)
    main = scroll.orkspaces[0]
    for doomed in (main.id, "nope"):
        try:
            ts.remove_orkspace(scroll, doomed)
        except ValueError:
            pass
        else:
            raise AssertionError(f"removed {doomed}")
    lab = ts.new_orkspace(scroll, "Lab")
    scroll.active_orkspace_id = lab.id
    ts.move_building(scroll, "farm", lab.id)
    try:
        ts.remove_orkspace(scroll, lab.id)
    except ValueError:
        pass
    else:
        raise AssertionError("removed an orkspace with buildings")
    ts.move_building(scroll, "farm", main.id)
    ts.remove_orkspace(scroll, lab.id)
    assert [o.id for o in scroll.orkspaces] == [main.id] and scroll.active_orkspace_id == main.id


def test_v1_biome_and_solid_black_migrate():
    v1 = {"version": 1, "windows": {"forge": {"x": 0, "y": 0, "w": 40, "h": 12}},
          "biome": "ice", "terrain_solid_black": True}
    scroll = ts.migrate_v1(v1, PRESETS)
    assert scroll.orkspaces[0].biome == "ice"
    assert scroll.preferences["terrain_solid_black"] is True
    assert ts.validate(scroll.to_dict()) == []


def test_garrison_recruit_dismiss_and_lead():
    scroll = ts.default_scroll(PRESETS)
    forge = scroll.building("forge")
    assert forge.garrison.lead.name == "Smith"
    coder = ts.recruit(scroll, "forge", "Coder", role="implements tickets", orders="take T1001")
    coder2 = ts.recruit(scroll, "forge", "Coder", trigger={"type": "cron", "expression": "0 5 * * *"})
    assert (coder.id, coder2.id) == ("coder", "coder_2")
    assert coder2.trigger == {"type": "cron", "expression": "0 5 * * *"}
    assert [m.name for m in forge.garrison.members] == ["Smith", "Coder", "Coder"]
    assert ts.validate(scroll.to_dict()) == []
    for bad in (("nope", "X"), ("forge", "  ")):
        try:
            ts.recruit(scroll, *bad)
        except ValueError:
            pass
        else:
            raise AssertionError(f"recruited {bad}")
    try:
        ts.dismiss_orc(scroll, "forge", "smith")
    except ValueError:
        pass
    else:
        raise AssertionError("dismissed the lead")
    ts.set_lead(scroll, "forge", "coder")
    assert forge.garrison.lead is coder
    ts.dismiss_orc(scroll, "forge", "smith")
    assert [m.id for m in forge.garrison.members] == ["coder", "coder_2"]
    assert ts.validate(scroll.to_dict()) == []


def test_garrison_is_capped_and_duplicate_ids_are_invalid():
    scroll = ts.default_scroll(PRESETS)
    for i in range(ts.MAX_GARRISON - 1):
        ts.recruit(scroll, "farm", f"Peon {i}")
    try:
        ts.recruit(scroll, "farm", "one too many")
    except ValueError:
        pass
    else:
        raise AssertionError("garrison over the cap")
    data = scroll.to_dict()
    farm = next(b for b in data["buildings"] if b["id"] == "farm")
    farm["garrison"]["handlers"].append(dict(farm["garrison"]["handlers"][0]))
    assert any("duplicate ork ids" in p for p in ts.validate(data))


def test_add_custom_building_places_it_in_the_active_orkspace():
    scroll = ts.default_scroll(PRESETS)
    lab = ts.new_orkspace(scroll, "Lab", "ice")
    scroll.active_orkspace_id = lab.id
    spec = {"id": "ci_watch", "title": "CI Watch", "icon": "🛠", "orc": {"name": "Tinker", "role": "build log"}}
    b = ts.add_custom_building(scroll, spec)
    assert b.preset_ref == "custom:ci_watch" and b.preset_id == "ci_watch"
    assert scroll.orkspace_of("ci_watch") is lab
    assert b.garrison.lead.name == "Tinker" and b.garrison.lead.role == "build log"
    assert ts.validate(scroll.to_dict()) == []
    try:
        ts.add_custom_building(scroll, spec)
    except ValueError:
        pass
    else:
        raise AssertionError("added the same building twice")
