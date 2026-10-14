"""The cart's waybill, minimal (docs/design/cart-waybill.md §2, pulled into P0 by decisions-2026-10.md §13.1): a task's
whole way so far — each building it stopped at, the ork that worked on it there, the tokens and money spent there and
how long it stayed — read from what the cart already carries (its payload's `trail` of hops, realm/pipes.py) and from
the town's record of carts on the roads. Nothing is estimated: a number no hop recorded is None, and the page says
"not recorded".

    waybill(town, cart="<road key>@<at>")    a cart on a road (the snapshot's cart id)
    waybill(town, building="pool")           the newest cart into a building (its steward's bubble)
    waybill(town, building="pool", task="t1")   an Agent pool's task (an ork's console, its Task tab)
"""
from __future__ import annotations

import datetime as dt
from typing import Any

from orkcraft.realm import pipes
from orkcraft.scroll import road_key


def _title_of(town, bid: str) -> str:
    b = next((x for x in town.scroll.buildings if x.id == bid), None)
    return b.title if b is not None else bid


def _clock(at: str) -> str:
    try:
        return dt.datetime.fromisoformat(at).strftime("%H:%M")
    except (TypeError, ValueError):
        return ""


def _find(town, cart: str = "", building: str = ""):
    every = list(getattr(getattr(town, "roads", None), "carts", []) or [])
    if cart:
        key, _, at = cart.rpartition("@")
        for c in reversed(every):
            if road_key(c.target, c.road_id) == key and f"{c.at:.3f}" == at:
                return c
        return None
    return next((c for c in reversed(every) if c.target == building), None) if building else None


def _stop(town, h: pipes.Hop) -> dict[str, Any]:
    return {"building": h.building, "title": _title_of(town, h.building), "ork": h.orc, "kind": h.kind,
            "tokens": h.tokens, "cost": h.cost, "ms": h.ms, "at": _clock(h.at), "outcome": h.outcome, "model": h.model}


def _task(town, building: str, task: str) -> dict[str, Any] | None:
    """An Agent pool's task: the stops before it came, and its own here."""
    w = getattr(town, "workers", {}).get(building)
    t = w.state.task(task) if w is not None and hasattr(w, "state") and hasattr(w.state, "task") else None
    if t is None:
        return None
    hops = [pipes.Hop(**h) if isinstance(h, dict) else h for h in t.trail or []]
    stops = [_stop(town, h) for h in hops]
    stops.append({"building": building, "title": _title_of(town, building), "ork": t.orc, "kind": "agent",
                  "tokens": t.tokens, "cost": t.cost_usd, "ms": None, "at": "", "outcome": t.status, "model": ""})
    toks = [s["tokens"] for s in stops if s["tokens"] is not None]
    costs = [s["cost"] for s in stops if s["cost"] is not None]
    times = [s["ms"] for s in stops if s["ms"] is not None]
    return {"title": t.title, "ref": t.ref, "source": t.source, "source_title": _title_of(town, t.source) if t.source else "",
            "stops": stops, "now": {"building": building, "title": _title_of(town, building), "status": t.status},
            "tokens": sum(toks) if toks else None, "cost": round(sum(costs), 4) if costs else None,
            "ms": sum(times) if times else None}


def waybill(town, cart: str = "", building: str = "", task: str = "") -> dict[str, Any] | None:
    """The waybill of one cart, or None when the town has no such cart."""
    if building and task:
        try:
            return _task(town, building, task)
        except TypeError:                  # an older trail that does not read as hops
            return None
    c = _find(town, cart, building)
    if c is None:
        return None
    p: pipes.Payload = c.payload
    stops = [_stop(town, h) for h in p.trail or ()]
    tokens, cost = pipes.trail_totals(p.trail or ())
    times = [h.ms for h in p.trail or () if h.ms is not None]
    return {
        "title": p.title or "", "ref": p.ref or "", "source": c.source, "source_title": _title_of(town, c.source),
        "stops": stops,
        # where it is now: the building it is going to or stands at, and how it stands there
        "now": {"building": c.target, "title": _title_of(town, c.target), "status": c.status},
        "tokens": tokens, "cost": cost, "ms": sum(times) if times else None,
    }
