"""🧭 The steward's plan: a task judged simple goes to one light ork, a hard one becomes a graph of
subtasks (design: docs/design/barracks-planning.md §3–4).

    clearly_simple(task)                   the rules decide when they are sure: a short task, no steps
    plan_prompt(...) / parse(text)         the steward answers `SIMPLE` or a JSON plan; the code checks it
    ready(children, limit)                 the subtasks that may start now: what they wait for is done,
                                           nothing running touches the same files, within the limit
    trim(subs, left, costs, tokens_left)   fit the plan into the $ budget and the quota left: lower tiers
                                           where allowed, never a part dropped
    final_prompt(...) / rework_of(...)     the steward's last look at the whole, against the request

The goal of the building (🪙 thrift · ⚖️ balance · 💎 quality) moves the defaults: `GOALS`.
The steward's answer is untrusted text: a plan is used only when it passes `check`.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from orkcraft.realm import tiers

MAX_SUBTASKS = 6
SHORT = 400                      # characters: a task this short, with no steps, is simple by the rules
STEP = re.compile(r"^\s*(?:[-*+]|\d+[.)]|#{1,6})\s+\S", re.M)
TICKETS = re.compile(r"\b([A-Z]{1,5}-?\d{2,6})\b")
SUB_ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,23}$")
SIMPLE = re.compile(r"^\s*\**\s*SIMPLE\b", re.I)
SUB_REWORK = re.compile(r"^\s*`?([a-z0-9][a-z0-9-]{0,23})`?\s*:\s*(.+)", re.S)
DEFAULT_COST = {"elder": 1.0, "warrior": 0.3, "laborer": 0.05}   # $ a run, before the barracks has a record
DEFAULT_TOKENS = {"elder": 80_000, "warrior": 60_000, "laborer": 30_000}   # tokens a run, likewise
QUOTA_SHARE = 0.5                # a plan may take at most this share of what is left of the quota
BRIEF_LIMIT = 4000               # characters of the whole request a subtask's ork reads


@dataclass(frozen=True)
class Goal:
    simple: str                  # the tier of a simple task
    shift: int                   # a subtask's tier against the plan's: -1 lighter, +1 heavier
    parallel: int                # subtasks at once at most (0: as many as the pool has orks)
    sub_review: bool             # a subtask is read by the steward after its tests (else the tests only)
    final: str                   # the tier of the steward's last look at the whole


GOALS = {
    "thrift": Goal("laborer", -1, 2, False, "warrior"),
    "balance": Goal("laborer", 0, 0, True, "elder"),
    "quality": Goal("warrior", 1, 0, True, "elder"),
}
PLAN_TIER = "elder"              # a wrong plan costs more than everything after it
REVIEW_TIER = "warrior"          # the steward's read of a simple task or a subtask


def goal_of(aim: str) -> Goal:
    return GOALS.get(aim, GOALS["balance"])


def shift(tier: str, by: int) -> str:
    """One tier lighter (-1) or heavier (+1), within the three."""
    i = tiers.TIERS.index(tier) if tier in tiers.TIERS else tiers.TIERS.index("warrior")
    return tiers.TIERS[max(0, min(len(tiers.TIERS) - 1, i - by))]       # TIERS runs heaviest first


def up(tier: str) -> str | None:
    """The next heavier tier (escalation after a failure), None from the elder."""
    heavier = shift(tier, 1)
    return heavier if heavier != tier else None


# -- the triage -------------------------------------------------------------------------------------

def clearly_simple(title: str, text: str) -> bool:
    """The rules are sure it is simple: short, no list of steps or sections, one ticket at most."""
    body = f"{title}\n{text}"
    return (len(text) <= SHORT and len(STEP.findall(text)) < 3
            and len(set(TICKETS.findall(body))) <= 1)


# -- the plan ---------------------------------------------------------------------------------------

@dataclass
class Sub:
    id: str
    title: str
    brief: str
    tier: str = "warrior"
    persona: str = ""
    persona_prompt: str = ""     # the steward's new persona: who does this part (§4.3)
    touches: list[str] = field(default_factory=list)
    after: list[str] = field(default_factory=list)
    cheaper_ok: bool = False


def plan_prompt(keeper: str, orders: str, title: str, text: str, aim: str, max_parallel: int,
                personas: list[tuple[str, str, str]]) -> str:
    """`personas`: (name, tier, its first line) of those the barracks keeps."""
    known = "\n".join(f"- `{n}` ({t}): {line}" for n, t, line in personas) or "(none yet)"
    rules = f"## Your rules\n\n{orders.strip()}" if orders.strip() else ""
    return "\n\n".join(p for p in [
        f"You are {keeper}, the steward of a barracks of coding agents. PLAN the task below before anyone works "
        "on it: you will review every part and the whole, so keep the operator's intent in mind.",
        rules, f"## The task: {title}", text,
        f"## The barracks\n\nIts goal: {aim}. At most {max_parallel} agents work at once. Tiers: `elder` (the "
        "heaviest model: design, tricky code), `warrior` (ordinary code), `laborer` (light, fast and cheap: "
        "mechanical edits, docs, renames).",
        f"## Personas it keeps\n\n{known}",
        "If one agent can do it in one go, answer `SIMPLE` on the first line and nothing else.",
        "Otherwise answer one JSON object and nothing else:\n\n"
        '{"subtasks": [{"id": "api", "title": "…", "brief": "what exactly to do and what done looks like", '
        '"tier": "warrior", "persona": "backend", "persona_prompt": "", "touches": ["src/api/"], '
        '"after": [], "cheaper_ok": false}]}\n\n'
        f"- at most {MAX_SUBTASKS} subtasks; `id`: lowercase letters, digits and dashes;\n"
        "- `touches`: the files or folders it changes — parts that touch the same ones never run at once;\n"
        "- `after`: the ids it needs done first (no cycles); it starts from their merged work;\n"
        "- `persona`: one of those above, or a new name with `persona_prompt` — a few lines on who this agent "
        "is and how it works;\n"
        "- `cheaper_ok`: true when a lighter tier would still do, should the budget be short."] if p)


def parse(text: str) -> tuple[list[Sub] | None, list[str]]:
    """(subtasks, errors) from the steward's answer; (None, []) when it says SIMPLE."""
    text = (text or "").strip()
    if SIMPLE.match(text):
        return None, []
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        return [], ["the answer is neither SIMPLE nor a JSON plan"]
    try:
        data = json.loads(text[start:end + 1])
    except ValueError as e:
        return [], [f"the plan is not JSON: {e}"]
    raw = data.get("subtasks") if isinstance(data, dict) else None
    if not isinstance(raw, list) or not raw:
        return [], ["the plan has no `subtasks`"]
    subs: list[Sub] = []
    for item in raw:
        if not isinstance(item, dict):
            return [], ["a subtask is not an object"]
        subs.append(Sub(
            id=str(item.get("id") or "").strip(), title=str(item.get("title") or "").strip()[:80],
            brief=str(item.get("brief") or "").strip(), tier=str(item.get("tier") or "warrior").strip().lower(),
            persona=_name(item.get("persona")), persona_prompt=str(item.get("persona_prompt") or "").strip()[:2000],
            touches=[str(x).strip() for x in item.get("touches") or [] if str(x).strip()][:20],
            after=[str(x).strip() for x in item.get("after") or [] if str(x).strip()],
            cheaper_ok=item.get("cheaper_ok") is True))
    return subs, check(subs)


def _name(value: object) -> str:
    return re.sub(r"[^a-z0-9-]+", "-", str(value or "").lower()).strip("-")[:30]


def check(subs: list[Sub]) -> list[str]:
    """What is wrong with a plan: ids, titles, tiers, the graph."""
    errors: list[str] = []
    if len(subs) > MAX_SUBTASKS:
        errors.append(f"{len(subs)} subtasks: at most {MAX_SUBTASKS}")
    ids = [s.id for s in subs]
    for s in subs:
        if not SUB_ID.match(s.id):
            errors.append(f"`{s.id}`: an id is lowercase letters, digits and dashes")
        if not s.title or not s.brief:
            errors.append(f"`{s.id}`: a title and a brief are needed")
        if s.tier not in tiers.TIERS:
            errors.append(f"`{s.id}`: the tier is elder, warrior or laborer")
        for a in s.after:
            if a not in ids:
                errors.append(f"`{s.id}` is after `{a}`, which is not in the plan")
    if len(set(ids)) != len(ids):
        errors.append("two subtasks share an id")
    if not errors and _cycle(subs):
        errors.append("`after` makes a cycle")
    return errors


def _cycle(subs: list[Sub]) -> bool:
    after = {s.id: set(s.after) for s in subs}
    done: set[str] = set()
    while True:
        free = {i for i, deps in after.items() if i not in done and deps <= done}
        if not free:
            return len(done) < len(after)
        done |= free


def overlap(a: list[str], b: list[str]) -> bool:
    """Two parts touch the same files: a path of one is the other's, or inside it."""
    def norm(p: str) -> str:
        return p.strip().lstrip("./").rstrip("/")
    return any(x == y or x.startswith(y + "/") or y.startswith(x + "/") or not x or not y
               for x in map(norm, a) for y in map(norm, b))


def ready(children: list, limit: int) -> list:
    """The `blocked` children that may start now, in the plan's order: every `after` is done, nothing
    queued or running touches the same files, and no more than `limit` at once (0: no limit)."""
    by_sub = {c.sub: c for c in children}
    active = [c for c in children if c.status in ("queued", "working", "reviewing", "asked")]
    out = []
    for c in children:
        if c.status != "blocked":
            continue
        if limit and len(active) >= limit:
            break
        if any(by_sub.get(a) is None or by_sub[a].status != "done" for a in c.after):
            continue
        if any(c.touches and o.touches and overlap(c.touches, o.touches) for o in active):
            continue
        out.append(c)
        active.append(c)
    return out


# -- the budget ------------------------------------------------------------------------------------

def tier_costs(stats: dict) -> dict[str, float]:
    """$ a run per tier, from the barracks' own record (stats.json, by harness:model), else a guess."""
    runs: dict[str, list[float]] = {}
    for key, st in (stats or {}).items():
        harness, _, model = key.partition(":")
        tier = tiers.step_tier({"harness": harness, "model": model})
        if tier and st.get("runs"):
            runs.setdefault(tier, []).append(float(st.get("cost", 0.0)) / int(st["runs"]))
    return {t: (sum(runs[t]) / len(runs[t]) if runs.get(t) else DEFAULT_COST[t]) for t in tiers.TIERS}


def tier_tokens(stats: dict) -> dict[str, int]:
    """Tokens a run per tier, from the barracks' own record, else a guess."""
    runs: dict[str, list[float]] = {}
    for key, st in (stats or {}).items():
        harness, _, model = key.partition(":")
        tier = tiers.step_tier({"harness": harness, "model": model})
        if tier and st.get("runs") and st.get("tokens"):
            runs.setdefault(tier, []).append(int(st["tokens"]) / int(st["runs"]))
    return {t: int(sum(runs[t]) / len(runs[t])) if runs.get(t) else DEFAULT_TOKENS[t] for t in tiers.TIERS}


def cost(subs: list[Sub], costs: dict[str, float]) -> float:
    return sum(costs.get(s.tier, DEFAULT_COST["warrior"]) for s in subs)


def tokens(subs: list[Sub], per: dict[str, int]) -> int:
    return sum(per.get(s.tier, DEFAULT_TOKENS["warrior"]) for s in subs)


def trim(subs: list[Sub], left: float | None, costs: dict[str, float], tokens_left: float | None = None,
         per: dict[str, int] | None = None) -> tuple[bool, list[str]]:
    """Fit the plan into what is left of the budget in $ (None: no budget) and of the quota in tokens
    (None: no quota known), never by dropping a part: lower tiers where the steward allowed it
    (`cheaper_ok`), the dearest first. (fits, what was lowered)."""
    notes: list[str] = []
    per = per or DEFAULT_TOKENS

    def over() -> bool:
        return (left is not None and cost(subs, costs) > left) or \
            (tokens_left is not None and tokens(subs, per) > tokens_left)

    while over():
        can = [s for s in subs if s.cheaper_ok and shift(s.tier, -1) != s.tier]
        if not can:
            return False, notes
        s = max(can, key=lambda x: costs.get(x.tier, 0.0))
        lower = shift(s.tier, -1)
        notes.append(f"{s.id}: {s.tier} → {lower}")
        s.tier = lower
    return True, notes


# -- the whole ------------------------------------------------------------------------------------

def child_text(parent_title: str, parent_text: str, sub: Sub, others: list[Sub]) -> str:
    """What a subtask's ork reads: its part, and the whole for context."""
    whole = parent_text if len(parent_text) <= BRIEF_LIMIT else parent_text[:BRIEF_LIMIT] + "\n… (cut)"
    rest = "\n".join(f"- `{o.id}` {o.title}" for o in others if o.id != sub.id)
    return "\n\n".join(p for p in [
        sub.brief,
        f"## The whole task (others do the other parts — do only yours): {parent_title}\n\n{whole}",
        f"## The other parts\n\n{rest}" if rest else ""] if p)


def final_prompt(keeper: str, orders: str, title: str, text: str, plan: list[dict], reports: list[tuple[str, str]],
                 diff: str, tests: str, limit: int) -> str:
    """The steward's last look: the merged work against the operator's request, word for word."""
    cut = diff if len(diff) <= limit else diff[:limit] + "\n… (cut)"
    steps = "\n".join(f"- `{p.get('id')}` {p.get('title')} ({p.get('tier')})" for p in plan)
    parts = "\n\n".join(f"### `{sub}`\n\n{rep.strip()[:2000] or '(no report)'}" for sub, rep in reports)
    return "\n\n".join(p for p in [
        f"You are {keeper}, the steward of a barracks of coding agents. You planned the task below and every "
        "part was done and accepted; now judge the WHOLE against what the operator asked for.",
        f"## Your rules\n\n{orders.strip()}" if orders.strip() else "",
        f"## The operator's request: {title}", text, f"## Your plan\n\n{steps}", f"## The parts' reports\n\n{parts}",
        f"## Tests\n\n{tests}" if tests else "",
        f"## The merged diff\n\n```diff\n{cut}\n```" if diff.strip() else "## The merged diff\n\n(empty)",
        "Answer `ACCEPT` on the first line when the request is met. Otherwise `REWORK: <id>: what to fix` — the "
        "part that has to change — or `REWORK: new: what is missing` for something no part covered."] if p)


def rework_of(notes: str, ids: list[str]) -> tuple[str, str]:
    """(the part to send back or "", the notes) from `REWORK: <id>: …`."""
    m = SUB_REWORK.match(notes or "")
    if m and m.group(1) in ids:
        return m.group(1), m.group(2).strip()
    if m and m.group(1) == "new":
        return "", m.group(2).strip()
    return "", (notes or "").strip()
