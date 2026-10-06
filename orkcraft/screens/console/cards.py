"""What the console says of a selected ork, building or road, as Rich text: the cards and lines
that Info, the garrison and the War Map show (the GUI says the same in `gui/info.py`)."""
from __future__ import annotations

from typing import TYPE_CHECKING

from rich.text import Text

from orkcraft.realm.orcs import ALERT_ICON, RESIDENT, WORKER, Orc
from orkcraft.tui.text import scheme_text

if TYPE_CHECKING:
    from orkcraft.realm.roster import Roster


def orc_key(o: Orc) -> str:
    if o.category == RESIDENT:
        return f"orc:resident:{o.ref}"
    return f"orc:{o.category}:{o.building or o.ref or o.name}"


STATUS_DISPLAY = {
    "alert": f"{ALERT_ICON} Wait",
    "busy": "🔨 Busy",
    "idle": "💤 Idle",
    "frozen": "🛑 Frozen",
    "draft": "📝 Draft",
}


def road_card(app, key: str) -> Text:
    """The road card of the console: source → target, event, filter, handler, carts."""
    from orkcraft import scroll as ts
    from orkcraft.realm import pipes
    from orkcraft.widgets.road_layer import split_key

    t = Text()
    target_id, road_id = split_key(key)
    scroll_obj = getattr(app, "scroll", None)
    found = ts.find_road(scroll_obj, road_id, target_id) if scroll_obj is not None else None
    if found is None:
        t.append("This road no longer exists.", style="dim")
        return t
    target, road = found
    src = scroll_obj.building(road.source)
    t.append(f"{src.icon + ' ' if src and src.icon else ''}{src.title if src else road.source}", style="bold")
    t.append("  →  ")
    t.append(f"{target.icon + ' ' if target.icon else ''}{target.title}\n", style="bold")
    signal = f"  ·  signal {road.label}" if road.label else ""
    t.append(f"Event: {pipes.label(road.event)}{signal}\n")
    flt = "; ".join(f"{k}={','.join(map(str, v)) if isinstance(v, list) else v}" for k, v in road.filter.items())
    t.append(f"Filter: {flt or 'none'}\n", style="" if flt else "dim")
    orc = target.garrison.handler(road.handler) if road.handler else None
    t.append(f"Handler: {orc.avatar} {orc.name} ({orc.kind})\n" if orc else "Handler: plain\n")
    counts: dict[str, int] = {}
    engine = getattr(app, "roads", None)
    for cart in getattr(engine, "carts", []):
        if cart.target == target_id and cart.road_id == road_id:
            counts[cart.status] = counts.get(cart.status, 0) + 1
    order = ("sent", "delivered", "filtered", "held", "error")
    carts = " · ".join(f"{counts[k]} {k}" for k in order if counts.get(k))
    t.append(f"Carts: {carts or 'none yet'}\n", style="" if carts else "dim")
    return t


def unit_details(app, orc: Orc) -> Text:
    """Kind, harness scheme, roads, re-run policy and the reason — and the steward's last report."""
    from orkcraft.realm import looks, tiers

    t = Text()
    t.append(f"{'Steward' if orc.lead else 'Handler'} · {looks.KIND_LABELS.get(orc.kind, orc.kind)}")
    if orc.tier_icon:
        t.append(f" · {tiers.label(orc.tier)}", style=tiers.TIER_STYLES.get(orc.tier or "", ""))
    scheme = scheme_text(orc.harness, orc.kind)
    if scheme.plain:
        t.append("  ")
        t.append(scheme)
        t.append(f"  ({looks.scheme_long(orc.harness, orc.kind)})", style="dim")
    t.append("\n")
    for label in orc.roads:
        t.append(f"◂ {label}\n", style="dim")
    if not orc.lead and orc.run:
        restart = "restart on new data" if orc.run.get("restart_on_new") else "finish, then rerun"
        t.append(f"Rerun: {orc.run.get('quiet_s', 0)} s quiet · {restart}\n", style="dim")
    if orc.why:
        t.append(f"Why {orc.kind}: {orc.why}\n", style="italic dim")
    if orc.lead and orc.building:
        from orkcraft.realm import steward
        report = steward.load_report(getattr(app, "repo_root", None), orc.building) if getattr(app, "repo_root", None) else None
        if report:
            t.append(f"Last watch {report.get('ts', '')[:16].replace('T', ' ')}: "
                     f"{len(report.get('findings', []))} finding(s), {len(report.get('proposals', []))} proposal(s)\n")
        else:
            t.append("Not watched yet — [W] Watch now\n", style="dim")
    return t


def _spend_of(app, orc: Orc):
    from orkcraft.realm import roads, steward, unit_info

    repo = getattr(app, "repo_root", None)
    snap = getattr(app, "snapshot", None)
    if orc.category == RESIDENT and orc.building and repo is not None:
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
    term = orc.session if orc.category == RESIDENT else (orc.ref if orc.category == WORKER else "")
    if term and snap is not None and term in snap.cost_by_terminal:
        spend = spend.add(unit_info.Spend(usd=snap.cost_by_terminal[term]))
    return spend


def _append_tier(t: Text, orc: Orc) -> None:
    """🔮 / ⚔ / ⛏ before a handler's name, in its tier's colour (stewards have none)."""
    from orkcraft.realm import tiers
    if orc.tier_icon:
        t.append(f"{orc.tier_icon} ", style=tiers.TIER_STYLES.get(orc.tier or "", ""))


def orc_info(app, orc: Orc) -> Text:
    from orkcraft.realm import unit_info

    t = Text()
    st = STATUS_DISPLAY.get(orc.status, f"{orc.status_icon} {orc.status.capitalize()}")
    name_style = "bold yellow" if orc.status == "alert" else "bold"
    t.append("★ " if orc.lead else "", style=name_style)
    _append_tier(t, orc)
    t.append(orc.name, style=name_style)
    t.append(f"  {st}\n", style="dim")
    b = app.building(orc.building) if orc.building else None
    for sentence in unit_info.orc_sentences(orc, f"{b.icon} {b.title}" if b else ""):
        t.append(sentence + "\n")
    snap = getattr(app, "snapshot", None)
    term = orc.session if orc.category == RESIDENT else (orc.ref if orc.category == WORKER else "")
    live = snap.model_by_terminal.get(term, "") if snap is not None and term else ""
    models = unit_info.models_of(orc, live)
    if models:
        t.append("Models: ", style="dim")
        for i, (letter, style, label) in enumerate(models):
            t.append(("  " if i else "") + letter, style=style)
            t.append(f" {label}", style="dim")
        t.append("\n")
    if orc.category == RESIDENT and not orc.lead and orc.kind not in unit_info.FREE_KINDS:
        if orc.session:
            meta = getattr(getattr(app, "chat", None), "meta", {}).get(orc.session)
            t.append(f"● deployed · {meta[1] if meta and meta[1] else orc.session}\n", style="green")
        else:
            t.append("not deployed — C opens a session\n", style="dim")
    spend = _spend_of(app, orc)
    t.append(spend.text())
    if term and snap is not None and snap.context_by_terminal.get(term):
        t.append(f" · {unit_info.fmt_tokens(snap.context_by_terminal[term])} in context", style="dim")
    return t


def orc_about(app, orc: Orc) -> str:
    """Why the orc is here: its role, its orders, what it does now."""
    from orkcraft.realm import unit_info

    b = app.building(orc.building) if orc.building else None
    return " ".join(unit_info.orc_sentences(orc, f"{b.icon} {b.title}" if b else ""))


def orc_runs(app, orc: Orc) -> Text:
    """One quiet line: what it spent over its runs, and its own 👍 / 👎."""
    from orkcraft.realm import feedback

    parts = [_spend_of(app, orc).text()]
    repo = getattr(app, "repo_root", None)
    if repo is not None and "/" in orc.ref:
        sc = feedback.scores(repo).get(orc.ref, {})
        parts.append(f"👍 {sc.get('likes', 0)} 👎 {sc.get('dislikes', 0)}")
    parts.append("● deployed" if orc.session else "not deployed")
    return Text(" · ".join(parts), style="dim", no_wrap=True, overflow="ellipsis")


def building_about(app, building_id: str) -> str:
    """Why the building is here: its own summary, else its type's, else its role."""
    from orkcraft.realm import catalog

    b = app.building(building_id)
    spec = app.spec_of(building_id) if hasattr(app, "spec_of") else None
    about = (spec or {}).get("summary") or ""
    if not about and spec:
        about = catalog.type_of(spec).summary
    return about or (b.role if b else "") or "No description yet."


def building_runs(app, building_id: str, roster: Roster) -> Text:
    """One quiet line: what the garrison spent, the week's runs, 👍 / 👎."""
    from orkcraft.realm import unit_info

    orcs = roster.garrison(building_id)
    total = unit_info.Spend(free=True)
    for o in orcs:
        total = total.add(_spend_of(app, o))
    parts = [total.text() if orcs else "🪙 nothing spent — no orks"]
    repo = getattr(app, "repo_root", None)
    if repo is not None:                     # the steward's journal
        from orkcraft.realm import feedback
        j = feedback.journal(repo, building_id)
        parts.append(f"week: {j['runs']} runs ({j['ok']} ✓ {j['failed']} ✗) · {j['results']} results")
        parts.append(f"👍 {j['likes']} 👎 {j['dislikes']}")
    return Text(" · ".join(parts), style="dim", no_wrap=True, overflow="ellipsis")


def building_listens(app, building_id: str) -> Text:
    """Who the building listens to, and which orc (or a plain road) takes each cart."""
    from orkcraft import scroll as ts
    from orkcraft.realm import pipes, tiers

    t = Text(no_wrap=True, overflow="ellipsis")
    scroll_obj = getattr(app, "scroll", None)
    target = scroll_obj.building(building_id) if scroll_obj is not None else None
    roads = ts.incoming(scroll_obj, building_id) if scroll_obj is not None else []
    if not roads:
        t.append("Listens to nobody yet", style="dim")
        return t
    t.append("Listens: ", style="dim")
    for i, road in enumerate(roads):
        if i:
            t.append(" · ", style="dim")
        src = scroll_obj.building(road.source)
        t.append(f"◂ {src.icon + ' ' if src and src.icon else ''}{src.title if src else road.source}", style="bold")
        t.append(f" {road.label or pipes.label(road.event)}", style="dim")
        orc = target.garrison.handler(road.handler) if target and road.handler else None
        if orc is not None:
            icon = tiers.icon(tiers.orc_tier(orc.harness, orc.kind))
            t.append(f" → {orc.avatar} {icon + ' ' if icon else ''}{orc.name}")
        else:
            t.append(" → plain", style="dim")
    return t

