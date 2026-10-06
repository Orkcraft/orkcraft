"""🪔 Clan Fire in the GUI: the clan, the document under review, the review turn by turn and cycle by
cycle, the report and the past reviews. Every act is the worker's (core/workers/council.py)."""
from __future__ import annotations

from orkcraft.gui import markdown
from orkcraft.gui.views import ActError, text
from orkcraft.realm import team as tm
from orkcraft.realm import tiers

OWN_QUICK = True              # its quick actions are in its preview (js/buildings/), not the generic buttons
KEEP = 60_000                 # characters of a document the page gets (Lake opens the whole of it)
OUTCOME = {"approved": "approved", "rework": "sent back", "budget": "stopped: budget", "asked": "waits for you",
           "error": "failed", "stopped": "stopped", "running": "reviewing"}


def _money(x: float) -> str:
    return f"${x:.2f}"


def _tally(d: tm.Discussion) -> dict:
    r = d.reviews()
    return {"ok": sum(t.verdict == "approve" for t in r), "no": sum(t.verdict in ("changes", "veto") for t in r)}


def card(w) -> dict:
    """Closed (docs/design/building-views.md): `cycle 2/3 · 3 ✓ 1 ✗ · $0.40` while it reviews, else the last
    outcome; `N queued`."""
    d = w.current
    out = {"state": "none", "queued": len(w.waiting), "triage": bool(w.routes), "of": len(w.team)}
    if d is None:
        return out
    out.update({"state": "running" if d.outcome == "running" else d.outcome, "cycle": d.cycle, "max": w.max_cycles,
                "route": d.route,
                "spent": _money(d.spent), "outcome": OUTCOME.get(d.outcome, d.outcome), **_tally(d)})
    return out


def _tier(m: tm.Member) -> str:
    return tiers.TIER_LABELS.get(tiers.step_tier({"harness": m.harness, "model": m.model}) or "", "")


def _turn(t: tm.Turn) -> dict:
    return {"role": t.role, "kind": t.kind, "verdict": t.verdict, "note": t.note,
            "cost": _money(t.cost) if t.cost else "", "at": t.at[11:16], "text": t.text[:KEEP],
            "html": markdown.render(t.text)}


def _review(w, d: tm.Discussion, full: bool) -> dict:
    row = {"id": d.id, "title": d.title, "cycle": d.cycle, "outcome": d.outcome,
           "outcome_word": OUTCOME.get(d.outcome, d.outcome), "spent": _money(d.spent),
           "started": d.started.replace("T", " ")[:16], "route": d.route, "task": d.task, "when": d.when,
           **_tally(d)}
    if full:
        row.update({"doc": d.doc[:KEEP], "doc_html": markdown.render(d.doc), "doc_path": d.doc_path,
                    "question": d.question if d.outcome == "asked" else "", "decision": d.decision, "error": d.error,
                    "turns": [_turn(t) for t in d.turns],
                    "report": tm.report_markdown(d, w.team), "report_html": markdown.render(tm.report_markdown(d, w.team))})
    return row


def detail(w) -> dict:
    d, veto = w.current, w.veto
    verdict, says = {}, {}
    if d is not None:
        for t in d.reviews():
            verdict[t.role] = t.verdict
            says[t.role] = next((ln.strip() for ln in t.text.splitlines() if ln.strip()), "")[:200]
    members = [{"role": m.role, "label": m.label, "tier": _tier(m), "veto": m.role.lower() in veto,
                "verdict": verdict.get(m.role, ""), "says": says.get(m.role, ""), "brief": w.rel(w.role_file(m.role)),
                "briefed": bool(tm.brief_text(w.role_file(m.role)))} for m in w.team]
    cycles = []
    for x in w.history if d is not None else ():       # the same document sent back before: its earlier cycles
        if x.id == d.id or x.title != d.title:
            continue
        if x.outcome != "rework":
            break
        cycles.insert(0, _review(w, x, True))
    steward = w.steward()
    return {
        "members": members,
        "steward": {"label": steward.harness + (f":{steward.model}" if steward.model else ""),
                    "brief": w.rel(w.steward_file), "briefed": bool(steward.brief), "prompt": steward.prompt},
        "max_cycles": w.max_cycles, "budget": _money(w.budget), "busy": w.busy, "routes": w.routes,
        "current": _review(w, d, True) if d is not None else None,
        "cycles": cycles,
        "queued": [x[0] for x in w.waiting],
        "history": [_review(w, x, False) for x in w.history if d is None or x.id != d.id],
    }


# -- acts --------------------------------------------------------------------------------------------

def _review_act(w, args: dict) -> str:
    """`started`, `queued` (a review is under way, or the steward waits for an answer), or "" (the worker said why)."""
    what = text(args, "text").strip()
    if not what:
        raise ActError("Give a repo path, or paste the text to review")
    queued = w.busy or (w.current is not None and w.current.outcome == "asked")
    return "started" if w.review_input(what) else "queued" if queued else ""


def _answer(w, args: dict) -> bool:
    d = w.current
    if d is None or d.outcome != "asked":
        raise ActError("The steward asks nothing now")
    answer = text(args, "text", 20_000).strip()
    if not answer:
        raise ActError("An empty answer")
    return w.reply(answer)


def _add_member(w, args: dict) -> str:
    role = " ".join(text(args, "role", 100).split())
    if not role:
        raise ActError("A member needs a role")
    if any(m.role.lower() == role.lower() for m in w.team):
        raise ActError(f"{role} is in the clan already")
    member = w.add_member(role, text(args, "harness", 100).strip() or "claude")
    if member is None:
        raise ActError("A member is a role and claude, agy or codex[:model]")
    return member.role


def _stop(w, args: dict) -> int:
    return w.halt()


def _show(w, args: dict) -> dict:
    """A past review in full (the window shows it in place of the current one)."""
    rid = text(args, "review", 100)
    d = next((x for x in w.history if x.id == rid), None)
    if d is None:
        raise ActError("That review is gone")
    return _review(w, d, True)


ACTS = {"review": _review_act, "answer": _answer, "add_member": _add_member, "stop": _stop, "show": _show}
