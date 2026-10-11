"""🧪 The Test bench in the GUI (docs/design/test-bench.md §2, §10): its card says what it tests, its goal and how its
cases stand against the bare AI tool; its window is the goal, its cases with their last test, and what to change.
The shipped cases and the reviews stay below it (js/bench.js). The runs are the host's bench (gui/bench.py,
gui/lab_runs.py), given to the worker when its window is first drawn."""
from __future__ import annotations

from orkcraft.gui.views import ActError, text
from orkcraft.realm import bench, lab_cases, lab_envs, tiers


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
        return {"subject": None, "count": 0, "goal": w.state["goal"], "scheme": None}
    metric = lab_cases.metric_of(w.state["goal"])
    return {"subject": s, "count": len(w.subjects()), "last": w.last_of(s), "targets": len(w.targets()),
            "goal": w.state["goal"], "metric": metric, "cases": len(w.cases_of(s["id"])),
            "summary": lab_cases.summary(w.results_of(s["id"]), metric), "scheme": w.scheme()}


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
        "virtual": [_change(w, c) for c in w.changes_of(s["id"])], "pr": (w.state.get("prs") or {}).get(s["id"], ""),
        "envs": w.envs(), "sets": _sets(w, s), "busy_what": engine.lab.busy.get(engine.lab.key(w, s), "") if engine else "",
        "pools": [{"id": b.id, "title": b.title} for b in w.town.scroll.buildings
                  if not b.demolished and catalog_type(w, b.id) == "barracks"],
    })
    return out


DIFF_SHOWN = 6000                  # characters of a code change's diff the window shows


def _change(w, c: dict) -> dict:
    """A change tried on the virtual building, as the window lists it."""
    out = {k: c.get(k) for k in ("id", "kind", "title", "why", "at", "files")}
    out["building"] = w.town.title_of(c["building"]) if c.get("building") else ""
    out["diff"] = c["diff"][:DIFF_SHOWN] if isinstance(c.get("diff"), str) else [d for d in c.get("diff") or [] if d[0] != " "]
    return out


def _sets(w, s: dict) -> list[dict]:
    """Each case set with its cases, its last run's means and what running it again will cost."""
    results = w.results_of(s["id"])
    out = []
    for cs in w.sets_of(s["id"]):
        cases = w.cases_in(s["id"], cs["id"])
        out.append({**cs, "cases": [{"id": c["id"], "title": c["title"]} for c in cases],
                    "summary": lab_envs.summary_of(cases, results), "estimate": lab_envs.estimate(cases, results, len(cases))})
    return out


def catalog_type(w, bid: str) -> str:
    from orkcraft.realm import catalog
    spec = w.town.spec_of(bid)
    return catalog.type_of(spec).id if spec else ""


def _subject(w) -> dict:
    s = w.subject()
    if s is None:
        raise ActError("Set the Test bench up first: pick what it tests")
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


def _lab_call(w, fn, *a) -> bool:
    from orkcraft.gui.lab_runs import LabError
    try:
        fn(w, _subject(w), *a)
    except LabError as e:
        raise ActError(str(e)) from None
    return True


def _env_add(w, args: dict) -> bool:
    return _lab_call(w, _engine(w).lab.make_env, text(args, "about", 2000))


def _set_add(w, args: dict) -> bool:
    count = args.get("count")
    if not isinstance(count, int) or not 1 <= count <= lab_envs.SET_MAX:
        raise ActError(f"A set has 1 to {lab_envs.SET_MAX} cases")
    return _lab_call(w, _engine(w).lab.make_set, text(args, "env", 40), text(args, "about", 2000), count)


def _set_run(w, args: dict) -> bool:
    s = _subject(w)
    ids = [c["id"] for c in w.cases_in(s["id"], text(args, "set", 40))]
    if not ids:
        raise ActError("That set has no case")
    return _lab_call(w, lambda w_, s_: _engine(w_).lab.run(w_, s_, ids))


def _set_remove(w, args: dict) -> bool:
    if not w.remove_set(_subject(w)["id"], text(args, "set", 40)):
        raise ActError("No such case set")
    return True


def _try(w, args: dict) -> bool:
    return _lab_call(w, _engine(w).lab.try_change, text(args, "proposal", 40), text(args, "building", 200))


def _take_back(w, args: dict) -> bool:
    s = _subject(w)
    change = text(args, "change", 40)
    if change == "code":
        return _lab_call(w, _engine(w).lab.drop_code)
    if not w.take_back(s["id"], change):
        raise ActError("No such change")
    return True


def _save_changes(w, args: dict) -> dict:
    saved, problems = w.save_changes(_subject(w)["id"])
    if problems:
        raise ActError("Not saved: " + "; ".join(problems[:3]))
    return {"saved": saved}


def _pr_preview(w, args: dict) -> dict:
    from orkcraft.gui.lab_runs import LabError
    try:
        return _engine(w).lab.pr_preview(w, _subject(w))
    except LabError as e:
        raise ActError(str(e)) from None


def _pr_send(w, args: dict) -> bool:
    return _lab_call(w, _engine(w).lab.send_pr)


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


def _setup(w, args: dict) -> list[str]:
    """Its setup (docs/design/improve-buildings.md §5.1): the building picked, or the buildings framed on the map."""
    ids = args.get("ids")
    if not isinstance(ids, list) or not ids or not all(isinstance(i, str) for i in ids):
        raise ActError("Pick a building, or frame several on the map")
    try:
        return w.set_scheme([i[:200] for i in ids[:24]])
    except ValueError as e:
        raise ActError(str(e)) from None


def _candidates(w, args: dict) -> list[dict]:
    """What its setup offers to test: every standing building but the Improve ones and the Town Hall."""
    from orkcraft.core.workers.lab import IMPROVE
    out = []
    for b in w.town.scroll.buildings:
        kind = catalog_type(w, b.id)
        if not b.demolished and kind and kind not in IMPROVE and kind != "town_hall":
            out.append({"id": b.id, "title": b.title, "type": kind})
    return out


ACTS = {"pr_preview": _pr_preview, "pr_send": _pr_send, "try": _try, "take_back": _take_back, "save_changes": _save_changes, "env_add": _env_add, "set_add": _set_add, "set_run": _set_run, "set_remove": _set_remove, "setup": _setup, "candidates": _candidates, "refresh": _refresh, "pick": _pick, "goal": _goal, "settings": _settings, "generate": _generate, "add": _add, "remove": _remove,
        "run": _run, "run_all": lambda w, a: _run(w, a, every=True), "stop": _stop, "propose": _propose,
        "tasks": _tasks, "lab.run": _run_first}
