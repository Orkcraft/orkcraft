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
    assert set(catalog.TYPES) == want | {"town_hall", "custom", "workshop"} | catalog.GUI_ONLY
    assert catalog.DEFAULT_TYPE in catalog.TYPES
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
    assert catalog.type_of(spec).size == "L"
    assert catalog.events_of(spec) == ["calendar.event_due", "calendar.event_added", "calendar.event_removed",
                                       "calendar.day_schedule", "calendar.event_upcoming", "calendar.doc_opened"]
    assert [a.id for a in catalog.quick_actions_of(spec)] == ["calendar.new", "calendar.prepare"]
    picked = {"type": "calendar", "size": "M", "events": ["calendar.day_schedule"], "quick_actions": []}
    assert catalog.events_of(picked) == ["calendar.day_schedule"]
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


def test_pool_config_is_checked(fake_repo: Path):
    spec = {"id": "barracks", "title": "Barracks", "icon": "🏕", "orc": {"name": "Foreman"}, "type": "pool",
            "config": {"max_orcs": 3, "budget_usd": 5, "providers": ["claude", "agy"], "worktrees": True}}
    assert masonry.validate_spec(spec, fake_repo) == []
    bad = masonry.validate_spec({**spec, "config": {"max_orcs": 50, "worktrees": "yes"}}, fake_repo)
    assert any("max_orcs must be between 1 and 10" in e for e in bad) and any("worktrees must be bool" in e for e in bad)


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


def test_the_landscape_is_the_seven_types_that_need_no_ork():
    """docs/design/landscape.md §2: seven types are land, not buildings; the wizard lists buildings first and
    the land as a group of its own after them; the word is in the glossary."""
    from orkcraft.gui import builder
    from orkcraft.realm import lexicon

    assert catalog.LANDSCAPE == {"signpost", "mill", "pit", "lake", "forest", "crag", "horn"}
    assert not {"town_hall", "workshop", "war_drum", "loot", "forge"} & catalog.LANDSCAPE
    listed = builder.catalog_types()
    flags = [t["landscape"] for t in listed]
    assert flags == sorted(flags) and any(flags) and not flags[0]          # buildings first, then the land
    assert {t["intent"] for t in listed if t["landscape"]} == {builder.LANDSCAPE_GROUP}
    assert builder.LANDSCAPE_GROUP not in {t["intent"] for t in listed if not t["landscape"]}
    assert "landscape" in {t.key for t in lexicon.TERMS}


def test_the_build_tray_offers_the_roles_own_buildings_first():
    """The tray's For you (docs/design/warchief-line-and-cards.md §2): the buildings the onboarding's role uses most in
    its ready towns, and the sources it reads for External listeners."""
    from orkcraft.gui import builder
    assert builder.for_role("engineer")[:3] == ["watchtower", "barracks", "loot"]
    listed = {t["id"]: t for t in builder.catalog_types({"role": "designer"})}
    assert listed["barracks"]["yours"] == 0 and listed["mill"]["yours"] == -1
    assert listed["watchtower"]["role_sources"][0] == "figma" and "role_sources" not in listed["fields"]
    assert all(t["yours"] >= -1 for t in builder.catalog_types())        # no role: the catch-all's
