"""🧪 The Test bench in the GUI (docs/design/test-bench.md §2, §10): its card says what it tests, its goal and how its
cases stand against the bare AI tool; its window is the goal, its cases with their last test, and what to change.
The shipped cases and the reviews stay below it (js/bench.js). The runs are the host's bench (gui/bench.py,
gui/lab_runs.py), given to the worker when its window is first drawn."""
from __future__ import annotations

from orkcraft.gui.views import ActError, text
from orkcraft.realm import bench, lab_cases, tiers


def attach(w, host) -> None:
    w.bench = host.bench


def _engine(w):
    engine = getattr(w, "bench", None)
    if engine is None:
        raise ActError("Open the Test bench once first")
    return engine


def card(w) -> dict:
    s = w.subject()
    if s is None:
        return {"subject": None, "count": 0, "goal": w.state["goal"]}
    metric = lab_cases.metric_of(w.state["goal"])
    return {"subject": s, "count": len(w.subjects()), "last": w.last_of(s), "targets": len(w.targets()),
            "goal": w.state["goal"], "metric": metric, "cases": len(w.cases_of(s["id"])),
            "summary": lab_cases.summary(w.results_of(s["id"]), metric)}


def detail(w) -> dict:
    s = w.subject()
    out = {"subjects": w.subjects(), "subject": s["id"] if s else "", "targets": w.targets(), "heard": w.heard[:5],
           "last": w.last, "goal": w.state["goal"], "settings": w.state["settings"]}
    engine = getattr(w, "bench", None)
    if s is None:
        return out
    metric = lab_cases.metric_of(w.state["goal"])
    job = engine.lab.job(w) if engine is not None else None
    out.update({
        "metric": metric, "entries": w.entries(s), "cases": w.cases_of(s["id"]), "results": w.results_of(s["id"]),
        "summary": lab_cases.summary(w.results_of(s["id"]), metric),
        "proposals": w.state["proposals"].get(s["id"]) or {},
        "busy": engine.lab.busy.get(engine.lab.key(w, s), "") if engine is not None else "",
        "job": job.public() if job else None,
        "tools": engine.lab.tools() if engine is not None else [{"id": "main", "title": "Main tool"}],
        "tiers": engine.lab.tiers() if engine is not None else [{"id": "", "title": "Its own"}],
        "pools": [{"id": b.id, "title": b.title} for b in w.town.scroll.buildings
                  if not b.demolished and catalog_type(w, b.id) == "barracks"],
    })
    return out


def catalog_type(w, bid: str) -> str:
    from orkcraft.realm import catalog
    spec = w.town.spec_of(bid)
    return catalog.type_of(spec).id if spec else ""


def _subject(w) -> dict:
    s = w.subject()
    if s is None:
        raise ActError("Pull a road from a building into the Test bench first")
    return s


def _pick(w, args: dict) -> bool:
    if not w.pick(text(args, "id", 200)):
        raise ActError("That building's road does not come into the Test bench")
    return True


def _goal(w, args: dict) -> bool:
    w.set_goal(text(args, "goal", 1000))
    return True


def _settings(w, args: dict) -> bool:
    values = {}
    for key in ("tool", "bare_tool"):
        if key in args:
            values[key] = text(args, key, 40) or "main"
    for key in ("tier", "bare_tier"):
        if key in args:
            tier = text(args, key, 20)
            if tier and tier not in tiers.TIERS:
                raise ActError("No such tier")
            values[key] = tier
    if "max_spend" in args:
        try:
            values["max_spend"] = min(max(float(args["max_spend"]), 0.1), 50.0)
        except (TypeError, ValueError):
            raise ActError("The spend limit is a number of dollars") from None
    if "judge" in args:
        values["judge"] = bool(args["judge"])
    w.set_settings(**values)
    return True


def _generate(w, args: dict) -> bool:
    from orkcraft.gui.lab_runs import LabError
    try:
        _engine(w).lab.generate(w, _subject(w))
    except LabError as e:
        raise ActError(str(e)) from None
    return True


def _add(w, args: dict) -> str:
    s = _subject(w)
    body = text(args, "text", 6000).strip()
    if not body:
        raise ActError("Write the case's input")
    entry = text(args, "entry", 200)
    if entry and entry not in {e["id"] for e in w.entries(s)}:
        raise ActError("No such way in")
    expect = [x.strip() for x in text(args, "expect", 400).split(",") if x.strip()]
    entries = w.entries(s)
    case = lab_cases.new_case(text(args, "title", 120) or body[:60], body, entry or (entries[0]["id"] if entries else ""),
                              expect)
    if not w.add_cases(s["id"], [case]):
        raise ActError(f"At most {lab_cases.MAX_CASES} cases")
    return case["id"]


def _remove(w, args: dict) -> bool:
    if not w.remove_case(_subject(w)["id"], text(args, "case", 40)):
        raise ActError("No such case")
    return True


def _run(w, args: dict, every: bool = False) -> bool:
    from orkcraft.gui.lab_runs import LabError
    s = _subject(w)
    ids = None if every else [text(args, "case", 40)]
    try:
        _engine(w).lab.run(w, s, ids, then_propose=every)
    except LabError as e:
        raise ActError(str(e)) from None
    return True


def _stop(w, args: dict) -> bool:
    _engine(w).lab.stop(w)
    return True


def _propose(w, args: dict) -> bool:
    from orkcraft.gui.lab_runs import LabError
    try:
        _engine(w).lab.propose(w, _subject(w))
    except LabError as e:
        raise ActError(str(e)) from None
    return True


def _tasks(w, args: dict) -> int:
    from orkcraft.gui.lab_runs import LabError
    picks = [str(x) for x in args.get("picks") or []]
    try:
        return _engine(w).lab.tasks(w, _subject(w), picks, text(args, "pool", 200))
    except LabError as e:
        raise ActError(str(e)) from None


def _run_first(w, args: dict) -> str:
    """The quick action: every case of its own when it has them, else the first shipped case of what it tests."""
    s = _subject(w)
    if w.cases_of(s["id"]):
        _run(w, {}, every=True)
        return "all"
    if not s["can_run"]:
        raise ActError(f"Runs come to the {s['word']} later")
    ready = [c for c in bench.cases(w.repo_root, s["type"]) if c.reviewed]
    if not ready:
        raise ActError(f"The {s['word']} has no case to run")
    _engine(w).run({"id": s["id"], "case": ready[0].id, "tool": str(w.config.get("tool") or "main"),
                    "max_spend": w.config.get("max_spend") or bench.DEFAULT_MAX_SPEND, "lab": w.building_id})
    return ready[0].id


def _refresh(w, args: dict) -> bool:
    """While a run or an agent works: the window asks again for its lines."""
    w.changed()
    return True


ACTS = {"refresh": _refresh, "pick": _pick, "goal": _goal, "settings": _settings, "generate": _generate, "add": _add, "remove": _remove,
        "run": _run, "run_all": lambda w, a: _run(w, a, every=True), "stop": _stop, "propose": _propose,
        "tasks": _tasks, "lab.run": _run_first}
