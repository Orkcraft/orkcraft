"""💬 What the Test bench's runs mean, in words a person reads (docs/design/test-bench.md §10.3): for each case, how the
building did against the AI tool alone in one sentence, where its extra time and tokens went (read from its model
calls, realm/call_log.py), and what to change about it and why. No face and no model: the words are made from the
numbers, so they say only what the runs show.

    explain.story(title, reports, calls)     {"status": good | watch | bad, "summary", "details": […], "changes": […]}
    explain.changes(stories)                 the changes of every case, the same ones together, the worst first

`reports` are one case's runs (its repeats); `calls` maps a run's id to its model calls (`bench.calls_of`).
"""
from __future__ import annotations

import statistics

from orkcraft.realm import bench

SAME = 0.10                      # within this share of the AI tool alone it costs "about the same"
OUTSIDE = 0.25                   # time outside the AI tool beyond this share of the building's is worth a word
LONG_PROMPT = 1.5                # a prompt this many times the AI tool's is worth a word
STEPS = {"work": "the work itself", "sort": "sorting what came in", "plan": "planning it in parts",
         "review": "reviewing the result", "check": "running its checks", "answer": "answering an ork's question",
         "look": "looking at a service", "ingest": "taking in sources", "retro": "a retro", "build": "building",
         "chat": "a chat"}


def _median(values: list[float]) -> float:
    return statistics.median(values) if values else 0.0


def _share(v: float) -> str:
    return f"{abs(v):.0%}"


def _passed(s: bench.Side) -> bool:
    return bool(s.passed) and not s.error


def _calls(lines: list[dict], side: str) -> list[dict]:
    return [x for x in lines if (x.get("side") or "") == side]


def story(title: str, reports: list[bench.Report], calls: dict[str, list[dict]] | None = None) -> dict:
    """One case in words: a sentence, what lies under it, and what to change."""
    pairs = [r for r in reports if r.building is not None and r.bare is not None]
    calls = calls or {}
    if not pairs:
        err = next((r.building.error for r in reports if r.building is not None and r.building.error), "")
        return {"case": title, "status": "bad", "summary": f"It did not run{': ' + err if err else ''}.",
                "details": [], "changes": [{"what": "Make the run finish first", "why": err or "No run came back.",
                                            "case": title, "weight": 3}]}
    n = len(pairs)
    mine, theirs = sum(_passed(r.building) for r in pairs), sum(_passed(r.bare) for r in pairs)
    g = bench.pooled_gaps(pairs)
    details: list[str] = []
    changes: list[dict] = []

    # how good: its check against the AI tool's
    runs = "" if n == 1 else f" ({mine} of {n} runs, the AI tool {theirs} of {n})"
    if mine < theirs:
        status, quality = "bad", f"It does worse than the AI tool alone{runs}"
    elif mine > theirs:
        status, quality = "good", f"It does better than the AI tool alone{runs}"
    elif mine == n:
        status, quality = "good", "It does as well as the AI tool alone"
    elif mine == 0:
        status, quality = "bad", "Neither it nor the AI tool alone gets it right"
    else:
        status, quality = "watch", f"It gets it right only sometimes, as the AI tool alone does{runs}"
    missed = sorted({x["name"] for r in pairs for x in r.building.checks if not x.get("ok")})
    failed_tail = next((r.building.check_tail for r in pairs if r.building.passed is False and r.building.check_tail), "")
    if missed:
        details.append("It missed: " + "; ".join(missed[:4]) + ("…" if len(missed) > 4 else "") + ".")
    errors = sorted({r.building.error for r in pairs if r.building.error})
    if errors:
        details.append("It did not finish: " + errors[0][:200])
    if mine < theirs or (mine < n and mine == theirs == 0):
        changes.append({"what": "Make it get the result right first",
                        "why": f"{quality.rstrip('.')}." + (f" It missed {missed[0]}." if missed else
                                                          f" Its check said: {failed_tail[-160:]}" if failed_tail else
                                                          " Compare its answer with the AI tool's in the run."),
                        "case": title, "weight": 3})
    elif 0 < mine < n:
        changes.append({"what": "Make it steady", "why": f"It passed {mine} of {n} runs: the failed one shows what "
                                                         "it gets wrong now and then.", "case": title, "weight": 2})

    # how costly: time and tokens against the AI tool's
    cost = []
    if g["time"] is not None:
        cost.append("about as fast" if abs(g["time"]) <= SAME else
                    f"{_share(g['time'])} {'slower' if g['time'] > 0 else 'faster'}")
    if g["spend"] is not None:
        what = "tokens" if g["spend_by"] == "tokens" else "money"
        cost.append(f"about the same {what}" if abs(g["spend"]) <= SAME else
                    f"{_share(g['spend'])} {'more' if g['spend'] > 0 else 'fewer' if what == 'tokens' else 'less'} {what}")
    if status == "good" and ((g["time"] or 0) > 0.5 or (g["spend"] or 0) > 0.3):
        status = "watch"
    summary = quality + (", " + " and ".join(cost) if cost else "") + "."

    # where it went: the building's calls against the AI tool's
    mine_calls = [_calls(calls.get(r.id, []), "building") for r in pairs]
    bare_calls = [_calls(calls.get(r.id, []), "bare") for r in pairs]
    if any(mine_calls):
        b_secs = _median([r.building.seconds for r in pairs])
        in_tool = _median([sum(float(x.get("seconds") or 0) for x in c) for c in mine_calls])
        n_calls = _median([len(c) for c in mine_calls])
        bare_n = _median([len(c) for c in bare_calls]) or 1
        steps: dict[str, list[float]] = {}
        for c in mine_calls:
            for x in c:
                steps.setdefault(x.get("purpose") or "work", []).append(float(x.get("seconds") or 0))
        if n_calls > bare_n:
            extra = [f"{STEPS.get(p, p)} ({len(v) // n} call{'s' if len(v) // n != 1 else ''}, ~{sum(v) / n:.0f} s)"
                     for p, v in steps.items() if p != "work"] or [f"{n_calls:.0f} calls of its work"]
            details.append(f"It asks the AI tool {n_calls:.0f} times where the AI tool alone answers in "
                           f"{bare_n:.0f}: " + ", ".join(extra) + ".")
            if mine <= theirs and (g["time"] or 0) > SAME:
                step, secs = max(((p, sum(v) / n) for p, v in steps.items() if p != "work"), key=lambda t: t[1],
                                 default=("", 0.0))
                if step:
                    changes.append({"what": f"Skip {STEPS.get(step, step)} on tasks like this one",
                                    "why": f"It spends ~{secs:.0f} s of {b_secs:.0f} s on it, and the result is no "
                                           "better than the AI tool's without it.", "case": title, "weight": 2})
        bare_in = _median([sum(float(x.get("seconds") or 0) for x in c) for c in bare_calls])
        if bare_in and in_tool > bare_in * (1 + SAME):
            details.append(f"The AI tool works {in_tool:.0f} s for it against {bare_in:.0f} s alone.")
        outside = b_secs - in_tool
        if b_secs and outside / b_secs > OUTSIDE:
            details.append(f"{outside:.0f} s of its {b_secs:.0f} s go outside the AI tool: opening its town, "
                           "handing the task on, waiting between looks.")
            changes.append({"what": "Cut the waiting around the AI tool",
                            "why": f"{_share(outside / b_secs)} of its time ({outside:.0f} s) is not the AI tool "
                                   "working: starting up, handing on, polling.", "case": title, "weight": 1})
        b_prompt = _median([sum(int(x.get("prompt_chars") or 0) for x in c) for c in mine_calls])
        t_prompt = _median([sum(int(x.get("prompt_chars") or 0) for x in c) for c in bare_calls])
        if t_prompt and b_prompt / t_prompt >= LONG_PROMPT:
            details.append(f"What it sends the AI tool is {b_prompt / t_prompt:.1f}× as long as the task alone.")
            more = []
            if (g["spend"] or 0) > SAME:
                more.append(f"spends {_share(g['spend'])} more {'tokens' if g['spend_by'] == 'tokens' else 'money'}")
            if (g["time"] or 0) > SAME:
                more.append(f"takes {_share(g['time'])} longer")
            if more:
                changes.append({"what": "Shorten what it sends the AI tool",
                                "why": f"Its prompts are {b_prompt / t_prompt:.1f}× as long as the task, and it "
                                       f"{' and '.join(more)} than the AI tool alone.", "case": title, "weight": 2})
    return {"case": title, "status": status, "summary": summary, "details": details, "changes": changes}


def changes(stories: list[dict], extra: list[dict] | None = None) -> list[dict]:
    """Every story's changes, the same one once with the cases it is for, the weightiest and most common first.
    `extra`: the reviewers' advice ({what, why, who}), after what the runs measured."""
    seen: dict[str, dict] = {}
    for s in stories:
        for c in s["changes"]:
            got = seen.setdefault(c["what"], {"what": c["what"], "why": c["why"], "cases": [], "weight": c["weight"],
                                              "from": "measured"})
            got["cases"].append(c["case"])
            got["weight"] = max(got["weight"], c["weight"])
    out = sorted(seen.values(), key=lambda c: (-c["weight"], -len(c["cases"])))
    return out + [{"what": e["what"], "why": e["why"], "cases": [], "weight": 0, "from": e.get("who") or "a reviewer"}
                  for e in extra or []]
