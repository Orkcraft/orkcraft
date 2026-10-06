"""Roads as the core lays them: what a receiver can take from a source, laying, removing and
re-handling a road. The dialogs that ask which road are the face's; these are the acts.

Every change publishes `ROADS` (the face saves the scroll and redraws), leaves a line in the
receiver's chronicle and, unless it is one of many, a checkpoint in the camp's git.
"""
from __future__ import annotations

from orkcraft import scroll
from orkcraft.core import bus
from orkcraft.core.town import Town
from orkcraft.realm import catalog, pipes


def choices(town: Town, source_id: str, target_id: str) -> list[tuple[str, str | None, str]]:
    """(event, handler or None, label) the receiver can subscribe to from the source."""
    if town.scroll is None or source_id == target_id:
        return []
    src, tgt = town.scroll.building(source_id), town.scroll.building(target_id)
    if src is None or tgt is None:
        return []
    has_garrison = bool(src.garrison.members)
    out = [(ev, None, f"plain · {pipes.label(ev)}")
           for ev in pipes.road_events(source_id, target_id, has_garrison, handler=False)]
    spec = town.custom_specs.get(source_id)
    if spec is not None and catalog.type_of(spec).id == "signpost":     # one road per route
        from orkcraft.realm import signpost
        out = [(f"signpost.routed#{r}", None, f"plain · route {r}")
               for r in signpost.routes((spec.get("config") or {}).get("rules") or [])] + out
    if spec is not None and catalog.type_of(spec).id == "council":       # a clan that routes: one road per route
        from orkcraft.realm import team
        out = [(f"team.routed#{r}", None, f"plain · route {r}") for r in team.routes_of(spec.get("config") or {})] + out
    for orc in tgt.garrison.handlers:
        for ev in pipes.road_events(source_id, target_id, has_garrison, handler=True):
            out.append((ev, orc.id, f"{orc.avatar} {orc.name} ({orc.kind}) · {pipes.label(ev)}"))
    return out


def listenable(town: Town, source_id: str, target_id: str) -> list[tuple[str, str]]:
    """(event, label) a listener with a prompt (Roads v3: a rule makes the handler) can take."""
    src = town.scroll.building(source_id) if town.scroll is not None else None
    if src is None or source_id == target_id:
        return []
    return [(ev, pipes.label(ev)) for ev in pipes.road_events(source_id, target_id, bool(src.garrison.members),
                                                              handler=True)]


def lay(town: Town, target_id: str, source_id: str, event: str, handler: str | None,
        quiet: bool = False) -> scroll.Road | None:
    """A road from `source_id` into `target_id` on `event` (`signpost.routed#<route>`: a road that
    waits for that route). `quiet`: one of many (a town plan) — no toast and no checkpoint of its own."""
    event, _, route = event.partition("#")
    flt = {"route": [route]} if route else None
    try:
        road = scroll.subscribe(town.scroll, target_id, source_id, event, flt, handler=handler, label=route)
    except ValueError as e:
        town.toast(str(e), title="Roads", severity="warning")
        return None
    town.publish(bus.ROADS)
    if not quiet:
        town.checkpoint("road", target_id, f"road from {source_id} on {event}{' (' + route + ')' if route else ''}")
    src, tgt = town.scroll.building(source_id), town.scroll.building(target_id)
    orc = tgt.garrison.handler(handler) if handler and tgt else None
    who = orc.name if orc else "plain"
    src_title = src.title if src else source_id
    town.record(target_id, "road_subscribed", source=src_title, event=pipes.label(event), handler=who)
    if not quiet:
        town.toast(f"🛤 {src_title} → {tgt.title if tgt else target_id} ({pipes.label(event)}, {who})", title="Roads")
    return road


def remove(town: Town, key: str) -> scroll.Road | None:
    target_id, road_id = scroll.split_key(key)
    try:
        road = scroll.unsubscribe(town.scroll, target_id, road_id)
    except ValueError as e:
        town.toast(str(e), title="Roads", severity="warning")
        return None
    town.publish(bus.ROADS)
    town.checkpoint("road", target_id, f"remove road {road_id}")
    src = town.scroll.building(road.source)
    town.record(target_id, "road_removed", source=src.title if src else road.source, event=pipes.label(road.event))
    town.toast(f"🚧 road from {src.title if src else road.source} removed", title="Roads")
    return road


def handlers(town: Town, key: str) -> list[tuple[str, str]] | None:
    """(orc id, label) of the receiver's handlers a road can go to; None when the road is gone."""
    target_id, road_id = scroll.split_key(key)
    found = scroll.find_road(town.scroll, road_id, target_id)
    if found is None:
        return None
    tgt, _ = found
    return [(o.id, f"{o.avatar} {o.name} ({o.kind})") for o in tgt.garrison.handlers]


def set_handler(town: Town, key: str, handler: str | None) -> bool:
    """The road's handler (None: plain). A handler takes whatever the source emits; plain only what
    the receiver shows."""
    target_id, road_id = scroll.split_key(key)
    found = scroll.find_road(town.scroll, road_id, target_id)
    if found is None:
        return False
    tgt, road = found
    if handler is None and road.event not in pipes.road_events(road.source, target_id, handler=False):
        town.toast(f"{tgt.title} cannot show this event without a handler", title="Roads", severity="warning")
        return False
    try:
        scroll.set_road_handler(town.scroll, target_id, road_id, handler)
    except ValueError as e:
        town.toast(str(e), title="Roads", severity="warning")
        return False
    town.publish(bus.ROADS)
    src = town.scroll.building(road.source)
    orc = tgt.garrison.handler(handler) if handler else None
    town.record(target_id, "road_changed", source=src.title if src else road.source,
                handler=orc.name if orc else "plain")
    return True
