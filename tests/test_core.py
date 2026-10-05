"""The core without a face: a Town, its bus and its services, with no Textual app around them."""
from __future__ import annotations

from pathlib import Path

from orkcraft.core import buildings, bus, roads
from orkcraft.core.bus import Bus
from orkcraft.core.night import Night
from orkcraft.core.town import Town
from orkcraft.core.treasury import Treasury
from orkcraft.realm import checkpoint
from orkcraft.scroll import road_key


def _town(repo: Path) -> tuple[Town, list]:
    town = Town(repo)
    seen: list = []
    town.bus.subscribe(bus.ANY, seen.append)
    return town, seen


def _topics(seen) -> list[str]:
    return [e.topic for e in seen]


def test_bus_delivers_to_a_topic_and_to_any_and_unsubscribes():
    b, got = Bus(), []
    off = b.subscribe("roads", lambda e: got.append(("roads", e.data)))
    b.subscribe(bus.ANY, lambda e: got.append(("any", e.topic)))
    b.publish("roads", why="test")
    off()
    b.publish("roads")
    assert got == [("roads", {"why": "test"}), ("any", "roads"), ("any", "roads")]


def test_a_town_loads_without_a_face_and_saves_its_scroll(fake_repo, isolated_layout_file):
    town, _ = _town(fake_repo)
    assert town.scroll.building("town_hall") is not None and town.building("loot") is not None
    assert town.title_of("town_hall").endswith("Town Hall")
    assert {"loot", "town_hall"} <= town.taken_ids()
    assert town.save() and isolated_layout_file.exists()


def test_raising_a_spec_and_laying_a_road_publish_what_changed(fake_repo):
    town, seen = _town(fake_repo)
    checkpoint.ensure(fake_repo)
    spec = buildings.type_spec(town, "fields")
    built = buildings.raise_spec(town, spec)
    assert built is not None and built.id in town.custom_specs and town.scroll.building(built.id) is not None

    choices = roads.choices(town, built.id, "loot")
    assert choices, "Task Fields send something the Loot can take"
    event, handler, _ = choices[0]
    road = roads.lay(town, "loot", built.id, event, handler)
    assert road is not None
    assert bus.ROADS in _topics(seen) and any(e.topic == bus.TOAST and "🛤" in e.data["message"] for e in seen)
    assert checkpoint.history(fake_repo, "loot", 1), "the road is a checkpoint in the camp's git"

    seen.clear()
    assert roads.remove(town, road_key("loot", road.id)) is not None
    assert town.scroll.building("loot").roads == [] and bus.ROADS in _topics(seen)


def test_a_refused_road_is_said_not_raised(fake_repo):
    town, seen = _town(fake_repo)
    assert roads.lay(town, "nowhere", "loot", "pit.file", None) is None
    assert [e.data["severity"] for e in seen if e.topic == bus.TOAST] == ["warning"]


def test_the_treasury_holds_the_purse_and_says_so_once(fake_repo):
    town, seen = _town(fake_repo)
    treasury = Treasury(town)
    town.scroll.budget.gold_session_limit_usd = 1.0
    assert not treasury.exhausted()
    town.snapshot.spent_usd = 2.0
    assert treasury.exhausted(quiet=True) and not seen
    assert treasury.exhausted() and _topics(seen) == [bus.TOAST]
    gold, level, lumber, _ = treasury.resources()
    assert gold.endswith("/ $1.00") and level and lumber.startswith("—")


def test_the_night_counts_its_hours(fake_repo):
    night = Night(Town(fake_repo))
    assert night.tick(quiet=True) is False and night.quiet_since
    night.elders_count = 3
    assert night.tick(quiet=False) is True
    night.morning()
    assert night.quiet_since is None and night.elders_count == 0
    assert night.next_change(quiet=False, level=3, exhausted=False) is None     # by day the orks wait
