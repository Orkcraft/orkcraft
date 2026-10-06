"""Delivery as the core does it: the road engine over the `Town`, and what each of its callbacks
means — a cart delivered into a building, a handler's result, a run that ended.

The engine calls back through `town.call` (a face that draws on one thread hops there), so every
function here runs where the face wants it. They change the town, record what happened and
publish it: `DELIVERED`, `OUTPUT`, `CART`, `RUN`, `LOOT`. The face shows it.
"""
from __future__ import annotations

from pathlib import Path

from orkcraft import scroll
from orkcraft.core import bus
from orkcraft.realm import catalog, feedback, metrics, pipes, roads


def engine(town) -> roads.Engine:
    """The road engine with its callbacks on the town (read at call time, so a face may replace
    `town.call` and `town.budget_ok` after the town is built)."""
    return roads.Engine(
        lambda: town.scroll, town.repo_root,
        deliver=lambda target_id, payload: town.deliver(target_id, payload),
        on_output=lambda *a: output(town, *a),
        on_run=lambda run: ran(town, run),
        meta=lambda payload: meta(town, payload),
        on_cart=lambda cart: town.publish(bus.CART, cart=cart),
        budget_ok=lambda: bool(town.budget_ok()),
        call=lambda fn, *a: town.call(fn, *a),
        run_env={"ORKCRAFT_RUN": town.run_id},
        travel=lambda: getattr(town, "cart_travel_s", 0.0),
    )


def markdown_of(town, payload: pipes.Payload) -> tuple[str, str]:
    """(title, markdown) of what a road carries: a file's text, else the value itself."""
    if payload.kind == pipes.FILE:
        return pipes.read_file_payload(town.repo_root, payload.value)
    return payload.title or "report", payload.value


def _title(town, building_id: str) -> str:
    b = town.scroll.building(building_id) if town.scroll is not None else None
    return b.title if b is not None and b.title else building_id


def deliver(town, target_id: str, payload: pipes.Payload, title: str = "", markdown: str = "") -> None:
    """A cart arrives in `target_id`: the faces show it (`DELIVERED`), the building's worker takes
    it, a text cart into Loot is kept as a report, and the receiver's chronicle says so."""
    feedback.record_delivery(town.repo_root, target_id, payload.source)            # the session's graph
    t, md = (title, markdown) if markdown else markdown_of(town, payload)
    worker = town.worker(target_id)
    town.publish(bus.DELIVERED, building=target_id, payload=payload, title=t, markdown=md,
                 label=f"{_title(town, payload.source)} → {t}", worker=worker is not None)
    if worker is not None:
        worker.receive(payload, t, md)
    if target_id == "loot" and payload.kind == pipes.TEXT:
        path = pipes.write_loot(town.repo_root, payload.source, title or payload.title, markdown or payload.value)
        town.publish(bus.LOOT, path=str(path), source=payload.source)
        town.toast(f"📦 report saved: loot/pipes/{path.name}", title="Loot")
    town.record(target_id, "payload_received", kind=payload.kind, source=_title(town, payload.source))


def output(town, target_id: str, orc: scroll.OrcSpec, title: str, markdown: str,
           trail: tuple = (), ref: str = "") -> None:
    """A handler's result: a custom building shows it (`OUTPUT`), anywhere else it is kept as a
    Loot report. `trail` is every hop the result went through, the handler's own last."""
    if target_id in town.custom_specs:
        town.publish(bus.OUTPUT, building=target_id, orc=orc.id, title=title, markdown=markdown,
                     trail=tuple(trail), ref=ref)
        return
    path = pipes.write_loot(town.repo_root, target_id, title, markdown)
    town.publish(bus.LOOT, path=str(path), source=target_id)
    town.toast(f"📦 {title}: loot/pipes/{path.name}", title="Handler")


def ran(town, run: roads.HandlerRun) -> None:
    """A handler (or a building's own agent) finished: the Tally Crag counts it, the chronicle
    keeps it, and the faces mark it on the map (`RUN`)."""
    if run.outcome in ("done", "error"):         # every run of the camp, for the Tally Crag
        try:
            metrics.record_run(town.repo_root, run.target, run.outcome, run.cost_usd, run.tokens)
        except OSError:
            pass
    b = town.scroll.building(run.target) if town.scroll is not None else None
    orc = b.garrison.orc(run.orc_id) if b else None
    name = orc.name if orc else run.orc_id
    town.record(run.target, "handler_ran", by=name, orc=name, outcome=run.outcome, roads=len(run.roads))
    town.publish(bus.RUN, run=run, name=name)


def meta(town, payload: pipes.Payload) -> dict:
    """Type / status / subtype of the Markdown item a payload names (the source filter and the
    personal guard). Only the showcase sandbox indexes items; elsewhere the dict is empty and road
    filters on node_type / node_status do not match."""
    if town.graph is None:
        return {}
    ident = payload.value if payload.kind == pipes.NODE else ""
    if payload.kind == pipes.FILE and payload.value.endswith(".md"):
        ident = Path(payload.value).stem
    entity = town.graph.get_entity(ident) if ident else None
    if entity is None:
        return {}
    return {"type": entity.type, "status": entity.status, "title": entity.title,
            "subtype": "personal" if entity.is_personal else entity.subtype}


def emit(town, building_id: str, event_id: str, value: str, title: str = "",
         trail: tuple = (), ref: str = "", route: str = "") -> bool:
    """A typed building sends one of its events: only when a road carries it (with the trail of
    what it passes on, when it gives one, and the route it was given, when it was routed)."""
    spec = town.custom_specs.get(building_id)
    ev = catalog.type_of(spec).event(event_id) if spec else None
    if ev is not None:
        feedback.record_output(town.repo_root, building_id, event_id, value)      # what 👍 / 👎 rate
        if getattr(town, "lake", None) is not None:          # a road of it once went into a Lake building
            town.lake.follow(building_id, event_id, ev.kind, value, title)
    if ev is None or town.scroll is None or not scroll.has_outgoing(town.scroll, building_id, event_id):
        return False
    town.roads.emit(pipes.Payload(ev.kind, value, building_id, event_id, title, tuple(trail), ref, route))
    return True
