"""The steward 🪧🧌: watches how a building is used and proposes how to automate it.

A steward is a hybrid: this module's metrics are local code and cost nothing; a model is asked
only when they find a reason.

    report = watch(repo_root, scroll, "scrying", carts=app.roads.carts, runs=app.roads.runs)
    report.findings          # free: errors, jams, noisy filters, spend, an agent repeating itself …
    report.proposals         # only when there were findings: validated, demotions replayed
    apply_proposal(scroll, "scrying", report.proposals[0])

Proposals: `demote` (an agent handler or a road rule → a chain, replayed on its recorded runs before it
can replace it; or → a script / a hybrid, replayed only once the Council and the operator reviewed it),
`hand` (an agent on the steward's own tool → a road rule), `rule` (code that came from a rule and keeps
failing → back to its words), `set_run` (quiet period / restart), `filter` (a road's source filter),
`new_road` (a road from another building), `ui` (a new layout of its window: a UI document,
docs/design-system.md), `note` (anything else, for the operator). `redesign` asks for a `ui`
proposal alone, from what the operator wants changed. Each is
checked on a copy of the scroll; an invalid answer goes back to the model with the errors, at
most `MAX_ATTEMPTS` rounds. The model sees only the metrics summary and the findings — never the
graph, never the recorded inputs. The replay's ground truth is the agent's own past outputs, so
a high score means "the chain agrees with the agent", not "the chain is right".
"""
from __future__ import annotations

import ast
import copy
import datetime as dt
import hashlib
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable

from orkcraft import scroll as ts
from orkcraft.design import ui as design_ui
from orkcraft.realm import builders, looks, roads
from orkcraft.realm.steward_metrics import (  # noqa: F401  (the free half, as before the split)
    READY_SCORE, Finding, Metrics, Replay, collect, findings, output_similarity, replay, replay_script,
    stewards_own, weekly_spend)
from orkcraft.realm.steward_models import (  # noqa: F401  (its models, as before the split)
    NOT_YET, PURPOSE, TYPE_USES, USES, WORK, WORK_ALL, Pick, _g, goal_tier, harness_for, is_work, model_for,
    pick, purpose_of, runner_for, set_models, tier_for, uses)


MAX_ATTEMPTS = 3
SCRIPT_LIMIT = 20_000           # characters of a script the steward writes
PROPOSALS_DIR = Path(".orkcraft") / "steward"


# -- proposals (the escalation) --------------------------------------------------------------------

PROPOSE = """You are the steward of the {title} building in orkcraft, a harness where buildings pass events along
roads to handlers (chain = declarative ops, script = reviewed Python, steward = a road rule in words that YOU carry
out on every cart, agent = its own model tools, hybrid = a script that hands the carts it cannot decide to you).
Code over thinking: do not spend tokens on what code can do. A road rule or an agent that only processes its
carts (picks fields, filters, reformats, counts, sorts by a keyword, fills a template) becomes a chain when the
ops can do it, else a script; where only part is routine, a hybrid. The rule that costs most goes first.

THE BUILDING:
{building}

METRICS OVER {days} DAYS:
{metrics}

FINDINGS (why you were woken up):
{findings}

RECORDED RUNS (one input record and its output per road rule or agent, for demotions):
{samples}

WHAT THE RULES AND AGENTS COST ({days} days): {spend}

Chain ops (records have fields road, source, event, kind, value, title, id, path, text, type, status, outcome):
filter {{field, cmp: eq|ne|in|contains|matches, value}} · pick {{fields}} · extract {{field, regex, as}} ·
sort {{by, desc}} · limit {{n}} · count {{as}} · group {{by}} · template {{md with {{field}}}} · join {{sep}}
Road filter keys: node_type, node_status, exclude_personal, path_prefix, outcome, match, route, want.
{feedback}
Answer with ONE JSON object and nothing else: {{"proposals": [ ... 1-4 items ... ]}}, each one of
{{"type": "demote", "orc": "<rule or agent handler id>", "chain": [ops], "why": "..."}}
{{"type": "demote", "orc": "<rule or agent handler id>", "script": "<python: JSON records on stdin, Markdown on stdout; a hybrid exits 3 for a cart you should decide>", "hybrid": bool, "why": "..."}}
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
        """Applicable now: a chain once its replay agrees; a script once reviewed (it is replayed then)."""
        if self.type != "demote" or self.data.get("script"):
            return True
        return self.replay is not None and self.replay.ready

    def to_dict(self) -> dict:
        d = {"type": self.type, "why": self.why, **self.data}
        if self.replay is not None:
            d["replay"] = {**asdict(self.replay), "ready": self.replay.ready}   # the night reads it (core/night.py)
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
            raise ValueError(f"{d.get('orc')!r} is not an agent handler or a road rule of {building_id}")
        if d.get("script"):                           # its words (`orders`) stay next to the code: the way back
            source = str(d["script"])
            kind = "hybrid" if d.get("hybrid") else "script"
            ts.update_orc(scroll, building_id, orc.id, kind=kind, chain=[], harness=[], avatar=looks.kind_icon(kind),
                          why=p.why, run=None, script={"path": script_path(building_id, orc.id),
                                                       "sha256": hashlib.sha256(source.encode()).hexdigest(),
                                                       "reviewed": bool(d.get("reviewed"))})
            return f"{orc.name} turned into a {'hybrid (script, the steward for the rest)' if kind == 'hybrid' else 'script'}"
        ts.update_orc(scroll, building_id, orc.id, kind="chain", chain=list(d.get("chain") or []), harness=[],
                      avatar="🪧", why=p.why, run=None, script=None)
        return f"{orc.name} demoted to a chain"
    if p.type == "hand":
        b = scroll.building(building_id)
        orc = b.garrison.handler(str(d.get("orc"))) if b else None
        if orc is None or orc.kind != "agent" or not orc.orders.strip():
            raise ValueError(f"{d.get('orc')!r} is not an agent handler with orders in {building_id}")
        ts.update_orc(scroll, building_id, orc.id, kind="steward", harness=[], avatar="📜", why=p.why)
        return f"{orc.name} handed to the steward as a road rule"
    if p.type == "rule":
        b = scroll.building(building_id)
        orc = b.garrison.handler(str(d.get("orc"))) if b else None
        if orc is None or orc.kind not in ("chain", "script", "hybrid") or not orc.orders.strip():
            raise ValueError(f"{d.get('orc')!r} is no code with a rule's words in {building_id}")
        ts.update_orc(scroll, building_id, orc.id, kind="steward", chain=[], script=None, harness=[], avatar="📜",
                      why=p.why, run=None)
        return f"{orc.name} back to its rule in words"
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


def script_path(building_id: str, orc_id: str) -> str:
    """Where a handler's script lives (repo-relative), as the Recruiter keeps one."""
    return f".orkcraft/scripts/{building_id}-{orc_id}"[:60].replace("_", "-") + ".py"


def free_moves(scroll: ts.TownScroll, b: ts.BuildingSpec, found: list[Finding]) -> list[Proposal]:
    """What the findings say by themselves, no model needed: an agent on the steward's own tool is handed to
    the steward; code that came from a rule and keeps failing goes back to the rule's words."""
    out = []
    for f in found:
        if f.kind == "hand":
            out.append(Proposal("hand", f.summary, {"orc": f.orc_id}))
        elif f.kind == "code_failing":
            out.append(Proposal("rule", f.summary, {"orc": f.orc_id}))
    trial = copy.deepcopy(scroll)
    kept = []
    for p in out:
        try:
            apply_proposal(copy.deepcopy(trial), b.id, p)
            kept.append(p)
        except (ValueError, TypeError, KeyError):
            continue
    return kept


FREE_KINDS = ("wiki_bypass", "hand", "code_failing")


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
        if p.type == "demote" and p.data.get("script"):
            source = p.data["script"]
            if not isinstance(source, str) or len(source) > SCRIPT_LIMIT:
                errors.append(f"proposal {i} (demote): script must be Python text up to {SCRIPT_LIMIT} characters")
                continue
            try:
                ast.parse(source)
            except SyntaxError as e:
                errors.append(f"proposal {i} (demote): the script does not parse: line {e.lineno}: {e.msg}")
                continue
            p.data = {**p.data, "reviewed": False}       # replayed once the Council and the operator reviewed it
        elif p.type == "demote":
            p.replay = replay(list(p.data.get("chain") or []), roads.read_examples(repo_root, building_id, str(p.data["orc"])))
        out.append(p)
    return (out, []) if not errors else ([], errors)


def watch(repo_root: Path, scroll: ts.TownScroll, building_id: str, *, carts: Iterable[roads.Cart] = (),
          runs: Iterable[roads.HandlerRun] = (), sessions: list | None = None,
          runner: builders.Runner = builders.main_runner, budget_ok: bool = True,
          now: dt.datetime | None = None, max_attempts: int = MAX_ATTEMPTS) -> StewardReport:
    """Metrics → findings → (only if any, and within 🪙) proposals. Never raises."""
    m = collect(repo_root, scroll, building_id, carts=carts, runs=runs, sessions=sessions, now=now)
    report = StewardReport(building_id, m, findings(m, scroll))
    b = scroll.building(building_id)
    if b is None or not report.findings:
        return report
    known = wiki_loop(scroll, b, [f for f in report.findings if f.kind == "wiki_bypass"]) + free_moves(scroll, b, report.findings)
    report.proposals = known                              # free: no model needed to say these
    if known and all(f.kind in FREE_KINDS for f in report.findings):
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
            samples=_samples(repo_root, b), feedback=feedback,
            spend="; ".join(f"{o}: {m.run_count.get(o, 0)} runs, ${usd:.2f}" for o, usd in
                            sorted(m.run_spend.items(), key=lambda kv: -kv[1])) or "nothing recorded")
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
            for p in proposals:                          # the spend it saves: the signal (§2a)
                usd = weekly_spend(m, str(p.data.get("orc") or "")) if p.type == "demote" else 0.0
                if usd:
                    p.data = {**p.data, "saves": f"≈ ${usd:.2f}/week → " + ("less" if p.data.get("hybrid") else "$0")}
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
             runner: builders.Runner = builders.main_runner, budget_ok: bool = True,
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


def rule_spend(m: Metrics) -> list[dict]:
    """Per model handler, costliest first: its runs and spend in the window (the report's spend lines)."""
    return [{"orc": o, "runs": m.run_count.get(o, 0), "usd": usd}
            for o, usd in sorted(m.run_spend.items(), key=lambda kv: -kv[1])]


def save_report(repo_root: Path, report: StewardReport) -> Path:
    """`.orkcraft/steward/<building>.json` (git-ignored): the last report, for the UI."""
    path = repo_root / PROPOSALS_DIR / f"{report.building_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "ts": dt.datetime.now().isoformat(timespec="seconds"), "building": report.building_id,
        "findings": [asdict(f) for f in report.findings], "proposals": [p.to_dict() for p in report.proposals],
        "escalated": report.escalated, "attempts": report.attempts, "cost_usd": report.cost_usd,
        "error": report.error, "metrics": asdict(report.metrics), "rules": rule_spend(report.metrics),
    }
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return path


def load_report(repo_root: Path, building_id: str) -> dict | None:
    try:
        data = json.loads((repo_root / PROPOSALS_DIR / f"{building_id}.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None
