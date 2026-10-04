"""The Town Builder: the operator's words become a plan of a whole town.

    plan = town_builder.plan(order, repo_root, taken_ids, runner)     # never raises
    plan.ok → plan.specs (typed building specs, checked) and plan.roads (source, event, target)

One `claude -p` call per attempt, in an empty folder, like the Foreman: the planner sees the order
and the building catalog, never the project. Its answer is untrusted: buildings come only from the
catalog's types (a spec, data — never code) and pass `masonry.validate_spec`; roads are plain (no
orc handles them, nothing runs a model) and may only wait for an event their source sends. A plan
that fails goes back with the problems, up to `MAX_ATTEMPTS` times. Nothing is raised here: the
operator approves the plan first (screens/town_plan.py).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from orkcraft.realm import builders, catalog, masonry

MAX_ATTEMPTS = 3
MAX_BUILDINGS = 8
MAX_ROADS = 12
ORDER_LIMIT = 4000
KEY = re.compile(r"^[a-z][a-z0-9_]{1,31}$")
SPEC_KEYS = ("title", "icon", "summary", "size", "events", "quick_actions", "config", "roof")

PLANNER = """You are the Town Builder of orkcraft, a terminal harness where every window is a typed
"building" on a town map, and roads carry events ("carts") from one building to another. The operator
described the town they need. Plan it from the building catalog below.

WHAT THE OPERATOR WANTS:
{order}

BUILDING TYPES (choose only from these; every event, quick action and config key must be the type's own):
{catalog}

Plan 2-{max_buildings} buildings — the fewest that do the job; the Town Hall already stands, never plan it.
For each: a "key" (snake_case, unique in the plan), its "type", a plain functional title (no fantasy),
one emoji icon, a one-sentence "why" (what it does for this operator), and — only when the request
says — size (XS S M L), the events it sends, up to two quick actions and the type's config (never
invent passwords or tokens; config only names environment variables that hold them).
Then 0-{max_roads} roads: each carries one event a source building sends to a target building that
should receive it ("from" and "to" are keys of the plan, "event" one of the source type's events or
on_selection_change), with a one-sentence "why".
{template}{feedback}
Answer with ONE JSON object and nothing else:
{{"title": "<the town's name, plain>", "summary": "<one sentence>",
  "buildings": [{{"key": "...", "type": "...", "title": "...", "icon": "...", "why": "...",
                 "size": "S", "events": ["..."], "quick_actions": ["..."], "config": {{}}}}],
  "roads": [{{"from": "<key>", "event": "...", "to": "<key>", "why": "..."}}]}}"""


ADAPT = """
START FROM A TEMPLATE. These are ready towns for the operator's role, in the answer's own shape. Pick
the one closest to what they said and adapt it — do not start from nothing:
{templates}
Adapt it to the operator's answers above:
- every data source they named needs a way in. EVERY WEBHOOK COMES IN THROUGH A WATCHTOWER — no
  other building listens for webhooks: a tool that pushes events (Jira, Linear, Asana, the stores,
  monitoring, support desks…) is a Watchtower with its webhook, and so are mail, GitHub and
  schedules; a Pit only for files and links they paste by hand; a Scroll Dump for documents
  exported to a folder; a File Forest for a folder of files;
- every place their results go needs a way out: a Catapult to that tool's API (config may name the
  environment variable with its token in token_env), a Loot Vault for files they accept first;
- every problem they named is answered by a building or a road — say which in its "why";
- what went wrong with AI before is avoided: keep a person's accept step (Loot Vault) where they
  distrust the output, prefer rules (Totem, Mill) over agents where results must not vary;
- match their experience: new to orkestration → fewer buildings and an accept step before anything
  leaves;
- their AI tools: work a tool is liked for (👍 docs, code…) may go to agents in the town; work a tool
  is weak at (👎 tickets…) gets a person's accept step or a rule (Totem, Mill) instead of an agent —
  say so in the "why";
- drop the template's buildings that serve nothing they said; keep its names where they still fit.
"""


@dataclass
class PlannedRoad:
    source: str        # building id
    event: str
    target: str        # building id
    why: str = ""


@dataclass
class TownPlan:
    title: str = ""
    summary: str = ""
    specs: list[dict] = field(default_factory=list)
    whys: dict[str, str] = field(default_factory=dict)       # building id → why
    roads: list[PlannedRoad] = field(default_factory=list)
    attempts: list[builders.Attempt] = field(default_factory=list)
    cost_usd: float | None = None
    error: str = ""                                           # outside validation: CLI missing, timeout…

    @property
    def ok(self) -> bool:
        return bool(self.specs) and not self.error


def offered_types() -> list[catalog.BuildingType]:
    """The types a plan may use: the camp's, without the system ones and the Builder's scratch type."""
    return [t for t in catalog.TYPES.values() if t.id != catalog.DEFAULT_TYPE
            and t.id not in catalog.SYSTEM_TYPES | catalog.SCRATCH_TYPES]


def _free_id(base: str, taken: set[str]) -> str:
    bid, n = base, 1
    while bid in taken:
        bid, n = f"{base}_{n}", n + 1
    return bid


def check(answer: dict, repo_root: Path, taken: set[str] | frozenset[str]) -> tuple[TownPlan, list[str]]:
    """The plan in an answer, with every problem; a plan with problems is never raised."""
    problems: list[str] = []
    plan = TownPlan(title=str(answer.get("title") or "")[:60], summary=str(answer.get("summary") or "")[:200])
    allowed = {t.id: t for t in offered_types()}
    taken = set(taken) | set(masonry.ID_RESERVED)
    items = answer.get("buildings")
    if not isinstance(items, list) or not items:
        return plan, ["no buildings: plan at least two"]
    if len(items) > MAX_BUILDINGS:
        problems.append(f"{len(items)} buildings: plan at most {MAX_BUILDINGS}")
    ids: dict[str, str] = {}                                  # plan key → building id
    for i, item in enumerate(items[:MAX_BUILDINGS]):
        if not isinstance(item, dict):
            problems.append(f"buildings/{i}: not an object")
            continue
        key, type_id = str(item.get("key") or ""), str(item.get("type") or "")
        type_id = catalog.ALIASES.get(type_id, type_id)
        if not KEY.match(key) or key in ids:
            problems.append(f"buildings/{i}: key {key!r} must be unique snake_case (2-32 chars)")
            continue
        if type_id not in allowed:
            problems.append(f"buildings/{i} ({key}): type {type_id!r} is not in the catalog")
            continue
        t = allowed[type_id]
        bid = _free_id(key, taken)
        spec = {"id": bid, "type": type_id, "title": t.title, "icon": t.icon, "summary": t.summary[:200],
                "orc": {"name": t.orc, "role": t.preview[:80]}}
        spec.update({k: item[k] for k in SPEC_KEYS if item.get(k) not in (None, "", [], {})})
        errors = masonry.validate_spec(spec, repo_root, taken)
        if errors:
            problems.extend(f"buildings/{i} ({key}): {e}" for e in errors)
            continue
        taken.add(bid)
        ids[key] = bid
        plan.specs.append(spec)
        plan.whys[bid] = str(item.get("why") or "")[:200]
    roads = answer.get("roads") or []
    if not isinstance(roads, list):
        problems.append("roads: must be a list")
        roads = []
    if len(roads) > MAX_ROADS:
        problems.append(f"{len(roads)} roads: plan at most {MAX_ROADS}")
    specs = {s["id"]: s for s in plan.specs}
    seen: set[tuple[str, str, str]] = set()
    for i, r in enumerate(roads[:MAX_ROADS]):
        if not isinstance(r, dict):
            problems.append(f"roads/{i}: not an object")
            continue
        src, dst, event = ids.get(str(r.get("from"))), ids.get(str(r.get("to"))), str(r.get("event") or "")
        if src is None or dst is None:
            problems.append(f"roads/{i}: from {r.get('from')!r} and to {r.get('to')!r} must be keys of planned buildings")
            continue
        if src == dst:
            problems.append(f"roads/{i}: a road joins two different buildings")
            continue
        sends = set(catalog.events_of(specs[src])) | {"on_selection_change"}
        if event not in sends:
            problems.append(f"roads/{i}: {r.get('from')} ({specs[src]['type']}) does not send {event!r}; "
                            f"it sends {', '.join(sorted(sends))}")
            continue
        if (src, event, dst) in seen:
            continue
        seen.add((src, event, dst))
        plan.roads.append(PlannedRoad(src, event, dst, str(r.get("why") or "")[:200]))
    if len(plan.specs) < 2 and not problems:
        problems.append("plan at least two buildings")
    return plan, problems


def plan(order: str, repo_root: Path, taken: set[str] | frozenset[str] = frozenset(),
         runner: builders.Runner = builders.claude_runner, feedback: str = "",
         max_attempts: int = MAX_ATTEMPTS, templates: str = "") -> TownPlan:
    """Ask for a plan until one passes `check` or the attempts run out. Never raises.
    `feedback` is the operator's note on a plan they turned down; `templates` (intents.templates_text)
    are the role's ready towns, to adapt instead of planning from nothing."""
    order = order.strip()[:ORDER_LIMIT]
    text_catalog = catalog.catalog_text(offered_types())
    attempts: list[builders.Attempt] = []
    total: float | None = None
    note = f"\nTHE OPERATOR TURNED DOWN YOUR LAST PLAN AND SAYS:\n{feedback.strip()[:600]}\n" if feedback.strip() else ""
    for _ in range(max_attempts):
        attempt = builders.Attempt()
        try:
            text, cost = runner(PLANNER.format(order=order, catalog=text_catalog, max_buildings=MAX_BUILDINGS,
                                               max_roads=MAX_ROADS, feedback=note + builders._feedback(attempts),
                                               template=ADAPT.format(templates=templates) if templates else ""))
        except RuntimeError as e:
            attempts.append(attempt)
            return TownPlan(attempts=attempts, cost_usd=total, error=str(e))
        if cost is not None:
            total = (total or 0.0) + cost
        attempt.mason = text
        answer = builders.extract_json(text)
        if answer is None:
            attempt.errors = ["the answer had no JSON object"]
            attempts.append(attempt)
            continue
        result, attempt.errors = check(answer, repo_root, taken)
        attempts.append(attempt)
        if not attempt.errors:
            result.attempts, result.cost_usd = attempts, total
            return result
    return TownPlan(attempts=attempts, cost_usd=total,
                    error="no plan passed the checks: " + "; ".join((attempts[-1].errors if attempts else [])[:3]))
