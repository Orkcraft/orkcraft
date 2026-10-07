"""Roads as the core lays them: what a receiver can take from a source, laying, removing and
re-handling a road. The dialogs that ask which road are the face's; these are the acts.

Every change publishes `ROADS` (the face saves the scroll and redraws), leaves a line in the
receiver's chronicle and, unless it is one of many, a checkpoint in the camp's git.
"""
from __future__ import annotations

from orkcraft import scroll
from orkcraft.core import bus
from orkcraft.core.town import Town
from orkcraft.realm import catalog, pipes, road_planner


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
    if spec is not None and catalog.type_of(spec).id == "council":       # a board's exits: one road per exit
        from orkcraft.realm import team
        out = [(f"team.routed#{e.id}", None, f"plain · exit {e.name}") for e in team.exits_of(spec.get("config") or {})] + out
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


def _help(event: str) -> str:
    for t in catalog.TYPES.values():
        e = t.event(event.partition("#")[0])
        if e is not None:
            return e.help
    return ""


def contract(town: Town, target_id: str, source_id: str | None = None,
             among: list[str] | None = None) -> tuple[road_planner.Target, list[road_planner.Source]]:
    """What the road planner sees: what the receiver takes and what each building that could send it
    sends — `source_id` alone when the road was drawn from it, else every building (of `among`)."""
    sc = town.scroll
    tgt = sc.building(target_id) if sc is not None else None
    if tgt is None:
        raise ValueError(f"unknown building {target_id!r}")
    tspec = town.custom_specs.get(target_id)
    target = road_planner.Target(target_id, tgt.title, catalog.takes(catalog.type_of(tspec).id) if tspec else "")
    ids = [source_id] if source_id else [b.id for b in sc.buildings if not b.demolished]
    if among is not None and not source_id:
        ids = [i for i in ids if i in set(among)]
    sources = []
    for sid in ids:
        src = sc.building(sid)
        if src is None or src.demolished or sid == target_id:
            continue
        spec = town.custom_specs.get(sid)
        plain = tuple(road_planner.Event(ev, label.removeprefix("plain · "), _help(ev))
                      for ev, h, label in choices(town, sid, target_id) if h is None)
        ruled = tuple(road_planner.Event(ev, label, _help(ev)) for ev, label in listenable(town, sid, target_id))
        sources.append(road_planner.Source(sid, src.title, catalog.type_of(spec).summary if spec else "", plain, ruled))
    return target, sources


def lay(town: Town, target_id: str, source_id: str, event: str, handler: str | None,
        quiet: bool = False, match: str = "") -> scroll.Road | None:
    """A road from `source_id` into `target_id` on `event` (`signpost.routed#<route>`: a road that
    waits for that route; `match`: only what the regex finds in a cart leaves the source).
    `quiet`: one of many (a town plan) — no toast and no checkpoint of its own."""
    event, _, route = event.partition("#")
    flt = {"route": [route]} if route else {}
    if match:
        flt["match"] = match
    flt = flt or None
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
        what = _exit_name(town, source_id, route) if event == "team.routed" else ""
        town.toast(f"🛤 {src_title} → {tgt.title if tgt else target_id} ({what or pipes.label(event)}, {who})", title="Roads")
    return road


def _exit_name(town: Town, board: str, route: str) -> str:
    """A Review board's exit by its route, in words (`to-development` → `exit To development`)."""
    from orkcraft.realm import team
    spec = town.custom_specs.get(board)
    names = {e.id: e.name for e in team.exits_of((spec or {}).get("config") or {})} if route else {}
    return f"exit {names[route]}" if route in names else ""


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
