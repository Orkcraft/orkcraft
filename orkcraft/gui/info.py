"""What the console says of a selected building or ork, as plain data: its Info (what it is, why it
is here, what it spent, its 👍 / 👎, who it listens to) and an ork's 🎒 Inventory (its models and the
tools of its latest runs).

The TUI's console builds the same from the same realm functions (`screens/console/`: Info,
garrison, Inventory); here they are data for the page, with no toolkit. A text that may carry emoji
comes twice, as it is and `_plain`, for Office. The page asks for it (`info`) while something is
selected, so the files it reads (the journal, the scores, the transcripts) are read for one only.

    building(town, muster, "forge")          # {"about", "spend", "week", "likes", "listens", ...}
    ork(town, muster, "forge/smith")         # {"about", "spend", "models", "tools", ...}
"""
from __future__ import annotations

from typing import Any

from orkcraft import autonomy
from orkcraft import scroll as ts
from orkcraft.core.roster import Muster
from orkcraft.core.town import Town
from orkcraft.gui import views
from orkcraft.realm import catalog, checkpoint, chronicles, feedback, inventory, modes, pipes, roads, steward, tiers, unit_info
from orkcraft.realm.orcs import RESIDENT, WORKER, Orc


def _both(key: str, text: str) -> dict[str, str]:
    return {key: text, f"{key}_plain": modes.text(text, modes.OFFICE)}


def find_ork(muster: Muster, ref: str) -> Orc | None:
    """A garrison ork by its ref (`<building>/<orc id>`), a War Tent one by its session key."""
    return next((o for o in muster.roster.orcs if o.ref == ref), None)


def terminal_of(orc: Orc) -> str:
    """The session whose telemetry is the ork's own: a deployed garrison ork's, a worker's."""
    return orc.session if orc.category == RESIDENT else (orc.ref if orc.category == WORKER else "")


def spend_of(town: Town, orc: Orc) -> unit_info.Spend:
    """What the ork spent: the steward's last watch, a handler's runs, a live session's telemetry."""
    repo, snap = town.repo_root, town.snapshot
    if orc.category == RESIDENT and orc.building:
        if orc.lead:
            report = steward.load_report(repo, orc.building) or {}
            cost = report.get("cost_usd")
            spend = unit_info.Spend(usd=float(cost) if isinstance(cost, (int, float)) else None,
                                    runs=1 if report else 0)
        elif orc.kind in unit_info.FREE_KINDS:
            spend = unit_info.Spend(free=True)
        else:
            orc_id = orc.ref.split("/", 1)[1] if "/" in orc.ref else orc.ref
            spend = unit_info.handler_spend(roads.examples_file(repo, orc.building, orc_id))
    else:
        spend = unit_info.Spend()
    term = terminal_of(orc)
    if term and term in snap.cost_by_terminal:
        spend = spend.add(unit_info.Spend(usd=snap.cost_by_terminal[term]))
    return spend


def _about(town: Town, building_id: str) -> str:
    """Why the building is here: its own summary, else its type's, else its role."""
    spec = town.spec_of(building_id)
    about = (spec or {}).get("summary") or ""
    if not about and spec:
        about = catalog.type_of(spec).summary
    bs = town.scroll.building(building_id)
    return about or getattr(bs, "role", "") or "No description yet."


KINDS = {"agent": "agent", "hybrid": "agent + script", "script": "script", "chain": "chain"}


def _handler(town: Town, muster: Muster, building_id: str, orc) -> dict[str, Any]:
    """One handler of the garrison as the steward's window lists it: who, what kind, what it does now,
    and what a click edits (an agent's orders, a script's file)."""
    ref = f"{building_id}/{orc.id}"
    live = find_ork(muster, ref)
    return {"ref": ref, "name": orc.name, "kind": orc.kind, "kind_label": KINDS.get(orc.kind, orc.kind),
            "status": live.status if live is not None else orc.status,
            "tier": tiers.orc_tier(orc.harness, orc.kind) or "",
            "script": str((orc.script or {}).get("path") or ""),
            "trigger": str((orc.trigger or {}).get("type") or "on_demand")}


def _listens(town: Town, muster: Muster, building_id: str) -> list[dict[str, Any]]:
    """Who the building listens to, and which ork (or a plain road) takes each cart."""
    scroll = town.scroll
    target = scroll.building(building_id)
    out = []
    for road in ts.incoming(scroll, building_id):
        src = scroll.building(road.source)
        orc = target.garrison.handler(road.handler) if target is not None and road.handler else None
        out.append({"key": ts.road_key(building_id, road.id), "from": road.source,
                    "title": src.title if src else road.source,
                    "label": road.label or pipes.label(road.event),
                    "handler": orc.name if orc is not None else "",
                    "tier": tiers.orc_tier(orc.harness, orc.kind) or "" if orc is not None else "",
                    "orc": _handler(town, muster, building_id, orc) if orc is not None else None})
    return out


def _others(town: Town, muster: Muster, building_id: str) -> list[dict[str, Any]]:
    """The handlers no road brings carts to: they work on a schedule or when asked."""
    b = town.scroll.building(building_id)
    if b is None:
        return []
    on_roads = {r.handler for r in b.roads if r.handler}
    return [_handler(town, muster, building_id, h) for h in b.garrison.handlers if h.id not in on_roads]


def _steward(town: Town, muster: Muster, building_id: str) -> dict[str, Any] | None:
    """The building's steward (its garrison's lead) for the head of its window: name, status, model."""
    lead = next((o for o in muster.roster.garrison(building_id) if o.lead), None)
    if lead is None:
        return None
    term = terminal_of(lead)
    models = inventory.models_of(lead, town.snapshot.model_by_terminal.get(term, "") if term else "")
    return {"ref": lead.ref, "name": lead.name, "status": lead.status, "tier": lead.tier or "",
            "model": models[0][1] if models else "", "models": len(models)}


def _town_autonomy(town: Town) -> str:
    """The town's autonomy level, which a building without its own follows: `📜 Morning advice`."""
    level = getattr(town.machine, "autonomy", autonomy.DEFAULT_LEVEL)
    lv = next((x for x in autonomy.LEVELS if x.n == level), autonomy.LEVELS[autonomy.DEFAULT_LEVEL])
    return f"{lv.icon} {lv.title}"


def building(town: Town, muster: Muster, building_id: str) -> dict[str, Any] | None:
    bs = town.scroll.building(building_id)
    if bs is None or bs.demolished:
        return None
    orcs = muster.roster.garrison(building_id)
    total = unit_info.Spend(free=True)
    for o in orcs:
        total = total.add(spend_of(town, o))
    j = feedback.journal(town.repo_root, building_id)
    aim = bs.aim
    spec = town.spec_of(building_id)
    return {
        "id": building_id,
        **_both("about", _about(town, building_id)),
        **_both("spend", total.text() if orcs else "🪙 nothing spent — no orks"),
        "week": {"runs": j["runs"], "ok": j["ok"], "failed": j["failed"], "results": j["results"]},
        "likes": j["likes"], "dislikes": j["dislikes"],
        "goal": aim, "goal_title": ts.GOAL_TITLES[aim],
        "pinned": bool(bs.pinned),
        "can_revert": checkpoint.can_revert(town.repo_root, building_id),
        "autonomy": bs.autonomy or "",
        "town_autonomy": _town_autonomy(town),
        "listens": _listens(town, muster, building_id),
        "others": _others(town, muster, building_id),
        "steward": _steward(town, muster, building_id),
        "quick": [] if getattr(views.of(catalog.type_of(spec).id if spec else ""), "OWN_QUICK", False) else
                 [{"id": a.id, "label": a.label, "glyph": a.glyph} for a in catalog.quick_actions_of(spec)],
    }


def ork(town: Town, muster: Muster, ref: str) -> dict[str, Any] | None:
    orc = find_ork(muster, ref)
    if orc is None:
        return None
    b = town.scroll.building(orc.building) if orc.building else None
    sentences = unit_info.orc_sentences(orc, b.title if b is not None else "")
    term = terminal_of(orc)
    snap = town.snapshot
    live = snap.model_by_terminal.get(term, "") if term else ""
    scores = feedback.scores(town.repo_root).get(orc.ref, {}) if "/" in orc.ref else {}
    context = snap.context_by_terminal.get(term) if term else None
    return {
        "ref": orc.ref, "name": orc.name, "building": orc.building or "", "lead": orc.lead,
        "kind": orc.kind, "tier": orc.tier or "", "status": orc.status, "scheme": orc.scheme,
        **_both("about", " ".join(sentences)),
        **_both("spend", spend_of(town, orc).text()),
        "context": unit_info.fmt_tokens(context) if context else "",
        "likes": int(scores.get("likes", 0)), "dislikes": int(scores.get("dislikes", 0)),
        "deployed": bool(orc.session), "session": orc.session,
        "garrison": orc.category == RESIDENT,
        "models": [{"tier": tier or "", "tier_label": modes.text(tiers.label(tier), modes.OFFICE) if tier else "", "model": model}
                   for tier, model in inventory.models_of(orc, live)],
        "tools": [{"tool": u.name, "name": inventory.short_tool(u.name), "count": u.count}
                  for u in inventory.recent_tools(town.repo_root, orc)],
    }


def history(town: Town, muster: Muster, building_id: str, ref: str = "", tool: str = "") -> dict[str, Any]:
    """📜 The Building Chronicles, newest first; for an ork its own events and its latest runs (with
    `tool`, only the runs that called it)."""
    orc = find_ork(muster, ref) if ref else None
    events = []
    for e in chronicles.history(town.repo_root, building_id, limit=200):
        if orc is not None and e.get("orc") != orc.name:
            continue
        icon, sentence = chronicles.describe(e)
        events.append({"ts": str(e.get("ts", ""))[:16].replace("T", " "), "by": str(e.get("by", "")),
                       "icon": icon, "text": sentence})
    runs = []
    if orc is not None:
        for s in inventory.sessions_of(town.repo_root, orc)[:inventory.RECENT_RUNS * 4]:
            if tool:
                run = inventory.read_run(s.transcript) if s.transcript else None
                if run is None or not any(step.kind == "tool" and step.tool == tool for step in run.steps):
                    continue
            when = s.last or s.started
            runs.append({"key": s.key, "harness": s.harness, "title": modes.strip_emoji(s.title or s.short_id),
                         "when": when.isoformat(timespec="minutes").replace("T", " ") if when else ""})
    return {"events": events, "runs": runs}
