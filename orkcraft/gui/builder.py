"""Changing the town from the GUI: raising a building from the catalog, demolishing one, laying
and removing roads. Each act is a core service (core/buildings.py, core/roads.py); this module
words what the page sends and returns what it draws.

    builder.catalog(town)                         # the types a building can be raised from
    builder.build(host, {"type": "lake"})         # → the new building's id
    builder.road_choices(host, {"from": "pit", "to": "lake"})
    builder.lay_road(host, {"from": "pit", "to": "lake", "event": "pit.text", "handler": None})
"""
from __future__ import annotations

from typing import Any

from orkcraft.core import buildings, roads
from orkcraft.realm import catalog, lake, modes


class BuildError(Exception):
    """What the page asked for cannot be done; its text is shown to the person."""


def catalog_types() -> list[dict[str, Any]]:
    """Every type a building can be raised from, as the wizard lists them."""
    hidden = catalog.SYSTEM_TYPES | catalog.SCRATCH_TYPES | lake.WINDOW_TYPES | {catalog.DEFAULT_TYPE}
    return [{"id": t.id, "title": t.title, "summary": modes.strip_emoji(t.summary), "agentic": t.agentic,
             "takes": catalog.takes(t.id), "sends": [e.label for e in t.events][:6]}
            for t in catalog.TYPES.values() if t.id not in hidden]


def _id(args: dict, key: str) -> str:
    value = args.get(key)
    if not isinstance(value, str) or not value:
        raise BuildError(f"{key} is missing")
    return value[:200]


def build(host, args: dict) -> str:
    """A building straight from the catalog (the type's defaults, no model call), in the active
    orkspace; it is committed in the camp's own git as the TUI's presets are."""
    town = host.town
    spec = buildings.type_spec(town, _id(args, "type"))
    if spec is not None and spec.get("type") in lake.WINDOW_TYPES:
        raise BuildError("Lake is the town's window, not a building: a document's mark opens it")
    if spec is None:
        raise BuildError("That type cannot be raised here")
    hut = args.get("hut")
    spot = [float(hut[0]), float(hut[1])] if isinstance(hut, list) and len(hut) == 2 else None
    built = buildings.raise_spec(town, spec, spot)
    if built is None:
        raise BuildError("The building was refused (see the note)")
    ork = town.scroll.active_orkspace
    town.record(built.id, "building_raised", orkspace=ork.name if ork else town.scroll.active_orkspace_id)
    town.worker(built.id)
    town.save()
    town.toast(f"{spec['title']} raised", title="Build")
    town.checkpoint("create", built.id, f"raise {spec.get('type') or 'custom'} {spec['title']}")
    host.refresh_roster()
    return built.id


def demolish(host, args: dict) -> bool:
    bid = _id(args, "id")
    if not buildings.demolish(host.town, bid):
        raise BuildError("That building cannot come down")
    host.town.checkpoint("demolish", bid, "demolished from the GUI")
    host.refresh_roster()
    return True


def road_choices(host, args: dict) -> list[dict[str, Any]]:
    """What a road from one building into another may carry: plain, or to one of its orks."""
    out = roads.choices(host.town, _id(args, "from"), _id(args, "to"))
    return [{"event": ev, "handler": h, "label": modes.strip_emoji(label)} for ev, h, label in out]


def lay_road(host, args: dict) -> str:
    src, dst, event = _id(args, "from"), _id(args, "to"), _id(args, "event")
    handler = args.get("handler") if isinstance(args.get("handler"), str) else None
    allowed = {(ev, h) for ev, h, _ in roads.choices(host.town, src, dst)}
    if (event, handler) not in allowed:
        raise BuildError("That road cannot be laid between these buildings")
    road = roads.lay(host.town, dst, src, event, handler)
    if road is None:
        raise BuildError("The road was refused (see the note)")
    return f"{dst}:{road.id}"


def remove_road(host, args: dict) -> bool:
    if roads.remove(host.town, _id(args, "key")) is None:
        raise BuildError("No such road")
    return True
