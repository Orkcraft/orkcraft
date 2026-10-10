"""Town Scroll roads (subscriptions between buildings, rally points) and custom buildings.

Part of orkcraft.scroll, which re-exports every name here: import it from there."""
from __future__ import annotations

import re

from orkcraft.scroll import (HISTORY_DIR, MAX_ROADS, ROAD_EVENTS, BuildingSpec, Garrison, OrcSpec, Road,
                             TownScroll, _typed_events)
from orkcraft.scroll_checks import _cycle, filter_problems
from orkcraft.scroll_garrisons import _building, _orc_id

# -- roads ------------------------------------------------------------------------------------------------

def incoming(scroll: TownScroll, building_id: str) -> list[Road]:
    b = scroll.building(building_id)
    return list(b.roads) if b else []


def outgoing(scroll: TownScroll, building_id: str) -> list[tuple[BuildingSpec, Road]]:
    """(target building, road) for every road leaving `building_id`."""
    return [(b, r) for b in scroll.buildings for r in b.roads if r.source == building_id]


def road_key(target_id: str, road_id: str) -> str:
    """Road ids are unique per receiver; a town needs one key for all roads: `<target id>:<road id>`."""
    return f"{target_id}:{road_id}"


def split_key(key: str) -> tuple[str, str]:
    target, _, road = key.partition(":")
    return target, road


def find_road(scroll: TownScroll, road_id: str, target_id: str | None = None) -> tuple[BuildingSpec, Road] | None:
    """(target building, road) by road id — ids are unique per receiver, so pass the target when known."""
    for b in scroll.buildings:
        if target_id is not None and b.id != target_id:
            continue
        r = b.road(road_id)
        if r is not None:
            return b, r
    return None


def has_outgoing(scroll: TownScroll, building_id: str, event: str) -> bool:
    """Does any road carry `event` out of `building_id`? (whether to emit it at all)"""
    return any(r.event == event for _, r in outgoing(scroll, building_id))


# A Test bench's road into a chain it tests (docs/design/test-bench.md §2): it only says where the chain begins, and
# no cart ever goes down it in the town (a run gives the case to a copy), so the road back from the chain's end
# closes no loop.
CASE_EVENT = "lab.case"


def _closes_no_loop(event: str, flt: dict | None) -> bool:
    return bool((flt or {}).get("returns")) or event == CASE_EVENT


def _road_edges(scroll: TownScroll) -> dict[str, set[str]]:
    edges: dict[str, set[str]] = {}
    for b in scroll.buildings:
        for r in b.roads:
            if not _closes_no_loop(r.event, r.filter):      # a return road brings results back: no loop
                edges.setdefault(r.source, set()).add(b.id)
    return edges


def subscribe(scroll: TownScroll, target_id: str, source_id: str, event: str = "on_selection_change",
              filter: dict | None = None, handler: str | None = None, label: str = "") -> Road:
    """Give `target_id` an incoming road from `source_id` (Y on the receiver).

    Raises ValueError for unknown buildings, a self-road, an unknown event, a bad filter, a
    handler that is not one of the target's handlers, a duplicate road, too many roads or a loop.
    """
    src, dst = scroll.building(source_id), scroll.building(target_id)
    if src is None or dst is None:
        raise ValueError(f"unknown building {source_id!r} or {target_id!r}")
    if source_id == target_id:
        raise ValueError("a road cannot come from its own building")
    if event not in ROAD_EVENTS and event not in _typed_events():
        raise ValueError(f"unknown road event {event!r}")
    flt = dict(filter or {})
    if problems := filter_problems(flt):
        raise ValueError("filter: " + "; ".join(problems))
    if handler is not None and dst.garrison.handler(handler) is None:
        raise ValueError(f"{dst.title} has no handler {handler!r}")
    if len(dst.roads) >= MAX_ROADS:
        raise ValueError(f"{dst.title}: at most {MAX_ROADS} incoming roads")
    for r in dst.roads:
        if (r.source, r.event, r.handler, r.filter) == (source_id, event, handler, flt):
            raise ValueError(f"{dst.title} already has this road from {src.title}")
    edges = _road_edges(scroll)
    if not _closes_no_loop(event, flt):               # a return road brings results back: it closes no loop
        edges.setdefault(source_id, set()).add(target_id)
    if _cycle(edges) is not None:
        raise ValueError(f"{src.title} → {dst.title} would close a loop of roads")
    short = event.replace(".", "_") if "." in event else event.removeprefix("on_").split("_")[0]   # typed: mail_received
    base = f"{source_id}-{short}"[:60]
    ids = {r.id for r in dst.roads}
    rid, n = base, 2
    while rid in ids:
        rid, n = f"{base}-{n}", n + 1
    if label and not re.fullmatch(r"[a-z0-9_:.-]{1,32}", label):
        raise ValueError(f"bad road label {label!r}")
    road = Road(rid, source_id, event, flt, handler, label=label)
    dst.roads.append(road)
    return road


def unsubscribe(scroll: TownScroll, target_id: str, road_id: str) -> Road:
    b = _building(scroll, target_id)
    road = b.road(road_id)
    if road is None:
        raise ValueError(f"{b.title}: no road {road_id!r}")
    b.roads.remove(road)
    return road


def set_road_handler(scroll: TownScroll, target_id: str, road_id: str, handler: str | None) -> Road:
    """Put a handler on a road (or take it off: None → plain road)."""
    b = _building(scroll, target_id)
    road = b.road(road_id)
    if road is None:
        raise ValueError(f"{b.title}: no road {road_id!r}")
    if handler is not None and b.garrison.handler(handler) is None:
        raise ValueError(f"{b.title} has no handler {handler!r}")
    road.handler = handler
    return road


def set_road_filter(scroll: TownScroll, target_id: str, road_id: str, filter: dict | None) -> Road:
    b = _building(scroll, target_id)
    road = b.road(road_id)
    if road is None:
        raise ValueError(f"{b.title}: no road {road_id!r}")
    flt = dict(filter or {})
    if problems := filter_problems(flt):
        raise ValueError("filter: " + "; ".join(problems))
    road.filter = flt
    return road


# -- custom buildings (Mason & Artisan) ---------------------------------------------------------------

def add_custom_building(scroll: TownScroll, spec: dict, orkspace_id: str | None = None) -> BuildingSpec:
    """Register a validated custom building spec (`realm.masonry`) in an orkspace (default: the active).

    Its steward is the spec's orc. Raises ValueError when the id is taken or the orkspace unknown.
    """
    bid = str(spec["id"])
    if scroll.building(bid) is not None:
        raise ValueError(f"a building {bid!r} already exists")
    ork = scroll.orkspace(orkspace_id) if orkspace_id else scroll.active_orkspace
    if ork is None:
        raise ValueError(f"unknown orkspace {orkspace_id!r}")
    orc = spec.get("orc") or {}
    orc_name = str(orc.get("name") or "Peon")
    b = BuildingSpec(
        id=bid, preset_ref=f"custom:{bid}", title=str(spec["title"]), icon=str(spec.get("icon", "")),
        chronicles={"enabled": True, "log_file": str(HISTORY_DIR / f"{bid}.events.jsonl")},
        garrison=Garrison(OrcSpec(_orc_id(orc_name), orc_name, role=str(orc.get("role", "")))),
    )
    scroll.buildings.append(b)
    ork.buildings.append(bid)
    return b
