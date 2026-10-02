"""Town Scroll v3 contract: roads, handlers, the steward and their rules (T1098 stage 1)."""
from __future__ import annotations

import pytest

from orkcraft import scroll as ts

PRESETS = {
    "forge": {"title": "Forge", "icon": "⚒️", "orc": "Smith", "role": "kanban", "category": "core"},
    "loot": {"title": "Loot Chest", "icon": "📦", "orc": "Quartermaster", "role": "files", "category": "core"},
    "scrying": {"title": "Scrying Spire", "icon": "🔮", "orc": "Shaman", "role": "preview", "category": "core"},
    "town_hall": {"title": "War Tent", "icon": "💬", "orc": "Peon", "role": "sessions", "category": "core"},
}
CHAIN = [{"op": "filter", "field": "status", "cmp": "eq", "value": "done"},
         {"op": "pick", "fields": ["id", "title"]},
         {"op": "template", "md": "- {id} {title}"}]


def fresh() -> ts.TownScroll:
    return ts.default_scroll(PRESETS)


def valid(scroll: ts.TownScroll) -> None:
    assert ts.validate(scroll.to_dict()) == []


def test_steward_is_the_resident_and_handlers_start_empty():
    scroll = fresh()
    forge = scroll.building("forge")
    assert forge.garrison.steward.name == "Smith" and forge.garrison.handlers == []
    assert forge.garrison.members == [forge.garrison.steward] and forge.garrison.lead_orc_id == "smith"
    data = scroll.to_dict()
    assert next(b for b in data["buildings"] if b["id"] == "forge")["garrison"] == {
        "steward": {"id": "smith", "name": "Smith", "role": "kanban", "avatar": "🧌", "status": "idle",
                    "trigger": {"type": "on_demand"}, "orders": "", "kind": "agent",
                    "harness": [{"role": "run", "harness": "claude"}]},
        "handlers": []}
    valid(scroll)


def test_subscribe_a_chain_handler_to_two_roads_and_roundtrip():
    scroll = fresh()
    scribe = ts.add_handler(scroll, "scrying", "Scribe", kind="chain", chain=CHAIN, why="a template is enough")
    assert scribe.avatar == "🗿" and scribe.harness == [] and scribe.run_policy == {"quiet_s": 0, "restart_on_new": True}
    r1 = ts.subscribe(scroll, "scrying", "forge", "on_task_completed", {"outcome": ["halted"]}, handler="scribe")
    r2 = ts.subscribe(scroll, "scrying", "loot", "on_selection_change", {"path_prefix": ["loot/"]}, handler="scribe")
    assert (r1.id, r2.id) == ("forge-task", "loot-selection")
    spire = scroll.building("scrying")
    assert [r.id for r in spire.roads_of("scribe")] == ["forge-task", "loot-selection"]
    assert [(t.id, r.id) for t, r in ts.outgoing(scroll, "forge")] == [("scrying", "forge-task")]
    assert ts.incoming(scroll, "scrying") == spire.roads
    assert scroll.rally_of("forge") is None          # a road with a handler is not a plain rally
    valid(scroll)
    again = ts.TownScroll.from_dict(scroll.to_dict())
    assert again.to_dict()["buildings"] == scroll.to_dict()["buildings"]
    assert again.building("scrying").garrison.handler("scribe").chain == CHAIN


def test_subscribe_refuses_bad_roads():
    scroll = fresh()
    ts.add_handler(scroll, "scrying", "Seer")
    ts.subscribe(scroll, "scrying", "forge", "on_task_completed")
    bad = [
        (("scrying", "scrying"), {}, "own building"),
        (("scrying", "ghost"), {}, "unknown building"),
        (("scrying", "forge", "telepathy"), {}, "unknown road event"),
        (("scrying", "forge"), {"handler": "smith"}, "no handler"),        # the steward handles no roads
        (("scrying", "forge"), {"handler": "shaman"}, "no handler"),
        (("scrying", "forge", "on_task_completed"), {}, "already has this road"),
        (("scrying", "forge"), {"filter": {"match": "("}}, "bad regex"),
        (("scrying", "forge"), {"filter": {"colour": "red"}}, "filter"),
        (("forge", "scrying"), {}, "loop"),                                 # scrying ← forge exists
    ]
    for args, kw, needle in bad:
        with pytest.raises(ValueError, match=needle):
            ts.subscribe(scroll, *args, **kw)
    # the same source and event with another filter or handler is a different road
    ts.subscribe(scroll, "scrying", "forge", "on_task_completed", {"outcome": ["done"]})
    ts.subscribe(scroll, "scrying", "forge", "on_task_completed", handler="seer")
    assert len(scroll.building("scrying").roads) == 3
    valid(scroll)


def test_loops_through_several_buildings_are_refused():
    scroll = fresh()
    ts.subscribe(scroll, "loot", "forge", "on_task_completed")
    ts.subscribe(scroll, "scrying", "loot", "on_selection_change")
    with pytest.raises(ValueError, match="loop"):
        ts.subscribe(scroll, "forge", "scrying", "on_task_completed")
    data = scroll.to_dict()
    forge = next(b for b in data["buildings"] if b["id"] == "forge")
    forge["roads"] = [{"id": "back", "from": "scrying", "event": "on_task_completed", "handler": None}]
    assert any("loop" in p for p in ts.validate(data))


def test_validate_checks_road_references():
    data = fresh().to_dict()
    spire = next(b for b in data["buildings"] if b["id"] == "scrying")
    spire["roads"] = [
        {"id": "a", "from": "ghost", "event": "on_selection_change", "handler": None},
        {"id": "b", "from": "scrying", "event": "on_selection_change", "handler": None},
        {"id": "c", "from": "forge", "event": "on_selection_change", "handler": "shaman"},
        {"id": "c", "from": "loot", "event": "on_selection_change", "handler": None},
    ]
    problems = "\n".join(ts.validate(data))
    assert "source 'ghost' does not exist" in problems
    assert "cannot come from its own building" in problems
    assert "handler 'shaman' is not a handler of scrying" in problems
    assert "duplicate road ids c" in problems


def test_kind_rules():
    scroll = fresh()
    cases = [
        ({"kind": "chain"}, "a chain needs at least one op"),
        ({"kind": "script"}, "a script needs a script"),
        ({"kind": "hybrid", "script": {"path": ".orkcraft/scripts/smith.py"}, "harness": []}, "needs a harness"),
        ({"kind": "agent", "harness": []}, "needs a harness"),
        ({"kind": "agent", "chain": CHAIN}, "only a chain has chain ops"),
        ({"kind": "chain", "chain": [{"op": "eval", "code": "1"}]}, "chain"),
        ({"kind": "chain", "chain": [{"op": "extract", "field": "title", "regex": "[", "as": "x"}]}, "bad regex"),
        ({"kind": "script", "script": {"path": "../../etc/passwd.py"}}, "script"),
        ({"harness": [{"role": "write", "harness": "gpt"}]}, "harness"),
        ({"harness": [{"role": "run", "harness": "pipeline:../x.json"}]}, "harness"),
        ({"kind": "wizard"}, "kind"),
    ]
    for kw, needle in cases:
        with pytest.raises(ValueError, match=needle):
            ts.add_handler(scroll, "forge", "Bad", **kw)
    assert scroll.building("forge").garrison.handlers == []   # nothing half-added


def test_script_and_hybrid_handlers_start_as_drafts():
    scroll = fresh()
    tally = ts.add_handler(scroll, "forge", "Tally", kind="script", script={"path": ".orkcraft/scripts/tally.py"})
    assert tally.status == "draft" and tally.avatar == "🗿" and tally.harness == []
    scheme = [{"role": "write", "harness": "agy"}, {"role": "review", "harness": "claude"}]
    warden = ts.add_handler(scroll, "forge", "Warden", kind="hybrid", harness=scheme,
                            script={"path": ".orkcraft/scripts/warden.py", "sha256": "0" * 64, "reviewed": True})
    assert warden.status == "idle" and warden.avatar == "🗿🧌" and warden.uses_model
    assert warden.run_policy == {"quiet_s": 30, "restart_on_new": True}
    studio = ts.add_handler(scroll, "forge", "Studio",
                            harness=[{"role": "run", "harness": "pipeline:product-studio/pipelines/sprint.json"}],
                            run={"quiet_s": 5})
    assert studio.run_policy == {"quiet_s": 5, "restart_on_new": True}
    valid(scroll)


def test_remove_handler_keeps_its_roads_as_plain_roads():
    scroll = fresh()
    ts.add_handler(scroll, "scrying", "Scribe", kind="chain", chain=CHAIN)
    ts.subscribe(scroll, "scrying", "forge", "on_task_completed", handler="scribe")
    assert ts.remove_handler(scroll, "scrying", "scribe") == ["forge-task"]
    road = scroll.building("scrying").roads[0]
    assert road.plain and scroll.rally_of("forge").target_building_id == "scrying"
    with pytest.raises(ValueError, match="steward"):
        ts.remove_handler(scroll, "scrying", "shaman")
    valid(scroll)


def test_set_steward_swaps_and_refuses_an_orc_on_roads():
    scroll = fresh()
    ts.add_handler(scroll, "forge", "Coder")
    ts.add_handler(scroll, "forge", "Scribe", kind="chain", chain=CHAIN)
    ts.subscribe(scroll, "forge", "loot", "on_selection_change", handler="scribe")
    with pytest.raises(ValueError, match="works on roads"):
        ts.set_steward(scroll, "forge", "scribe")
    ts.set_steward(scroll, "forge", "coder")
    g = scroll.building("forge").garrison
    assert g.steward.id == "coder" and [m.id for m in g.handlers] == ["smith", "scribe"]
    valid(scroll)


def test_update_orc_is_all_or_nothing():
    scroll = fresh()
    ts.update_orc(scroll, "forge", "smith", orders="watch T1001",
                  harness=[{"role": "write", "harness": "agy"}, {"role": "review", "harness": "claude"}])
    smith = scroll.building("forge").garrison.steward
    assert smith.orders == "watch T1001" and len(smith.harness) == 2
    with pytest.raises(ValueError, match="a chain needs"):
        ts.update_orc(scroll, "forge", "smith", kind="chain", orders="lost")
    assert smith.kind == "agent" and smith.orders == "watch T1001"
    with pytest.raises(ValueError, match="cannot change"):
        ts.update_orc(scroll, "forge", "smith", id="other")
    valid(scroll)


def test_road_handler_and_filter_can_change():
    scroll = fresh()
    ts.add_handler(scroll, "scrying", "Seer")
    road = ts.subscribe(scroll, "scrying", "forge", "on_task_completed")
    ts.set_road_handler(scroll, "scrying", road.id, "seer")
    ts.set_road_filter(scroll, "scrying", road.id, {"node_type": ["task"], "exclude_personal": True})
    assert road.handler == "seer" and road.filter["exclude_personal"] is True
    with pytest.raises(ValueError):
        ts.set_road_filter(scroll, "scrying", road.id, {"node_type": ["person"]})
    with pytest.raises(ValueError):
        ts.set_road_handler(scroll, "scrying", road.id, "shaman")
    ts.set_road_handler(scroll, "scrying", road.id, None)
    assert road.plain
    ts.unsubscribe(scroll, "scrying", road.id)
    assert scroll.building("scrying").roads == []
    valid(scroll)


def test_rally_compat_replaces_only_plain_roads():
    scroll = fresh()
    ts.add_handler(scroll, "loot", "Keeper", kind="chain", chain=CHAIN)
    ts.subscribe(scroll, "loot", "forge", "on_task_completed", handler="keeper")
    ts.set_rally_point(scroll, "forge", "scrying")
    ts.set_rally_point(scroll, "forge", "scrying", "on_task_completed")
    assert sorted((t.id, r.event, r.handler or "") for t, r in ts.outgoing(scroll, "forge")) == [
        ("loot", "on_task_completed", "keeper"), ("scrying", "on_task_completed", "")]
    assert ts.clear_rally_point(scroll, "forge") is True
    assert [(t.id, r.handler) for t, r in ts.outgoing(scroll, "forge")] == [("loot", "keeper")]
    valid(scroll)


def test_preferences_have_road_and_cart_modes():
    scroll = fresh()
    assert scroll.preferences["carts"] == "selected" and scroll.preferences["roads"] == "faint"
    scroll.preferences["carts"] = "everywhere"
    assert any("carts" in p for p in ts.validate(scroll.to_dict()))


def test_events_a_road_can_carry():
    from orkcraft.realm import pipes
    assert pipes.emits("forge") == ["on_selection_change", "on_task_completed"]
    assert pipes.emits("scrying") == ["on_task_completed"] and pipes.emits("scrying", False) == []
    assert pipes.road_events("forge", "scrying") == ["on_selection_change", "on_task_completed"]
    assert pipes.road_events("forge", "farm") == []                        # the farm shows nothing …
    assert pipes.road_events("forge", "farm", handler=True) == ["on_selection_change", "on_task_completed"]
    assert pipes.road_events("forge", "forge", handler=True) == []
    scroll = fresh()
    r = ts.subscribe(scroll, "scrying", "forge", "on_task_completed")
    assert ts.find_road(scroll, r.id) == (scroll.building("scrying"), r)
    assert ts.find_road(scroll, r.id, "loot") is None
