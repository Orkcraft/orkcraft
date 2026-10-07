"""The retros and the orks' own changes, without a face: what the TUI's retros and night do
(tui/retros.py, tui/night.py), for a face that drives them — the GUI's host.

    daily_job(town, now)          the Building retro when `optimize_at` is due: a function to run in a
                                  thread (the Council's one proposal) and `daily_done` with its result
    weekly_job(town, now)         the Town retro when `weekly_at` is due, and `weekly_done`
    apply_weekly_item(town, …)    one Town retro item applied, checked again against the town as it is
    apply_change(town, c)         a change the orks may make themselves tonight (core/night.py `candidates`)
    probation(town, now)          their changes on probation: one with a 👎 or more failed runs since is
                                  taken back, one that lived through 24 h is kept
    hushed(town)                  what the orks do in quiet hours says no toast: the list after them does

Nothing here shows a dialog: it changes the town and says so with a toast (or, hushed, not at all).
"""
from __future__ import annotations

import contextlib
import copy
import datetime as dt
import functools
from typing import Any, Callable, Iterator

from orkcraft.core import buildings as core_buildings
from orkcraft.core import bus, runners, treasury
from orkcraft.core.town import Town
from orkcraft.realm import (audit, builders, checkpoint, evolution, fastpath, feedback, optimize, steward,
                            weekly, workshop)


@contextlib.contextmanager
def hushed(town: Town) -> Iterator[None]:
    """The orks at work in quiet hours: no toasts — the ledger and the list after quiet hours tell."""
    town.toast = lambda *a, **k: None            # type: ignore[method-assign]
    try:
        yield
    finally:
        del town.toast


def _limits(town: Town) -> tuple[list, list[str]]:
    """(the Town Hall's last quota reads, the enabled subscription tools): what a building's pressure is
    measured against (realm/pressure.py)."""
    hall = town.workers.get("town_hall")
    return list(getattr(hall, "limits", None) or []), treasury.subscriptions(town.machine)


# -- 🔧 the Building retro (daily) ---------------------------------------------------------------------

def daily_job(town: Town, now: dt.datetime) -> Callable[[], optimize.Result] | None:
    """When `optimize_at` is due: today's hungriest building the operator is not happy with, and the
    work that asks the Council for one proposal (run it in a thread). None when nothing is due."""
    repo = town.repo_root
    expr = str(fastpath.settings(repo).get("optimize_at") or "")
    if town.demo or not expr or not steward.due(expr, optimize.last_run(repo), now):
        return None
    optimize.mark_run(repo, now)
    goals = {b.id: b.aim for b in town.scroll.buildings if not b.demolished}
    cand = optimize.leader(repo, None, *_limits(town), goals=goals)
    if cand is None:
        return None
    spec = town.custom_specs.get(cand.building)
    ps = optimize.parts(town.scroll, spec, cand.building, repo)
    if not ps:
        return None
    cfg = (spec or {}).get("config") or {}
    mocks = workshop.load_blueprint(repo, cand.building).get("mocks") or []
    runtime = str(cfg.get("runtime") or "python")
    return lambda: optimize.propose(repo, cand, ps, runners.OPTIMIZE_RUNNER or builders.main_runner, runtime, mocks)


def daily_done(town: Town, result: optimize.Result) -> None:
    """The Council's proposal is kept for the operator (the Town Hall lists it: Apply / Dismiss)."""
    if result.proposal is None:
        return
    optimize.save(town.repo_root, result.proposal)
    town.publish(bus.HALL)
    town.toast(f"a proposal for {town.title_of(result.proposal.building)} waits in the Town Hall",
               title="🔧 Building retro")


# -- 🗓 the Town retro (weekly) ------------------------------------------------------------------------

def weekly_job(town: Town, now: dt.datetime) -> Callable[[], weekly.Result] | None:
    """When `weekly_at` is due: the heavy model over the whole town (run it in a thread)."""
    repo = town.repo_root
    expr = str(fastpath.settings(repo).get("weekly_at") or "")
    if town.demo or not expr or not steward.due(expr, weekly.last_run(repo), now):
        return None
    weekly.mark_run(repo, now)
    model = str(fastpath.settings(repo).get("weekly_model") or "opus")
    runner = runners.WEEKLY_RUNNER or functools.partial(builders.main_runner, model=model)
    rules = audit.run(repo, town.scroll, dict(town.custom_specs), town.snapshot.spent_usd,
                      town.scroll.budget.gold_session_limit_usd)
    snapshot, specs = copy.deepcopy(town.scroll), copy.deepcopy(town.custom_specs)
    return lambda: weekly.run(repo, snapshot, specs, runner, model, rules)


def weekly_done(town: Town, result: weekly.Result) -> None:
    if result.report is None:
        town.toast(result.error or "no report", title="🗓 Town retro failed", severity="warning")
        return
    town.publish(bus.HALL)
    waiting = sum(1 for i in result.report.items if i.applicable)
    town.toast(f"{waiting} change(s) wait in the Town Hall" if waiting else "nothing to change this week",
               title="🗓 Town retro")


def apply_weekly_item(town: Town, report: weekly.Report, n: int, by: str = "you") -> bool:
    """One item of the Town retro, checked again against the town as it is now, applied with its own
    checkpoint `weekly(<id>)` and a line in the ledger. A removal stays the TUI's (it asks first)."""
    item = next((i for i in report.items if i.n == n), None)
    if item is None or n in report.applied:
        return False
    item = weekly.check_item(item, town.repo_root, town.scroll, town.custom_specs)
    if not item.applicable:
        town.toast(f"{item.title}: {'; '.join(item.problems) or 'advice only'}", title="🗓 Not applied", severity="warning")
        return False
    bid, ok = item.building, False
    if item.change in optimize.ACTIONS:
        p = optimize.Proposal(f"w{report.ts[:10]}-{item.n}", report.ts, bid, item.change, str(item.data.get("target")),
                              item.before, item.after, item.why)
        ok = core_buildings.apply_proposal(town, p, kind="weekly", by=by)       # its line in the ledger, too
    elif item.change == "add_building":
        spec = weekly.new_spec(item)
        ok = core_buildings.raise_spec(town, spec) is not None
        bid = spec["id"]
    elif item.change == "set_config":
        spec = town.custom_specs.get(bid)
        if spec is not None:
            new = dict(spec, config={**(spec.get("config") or {}), str(item.data["key"]): item.data.get("value")})
            problems = core_buildings.set_spec(town, bid, new)
            if problems:
                town.toast("; ".join(problems), title="🗓 Not applied", severity="warning")
            else:
                town.checkpoint("weekly", bid, f"set {item.data['key']}: {item.why[:60]}")
                ok = True
    else:
        town.toast(f"{item.title}: removals are applied in the TUI, which asks first", title="🗓 Not applied")
        return False
    if not ok:
        return False
    if item.change not in optimize.ACTIONS:
        last = checkpoint.history(town.repo_root, bid, 1)
        evolution.record(town.repo_root, evolution.Change(
            bid, item.change, "weekly", item.title[:120], item.why[:200], by=by,
            sha=last[0].sha if last else "", key=f"weekly:{report.ts}:{item.n}"))
    report.applied = sorted(set(report.applied) | {item.n})
    weekly.save(town.repo_root, report)
    town.publish(bus.HALL)
    return True


def decline_weekly_item(town: Town, report: weekly.Report, n: int) -> None:
    """The operator said no to one item: it is not applied, by them or by the orks."""
    report.declined = sorted(set(report.declined) | {n})
    weekly.save(town.repo_root, report)
    town.publish(bus.HALL)


# -- 🌙 the orks' own changes ---------------------------------------------------------------------------

def apply_change(town: Town, c: dict[str, Any]) -> bool:
    """A change the orks make themselves tonight (core/night.py `candidates`), hushed."""
    with hushed(town):
        if c["source"] == "steward":
            return core_buildings.apply_steward(town, c["building"], c["data"], c["index"], by="orcs") is not None
        if c["source"] == "daily":
            return core_buildings.apply_proposal(town, c["proposal"], kind="auto-improve", by="orcs")
        return apply_weekly_item(town, c["report"], c["item"].n, by="orcs")


def revert_change(town: Town, change: evolution.Change, note: str, seen: bool = False) -> bool:
    """Take one change back — only while it is still its building's last checkpoint, so nothing newer is
    lost; otherwise it is marked stuck and the operator decides (Revert under the steward)."""
    last = checkpoint.history(town.repo_root, change.building, 1)
    if not change.sha or not last or last[0].sha != change.sha:
        change.status, change.note, change.seen = "stuck", f"{note} — changed since, Revert on it decides", seen
        evolution.update(town.repo_root, change)
        return False
    with hushed(town):
        ok = core_buildings.revert(town, change.building)
    change.status, change.note, change.seen = ("reverted" if ok else "stuck"), note, seen
    evolution.update(town.repo_root, change)
    return ok


def probation(town: Town, now: dt.datetime | None = None) -> list[evolution.Change]:
    """The orks' changes on probation: taken back on a 👎 or more failed runs since, kept after 24 h.
    The ones taken back (the operator is told)."""
    now = now or dt.datetime.now()
    feedback.sweep_unseen(town.repo_root, now)          # results nobody opened for a day
    reverted = []
    for change in evolution.on_probation(town.repo_root):
        reason = evolution.verdict(town.repo_root, change, now)
        if reason is None:
            if now >= change.until:
                change.status = "kept"
                evolution.update(town.repo_root, change)
            continue
        if revert_change(town, change, f"probation: {reason}"):
            reverted.append(change)
    if reverted:
        names = ", ".join(f"{town.title_of(c.building)} ({c.change})" for c in reverted[:3])
        town.toast(f"{names} — {reverted[0].note}", title=f"↩ {len(reverted)} change(s) by the orks taken back",
                   severity="warning", timeout=15)
    return reverted


def morning_words(town: Town) -> str:
    """The list after quiet hours: what the orks changed while the operator was away (then seen)."""
    changes = [c for c in evolution.unseen(town.repo_root) if c.by == "orcs"]
    evolution.mark_seen(town.repo_root)
    if not changes:
        return ""
    lines = [f"{town.title_of(c.building)}: {c.summary}" for c in changes[:5]]
    more = f"\n…and {len(changes) - 5} more" if len(changes) > 5 else ""
    return "\n".join(lines) + more + "\nEach is on probation for 24 h; Revert under its steward takes it back."
