"""🔧 The Building retro (local optimisation): a proposal for the hungriest building the operator
is not happy with — never applied on its own (operator decision 2026-10-02).

    the leader   the building that eats most of the camp and of the limit (realm/pressure.py: its share
                 of the last 24 h, or the pressure on the binding quota when one is read), if since its
                 last change (its last checkpoint) it got no 👍, or today it got at least one 👎; a
                 liked one passes the turn to the next (below MIN_SHARE of the camp nobody is picked)
    its parts    what calls a model there: agent handlers' orders, a Workshop's steward prompt (with
                 its script), a Barracks' standing orders
    the Council  one model call: ONE change that spends fewer tokens and keeps what was liked —
                   shrink   a shorter prompt for one part (at most 70 % of its length)
                   chain    an agent handler becomes chain ops (data, no model)
                   script   a Workshop's script handles every cart itself; its steward prompt goes
    the check    shrink is shorter; a chain passes `orc_problems`; a script parses, passes the
                 Council's rules and every mock cart of the blueprint in the sandbox

A proposal waits in `.orkcraft/optimize/proposals.jsonl` until the operator applies it (one click:
the change, a checkpoint `auto-improve(<id>)`, and Z takes it back) or dismisses it.
"""
from __future__ import annotations

import datetime as dt
import json
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path

from orkcraft.realm import builders, feedback, metrics, pressure

DIR = Path(".orkcraft") / "optimize"
SHRINK = 0.7
MIN_SHARE = 0.1          # of the camp's tokens in 24 h: below it a building is not worth a retro
ACTIONS = ("shrink", "chain", "script")

PROMPT = """You are the Council of orkcraft, a terminal harness where buildings pass events along roads to
scripts, chains and agents. Optimise ONE building: in the last 24 h it spent {tokens} tokens (${cost:.2f}) —
{use} — and {reason}.

ITS MODEL-DRIVEN PARTS:
{parts}

RESULTS THE OPERATOR LIKED (keep these working):
{references}

ITS RECENT RUNS (its logs):
{runs}

WHAT THE OPERATOR DISLIKED:
{incidents}

Pick ONE change that spends fewer tokens without losing what the operator liked:
- "shrink": a shorter prompt for one part — same intent, at most 70% of its length
- "chain": only for an agent handler (orc:…) whose job needs no judgement — chain ops, a list of
  {{"op":"filter","field":f,"cmp":"eq|ne|in|contains|matches","value":v}} {{"op":"pick","fields":[..]}}
  {{"op":"extract","field":f,"regex":r,"as":f2}} {{"op":"sort","by":f,"desc":bool}} {{"op":"limit","n":N}}
  {{"op":"count","as":f}} {{"op":"group","by":f}} {{"op":"template","md":"text with {{field}}"}} {{"op":"join","sep":s}}
  over records with fields road, source, event, kind, value, title, id, path, text, type, status, outcome
- "script": only for the steward — a new python script (stdin: the cart as JSON; stdout: the result;
  exit 0 done, 4 alert, never 3) that handles every cart itself, so the steward prompt can go
Answer with ONE JSON object and nothing else:
{{"action": "shrink|chain|script", "target": "<part id>", "prompt": "<for shrink>", "chain": [..],
  "script": "<for script>", "why": "<one sentence>", "saving": "<what it saves, roughly>"}}"""


@dataclass
class Candidate:
    building: str
    tokens: int
    cost: float
    likes: int             # 👍 since its last change
    dislikes: int          # 👎 today
    share: float = 0.0     # of the camp's tokens in 24 h
    use: str = ""          # its share and pressure in words (pressure.describe)

    @property
    def reason(self) -> str:
        if self.dislikes:
            return f"the operator disliked it {self.dislikes}× today"
        return "the operator has not liked it since its last change"


@dataclass
class Part:
    id: str              # orc:<id> | steward | orders
    kind: str            # agent | steward | orders
    text: str
    script: str = ""     # the steward's script, for context


@dataclass
class Proposal:
    id: str
    ts: str
    building: str
    action: str
    target: str
    before: str
    after: str           # the new prompt, the chain as JSON, or the new script
    why: str = ""
    saving: str = ""
    tokens: int = 0
    status: str = "pending"      # pending | applied | dismissed
    commit: str = ""
    cost_usd: float | None = None


@dataclass
class Result:
    proposal: Proposal | None = None
    error: str = ""
    problems: list[str] = field(default_factory=list)


# -- the leader -------------------------------------------------------------------------------------

def leader(repo_root: Path, now: dt.datetime | None = None, limits=None, providers=None) -> Candidate | None:
    """The building that eats most of the camp and of the limit, when the operator disliked it today or
    has not liked it since its last change; a liked one passes the turn to the next. None when nobody
    with at least MIN_SHARE of the camp's tokens is left."""
    now = now or dt.datetime.now()
    camp = pressure.measure(repo_root, limits, now, providers)
    if not camp.tokens:
        return None
    since = now.replace(hour=0, minute=0, second=0, microsecond=0)
    costs: dict[str, float] = {}
    for row in metrics._read(repo_root / metrics.LEDGER, now - pressure.WINDOW):
        if row["_at"] > now - pressure.WINDOW:
            costs[str(row.get("building") or "")] = costs.get(str(row.get("building") or ""), 0.0) + float(row.get("cost") or 0.0)
    from orkcraft.realm import checkpoint
    incidents = feedback.incidents(repo_root, 1000)
    for bid in sorted(camp.buildings, key=lambda b: (camp.buildings[b].weight, camp.buildings[b].tokens), reverse=True):
        use = camp.buildings[bid]
        if use.share < MIN_SHARE:
            break
        mine = checkpoint.history(repo_root, bid, limit=1)
        changed = mine[0].at[:19] if mine else ""
        likes = sum(1 for r in feedback.references(repo_root, bid, 1000) if str(r.get("ts", "")) > changed)
        dislikes = sum(1 for i in incidents if i.building == bid and i.ts >= since.isoformat(timespec="seconds"))
        if likes and not dislikes:
            continue
        return Candidate(bid, use.tokens, round(costs.get(bid, 0.0), 4), likes, dislikes, round(use.share, 4),
                         pressure.describe(use, camp))
    return None


def run_logs(repo_root: Path, building: str, limit: int = 5) -> list[str]:
    """The building's recent runs: what came in and what came out — Workshop and
    Mill runs, agent handlers' examples — for the Council to read."""
    root = repo_root / ".orkcraft"
    out: list[str] = []
    files = [p for p in root.glob(f"*/{building}/runs.jsonl")] + list((root / "history" / "handlers" / building).glob("*.jsonl"))
    for path in files:
        try:
            lines = path.read_text(encoding="utf-8").splitlines()[-limit:]
        except OSError:
            continue
        for line in reversed(lines):
            try:
                r = json.loads(line)
            except ValueError:
                continue
            got = r.get("input") or json.dumps(r.get("inputs") or "", ensure_ascii=False)
            gave = r.get("out") or r.get("result") or r.get("output") or r.get("error") or r.get("err") or ""
            out.append(f"- in: {str(got)[:240]} → out: {str(gave)[:240]}")
    return out[:limit * 2]


def parts(scroll, spec: dict | None, building: str, repo_root: Path | None = None) -> list[Part]:
    out = []
    b = scroll.building(building) if scroll is not None else None
    if b is not None:
        for orc in b.garrison.handlers:
            if orc.kind in ("agent", "hybrid") and orc.orders.strip():
                out.append(Part(f"orc:{orc.id}", "agent", orc.orders))
    cfg = (spec or {}).get("config") or {}
    if cfg.get("steward_prompt"):
        from orkcraft.realm import workshop
        script = workshop.load_script(repo_root, building, str(cfg.get("runtime") or "python")) if repo_root else ""
        out.append(Part("steward", "steward", str(cfg["steward_prompt"]), script))
    if cfg.get("orders"):
        out.append(Part("orders", "orders", str(cfg["orders"])))
    return out


# -- the proposal -----------------------------------------------------------------------------------

def _parts_text(ps: list[Part]) -> str:
    lines = []
    for p in ps:
        what = {"agent": "an agent handler's orders", "steward": "the Workshop's steward prompt (exit 3 carts)",
                "orders": "the Barracks' standing orders"}[p.kind]
        lines.append(f"[{p.id}] {what}:\n{p.text[:3000]}")
        if p.script:
            lines.append(f"  its script:\n{p.script[:4000]}")
    return "\n\n".join(lines)


def check(data: dict, ps: list[Part], building: str, repo_root: Path, runtime: str = "python",
          mocks: list[dict] | None = None) -> tuple[str, list[str]]:
    """(the change as text, problems)."""
    action, target = data.get("action"), str(data.get("target") or "")
    part = next((p for p in ps if p.id == target), None)
    if action not in ACTIONS:
        return "", [f"action: one of {', '.join(ACTIONS)}"]
    if part is None:
        return "", [f"target: one of {', '.join(p.id for p in ps)}"]
    if action == "shrink":
        new = str(data.get("prompt") or "").strip()
        if not new:
            return "", ["prompt: the shorter prompt"]
        if len(new) > SHRINK * len(part.text):
            return "", [f"prompt: {len(new)} chars — at most {int(SHRINK * len(part.text))} (70 %)"]
        return new, []
    if action == "chain":
        if part.kind != "agent":
            return "", ["chain: only an agent handler (orc:…) can become a chain"]
        from orkcraft import scroll as ts
        ops = data.get("chain")
        orc = {"id": target[4:], "name": target[4:], "kind": "chain", "chain": ops if isinstance(ops, list) else []}
        problems = ts.orc_problems(orc)
        return (json.dumps(ops, ensure_ascii=False), problems) if not problems else ("", problems)
    # script: the steward goes, the script does it all
    if part.kind != "steward":
        return "", ["script: only for the steward"]
    from orkcraft.realm import fastpath, workshop
    source = str(data.get("script") or "")
    if (why := workshop.check_syntax(source, runtime)):
        return "", [f"script: {why}"]
    subject = fastpath.Subject("building", building, {"id": building, "type": "workshop", "config": {}}, source)
    blocks = [n.text for n in fastpath.rules(subject, repo_root) if n.severity == "block" and n.role == "warder"]
    if blocks:
        return "", [f"script: {b}" for b in blocks]
    runs = workshop.sandbox(source, runtime, mocks or [])
    bad = [f"mock cart {i}: exit {r.code} {r.err[:80]}" for i, r in enumerate(runs, 1)
           if r.outcome not in ("done", "alert")]
    return (source, []) if not bad else ("", [f"script: {b}" for b in bad])


def propose(repo_root: Path, cand: Candidate, ps: list[Part], runner: builders.Runner = builders.claude_runner,
            runtime: str = "python", mocks: list[dict] | None = None, attempts: int = 2) -> Result:
    """One Council call (a second with its problems). Never raises."""
    refs = feedback.references(repo_root, cand.building, 3)
    incs = [i for i in feedback.incidents(repo_root, 20) if i.building == cand.building][:3]
    base = PROMPT.format(tokens=cand.tokens, cost=cand.cost, use=cand.use or "the most of the camp",
                         reason=cand.reason, parts=_parts_text(ps),
                         runs="\n".join(run_logs(repo_root, cand.building)) or "- none kept",
                         references="\n".join(f"- {r.get('value', '')[:400]}" for r in refs) or "- none yet",
                         incidents="\n".join(f"- {i.kind}: {i.note or '(no note)'} · output: {i.output[:200]}"
                                             for i in incs) or "- none")
    result, total, problems = Result(), None, []
    for _ in range(attempts):
        prompt = base + ("\n\nYOUR LAST ANSWER WAS REJECTED:\n" + "\n".join(f"- {p}" for p in problems) if problems else "")
        try:
            text, cost = runner(prompt)
        except Exception as e:  # the CLI missing, a timeout
            result.error = str(e)[:300]
            return result
        if cost is not None:
            total = (total or 0.0) + cost
        data = builders.extract_json(text)
        if data is None:
            problems = ["answer with ONE JSON object"]
            continue
        after, problems = check(data, ps, cand.building, repo_root, runtime, mocks)
        if not problems:
            part = next(p for p in ps if p.id == data["target"])
            result.proposal = Proposal(uuid.uuid4().hex[:8], dt.datetime.now().isoformat(timespec="seconds"),
                                       cand.building, data["action"], part.id, part.text, after,
                                       str(data.get("why") or "")[:300], str(data.get("saving") or "")[:200],
                                       cand.tokens, cost_usd=total)
            return result
    result.problems = problems
    return result


# -- the queue --------------------------------------------------------------------------------------

def _path(repo_root: Path) -> Path:
    return repo_root / DIR / "proposals.jsonl"


def proposals(repo_root: Path) -> list[Proposal]:
    """Every proposal, the latest state of each, newest first."""
    try:
        lines = _path(repo_root).read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    latest: dict[str, Proposal] = {}
    for line in lines:
        try:
            p = Proposal(**json.loads(line))
        except (ValueError, TypeError):
            continue
        latest.pop(p.id, None)
        latest[p.id] = p
    return list(reversed(latest.values()))


def pending(repo_root: Path) -> list[Proposal]:
    return [p for p in proposals(repo_root) if p.status == "pending"]


def save(repo_root: Path, p: Proposal) -> None:
    path = _path(repo_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(asdict(p), ensure_ascii=False) + "\n")


def last_run(repo_root: Path) -> dt.datetime | None:
    try:
        return dt.datetime.fromisoformat(json.loads((repo_root / DIR / "last.json").read_text(encoding="utf-8"))["at"])
    except (OSError, ValueError, KeyError, TypeError):
        return None


def mark_run(repo_root: Path, now: dt.datetime | None = None) -> None:
    path = repo_root / DIR / "last.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"at": (now or dt.datetime.now()).isoformat(timespec="seconds")}), encoding="utf-8")
