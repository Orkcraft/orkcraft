"""🛠 Workshop in the GUI: its runs, the chosen one's input, output and result, and Test's log. Every
act is the worker's (core/workers/workshop.py); the script itself is edited in Lake (js/lake.js)."""
from __future__ import annotations

from orkcraft.core.workers.workshop import SENT
from orkcraft.gui.views import ActError
from orkcraft.realm import workshop

REFRESH_S = 30.0              # as the TUI: its schedule is looked at this often
RUNS = 30                     # runs the window gets
CUT = 4000                    # characters of an input or an output it gets


def refresh(w) -> None:
    w.tick()


def _mark(r: workshop.Run) -> str:
    """✓ done, ! alert, → keeper (handed to its keeper's prompt), ✗ failed."""
    return {"done": "✓", "alert": "!", "escalated": "→ keeper"}.get(r.outcome, "✗")


def card(w) -> dict:
    """Closed (docs/design/building-views.md): the last run, the first line of what it said, and the schedule."""
    r = w.runs[0] if w.runs else None
    said = next((ln.strip() for ln in ((r.result or r.err) if r else "").splitlines() if ln.strip()), "")
    return {"running": w.running, "mark": _mark(r) if r else "", "outcome": r.outcome if r else "",
            "at": r.at[11:16] if r else "", "schedule": w.schedule, "said": said[:80], "runs": len(w.runs)}


def _shape(layout: str, r: workshop.Run) -> dict:
    """How its result shows, by the building's layout: a table, a card, else the log."""
    if layout != "log" and r.ok and r.result:
        kind, data = workshop.shape(r.result)
        if kind == "rows" and layout == "table":
            cols = list(dict.fromkeys(k for row in data for k in row))[:8]
            return {"kind": "table", "columns": cols,
                    "rows": [[str(row.get(c, ""))[:80] for c in cols] for row in data[:50]]}
        if kind == "card":
            return {"kind": "card", "fields": [[str(k), str(v)[:400]] for k, v in list(data.items())[:20]]}
    return {"kind": "log"}


def _run(layout: str, r: workshop.Run, test: bool = False) -> dict:
    return {"at": r.at, "time": r.at[11:19], "event": r.event or "cart", "source": r.source, "code": r.code,
            "ms": r.ms, "outcome": r.outcome, "mark": _mark(r), "ok": r.ok,
            "sent": "" if test else SENT.get(r.outcome, ""),
            "input": r.input[:CUT], "result": r.result[:CUT], "err": r.err[:CUT], "keeper": bool(r.steward),
            "shape": _shape(layout, r)}


def detail(w) -> dict:
    try:
        script = w.script.relative_to(w.repo_root).as_posix()
    except ValueError:
        script = str(w.script)
    return {"script": script, "runtime": w.runtime, "layout": w.layout, "schedule": w.schedule,
            "keeper": bool(w.config.get("steward_prompt")), "keeper_name": w.keeper, "running": w.running, "has_cart": w.last_cart is not None,
            "runs": [_run(w.layout, r) for r in w.runs[:RUNS]],
            "tests": [_run(w.layout, r, True) for r in w.tests], "tested_at": w.tested_at}


def _run_again(w, args: dict) -> bool:
    why = w.run_again()
    if why:
        raise ActError(why)
    return True


def _test(w, args: dict) -> dict:
    tests = w.run_tests()
    ok = sum(1 for r in tests if r.ok)
    if not tests:
        w.toast("its blueprint has no mock carts", severity="warning")
    else:
        w.toast(f"{ok}/{len(tests)} mock carts passed", severity="information" if ok == len(tests) else "warning")
    return {"passed": ok, "total": len(tests)}


# The type's quick actions (realm/catalog.py) by their ids.
ACTS = {"workshop.run": _run_again, "workshop.test": _test}
