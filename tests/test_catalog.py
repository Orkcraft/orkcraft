"""Building types (T1105 stage 1): the catalog, typed specs, their checks, typed events on roads."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from orkcraft import scroll as ts
from orkcraft.realm import catalog, masonry, pipes
from orkcraft.realm.huts import ART


def test_catalog_is_complete_and_consistent():
    want = {"pit", "watchtower", "signpost", "mill", "fields", "barracks", "council", "war_drum", "forest", "scrolls",
            "lake", "forge", "loot", "crag", "catapult", "horn"}          # the camp of T1107, and the Horn
    assert set(catalog.TYPES) == want | {"town_hall", "custom", "workshop"} and catalog.DEFAULT_TYPE in catalog.TYPES
    seen: set[str] = set()
    for t in catalog.TYPES.values():
        assert t.size in catalog.SIZES and t.art in ART and t.summary and t.preview and t.full
        for e in t.events:
            assert catalog.EVENT_ID.match(e.id) and e.id.split(".")[0] and e.kind in ("text", "file", "node")
            assert e.id not in seen, e.id          # an event id belongs to one type
            seen.add(e.id)
        assert all(catalog.EVENT_ID.match(a.id) and len(a.glyph) == 1 for a in t.actions)
    assert catalog.all_event_ids() == seen
    w, h = catalog.SIZES["L"]
    assert w <= 30 and h <= 12                      # fits a 200×44 town several times


def test_defaults_come_from_the_type():
    spec = {"type": "calendar"}
    assert catalog.size_of(spec) == catalog.SIZES["L"]
    assert catalog.events_of(spec) == ["calendar.event_due", "calendar.event_added", "calendar.event_removed",
                                       "calendar.day_schedule", "calendar.event_upcoming", "calendar.doc_opened"]
    assert [a.id for a in catalog.quick_actions_of(spec)] == ["calendar.new", "calendar.prepare"]
    picked = {"type": "calendar", "size": "M", "events": ["calendar.day_schedule"], "quick_actions": []}
    assert catalog.size_of(picked) == catalog.SIZES["M"] and catalog.events_of(picked) == ["calendar.day_schedule"]
    assert catalog.quick_actions_of(picked) == []
    assert catalog.type_of({}).id == "custom" and catalog.events_of({}) == []


def _mail(**kw) -> dict:
    return {"id": "inbox", "title": "Inbox", "icon": "📨", "orc": {"name": "Raven"}, "type": "mail",
            "config": {"host": "imap.example.com", "user_env": "MAIL_USER", "password_env": "MAIL_PASS"}, **kw}


def test_typed_spec_needs_no_panes_and_is_checked(fake_repo: Path):
    assert masonry.validate_spec(_mail(), fake_repo) == []
    assert masonry.validate_spec(_mail(events=["mail.received"], quick_actions=["mail.refresh"], size="S"), fake_repo) == []
    schema = " | ".join(masonry.validate_spec(_mail(quick_actions=["mail.open_new", "mail.refresh", "x.y"], size="XL"),
                                               fake_repo))
    assert "size" in schema and "quick_actions" in schema                  # the schema stops these first
    text = " | ".join(masonry.validate_spec(_mail(events=["tasks.created"], quick_actions=["agent.run"],
                                                  config={"host": 5, "colour": "red"}), fake_repo))
    assert "does not send 'tasks.created'" in text and "has no action 'agent.run'" in text
    assert "host must be str" in text and "takes no 'colour'" in text
    assert any("type" in e for e in masonry.validate_spec(_mail(type="castle"), fake_repo))
    # an old spec (no type) still needs its panes
    old = {"id": "old", "title": "Old", "icon": "🏗", "orc": {"name": "Peon"}}
    assert masonry.validate_spec(old, fake_repo)
    assert masonry.validate_spec({**old, "data": [{"name": "c", "source": "git_log"}],
                                  "layout": {"direction": "vertical", "panes": [{"widget": "list", "data": "c"}]}},
                                 fake_repo) == []


def test_typed_events_on_roads(fake_repo: Path):
    pipes.TYPED.clear()
    pipes.set_typed("inbox", catalog.events_of(_mail()))
    assert "mail.received" in pipes.emits("inbox", has_garrison=False)
    assert pipes.label("mail.received") == "new mail" and pipes.label("on_task_completed") == "task completed"
    assert "mail.received" in pipes.modes_for("inbox", "loot")         # a text event to a text receiver
    s = ts.default_scroll({"loot": {"title": "Artifacts", "icon": "📦", "orc": "Q", "role": "", "category": "core"},
                           "inbox": {"title": "Inbox", "icon": "📨", "orc": "Raven", "role": "", "category": "core"}})
    road = ts.subscribe(s, "loot", "inbox", "mail.received")
    assert road.event == "mail.received"
    with pytest.raises(ValueError):
        ts.subscribe(s, "loot", "inbox", "mail.exploded")
    pipes.TYPED.clear()


@pytest.mark.asyncio
async def test_a_typed_building_loads_and_sends_along_its_road(fake_repo: Path):
    from orkcraft.app import OrkcraftApp
    from orkcraft.realm.pipes import Payload

    assert masonry.save_spec(fake_repo, _mail()) == []
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    assert "mail.received" in pipes.emits("inbox", False)
    ts.add_handler(app.scroll, "loot", "Clerk", kind="chain", chain=[{"op": "count"}])
    ts.subscribe(app.scroll, "loot", "inbox", "mail.received", handler="clerk")
    async with app.run_test(size=(160, 45)) as pilot:
        await pilot.pause()
        w = app.desktop.get_window("inbox")
        from orkcraft.screens.typed.watchtower_view import WatchtowerView
        assert w is not None and w.query(WatchtowerView)                       # its type's own view
        carts = app.roads.emit(Payload("text", "From: boss · Subject: hi", "inbox", "mail.received"))
        assert carts and carts[0].target == "loot"
        choices = app._road_choices("inbox", "loot")
        assert any(ev == "mail.received" and h == "clerk" for ev, h, _ in choices)
    data = json.loads(masonry.spec_file(fake_repo, "inbox").read_text())
    assert data["type"] == "watchtower"                                  # saved as its camp building


def test_pool_config_is_checked(fake_repo: Path):
    spec = {"id": "barracks", "title": "Barracks", "icon": "🏕", "orc": {"name": "Foreman"}, "type": "pool",
            "config": {"max_orcs": 3, "budget_usd": 5, "providers": ["claude", "agy"], "worktrees": True}}
    assert masonry.validate_spec(spec, fake_repo) == []
    bad = masonry.validate_spec({**spec, "config": {"max_orcs": 50, "worktrees": "yes"}}, fake_repo)
    assert any("max_orcs must be between 1 and 10" in e for e in bad) and any("worktrees must be bool" in e for e in bad)


def test_every_buildable_type_has_its_own_view():
    from orkcraft.screens.typed import _views, view_for
    from orkcraft.screens.custom_view import CustomBuildingView

    views = _views()
    for tid in catalog.TYPES:
        if tid in catalog.SYSTEM_TYPES or tid == catalog.DEFAULT_TYPE:
            continue
        assert tid in views, f"{tid} has no view"
        assert type(view_for({"id": "x", "type": tid})) is views[tid]
    assert type(view_for({"id": "x", "type": "custom"})) is CustomBuildingView


def test_a_typed_road_is_saved(fake_repo: Path, tmp_path: Path):
    from orkcraft.app import OrkcraftApp

    assert masonry.save_spec(fake_repo, _mail()) == []
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    road = ts.subscribe(app.scroll, "loot", "inbox", "mail.received")
    assert road.id == "inbox-mail_received"
    assert ts.save(tmp_path / "scroll.json", app.scroll) == []          # a dotted id would be refused
    again, problems = ts.load(tmp_path / "scroll.json", {})
    assert problems == [] and again.building("loot").road("inbox-mail_received").event == "mail.received"


def test_old_types_load_as_camp_buildings(fake_repo: Path):
    assert {catalog.migrate({"type": old})["type"] for old in catalog.ALIASES} <= set(catalog.TYPES)
    assert catalog.type_of({"type": "tasks"}).id == "fields" and catalog.type_of({"type": "git"}).id == "forge"
    script = catalog.migrate({"id": "s", "type": "agent", "events": ["agent.done"],
                              "config": {"skill": "make lint", "harness": "script"}})
    assert script["type"] == "mill" and script["config"] == {"steps": ["script: make lint"]} and "events" not in script
    agent = catalog.migrate({"id": "a", "type": "agent", "config": {"skill": "Review it.", "harness": "agy"}})
    assert agent["type"] == "barracks" and agent["config"] == {"max_orcs": 1, "providers": ["agy"], "orders": "Review it."}
    # a spec file of T1105 on disk loads, and its state folder moves to the new type's
    folder = fake_repo / masonry.SPECS_DIR
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "todo.json").write_text(json.dumps({"version": 1, "id": "todo", "title": "Todo", "icon": "📋",
                                                  "orc": {"name": "Smith"}, "type": "tasks"}))
    specs, problems = masonry.load_specs(fake_repo)
    assert problems == [] and specs[0]["type"] == "fields"


@pytest.mark.asyncio
async def test_a_new_camp_has_only_the_town_hall_and_builds_from_the_catalog(fake_repo: Path, monkeypatch):
    from orkcraft.app import OrkcraftApp
    from orkcraft.screens.presets_modal import PresetsModal

    monkeypatch.setattr(ts, "STARTING", ("town_hall",))              # the real default (conftest keeps the old)
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=(160, 45)) as pilot:
        await pilot.pause()
        standing = [b.id for b in app.scroll.buildings if not b.demolished]
        assert standing == ["town_hall"]
        app.action_presets_catalog()
        await pilot.pause()
        lst = app.screen.query_one("#presets-list")
        ids = [lst.get_option_at_index(i).id for i in range(lst.option_count)]
        assert sum(1 for i in ids if i and i.startswith("type:")) == 15
        assert isinstance(app.screen, PresetsModal)
        lst.highlighted = ids.index("type:forge")
        await pilot.press("enter")
        await pilot.pause()
        from orkcraft.screens.build_wizard import BuildReview
        assert isinstance(app.screen, BuildReview)                       # step 2: this building's settings
        await pilot.press("ctrl+s")
        await pilot.pause()
        assert app.custom_specs["forge_1"]["type"] == "forge"           # "forge" is a reserved id
        assert app.desktop.get_window("forge_1") is not None
        assert app.build_from_type("crag") and app.custom_specs["crag"]["title"] == "Tally Crag"



@pytest.mark.asyncio
async def test_a_preset_is_picked_by_intent_then_named_and_set(fake_repo: Path):
    from textual.widgets import Input

    from orkcraft.app import OrkcraftApp
    from orkcraft.screens.build_wizard import BuildReview

    ids = [t for _, types in catalog.INTENTS for t in types]
    assert len(ids) == len(set(ids)) == 15                              # every camp type under one intent
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=(160, 45)) as pilot:
        await pilot.pause()
        app.action_presets_catalog()
        await pilot.pause()
        lst = app.screen.query_one("#presets-list")
        labels = [str(lst.get_option_at_index(i).prompt) for i in range(lst.option_count)]
        assert any("Watch load, limits and spend" in x for x in labels)
        oids = [lst.get_option_at_index(i).id for i in range(lst.option_count)]
        lst.highlighted = oids.index("type:crag")
        await pilot.press("enter")
        await pilot.pause()
        form = app.screen
        assert isinstance(form, BuildReview) and "FROM A PRESET · 2/3" in str(form.query_one(".wizard-title").render())
        form.query_one("#review-title", Input).value = "Token Load"
        form.query_one("#review-icon", Input).value = "🔥"
        form.query_one("#review-summary", Input).value = "tokens per hour"
        form.query_one("#cfg-orientation", Input).value = "diagonal"
        form.query_one("#cfg-source", Input).value = "tokens"
        await pilot.press("ctrl+s")
        await pilot.pause()
        assert app.screen is form and "orientation" in str(form.query_one("#review-errors").render())
        form.query_one("#cfg-orientation", Input).value = "horizontal"
        await pilot.press("ctrl+s")
        await pilot.pause()
        spec = app.custom_specs["crag"]
        assert (spec["title"], spec["icon"], spec["summary"]) == ("Token Load", "🔥", "tokens per hour")
        assert spec["config"] == {"orientation": "horizontal", "source": "tokens"}
        assert not (fake_repo / ".orkcraft/council/reviews.jsonl").exists()   # presets skip the Council


def test_list_settings_take_json_and_semicolons():
    from orkcraft.screens.build_wizard import _parse, _show

    assert _parse(list, "a, b") == ["a", "b"]
    assert _parse(list, "join: , ; upper") == ["join: ,", "upper"]
    assert _parse(list, '[{"if": "x", "route": "y"}]') == [{"if": "x", "route": "y"}]
    assert _show([{"a": 1}]) == '[{"a": 1}]' and _show(["a", "b"]) == "a, b"
