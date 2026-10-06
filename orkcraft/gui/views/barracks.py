"""🏕 Barracks in the GUI: the orks and their tasks, the queue, the steward's questions and rules.
Every act is the worker's (core/workers/barracks.py); an ork's terminal is a session of the core's
sessions service (core/sessions.py), opened on its own worktree."""
from __future__ import annotations

import os

from orkcraft.gui.views import ActError, text
from orkcraft.realm import barracks as bk
from orkcraft.realm import tiers
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


def card(w) -> dict:
    """Closed (docs/design/building-views.md): `active 2/4 · queue 3`, `✓5 ✗1 · $1.20`, `<keeper> asks` first."""
    st, f = w.state, w.foreman
    return {"asks": w.keeper if st.asked else "",
            "active": sum(1 for o in st.orcs if o.status == "working"), "max": f.max_orcs, "queue": len(st.queue),
            "done": sum(1 for t in st.tasks if t.status == "done"),
            "failed": sum(1 for t in st.tasks if t.status == "failed"),
            "spent": _money(st.spent), "paused": st.paused}


def _tier(o: bk.PoolOrc) -> str:
    return tiers.TIER_LABELS.get(tiers.step_tier({"harness": o.harness, "model": o.model}) or "", "")


def _task(t: bk.PoolTask, full: bool = False) -> dict:
    row = {"id": t.id, "title": t.title, "status": t.status, "lane": LANE_OF.get(t.status, "queue"), "ork": t.orc,
           "wait_for": t.wait_for, "branch": t.branch, "reworks": max(t.attempts - 1, 0), "warm": t.warm,
           "cost": _money(t.cost_usd) if t.cost_usd else "", "pr": t.pr, "pr_state": t.pr_state, "scope": t.scope,
           "asks": t.status == "asked", "draft": bool(t.draft), "arrived": t.arrived,
           "tier": t.tier, "persona": t.persona, "parent": t.parent, "part": t.sub, "after": list(t.after),
           "parts": len(t.plan)}
    if full:
        row.update({"brief": t.text[:KEEP], "report": t.result[:KEEP], "error": t.error, "notes": t.feedback,
                    "question": t.question, "target": t.target, "draft_text": t.draft[:KEEP], "decided": t.decided,
                    "files": list(t.files), "qa": [dict(zip(("q", "a", "who"), (list(x) + ["", "", ""])[:3])) for x in t.qa]})
    return row


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
    tasks = [_task(t, full=True) for t in st.queue] + [_task(t, full=True) for t in reversed(st.tasks)]
    return {
        "keeper": w.keeper, "paused": st.paused, "max": f.max_orcs, "spent": _money(st.spent),
        "budget": _money(f.budget) if f.budget else "", "max_reworks": f.max_reworks,
        "providers": [h + (":" + m if m else "") for h, m in f.providers],
        "steward": str(w.config.get("steward") or "claude"), "steward_cost": _money(st.steward_cost),
        "test_cmd": str(w.config.get("test_cmd") or ""), "worktrees": w.worktrees,
        "rules": [ln for ln in w.orders.splitlines() if ln.strip()],
        "orks": orks,
        "lanes": [{"id": lid, "label": label} for lid, label in LANES],
        "tasks": tasks,
        "asked": [_task(t, full=True) for t in st.asked],
        "decisions": [{"at": d.at[11:16], "action": d.action, "ork": d.orc, "why": d.why} for d in st.decisions(30)],
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
    elif orc.session and orc.harness in ("claude", "codex", "agy"):
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


ACTS = {"task": _new_task, "pause": _pause, "answer": _answer, "add_rule": _add_rule,
        "diff": _diff, "terminal": _terminal}
