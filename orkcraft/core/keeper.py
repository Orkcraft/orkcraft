"""The keeper of a building (docs/design/building-views.md §2): the person says in plain words what the
building should do, and its keeper — the building's steward — writes it in the building's own language.
Nobody edits a building's rules or settings by hand.

    proposal = keeper.ask(repo, spec, scroll, building_id, "send bugs to the forge", runner=…)
    keeper.apply(town, building_id, proposal, request)     # checked again, saved, a checkpoint (Z takes it back)

What a keeper may change is its type's **subject**: the building's whole `config` (every type), or a part
of it a type registers with `register` (the Signpost's `rules`, the Workshop's script and schedule here;
other types add theirs). A part may live outside the spec (the Workshop's script is a file): the subject
then loads it, checks it and keeps it when the proposal is taken, in the same checkpoint. Every
proposal is checked like any spec (`masonry.validate_spec`, so `catalog.validate` and the type's own
checks); a rejected answer goes back to the model with its problems. A request may come with a
selection (a part of a document in Lake): the keeper then answers about it, and may still propose a change.

No face: the model call is `runners.KEEPER_RUNNER` (tests and the demo put a fake there), and the face
runs `ask` in its own thread and shows what comes back.
"""
from __future__ import annotations

import copy
import difflib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from orkcraft import scroll as ts
from orkcraft.core import bus
from orkcraft.core.town import Town
from orkcraft.realm import builders, catalog, evolution, masonry, signpost, workshop

MAX_ATTEMPTS = 3
SELECTION_LIMIT = 20_000


@dataclass(frozen=True)
class Subject:
    """What a type's keeper writes: `read` takes it out of a spec, `write` puts a new one in (a new spec);
    `shape` says what is wrong with a value's form before the spec is checked; `lines` shows it for the diff.
    A part kept outside the spec (a file): `load` reads the whole value in place of `read`, `problems` checks
    it against the spec, `keep` saves it when the proposal is taken (before the checkpoint)."""
    kind: str
    what: str
    language: Callable[[dict], str]
    read: Callable[[dict], Any]
    write: Callable[[dict, Any], dict]
    shape: Callable[[Any], str | None]
    lines: Callable[[Any], list[str]]
    load: Callable[[Path, str, dict], Any] | None = None
    problems: Callable[[dict, Any], list[str]] | None = None
    keep: Callable[[Path, str, dict, Any], None] | None = None

    def now(self, repo_root: Path, building_id: str, spec: dict) -> Any:
        """What it is now: from the spec, and from its files when it keeps a part outside it."""
        return self.load(repo_root, building_id, spec) if self.load else self.read(spec)


def _config_lines(config: Any) -> list[str]:
    out: list[str] = []
    for key in sorted(config or {}):
        value = config[key]
        if isinstance(value, list):
            out.append(f"{key}:")
            out += [f"  - {x}" for x in value]
        else:
            out.append(f"{key}: {json.dumps(value, ensure_ascii=False)}")
    return out


def _config_language(spec: dict) -> str:
    t = catalog.type_of(spec)
    help_ = catalog.CONFIG_HELP.get(t.id, {})
    lines = [f"{k} ({catalog._param_text(p)}): {help_.get(k, '')}".rstrip(": ") for k, p in t.config.items()]
    return "\n".join(lines) or "this type takes no settings"


CONFIG = Subject(
    "config", "the building's settings: a JSON object of its config keys (the whole object, as it should be)",
    _config_language,
    read=lambda spec: dict(spec.get("config") or {}),
    write=lambda spec, value: {**spec, "config": dict(value)},
    shape=lambda value: None if isinstance(value, dict) else "value must be a JSON object of settings",
    lines=_config_lines,
)

RULES = Subject(
    "rules", "the Signpost's rules: a JSON list of strings, one rule per string, the first that matches wins",
    lambda spec: (signpost.__doc__ or "").split("One rule per line", 1)[-1].strip(),
    read=lambda spec: [str(r) for r in (spec.get("config") or {}).get("rules") or []],
    write=lambda spec, value: {**spec, "config": {**(spec.get("config") or {}), "rules": [str(x).strip() for x in value]}},
    shape=lambda value: None if isinstance(value, list) and all(isinstance(x, str) for x in value)
    else "value must be a JSON list of rule strings",
    lines=lambda value: [str(x) for x in value or []],
)

SCRIPT_LIMIT = 64 * 1024


def _ws_runtime(spec: dict) -> str:
    return str((spec.get("config") or {}).get("runtime") or "python")


def _ws_read(spec: dict) -> dict:
    return {"schedule": str((spec.get("config") or {}).get("schedule") or "").strip(), "script": ""}


def _ws_load(repo_root: Path, building_id: str, spec: dict) -> dict:
    return {**_ws_read(spec), "script": workshop.load_script(repo_root, building_id, _ws_runtime(spec))}


def _ws_write(spec: dict, value: dict) -> dict:
    config = {k: v for k, v in (spec.get("config") or {}).items() if k != "schedule"}
    if str(value.get("schedule") or "").strip():
        config["schedule"] = str(value["schedule"]).strip()
    return {**spec, "config": config}


def _ws_shape(value: Any) -> str | None:
    if not isinstance(value, dict) or set(value) != {"schedule", "script"}:
        return 'value must be a JSON object {"schedule": "...", "script": "..."}'
    if not isinstance(value["schedule"], str) or not isinstance(value["script"], str):
        return 'schedule and script must be strings (schedule "" runs it only on carts)'
    if len(value["script"]) > SCRIPT_LIMIT:
        return f"the script is longer than {SCRIPT_LIMIT} characters"
    return None


def _ws_problems(spec: dict, value: dict) -> list[str]:
    why = workshop.check_syntax(value["script"], _ws_runtime(spec))
    return [f"script: {why}"] if why else []


def _ws_keep(repo_root: Path, building_id: str, spec: dict, value: dict) -> None:
    runtime = _ws_runtime(spec)
    if value["script"] != workshop.load_script(repo_root, building_id, runtime):
        workshop.save_script(repo_root, building_id, runtime, value["script"])


def _ws_language(spec: dict) -> str:
    runtime = _ws_runtime(spec)
    contract = (workshop.__doc__ or "").split("The contract", 1)[-1].split("Scripts run with", 1)[0].strip()
    name = workshop.RUNTIMES.get(runtime, workshop.RUNTIMES["python"])[1]
    return (f"The script is {runtime} ({name}), run with no shell in the project's folder. The contract {contract}\n"
            f"schedule: {catalog.CONFIG_HELP['workshop']['schedule']}; \"\" runs it only on carts.\n"
            "The runtime, the layout and the steward prompt stay as they are.")


def _ws_lines(value: Any) -> list[str]:
    value = value or {}
    return [f"schedule: {value.get('schedule') or 'none'}", "script:",
            *[f"  {line}" for line in str(value.get("script") or "").splitlines()]]


SCRIPT = Subject(
    "script and schedule", "the Workshop's script and its schedule: a JSON object "
    '{"schedule": "<when it runs on its own, or empty>", "script": "<the whole script, as it should be>"}',
    _ws_language, read=_ws_read, write=_ws_write, shape=_ws_shape, lines=_ws_lines,
    load=_ws_load, problems=_ws_problems, keep=_ws_keep,
)

SUBJECTS: dict[str, Subject] = {"signpost": RULES, "workshop": SCRIPT}


def register(type_id: str, subject: Subject) -> None:
    """A type's keeper writes `subject` instead of its whole config (its track calls this at import)."""
    SUBJECTS[type_id] = subject


def subject_of(spec: dict | None) -> Subject:
    return SUBJECTS.get(catalog.type_of(spec).id, CONFIG)


# -- what the keeper proposes ---------------------------------------------------------------------------

@dataclass
class Proposal:
    building_id: str
    kind: str = ""
    before: Any = None
    after: Any = None              # None: nothing to change (an answer only)
    why: str = ""
    answer: str = ""
    cost_usd: float | None = None
    attempts: int = 0
    error: str = ""
    errors: list[str] = field(default_factory=list)

    @property
    def changes(self) -> bool:
        return self.after is not None and self.after != self.before

    def diff(self, subject: Subject) -> list[list[str]]:
        """[op, line] with op "+", "-" or " ": what changes, line by line."""
        a, b = subject.lines(self.before), subject.lines(self.after if self.after is not None else self.before)
        out: list[list[str]] = []
        for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(a=a, b=b, autojunk=False).get_opcodes():
            if tag == "equal":
                out += [[" ", x] for x in a[i1:i2]]
                continue
            out += [["-", x] for x in a[i1:i2]]
            out += [["+", x] for x in b[j1:j2]]
        return out


def selection_of(value: Any) -> dict | None:
    """A selection from Lake as plain data: {text, path, title, lines}; None when there is none."""
    if isinstance(value, str):
        value = {"text": value}
    if not isinstance(value, dict):
        return None
    text = value.get("text")
    if not isinstance(text, str) or not text.strip():
        return None
    out: dict[str, Any] = {"text": text[:SELECTION_LIMIT]}
    for key in ("path", "title"):
        if isinstance(value.get(key), str) and value[key].strip():
            out[key] = value[key].strip()[:500]
    lines = value.get("lines")
    if isinstance(lines, list) and len(lines) == 2 and all(isinstance(n, int) and not isinstance(n, bool) for n in lines):
        out["lines"] = [int(n) for n in lines]
    return out


KEEP = """You are {keeper}, the keeper of the {title} building in orkcraft: {summary}.
The operator never edits the building's rules or settings by hand. They say in plain words what they want,
and you write it in the building's own language.

WHAT THE OPERATOR WANTS:
{request}
{selection}
WHAT YOU WRITE: {what}

ITS LANGUAGE:
{language}

ITS ROADS:
{roads}

WHAT IT IS NOW:
{current}
{feedback}
Answer with ONE JSON object and nothing else:
{{"value": <the whole new value, or null when nothing should change>,
  "why": "<one sentence for the operator: what changes>",
  "answer": "<what you say to the operator; on a selection, your answer about it>"}}"""


def _roads(scroll, building_id: str) -> str:
    lines = [f"in: from {r.source} on {r.event}{f', filter {json.dumps(r.filter)}' if r.filter else ''}"
             for r in ts.incoming(scroll, building_id)]
    lines += [f"out: to {target.id} on {r.event}{f', filter {json.dumps(r.filter)}' if r.filter else ''}"
              for target, r in ts.outgoing(scroll, building_id)]
    return "\n".join(lines) or "none"


def _selection_text(sel: dict | None) -> str:
    if sel is None:
        return ""
    where = sel.get("path") or sel.get("title") or "a document"
    if sel.get("lines"):
        where += f", lines {sel['lines'][0]}–{sel['lines'][1]}"
    return f"\nTHE OPERATOR SELECTED THIS (in {where}) AND ASKS ABOUT IT:\n<<<\n{sel['text']}\n>>>\n"


def check(answer: Any, spec: dict, subject: Subject, repo_root: Path,
          existing_ids: frozenset[str] | set[str]) -> tuple[Any, list[str]]:
    """(the new value or None, []) or (None, the problems) of a model's answer."""
    if not isinstance(answer, dict) or "value" not in answer:
        return None, ['answer with {"value": ..., "why": "...", "answer": "..."}']
    value = answer["value"]
    if value is None:
        if not str(answer.get("answer") or "").strip():
            return None, ["with no value, say why in answer"]
        return None, []
    if not str(answer.get("why") or "").strip():
        return None, ["why is required"]
    wrong = subject.shape(value)
    if wrong:
        return None, [wrong]
    if subject.problems and (own := subject.problems(spec, value)):
        return None, own
    problems = masonry.validate_spec(subject.write(copy.deepcopy(spec), value), repo_root, existing_ids)
    return (value, []) if not problems else (None, problems)


def ask(repo_root: Path, spec: dict, scroll, building_id: str, request: str, *, selection: Any = None,
        runner: builders.Runner = builders.main_runner, budget_ok: bool = True,
        existing_ids: frozenset[str] | set[str] = frozenset(), max_attempts: int = MAX_ATTEMPTS,
        looker: str = "") -> Proposal:
    """The person's words → the keeper's proposal (checked against the type's contract; a rejected answer
    goes back with its problems). Never raises. `looker`: the building whose steward speaks, when it is not the
    building's own (landscape has no ork: core/wakes.py)."""
    subject = subject_of(spec)
    p = Proposal(building_id, subject.kind, before=subject.now(repo_root, building_id, spec))
    if not budget_ok:
        p.error = "the budget is spent — the keeper calls a model"
        return p
    b = scroll.building(building_id) if scroll is not None else None
    t = catalog.type_of(spec)
    who = scroll.building(looker) if scroll is not None and looker else b
    keeper = who.garrison.steward.name if who is not None and who.garrison.steward else "the keeper"
    sel = selection_of(selection)
    feedback = ""
    for _ in range(max_attempts):
        prompt = KEEP.format(
            keeper=keeper, title=b.title if b is not None else building_id, summary=f"{t.title} — {t.summary}",
            request=request.strip()[:2000], selection=_selection_text(sel), what=subject.what,
            language=subject.language(spec), roads=_roads(scroll, building_id) if scroll is not None else "none",
            current=json.dumps(p.before, ensure_ascii=False, indent=1), feedback=feedback)
        p.attempts += 1
        try:
            text, cost = runner(prompt)
        except RuntimeError as e:
            p.error = str(e)
            return p
        if cost is not None:
            p.cost_usd = (p.cost_usd or 0.0) + cost
        answer = builders.extract_json(text)
        value, errors = check(answer, spec, subject, repo_root, existing_ids)
        if not errors:
            p.after, p.errors = value, []
            p.why = str(answer.get("why") or "").strip()[:500]
            p.answer = str(answer.get("answer") or "").strip()[:8000]
            return p
        p.errors = errors
        feedback = "\nYOUR PREVIOUS ANSWER WAS REJECTED. Fix every problem:\n" + "\n".join(f"- {e}" for e in errors[:12])
    p.error = "; ".join(p.errors[:3]) or "no answer"
    return p


def apply(town: Town, building_id: str, p: Proposal, request: str = "") -> list[str]:
    """The person takes the keeper's proposal: checked again on the spec as it stands now, saved, a
    checkpoint `keeper(<id>)` (Revert takes it back), a line in the chronicle and the ledger. [] or the problems."""
    spec = town.custom_specs.get(building_id)
    if spec is None:
        return ["its keeper keeps no settings here"]
    subject = subject_of(spec)
    if subject.kind != p.kind or p.after is None:
        return ["nothing to apply"]
    wrong = subject.shape(p.after)
    if wrong:
        return [wrong]
    if subject.problems and (own := subject.problems(spec, p.after)):
        return own
    new = subject.write(copy.deepcopy(spec), p.after)
    others = set(town.custom_specs) - {building_id}
    problems = masonry.save_spec(town.repo_root, new, existing_ids=others)
    if problems:
        return problems
    if subject.keep:
        try:
            subject.keep(town.repo_root, building_id, new, p.after)
        except OSError as e:
            return [f"could not keep its {p.kind}: {e}"]
    town.custom_specs[building_id] = new
    town.publish(bus.SPEC, building=building_id, spec=new)
    why = p.why or request or f"new {p.kind}"
    sha = town.checkpoint("keeper", building_id, f"{p.kind}: {why}"[:60])
    town.record(building_id, "proposal_applied", what=f"the keeper's new {p.kind}: {why}")
    try:
        evolution.record(town.repo_root, evolution.Change(building_id, "set_config", "steward", f"new {p.kind}",
                                                          why[:200], by="you", sha=sha or ""))
    except OSError:
        pass
    return []
