"""A steward's free half: the metrics of a building's use, what they find, and the replay that checks a
demotion on its recorded runs — local code that costs nothing (no model is asked). Split out of
`realm/steward.py`, which re-exports it.
"""
from __future__ import annotations

import datetime as dt
import difflib
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from orkcraft import scroll as ts
from orkcraft.realm import chains, chronicles, roads
from orkcraft.realm.steward_models import harness_for

WINDOW_DAYS = 7
READY_SCORE = 0.8               # replay agreement needed for a demotion to be "ready"
MIN_EXAMPLES = 5                # recorded agent runs before a demotion is considered
REPEAT_SIMILARITY = 0.7
SPEND_SHARE = 0.25              # of the 🪙 session limit, in the window
WIKI_READS = 3                  # an agent's own trips into a wiki before a road to it is proposed


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
    run_spend: dict[str, float] = field(default_factory=dict)        # model handler id → 🪙 of its runs in the window
    run_count: dict[str, int] = field(default_factory=dict)          # model handler id → its runs in the window

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
            recent = [e for e in ex if _within(e, since)]
            if recent:                                   # what a rule (or an agent) costs on its tier: the signal
                m.run_count[orc.id] = len(recent)
                m.run_spend[orc.id] = round(sum(float(e.get("cost_usd") or 0) for e in recent), 4)
    return m


def _within(example: dict, since: dt.datetime) -> bool:
    """A recorded run in the window (one without a time counts: older logs had none)."""
    try:
        return dt.datetime.fromisoformat(str(example["ts"])) >= since
    except (KeyError, ValueError):
        return True


def weekly_spend(m: Metrics, orc_id: str) -> float:
    """What a model handler's runs cost per week, from the window's runs."""
    return round(m.run_spend.get(orc_id, 0.0) * 7 / max(1, m.days), 2)


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
    kind: str            # handler_errors | jam | repeats | noisy_filter | spend | unused | wiki_bypass | hand | code_failing
    summary: str
    orc_id: str = ""
    road_id: str = ""
    evidence: dict = field(default_factory=dict)


def stewards_own(harness: list | None, b: ts.BuildingSpec | None) -> bool:
    """Whether an agent's tools are nothing its building's steward lacks: one step, on the steward's own tool
    (`main` read as the machine's main tool) — then it is the steward's work, a road rule."""
    steps = [s for s in harness or [] if isinstance(s, dict)]
    return len(steps) == 1 and roads.resolve(str(steps[0].get("harness") or "")) == roads.resolve(harness_for(b))


def _on_stewards_tool(orc: ts.OrcSpec, b: ts.BuildingSpec) -> bool:
    return stewards_own(orc.harness, b)


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
    # Code over thinking (docs/design/steward-listens.md §2a): the rule that costs most is looked at first.
    for orc_id, n in sorted(m.examples.items(), key=lambda kv: -m.run_spend.get(kv[0], 0.0)):
        sim = m.similarity.get(orc_id, 0.0)
        orc = b.garrison.handler(orc_id)
        what = "a road rule" if orc is not None and orc.kind == "steward" else "an agent"
        if n >= MIN_EXAMPLES and sim >= REPEAT_SIMILARITY:
            cost = f", ${weekly_spend(m, orc_id):.2f}/week" if m.run_spend.get(orc_id) else ""
            out.append(Finding("repeats", f"{orc_id} ({what}) gave {n} answers of the same shape "
                                          f"(likeness {sim:.2f}{cost}): code may do", orc_id=orc_id,
                               evidence={"examples": n, "similarity": sim, "usd_week": weekly_spend(m, orc_id)}))
    for orc in b.garrison.handlers:
        if orc.kind == "agent" and _on_stewards_tool(orc, b):
            out.append(Finding("hand", f"{orc.name} (an agent) thinks on the steward's own tool: hand it to the "
                                       f"steward as a road rule", orc_id=orc.id))
        errors = m.runs.get(orc.id, {}).get("error", 0)
        if orc.kind in ("chain", "script", "hybrid") and orc.orders.strip() and errors >= 3 \
                and errors * 2 >= sum(m.runs.get(orc.id, {}).values()):
            out.append(Finding("code_failing", f"{orc.name}'s code failed {errors} times: back to its rule in words "
                                               f"until the carts settle", orc_id=orc.id))
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
    escalated: int = 0          # a hybrid's carts it handed to the steward (left out of the score)

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


def replay_script(source: str, examples: list[dict], repo_root: Path, hybrid: bool = False) -> Replay:
    """Run a reviewed script on recorded inputs and compare with the outputs (as `replay`). Only ever called
    once the Council and the operator reviewed it. A hybrid's exit 3 hands a cart to the steward: such a cart
    is left out of the score (`escalated`), and a script that hands every cart over is not ready."""
    import tempfile
    import threading
    rep = Replay(total=len(examples))
    ratios = []
    with tempfile.TemporaryDirectory(prefix="orkcraft-replay-") as tmp:
        path = Path(tmp) / "handler.py"
        path.write_text(source, encoding="utf-8")
        for e in examples:
            try:
                code, got, err = roads.run_handler_script(path, e["inputs"], repo_root, threading.Event(), timeout_s=20)
            except (RuntimeError, InterruptedError, OSError) as x:
                code, got, err = 1, "", str(x)
            if hybrid and code == roads.ESCALATE:
                rep.escalated += 1
                continue
            ratio = 0.0 if code != 0 else difflib.SequenceMatcher(None, _norm(e["output"]), _norm(got)).ratio()
            ratios.append(ratio)
            rep.exact += int(code == 0 and _norm(e["output"]) == _norm(got))
            if len(rep.samples) < 3 and ratio < 1.0:
                rep.samples.append({"expected": e["output"][:400], "got": (got or err)[:400], "likeness": round(ratio, 3)})
    rep.total -= rep.escalated
    rep.score = round(sum(ratios) / len(ratios), 3) if ratios else 0.0
    return rep
