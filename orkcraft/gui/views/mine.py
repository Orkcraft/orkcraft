"""⛏️ The Mine in the GUI (docs/design/mine.md §9): its card says the research in work and its round, the sources
each tool found, what is confirmed and disputed and the cost; its window asks a question (with what it may
cost before it starts), shows the research in work (the plan, a column per tool, the findings marked), the
disputes waiting on the person, the reports and the repeats. The research is the worker's
(core/workers/mine.py)."""
from __future__ import annotations

from orkcraft.gui.views import ActError, text
from orkcraft.realm import harnesses, research

REFRESH_S = 30.0              # repeats that are due, answers that did not come
REPORTS = 30                  # reports the window lists
CUT = 60_000                  # what the window gets of one report


def refresh(w) -> None:
    w.tick()


def _tool(t: str) -> dict:
    h = harnesses.get(t)
    return {"id": t, "title": h.title if h else t, "mark": h.mark if h else "?"}


def _counts(r: dict) -> dict:
    return r.get("counts") or research.counts(r)


def _sources(r: dict) -> dict:
    return r.get("sources") or research.per_tool(r)


def card(w) -> dict:
    """Closed: the research in work (its round), else the last report; the sources per tool, the counts, the cost."""
    r = w.running or (w.researches[0] if w.researches else None)
    waiting = len(w.waiting())
    if r is None:
        return {"state": "none", "tools": [_tool(t) for t in w.tools()], "waiting": 0}
    return {"state": "running" if w.running is r else r.get("status", ""), "question": r["question"][:120],
            "round": r.get("round", 0), "rounds": w.rounds, "status": r.get("status", ""),
            "tools": [{**_tool(t), "sources": _sources(r).get(t, 0)} for t in r.get("tools") or []],
            "counts": _counts(r), "cost": round(float(r.get("cost") or 0.0), 2), "waiting": waiting,
            "at": r.get("ended") or r.get("created", ""), "queue": len(w.queue)}


def _group(r: dict, g: dict) -> dict:
    return {"id": g["id"], "sub": g["sub"], "claim": g["claim"], "state": g.get("state", ""),
            "minds": research.minds_of(r, g), "decided": g.get("decided", ""),
            "sources": [{"url": s["url"], "title": s.get("title") or research.domain(s["url"]),
                         "site": research.domain(s["url"])} for s in research.independent(research.sources_of(r, g))]}


def _path(w, r: dict) -> str:
    """The report's file, as the Inspector opens it: the Mine's own copy (the Wiki's may be edited by then)."""
    md = w._file(r["id"], "md")
    try:
        return md.relative_to(w.repo_root).as_posix() if md.is_file() else ""
    except ValueError:
        return ""


def _research(w, r: dict, full: bool) -> dict:
    out = {"id": r["id"], "question": r["question"], "status": r.get("status", ""), "trigger": r.get("trigger", ""),
           "created": r.get("created", ""), "ended": r.get("ended", ""), "round": r.get("round", 0),
           "cost": round(float(r.get("cost") or 0.0), 4), "limit": r.get("limit", 0), "counts": _counts(r),
           "stopped": r.get("stopped", ""), "error": r.get("error", ""), "wiki_note": r.get("wiki_note", ""),
           "repeat": bool(r.get("repeat")), "path": _path(w, r)}
    if full:
        groups = [g for g in r.get("groups") or [] if g.get("state") not in (None, "dropped")]
        out.update(plan=r.get("plan") or [], groups=[_group(r, g) for g in groups],
                   tools=[{**_tool(t), "sources": _sources(r).get(t, 0),
                           "findings": sum(1 for f in r.get("findings") or [] if f["tool"] == t),
                           **{k: (r.get("per_tool") or {}).get(t, {}).get(k, "") for k in ("mind", "cost", "error")}}
                          for t in r.get("tools") or []],
                   disputes=[[_group(r, a), _group(r, b)] for a, b in research.disputes(r)],
                   report=w.report_text(r)[:CUT])
    return out


def detail(w) -> dict:
    low, high = w.estimate()
    open_id = w.running["id"] if w.running else (w.waiting()[0]["id"] if w.waiting() else "")
    return {
        "tools": [_tool(t) for t in w.tools()], "web_tools": [_tool(t) for t in w.web_tools()],
        "estimate": [low, high], "limit": w.limit, "month_limit": w.month_limit, "month_spent": w.month_spent(),
        "rounds": w.rounds, "running": bool(w.running), "queue": [q["question"] for q in w.queue],
        "current": _research(w, w.get(open_id), True) if open_id and w.get(open_id) else None,
        "reports": [_research(w, r, False) for r in w.researches[:REPORTS]],
        "repeats": w.repeats, "calendar": w._calendar(),
        "wiki": w.wiki_id() or "",
    }


def _number(args: dict, key: str) -> float | None:
    value = args.get(key)
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        raise ActError(f"{key} is not a number") from None


def _lines(args: dict, key: str) -> list[str]:
    return [ln.strip() for ln in text(args, key, 4000).splitlines() if ln.strip()]


def _ask(w, args: dict) -> str:
    try:
        return w.ask(text(args, "question", 4000), _lines(args, "must"), _lines(args, "skip"), _number(args, "limit"))
    except ValueError as e:
        raise ActError(str(e)) from None


def _open(w, args: dict) -> dict:
    r = w.get(text(args, "id", 40))
    if r is None:
        raise ActError("No such research")
    return _research(w, r, True)


def _decide(w, args: dict) -> bool:
    answer = text(args, "answer", 10)
    if answer not in ("more", "a", "b", "keep"):
        raise ActError("Answer more, a, b or keep")
    try:
        a, b = int(args.get("a")), int(args.get("b"))
    except (TypeError, ValueError):
        raise ActError("Which dispute?") from None
    w.decide(text(args, "id", 40), a, b, answer)
    return True


def _repeat(w, args: dict) -> bool:
    try:
        return w.set_repeat(text(args, "question", 4000), text(args, "every", 80).strip(), _number(args, "limit"))
    except ValueError as e:
        raise ActError(str(e)) from None


def _again(w, args: dict) -> str:
    r = w.get(text(args, "id", 40))
    if r is None:
        raise ActError("No such research")
    try:
        return w.ask(r["question"], r.get("must") or [], r.get("skip") or [], r.get("limit"))
    except ValueError as e:
        raise ActError(str(e)) from None


ACTS = {"ask": _ask, "open": _open, "decide": _decide, "repeat": _repeat, "again": _again}
