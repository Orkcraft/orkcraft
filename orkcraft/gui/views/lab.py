"""🧪 The Test bench in the GUI (docs/design/test-bench.md §2): its card says the building it tests and its last run; its
window is the bench (js/bench.js) for that building, and its roads in say which buildings it may test. The runs and
the reviews are the host's bench (gui/bench.py), given to the worker when its window is first drawn."""
from __future__ import annotations

from orkcraft.gui.views import ActError, text


def attach(w, host) -> None:
    w.bench = host.bench


def card(w) -> dict:
    s = w.subject()
    if s is None:
        return {"subject": None, "count": 0}
    return {"subject": s, "count": len(w.subjects()), "last": w.last_of(s), "targets": len(w.targets())}


def detail(w) -> dict:
    s = w.subject()
    return {"subjects": w.subjects(), "subject": s["id"] if s else "", "targets": w.targets(),
            "heard": w.heard[:5], "last": w.last}


def _pick(w, args: dict) -> bool:
    if not w.pick(text(args, "id", 100)):
        raise ActError("That building's road does not come into the Test bench")
    return True


def _run_first(w, args: dict) -> str:
    """Run the first case of the building it tests, on its own tool and spend limit."""
    from orkcraft.realm import bench
    s = w.subject()
    if s is None:
        raise ActError("Pull a road from a building into the Test bench first")
    if not s["can_run"]:
        raise ActError(f"Runs come to the {s['word']} later")
    ready = [c for c in bench.cases(w.repo_root, s["type"]) if c.reviewed]
    if not ready:
        raise ActError(f"The {s['word']} has no case to run")
    engine = getattr(w, "bench", None)
    if engine is None:
        raise ActError("Open the Test bench once first")
    engine.run({"id": s["id"], "case": ready[0].id, "tool": str(w.config.get("tool") or "main"),
                "max_spend": w.config.get("max_spend") or bench.DEFAULT_MAX_SPEND, "lab": w.building_id})
    return ready[0].id


ACTS = {"pick": _pick, "lab.run": _run_first}
