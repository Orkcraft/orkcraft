"""What the GUI shows of the town, as plain data: one snapshot the page draws from.

Pure functions over a `core.Town` and its roster. The host sends a fresh snapshot whenever the town
changes; the page keeps it in signals, so only what changed is drawn again. The page has two looks,
Camp and Office (`look`, the person's: docs/design/portrait.md §3; the phone reads it too); it drops
pictographs and words the resources (`modes.RESOURCES`), and a text that may carry emoji comes twice, as it is and `_plain` (in
today's words, without emoji: `modes.plain`). `words` are the old Camp spellings with today's words
(`realm/lexicon.py`), for the page's labels and the town's older titles.

    snapshot(town, muster, treasury)   # {"project", "hud", "orkspaces", "buildings", "roads", "alerts"}
"""
from __future__ import annotations

import re

import time
from pathlib import Path
from typing import Any

from orkcraft import schedule, settings
from orkcraft.env import getenv
from orkcraft.core import runners, slots
from orkcraft.core import treasury as tr
from orkcraft.core.roster import Muster
from orkcraft.core.town import Town
from orkcraft.gui import projects as gui_projects
from orkcraft.gui import views
from orkcraft.realm import card_docs, catalog, halt, lexicon, modes, motion, pipes, script_first, status, steward_models
from orkcraft.realm.buildings import TOWN_HALL
from orkcraft.scroll import road_key

HUT_WIDTHS = [40, 40, 40]      # characters a status line may take on an Office hut card
PAGES = Path(__file__).parent / "static" / "js" / "buildings"     # a type's own page code: <type>.js


def _ork(o, steward_rank: str = "") -> dict[str, Any]:
    """`rank`: the chevrons it wears when it comes out (js/visit.js): its tier, or for the steward that keeps the
    building, the tier its road rules run at (chosen, else its building's goal's) — how heavy a mind is at work."""
    return {"name": o.name, "kind": o.kind, "status": o.status, "lead": o.lead, "scheme": o.scheme,
            "tier": o.tier or "", "rank": o.tier or (steward_rank if o.lead else ""),
            "role": o.role, "ref": o.ref, "session": o.session}


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


def cart_ref(alert_id: str) -> str:
    """The short ref a waiting cart's chip shows (docs/design/town-readability.md §3, `#42 · Login form`): the last part
    of its question's id when that is a short key (`view:outputs:review:16307ea4` → `16307ea4`); "" for none (a
    terminal's prompt is not a cart)."""
    if alert_id.startswith("term:"):
        return ""
    last = alert_id.rsplit(":", 1)[-1]
    return last if 0 < len(last) <= 8 and last.replace("-", "").replace("_", "").isalnum() else ""


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
            "size": list(bs.hut_size) if bs.hut_size else None,   # its card stretched by the person (js/hut.js)
            "pinned": bool(bs.pinned),
            "folded": bool(bs.folded) and bs.id != TOWN_HALL,   # its title bar only (js/hut.js)
            "roads": catalog.type_of(spec).roads if spec else "free",   # "setup"/"none": no road handle (catalog)
            "card_doc": card_docs.current(type_id) if spec else None,     # its card's layout: this machine's, else shipped
            "level": bs.level or 0, "goal": bs.aim,              # the flag on its roof (docs/design/growth.md §5)
            "status": (lines := _hut_lines(town, bs.id)),
            "status_plain": [modes.plain(x) for x in lines],
            "state": worker.status() if worker is not None else "",
            # road rules are the steward's work, not orks: listed under it (`rules`), never drawn
            "garrison": [_ork(o, steward_models.tier_for(bs, "listen") or steward_models.level_of(bs))
                         for o in garrison if o.kind != "steward"],
            "rules": [{"ref": o.ref, "name": o.name, "status": o.status} for o in garrison if o.kind == "steward"],
            "alert": {"id": asking.alert.id, "title": asking.alert.title, "ref": cart_ref(asking.alert.id),
                      "waited": round(time.monotonic() - since, 1) if since else 0.0} if asking else None,
            "has_worker": worker is not None,
            # its work is code: no ork lives in it, one visits (docs/design/yards.md §2); `visit` is the host's
            "yard": bool(spec) and script_first.is_script_first(spec, bs),
            "visit": "",
            "paused": _paused(worker),
            "card": _card(type_id, worker),
            # its quick actions, on its command card in the Warchief's line (js/warchief.js): each opens its own
            # small window or just does it, never the whole building
            "quick": [{"id": a.id, "label": a.label} for a in catalog.quick_actions_of(spec)] if spec else [],
            "page": (PAGES / f"{type_id}.js").is_file(),
            # its steward takes words on its card (core/keeper.py, gui/keeper.py): it keeps settings, and a model
            # answers (the demo's calls none)
            "keeper": bs.id in town.custom_specs and not (town.demo and runners.KEEPER_RUNNER is None),
            "loose": _loose(worker),                       # its exits with no road yet: stubs on the map
            "signal": None,                                # an ork's own ! or ⏳ (`signals`, from the 🥩 rows)
        })
    return out


def signals(found: list[dict[str, Any]], rows: list[dict[str, Any]]) -> None:
    """Each building's ork stopped on its own error (`!`) or held for a limit (⏳), from the 🥩 rows (core/slots.py),
    for the ork that comes out of it (js/visit.js): the error first. A question is the ork's ❓ (`alert`); the
    building burns only when it is broken itself (docs/design/town-readability.md §4)."""
    by = {b["id"]: b for b in found}
    for kind, state in (("error", status.ERROR), ("held", status.HELD)):
        for r in rows:
            b = by.get(r.get("building_id") or "")
            if b is not None and b.get("signal") is None and r.get("state") == state:
                b["signal"] = {"kind": kind, "key": r["key"], "name": r["name"], "line": r["line"]}


def visit(b: dict[str, Any], jobs) -> str:
    """Why an ork is in a yard now (docs/design/yards.md §2b): "alert" while it asks, "wake" while a wake's
    proposal waits, "asked" while a job of its own runs or waits (the keeper, Redesign, Ork setup); "" for none
    and for every building that is no yard."""
    if not b.get("yard"):
        return ""
    if b.get("alert"):
        return "alert"
    mine = [j for j in jobs if j.get("building") == b["id"]]
    if any(j.get("_wake") for j in mine):
        return "wake"
    return "asked" if mine else ""


def _loose(worker) -> list[dict]:
    try:
        return list(worker.loose_ends()) if worker is not None else []
    except Exception:                      # a building's stubs never break the snapshot
        return []


def _exit_names(town: Town, source: str) -> dict[str, str]:
    """A Review board's exits by route (`to-development` → `To development`): its roads' signs say the name."""
    spec = town.custom_specs.get(source)
    if spec is None or catalog.type_of(spec).id != "council":
        return {}
    from orkcraft.realm import team
    return {e.id: e.name for e in team.exits_of(spec.get("config") or {})}


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
                        "sign": _exit_sign(town, r) or (sign(r) if flt.get("route") or "-" in (r.label or "") else ""),
                        "returns": bool(flt.get("returns"))})
    return out


def _exit_sign(town: Town, road) -> str:
    """The sign of a road that takes a Review board's exit: the exit's name."""
    routes = (road.filter or {}).get("route") or []
    names = _exit_names(town, road.source) if routes else {}
    return " · ".join(names[r] for r in routes if r in names)


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
CART_STANDS_S = 3600.0        # a cart that stopped (held, stuck, waiting for the person) stands at its stop this long
STANDING_PER_ROAD = 9         # the most carts a road's stop keeps (a pile says ×N)
CODE_SUFFIXES = frozenset((".py", ".js", ".ts", ".tsx", ".jsx", ".go", ".rs", ".rb", ".java", ".kt", ".swift", ".c",
                           ".h", ".cpp", ".cs", ".php", ".sh", ".sql", ".css", ".html", ".diff", ".patch"))
DOC_SUFFIXES = frozenset((".md", ".txt", ".rst", ".adoc", ".pdf", ".docx"))


def load_of(payload: pipes.Payload, source_type: str = "") -> str:
    """What a cart carries, by its kind (docs/design/town-readability.md §3): code, asset, message or doc. Read
    from what the cart is (its kind of work, its file, the building that sent it), never from what its text says."""
    if source_type == "watchtower" or payload.want == pipes.REPLY:
        return "message"
    if payload.want == pipes.CHANGE:
        return "code"
    if payload.want in (pipes.DOC, pipes.KNOW):
        return "doc"
    if payload.kind == pipes.FILE:
        suffix = Path(payload.value or "").suffix.lower()
        return "code" if suffix in CODE_SUFFIXES else "doc" if suffix in DOC_SUFFIXES else "asset"
    return "doc" if payload.kind == pipes.TEXT else "asset"


def short_ref(ref: str) -> str:
    """A cart's ref as its chip says it: `#42` from `42`, `#42`, `tasks/todo/42-login.md`; "" when it has no number."""
    m = re.search(r"(\d+)", Path(str(ref or "")).name)
    return f"#{m.group(1)}" if m else ""


def _asking(muster: Muster | None) -> tuple[set[str], set[str]]:
    """The refs the open questions are about, and the buildings whose orks ask."""
    if muster is None:
        return set(), set()
    found = list(muster.roster.alerts) + [o.alert for o in muster.roster.orcs if o.alert is not None]
    return ({a.ref for a in found if a.ref},
            {o.building for o in muster.roster.orcs if o.alert is not None and o.building})


def carts(town: Town, now: float | None = None, muster: Muster | None = None) -> list[dict[str, Any]]:
    """The carts that left lately: on which road, what they carry, how long ago, how long the road takes
    (`travel`; the page draws each moving from gate to gate). A filtered one turns back at the source.
    A cart that stopped stands at its road's stop (`stands`) while it waits: held for a limit's reset, stuck on an
    error, or waiting for the person (its ref is an open question's, or it is the latest into a building that asks);
    the newest of a ref only, a few a road (docs/design/town-readability.md §3)."""
    from orkcraft.gui.views.watchtower import subject
    engine = getattr(town, "roads", None)
    now = time.monotonic() if now is None else now
    refs, asking = _asking(muster)
    every = list(getattr(engine, "carts", []) or [])[-500:]
    latest_in: dict[str, Any] = {}                   # building → the newest cart into it
    seen_ref: set[tuple[str, str]] = set()
    for c in every:
        latest_in[c.target] = c
    out, standing = [], {}
    for c in reversed(every):
        age = now - c.at
        if age < 0:
            continue
        key = road_key(c.target, c.road_id)
        ref = c.payload.ref or ""
        newer = bool(ref) and (key, ref) in seen_ref
        if ref:
            seen_ref.add((key, ref))
        state = ("back" if c.status == "filtered" else "held" if c.status == "held" else
                 "stuck" if c.status == "error" else "moving")
        if state == "moving" and ((ref and ref in refs) or (c.target in asking and latest_in.get(c.target) is c)):
            state = "ask"
        stands = state in ("held", "stuck", "ask") and not newer
        if stands:
            if age > CART_STANDS_S or standing.get(key, 0) >= STANDING_PER_ROAD:
                continue
            standing[key] = standing.get(key, 0) + 1
        elif age > CART_SHOWN_S:
            continue
        title = c.payload.title or ""
        spec = town.custom_specs.get(c.source)
        source_type = catalog.type_of(spec).id if spec is not None else ""
        if source_type == "watchtower":
            title = subject(title)                   # the Inbox's card says who sent it and where from
        elif c.payload.mode == "pool.done":
            title = outcome(c.payload.value) or title  # done work reads as what came of it
        out.append({"id": f"{key}@{c.at:.3f}", "road": key, "status": c.status, "title": modes.strip_emoji(title)[:80],
                    "age": round(age, 2), "load": load_of(c.payload, source_type), "ref": short_ref(ref),
                    "state": state, "stands": stands})
    out.reverse()
    return out


def _paused(worker) -> bool:
    """A building that stopped taking work until the person resumes it (Barracks, Catapult: Halt All or ⏸)."""
    own = getattr(worker, "paused", None)
    kept = getattr(getattr(worker, "state", None), "paused", None)
    return own is True or kept is True


def orkspaces(town: Town, muster: Muster) -> list[dict[str, Any]]:
    out = []
    for o in town.scroll.orkspaces:
        ids = set(o.buildings)
        standing = [b for b in town.scroll.buildings if b.id in ids and not b.demolished and b.id != "town_hall"]
        out.append({"id": o.id, "name": o.name, "icon": o.icon, "biome": o.biome, "hotkey": o.hotkey,
                    "project": o.project or "",                   # the folder it works in (docs/design/projects.md)
                    "buildings": list(o.buildings), "questions": len(muster.questions_of(o.id)),
                    "count": len(standing),                       # what the War Map's land says and dots
                    "paused": sum(1 for b in standing if _paused(town.workers.get(b.id))),
                    "working": sum(1 for x in muster.roster.orcs if x.building in ids and x.status == "busy")})
    return out


def agents_working(muster: Muster) -> int:
    """The agents at work now: the roster's (War Tent sessions, orks marked busy) and every agent process the
    buildings run (realm/halt.py: a librarian, a review, a road's handler, a Mill step…)."""
    return muster.roster.working + halt.agents()


def hud(town: Town, muster: Muster, treasury: tr.Treasury, limits: list | None = None) -> dict[str, Any]:
    gold, gold_level, lumber, lumber_level = treasury.resources()
    quota, quota_level, show_gold = tr.quota(town.machine, limits or [])
    return {
        "gold": gold, "gold_level": gold_level, "show_gold": show_gold,
        "lumber": lumber, "lumber_level": lumber_level,
        "quota": quota, "quota_level": quota_level,
        "supply": muster.roster.active, "supply_max": town.scroll.budget.supply_max_workers,
        "agents_working": (working := agents_working(muster)), "agents": max(len(muster.roster.agents), working),
        "alerts": len(muster.roster.alerts),
        "hour": (hour := schedule.status(town.machine)),
        "hour_plain": modes.plain(hour),
        "quiet": schedule.quiet_now(town.machine),
        "quiet_hours": (f"{schedule.fmt(town.machine.quiet.start)}–{schedule.fmt(town.machine.quiet.end)}"
                        if town.machine.quiet is not None else ""),     # the sun and moon's menu (js/chrome.js Hour)
        "fire": town.machine.fire,                 # flames over a building that waits (the portrait's menu; js/hut.js)
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
             # a building's own question (a Review gate's carts) names its building, as an ork's names its own
             "who": who.get(a.id, ""), "building": by_alert.get(a.id) or (a.ref if a.source == "view" else ""),
             "advice": _advice(night, a),
             "waited": round(now - muster.alert_first_seen.get(a.id, now), 1)} for a in found]


def snapshot(town: Town, muster: Muster, treasury: tr.Treasury, limits: list | None = None,
             live=None, night=None) -> dict[str, Any]:
    found, ork_slots = buildings(town, muster), slots.summary(town, muster)
    signals(found, ork_slots["rows"])
    return {
        "project": town.scroll.meta.get("project_name") or town.repo_root.name,
        "repo": str(town.repo_root),
        "demo": bool(town.demo),
        "look": settings.look_now(town.machine),   # camp | office now, the person's (docs/design/portrait.md §3)
        # Connect Google is put away for now (docs/design/google-account.md §3): its wizard is long. ORKCRAFT_GOOGLE=1 shows it.
        "google": getenv("GOOGLE").lower() in ("1", "true", "yes", "on"),
        "resources": {k: v[1] for k, v in modes.RESOURCES.items()},
        "words": lexicon.table(),
        "active_orkspace": town.scroll.active_orkspace_id,
        "orkspaces": orkspaces(town, muster),
        "projects": gui_projects.snapshot(town),
        "buildings": found,
        "roads": roads(town),
        "carts": carts(town, muster=muster),
        "travel": float(getattr(town, "cart_travel_s", 0.0) or 0.0),
        "hud": hud(town, muster, treasury, limits),
        "slots": ork_slots,                       # 🥩 the orks at work or waiting on you, one row each (core/slots.py)
        "sessions": sessions(live),
        "alerts": alerts(town, muster, night),
        "motions": motion.ready(),               # the houses that move at work (docs/design/building-motion.md)
    }
