"""A Test bench's code change as a pull request with its evidence (docs/design/improve-buildings.md §4).

What goes: the files the change touched, each as installed and as changed (realm/code_overlay.py), and a body that
says the goal, the scheme, each case set (what its cases do and where, never their inputs: those may be the person's)
and how the building did against the bare AI tool on the runs made with the change. It may go only when the building
is ahead on the goal's metric in most of the cases run with it.

    lab_pr.files(state_dir)                          {path: (as installed, as changed)}
    lab_pr.ready(cases, results, since, metric)      (True, "") or (False, why not)
    lab_pr.body(…)                                   the pull request's description
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import orkcraft
from orkcraft.realm import code_overlay

TITLE_CHARS = 72


def files(state_dir: Path) -> dict[str, tuple[str, str]]:
    top = code_overlay.root(state_dir)
    out = {}
    for path in code_overlay.changed(state_dir):
        shown = subprocess.run(["git", "show", f"{code_overlay.BASE}:{path}"], cwd=top, capture_output=True, text=True)
        base = shown.stdout if shown.returncode == 0 else ""     # "": a file the change added
        now = top / path
        out[path] = (base, now.read_text(encoding="utf-8") if now.is_file() else "")
    return out


def with_change(cases: list[dict], results: dict, since: str) -> list[tuple[dict, dict]]:
    """The cases run with the change on (their last run after it was made), each with what it said."""
    return [(c, results[c["id"]]) for c in cases
            if c["id"] in results and results[c["id"]].get("scheme") and str(results[c["id"]].get("at") or "") >= since]


def _ahead(r: dict, metric: str) -> bool:
    key = {"tokens": "tokens", "time": "time"}.get(metric, "quality")
    v = r.get(key)
    return v is not None and (v > 0 if key == "quality" else v < 0)


def ready(cases: list[dict], results: dict, since: str, metric: str) -> tuple[bool, str]:
    rows = with_change(cases, results, since)
    if not rows:
        return False, "Run the cases with the change first: a pull request carries what they said"
    ahead = sum(_ahead(r, metric) for _c, r in rows)
    if ahead * 2 <= len(rows):
        return False, f"Ahead of the bare AI tool on {metric} in {ahead} of {len(rows)} cases run with it: it goes " \
                      "when it is ahead in most"
    return True, ""


def title(why: str) -> str:
    line = " ".join((why or "An improvement from the Test bench").split(";")[0].split())
    return line[:TITLE_CHARS]


def body(goal: str, about: str, why: str, metric: str, sets: list[dict], rows: list[tuple[dict, dict]],
         touched: list[str], data_changes: list[str]) -> str:
    def pct(v):
        return "—" if v is None else f"{v:+.0%}"

    ahead = sum(_ahead(r, metric) for _c, r in rows)
    lines = [f"Sent from a Test bench in Orkcraft {orkcraft.__version__} (the Mechanic).", "",
             "## What it changes", why or "—", "", "Files: " + ", ".join(f"`{f}`" for f in touched), "",
             "## The goal", goal or "do better than the bare AI tool", "", f"Scheme: {about}", "",
             "## Evidence",
             f"Against the bare AI tool on the same input, on the runs made with this change: ahead on **{metric}** in "
             f"**{ahead} of {len(rows)}** cases.", "",
             "| case set | environment | cases | time | tokens | quality |", "|---|---|---|---|---|---|"]
    for s in sets:
        mine = [r for c, r in rows if c.get("set") == s["id"]]
        if not mine:
            continue

        def mean(key):
            vals = [r[key] for r in mine if r.get(key) is not None]
            return sum(vals) / len(vals) if vals else None
        q = mean("quality")
        lines.append(f"| {s['about'][:80]} | {s.get('env_name', '')} | {len(mine)} | {pct(mean('time'))} | "
                     f"{pct(mean('tokens'))} | {'—' if q is None else f'{q:+.1f}'} |")
    loose = [r for c, r in rows if not c.get("set")]
    if loose:
        lines.append(f"| single cases | | {len(loose)} | | | |")
    lines += ["", "Time and tokens: the building against the bare AI tool (−20% is 20% less). Quality: the building's "
              "score minus the bare tool's. The cases' inputs stay on the machine that ran them."]
    if data_changes:
        lines += ["", "## Settings tried with it", *[f"- {d}" for d in data_changes]]
    return "\n".join(lines)
