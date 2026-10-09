"""🏕 Barracks in the GUI: the orks and their tasks, the queue, the steward's questions and rules.
Every act is the worker's (core/workers/barracks.py); an ork's terminal is a session of the core's
sessions service (core/sessions.py), opened on its own worktree."""
from __future__ import annotations

import os
from pathlib import Path

from orkcraft.gui import folders
from orkcraft.gui.views import ActError, text
from orkcraft.realm import barracks as bk
from orkcraft.realm import catalog, harnesses, lexicon, paths, pipes, tiers
from orkcraft.sources import sessions as past

OWN_QUICK = True              # its quick actions are in its preview (js/buildings/), not the generic buttons
REFRESH_S = 30.0              # the pull requests of done tasks are looked at now and then (the worker's own pace)
KEEP = 20_000                 # characters of a brief or a report the page gets
LANES = (("queue", "Queue"), ("work", "Working"), ("review", "Review"), ("done", "Done"), ("failed", "Failed"))
LANE_OF = {"queued": "queue", "working": "work", "reviewing": "review", "asked": "review", "done": "done",
           "failed": "failed", "planning": "queue", "blocked": "queue", "planned": "work"}


def refresh(w) -> None:
    w.tick()


def _money(x: float) -> str:
    return f"${x:.2f}"


LANES_MAX = 6            # the orks its card shows a lane for


def _lanes(st) -> list[dict]:
    """A lane per ork, for its card (the owner's ask: who works on what at a glance): its name, its AI tool and tier,
    working | resting | asks, its topic — the persona it was hired as, the kind of work it takes for good, never the
    one request — and how many tasks of that topic wait in the queue (its follow-ups first)."""
    asking = {t.orc for t in st.asked}
    out = []
    for o in st.orcs[:LANES_MAX]:
        waits = sum(1 for t in st.queue if t.wait_for == o.name
                    or (not t.wait_for and o.persona and t.persona == o.persona))
        out.append({"name": o.name, "harness": o.harness, "tier": o.tier or "",
                    "state": "asks" if o.name in asking else "working" if o.status == "working" else "resting",
                    "topic": o.persona, "queue": waits})
    return out


def card(w) -> dict:
    """Closed (docs/design/building-views.md): how many orks work of how many, `queue 3`, `✓5 ✗1 · $1.20`,
    `<keeper> asks`; a lane per ork (`_lanes`); who works on what (two at most), else the last task that ended."""
    st, f = w.state, w.foreman
    ended = next((t for t in reversed(st.tasks) if t.status in ("done", "failed")), None)
    return {"asks": w.keeper if st.asked else "",
            "active": sum(1 for o in st.orcs if o.status == "working"), "max": f.max_orcs, "queue": len(st.queue),
            "done": sum(1 for t in st.tasks if t.status == "done"),
            "failed": sum(1 for t in st.tasks if t.status == "failed"),
            "spent": _money(st.spent), "paused": st.paused,
            "working": [{"ork": o.name, "task": t.title, "want": lexicon.want_word(t.want)} for o in st.orcs
                        if o.status == "working"
                        and (t := st.task(o.task)) is not None][:2],
            "last": {"title": ended.title, "ok": ended.status == "done"} if ended else None,
            "lanes": _lanes(st), "more": max(len(st.orcs) - LANES_MAX, 0)}


def _tier(o: bk.PoolOrc) -> str:
    return tiers.TIER_LABELS.get(tiers.step_tier({"harness": o.harness, "model": o.model}) or "", "")


def _names(w) -> dict[str, str]:
    scroll = w.town.scroll
    return {b.id: b.title for b in getattr(scroll, "buildings", ())} if scroll is not None else {}


WANT_BY = {paths.TABLE: "by its table", paths.SORT: "by the sort"}


def _want(t: bk.PoolTask, names: dict[str, str]) -> dict:
    """Its kind of work and who named it (docs/design/barracks-flows.md §9): `Reply` · `from External listeners`,
    `by the sort`, `by its table`; a task no one named a kind for says nothing."""
    by = t.want_by if t.want else ""
    note = WANT_BY.get(by) or (f"from {names.get(by, by)}" if by else "")
    return {"want": lexicon.want_word(t.want), "want_note": note, "code_card": t.code_card}


def _kinds(w, names: dict[str, str]) -> dict:
    """What the pool takes and its table *source → kind of work*, one row per building a road brings carts
    from (its own setting, else the default for its type)."""
    table = w.want_table
    rows, seen = [], set()
    for road in getattr(w.town.scroll.building(w.building_id), "roads", ()) if w.town.scroll else ():
        src = road.source
        if src in seen:
            continue
        seen.add(src)
        spec = w.town.custom_specs.get(src)
        type_id = catalog.type_of(spec).id if spec else ""
        rows.append({"source": src, "title": names.get(src, src), "want": paths.by_source(table, src, type_id),
                     "own": src in (w.config.get("want_by_source") or {})})
    return {"wants": list(w.wants), "all": [{"id": k, "label": lexicon.want_word(k)} for k in paths.DEFAULT_WANTS],
            "table": rows}


def _task(t: bk.PoolTask, full: bool = False, names: dict[str, str] | None = None) -> dict:
    row = {"id": t.id, "title": t.title, "status": t.status, "lane": LANE_OF.get(t.status, "queue"), "ork": t.orc,
           "wait_for": t.wait_for, "branch": t.branch, "reworks": max(t.attempts - 1, 0), "warm": t.warm,
           "cost": _money(t.cost_usd) if t.cost_usd else "", "pr": t.pr, "pr_state": t.pr_state, "scope": t.scope,
           "asks": t.status == "asked", "draft": bool(t.draft), "arrived": t.arrived,
           "tier": t.tier, "persona": t.persona, "parent": t.parent, "part": t.sub, "after": list(t.after),
           "parts": len(t.plan), "overlaps": [_overlap(o) for o in t.overlaps], "held": t.held_since > 0,
           "design": t.design, "against": list(t.against), "designs": list(t.designs), "claimed": list(t.claimed),
           **_want(t, names or {})}
    if full:
        row.update({"brief": t.text[:KEEP], "report": t.result[:KEEP], "error": t.error, "notes": t.feedback,
                    "question": t.question, "target": bk.publish_kind(t.target)[1] or t.target,
                    "draft_text": t.draft[:KEEP], "decided": t.decided,
                    "files": list(t.files), "qa": [dict(zip(("q", "a", "who"), (list(x) + ["", "", ""])[:3])) for x in t.qa]})
    return row


def _overlap(o: dict) -> dict:
    return {k: o.get(k) or ("" if k not in ("paths", "conflicts") else []) for k in
            ("key", "title", "building", "paths", "branch", "pr", "status", "brief", "conflicts")}


def _areas(w) -> list[dict]:
    """The repository's areas in work (docs/design/barracks-designs.md §3), every pool's."""
    if w.claims_mode == "off":
        return []
    return [{"title": c.title, "building": c.building, "mine": c.building == w.building_id, "task": c.task,
             "paths": list(c.paths), "status": c.status, "pr": c.pr, "brief": c.brief, "guessed": c.guessed,
             "since": c.since[:16].replace("T", " ")} for c in w.area().load()]


def detail(w) -> dict:
    st, f = w.state, w.foreman
    asking = {t.orc for t in st.asked}
    orks = []
    for o in st.orcs:
        now = st.task(o.task) if o.task else None
        orks.append({"name": o.name, "label": o.label, "tier": _tier(o), "status": o.status,
                     "task": {"id": now.id, "title": now.title, "status": now.status} if now else None,
                     "done": o.done, "failed": o.failed, "cost": _money(o.cost_usd), "tokens": o.tokens,
                     "worktree": o.worktree, "branch": o.branch, "session": o.session, "asks": o.name in asking,
                     "recent": list(o.recent), "terminal": _key(w, o.name)})
    names = _names(w)
    tasks = [_task(t, True, names) for t in st.queue] + [_task(t, True, names) for t in reversed(st.tasks)]
    return {
        "keeper": w.keeper, "paused": st.paused, "max": f.max_orcs, "spent": _money(st.spent),
        "budget": _money(f.budget) if f.budget else "", "max_reworks": f.max_reworks,
        "providers": [h + (":" + m if m else "") for h, m in f.providers],
        "steward": str(w.config.get("steward") or "main"), "steward_cost": _money(st.steward_cost),
        "test_cmd": str(w.config.get("test_cmd") or ""), "worktrees": w.worktrees,
        "repo": str(w.code_root), "repo_own": bool(str(w.config.get("repo") or "").strip()),
        "recent": folders.recent(getattr(w.town, "machine", None)),
        "rules": [ln for ln in w.orders.splitlines() if ln.strip()],
        "orks": orks,
        "lanes": [{"id": lid, "label": label} for lid, label in LANES],
        "tasks": tasks,
        "asked": [_task(t, True, names) for t in st.asked],
        "decisions": [{"at": d.at[11:16], "action": d.action, "ork": d.orc, "why": d.why} for d in st.decisions(30)],
        "areas": _areas(w),
        "kinds": _kinds(w, names),
    }


# -- acts --------------------------------------------------------------------------------------------

def _new_task(w, args: dict) -> str:
    title, brief = text(args, "title", 500), text(args, "brief", 50_000)
    task = w.new_task(" ".join(title.split()), brief)
    if task is None:
        raise ActError("A task needs a title or a brief")
    return task.id


def _pause(w, args: dict) -> bool:
    return w.pause()


def _answer(w, args: dict) -> str:
    """The person's answer to the oldest question (or `task`'s): the rule the steward proposes from it."""
    task_id = text(args, "task", 100) or next((t.id for t in w.state.asked), "")
    task = w.state.task(task_id)
    if task is None or task.status != "asked":
        raise ActError("That question was answered already")
    return w.answer(task.id, text(args, "text", 20_000))


def _add_rule(w, args: dict) -> bool:
    rule = text(args, "rule", 1_000).strip()
    if not rule:
        raise ActError("An empty rule")
    return w.add_rule(rule)


def _wants(w, args: dict) -> list[str]:
    """The kinds of work it takes (`wants`: a list of change · reply · doc); what it takes now."""
    got = args.get("wants")
    if not isinstance(got, list) or any(pipes.want_of(x) not in paths.DEFAULT_WANTS for x in got):
        raise ActError("wants: a list of change, reply, doc")
    if not w.save_config({"wants": [x for x in paths.DEFAULT_WANTS if x in got]}):
        raise ActError("Not saved")
    return list(w.wants)


def _want_by_source(w, args: dict) -> str:
    """One row of its table: carts from `source` are `want` (change · reply · doc; "" takes the row out)."""
    source, want = text(args, "source", 100), str(args.get("want") or "")
    if not source or (want and pipes.want_of(want) not in paths.DEFAULT_WANTS):
        raise ActError("want_by_source: a source and change, reply, doc or nothing")
    table = {k: v for k, v in dict(w.config.get("want_by_source") or {}).items() if k != source}
    if want:
        table[source] = want
    if not w.save_config({"want_by_source": table or None}):
        raise ActError("Not saved")
    return want


def _diff(w, args: dict) -> dict:
    """The task's branch against its base, for Lake."""
    task = w.state.task(text(args, "task", 100))
    if task is None:
        raise ActError("That task is gone")
    if not task.branch or not w.uses_git:
        raise ActError("This task has no branch to show")
    orc = w.state.orc(task.orc)
    workdir = orc.worktree if orc is not None and orc.worktree else str(w.repo_root)
    try:
        commits, diff = w.task_git.diff(workdir, task.base, task.branch)
    except Exception as e:  # git that fails is said, never thrown at the page
        raise ActError(f"No diff: {e}") from None
    return {"title": f"{task.title} — {task.branch}", "text": diff or "(no changes on the branch)",
            "commits": commits}


def _key(w, name: str) -> str:
    return f"pool:{w.building_id}/{name.lower()}"


def _terminal(w, args: dict) -> str:
    """The ork's own terminal: its last session resumed on its worktree (a new one when it has none; in the
    sandbox, a shell there). The key of the session (core/sessions.py)."""
    orc = w.state.orc(text(args, "ork", 100))
    if orc is None:
        raise ActError("No such ork in this Barracks")
    sessions = getattr(w.town, "sessions", None)
    if sessions is None:
        raise ActError("Terminals open in the GUI and the TUI's War Tent")
    key = _key(w, orc.name)
    running = sessions.get(key)
    if running is not None and running.running:
        return key
    if orc.status == "working":
        raise ActError(f"{orc.name} is working — its terminal opens when it is free")
    cwd = orc.worktree or str(w.repo_root)
    if w.simulated:
        command, harness = [os.environ.get("SHELL") or "/bin/sh"], "shell"
    elif orc.session and orc.harness in harnesses.REGISTRY:
        command = past.resume_command(past.Session(orc.harness, orc.session)) or past.new_command(orc.harness)
        harness = orc.harness
    else:
        command, harness = past.new_command(orc.harness), orc.harness
    try:
        sessions.open(key, command, harness, f"{orc.name} · {w.title}", cwd=cwd,
                      env={"ORKCRAFT_ORC": f"{w.building_id}/{orc.name.lower()}"})
    except OSError as e:
        raise ActError(f"{orc.name}'s terminal did not open: {e}") from None
    return key


def _repo(w, args: dict) -> str:
    """The folder of code its orks work in (an existing project, its own git); "" gives it back to the town's own.
    It takes effect for the next ork it hires: the ones at work keep their worktrees."""
    path = text(args, "path", 2000).strip()
    if path:
        folder = Path(path).expanduser()
        if not folder.is_dir():
            raise ActError(f"No folder at {path}")
        path = str(folder.resolve())
        if getattr(w.town, "machine", None) is not None:
            folders.remember(w.town.machine, path)
    if not w.save_config({"repo": path or None}):
        raise ActError("Not saved")
    return str(w.code_root)


def _pick(w, args: dict) -> str:
    """The system's folder dialog (on a thread): a token to ask `picked` with."""
    return folders.start(text(args, "start", 2000).strip() or str(w.code_root))


def _picked(w, args: dict) -> dict:
    return folders.result(text(args, "token", 40))


ACTS = {"task": _new_task, "pause": _pause, "answer": _answer, "add_rule": _add_rule,
        "diff": _diff, "terminal": _terminal, "wants": _wants, "want_by_source": _want_by_source,
        "repo": _repo, "pick": _pick, "picked": _picked}
