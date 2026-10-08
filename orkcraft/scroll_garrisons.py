"""Town Scroll edits of orkspaces and garrisons (the UI calls these; they keep the cross-references valid).

Part of orkcraft.scroll, which re-exports every name here: import it from there."""
from __future__ import annotations

from typing import Any

from orkcraft.realm.looks import kind_icon
from orkcraft.scroll import (BIOMES, DEFAULT_HARNESS, MAX_GARRISON, TRIGGER_TYPES, BuildingSpec, OrcSpec, Orkspace,
                             Presets, TownScroll, building_from_preset)
from orkcraft.scroll_checks import orc_problems

# -- orkspace operations (the UI calls these; they keep the cross-references valid) ---------------------------

HOTKEYS = tuple(f"F{i}" for i in range(1, 9))
MAX_ORKSPACES = len(HOTKEYS)


def ensure_presets(scroll: TownScroll, presets: Presets) -> list[str]:
    """Add registry buildings the scroll does not know yet (demolished, in the first orkspace).

    Buildings whose preset left the registry are kept in the file untouched. Returns the added ids.
    """
    known = {b.id for b in scroll.buildings}
    added = []
    for pid, p in presets.items():
        if pid in known:
            b = scroll.building(pid)
            if b is not None and (b.preset_ref.startswith("core:") or b.preset_ref.startswith("legacy:")):
                b.title = p.get("title", b.title)
                b.icon = p.get("icon", b.icon)
                lead = b.garrison.steward          # a resident renamed (Chieftain → Warchief): its id stays
                if lead is not None and lead.name in p.get("was", ()):
                    lead.name = p.get("orc", lead.name)
            continue
        b = building_from_preset(pid, presets)
        b.demolished = True
        scroll.buildings.append(b)
        scroll.orkspaces[0].buildings.append(b.id)
        added.append(b.id)
    return added


def _slug(name: str) -> str:
    out = "".join(c if c.isascii() and (c.isalnum() or c in "_-") else "_" for c in name.strip().lower())
    out = out.strip("_-")[:64]
    return out or "camp"


def new_orkspace(scroll: TownScroll, name: str, biome: str = "forest", icon: str = "⛺") -> Orkspace:
    """Append an empty orkspace with a unique id and the first free hotkey F1–F8.

    Raises ValueError for an unknown biome, an empty name or when all eight hotkeys are taken.
    """
    name = name.strip()
    if not name:
        raise ValueError("an orkspace needs a name")
    if biome not in BIOMES:
        raise ValueError(f"unknown biome {biome!r}")
    taken = {o.hotkey for o in scroll.orkspaces}
    hotkey = next((k for k in HOTKEYS if k not in taken), None)
    if hotkey is None or len(scroll.orkspaces) >= MAX_ORKSPACES:
        raise ValueError(f"at most {MAX_ORKSPACES} orkspaces (F1–F8)")
    base = _slug(name)
    ids = {o.id for o in scroll.orkspaces}
    oid, n = base, 2
    while oid in ids:
        suffix = f"_{n}"
        oid, n = base[: 64 - len(suffix)] + suffix, n + 1
    ork = Orkspace(oid, name, biome, icon, hotkey)
    scroll.orkspaces.append(ork)
    return ork


def orkspace_by_hotkey(scroll: TownScroll, hotkey: str) -> Orkspace | None:
    key = hotkey.upper()
    return next((o for o in scroll.orkspaces if o.hotkey == key), None)


def move_building(scroll: TownScroll, building_id: str, orkspace_id: str) -> None:
    """Put a building on another canvas (a building lives in exactly one orkspace) and raise it there."""
    target = scroll.orkspace(orkspace_id)
    b = scroll.building(building_id)
    if target is None or b is None:
        raise ValueError(f"unknown orkspace {orkspace_id!r} or building {building_id!r}")
    for o in scroll.orkspaces:
        if o is target:
            continue
        if building_id in o.buildings:
            o.buildings.remove(building_id)
        if building_id in o.window_order:
            o.window_order.remove(building_id)
        if o.active_building == building_id:
            o.active_building = None
    if building_id not in target.buildings:
        target.buildings.append(building_id)
    b.demolished = False


def remove_orkspace(scroll: TownScroll, orkspace_id: str) -> None:
    """Delete an empty orkspace; never the last one. The active one falls back to the first left."""
    ork = scroll.orkspace(orkspace_id)
    if ork is None:
        raise ValueError(f"unknown orkspace {orkspace_id!r}")
    if len(scroll.orkspaces) == 1:
        raise ValueError("the last orkspace cannot be removed")
    if ork.buildings:
        raise ValueError(f"{ork.name} still holds buildings: move or demolish them first")
    scroll.orkspaces.remove(ork)
    if scroll.active_orkspace_id == orkspace_id:
        scroll.active_orkspace_id = scroll.orkspaces[0].id


# -- garrison operations -----------------------------------------------------------------------------------

def _orc_id(name: str) -> str:
    oid = _slug(name)
    return "orc" if oid == "camp" else oid  # _slug's fallback for names without latin letters


def _building(scroll: TownScroll, building_id: str) -> BuildingSpec:
    b = scroll.building(building_id)
    if b is None:
        raise ValueError(f"unknown building {building_id!r}")
    return b


def _unique_orc_id(b: BuildingSpec, name: str) -> str:
    base = _orc_id(name)
    ids = {m.id for m in b.garrison.members}
    oid, n = base, 2
    while oid in ids:
        suffix = f"_{n}"
        oid, n = base[: 64 - len(suffix)] + suffix, n + 1
    return oid


def add_handler(scroll: TownScroll, building_id: str, name: str, *, kind: str = "agent", role: str = "",
                orders: str = "", harness: list[dict] | None = None, chain: list[dict] | None = None,
                script: dict | None = None, run: dict | None = None, why: str = "",
                trigger: dict | None = None, avatar: str | None = None) -> OrcSpec:
    """Add a handler (no roads yet — `subscribe(..., handler=id)` gives it some).

    Raises ValueError for an unknown building, an empty name, a full garrison or an orc that
    breaks the schema or the kind rules (`orc_problems`). A script handler starts as `draft`
    until the operator reviews its code.
    """
    b = _building(scroll, building_id)
    name = name.strip()
    if not name:
        raise ValueError("an ork needs a name")
    if len(b.garrison.members) >= MAX_GARRISON:
        raise ValueError(f"{b.title}: the garrison is full ({MAX_GARRISON})")
    if trigger is not None and trigger.get("type") not in TRIGGER_TYPES:
        raise ValueError(f"unknown trigger type {trigger.get('type')!r}")
    if harness is None:
        harness = [] if kind in ("chain", "script", "steward") else [dict(s) for s in DEFAULT_HARNESS]
    orc = OrcSpec(
        _unique_orc_id(b, name), name, role=role.strip(), orders=orders.strip(), kind=kind,
        avatar=avatar or kind_icon(kind),
        status="draft" if script is not None and not script.get("reviewed") else "idle",
        trigger=dict(trigger) if trigger else {"type": "pipe" if kind != "agent" else "on_demand"},
        harness=[dict(s) for s in harness], chain=[dict(op) for op in chain or []],
        script=dict(script) if script else None, run=dict(run) if run else None, why=why.strip(),
    )
    problems = orc_problems(orc.to_dict())
    if problems:
        raise ValueError("; ".join(problems))
    b.garrison.handlers.append(orc)
    return orc


def remove_handler(scroll: TownScroll, building_id: str, orc_id: str) -> list[str]:
    """Remove a handler; its roads stay as plain roads. Returns those road ids."""
    b = _building(scroll, building_id)
    orc = b.garrison.handler(orc_id)
    if orc is None:
        if b.garrison.steward and b.garrison.steward.id == orc_id:
            raise ValueError(f"{b.garrison.steward.name} is the steward of {b.title}: replace it, don't dismiss it")
        raise ValueError(f"{b.title}: no ork {orc_id!r}")
    b.garrison.handlers.remove(orc)
    freed = []
    for r in b.roads_of(orc_id):
        r.handler = None
        freed.append(r.id)
    return freed


def set_steward(scroll: TownScroll, building_id: str, orc_id: str) -> None:
    """Promote a handler to steward; the old steward becomes a handler without roads.

    Raises ValueError when the orc still works on roads (a steward watches the building, it
    does not handle roads) — unsubscribe them first.
    """
    b = _building(scroll, building_id)
    g = b.garrison
    if g.steward and g.steward.id == orc_id:
        return
    orc = g.handler(orc_id)
    if orc is None:
        raise ValueError(f"unknown building {building_id!r} or ork {orc_id!r}")
    if b.roads_of(orc_id):
        raise ValueError(f"{orc.name} works on roads of {b.title}: move them to another handler first")
    idx = g.handlers.index(orc)
    g.handlers.remove(orc)
    if g.steward is not None:
        g.handlers.insert(idx, g.steward)
    g.steward = orc


def update_orc(scroll: TownScroll, building_id: str, orc_id: str, **changes: Any) -> OrcSpec:
    """Change fields of a steward or handler (orders, trigger, kind, harness, chain, run, …),
    all or nothing: an orc that would break the rules is refused with ValueError."""
    b = _building(scroll, building_id)
    orc = b.garrison.orc(orc_id)
    if orc is None:
        raise ValueError(f"{b.title}: no ork {orc_id!r}")
    unknown = set(changes) - set(OrcSpec.__dataclass_fields__) - {"id"}
    if unknown or "id" in changes:
        raise ValueError(f"cannot change {', '.join(sorted(unknown | ({'id'} & set(changes))))}")
    candidate = {**orc.to_dict(), **changes}
    candidate = {k: v for k, v in candidate.items() if v is not None}
    problems = orc_problems(candidate)
    if problems:
        raise ValueError("; ".join(problems))
    for k, v in changes.items():
        setattr(orc, k, v)
    return orc


# v2 operations, kept for the current UI: recruit adds an agent handler (or the steward when
# there is none), dismiss removes a handler.

def recruit(scroll: TownScroll, building_id: str, name: str, role: str = "", orders: str = "",
            trigger: dict | None = None, tier: str | None = None) -> OrcSpec:
    """`tier` (elder | warrior | laborer, realm/tiers.py) picks the model; None leaves the CLI's."""
    from orkcraft.realm import tiers
    b = _building(scroll, building_id)
    harness = tiers.with_tier([dict(s) for s in DEFAULT_HARNESS], tier) if tier else None
    orc = add_handler(scroll, building_id, name, role=role, orders=orders,
                      trigger=trigger or {"type": "on_demand"}, harness=harness)
    if b.garrison.steward is None:
        b.garrison.handlers.remove(orc)
        b.garrison.steward = orc
    return orc


def dismiss_orc(scroll: TownScroll, building_id: str, orc_id: str) -> None:
    b = _building(scroll, building_id)
    if b.garrison.steward and b.garrison.steward.id == orc_id:
        raise ValueError(f"{b.garrison.steward.name} leads {b.title} and cannot be dismissed")
    remove_handler(scroll, building_id, orc_id)

