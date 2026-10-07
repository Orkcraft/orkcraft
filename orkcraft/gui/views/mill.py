"""⚙️ The Mill in the GUI: the last run on its card; the steps as a chain (the failing one marked), the
runs with their costs, what every step of a run made of its input, and the queue. The milling is the
worker's (core/workers/mill.py)."""
from __future__ import annotations

from orkcraft.core.workers.mill import HELP, failed_step
from orkcraft.gui.views import ActError, text
from orkcraft.realm import mill

RUNS = 50                     # runs the window lists
CUT = 4000                    # what the window shows of an input or a result


def _cut(s: str) -> str:
    return s if len(s) <= CUT else s[:CUT] + "…"


def _first(s: str) -> str:
    """A result's or an error's first non-empty line, short, for the closed card's foot: as words, without the
    Markdown marks it may start with (`### Daily brief` says `Daily brief`)."""
    line = next((ln.strip() for ln in (s or "").splitlines() if ln.strip()), "")
    return line.lstrip("#>*-+ ").strip()[:120] or line[:120]


def card(w) -> dict:
    """Closed: the last run's state and time (or milling, or no runs yet); every state also says how many
    steps and runs, and a finished run its first line (`line`) and, failed, the step it stopped at."""
    base = {"steps": len(w.steps), "runs": len(w.runs)}
    if w.running:
        return {"state": "running", "at": w.current.started if w.current else "", "queue": len(w.queue),
                "title": (w.current.title if w.current else ""), **base}
    if w.runs:
        j = w.runs[0]
        return {"state": "ok" if j.ok else "failed", "at": j.started, "queue": 0, "failed": failed_step(j),
                "line": _first(j.result if j.ok else j.error), **base}
    return {"state": "none", "at": "", "queue": 0, **base}


def _run(j, full: bool) -> dict:
    out = {"id": j.id, "title": j.title, "trigger": j.trigger, "started": j.started, "ended": j.ended,
           "ok": j.ok, "error": j.error, "cost": j.cost_usd, "agent": j.meta.get("agent", 0),
           "items": j.meta.get("items", 0), "failed": failed_step(j),
           "result": _cut(j.result if j.ok else j.error)[:300 if not full else CUT]}
    if full:
        out["input"] = _cut(j.input)
        out["cut"] = bool(j.meta.get("cut"))
        out["steps"] = list(j.meta.get("steps") or [])
    return out


def detail(w) -> dict:
    last = w.runs[0] if w.runs else None
    failed = failed_step(last) if last is not None else None
    return {
        "steps": w.steps, "problems": mill.check(w.steps), "failed": failed, "help": HELP,
        "running": w.running, "current": _run(w.current, False) if w.current else None,
        "queue": [{"title": q[2] or q[1], "trigger": q[1], "size": len(q[0])} for q in list(w.queue)],
        "runs": [_run(j, True) for j in w.runs[:RUNS]],
        "spent": round(sum(j.cost_usd or 0.0 for j in w.runs), 4),
        "has_input": bool(w.last_input),
    }


def _run_again(w, args: dict) -> bool:
    if not w.last_input:
        raise ActError("Nothing has arrived yet — a road brings the input")
    return w.run_again()


def _set_steps(w, args: dict) -> bool:
    steps = [ln.strip() for ln in text(args, "steps", 50_000).splitlines() if ln.strip()]
    problems = mill.check(steps)
    if problems:
        raise ActError("; ".join(problems[:3]))
    if not w.set_steps(steps):
        raise ActError("The steps were not saved")
    return True


ACTS = {"run": _run_again, "set_steps": _set_steps}
