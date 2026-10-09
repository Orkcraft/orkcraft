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
from orkcraft.realm import catalog, intents, lake, modes, naming


class BuildError(Exception):
    """What the page asked for cannot be done; its text is shown to the person."""


LANDSCAPE_GROUP = "Landscape: works by itself, needs no ork"   # the wizard's last group (landscape.md §6)


FOR_YOU = 6               # the role's buildings the tray may offer first; it shows three not standing yet


def for_role(role_id: str) -> list[str]:
    """The building types the onboarding's role uses most, most first: counted over its ready towns
    (realm/intents.py INTENTS), the order they first come in breaking a tie."""
    count: dict[str, int] = {}
    for i in intents.INTENTS:
        if i.role == role_id:
            for b in i.plan.get("buildings", []):
                count[b["type"]] = count.get(b["type"], 0) + 1
    return sorted(count, key=lambda t: -count[t])[:FOR_YOU]


def catalog_types(profile: dict | None = None) -> list[dict[str, Any]]:
    """Every type a building can be raised from, as the wizard lists them, each with what it is for
    (`intent`: the catalog's "What do you need?" groups, in their order). Buildings come first;
    the landscape (no ork, docs/design/landscape.md) is a group of its own after them. `yours`: its place among
    the role's own (`for_role`, the onboarding's `profile`), -1 when it is not one (the Build row's first icons)."""
    mine = for_role(intents.role(str((profile or {}).get("role") or "")).id)
    hidden = (catalog.SYSTEM_TYPES | catalog.SCRATCH_TYPES | catalog.RETIRED_TYPES | lake.WINDOW_TYPES
              | {catalog.DEFAULT_TYPE})
    intent = {tid: need for need, ids in catalog.INTENTS for tid in ids}
    order = {tid: n for n, tid in enumerate(tid for _, ids in catalog.INTENTS for tid in ids)}
    types = sorted((t for t in catalog.TYPES.values() if t.id not in hidden),
                   key=lambda t: (t.landscape, order.get(t.id, len(order))))
    return [{"id": t.id, "title": t.title, "summary": modes.strip_emoji(t.summary), "agentic": t.agentic,
             "landscape": t.landscape, "takes": catalog.takes(t.id), "sends": [e.label for e in t.events][:6],
             "intent": LANDSCAPE_GROUP if t.landscape else intent.get(t.id, "Something else"),
             "yours": mine.index(t.id) if t.id in mine else -1} for t in types]


def _id(args: dict, key: str) -> str:
    value = args.get(key)
    if not isinstance(value, str) or not value:
        raise BuildError(f"{key} is missing")
    return value[:200]


def build(host, args: dict) -> str:
    """A building straight from the catalog (the type's defaults, no model call), in the active
    orkspace; it is committed in the camp's own git as the TUI's presets are."""
    town = host.town
    if catalog.ALIASES.get(_id(args, "type"), _id(args, "type")) in lake.WINDOW_TYPES:
        raise BuildError("Lake is the town's window, not a building: a document's mark opens it")
    spec = buildings.type_spec(town, _id(args, "type"))
    if spec is None:
        raise BuildError("That type cannot be raised here")
    prompt = args.get("prompt")
    asked = (spec.get("type") or "", " ".join(prompt.split())[:2000]) if isinstance(prompt, str) and prompt.strip() else None
    if asked is not None:
        # The Warchief's Build offer stays in its chat: a second press on it opens what the first one raised.
        done = host.raised_for.get(asked)
        kept = town.scroll.building(done) if done else None
        if kept is not None and not kept.demolished:
            return done
        spec["title"] = naming.from_prompt(prompt[:2000], spec["title"])   # built for a request: named after it, ≤ 4 words
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
    if asked is not None:
        host.raised_for[asked] = built.id
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
