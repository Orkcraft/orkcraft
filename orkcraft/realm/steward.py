"""The steward 🪧🧌: watches how a building is used and proposes how to automate it.

A steward is a hybrid: this module's metrics are local code and cost nothing; a model is asked
only when they find a reason.

    report = watch(repo_root, scroll, "scrying", carts=app.roads.carts, runs=app.roads.runs)
    report.findings          # free: errors, jams, noisy filters, spend, an agent repeating itself …
    report.proposals         # only when there were findings: validated, demotions replayed
    apply_proposal(scroll, "scrying", report.proposals[0])

Proposals: `demote` (an agent handler → a chain, replayed on its recorded runs before it can
replace the agent), `set_run` (quiet period / restart), `filter` (a road's source filter),
`new_road` (a road from another building), `ui` (a new layout of its window: a UI document,
docs/design-system.md), `note` (anything else, for the operator). `redesign` asks for a `ui`
proposal alone, from what the operator wants changed. Each is
checked on a copy of the scroll; an invalid answer goes back to the model with the errors, at
most `MAX_ATTEMPTS` rounds. The model sees only the metrics summary and the findings — never the
graph, never the recorded inputs. The replay's ground truth is the agent's own past outputs, so
a high score means "the chain agrees with the agent", not "the chain is right".
"""
from __future__ import annotations

import copy
import datetime as dt
import difflib
import json
import re
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable

from orkcraft import scroll as ts
from orkcraft.design import ui as design_ui
from orkcraft.realm import builders, chains, chronicles, roads, tiers

# -- which model for which of its tasks ----------------------------------------------------------------

# What every steward calls a model for, and what a type's steward does besides (the Barracks' answers to
# its orks and its review of their work). Its spec keeps a tier per task (`OrcSpec.models`); a task with
# none runs on the default (the CLI's own model, or the type's setting).
USES = {"watch": "Watch: findings and proposals", "redesign": "Redesign the window", "keeper": "Rules and settings"}
TYPE_USES = {"barracks": {"triage": "Sort the tasks", "plan": "Plan the tasks", "answer": "Answer the orks' questions",
                         "review": "Review their work", "final": "Look at the whole"}}


def uses(type_id: str) -> dict[str, str]:
    """Its tasks, the type's own last: id → what it is."""
    return {**USES, **TYPE_USES.get(type_id, {})}


def tier_for(b: ts.BuildingSpec | None, use: str) -> str:
    """The tier its steward runs `use` on, or "" for the default."""
    stew = b.garrison.steward if b is not None else None
    tier = str(((stew.models if stew is not None else None) or {}).get(use) or "")
    return tier if tier in tiers.TIERS else ""


def model_for(b: ts.BuildingSpec | None, use: str, harness: str = "claude") -> str:
    """The model of that tier on `harness`, or "" for the default."""
    tier = tier_for(b, use)
    return tiers.MODELS.get(harness, {}).get(tier, "") if tier else ""


def runner_for(b: ts.BuildingSpec | None, use: str, fake: builders.Runner | None = None) -> builders.Runner:
    """The model call for one of its tasks: the test's or demo's fake as it is, else Claude on its tier."""
    if fake is not None:
        return fake
    model = model_for(b, use)
    return (lambda prompt: builders.claude_runner(prompt, model=model)) if model else builders.claude_runner


def set_models(b: ts.BuildingSpec, models: dict[str, str]) -> dict[str, str]:
    """Its steward's tier per task (an unknown task or tier is left out; empty: the default)."""
    if b.garrison.steward is None:
        raise ValueError(f"{b.title} has no steward")
    known = set(USES) | {u for t in TYPE_USES.values() for u in t}
    kept = {u: t for u, t in models.items() if u in known and t in tiers.TIERS}
    b.garrison.steward.models = kept or None
    return kept

MAX_ATTEMPTS = 3
WINDOW_DAYS = 7
PROPOSALS_DIR = Path(".orkcraft") / "steward"
READY_SCORE = 0.8               # replay agreement needed for a demotion to be "ready"
MIN_EXAMPLES = 5                # recorded agent runs before a demotion is considered
REPEAT_SIMILARITY = 0.7
SPEND_SHARE = 0.25              # of the 🪙 session limit, in the window
WIKI_READS = 3                  # an agent's own trips into a wiki before a road to it is proposed


# -- schedule ------------------------------------------------------------------------------------

_DAYS = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}


def _field_matches(spec: str, value: int, lo: int, hi: int) -> bool:
    for part in spec.split(","):
        step = 1
        if "/" in part:
            part, s = part.split("/", 1)
            step = int(s)
        if part == "*":
            a, b = lo, hi
        elif "-" in part:
            a, b = (int(x) for x in part.split("-", 1))
        else:
            a = b = int(part)
        if a <= value <= b and (value - a) % step == 0:
            return True
    return False


def _cron_match(fields: list[str], t: dt.datetime) -> bool:
    minute, hour, dom, month, dow = fields
    cron_dow = (t.weekday() + 1) % 7          # cron: 0 = Sunday
    return (_field_matches(minute, t.minute, 0, 59) and _field_matches(hour, t.hour, 0, 23)
            and _field_matches(dom, t.day, 1, 31) and _field_matches(month, t.month, 1, 12)
            and (_field_matches(dow, cron_dow, 0, 7) or (dow != "*" and cron_dow == 0 and _field_matches(dow, 7, 0, 7))))


def to_cron(expr: str) -> list[str] | None:
    """A 5-field cron, or `daily HH:MM`, `weekly <day> HH:MM`, `hourly` (the processes' form)."""
    e = expr.strip().lower()
    if m := re.fullmatch(r"daily (\d{1,2}):(\d{2})", e):
        return [str(int(m[2])), str(int(m[1])), "*", "*", "*"]
    if m := re.fullmatch(r"weekly (mon|tue|wed|thu|fri|sat|sun) (\d{1,2}):(\d{2})", e):
        return [str(int(m[3])), str(int(m[2])), "*", "*", str((_DAYS[m[1]] + 1) % 7)]
    if e == "hourly":
        return ["0", "*", "*", "*", "*"]
    fields = e.split()
    if len(fields) == 5 and all(re.fullmatch(r"[\d*/,\-]+", f) for f in fields):
        return fields
    return None


def due(expr: str, last: dt.datetime | None, now: dt.datetime) -> bool:
    """Did a scheduled time pass after `last` (or in the last minute, never run before)?"""
    fields = to_cron(expr)
    if fields is None:
        return False
    try:
        t = (last or now - dt.timedelta(minutes=1)).replace(second=0, microsecond=0) + dt.timedelta(minutes=1)
        end = now.replace(second=0, microsecond=0)
        t = max(t, end - dt.timedelta(days=8))
        while t <= end:
            if _cron_match(fields, t):
                return True
            t += dt.timedelta(minutes=1)
    except ValueError:
        return False
    return False


def next_due(expr: str, after: dt.datetime, within: dt.timedelta = dt.timedelta(days=8)) -> dt.datetime | None:
    """The first scheduled minute after `after`, at most `within` later; None when there is none in
    that time or `expr` is not a schedule. Skips whole days and hours that cannot match."""
    fields = to_cron(expr)
    if fields is None:
        return None
    minute, hour, dom, month, dow = fields
    t = after.replace(second=0, microsecond=0) + dt.timedelta(minutes=1)
    end = after + within
    try:
        while t <= end:
            if not _cron_match(["*", "*", dom, month, dow], t):
                t = (t + dt.timedelta(days=1)).replace(hour=0, minute=0)
            elif not _cron_match(["*", hour, dom, month, dow], t):
                t = (t + dt.timedelta(hours=1)).replace(minute=0)
            elif not _field_matches(minute, t.minute, 0, 59):
                t += dt.timedelta(minutes=1)
            else:
                return t
    except ValueError:
        return None
    return None


# -- metrics (free) ------------------------------------------------------------------------------

@dataclass
class Metrics:
    building_id: str
    days: int = WINDOW_DAYS
    events: dict[str, int] = field(default_factory=dict)             # chronicle type → count
    spend_usd: dict[str, float] = field(default_factory=dict)        # orc id → 🪙 of its sessions
    runs: dict[str, dict[str, int]] = field(default_factory=dict)    # orc id → outcome → count
    carts_in: dict[str, dict[str, int]] = field(default_factory=dict)   # road id → status → count
    carts_out: int = 0
    examples: dict[str, int] = field(default_factory=dict)           # agent orc id → recorded runs
    similarity: dict[str, float] = field(default_factory=dict)       # agent orc id → output likeness
    wiki_reads: dict[str, int] = field(default_factory=dict)         # wiki building id → its agents' own trips there

    @property
    def total_spend(self) -> float:
        return round(sum(self.spend_usd.values()), 4)


_SHAPE = [(re.compile(r"\b[TCP]\d{4,}\b"), "<ID>"), (re.compile(r"\d+([.,]\d+)?"), "<N>"),
          (re.compile(r"\s+"), " ")]


def _shape(text: str, inputs: list | None = None) -> str:
    """The output with the input's own values masked (longest first), then ids and numbers:
    a template filled from the input collapses to the same shape every time."""
    values = []
    for rec in inputs or []:
        if isinstance(rec, dict):
            values += [(k, str(v)) for k, v in rec.items() if isinstance(v, (str, int, float)) and len(str(v)) >= 3]
    for key, value in sorted(values, key=lambda kv: -len(kv[1])):
        text = text.replace(value, f"<{key}>")
    for pattern, repl in _SHAPE:
        text = pattern.sub(repl, text)
    return text.strip()


def output_similarity(outputs: list[str], inputs: list[list] | None = None) -> float:
    """How alike an agent's outputs are once the input values, ids and numbers are masked (0..1)."""
    inputs = inputs or [[] for _ in outputs]
    shapes = [_shape(o, i) for o, i in zip(outputs, inputs) if o.strip()]
    if len(shapes) < 2:
        return 0.0
    pairs = list(zip(shapes, shapes[1:]))
    return round(sum(difflib.SequenceMatcher(None, a, b).ratio() for a, b in pairs) / len(pairs), 3)


def _session_cost(transcript: str | None) -> float:
    if not transcript:
        return 0.0
    from orkcraft.sources.transcripts import read_run
    return read_run(transcript).cost or 0.0


def collect(repo_root: Path, scroll: ts.TownScroll, building_id: str, *, carts: Iterable[roads.Cart] = (),
            runs: Iterable[roads.HandlerRun] = (), sessions: list | None = None, days: int = WINDOW_DAYS,
            now: dt.datetime | None = None) -> Metrics:
    """Everything the steward knows about a building, from local files and the engine's memory."""
    now = now or dt.datetime.now()
    since = now - dt.timedelta(days=days)
    b = scroll.building(building_id)
    m = Metrics(building_id, days)
    if b is None:
        return m
    events: Counter = Counter()
    for e in chronicles.history(repo_root, building_id, limit=2000):
        try:
            when = dt.datetime.fromisoformat(str(e.get("ts", "")))
        except ValueError:
            continue
        if when >= since:
            events[e.get("type", "?")] += 1
    m.events = dict(events)
    if sessions is None:
        from orkcraft.sources.sessions import collect_sessions
        try:
            sessions = collect_sessions(repo_root)
        except OSError:
            sessions = []
    for orc in b.garrison.members:
        ref = f"{building_id}/{orc.id}"
        cost = sum(_session_cost(s.transcript) for s in sessions
                   if ref in getattr(s, "orcs", set()) and (s.last is None or s.last.replace(tzinfo=None) >= since))
        if cost:
            m.spend_usd[orc.id] = round(cost, 4)
    for run in runs:
        if run.target == building_id:
            m.runs.setdefault(run.orc_id, {}).setdefault(run.outcome, 0)
            m.runs[run.orc_id][run.outcome] += 1
    live = {r.id for r in b.roads}
    for cart in carts:
        if cart.target == building_id and cart.road_id in live:
            m.carts_in.setdefault(cart.road_id, {}).setdefault(cart.status, 0)
            m.carts_in[cart.road_id][cart.status] += 1
        elif cart.source == building_id:
            m.carts_out += 1
    m.wiki_reads = wiki_trips(repo_root, building_id, sessions, since)
    for orc in b.garrison.handlers:
        if orc.uses_model:
            ex = roads.read_examples(repo_root, building_id, orc.id)
            if ex:
                m.examples[orc.id] = len(ex)
                m.similarity[orc.id] = output_similarity([e["output"] for e in ex], [e["inputs"] for e in ex])
    return m


def wikis(repo_root: Path) -> dict[str, str]:
    """The project's LLM wikis: Scroll Dump building id → its wiki's folder (repo-relative)."""
    from orkcraft.realm import catalog, masonry, wiki
    try:
        specs, _ = masonry.load_specs(repo_root)
    except OSError:
        return {}
    out = {}
    for spec in specs:
        if catalog.migrate(spec).get("type") == "scrolls":
            cfg = spec.get("config") or {}
            folder = str(cfg.get("wiki") or "").strip() or wiki.default_dir(wiki.topic_of(cfg))
            out[str(spec.get("id"))] = folder.strip("/")
    return out


def wiki_trips(repo_root: Path, building_id: str, sessions: list, since: dt.datetime) -> dict[str, int]:
    """How often the building's agents went into a wiki by themselves (a tool call naming its folder)."""
    folders = {bid: f for bid, f in wikis(repo_root).items() if bid != building_id}
    if not folders:
        return {}
    from orkcraft.sources.transcripts import read_run
    trips: Counter = Counter()
    for s in sessions:
        if not any(str(o).startswith(f"{building_id}/") for o in getattr(s, "orcs", set())):
            continue
        if not s.transcript or (s.last is not None and s.last.replace(tzinfo=None) < since):
            continue
        for step in read_run(s.transcript).steps:
            if step.kind == "tool":
                for bid, folder in folders.items():
                    if f"{folder}/" in step.detail or f"{folder}/" in step.title:
                        trips[bid] += 1
    return dict(trips)


@dataclass
class Finding:
    kind: str            # handler_errors | jam | repeats | noisy_filter | spend | unused | wiki_bypass
    summary: str
    orc_id: str = ""
    road_id: str = ""
    evidence: dict = field(default_factory=dict)


def findings(m: Metrics, scroll: ts.TownScroll) -> list[Finding]:
    b = scroll.building(m.building_id)
    if b is None:
        return []
    out: list[Finding] = []
    for orc_id, outcomes in m.runs.items():
        total = sum(outcomes.values())
        errors, done, interrupted = outcomes.get("error", 0), outcomes.get("done", 0), outcomes.get("interrupted", 0)
        if errors >= 3 and errors * 2 >= total:
            out.append(Finding("handler_errors", f"{orc_id} failed {errors} of {total} runs", orc_id=orc_id,
                               evidence=dict(outcomes)))
        if interrupted >= 3 and interrupted >= done:
            out.append(Finding("jam", f"{orc_id} was restarted {interrupted} times and finished {done}: "
                                      f"events arrive faster than it works", orc_id=orc_id, evidence=dict(outcomes)))
    for orc_id, n in m.examples.items():
        sim = m.similarity.get(orc_id, 0.0)
        if n >= MIN_EXAMPLES and sim >= REPEAT_SIMILARITY:
            out.append(Finding("repeats", f"{orc_id} (an agent) gave {n} answers of the same shape "
                                          f"(likeness {sim:.2f}): a chain may do", orc_id=orc_id,
                               evidence={"examples": n, "similarity": sim}))
    for road_id, statuses in m.carts_in.items():
        total = sum(statuses.values())
        filtered = statuses.get("filtered", 0)
        if total >= 20 and filtered >= 0.95 * total:
            out.append(Finding("noisy_filter", f"road {road_id} dropped {filtered} of {total} events at the "
                                               f"source", road_id=road_id, evidence=dict(statuses)))
    limit = scroll.budget.gold_session_limit_usd
    if limit and m.total_spend >= SPEND_SHARE * limit:
        out.append(Finding("spend", f"{b.title} spent ${m.total_spend:.2f} in {m.days} days "
                                    f"({m.total_spend / limit:.0%} of the ${limit:.0f} limit)",
                           evidence={"by_orc": m.spend_usd}))
    fed = {r.source for r in b.roads}
    for wiki_id, n in sorted(m.wiki_reads.items()):
        if n >= WIKI_READS and wiki_id not in fed:
            out.append(Finding("wiki_bypass", f"{b.title}'s agents went into the {wiki_id} wiki by themselves {n} "
                                              f"times: send their tasks through it", evidence={"wiki": wiki_id, "trips": n}))
    if not b.demolished and not m.events and not m.carts_in and not m.carts_out and not m.runs and not m.wiki_reads:
        out.append(Finding("unused", f"{b.title}: no events, carts or runs in {m.days} days"))
    return out


# -- replay ----------------------------------------------------------------------------------------

@dataclass
class Replay:
    score: float = 0.0          # mean likeness of the chain's output to the agent's
    exact: int = 0
    total: int = 0
    samples: list[dict] = field(default_factory=list)    # a few {expected, got, likeness}

    @property
    def ready(self) -> bool:
        return self.total >= 1 and self.score >= READY_SCORE


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def replay(chain: list[dict], examples: list[dict]) -> Replay:
    """Run a chain on recorded agent inputs and compare with the agent's outputs."""
    rep = Replay(total=len(examples))
    ratios = []
    for e in examples:
        got = chains.run_chain(chain, e["inputs"])
        expected = e["output"]
        ratio = 0.0 if not got.ok else difflib.SequenceMatcher(None, _norm(expected), _norm(got.markdown)).ratio()
        ratios.append(ratio)
        rep.exact += int(got.ok and _norm(expected) == _norm(got.markdown))
        if len(rep.samples) < 3 and ratio < 1.0:
            rep.samples.append({"expected": expected[:400], "got": (got.markdown or got.error)[:400],
                                "likeness": round(ratio, 3)})
    rep.score = round(sum(ratios) / len(ratios), 3) if ratios else 0.0
    return rep


# -- proposals (the escalation) --------------------------------------------------------------------

PROPOSE = """You are the steward of the {title} building in orkcraft, a terminal harness where windows pass
events along roads to handler orcs (chain = declarative ops, script = reviewed Python, agent = Claude / agy,
hybrid = script + agent). Cheaper is better: an agent should be demoted to a chain when a chain can do its job.

THE BUILDING:
{building}

METRICS OVER {days} DAYS:
{metrics}

FINDINGS (why you were woken up):
{findings}

RECORDED AGENT RUNS (one input record and its output per agent, for demotions):
{samples}

Chain ops (records have fields road, source, event, kind, value, title, id, path, text, type, status, outcome):
filter {{field, cmp: eq|ne|in|contains|matches, value}} · pick {{fields}} · extract {{field, regex, as}} ·
sort {{by, desc}} · limit {{n}} · count {{as}} · group {{by}} · template {{md with {{field}}}} · join {{sep}}
Road filter keys: node_type, node_status, exclude_personal, path_prefix, outcome, match, route.
{feedback}
Answer with ONE JSON object and nothing else: {{"proposals": [ ... 1-4 items ... ]}}, each one of
{{"type": "demote", "orc": "<agent handler id>", "chain": [ops], "why": "..."}}
{{"type": "set_run", "orc": "<handler id>", "run": {{"quiet_s": N, "restart_on_new": bool}}, "why": "..."}}
{{"type": "filter", "road": "<road id>", "filter": {{...}}, "why": "..."}}
{{"type": "new_road", "from": "<building id>", "event": "...", "filter": {{...}}, "handler": "<handler id or null>", "why": "..."}}
{{"type": "note", "text": "...", "why": "..."}}"""


@dataclass
class Proposal:
    type: str
    why: str
    data: dict = field(default_factory=dict)
    replay: Replay | None = None

    @property
    def ready(self) -> bool:
        return self.type != "demote" or (self.replay is not None and self.replay.ready)

    def to_dict(self) -> dict:
        d = {"type": self.type, "why": self.why, **self.data}
        if self.replay is not None:
            d["replay"] = asdict(self.replay)
        return d


@dataclass
class StewardReport:
    building_id: str
    metrics: Metrics
    findings: list[Finding] = field(default_factory=list)
    proposals: list[Proposal] = field(default_factory=list)
    escalated: bool = False
    attempts: int = 0
    cost_usd: float | None = None
    error: str = ""
    errors: list[str] = field(default_factory=list)     # of the last rejected answer


def apply_proposal(scroll: ts.TownScroll, building_id: str, p: Proposal | dict) -> str:
    """Apply one proposal to `scroll`; returns a one-line description. Raises ValueError."""
    if isinstance(p, dict):
        p = Proposal(str(p.get("type")), str(p.get("why") or ""), {k: v for k, v in p.items() if k not in ("type", "why", "replay")})
    d = p.data
    if p.type == "demote":
        b = scroll.building(building_id)
        orc = b.garrison.handler(str(d.get("orc"))) if b else None
        if orc is None or not orc.uses_model:
            raise ValueError(f"{d.get('orc')!r} is not an agent handler of {building_id}")
        ts.update_orc(scroll, building_id, orc.id, kind="chain", chain=list(d.get("chain") or []), harness=[],
                      avatar="🪧", why=p.why, run=None)
        return f"{orc.name} demoted to a chain"
    if p.type == "set_run":
        b = scroll.building(building_id)
        if b is None or b.garrison.handler(str(d.get("orc"))) is None:
            raise ValueError(f"{d.get('orc')!r} is not a handler of {building_id}")
        ts.update_orc(scroll, building_id, str(d["orc"]), run=dict(d.get("run") or {}))
        return f"{d['orc']}: run policy {d.get('run')}"
    if p.type == "filter":
        ts.set_road_filter(scroll, building_id, str(d.get("road")), dict(d.get("filter") or {}))
        return f"road {d['road']}: filter {d.get('filter')}"
    if p.type == "new_road":
        target = str(d.get("to") or building_id)
        if scroll.building(target) is None:
            raise ValueError(f"no building {target!r}")
        r = ts.subscribe(scroll, target, str(d.get("from")), str(d.get("event")), d.get("filter") or None,
                         handler=d.get("handler") or None)
        return f"new road {r.id}"
    if p.type == "ui":
        b = scroll.building(building_id)
        doc = d.get("ui")
        if b is None or not isinstance(doc, dict):
            raise ValueError("a ui proposal carries the whole UI document in `ui`")
        problems = design_ui.validate(doc, design_ui.contract(str(doc.get("type") or "")))
        if problems:
            raise ValueError("; ".join(problems[:6]))
        b.ui = copy.deepcopy(doc)
        return "a new layout"
    if p.type == "note":
        if not str(d.get("text") or "").strip():
            raise ValueError("a note needs text")
        return "note"
    raise ValueError(f"unknown proposal type {p.type!r}")


def _summary(scroll: ts.TownScroll, b: ts.BuildingSpec) -> str:
    lines = [f"id {b.id}; steward {b.garrison.steward.name if b.garrison.steward else '—'}"]
    for orc in b.garrison.handlers:
        lines.append(f"handler {orc.id} ({orc.kind}, run {orc.run_policy}): orders {orc.orders[:200]!r}; "
                     f"roads {[r.id for r in b.roads_of(orc.id)]}")
    for r in b.roads:
        lines.append(f"road {r.id}: from {r.source} {r.event}, filter {r.filter or 'none'}, handler {r.handler or 'plain'}")
    return "\n".join(lines)


def _samples(repo_root: Path, b: ts.BuildingSpec) -> str:
    out = []
    for orc in b.garrison.handlers:
        if not orc.uses_model:
            continue
        ex = roads.read_examples(repo_root, b.id, orc.id, limit=3)
        for e in ex[-1:]:
            rec = [{k: v for k, v in r.items() if k != "text" or len(str(v)) < 400} for r in e["inputs"][:3]]
            out.append(f"{orc.id}: input {json.dumps(rec, ensure_ascii=False)[:1200]} → output {e['output'][:600]!r}")
    return "\n".join(out) or "none"


def _check(answer: Any, repo_root: Path, scroll: ts.TownScroll, building_id: str) -> tuple[list[Proposal], list[str]]:
    if not isinstance(answer, dict) or not isinstance(answer.get("proposals"), list):
        return [], ['answer with {"proposals": [...]}']
    items = answer["proposals"]
    if not 1 <= len(items) <= 4:
        return [], ["give 1-4 proposals"]
    trial = copy.deepcopy(scroll)
    out, errors = [], []
    for i, item in enumerate(items, 1):
        if not isinstance(item, dict):
            errors.append(f"proposal {i}: not an object")
            continue
        p = Proposal(str(item.get("type")), str(item.get("why") or "").strip(),
                     {k: v for k, v in item.items() if k not in ("type", "why")})
        if not p.why:
            errors.append(f"proposal {i}: why is required")
            continue
        try:
            apply_proposal(copy.deepcopy(trial), building_id, p)
        except (ValueError, TypeError, KeyError) as e:
            errors.append(f"proposal {i} ({p.type}): {e}")
            continue
        if p.type == "demote":
            p.replay = replay(list(p.data.get("chain") or []), roads.read_examples(repo_root, building_id, str(p.data["orc"])))
        out.append(p)
    return (out, []) if not errors else ([], errors)


def watch(repo_root: Path, scroll: ts.TownScroll, building_id: str, *, carts: Iterable[roads.Cart] = (),
          runs: Iterable[roads.HandlerRun] = (), sessions: list | None = None,
          runner: builders.Runner = builders.claude_runner, budget_ok: bool = True,
          now: dt.datetime | None = None, max_attempts: int = MAX_ATTEMPTS) -> StewardReport:
    """Metrics → findings → (only if any, and within 🪙) proposals. Never raises."""
    m = collect(repo_root, scroll, building_id, carts=carts, runs=runs, sessions=sessions, now=now)
    report = StewardReport(building_id, m, findings(m, scroll))
    b = scroll.building(building_id)
    if b is None or not report.findings:
        return report
    known = wiki_loop(scroll, b, [f for f in report.findings if f.kind == "wiki_bypass"])
    if known and all(f.kind == "wiki_bypass" for f in report.findings):
        report.proposals = known                          # free: no model needed to say this
        return report
    if not budget_ok:
        report.error = "🪙 budget exhausted — findings only"
        return report
    report.escalated = True
    feedback = ""
    for _ in range(max_attempts):
        prompt = PROPOSE.format(
            title=b.title, building=_summary(scroll, b), days=m.days,
            metrics=json.dumps({k: v for k, v in asdict(m).items() if k != "building_id"}, ensure_ascii=False),
            findings="\n".join(f"- [{f.kind}] {f.summary}" for f in report.findings),
            samples=_samples(repo_root, b), feedback=feedback)
        report.attempts += 1
        try:
            text, cost = runner(prompt)
        except RuntimeError as e:
            report.error = str(e)
            return report
        if cost is not None:
            report.cost_usd = (report.cost_usd or 0.0) + cost
        proposals, errors = _check(builders.extract_json(text), repo_root, scroll, building_id)
        if proposals:
            report.proposals, report.errors = known + proposals, []
            return report
        report.errors = errors or ["no JSON object in the answer"]
        feedback = "\nYOUR PREVIOUS ANSWER WAS REJECTED. Fix every problem:\n" + "\n".join(f"- {e}" for e in report.errors[:12])
    return report


REDESIGN = """You are the steward of the {title} building in orkcraft. The operator wants its window laid out
differently. Its window is described by a UI document: panes of components in rows and columns, named
by roles from the design system. Rewrite the document.

WHAT THE OPERATOR WANTS:
{request}

THE BUILDING'S CONTRACT (the panes it has, the components each may wear):
{contract}

COMPONENTS: {components}
FONT ROLES: {fonts}
COLOUR ROLES (tone): {tones}

THE RULES:
{rules}

ITS UI DOCUMENT NOW:
{current}
{feedback}
Answer with ONE JSON object and nothing else: {{"proposals": [{{"type": "ui", "ui": <the whole new document>,
"why": "<one sentence for the operator>"}}]}}"""


def redesign(repo_root: Path, scroll: ts.TownScroll, building_id: str, type_id: str, request: str, *,
             runner: builders.Runner = builders.claude_runner, budget_ok: bool = True,
             max_attempts: int = MAX_ATTEMPTS) -> StewardReport:
    """The operator's wish for the building's window → one `ui` proposal (a whole UI document, checked
    against the type's contract; a rejected answer goes back with the problems). Never raises."""
    report = StewardReport(building_id, Metrics(building_id))
    b = scroll.building(building_id)
    if b is None:
        report.error = f"no building {building_id!r}"
        return report
    if not budget_ok:
        report.error = "🪙 budget exhausted — the steward costs a model call"
        return report
    from orkcraft.design import tokens
    contract = design_ui.contract(type_id)
    current = design_ui.current(b, type_id)
    report.escalated = True
    feedback = ""
    for _ in range(max_attempts):
        prompt = REDESIGN.format(
            title=b.title, request=request.strip()[:1500] or "make it easier to read", contract=contract.describe(),
            components="; ".join(f"{k} ({v})" for k, v in design_ui.COMPONENTS.items()),
            fonts=", ".join(tokens.FONTS), tones=", ".join(tokens.TONES), rules=design_ui.RULES,
            current=json.dumps(current, ensure_ascii=False, indent=1), feedback=feedback)
        report.attempts += 1
        try:
            text, cost = runner(prompt)
        except RuntimeError as e:
            report.error = str(e)
            return report
        if cost is not None:
            report.cost_usd = (report.cost_usd or 0.0) + cost
        answer = builders.extract_json(text)
        proposals, errors = _check(answer, repo_root, scroll, building_id)
        if proposals and all(p.type == "ui" for p in proposals):
            wrong = [p for p in proposals if (p.data.get("ui") or {}).get("type") != type_id]
            if not wrong:
                report.proposals, report.errors = proposals[:1], []
                return report
            errors = [f"ui.type must be {type_id!r}"]
        report.errors = errors or ['answer with {"proposals": [{"type": "ui", "ui": {...}, "why": "..."}]}']
        feedback = "\nYOUR PREVIOUS ANSWER WAS REJECTED. Fix every problem:\n" + "\n".join(f"- {e}" for e in report.errors[:12])
    return report


def wiki_loop(scroll: ts.TownScroll, b: ts.BuildingSpec, found: list[Finding]) -> list[Proposal]:
    """For each wiki the agents reach by themselves: the wiki's map to the building, and the
    building's own sources to the wiki — its tasks then pass through the wiki on their way in."""
    out: list[Proposal] = []
    trial = copy.deepcopy(scroll)

    def fits(p: Proposal) -> bool:                    # no loop of roads, no unknown building
        try:
            apply_proposal(trial, b.id, p)
            return True
        except (ValueError, TypeError, KeyError):
            return False

    for f in found:
        wiki_id = str(f.evidence.get("wiki"))
        if scroll.building(wiki_id) is None:
            continue
        first = Proposal("new_road", f"{f.summary}; the wiki's map then comes with every task",
                         {"from": wiki_id, "event": "knowledge.chunks"})
        if not fits(first):
            continue
        out.append(first)
        for r in b.roads:
            if r.source != wiki_id and not any(x.source == r.source and x.event == r.event
                                               for x in scroll.building(wiki_id).roads):
                p = Proposal("new_road", f"route {r.source} {r.event} through the {wiki_id} wiki "
                                         f"(then retire road {r.id})", {"to": wiki_id, "from": r.source, "event": r.event})
                if fits(p):
                    out.append(p)
    return out


def save_report(repo_root: Path, report: StewardReport) -> Path:
    """`.orkcraft/steward/<building>.json` (git-ignored): the last report, for the UI."""
    path = repo_root / PROPOSALS_DIR / f"{report.building_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "ts": dt.datetime.now().isoformat(timespec="seconds"), "building": report.building_id,
        "findings": [asdict(f) for f in report.findings], "proposals": [p.to_dict() for p in report.proposals],
        "escalated": report.escalated, "attempts": report.attempts, "cost_usd": report.cost_usd,
        "error": report.error, "metrics": asdict(report.metrics),
    }
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return path


def load_report(repo_root: Path, building_id: str) -> dict | None:
    try:
        data = json.loads((repo_root / PROPOSALS_DIR / f"{building_id}.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None
