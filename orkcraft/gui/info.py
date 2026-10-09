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
from orkcraft.core import buildings as core_buildings
from orkcraft.core.roster import Muster
from orkcraft.core.town import Town
from orkcraft.gui import views
from orkcraft.realm import (catalog, checkpoint, chronicles, feedback, growth, inventory, modes, pipes, roads, script_first,
                            steward, tiers, unit_info)
from orkcraft.realm.orcs import RESIDENT, WORKER, Orc


def _both(key: str, text: str) -> dict[str, str]:
    return {key: text, f"{key}_plain": modes.plain(text)}


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


KINDS = {"agent": "agent", "hybrid": "agent + script", "script": "script", "chain": "chain", "steward": "road rule"}


def _handler(town: Town, muster: Muster, building_id: str, orc) -> dict[str, Any]:
    """One handler of the garrison as the steward's window lists it: who, what kind, what it does now,
    and what a click edits (an agent's orders, a script's file)."""
    ref = f"{building_id}/{orc.id}"
    live = find_ork(muster, ref)
    return {"ref": ref, "name": orc.name, "kind": orc.kind, "kind_label": KINDS.get(orc.kind, orc.kind),
            "status": live.status if live is not None else orc.status,
            "tier": listen_tier(town, building_id) if orc.on_steward else tiers.orc_tier(orc.harness, orc.kind) or "",
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
                    "tier": (listen_tier(town, building_id) if orc.on_steward else tiers.orc_tier(orc.harness, orc.kind) or "")
                    if orc is not None else "",
                    "by": _handler(town, muster, building_id, orc) if orc is not None else None})
    return out


def _others(town: Town, muster: Muster, building_id: str) -> list[dict[str, Any]]:
    """The handlers no road brings carts to: they work on a schedule or when asked."""
    b = town.scroll.building(building_id)
    if b is None:
        return []
    on_roads = {r.handler for r in b.roads if r.handler}
    return [_handler(town, muster, building_id, h) for h in b.garrison.handlers
            if h.id not in on_roads and h.kind != "steward"]


def listen_tier(town: Town, building_id: str, own: str = "") -> str:
    """The tier its steward carries out its road rules at now (a rule's `own` tier, else the one picked, else the
    goal in force), "" for the default."""
    from orkcraft.core import delivery
    b = town.scroll.building(building_id)
    return roads.steward_steps(b, delivery.aim_now(town, building_id), own)[0].get("tier", "") if b is not None else ""


def _road_line(town: Town, road) -> str:
    """`⚒️ Inbox → here`: where a rule's road comes from and what it carries."""
    src = town.scroll.building(road.source)
    who = f"{src.icon} {src.title}".strip() if src is not None else road.source
    return f"{who} · {road.label or pipes.label(road.event)}"


def rule(town: Town, building_id: str, orc) -> dict[str, Any]:
    """One road rule of the steward's (a `steward` handler, docs/design/steward-listens.md): its words, its
    roads, its runs and what they spent on the steward's listen tier."""
    b = town.scroll.building(building_id)
    spend = unit_info.handler_spend(roads.examples_file(town.repo_root, building_id, orc.id))
    runs = [r for r in getattr(town.roads, "runs", []) if r.target == building_id and r.orc_id == orc.id]
    kept = roads.read_examples(town.repo_root, building_id, orc.id, limit=5)
    return {"ref": f"{building_id}/{orc.id}", "id": orc.id, "name": orc.name, "kind": orc.kind,
            "orders": orc.orders, "status": orc.status,
            "roads": [_road_line(town, r) for r in b.roads_of(orc.id)] if b is not None else [],
            "spend": spend.text(), "usd": spend.usd, "runs": spend.runs,
            "last": runs[-1].outcome if runs else "", "last_error": runs[-1].error if runs else "",
            "recent": [{"ts": str(e.get("ts", ""))[:16].replace("T", " "), "output": modes.plain(str(e.get("output", "")))[:300],
                        "cost": e.get("cost_usd")} for e in reversed(kept)],
            "tier": modes.plain(tiers.label(listen_tier(town, building_id, orc.tier))) or "its tool's default model",
            "own_tier": orc.tier if orc.tier in tiers.TIERS else "",
            "script": str((orc.script or {}).get("path") or "")}


def _rules(town: Town, building_id: str) -> list[dict[str, Any]]:
    b = town.scroll.building(building_id)
    return [rule(town, building_id, h) for h in b.garrison.handlers if h.kind == "steward"] if b is not None else []


def hand_over(town: Town, building_id: str, orc) -> dict[str, Any]:
    """What *Hand to the steward* changes for an agent handler: its tools and tier now, the steward's then, and
    what a run cost on its own and would cost at the steward's tier (an estimate from its recorded runs)."""
    from orkcraft.core import delivery
    from orkcraft.realm import recruiter
    b = town.scroll.building(building_id)
    [step] = roads.steward_steps(b, delivery.aim_now(town, building_id))
    spend = unit_info.handler_spend(roads.examples_file(town.repo_root, building_id, orc.id))
    per_run = spend.usd / spend.runs if spend.usd is not None and spend.runs else None
    now_tier, then_tier = tiers.orc_tier(orc.harness, orc.kind), step.get("tier")
    estimate = None
    if per_run is not None and now_tier in tiers.TIERS and then_tier in tiers.TIERS:
        estimate = per_run * TIER_COST[then_tier] / TIER_COST[now_tier] / max(1, len(orc.harness or []))
    tools = lambda steps: " → ".join(recruiter.HARNESS_NAMES.get(str(s.get("harness") or "main"), str(s.get("harness")))  # noqa: E731
                                     for s in steps) or recruiter.HARNESS_NAMES["main"]
    return {"name": orc.name, "orders": orc.orders, "roads": [_road_line(town, r) for r in b.roads_of(orc.id)],
            "tools_now": tools(orc.harness or ts.DEFAULT_HARNESS), "tools_then": tools([step]),
            "tier_now": modes.plain(tiers.label(now_tier)) or "its tool's default model",
            "tier_then": modes.plain(tiers.label(then_tier)) or "its tool's default model",
            "per_run_now": f"${per_run:.3f}" if per_run is not None else "",
            "per_run_then": f"≈ ${estimate:.3f}" if estimate is not None else "",
            "runs": spend.runs}


# What a run costs at each tier, relative to the warrior's — a rough guide for an estimate, never a bill
# (the light, middle and heavy models' list prices: about 1 : 3 : 5 for the same work).
TIER_COST = {"laborer": 1 / 3, "warrior": 1.0, "elder": 5 / 3}


def _steward(town: Town, muster: Muster, building_id: str) -> dict[str, Any] | None:
    """The building's steward (its garrison's lead) for the head of its window: name, status, model."""
    lead = next((o for o in muster.roster.garrison(building_id) if o.lead), None)
    if lead is None:
        return None
    term = terminal_of(lead)
    models = inventory.models_of(lead, town.snapshot.model_by_terminal.get(term, "") if term else "")
    bs, spec = town.scroll.building(building_id), town.spec_of(building_id)
    type_id = catalog.type_of(spec).id if spec else ""
    rank = steward.level_of(bs)                        # its own tier, Novice … Veteran (not its building's goal)
    column = steward.LEVEL_COLUMN[rank]
    uses = [{"id": use, "label": label, "tier": steward.tier_for(bs, use), "work": steward.is_work(type_id, use),
             "by_level": modes.plain(tiers.label(steward.goal_tier(type_id, use, column)))}
            for use, label in steward.uses(type_id).items()]
    rules = _rules(town, building_id)
    for u in uses:                                     # the road rules' spend shows under its listen tier
        if u["id"] == "listen" and rules:
            total = unit_info.Spend()
            for r in rules:
                total = total.add(unit_info.Spend(usd=r["usd"], runs=r["runs"]))
            u["spend"] = modes.plain(total.text())
    picked = [u["tier"] for u in uses if u["tier"]]
    default = models[0][1] if models else ""
    first = modes.plain(tiers.label(picked[0])) if picked else default
    return {"ref": lead.ref, "name": lead.name, "status": lead.status, "tier": lead.tier or "",
            "model": first or "default", "more": len({u["tier"] or "" for u in uses}) - 1 if picked else 0,
            "default": default, "uses": uses, "own": bs is not None and bs.garrison.steward is not None,
            "rank": rank, "rank_title": tiers.TIER_LABELS[rank], "ranks": list(reversed(tiers.TIERS)),
            "rank_set": bs is not None and bs.garrison.steward is not None and bs.garrison.steward.tier in tiers.TIERS}


def _town_autonomy(town: Town) -> str:
    """The town's autonomy level, which a building without its own follows: `🕰 On the clock`."""
    level = getattr(town.machine, "autonomy", autonomy.DEFAULT_LEVEL)
    lv = next((x for x in autonomy.LEVELS if x.n == level), autonomy.LEVELS[autonomy.DEFAULT_LEVEL])
    return f"{lv.icon} {lv.title}"


def _waits(town: Town, bs) -> dict:
    """🕰 its waits: its own (0 when it follows the town), the town's, what rules it now, the choices."""
    m = town.machine
    rules = autonomy.rules_of(bs, m.autonomy, m.autonomy_wait, m.rebuild_wait)
    return {"question": bs.question_wait or 0, "rebuild": bs.rebuild_wait or 0,
            "town_question": m.autonomy_wait, "town_rebuild": m.rebuild_wait,
            "clock": rules.level == autonomy.CLOCK,
            "questions": list(autonomy.QUESTION_WAITS), "rebuilds": list(autonomy.REBUILD_WAITS)}


def _script_first(town: Town, building_id: str) -> dict[str, Any] | None:
    """Whether its work is code (docs/design/script-first.md): {on, thinking, woke}; None for a type that thinks."""
    bs, spec = town.scroll.building(building_id), town.spec_of(building_id)
    if script_first.type_id(spec) not in script_first.TYPES | script_first.WHEN_CODE:
        return None
    last = script_first.wakes(town.repo_root, building_id, 1)
    woke = ""
    if last:
        when = str(last[0].get("ts", ""))[11:16]
        woke = f"woke {when} on {'an error' if last[0].get('why') == 'error' else 'a 👎'}"
    return {"on": script_first.is_script_first(spec, bs), "thinking": script_first.thinking(spec, bs), "woke": woke}


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
    code = _script_first(town, building_id)
    spend = total.text() if orcs else "🪙 nothing spent — no orks"
    if code is not None and code["on"] and total.usd in (None, 0) and not total.runs:
        spend = "🪙 no model"
    return {
        "id": building_id,
        **_both("about", _about(town, building_id)),
        **_both("spend", spend),
        "week": {"runs": j["runs"], "ok": j["ok"], "failed": j["failed"], "results": j["results"]},
        "likes": j["likes"], "dislikes": j["dislikes"],
        "goal": aim, "goal_title": ts.GOAL_TITLES[aim],
        "goal_hints": {g: core_buildings.goal_words(town, building_id, g) for g in ts.GOALS}  # the retros, an Agent pool's orks
        if catalog.type_of(spec).id in steward.WORK else {},
        "level": bs.level or 0, "level_mark": growth.mark(aim, bs.level or 0),
        "next": growth.next_step(town.repo_root, building_id, bs.level or 0),
        "pinned": bool(bs.pinned),
        "can_revert": checkpoint.can_revert(town.repo_root, building_id),
        "autonomy": bs.autonomy or "",
        "town_autonomy": _town_autonomy(town),
        "waits": _waits(town, bs),
        "listens": _listens(town, muster, building_id),
        "others": _others(town, muster, building_id),
        "rules": _rules(town, building_id),
        "steward": _steward(town, muster, building_id),
        "script_first": code,
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
        "models": [{"tier": tier or "", "tier_label": modes.plain(tiers.label(tier)) if tier else "", "model": model}
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
