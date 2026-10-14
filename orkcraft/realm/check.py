"""✅ `orkcraft check`: the gate before people use it (docs/design/check.md). Does the town do its main jobs well enough,
for a cost it should, and stay quiet when there is nothing to do?

    check.SCENARIOS                       the jobs it checks, each a few Test bench cases
    check.budgets(root)                   what "well enough" is: the defaults, then `.orkcraft/check/budgets.json`
    check.judge(reports, budget)          one case's runs against its budget → {"ok", "why", …}
    check.report(results, idle, budget)   the whole check as Markdown, green or red

A scenario's case runs in its building and in the bare AI tool, `repeat` times (core/bench.py), so the verdict reads
medians. A case passes when the building passed its check in most of its runs, is no worse than the bare tool, and its
time and spend over the bare tool's stay within the budget. The idle gate counts the model calls a town makes on its
own with nothing coming in (gui/idle_check.py): it must be none. No face and no model here.
"""
from __future__ import annotations

import datetime as dt
import json
import math
import statistics
from dataclasses import dataclass
from pathlib import Path

from orkcraft.realm import bench, check_pictures, explain

DIR = bench.BENCH.parent / "check"          # .orkcraft/check/<stamp>/report.md
PICTURE = "picture"                         # the pictures scenario's own kind: no bare tool to hold it against
LOOK = "look"                               # the windows' look, held against the last check's (gui/look_check.py)


@dataclass(frozen=True)
class Scenario:
    id: str
    title: str
    type: str                               # the building type its cases run in ("" : no kit for it yet)
    cases: tuple[str, ...]
    about: str = ""


SCENARIOS: tuple[Scenario, ...] = (
    Scenario("mail", "Mail sorted", "watchtower", ("customer-orders", "on-call", "sales-leads"),
             "External listeners read an inbox: what to keep, how important, who answers"),
    Scenario("todos", "Tasks from mail", "fields", ("mail-to-todos", "long-cards", "boiler-with-contacts"),
             "the Task board names to-dos from letters and plans them with the wiki"),
    Scenario("board", "Review board", "council", ("planted-flaws", "route-a-request"),
             "several orks debate a design and send a letter down the right exit"),
    Scenario("pictures", "Pictures redrawn", PICTURE, tuple(c["id"] for c in check_pictures.CASES),
             "the Alchemist paints a sprite again from a person's words; a judge compares before and after"),
    Scenario("looks", "Windows look right", LOOK, ("windows",),
             "every building's window pictured and held against the last check; a changed one judged: broken or not"),
    Scenario("wiki", "Wiki from mail", "", (),
             "the Wiki takes in what letters say: no Test bench kit for it yet"),
)

DEFAULTS = {
    "tool": "main",              # the AI tool both sides run on: the main one (Claude Code unless another is chosen);
                                 # never agy unless named (experimental: decisions-2026-10.md §5)
    "tier": "novice",            # …on its lightest model
    "repeat": 3,                 # runs of each case: the verdict reads medians
    "pass_share": 2 / 3,         # of its runs the building must pass its check in
    "time_over": 0.5,            # the building's median time at most this share over the bare tool's
    "spend_over": 0.3,           # …and its spend (tokens when the tool says no price)
    "max_spend": 2.0,            # $ one run of the building's side may spend before it is cut
    "idle_calls": 0,             # model calls a quiet town may make on its own
    "idle_hours": 8,             # how long the quiet town is ticked (a minute a tick)
    "picture_score": 6,          # of 10, the judge's least for a picture redrawn
}


def budgets(root: Path) -> dict:
    """The defaults, with what `.orkcraft/check/budgets.json` sets over them."""
    try:
        own = json.loads((root / DIR / "budgets.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        own = {}
    return {**DEFAULTS, **{k: v for k, v in (own if isinstance(own, dict) else {}).items() if k in DEFAULTS}}


def picked(names: list[str] | None = None) -> list[Scenario]:
    """The scenarios asked for by id (all when none)."""
    return [s for s in SCENARIOS if not names or s.id in names]


def _passed(s: bench.Side) -> bool:
    return bool(s.passed) and not s.error


def judge(reports: list[bench.Report], budget: dict) -> dict:
    """One case's runs (its repeats) against the budget."""
    pairs = [r for r in reports if r.building is not None and r.bare is not None]
    if not pairs:
        why = next((r.building.error for r in reports if r.building is not None and r.building.error), "") or "no run"
        return {"ok": False, "why": f"it did not run: {why}"[:300], "runs": 0}
    n = len(pairs)
    building = sum(_passed(r.building) for r in pairs)
    bare = sum(_passed(r.bare) for r in pairs)
    g = bench.pooled_gaps(pairs)
    need = math.ceil(budget["pass_share"] * n - 1e-9)
    why = []
    if building < need:
        why.append(f"passed {building} of {n} runs (needs {need})")
    if building < bare:
        why.append(f"worse than the bare AI tool ({building}/{n} against {bare}/{n})")
    if g["time"] is not None and g["time"] > budget["time_over"]:
        why.append(f"time {g['time']:+.0%} over the bare tool (budget {budget['time_over']:+.0%})")
    if g["spend"] is not None and g["spend"] > budget["spend_over"]:
        unit = " tokens" if g["spend_by"] == "tokens" else ""
        why.append(f"spend {g['spend']:+.0%}{unit} over the bare tool (budget {budget['spend_over']:+.0%})")
    cut = sum(1 for r in pairs if r.building.cut)
    if cut:
        why.append(f"{cut} run{'s' if cut > 1 else ''} cut at the spend or time limit")
    return {"ok": not why, "why": "; ".join(why), "runs": n, "building": building, "bare": bare,
            "time": g["time"], "spend": g["spend"], "spend_by": g["spend_by"], "time_range": g.get("time_range"),
            "cost": round(sum(r.building.cost for r in pairs) / n, 4),
            "tokens": int(statistics.median(r.building.tokens for r in pairs)),
            "seconds": round(statistics.median(r.building.seconds for r in pairs), 1)}


def judge_pictures(runs: list[dict], budget: dict) -> dict:
    """One picture case's runs (realm/check_pictures.py `run`) against the budget."""
    if not runs:
        return {"ok": False, "why": "it did not run", "runs": 0}
    n = len(runs)
    good = sum(check_pictures.passed(r, budget["picture_score"]) for r in runs)
    need = math.ceil(budget["pass_share"] * n - 1e-9)
    scores = sorted(r["score"] for r in runs if r.get("score") is not None)
    why = []
    if good < need:
        bad = next((r for r in runs if not check_pictures.passed(r, budget["picture_score"])), {})
        why.append(f"passed {good} of {n} runs (needs {need}): " + (
            bad.get("error") or ("no PNG" if not bad.get("png") else "the wrong size" if not bad.get("size_ok")
                                 else "the same picture again" if not bad.get("changed")
                                 else f"the judge gave {bad.get('score')}/10: {bad.get('notes', '')}"))[:300])
    return {"ok": not why, "why": "; ".join(why), "runs": n, "building": good,
            "score": scores[len(scores) // 2] if scores else None,
            "seconds": sorted(r["seconds"] for r in runs)[n // 2]}


def _pct(v) -> str:
    return "—" if v is None else f"{v:+.0%}"


def report(results: list[dict], idle: dict | None, budget: dict, tool: str = "main", at: str = "") -> tuple[bool, str]:
    """(green, the report as Markdown). `results`: [{"scenario": Scenario, "cases": [(case id, judge(...))]}];
    `idle`: {"calls": n, "by": [[who, n], …], "hours": h} or None when it was not checked."""
    rows, green = [], True
    for res in results:
        sc = res["scenario"]
        if not sc.type:
            rows.append(f"| {sc.title} | — | — | — | — | — | not checked: {sc.about.split(': ')[-1]} |")
            continue
        for cid, j in res["cases"]:
            green = green and j["ok"]
            if sc.type == LOOK:
                share = "" if j.get("share") is None else f"{j['share']:.0%} changed"
                rows.append(f"| {sc.title} | {cid} | {share or '—'} | — | — | {'✅' if j['ok'] else '❌'} | "
                            f"{j['why'] or 'as before'} |")
                continue
            if sc.type == PICTURE:
                score = "—" if j.get("score") is None else f"{j['score']:g}/10"
                rows.append(f"| {sc.title} | {cid} | {j.get('building', 0)}/{j['runs']} · judge {score} | "
                            f"{j.get('seconds', 0):.0f} s | — | {'✅' if j['ok'] else '❌'} | "
                            f"{j['why'] or 'within the budget'} |")
                continue
            spend = _pct(j.get("spend")) + (" tokens" if j.get("spend_by") == "tokens" else "")
            check = f"{j.get('building', 0)}/{j['runs']} · {j.get('bare', 0)}/{j['runs']}" if j["runs"] else "—"
            rows.append(f"| {sc.title} | {cid} | {check} | {_pct(j.get('time'))} | {spend} | "
                        f"{'✅' if j['ok'] else '❌'} | {j['why'] or 'within the budget'} |")
    times = "once" if int(budget["repeat"]) == 1 else f"{budget['repeat']} times"
    out = [f"# Orkline check · {at or dt.datetime.now().isoformat(timespec='minutes')}", "",
           f"AI tool: {tool}{', ' + budget['tier'] if budget.get('tier') else ''} · each case {times} · budget: passes in ≥ {budget['pass_share']:.0%} "
           f"of runs, no worse than the bare tool, time ≤ {budget['time_over']:+.0%} and spend ≤ "
           f"{budget['spend_over']:+.0%} over it (medians); a picture judged ≥ {budget['picture_score']}/10", ""]
    if rows:
        out += ["| Scenario | Case | Check: building · bare | Time | Spend | | Why |", "|---|---|---|---|---|---|---|", *rows]
    if idle is not None:
        ok = idle["calls"] <= budget["idle_calls"]
        green = green and ok
        out += ["", f"**Idle:** {idle['calls']} model call{'' if idle['calls'] == 1 else 's'} in {idle['hours']} hours of a "
                    f"quiet town {'✅' if ok else '❌'} (budget {budget['idle_calls']})"]
        out += [f"- {n} × {who}" for who, n in idle.get("by") or []]
    out += ["", f"**{'GREEN' if green else 'RED'}**" + ("" if green else ": what is ❌ above is what to fix first")]
    return green, "\n".join(out) + "\n"


def told(root: Path, series: str, scenarios: list[dict]) -> dict:
    """The check in words: each case's story (realm/explain.py), by scenario, and what to change.
    `scenarios`: results.json's ([{"id", "type", "cases": [{"case", "ok", "why", …}]}])."""
    titles = {s.id: s.title for s in SCENARIOS}
    out, every = [], []
    for sc in scenarios:
        stories = []
        for c in sc.get("cases") or []:
            cid = c.get("case", "")
            if sc.get("type") == LOOK:
                stories.append({"case": "every window" if cid == "windows" else f"the {cid} window",
                                "status": "good" if c.get("ok") else "bad", "summary": c.get("why") or "As before.",
                                "details": [], "changes": [] if c.get("ok") else [{
                                    "what": f"Fix how the {cid} window reads", "why": c.get("why") or "",
                                    "case": cid, "weight": 2}]})
                continue
            if sc.get("type") == PICTURE:
                words = next((p["words"] for p in check_pictures.CASES if p["id"] == cid), cid)
                score = c.get("score")
                stories.append({"case": f"“{words}”", "status": "good" if c.get("ok") else "bad",
                                "summary": (f"Redrawn and judged {score:g}/10." if c.get("ok") and score is not None
                                            else c.get("why") or "It did not pass."), "details": [],
                                "changes": [] if c.get("ok") else [{"what": "Make the Alchemist's pictures pass",
                                                                    "why": c.get("why") or "", "case": cid,
                                                                    "weight": 2}]})
                continue
            reports = [r for r in bench.runs(root, sc.get("type") or "") if r.series == series and r.case == cid]
            case = bench.case(root, sc.get("type") or "", cid)
            title = case.title if case is not None else cid
            stories.append(explain.story(title, reports, {r.id: bench.calls_of(root, r) for r in reports})
                           if reports else {"case": title, "status": "bad", "summary": c.get("why") or "It did not run.",
                                            "details": [], "changes": []})
        every += stories
        out.append({"id": sc.get("id"), "title": titles.get(sc.get("id"), sc.get("id")), "stories": stories})
    return {"scenarios": out, "changes": explain.changes(every)}


def words(told_: dict) -> str:
    """`told` as Markdown, for report.md and an agent's README."""
    mark = {"good": "✓", "watch": "!", "bad": "✗"}
    out = []
    for sc in told_["scenarios"]:
        if not sc["stories"]:
            continue
        out += [f"**{sc['title']}**"] + [f"- {mark[s['status']]} {s['case']}: {s['summary']}"
                                          + "".join(f"\n  - {d}" for d in s["details"]) for s in sc["stories"]] + [""]
    if told_["changes"]:
        out += ["**What to change**"] + [f"{n}. {c['what']} — {c['why']}" + (f" ({', '.join(c['cases'])})"
                                                                              if c["cases"] else "")
                                         for n, c in enumerate(told_["changes"], 1)]
    return "\n".join(out).strip()
