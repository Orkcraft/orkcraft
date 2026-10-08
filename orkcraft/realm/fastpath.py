"""The Council's Fast Path: a quick review of every new building, agent and road.

Presets skip it — they are code that was reviewed once. Everything the operator or a model makes
from scratch goes past five councillors, each with a fixed duty:

    👑 Chief     budget          model calls per event, re-runs, a reason for not using a cheaper kind
    🧱 Mason     schemas         the spec, the orc and the filter against their JSON Schemas; scripts parse
    🎨 Artisan   the TUI         titles, icons, keys, hut lines that fit the screen
    🛡 Warder    bash security   commands and scripts: sudo, curl | sh, rm -rf, secrets, the network
    ⛏ Peon      worktrees,      shared working trees, merges without tests, skipped permissions,
                 permissions,    scripts outside their folder
                 cache

Rules come first: they are free, instant and their findings are facts. A `block` stops the build
and says why. After the rules, when a light model is allowed (`fast_model`, haiku by default), the
five duties go to it in one call; its objections are opinions — the operator may approve anyway.
A model that cannot be reached never blocks: the review falls back to the rules.

Every review is appended to `.orkcraft/council/reviews.jsonl`; the settings live in
`.orkcraft/council/settings.json` (`fast_llm`, `fast_model`, `weekly_model`, `weekly_at`, `optimize_at`,
and the Elders' `elders_per_night` / `elders_context`).
"""
from __future__ import annotations

import ast
import datetime as dt
import functools
import json
import os
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable

from orkcraft.realm import audit

COUNCIL_DIR = Path(".orkcraft") / "council"
SETTINGS = {"fast_llm": True, "fast_model": "haiku", "weekly_model": "opus", "weekly_at": "weekly sun 05:00",
            "optimize_at": "daily 06:20",       # the local proposal (stage 8): in the operator's morning window
            "elders_per_night": 40, "elders_context": 14}    # the Elders (realm/elders.py): questions, screen lines
SUBJECT_LIMIT = 6000

# (id, icon, name, duty, the councillor's fixed prompt)
ROLES = (
    ("chief", "👑", "Chief", "budget",
     "You guard the budget. Object when a model is called where a chain or a script would do, when a "
     "model wakes on every small event (selections, every cart) or re-runs with no quiet time, and "
     "when many agents can run at once."),
    ("mason", "🧱", "Mason", "schemas",
     "You guard the data contracts. Object when fields, events or filters do not fit together, when an "
     "output another building reads has no clear shape, or when a script's input or output is vague."),
    ("artisan", "🎨", "Artisan", "TUI",
     "You guard the terminal screen. Object to long titles and labels, more than four panes or actions, "
     "unclear hut lines, and anything that will not read well in an 80-column terminal."),
    ("warder", "🛡", "Warder", "bash security",
     "You guard the machine. Object to shell commands that delete, escalate (sudo), pipe the network into "
     "a shell, interpolate untrusted text into a command, write outside the project, or hold a secret."),
    ("peon", "⛏", "Peon", "worktrees, permissions, cache",
     "You guard the workshop. Object when agents share one working tree, merge without tests, skip "
     "permission prompts, or recompute what could be cached between runs."),
)
ROLE_IDS = tuple(r[0] for r in ROLES)

PROMPT = """You are the Council of orkcraft, a terminal harness where windows ("buildings") pass events
along roads to scripts and agents. Review this new {kind} quickly. Each councillor answers only for its duty:

{duties}

THE NEW {kind_upper}:
{subject}

Rules already passed: {rules}

Answer with ONE JSON object and nothing else:
{{"chief": {{"ok": true, "note": ""}}, "mason": {{...}}, "artisan": {{...}}, "warder": {{...}}, "peon": {{...}}}}
"ok" is false only for a real problem; "note" is one short sentence (max 120 chars), empty when ok."""

Runner = Callable[[str], tuple[str, float | None]]

# -- the Warder's patterns: (regex, severity, why) --------------------------------------------------
_DANGER = [
    (re.compile(r"\bsudo\b|\bdoas\b"), "block", "escalates privileges (sudo)"),
    (re.compile(r"\b(curl|wget)\b[^|;\n]*\|\s*(ba|z|da)?sh\b"), "block", "pipes the network into a shell"),
    (re.compile(r"\brm\s+-[a-z]*r[a-z]*f?[a-z]*\s+(/|~|\$HOME|\*)(\s|$|/\*?\s|/\*?$)"), "block", "deletes recursively from /, ~ or *"),
    (re.compile(r"\bmkfs\b|\bdd\s+if=|>\s*/dev/(sd|nvme|disk)"), "block", "writes to a disk device"),
    (re.compile(r"(^|[\s'\"=])(/etc/|/usr/|/bin/|/System/|~/\.ssh|\$HOME/\.ssh)"), "block", "touches system files or ~/.ssh"),
    (re.compile(r"\bchmod\s+(-R\s+)?777\b"), "warn", "opens files to everyone (chmod 777)"),
    (re.compile(r"\beval\b|\bexec\s*\(|os\.system\(|shell\s*=\s*True"), "warn", "runs text as code (eval / shell=True)"),
    (re.compile(r"\$\(|`"), "warn", "substitutes a command inside a command"),
    (re.compile(r"\b(curl|wget|nc|ncat|ssh|scp)\b|requests\.|urllib|http\.client|socket\."), "warn", "goes to the network"),
]
# prompts: what makes a prompt unsafe — (regex, severity, why)
_PROMPT_RISKS = [
    (re.compile(r"(follow|obey|execute|do|run)\b[^.\n]{0,40}\b(instructions?|commands?|whatever)\b[^.\n]{0,40}\b"
                r"(in|from|inside)\b[^.\n]{0,30}\b(the )?(input|cart|mail|e-?mail|message|payload|page|issue|pr)",
                re.I), "warn", "obeys instructions found in its input — a prompt injection waits there"),
    (re.compile(r"\b(send|post|upload|forward|e-?mail|curl|push)\b[^.\n]{0,60}\b(https?://|to (an? )?(external|outside|remote))",
                re.I), "warn", "sends data out of the camp"),
    (re.compile(r"(\.env\b|~/\.ssh|id_rsa|\.aws/credentials|keychain|password ?store)", re.I), "block",
     "reads secret files"),
    (re.compile(r"\b(personal|private)\b[^.\n]{0,30}\b(node|notes?|context|journal)", re.I), "warn",
     "reaches for personal context — it must never leave the graph"),
    (re.compile(r"\b(rm -rf|git push( --force| -f)?|force[- ]push|drop table|delete (all|every)|deploy to prod)",
                re.I), "warn", "asks for a destructive or outward action"),
    (re.compile(r"\b(ignore|disregard) (all |any )?(previous|prior|above) (instructions|rules)", re.I), "block",
     "tells the model to ignore its rules"),
]
_PROMPT_KEYS = ("steward_prompt", "orders", "goal")
_PERMISSION_SKIP = re.compile(r"dangerously-skip-permissions|bypassPermissions|--yolo\b|permission[_-]?mode\W+bypass", re.I)
_COMMAND_KEYS = ("cmd", "command", "test_cmd", "script", "run", "exec")


@dataclass
class Note:
    role: str
    severity: str        # block | warn | object (the model's) | ok
    text: str = ""


@dataclass
class Subject:
    kind: str            # building | agent | road
    id: str
    data: dict = field(default_factory=dict)
    script: str = ""     # a script's source, when there is one

    @property
    def label(self) -> str:
        return f"{self.kind} {self.id}"


@dataclass
class Verdict:
    subject: Subject
    notes: list[Note] = field(default_factory=list)
    model: str = ""      # the light model that answered, "" for rules only
    cost_usd: float | None = None
    error: str = ""      # why the model did not answer

    @property
    def blocked(self) -> bool:
        return any(n.severity == "block" for n in self.notes)

    @property
    def objections(self) -> list[Note]:
        return [n for n in self.notes if n.severity == "object"]

    @property
    def warnings(self) -> list[Note]:
        return [n for n in self.notes if n.severity == "warn"]

    @property
    def clean(self) -> bool:
        return not any(n.severity != "ok" for n in self.notes)

    def of(self, role: str) -> list[Note]:
        return [n for n in self.notes if n.role == role and n.severity != "ok"]

    def reasons(self) -> list[str]:
        icons = {r[0]: f"{r[1]} {r[2]}" for r in ROLES}
        return [f"{icons.get(n.role, n.role)}: {n.text}" for n in self.notes if n.severity == "block"]


# -- settings and the light model -----------------------------------------------------------------

def settings(repo_root: Path) -> dict:
    try:
        data = json.loads((repo_root / COUNCIL_DIR / "settings.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    out = {**SETTINGS, **{k: v for k, v in data.items() if k in SETTINGS}} if isinstance(data, dict) else dict(SETTINGS)
    if os.environ.get("ORKCRAFT_COUNCIL_LLM", "").strip() in ("0", "false", "no", "off"):
        out["fast_llm"] = False
    return out


def save_settings(repo_root: Path, values: dict) -> dict:
    """Keep only known keys; the environment's ORKCRAFT_COUNCIL_LLM still wins when reading."""
    path = repo_root / COUNCIL_DIR / "settings.json"
    data = {**settings(repo_root), **{k: v for k, v in values.items() if k in SETTINGS}}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    return data


def light_runner(repo_root: Path) -> Runner | None:
    """The Fast Path's model call (the main tool on `fast_model`, a light one), or None when it is switched off."""
    s = settings(repo_root)
    if not s.get("fast_llm"):
        return None
    from orkcraft.realm import builders
    return functools.partial(builders.main_runner, model=str(s.get("fast_model") or "haiku"))


# -- the rules ------------------------------------------------------------------------------------

def _commands(spec: dict) -> list[tuple[str, str]]:
    """(where, command) of every shell command a building spec will run."""
    cfg = spec.get("config") or {}
    out = []
    for step in cfg.get("steps") or [] if isinstance(cfg.get("steps"), list) else []:
        if isinstance(step, str) and step.startswith("script:"):
            out.append(("mill step", step[7:].strip()))
    for key, value in cfg.items():
        if key in _COMMAND_KEYS and isinstance(value, str) and value.strip():
            out.append((key, value.strip()))
    return out


def _scan(where: str, text: str) -> list[Note]:
    notes, seen = [], set()
    for rx, severity, why in _DANGER:
        if rx.search(text) and why not in seen:
            seen.add(why)
            notes.append(Note("warder", severity, f"{where} {why}: {text.strip().splitlines()[0][:60] if text.strip() else ''}"))
    if audit._TOKENISH.search(text):
        notes.append(Note("warder", "block", f"{where} holds a secret — keep it in an environment variable"))
    return notes


def _scan_prompt(where: str, text: str) -> list[Note]:
    """The Warder on a prompt: injections, leaks, secrets, destructive asks (rules, no model)."""
    notes = [Note("warder", sev, f"{where} {why}") for rx, sev, why in _PROMPT_RISKS if rx.search(text or "")]
    if audit._TOKENISH.search(text or ""):
        notes.append(Note("warder", "block", f"{where} holds a secret — keep it in an environment variable"))
    return notes


def _tool_notes(where: str, harness: list[dict] | None, text: str) -> list[Note]:
    """The Warder on tools: an agent that writes files (agy accept-edits) asked to push or delete."""
    writes = any(str(s.get("harness")) == "agy" or str(s.get("role")) == "write" for s in harness or [])
    if writes and re.search(r"\b(push|deploy|delete|remove|publish|release)\b", text or "", re.I):
        return [Note("warder", "warn", f"{where} can write files and is asked to push, delete or publish — "
                                       "keep that behind a confirmation")]
    return []


def _building_rules(spec: dict, repo_root: Path, existing: set[str]) -> list[Note]:
    from orkcraft.realm import catalog, masonry
    spec = catalog.migrate(spec)
    notes = [Note("mason", "block", p) for p in masonry.validate_spec(spec, repo_root, existing)[:6]]
    cfg, kind = spec.get("config") or {}, spec.get("type") or catalog.DEFAULT_TYPE
    # Chief
    if kind == "barracks" and int(cfg.get("max_orcs") or 1) > 3:
        notes.append(Note("chief", "warn", f"up to {cfg['max_orcs']} agents at once — each one spends"))
    if kind == "mill" and isinstance(cfg.get("steps"), list):
        from orkcraft.realm import mill
        if mill.model_steps([str(s) for s in cfg["steps"]]) > 1:
            notes.append(Note("chief", "warn", "more than one agent step on every cart"))
    # Artisan
    title = str(spec.get("title") or "")
    if len(title) > 32:
        notes.append(Note("artisan", "warn", f"the title is {len(title)} characters — a hut shows about 20"))
    if not spec.get("icon"):
        notes.append(Note("artisan", "warn", "no icon — huts and tabs show one"))
    if len(spec.get("actions") or []) > 4:
        notes.append(Note("artisan", "warn", "more than four Command Card actions"))
    if len(spec.get("events") or []) > 4:
        notes.append(Note("artisan", "warn", f"{len(spec['events'])} events to wire — fewer is easier to follow"))
    if len([k for k, v in cfg.items() if v not in (None, "", [], {})]) > 8:
        notes.append(Note("artisan", "warn", "more than eight settings — split it, or keep the defaults"))
    for line in ((spec.get("mini") or {}).get("lines") or []):
        if isinstance(line, dict) and len(str(line.get("template", ""))) > 30:
            notes.append(Note("artisan", "warn", f"hut line '{str(line['template'])[:24]}…' will be cut"))
            break
    # Warder
    for where, cmd in _commands(spec):
        notes += _scan(where, cmd)
    for key, value in cfg.items():
        if isinstance(value, str) and key not in _COMMAND_KEYS and key not in _PROMPT_KEYS and audit._TOKENISH.search(value):
            notes.append(Note("warder", "block", f"setting '{key}' holds a secret — keep it in an environment variable"))
    for key in _PROMPT_KEYS:
        if isinstance(cfg.get(key), str):
            notes += _scan_prompt(f"its {key.replace('_', ' ')}", cfg[key])
    # Peon
    if kind == "barracks" and cfg.get("worktrees") is False:
        notes.append(Note("peon", "warn", "its orks share one working tree and may overwrite each other"))
    if kind == "forge" and not cfg.get("test_cmd") and not cfg.get("confirm"):
        notes.append(Note("peon", "warn", "merges without tests or a confirmation"))
    if _PERMISSION_SKIP.search(json.dumps(spec, ensure_ascii=False)):
        notes.append(Note("peon", "block", "skips permission prompts"))
    return notes


def _agent_rules(data: dict, script: str) -> list[Note]:
    from orkcraft import scroll as ts
    orc = dict(data.get("orc") or {})
    orc.setdefault("id", data.get("id") or "new_orc")
    notes = [Note("mason", "block", p) for p in ts.orc_problems(orc)[:6]]
    kind = orc.get("kind", "agent")
    run = {**ts.RUN_DEFAULTS.get(kind, ts.RUN_DEFAULTS["agent"]), **(orc.get("run") or {})}
    roads = data.get("roads") or []
    # Chief — a road rule is reviewed like an agent's orders: its text and its roads
    if kind in ("agent", "hybrid", "steward"):
        if not str(orc.get("why") or "").strip():
            notes.append(Note("chief", "warn", "a model on every run, and no word on why a chain or a script won't do"))
        if int(run.get("quiet_s") or 0) < 10:
            notes.append(Note("chief", "warn", "re-runs the model on every event with no quiet time"))
        if any(r.get("event") == "on_selection_change" for r in roads if isinstance(r, dict)):
            notes.append(Note("chief", "warn", "every selection wakes a model"))
        if len(orc.get("harness") or []) > 2:
            notes.append(Note("chief", "warn", f"{len(orc['harness'])} model steps per run"))
    # Mason: the script must at least parse
    if script and kind in ("script", "hybrid"):
        try:
            ast.parse(script)
        except SyntaxError as e:
            notes.append(Note("mason", "block", f"the script does not parse: line {e.lineno}: {e.msg}"))
    # Artisan
    if len(str(orc.get("name") or "")) > 24:
        notes.append(Note("artisan", "warn", "the ork's name is long for the roster"))
    if len(roads) > 3:
        notes.append(Note("artisan", "warn", f"{len(roads)} roads into one handler — hard to follow on the map"))
    notes += _scan_prompt("its orders", str(orc.get("orders") or ""))
    notes += _tool_notes("it", orc.get("harness"), str(orc.get("orders") or ""))
    # Warder
    if script:
        notes += _scan("the script", script)
    path = str((orc.get("script") or {}).get("path") or "")
    # Peon
    if path and (path.startswith("/") or ".." in Path(path).parts):
        notes.append(Note("peon", "block", f"the script lives outside its folder: {path}"))
    if _PERMISSION_SKIP.search(json.dumps(orc, ensure_ascii=False)):
        notes.append(Note("peon", "block", "skips permission prompts"))
    return notes


def _road_rules(data: dict) -> list[Note]:
    notes = []
    if data.get("source") == data.get("target"):
        notes.append(Note("mason", "block", "a building cannot listen to itself"))
    kind = data.get("handler_kind") or ""
    if kind in ("agent", "hybrid", "steward") and data.get("event") == "on_selection_change":
        notes.append(Note("chief", "warn", "every selection in the source wakes a model"))
    flt = data.get("filter") or {}
    if flt.get("match"):
        from orkcraft import scroll as ts
        notes += [Note("mason", "block", p) for p in ts.filter_problems(flt)]
    return notes


def rules(subject: Subject, repo_root: Path, existing: set[str] | frozenset[str] = frozenset()) -> list[Note]:
    if subject.kind == "building":
        notes = _building_rules(subject.data, repo_root, set(existing))
        if subject.script:                                  # a Workshop's script
            notes += _scan("the script", subject.script)
            if (subject.data.get("config") or {}).get("steward_prompt"):
                notes.append(Note("chief", "warn", "carts the script hands over (exit 3) go to a model"))
    elif subject.kind == "agent":
        notes = _agent_rules(subject.data, subject.script)
    else:
        notes = _road_rules(subject.data)
    flagged = {n.role for n in notes}
    return notes + [Note(r, "ok") for r in ROLE_IDS if r not in flagged]


# -- the light model ------------------------------------------------------------------------------

def _prompt(subject: Subject, notes: list[Note]) -> str:
    duties = "\n".join(f"- {rid} ({name}, {duty}): {text}" for rid, _, name, duty, text in ROLES)
    body = json.dumps(subject.data, ensure_ascii=False, indent=1)
    if subject.script:
        body += "\n\nSCRIPT:\n" + subject.script
    found = "; ".join(f"{n.role}: {n.text}" for n in notes if n.severity == "warn") or "no warnings"
    return PROMPT.format(kind=subject.kind, kind_upper=subject.kind.upper(), duties=duties,
                         subject=body[:SUBJECT_LIMIT], rules=found)


def _model_notes(text: str) -> list[Note]:
    from orkcraft.realm import builders
    data = builders.extract_json(text) or {}
    out = []
    for rid in ROLE_IDS:
        v = data.get(rid)
        if isinstance(v, dict) and v.get("ok") is False:
            out.append(Note(rid, "object", str(v.get("note") or "objects")[:160]))
    return out


def review(subject: Subject, repo_root: Path, existing: set[str] | frozenset[str] = frozenset(),
           runner: Runner | None = None, model: str = "") -> Verdict:
    """Rules, then (when `runner` is given and nothing blocked) the light model. Never raises."""
    notes = rules(subject, repo_root, existing)
    verdict = Verdict(subject, notes)
    if runner is None or verdict.blocked:
        return verdict
    try:
        text, cost = runner(_prompt(subject, notes))
    except Exception as e:  # the CLI missing, a timeout, a bad answer: the rules stand
        verdict.error = str(e)[:200]
        return verdict
    objections = _model_notes(text)
    flagged = {n.role for n in objections}
    verdict.notes = [n for n in notes if not (n.severity == "ok" and n.role in flagged)] + objections
    verdict.model, verdict.cost_usd = model or "light model", cost
    return verdict


def log(repo_root: Path, verdict: Verdict, decision: str) -> None:
    """decision: approved | rejected | overridden | cancelled."""
    path = repo_root / COUNCIL_DIR / "reviews.jsonl"
    record = {"ts": dt.datetime.now().isoformat(timespec="seconds"), "kind": verdict.subject.kind,
              "id": verdict.subject.id, "decision": decision, "model": verdict.model,
              "cost_usd": verdict.cost_usd, "error": verdict.error,
              "notes": [asdict(n) for n in verdict.notes if n.severity != "ok"]}
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError:
        pass


def recent(repo_root: Path, limit: int = 20) -> list[dict]:
    try:
        lines = (repo_root / COUNCIL_DIR / "reviews.jsonl").read_text(encoding="utf-8").splitlines()[-limit:]
    except OSError:
        return []
    out = []
    for line in reversed(lines):
        try:
            out.append(json.loads(line))
        except ValueError:
            continue
    return out
