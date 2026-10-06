"""What the GUI shows of the town, as plain data: one snapshot the page draws from.

Pure functions over a `core.Town` and its roster. The host sends a fresh snapshot whenever the town
changes; the page keeps it in signals, so only what changed is drawn again. The page has one look,
Office (`look` stays in the snapshot for the phone, docs/design/mobile.md): it drops pictographs and words resources the Office way (`modes.RESOURCES`), and a
text that may carry emoji comes twice, as it is and `_plain` (in Office's words, without emoji:
`modes.text`). `words` is the glossary (`realm/lexicon.py`) the page says its own labels in.

    snapshot(town, muster, treasury)   # {"project", "hud", "orkspaces", "buildings", "roads", "alerts"}
"""
from __future__ import annotations

import re

import time
from pathlib import Path
from typing import Any

from orkcraft import schedule
from orkcraft.core import treasury as tr
from orkcraft.core.roster import Muster
from orkcraft.core.town import Town
from orkcraft.gui import views
from orkcraft.realm import catalog, lexicon, modes, pipes
from orkcraft.scroll import road_key

HUT_WIDTHS = [40, 40, 40]      # characters a status line may take on an Office hut card
PAGES = Path(__file__).parent / "static" / "js" / "buildings"     # a type's own page code: <type>.js


def _ork(o) -> dict[str, Any]:
    return {"name": o.name, "kind": o.kind, "status": o.status, "lead": o.lead, "scheme": o.scheme,
            "tier": o.tier or "", "role": o.role, "ref": o.ref, "session": o.session}


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


def _card(type_id: str, worker) -> Any:
    """What a type's hut card shows (closed), from its view's `card(worker)`: small JSON, in every
    snapshot. None for a type without one (the card shows the status lines)."""
    view = views.of(type_id) if worker is not None else None
    card = getattr(view, "card", None)
    if card is None:
        return None
    try:
        return card(worker)
    except Exception:          # a card never takes the town down
        return None


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
            "type": (type_id := catalog.type_of(spec).id if spec else bs.preset_ref or bs.id),
            "hut": list(bs.hut) if bs.hut else None,
            "pinned": bool(bs.pinned),
            "level": bs.level or 0, "goal": bs.aim,              # the flag on its roof (docs/design/growth.md §5)
            "status": (lines := _hut_lines(town, bs.id)),
            "status_plain": [modes.text(x, modes.OFFICE) for x in lines],
            "state": worker.status() if worker is not None else "",
            "garrison": [_ork(o) for o in garrison],
            "alert": {"id": asking.alert.id, "title": asking.alert.title,
                      "waited": round(time.monotonic() - since, 1) if since else 0.0} if asking else None,
            "has_worker": worker is not None,
            "card": _card(type_id, worker),
            "page": (PAGES / f"{type_id}.js").is_file(),
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
            flt = r.filter or {}
            out.append({"id": road_key(bs.id, r.id), "road": r.id, "from": r.source, "to": bs.id, "event": r.event,
                        "label": r.label or pipes.label(r.event), "handler": r.handler or "",
                        "sign": sign(r) if flt.get("route") or "-" in (r.label or "") else "", "returns": bool(flt.get("returns"))})
    return out


def sign(road) -> str:
    """What the sign on a road says — one that waits for routes, or one named in words (a kebab-case label,
    `new-meeting`): its label in words (`task-for-human` → `task for human`), else its routes."""
    words = (road.label or ", ".join(str(x) for x in (road.filter or {}).get("route") or [])).replace("-", " ")
    return words.replace("_", " ").strip()


def outcome(report: str) -> str:
    """What a Barracks' report says came of the task: its first line after `**Task** — who did it`."""
    for ln in (report or "").splitlines():
        ln = ln.strip()
        if not ln or re.match(r"^\*\*.*\*\* — ", ln):
            continue
        return ln.strip(" #*")[:80]
    return ""


CART_SHOWN_S = 12.0           # a cart stays in the snapshot this long after it left (the page animates it)


def carts(town: Town, now: float | None = None) -> list[dict[str, Any]]:
    """The carts that left lately: on which road, what they carry, how long ago, how long the road takes
    (`travel`; the page draws each moving from gate to gate). A filtered one turns back at the source."""
    from orkcraft.gui.views.watchtower import subject
    engine = getattr(town, "roads", None)
    now = time.monotonic() if now is None else now
    out = []
    for c in list(getattr(engine, "carts", []) or [])[-40:]:
        age = now - c.at
        if age < 0 or age > CART_SHOWN_S:
            continue
        title = c.payload.title or ""
        spec = town.custom_specs.get(c.source)
        if spec is not None and catalog.type_of(spec).id == "watchtower":
            title = subject(title)                   # the Inbox's card says who sent it and where from
        elif c.payload.mode == "pool.done":
            title = outcome(c.payload.value) or title  # done work reads as what came of it
        out.append({"id": f"{road_key(c.target, c.road_id)}@{c.at:.3f}", "road": road_key(c.target, c.road_id),
                    "status": c.status, "title": modes.strip_emoji(title)[:80], "age": round(age, 2)})
    return out


def orkspaces(town: Town, muster: Muster) -> list[dict[str, Any]]:
    out = []
    for o in town.scroll.orkspaces:
        ids = set(o.buildings)
        standing = [b for b in town.scroll.buildings if b.id in ids and not b.demolished and b.id != "town_hall"]
        out.append({"id": o.id, "name": o.name, "icon": o.icon, "biome": o.biome, "hotkey": o.hotkey,
                    "buildings": list(o.buildings), "questions": len(muster.questions_of(o.id)),
                    "count": len(standing),                       # what the War Map's land says and dots
                    "working": sum(1 for x in muster.roster.orcs if x.building in ids and x.status == "busy")})
    return out


def hud(town: Town, muster: Muster, treasury: tr.Treasury, limits: list | None = None) -> dict[str, Any]:
    gold, gold_level, lumber, lumber_level = treasury.resources()
    quota, quota_level, show_gold = tr.quota(town.machine, limits or [])
    return {
        "gold": gold, "gold_level": gold_level, "show_gold": show_gold,
        "lumber": lumber, "lumber_level": lumber_level,
        "quota": quota, "quota_level": quota_level,
        "supply": muster.roster.active, "supply_max": town.scroll.budget.supply_max_workers,
        "agents_working": muster.roster.working, "agents": len(muster.roster.agents),
        "alerts": len(muster.roster.alerts),
        "hour": (hour := schedule.status(town.machine)),
        "hour_plain": modes.text(hour, modes.OFFICE),
        "quiet": schedule.quiet_now(town.machine),
    }


def sessions(live) -> list[dict[str, Any]]:
    """The War Tent: every session this run opened."""
    if live is None:
        return []
    return [{"key": s.key, "harness": s.harness, "title": modes.strip_emoji(s.title), "running": s.running,
             "exit_code": s.exit_code, "ork": s.ork, "ticket": s.ticket or ""} for s in live.live.values()]


def _advice(night, alert) -> dict[str, Any] | None:
    d = night.advice_for(alert) if night is not None else None
    return {"key": d.key, "why": modes.strip_emoji(d.why), "warn": modes.strip_emoji(d.warn)} if d else None


def alerts(town: Town, muster: Muster, night=None) -> list[dict[str, Any]]:
    """The questions that wait for the person (Orders), the longest waiting first."""
    who = muster.who()
    found = list(muster.roster.alerts)
    seen = {a.id for a in found}
    found += [o.alert for o in muster.roster.orcs if o.alert is not None and o.alert.id not in seen]
    now = time.monotonic()
    found.sort(key=lambda a: muster.alert_first_seen.get(a.id, now))
    by_alert = {o.alert.id: o.building for o in muster.roster.orcs if o.alert is not None and o.building}
    return [{"id": a.id, "title": modes.strip_emoji(a.title), "context": list(a.context[-12:]),
             "options": [[k, modes.strip_emoji(label)] for k, label in a.options], "source": a.source, "ref": a.ref,
             "who": who.get(a.id, ""), "building": by_alert.get(a.id, ""), "advice": _advice(night, a),
             "waited": round(now - muster.alert_first_seen.get(a.id, now), 1)} for a in found]


def snapshot(town: Town, muster: Muster, treasury: tr.Treasury, limits: list | None = None,
             live=None, night=None) -> dict[str, Any]:
    return {
        "project": town.scroll.meta.get("project_name") or town.repo_root.name,
        "repo": str(town.repo_root),
        "demo": bool(town.demo),
        "look": "office",
        "resources": {k: v[1] for k, v in modes.RESOURCES.items()},
        "words": lexicon.table(),
        "active_orkspace": town.scroll.active_orkspace_id,
        "orkspaces": orkspaces(town, muster),
        "buildings": buildings(town, muster),
        "roads": roads(town),
        "carts": carts(town),
        "travel": float(getattr(town, "cart_travel_s", 0.0) or 0.0),
        "hud": hud(town, muster, treasury, limits),
        "sessions": sessions(live),
        "alerts": alerts(town, muster, night),
    }
