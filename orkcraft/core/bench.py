"""🧪 The Test bench's building side (docs/design/test-bench.md §3.2): a town opened on the case's copy of the
project, the building raised there with the config it has in the operator's town (the bench's AI tool and
tier on top), the case's task given to it, and what it did read back once it is done.

    bench.run_building(case, project, base, template, tool, tier, max_spend) → realm.bench.Side
    bench.run(root, case, tool, tier, …)                                     → realm.bench.Report, both sides

The copy has no `origin` (realm/bench.py), so the building cannot push or open a pull request. Nothing here
writes to the operator's town: the copy has its own `.orkcraft/`. One town at a time (`Town` clears the
typed roads), so a face runs the bench as `orkcraft bench`, in a process of its own.
"""
from __future__ import annotations

import datetime as dt
import threading
import time
from pathlib import Path
from typing import Callable

from orkcraft.core import buildings
from orkcraft.core.town import Town
from orkcraft.realm import bench, checkpoint, masonry

TYPES = ("barracks",)                    # what the bench runs so far
TIMEOUT_S = 45 * 60                      # the building's side gives up after this
POLL_S = 1.0
# The bench's own say over a raised building: its work stays in the copy, the case's check is its tests,
# and its spend stops at the run's limit.
_KEEP_OUT = ("repo", "notes", "base")    # settings that point at the operator's own project or town


def template_of(root: Path, type_id: str, building_id: str = "") -> dict:
    """The config of the operator's building of that type (the one named, else the first), to raise as it is."""
    specs, _problems = masonry.load_specs(root)
    for s in specs:
        if s.get("type") == type_id and (not building_id or s.get("id") == building_id):
            return dict(s.get("config") or {})
    return {}


def bench_config(template: dict, case: bench.Case, tool: str, tier: str, max_spend: float) -> dict:
    config = {k: v for k, v in template.items() if k not in _KEEP_OUT}
    config.update(worktrees=True, budget_usd=max_spend)
    if case.check:
        config["test_cmd"] = case.check
    if tool != "main" or tier:
        entry = f"{tool}:{tier}" if tier else tool
        config["providers"] = [entry]
        config["steward"] = entry
    return config


def _settled(w, root_id: str) -> str:
    """"" while the task works; else done | failed | asked."""
    st = w.state
    if st.asked:
        return "asked"
    task = st.task(root_id)
    status = task.status if task is not None else ""
    return status if status in ("done", "failed") else ""


def run_building(case: bench.Case, project: Path, base: str, template: dict, tool: str = "main", tier: str = "",
                 max_spend: float = bench.DEFAULT_MAX_SPEND, timeout_s: float = TIMEOUT_S,
                 cancel: threading.Event | None = None, check_dir: Path | None = None,
                 say: Callable[[str], None] = lambda _line: None) -> bench.Side:
    """The building on the case, in a town of its own on `project`; then its result's check in `check_dir`.
    `say` hears each of its decisions as it is taken."""
    checkpoint.ensure(project)
    town = Town(project, auto_commit=False, layout_file=project / ".orkcraft.json")
    side, start, started = bench.Side("building"), time.monotonic(), dt.datetime.now()
    try:
        spec = buildings.type_spec(town, case.type)
        if spec is None:
            raise ValueError(f"no building type {case.type!r}")
        spec["config"] = bench_config({**(spec.get("config") or {}), **template}, case, tool, tier, max_spend)
        built = buildings.raise_spec(town, spec)
        if built is None:
            raise ValueError("the building was refused: " + "; ".join(town.scroll_problems[-3:]))
        w = town.worker(built.id)
        task = w.new_task(case.title, case.task)
        if task is None:
            raise ValueError("the case has no task")
        root_id, how, heard = task.id, "", 0
        while True:
            decisions = _in_order(w.state)
            for d in decisions[heard:]:
                say(f"+{_clock(time.monotonic() - start)} {_line(d)}")
            heard = len(decisions)
            if (how := _settled(w, root_id)):
                break
            if cancel is not None and cancel.is_set():
                how = "stopped"
            elif w.state.spent > max_spend:
                how, side.cut = "over its spend limit", True
            elif time.monotonic() - start > timeout_s:
                how, side.cut = f"over {int(timeout_s // 60)} minutes", True
            if how:
                w.stop()
                break
            time.sleep(POLL_S)
        side.seconds = round(time.monotonic() - start, 1)
        _read(w, root_id, how, side, started)
        if side.error:
            return side
        task = w.state.task(root_id)
        branch = task.branch if task is not None else ""
        if branch:
            side.files, side.lines = bench.changed(project, base, branch)
            where = check_dir or project.parent / "building-result"
            _worktree(project, where, branch)
            side.where = str(where)
            side.passed, side.check_tail = bench.check(case, where)
    except (ValueError, RuntimeError, OSError) as e:
        side.error = side.error or str(e)[:500]
        side.seconds = side.seconds or round(time.monotonic() - start, 1)
    finally:
        town.close()
    return side


def _clock(seconds: float) -> str:
    return f"{int(seconds // 60)}:{int(seconds % 60):02d}"


def _in_order(st) -> list:
    """The building's decisions, oldest first (its state reads them newest first)."""
    return list(reversed(st.decisions(500)))


def _line(d, limit: int = 200) -> str:
    """One line: a report's Markdown is folded onto it and cut on a word."""
    text = " ".join(f"{d.action}: {d.orc + ' — ' if d.orc else ''}{d.why}".split())
    if len(text) <= limit:
        return text
    return text[:limit - 1].rsplit(" ", 1)[0].rstrip(" ,;:—-") + "…"


def _steps(decisions, started: dt.datetime) -> list[dict]:
    """The decisions on the run's clock: seconds from its start, who (an ork, else the steward), what and why."""
    out = []
    for d in decisions:
        try:
            at = dt.datetime.fromisoformat(d.at).replace(tzinfo=None)
        except (TypeError, ValueError):
            continue
        out.append({"t": round(max(0.0, (at - started.replace(microsecond=0)).total_seconds()), 1),
                    "who": d.orc or "steward", "action": d.action, "why": d.why[:300]})
    return out


def _read(w, root_id: str, how: str, side: bench.Side, started: dt.datetime) -> None:
    st = w.state
    task = st.task(root_id)
    parts = [t for t in st.tasks + st.queue if t.parent == root_id]
    side.cost = round(st.spent, 4)
    side.tokens = sum(o.tokens for o in st.orcs)
    side.orks = len(st.orcs)
    side.text = ((task.result or task.error) if task is not None else "")[:4000]
    if how not in ("done", "failed"):
        side.error = {"asked": "it waits for an answer: " + "; ".join(t.question or t.title for t in st.asked)[:300]}\
            .get(how, f"stopped: {how}")
    elif how == "failed":
        side.error = (task.error if task is not None else "") or "the task failed"
    if task is not None:
        if task.kind:
            side.how.append(f"sorted as {task.kind}")
        if parts:
            side.how.append(f"planned in {len(parts)} parts: " + ", ".join(p.sub or p.title for p in parts))
        if task.attempts > 1:
            side.how.append(f"{task.attempts - 1} rework(s)")
    decisions = _in_order(st)
    side.how += [_line(d) for d in decisions[-40:]]
    side.steps = _steps(decisions, started)


def _worktree(project: Path, where: Path, branch: str) -> None:
    if where.exists():
        bench.git(project, "worktree", "remove", "--force", str(where))
    bench.git(project, "worktree", "add", "-q", "--detach", str(where), branch)


def run(root: Path, case: bench.Case, tool: str = "main", tier: str = "", building_id: str = "",
        max_spend: float = bench.DEFAULT_MAX_SPEND, sides: tuple[str, ...] = ("building", "bare"),
        say: Callable[[str], None] = lambda _line: None, cancel: threading.Event | None = None,
        bare_runner=None, orders: str | None = None) -> tuple[bench.Report, Path]:
    """One run of a case, the building's side then the bare tool's, each in its own copy; kept in its run folder.
    `orders`: the building's instructions for this run only (None: its own)."""
    now = dt.datetime.now()
    folder = bench.run_dir(root, case, now)
    report = bench.Report(id=folder.name, type=case.type, case=case.id, tool=tool, tier=tier,
                          at=now.isoformat(timespec="seconds"), orders_changed=orders is not None)
    template = template_of(root, case.type, building_id)
    if orders is not None:
        template["orders"] = orders
    if "building" in sides:
        say("the building works on the case…")
        project = folder / "building"
        base = bench.make_project(case, root, project)
        report.building = run_building(case, project, base, template, tool, tier, max_spend, cancel=cancel,
                                       check_dir=folder / "building-result", say=say)
        report.save(folder)
    if "bare" in sides and not (cancel is not None and cancel.is_set()):
        say("the bare AI tool works on the case…")
        project = folder / "bare"
        bench.make_project(case, root, project)
        report.bare = bench.bare(case, project, tool, tier, cancel, runner=bare_runner)
    report.save(folder)
    return report, folder
