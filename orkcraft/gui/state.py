"""What the GUI shows of the town, as plain data: one snapshot the page draws from.

Pure functions over a `core.Town` and its roster. The host sends a fresh snapshot whenever the town
changes; the page keeps it in signals, so only what changed is drawn again. Nothing here picks the
look: the page drops pictographs and words resources the Office way (`modes.RESOURCES`), and a
text that may carry emoji comes twice, as it is and `_plain` (`modes.strip_emoji`).

    snapshot(town, muster, treasury)   # {"project", "hud", "orkspaces", "buildings", "roads", "alerts"}
"""
from __future__ import annotations

import time
from typing import Any

from orkcraft import schedule
from orkcraft.core import treasury as tr
from orkcraft.core.roster import Muster
from orkcraft.core.town import Town
from orkcraft.realm import catalog, modes, pipes
from orkcraft.scroll import road_key

HUT_WIDTHS = [40, 40, 40]      # characters a status line may take on an Office hut card


def _ork(o) -> dict[str, Any]:
    return {"name": o.name, "kind": o.kind, "status": o.status, "lead": o.lead, "scheme": o.scheme,
            "tier": o.tier or "", "role": o.role}


def _hut_lines(town: Town, building_id: str) -> list[str]:
    """A building's live status lines (up to three): its worker says them (`mini_status`, else the
    TUI hut's `hut_lines`); a type without a worker has none in the GUI yet."""
    w = town.workers.get(building_id)
    mini, lines_of = getattr(w, "mini_status", None), getattr(w, "hut_lines", None)
    if mini is None and lines_of is None:
        return []
    try:
        lines = mini() if mini is not None else lines_of(HUT_WIDTHS)
        return [str(x) for x in lines if str(x).strip()][:3]
    except Exception:          # a status line never takes the town down
        return []


def buildings(town: Town, muster: Muster) -> list[dict[str, Any]]:
    out = []
    for bs in town.scroll.buildings:
        if bs.demolished:
            continue
        spec = town.spec_of(bs.id)
        garrison = muster.roster.garrison(bs.id)
        asking = next((o for o in garrison if o.alert is not None), None)
        since = muster.alert_first_seen.get(asking.alert.id) if asking else None
        worker = town.workers.get(bs.id)
        out.append({
            "id": bs.id, "title": bs.title, "icon": bs.icon,
            "type": catalog.type_of(spec).id if spec else bs.preset_ref or bs.id,
            "hut": list(bs.hut) if bs.hut else None,
            "status": (lines := _hut_lines(town, bs.id)),
            "status_plain": [modes.strip_emoji(x) for x in lines],
            "state": worker.status() if worker is not None else "",
            "garrison": [_ork(o) for o in garrison],
            "alert": {"id": asking.alert.id, "title": asking.alert.title,
                      "waited": round(time.monotonic() - since, 1) if since else 0.0} if asking else None,
            "has_worker": worker is not None,
        })
    return out


def roads(town: Town) -> list[dict[str, Any]]:
    """Every road as an edge: from its source to the building that keeps it (a road is incoming). Its
    `id` is the town-wide key (`scroll.road_key`): a road's own id is only unique in its building."""
    out = []
    for bs in town.scroll.buildings:
        if bs.demolished:
            continue
        for r in bs.roads:
            out.append({"id": road_key(bs.id, r.id), "road": r.id, "from": r.source, "to": bs.id, "event": r.event,
                        "label": r.label or pipes.label(r.event), "handler": r.handler or ""})
    return out


def orkspaces(town: Town, muster: Muster) -> list[dict[str, Any]]:
    out = []
    for o in town.scroll.orkspaces:
        out.append({"id": o.id, "name": o.name, "icon": o.icon, "biome": o.biome, "hotkey": o.hotkey,
                    "buildings": list(o.buildings), "questions": len(muster.questions_of(o.id))})
    return out


def hud(town: Town, muster: Muster, treasury: tr.Treasury, limits: list | None = None) -> dict[str, Any]:
    gold, gold_level, lumber, lumber_level = treasury.resources()
    quota, quota_level, show_gold = tr.quota(town.machine, limits or [])
    return {
        "gold": gold, "gold_level": gold_level, "show_gold": show_gold,
        "lumber": lumber, "lumber_level": lumber_level,
        "quota": quota, "quota_level": quota_level,
        "supply": muster.roster.active, "supply_max": town.scroll.budget.supply_max_workers,
        "alerts": len(muster.roster.alerts),
        "hour": (hour := schedule.status(town.machine)),
        "hour_plain": modes.strip_emoji(hour),
        "quiet": schedule.quiet_now(town.machine),
    }


def look(town: Town) -> str:
    """The look the page wears (`office` or `camp`): Shift is Office in office hours (schedule.py).
    The GUI draws Office only so far, so the page keeps `office` until Camp lands."""
    return "office" if schedule.plain_now(town.machine) else "camp"


def snapshot(town: Town, muster: Muster, treasury: tr.Treasury, limits: list | None = None) -> dict[str, Any]:
    return {
        "project": town.scroll.meta.get("project_name") or town.repo_root.name,
        "repo": str(town.repo_root),
        "demo": bool(town.demo),
        "look": look(town),
        "resources": {k: v[1] for k, v in modes.RESOURCES.items()},
        "active_orkspace": town.scroll.active_orkspace_id,
        "orkspaces": orkspaces(town, muster),
        "buildings": buildings(town, muster),
        "roads": roads(town),
        "hud": hud(town, muster, treasury, limits),
    }
