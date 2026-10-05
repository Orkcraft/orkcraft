"""Buildings as the core changes them: raising a checked spec, Z back to a checkpoint, a building's
goal, 👍 / 👎 on its results and on its orks, and the proposals of the retros and the stewards.

The face keeps what is shown (the window of a new building, the focus, the dialogs); everything that
changes the camp happens here and is published: `ROADS`, `ROSTER`, `HALL`, `SPEC`.
"""
from __future__ import annotations

import datetime as dt
import json
from typing import Any

from orkcraft import scroll
from orkcraft.core import bus
from orkcraft.core.town import Town
from orkcraft.realm import catalog, checkpoint, evolution, feedback, masonry, optimize, pipes, steward, workshop
from orkcraft.realm.buildings import Building, custom_building

GOAL_WORDS = {"thrift": "the retros will make it cheaper",
              "balance": "cheaper where it is liked, better where it is not",
              "quality": "the retros will make its results better — it may spend more (up to twice the prompt)"}


# -- raising ---------------------------------------------------------------------------------------

def type_spec(town: Town, type_id: str) -> dict | None:
    """A camp building's spec from the catalog: the type's defaults and a free id."""
    t = catalog.TYPES.get(type_id)
    if t is None or type_id in catalog.SYSTEM_TYPES | catalog.SCRATCH_TYPES or type_id == catalog.DEFAULT_TYPE:
        return None
    taken = town.taken_ids() | masonry.ID_RESERVED
    bid, n = type_id, 1
    while bid in taken:
        bid, n = f"{type_id}_{n}", n + 1
    return {"id": bid, "type": type_id, "title": t.title, "icon": t.icon, "summary": t.summary[:200],
            "orc": {"name": t.orc, "role": t.preview[:80]}}


def raise_spec(town: Town, spec: dict, hut: list[float] | None = None) -> Building | None:
    """Save a checked spec and stand its building in the active orkspace's scroll (at `hut`, the
    fractions of the town where its ghost settled). None, and said so, when the spec is refused."""
    spec = catalog.migrate(spec)
    problems = masonry.save_spec(town.repo_root, spec, existing_ids=town.taken_ids())
    if problems:
        town.toast("\n".join(problems), title="Save failed", severity="error")
        return None
    scroll.add_custom_building(town.scroll, spec)
    placed = town.scroll.building(spec["id"])
    if hut is not None and placed is not None:
        placed.hut = hut
    building = custom_building(spec)
    town.buildings.append(building)
    town.custom_specs[spec["id"]] = spec
    pipes.set_typed(spec["id"], catalog.events_of(spec))
    return building


def log_build_request(town: Town, prompt: str, result: Any) -> None:
    """Every build request (a builder's or the Town Builder's result), kept in `.orkcraft/build-requests.jsonl`."""
    record: dict[str, Any] = {
        "ts": dt.datetime.now().isoformat(timespec="seconds"),
        "prompt": prompt,
        "ok": result.ok,
        "attempts": len(result.attempts),
        "cost_usd": result.cost_usd,
    }
    if result.ok:
        spec = getattr(result, "spec", None)
        record["id"] = spec["id"] if spec else [s["id"] for s in getattr(result, "specs", [])]
    else:
        last_errs = result.attempts[-1].errors if result.attempts else []
        record["error"] = result.error or ("; ".join(last_errs) if last_errs else "build failed")
    queue = town.repo_root / ".orkcraft" / "build-requests.jsonl"
    try:
        queue.parent.mkdir(parents=True, exist_ok=True)
        with queue.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError:
        pass


# -- Z: back to a checkpoint -------------------------------------------------------------------------

def revert(town: Town, building_id: str) -> bool:
    """This building back to its previous checkpoint — its files, incoming roads and garrison;
    nothing else in the camp changes."""
    before = checkpoint.building_before(town.repo_root, building_id)
    if before is None:
        town.toast("no earlier checkpoint for this building", title="↶ Revert")
        return False
    parent, spec, entry, files = before
    if entry is None and spec is None:
        town.toast("this is the building's first checkpoint — demolish it with X instead", title="↶ Revert")
        return False
    checkpoint.restore_files(town.repo_root, building_id, spec, files)
    current = town.scroll.building(building_id) if town.scroll is not None else None
    if current is not None and entry is not None:
        old = scroll.TownScroll.from_dict({"active_orkspace_id": "x", "orkspaces": [], "buildings": [entry]}).buildings[0]
        known = {x.id for x in town.scroll.buildings}
        current.roads = [r for r in old.roads if r.source in known]
        current.garrison, current.actions = old.garrison, old.actions
        current.title, current.icon = old.title, old.icon
    if spec is not None:
        spec = catalog.migrate(spec)
        town.custom_specs[building_id] = spec
        pipes.set_typed(building_id, catalog.events_of(spec))
        town.publish(bus.SPEC, building=building_id, spec=spec, refresh=True)
    town.publish(bus.ROADS)
    town.publish(bus.ROSTER)
    town.checkpoint("revert", building_id, f"back to {parent[:8]}")
    town.toast(f"back to checkpoint {parent[:8]}", title=f"↶ {building_id}")
    return True


# -- a building's goal and 👍 / 👎 -------------------------------------------------------------------

def cycle_goal(town: Town, building_id: str) -> str | None:
    """🪙 Thrift → ⚖️ Balance → 💎 Quality → 🪙: what the retros improve the building towards."""
    b = town.scroll.building(building_id)
    if b is None:
        return None
    goal = scroll.GOALS[(scroll.GOALS.index(b.aim) + 1) % len(scroll.GOALS)]
    b.goal = None if goal == "balance" else goal
    town.save()
    town.toast(f"{town.title_of(building_id)}: {GOAL_WORDS[goal]}",
               title=f"{scroll.GOAL_ICONS[goal]} {scroll.GOAL_TITLES[goal]}")
    return goal


def like(town: Town, building_id: str) -> bool:
    """👍: the building's last result becomes a reference."""
    if feedback.like(town.repo_root, building_id) is None:
        town.toast("nothing to rate yet — it has sent no result", title="👍")
        return False
    town.toast(f"{town.title_of(building_id)}: its last result is a reference now", title="👍 Good")
    town.publish(bus.HALL)
    return True


def dislike_context(town: Town, building_id: str) -> tuple[str, list[tuple[str, float]]]:
    """(its last result, [(supplier, share of the blame)]) — what the 👎 dialog shows."""
    out = feedback.last_output(town.repo_root, building_id) or {}
    cascade = [(town.title_of(b), feedback.CASCADE[hop - 1])
               for b, hop in feedback.suppliers(town.repo_root, town.scroll, building_id)]
    return str(out.get("value", "")), cascade


def dislike(town: Town, building_id: str, kind: str, note: str) -> None:
    """👎: broken inputs penalise its suppliers upstream, its logic only it."""
    incident = feedback.dislike(town.repo_root, town.scroll, building_id, kind, note)
    who = ", ".join(f"{town.title_of(b)} −{p:g}" for b, p in incident.blamed.items()) or "nobody"
    town.toast(f"incident saved · {who}", title=f"👎 {town.title_of(building_id)}")
    town.publish(bus.HALL)


def rate_orc(town: Town, building_id: str, orc_id: str, name: str, good: bool, note: str = "") -> None:
    """👍 / 👎 on a garrison ork's own work (its building's results are rated on the building)."""
    feedback.rate_orc(town.repo_root, building_id, orc_id, good, note)
    town.toast(f"{name}: noted as good work" if good else f"{name}: incident saved",
               title="👍 Good" if good else "👎 Bad")


# -- proposals: the retros' and the stewards' ---------------------------------------------------------

def set_spec(town: Town, building_id: str, new: dict) -> list[str]:
    """A custom building's spec replaced by a checked one; [] when saved, else the problems."""
    problems = masonry.save_spec(town.repo_root, new, existing_ids=set(town.custom_specs) - {building_id})
    if problems:
        return problems
    town.custom_specs[building_id] = new
    town.publish(bus.SPEC, building=building_id, spec=new)
    return []


def apply_proposal(town: Town, p: optimize.Proposal, kind: str = "auto-improve", by: str = "you") -> bool:
    """The change, a checkpoint `<kind>(<id>)` (Z takes it back), the proposal marked applied."""
    if p.status != "pending":
        town.toast(f"this proposal was {p.status} already", title="🔧 Not applied", severity="warning")
        return False
    bid = p.building
    b = town.scroll.building(bid)
    spec = town.custom_specs.get(bid)
    stale = "it changed since the proposal — ask again"
    if p.target.startswith("orc:"):
        orc = b.garrison.handler(p.target[4:]) if b is not None else None
        if orc is None or orc.orders != p.before:
            town.toast(stale, title="🔧 Not applied", severity="warning")
            return False
        if p.action == "chain":
            orc.kind, orc.chain, orc.orders = "chain", json.loads(p.after), ""
        else:
            orc.orders = p.after
        town.save()
        town.publish(bus.ROSTER)
    else:
        cfg = dict((spec or {}).get("config") or {})
        key = "steward_prompt" if p.target == "steward" else "orders"
        if spec is None or cfg.get(key) != p.before:
            town.toast(stale, title="🔧 Not applied", severity="warning")
            return False
        if p.action == "script":
            cfg.pop(key, None)
            workshop.save_script(town.repo_root, bid, str(cfg.get("runtime") or "python"), p.after)
        else:
            cfg[key] = p.after
        problems = set_spec(town, bid, dict(spec, config=cfg))
        if problems:
            town.toast("\n".join(problems), title="🔧 Not applied", severity="error")
            return False
    sha = town.checkpoint(kind, bid, f"{p.action} {p.target}: {p.why[:60]}")
    p.status, p.commit = "applied", sha or ""
    optimize.save(town.repo_root, p)
    evolution.record(town.repo_root, evolution.Change(
        bid, p.action, "weekly" if kind == "weekly" else "daily", f"{p.action} {p.target}", p.why[:200],
        by=by, sha=p.commit, key=p.id))
    town.publish(bus.HALL)
    town.toast(f"{town.title_of(bid)}: {p.action} applied — Z on it takes it back", title="🔧 Applied")
    return True


def apply_steward(town: Town, building_id: str, data: dict, index: int, by: str) -> str | None:
    """One steward proposal applied, with its own checkpoint (Z takes it back) and a line in the
    ledger of changes (realm/evolution.py). None when it could not be applied."""
    proposal = data["proposals"][index]
    try:
        what = steward.apply_proposal(town.scroll, building_id, proposal)
    except (ValueError, TypeError, KeyError) as e:
        town.toast(f"not applied: {e}", title="Steward", severity="warning")
        return None
    town.publish(bus.ROADS)
    town.publish(bus.ROSTER)
    town.record(building_id, "proposal_applied", what=what)
    sha = town.checkpoint("auto-improve", building_id, f"steward: {what[:60]}") or ""
    evolution.record(town.repo_root, evolution.Change(
        building_id, str(proposal.get("type")), "steward", what, str(proposal.get("why") or "")[:200], by=by,
        sha=sha, key=f"steward:{building_id}:{data.get('ts', '')}:{index}"))
    return what
