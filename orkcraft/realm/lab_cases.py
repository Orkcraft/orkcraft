"""🧪 The Test bench building's own work (docs/design/test-bench.md §10): a goal in words, the cases it makes of it, what
the last test of each said against the bare AI tool, and what to change in the buildings to reach the goal.

    state = lab_cases.load(state_dir)                   kept beside the building until it is demolished
    lab_cases.case_prompt(goal, about, entries)         an agent's ask for the first cases → parse_cases(text)
    lab_cases.to_case(c, subject)                       a case the bench runs (`chain` kind: a cart in, what comes out)
    lab_cases.judge_prompt(…) / parse_judge(text)       a blind judge: which result does the case better
    lab_cases.result_of(report)                         what the window shows of a run: time, tokens, quality, both sides
    lab_cases.propose_prompt(…) / parse_proposals(text) what to change in code, roads or prompts for the goal

No face and no model here: the calls are the caller's (gui/bench.py), the shapes and the words are here.
"""
from __future__ import annotations

import datetime as dt
import json
import uuid
from pathlib import Path

from orkcraft.realm import bench, bench_kits

FILE = "lab.json"
MAX_CASES = 40
AREAS = ("code", "roads", "prompt", "settings")
GOALS = {                            # what a goal is about, by its words: the metric the window leads with
    "tokens": ("token", "spend", "cost", "cheap", "expens", "money", "$", "токен", "расход", "дешев", "стоим"),
    "time": ("time", "fast", "slow", "latency", "speed", "quick", "быстр", "время", "скорост", "долг"),
}


def metric_of(goal: str) -> str:
    """tokens, time or quality: what the goal asks to improve (quality when it names neither of the others)."""
    low = (goal or "").lower()
    for metric, words in GOALS.items():
        if any(w in low for w in words):
            return metric
    return "quality"


# -- the state kept beside the building ------------------------------------------------------------------------

def blank() -> dict:
    return {"goal": "", "settings": {"tool": "main", "tier": "", "bare_tool": "main", "bare_tier": "",
                                     "max_spend": bench.DEFAULT_MAX_SPEND, "judge": True},
            "cases": {}, "results": {}, "proposals": {}, "runs": {}}


def load(state_dir: Path) -> dict:
    try:
        data = json.loads((state_dir / FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return blank()
    out = blank()
    if isinstance(data, dict):
        out.update({k: v for k, v in data.items() if k in out})
        out["settings"] = {**blank()["settings"], **(data.get("settings") or {})}
    return out


def save(state_dir: Path, state: dict) -> None:
    state_dir.mkdir(parents=True, exist_ok=True)
    path = state_dir / FILE
    tmp = path.with_name(f"{path.stem}.{uuid.uuid4().hex[:8]}.tmp")      # two saves at once never share one
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(path)


def new_case(title: str, text: str, entry: str = "", expect: list | None = None, why: str = "",
             source: str = "manual") -> dict:
    return {"id": f"c{uuid.uuid4().hex[:6]}", "title": " ".join(title.split())[:120] or "A case",
            "text": text.strip()[:6000], "entry": entry, "expect": [w for w in (expect or []) if w][:8],
            "why": why[:300], "source": source, "at": dt.datetime.now().isoformat(timespec="seconds")}


# -- making the first cases ------------------------------------------------------------------------------------------

def case_prompt(goal: str, about: str, entries: list[dict], have: list[str] = ()) -> str:
    where = "\n".join(f"- `{e['id']}`: {e['title']} ({e['word']}) — {e.get('takes', '')}" for e in entries)
    return f"""You plan the test cases of a Test bench. It gives each case's input to a building or a chain of buildings of an
AI agents' town ({about}), and the same input to a bare AI tool, then compares time, tokens and how well each did.

The goal of the testing, in the operator's words: {goal or 'see whether the buildings do better than the bare tool'}

Where an input may go in:
{where}

{('Cases it has already: ' + '; '.join(have)) if have else ''}
Write 5 to 8 cases that tell whether the goal is reached: everyday ones and hard ones, short and long, the kinds of
work the operator's goal is about. Each input is what a person would really send in, complete (a task, a message, a
question, a document), never a description of one. `expect` is 1–4 words or short phrases a good result must say
(a group of alternatives as a list), or [] when only judgement can tell.

Answer with JSON only:
{{"cases": [{{"title": "…", "entry": "<an id from the list>", "text": "…", "expect": ["…", ["…", "…"]], "why": "what it tells about the goal"}}]}}"""


def parse_cases(text: str, entries: list[dict]) -> list[dict]:
    data = bench_kits.answer_json(text)
    ids = [e["id"] for e in entries]
    out = []
    for c in data.get("cases") or []:
        if not isinstance(c, dict) or not str(c.get("text") or "").strip():
            continue
        entry = str(c.get("entry") or "")
        expect = [x if isinstance(x, (str, list)) else str(x) for x in (c.get("expect") or [])]
        out.append(new_case(str(c.get("title") or ""), str(c["text"]), entry if entry in ids else (ids[0] if ids else ""),
                            expect, str(c.get("why") or ""), "generated"))
    return out[:MAX_CASES]


def to_case(c: dict, about: str, judge: bool, goal: str = "") -> bench.Case:
    """A case of the building's as one the bench runs: a cart into its entry, what comes out checked by its words,
    and, when asked, by a blind judge."""
    return bench.Case(id=c["id"], type="chain", title=c["title"], task="", level="",
                      inputs={"cart": {"title": c["title"], "text": c["text"]}, "entry": c.get("entry") or "",
                              "expect_words": c.get("expect") or [], "about": about, "judge": bool(judge),
                              "goal": goal},
                      expect=c.get("why") or "")


# -- the blind judge ----------------------------------------------------------------------------------------------

def judge_prompt(goal: str, case: bench.Case, first: str, second: str) -> str:
    cart = case.inputs.get("cart") or {}
    return f"""Two results of the same request, A and B, by two different systems. Judge which does the request better: is
it right, complete, usable as it is. Length is not quality. The goal of this testing: {goal or 'quality'}.

<request title="{cart.get('title', '')}">
{cart.get('text', '')[:4000]}
</request>

<A>
{first[:6000] or '(nothing came out)'}
</A>

<B>
{second[:6000] or '(nothing came out)'}
</B>

Answer with JSON only: {{"a": <0-10>, "b": <0-10>, "why": "a sentence"}}"""


def parse_judge(text: str) -> dict:
    data = bench_kits.answer_json(text)
    try:
        return {"a": max(0.0, min(10.0, float(data.get("a")))), "b": max(0.0, min(10.0, float(data.get("b")))),
                "why": str(data.get("why") or "")[:300]}
    except (TypeError, ValueError):
        return {}


# -- what the window shows of a run --------------------------------------------------------------------------------

def _side(s: bench.Side | None) -> dict | None:
    if s is None:
        return None
    ok = [x for x in s.checks if x.get("ok")]
    return {"seconds": s.seconds, "tokens": s.tokens, "cost": s.cost, "error": s.error, "cut": s.cut,
            "passed": s.passed, "checks": f"{len(ok)}/{len(s.checks)}" if s.checks else "", "score": s.score,
            "model": s.model}


def _delta(mine, theirs) -> float | None:
    return round((mine - theirs) / theirs, 3) if mine is not None and theirs else None


def result_of(r: bench.Report) -> dict:
    """A run as one row: each side, and the building against the bare tool (a share: -0.2 is 20 % less)."""
    b, t = _side(r.building), _side(r.bare)
    out = {"run": r.id, "at": r.at, "scheme": b, "bare": t}
    if b and t:
        out["time"] = _delta(b["seconds"], t["seconds"])
        out["tokens"] = _delta(b["tokens"], t["tokens"])
        out["cost"] = _delta(b["cost"], t["cost"])
        if b["score"] is not None and t["score"] is not None:
            out["quality"] = round(b["score"] - t["score"], 1)
        else:
            sb = 1 if b["passed"] else (-1 if b["passed"] is False or b["error"] else 0)
            st = 1 if t["passed"] else (-1 if t["passed"] is False or t["error"] else 0)
            out["quality"] = float(sb - st)
    return out


def summary(results: dict, metric: str) -> dict:
    """Over the last test of every case: how many the scheme is ahead in, and the mean change of the metric."""
    rows = [r for r in results.values() if r.get("scheme") and r.get("bare")]
    if not rows:
        return {"cases": 0}
    key = {"tokens": "tokens", "time": "time"}.get(metric, "quality")
    values = [r[key] for r in rows if r.get(key) is not None]

    def ahead(r: dict) -> bool:
        v = r.get(key)
        return v is not None and (v > 0 if key == "quality" else v < 0)

    return {"cases": len(rows), "ahead": sum(ahead(r) for r in rows), "metric": key,
            "mean": round(sum(values) / len(values), 3) if values else None}


# -- what to change --------------------------------------------------------------------------------------------------

def propose_prompt(goal: str, about: str, files: list[str], roads: list[str], results: list[str]) -> str:
    return f"""You improve a scheme of an AI agents' town so it reaches its goal. The scheme: {about}.
Its roads: {'; '.join(roads) or 'none: one building'}.

The goal, in the operator's words: {goal or 'do better than the bare AI tool'}

The last tests, each case against the bare AI tool on the same input (time, tokens, quality; quality is the scheme's
score minus the bare tool's):
{chr(10).join(results) or 'no test yet'}

Read the buildings' code before you propose; the files that make them:
{chr(10).join('- ' + f for f in files)}

Propose 3 to 8 changes, the ones that move the goal most first. Each is one of: `code` (a change in a building's
source), `roads` (lay, drop or change a road, or put another building in the chain), `prompt` (a steward's or an
ork's instructions), `settings` (a building's setting: a tier, a limit, a tool). Say exactly what to change and why it
moves the goal, and what it costs.

Answer with JSON only:
{{"proposals": [{{"area": "code|roads|prompt|settings", "title": "a short imperative line", "detail": "what exactly and why", "where": "the file, the building or the road", "effect": "what it should do to the goal"}}]}}"""


def parse_proposals(text: str) -> list[dict]:
    out = []
    for p in bench_kits.answer_json(text).get("proposals") or []:
        if isinstance(p, dict) and str(p.get("title") or "").strip():
            area = str(p.get("area") or "").lower()
            out.append({"id": f"p{len(out)}", "area": area if area in AREAS else "code",
                        "title": str(p["title"]).strip()[:200], "detail": str(p.get("detail") or "")[:2000],
                        "where": str(p.get("where") or "")[:200], "effect": str(p.get("effect") or "")[:300]})
    return out[:8]


def result_line(c: dict, r: dict) -> str:
    def pct(v):
        return "—" if v is None else f"{v:+.0%}"
    q = r.get("quality")
    return (f"- {c['title']}: time {pct(r.get('time'))}, tokens {pct(r.get('tokens'))}, "
            f"quality {'—' if q is None else f'{q:+.1f}'}")

