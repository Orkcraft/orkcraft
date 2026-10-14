"""🥩 The ork slots (docs/design/ork-console.md §8): the town's one list of orks at work or waiting on the person.

    slots.summary(town, muster)   → {"working", "limit", "asks", "held", "errors", "fire", "rows"}
    slots.console(town, muster, key) → the ork's console unfolded (§7): its row, and what its building tells of it —
                                    its role's sessions, its cart, its answer (§20), its terminal, its history (runs
                                    with their cost); a building that keeps no such record gives the row alone

One row per ork, in the one status of realm/status.py (§5) — the same marks the town draws — with its building, the
cart it works on, how long it has been at it (or has waited), its spend, its AI tool, the way to stop it softly (⏹,
§9) and, when it asks, the way to answer it. An ork stopped on its own error (`!`) has a row with what broke
(`error`) and `clear`; one held for a limit (⏳) has its wait: until when, and Run anyway (§19). Waiting first, then
the longest running: a long session that never asks is worth a look too.

The rows come from three places, each ork once:
    a building that keeps its own orks (an Agent pool: `ork_slots()`, core/workers/barracks_status.py)
    the roster: garrison orks, the sessions of the War Tent, the Council (core/roster.py)
    every agent process still running (realm/halt.py), named "<building>/<ork>", that neither of those named

Stop all (`halt` in the GUI) is not here: it is one button beside the list, and its first row in the face.
No face here: the GUI serves `summary` in its snapshot (gui/state.py).
"""
from __future__ import annotations

import time
from typing import Any

from orkcraft.core.roster import Muster
from orkcraft.realm import halt, status
from orkcraft.realm.orcs import RESIDENT, WORKER


def _title(town, building_id: str | None) -> str:
    spec = town.scroll.building(building_id) if building_id and town.scroll is not None else None
    return getattr(spec, "title", "") or ""


def _pool_rows(town, now: float) -> tuple[list[dict], set[str], set[str]]:
    """The rows of the buildings that keep their own orks; their keys; the buildings that burn."""
    rows, keys, burning = [], set(), set()
    for bid, w in list(getattr(town, "workers", {}).items()):
        if hasattr(w, "building_status"):
            try:
                if w.building_status() == status.BURNING:
                    burning.add(bid)
            except Exception:              # a building's status never breaks the list
                pass
        if not hasattr(w, "ork_slots"):
            continue
        try:
            got = w.ork_slots(now)
        except Exception:
            continue
        rows += got
        keys |= {r["key"] for r in got}
    return rows, keys, burning


def _roster_rows(town, muster: Muster, skip: set[str], now: float) -> list[dict]:
    rows = []
    mono = time.monotonic()
    for o in muster.roster.agents:
        if o.status not in ("busy", "alert") or (o.building or "") in skip:
            continue
        a = o.alert
        s = status.OrkStatus(o.name, status.ASKS if a is not None else status.THINKING, _title(town, o.building),
                             cart=o.task or "")
        seen = muster.alert_first_seen.get(a.id) if a is not None else None
        term = o.session if o.category == RESIDENT else (o.ref if o.category == WORKER else "")
        rows.append({**s.as_dict(now=now), "key": o.ref or o.name, "building_id": o.building or "",
                     "since_s": round(mono - seen) if seen is not None else None, "spend": 0.0,
                     "tool": ",".join(str(h.get("harness") or "") for h in o.harness if isinstance(h, dict)) or "",
                     "stop": {"command": "term.interrupt", "args": {"key": term}} if term and a is None else None,
                     "answer": {"kind": "alert", "id": a.id, "question": a.title,
                                "options": [[k, label] for k, label in a.options]} if a is not None else None})
    return rows


def _process_rows(town, known: set[str], now: float) -> list[dict]:
    """An agent process no one else named: a road's handler, a librarian, a review."""
    rows, seen = [], set()
    for who, agent in halt.live():
        if not agent or "/" not in who or who.lower() in known or who.lower() in seen:
            continue
        seen.add(who.lower())
        bid, ork = who.split("/", 1)
        s = status.OrkStatus(ork[:1].upper() + ork[1:], status.THINKING, _title(town, bid))
        rows.append({**s.as_dict(now=now), "key": who.lower(), "building_id": bid, "since_s": None, "spend": 0.0,
                     "tool": "", "stop": None, "answer": None})
    return rows


def _order(row: dict) -> tuple:
    return (-row.get("attention", 0), -(row.get("since_s") or 0), row.get("name", ""))


def rows(town, muster: Muster, now: float | None = None) -> tuple[list[dict], set[str]]:
    now = time.time() if now is None else now
    pool, keys, burning = _pool_rows(town, now)
    asking_pools = {r["building_id"] for r in pool if r["state"] == status.ASKS}
    # a building that keeps its own orks names them itself; its steward's 🔥 is the same question as its ork's ❓
    roster = _roster_rows(town, muster, asking_pools, now)
    roster = [r for r in roster if r["key"].lower() not in keys]
    known = keys | {r["key"].lower() for r in roster}
    found = pool + roster + _process_rows(town, known, now)
    burning |= {r["building_id"] for r in roster if r["state"] == status.ASKS and r["building_id"]}
    return sorted(found, key=_order), burning


def summary(town, muster: Muster, now: float | None = None) -> dict[str, Any]:
    found, burning = rows(town, muster, now)
    limit = getattr(getattr(town.scroll, "budget", None), "supply_max_workers", 0) if town.scroll is not None else 0
    count = {state: sum(1 for r in found if r["state"] == state) for state in (status.ASKS, status.HELD, status.ERROR)}
    # held work takes no slot (town-time.md §4); an ork stopped on its error holds none either
    return {"working": len(found) - sum(count.values()), "limit": limit, "asks": count[status.ASKS],
            "held": count[status.HELD], "errors": count[status.ERROR], "fire": len(burning), "rows": found}


def console(town, muster: Muster, key: str, now: float | None = None) -> dict[str, Any] | None:
    """The console of the ork `key` (a row's), unfolded: its row (None when it is not at work and not asking) and,
    from a building that keeps its own orks (`ork_console`, core/workers/barracks_console.py), the rest. An ork at
    rest still has a console: its history and its terminal."""
    now = time.time() if now is None else now
    found, _burning = rows(town, muster, now)
    row = next((r for r in found if r["key"] == key), None)
    bid, _, ork = (key or "").partition("/")
    w = getattr(town, "workers", {}).get(bid) if ork else None
    more = None
    if w is not None and hasattr(w, "ork_console"):
        orc = next((o for o in w.state.orcs if o.name.lower() == ork), None)
        try:
            more = w.ork_console(orc.name, now) if orc is not None else None
        except Exception:                  # a building's record never breaks the console
            more = None
    if row is None and more is None:
        return None
    if row is None:                        # at rest: its one status from its building
        st = more["state"]
        row = {**st, "key": key, "building_id": bid, "since_s": None, "spend": 0.0, "tool": more.get("tool", ""),
               "stop": None, "answer": None}
    return {"key": key, "row": row, **(more or {"role": "", "sessions": [], "cart": None, "answer": None,
                                                 "terminal": None, "history": [], "totals": None})}
