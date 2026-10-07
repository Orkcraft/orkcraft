"""The Recruiter: an operator's prompt becomes a validated road handler.

    result = recruit(request, scroll, "scrying")        # never raises; blocking (one Claude call per attempt)
    if result.ok:
        orc = apply(scroll, "scrying", result, repo_root)   # adds the handler and subscribes its roads

The Recruiter picks the cheapest kind that can do the job, in the order chain → script → steward
→ hybrid, and says why a cheaper kind was not enough (`why`). A `steward` handler is a road rule: its
words (`orders`) carried out by the building's steward on its own tool (docs/design/steward-listens.md);
a hybrid's script escalates to the steward too. An `agent` (its own tools) only for a pipeline of tools
the steward does not have. Like Mason it is one
`claude -p` call in an empty temp folder: it sees only the request, the building catalog (ids,
titles, the events each building emits) and the contract below — never the graph's content.
Its answer is untrusted text: it is used only when it passes `scroll.orc_problems` and a trial
`subscribe` of every road on a copy of the scroll; otherwise it gets the errors back, at most
`MAX_ATTEMPTS` rounds. A script's source is saved as a draft under `.orkcraft/scripts/`
and never runs until it is reviewed: the operator approves the preview and the Council passes it
(then it is marked reviewed; a changed file is held again — realm/roads.py `script_problem`).
"""
from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

import re

from orkcraft import scroll as ts
from orkcraft.realm import builders, pipes
from orkcraft.realm import harnesses as harnesses_

MAX_ATTEMPTS = 3
PROMPT_LIMIT = 2000
SCRIPT_LIMIT = 20_000

HARNESS_NAMES = {"main": "the main tool", **{h.id: h.title for h in harnesses_.REGISTRY.values()}}
RECRUITER = """You are the Recruiter of orkcraft, a terminal harness over a Markdown knowledge graph where
windows ("buildings") pass events to each other along roads. The operator wants a new handler orc
for the building {building_id} ({building_title}). A handler works on incoming roads: it keeps the
latest payload of each road and is re-run on every new event with all of them.

OPERATOR REQUEST:
{request}

BUILDINGS (id — title — events it emits):
{catalog}

Road events: on_selection_change (payload: a node id or a repo file path), on_task_completed (payload:
the final screen of a deployed orc's session as text). A road filter runs at the source; keys:
node_type [task|context|process], node_status [..], exclude_personal bool, path_prefix [..],
outcome [done|waiting|halted|unknown], match (a Python regex). Personal nodes never reach a model anyway.

KINDS — pick the FIRST that can do the job and explain in "why" what a cheaper kind could not do:
1. "chain": data, not code — a list of ops over records (one record per road that fired, fields:
   road, source, event, kind, value, title, id, path, text, type, status, outcome):
   {{"op":"filter","field":f,"cmp":"eq|ne|in|contains|matches","value":v}} {{"op":"pick","fields":[..]}}
   {{"op":"extract","field":f,"regex":r,"as":f2}} {{"op":"sort","by":f,"desc":bool}} {{"op":"limit","n":N}}
   {{"op":"count","as":f}} {{"op":"group","by":f}} {{"op":"template","md":"text with {{field}}"}} {{"op":"join","sep":s}}
   Field names are lowercase letters and _ only.
2. "script": a small Python script (stdin: JSON list of records, stdout: Markdown); give its source in
   "script_source". It will not run until the operator reviews it.
3. "steward": a road rule — the building's steward ({steward}) reads every cart with the building's purpose
   in mind and does what "orders" (the rule, in plain words) say. No "harness": it thinks on the steward's
   tool, at the steward's tier. This is the kind for anything that needs judgement.
4. "hybrid": a script that does the routine and exits 3 for the carts it cannot decide; those go to the
   steward with "orders". Give "script_source" and "orders", no "harness".
5. "agent" — ONLY when the operator asks for a pipeline of tools the steward does not have: "orders" and a
   "harness" scheme of 2+ steps {{"role":"run|plan|write|review","harness":"{harness_choice}"}}, e.g.
   [{{"role":"write","harness":"agy"}},{{"role":"review","harness":"claude"}}] ({harness_names}; only these are here).
   Each step takes a "tier", the lightest that will do: "laborer" (haiku / gemini flash low), "warrior"
   (sonnet / gemini flash high), "elder" (opus / gemini pro). Say in "why" why the steward will not do.
Optional "run": {{"quiet_s": 0-3600, "restart_on_new": bool}} (agents default to 30 s of quiet).
{feedback}
Answer with ONE JSON object and nothing else:
{{"name": "<an orc name, max 32 chars>", "role": "<what it does, short>", "kind": "chain|script|steward|hybrid|agent",
  "why": "<one or two sentences>", "orders": "<the rule in words, or the agent's prompt, or empty>", "harness": [..], "chain": [..],
  "script_source": "<python or empty>", "run": {{..}},
  "roads": [{{"from": "<building id>", "event": "<road event>", "filter": {{..}}}}]}}
Use 1-4 roads, never from {building_id} itself."""


@dataclass
class RecruitAttempt:
    answer: str = ""
    errors: list[str] = field(default_factory=list)


@dataclass
class RecruitResult:
    orc: dict | None                 # the handler as in the scroll (without id), roads separately
    roads: list[dict] = field(default_factory=list)
    script_source: str = ""
    attempts: list[RecruitAttempt] = field(default_factory=list)
    cost_usd: float | None = None
    error: str = ""

    @property
    def ok(self) -> bool:
        return self.orc is not None


def catalog(scroll: ts.TownScroll, building_id: str) -> str:
    lines = []
    for b in scroll.buildings:
        if b.demolished or b.id == building_id:
            continue
        events = pipes.emits(b.id, bool(b.garrison.members))
        lines.append(f"- {b.id} — {b.title} — {', '.join(events) or 'nothing'}")
    return "\n".join(lines)


# Roads v2: a road with a rule. A rule that needs no judgement is a chain or a script.
JUDGEMENT = re.compile(r"\b(summar|explain|classif|categori[sz]|decide|judge|assess|review|rewrite|translat|"
                       r"tone|sentiment|intent|suggest|recommend|answer|reply|draft|write|понят|кратк|резюм|"
                       r"классифиц|оцен|реши|перевед|ответ|напиш|объясн|предлож)", re.I)
ROAD_RULE = """
THESE ARE ROADS WITH A RULE: the handler works on exactly these roads — {roads} — give exactly these
(a filter is allowed). If the rule is deterministic (filter, pick, reformat, count, extract, route by a
pattern) it MUST be a chain or a script, never the steward or an agent."""


def _wanted(road) -> list[tuple[str, str]]:
    """(source, event) of a road with a rule: one tuple or a list of them."""
    if not road:
        return []
    return [tuple(road)] if isinstance(road, tuple) and len(road) == 2 and isinstance(road[0], str) else \
        [tuple(r) for r in road]


def needs_judgement(rule: str) -> bool:
    """Whether a road's rule asks for judgement a chain or a script cannot have."""
    return bool(JUDGEMENT.search(rule))


def _road_problems(orc: dict | None, roads: list[dict], road, rule: str) -> list[str]:
    wanted = set(_wanted(road))
    problems = []
    if {(r.get("from"), r.get("event")) for r in roads} != wanted or len(roads) != len(wanted):
        problems.append("give exactly these roads: " + "; ".join(f"from {s} on {e}" for s, e in sorted(wanted)))
    if orc and orc.get("kind") in ("agent", "hybrid", "steward") and not needs_judgement(rule):
        problems.append("the rule is deterministic — make it a chain or a script, not a model")
    return problems


def _feedback(attempts: list[RecruitAttempt]) -> str:
    if not attempts:
        return ""
    lines = "\n".join(f"- {e}" for e in attempts[-1].errors[:12])
    return f"\nYOUR PREVIOUS ANSWER WAS REJECTED. Fix every problem:\n{lines}\n"


def _script_path(orc_id: str, building_id: str) -> str:
    return f".orkcraft/scripts/{building_id}-{orc_id}"[:60].replace("_", "-") + ".py"


def stewards_own(harness: list | None, b: ts.BuildingSpec | None) -> bool:
    """Whether an agent's tools are nothing its building's steward lacks: one step, on the steward's own tool
    (`main` read as the machine's main tool) — then it is the steward's work, not an agent's."""
    from orkcraft.realm import roads, steward
    steps = [s for s in harness or [] if isinstance(s, dict)]
    if len(steps) != 1:
        return False
    return roads.resolve(str(steps[0].get("harness") or "")) == roads.resolve(steward.harness_for(b))


def check(answer: dict, scroll: ts.TownScroll, building_id: str) -> tuple[dict | None, list[dict], str, list[str]]:
    """(orc, roads, script source, problems) — the trial runs on a copy of the scroll."""
    if not isinstance(answer, dict):
        return None, [], "", ["the answer is not a JSON object"]
    problems: list[str] = []
    kind = answer.get("kind")
    source = answer.get("script_source") or ""
    if not isinstance(source, str) or len(source) > SCRIPT_LIMIT:
        problems.append(f"script_source must be text up to {SCRIPT_LIMIT} characters")
        source = ""
    if kind in ("script", "hybrid") and not source.strip():
        problems.append(f"a {kind} needs script_source")
    if kind in ("chain", "agent", "steward") and source.strip():
        problems.append(f"a {kind} has no script_source")
    if kind in ("steward", "hybrid") and answer.get("harness"):
        problems.append(f"a {kind} thinks on the steward's tool — give no harness")
    if kind == "agent" and stewards_own(answer.get("harness"), scroll.building(building_id)):
        problems.append("one step on the steward's own tool is the steward's work — make it a steward rule "
                        "(an agent only for a pipeline of tools the steward does not have)")
    if not str(answer.get("why") or "").strip():
        problems.append("why is required: say what a cheaper kind could not do")
    roads = answer.get("roads")
    if not isinstance(roads, list) or not 1 <= len(roads) <= 4:
        problems.append("give 1-4 roads")
        roads = []
    trial = copy.deepcopy(scroll)
    orc = None
    try:
        spec = trial.building(building_id)
        if spec is None:
            raise ValueError(f"unknown building {building_id!r}")
        kw = {k: answer[k] for k in ("role", "orders", "harness", "chain", "run", "why") if answer.get(k) not in (None, "", [], {})}
        if kind in ("steward", "hybrid"):
            kw["harness"] = []                       # the steward's tool, not one of its own
        if kind in ("script", "hybrid"):
            kw["script"] = {"path": _script_path(ts._orc_id(str(answer.get("name") or "orc")), building_id),
                            "sha256": hashlib.sha256(source.encode()).hexdigest(), "reviewed": False}
        added = ts.add_handler(trial, building_id, str(answer.get("name") or ""), kind=str(kind), **kw)
        orc = added.to_dict()
        for r in roads:
            if not isinstance(r, dict):
                problems.append("each road is an object {from, event, filter}")
                continue
            try:
                ts.subscribe(trial, building_id, str(r.get("from")), str(r.get("event")),
                             r.get("filter") or None, handler=added.id)
            except ValueError as e:
                problems.append(f"road from {r.get('from')!r}: {e}")
    except (ValueError, TypeError) as e:
        problems.append(str(e))
    if problems:
        return None, [], "", problems
    return orc, [{"from": r["from"], "event": r["event"], **({"filter": r["filter"]} if r.get("filter") else {})}
                 for r in roads], source, []


def _steward_words(b: ts.BuildingSpec) -> str:
    """Who the steward is, for the prompt: its name, its tool and what the building is for."""
    from orkcraft.realm import steward
    stew = b.garrison.steward
    if stew is None:
        return "none yet: the machine's main tool stands in"
    tool = HARNESS_NAMES.get(steward.harness_for(b) or "main", steward.harness_for(b))
    purpose = " ".join(x for x in (stew.role.strip(), stew.orders.strip()[:300]) if x)
    return f"{stew.name}, on {tool}" + (f"; the building is for: {purpose}" if purpose else "")


def recruit(request: str, scroll: ts.TownScroll, building_id: str, runner: builders.Runner = builders.main_runner,
            max_attempts: int = MAX_ATTEMPTS, road=None, harnesses: tuple[str, ...] = ("main",)) -> RecruitResult:
    """Ask the Recruiter until its handler passes the contract or the attempts run out. Never raises.
    `road` (source, event): a road with a rule — exactly that road, and no agent for a rule that
    needs no judgement. `harnesses`: the CLIs this machine runs, the only ones it may pick."""
    rule = request.strip()[:PROMPT_LIMIT]
    request = rule + (ROAD_RULE.format(roads="; ".join(f'{{"from": "{s}", "event": "{e}"}}' for s, e in _wanted(road)))
                      if road else "")
    spec = scroll.building(building_id)
    if spec is None:
        return RecruitResult(None, error=f"unknown building {building_id!r}")
    attempts: list[RecruitAttempt] = []
    total: float | None = None
    for _ in range(max_attempts):
        prompt = RECRUITER.format(request=request, building_id=building_id, building_title=spec.title,
                                  catalog=catalog(scroll, building_id), feedback=_feedback(attempts),
                                  harness_names=" / ".join(HARNESS_NAMES.get(h, h) for h in harnesses),
                                  harness_choice="|".join(harnesses), steward=_steward_words(spec))
        try:
            text, cost = runner(prompt)
        except RuntimeError as e:
            return RecruitResult(None, attempts=attempts, cost_usd=total, error=str(e))
        if cost is not None:
            total = (total or 0.0) + cost
        attempt = RecruitAttempt(answer=text)
        attempts.append(attempt)
        answer = builders.extract_json(text)
        orc, roads, source, problems = check(answer, scroll, building_id) if answer else (None, [], "", ["no JSON object in the answer"])
        if not problems and road is not None:
            problems = _road_problems(orc, roads, road, rule)
            if problems:
                orc, roads, source = None, [], ""
        if not problems:
            return RecruitResult(orc, roads, source, attempts, total)
        attempt.errors = problems
    return RecruitResult(None, attempts=attempts, cost_usd=total)


def apply(scroll: ts.TownScroll, building_id: str, result: RecruitResult, repo_root: Path) -> ts.OrcSpec:
    """Add the recruited handler and its roads to the real scroll (all or nothing) and save a
    script draft. Raises ValueError when the scroll changed and the handler no longer fits."""
    if result.orc is None:
        raise ValueError("nothing to apply")
    trial = copy.deepcopy(scroll)
    fields = {k: v for k, v in result.orc.items() if k not in ("id", "name", "status", "avatar", "trigger", "kind")}
    orc = ts.add_handler(trial, building_id, result.orc["name"], kind=result.orc.get("kind", "agent"), **fields)
    if orc.script is not None:          # the id may differ from the trial's: keep path and hash in step
        orc.script = {**orc.script, "path": _script_path(orc.id, building_id),
                      "sha256": hashlib.sha256(result.script_source.encode()).hexdigest(), "reviewed": False}
        orc.status = "draft"
    for r in result.roads:
        ts.subscribe(trial, building_id, r["from"], r["event"], r.get("filter"), handler=orc.id)
    if orc.script is not None:
        path = repo_root / orc.script["path"]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(result.script_source, encoding="utf-8")
    target, source = scroll.building(building_id), trial.building(building_id)
    target.garrison, target.roads = source.garrison, source.roads
    return target.garrison.handler(orc.id)
