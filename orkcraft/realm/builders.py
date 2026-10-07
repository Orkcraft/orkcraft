"""Mason & Artisan: a prompt becomes a validated custom building spec. Custom (panes) left the
catalog: no screen builds one any more (an old Town Scroll's still loads and draws); `build` stays for
the demo's feature shots. `propose` (the Foreman) is the live build wizard's.

    [B] prompt → Mason (data: which sources, which filters) → Artisan (panes, widgets, actions)
              → JSON spec → masonry.validate_spec → valid: raise it / invalid: back to Mason
                with the errors (at most `MAX_ATTEMPTS` rounds)

Both builders are one Claude call each (`claude -p … --output-format json`, the operator's own
Claude Code login — no API key needed). The call runs in an empty temporary folder, so the
builders see only what the prompt gives them: the operator's request and the catalog generated
by `masonry.catalog()` — never the graph's content. Their output is untrusted text: only a JSON
object that passes `validate_spec` is ever used, and a spec is data, never code.
"""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from orkcraft.realm import halt, huts, masonry, naming
from orkcraft.sources import telemetry
from orkcraft.sources.sessions import agy_bin, claude_bin, codex_bin

MAX_ATTEMPTS = 3
CALL_TIMEOUT_S = 240
PROMPT_LIMIT = 2000

# (prompt) -> (model text, cost in USD or None)
Runner = Callable[[str], tuple[str, float | None]]

MASON = """You are Mason, the data architect of orkcraft (a terminal harness over a Markdown knowledge graph).
The operator wants a new window ("building"). Decide which data it needs, using ONLY the catalog below.
Give the building a plain, functional title (e.g. "CI Monitor", "Recent Commits", "Pull Requests") — do NOT use fantasy, medieval, or fictional metaphors. The icon can be a fitting emoji.

OPERATOR REQUEST:
{request}

{catalog}
{feedback}
Answer with ONE JSON object and nothing else:
{{"id": "<snake_case, 2-32 chars>", "title": "<plain functional title, at most 4 words>", "icon": "<one emoji>",
  "summary": "<one sentence>", "orc": {{"name": "<a fitting ork name>", "role": "<what it watches>"}},
  "data": [{{"name": "<snake_case>", "source": "<a catalog source>", "params": {{...catalog params only...}}}}]}}
Use 1-6 data entries. Paths are relative to the repository root; never absolute, never outside it."""

ARTISAN = """You are Artisan, the UI designer of orkcraft. Mason chose this building's data:
{mason}

Lay it out using ONLY the catalog below: 1-4 panes (each pane shows one data entry by name with a
widget of the matching kind), a direction (vertical = stacked, horizontal = side by side), optional
ratios 1-4, optional table columns, and 0-4 Command Card actions with free keys.
Use plain, functional titles for panes and action labels (not fantasy).

Also design the collapsed view ("mini"): on the town map the building is a small card — up to three
status lines of at most 22 characters (the first is the most important; with the operator's art
switched on only the first two show) and the ASCII art piece it wears then, from this library:
{art}
Each line is a template over ONE data entry: list data offers {{count}} (rows, after the optional
"where" filter on row fields) and the first row's fields {{title}} {{id}} {{status}} {{priority}}
{{assignee}} {{type}} {{deadline}} {{when}} {{meta}}; text data offers {{last}} {{first}} {{heading}} (first Markdown heading) {{count}};
tree data offers {{count}}. Say what matters at a glance: the current state, the next thing, a problem.

{catalog}
{feedback}
Answer with ONE JSON object and nothing else: Mason's object with three keys added —
"layout": {{"direction": "vertical|horizontal", "panes": [{{"widget": "...", "data": "<data name>", "title": "...", "ratio": 1}}]}},
"actions": [{{"key": "<free key>", "label": "...", "action": "<catalog action>"}}],
"mini": {{"art": "<library name>", "lines": [{{"data": "<data name>", "template": "...", "where": {{"status": "..."}}}}]}}."""


@dataclass
class Attempt:
    mason: str = ""
    artisan: str = ""
    errors: list[str] = field(default_factory=list)


@dataclass
class BuildResult:
    spec: dict | None
    attempts: list[Attempt]
    cost_usd: float | None = None
    error: str = ""                 # a failure outside validation (CLI missing, timeout, …)

    @property
    def ok(self) -> bool:
        return self.spec is not None


def extract_json(text: str) -> dict | None:
    """The first JSON object in a model answer (code fences and chatter around it are ignored)."""
    decoder = json.JSONDecoder()
    for i, ch in enumerate(text):
        if ch != "{":
            continue
        try:
            obj, _ = decoder.raw_decode(text[i:])
        except ValueError:
            continue
        if isinstance(obj, dict):
            return obj
    return None


def _call(tool: str, cmd_in: Callable[[str], list[str]], stdin: str | None = None) -> subprocess.CompletedProcess:
    """One non-interactive CLI call (`cmd_in(folder)`) in an empty temporary folder, without orkcraft's
    own variables. Raises RuntimeError when the CLI is missing or silent, Stopped on 🛑 Halt All."""
    with tempfile.TemporaryDirectory(prefix="orkcraft-mason-") as empty:
        env = {k: v for k, v in os.environ.items() if not k.startswith("ORKCRAFT_")}
        cmd = cmd_in(empty)
        try:
            return halt.run(cmd, input=stdin, cwd=empty, env=env, timeout=CALL_TIMEOUT_S)   # 🛑 Halt All stops it
        except FileNotFoundError as e:
            raise RuntimeError(f"{TOOL_NAMES[tool]} CLI not found ({cmd[0]}) — install it or set "
                               f"ORKCRAFT_{tool.upper()}_BIN") from e
        except subprocess.TimeoutExpired as e:
            raise RuntimeError(f"no answer within {CALL_TIMEOUT_S} s") from e
        except halt.Halted as e:
            raise halt.Stopped() from e


def claude_runner(prompt: str, model: str | None = None) -> tuple[str, float | None]:
    """One non-interactive Claude Code call in an empty folder (`model`: an alias such as haiku or
    opus; None keeps the operator's default). Raises RuntimeError on failure."""
    proc = _call("claude", lambda _: [claude_bin(), "-p", prompt, "--output-format", "json",
                                      *(["--model", model] if model else [])])
    if proc.returncode != 0:
        raise RuntimeError(f"claude exited with {proc.returncode}: {(proc.stderr or proc.stdout).strip()[:300]}")
    out = proc.stdout.strip()
    text, cost = out, None
    try:
        envelope = json.loads(out)
    except ValueError:
        envelope = None
    if isinstance(envelope, dict) and isinstance(envelope.get("result"), str):
        raw = envelope.get("total_cost_usd")
        text, cost = envelope["result"], float(raw) if isinstance(raw, (int, float)) else None
    telemetry.charge(cost, f"claude -p {model or 'default'}")     # no transcript of this run: 🪙 here
    return text, cost


def agy_runner(prompt: str, model: str | None = None) -> tuple[str, float | None]:
    """One headless agy call in an empty folder, its shell in agy's sandbox and its edits only in that
    folder (`model`: one of agy's, realm/tiers.py; None its usual flash). Raises RuntimeError on failure."""
    from orkcraft.realm import roads
    proc = _call("agy", lambda empty: [agy_bin(), "--print", prompt, "--model", model or roads.AGY_MODEL,
                                       "--mode", "accept-edits", "--sandbox", "--add-dir", empty,
                                       "--output-format", "json"])
    if proc.returncode != 0:
        raise RuntimeError(roads.failure("agy", proc.returncode, proc.stdout, proc.stderr))
    text, cost, _ = roads._result_of(proc.stdout)
    telemetry.charge(cost, f"agy --print {model or 'default'}")
    return text, cost


def codex_runner(prompt: str, model: str | None = None) -> tuple[str, float | None]:
    """One `codex exec` in an empty folder and a read-only sandbox, its prompt on stdin (`model`: one
    of Codex's; None its default). Codex prints no price: the cost is None. Raises RuntimeError on failure."""
    from orkcraft.realm import roads
    proc = _call("codex", lambda _: [codex_bin(), *roads.codex_cmd("read-only", model or "")[1:]], stdin=prompt)
    if proc.returncode != 0:
        raise RuntimeError(roads.failure("codex", proc.returncode, proc.stdout, proc.stderr))
    text = roads.codex_result_of(proc.stdout)[0]
    if not text:
        raise RuntimeError(f"codex gave no answer: {(roads.codex_error(proc.stdout) or proc.stderr).strip()[:300]}")
    telemetry.charge(None, f"codex exec {model or 'default'}")
    return text, None


# The tools a planner (the Town Builder) may call, in the order one is picked when several are on.
RUNNERS: dict[str, Runner] = {"claude": claude_runner, "codex": codex_runner, "agy": agy_runner}
TOOL_NAMES = {"claude": "Claude Code", "codex": "Codex", "agy": "agy"}


def planner_tool(enabled) -> str | None:
    """The tool a planner calls: the first of `RUNNERS` the operator turned on, None when none is."""
    on = set(enabled)
    return next((t for t in RUNNERS if t in on), None)


def planner_runner(enabled) -> Runner | None:
    """`planner_tool`'s model call, None when no tool that plans is on."""
    tool = planner_tool(enabled)
    return RUNNERS[tool] if tool else None


def _feedback(attempts: list[Attempt]) -> str:
    if not attempts:
        return ""
    last = attempts[-1]
    lines = "\n".join(f"- {e}" for e in last.errors[:12])
    return f"\nYOUR PREVIOUS SPEC WAS REJECTED. Fix every problem:\n{lines}\n"


def build(request: str, repo_root: Path, existing_ids: set[str] | frozenset[str] = frozenset(),
          runner: Runner = claude_runner, max_attempts: int = MAX_ATTEMPTS) -> BuildResult:
    """Run Mason → Artisan until the spec validates or the attempts run out. Never raises."""
    request = request.strip()[:PROMPT_LIMIT]
    catalog = masonry.catalog()
    attempts: list[Attempt] = []
    total: float | None = None

    def call(prompt: str) -> str:
        nonlocal total
        text, cost = runner(prompt)
        if cost is not None:
            total = (total or 0.0) + cost
        return text

    for _ in range(max_attempts):
        attempt = Attempt()
        try:
            attempt.mason = call(MASON.format(request=request, catalog=catalog, feedback=_feedback(attempts)))
            mason = extract_json(attempt.mason)
            if mason is None:
                attempt.errors = ["Mason's answer had no JSON object"]
                attempts.append(attempt)
                continue
            attempt.artisan = call(ARTISAN.format(mason=json.dumps(mason, ensure_ascii=False, indent=2),
                                                  catalog=catalog, art=huts.art_catalog(),
                                                  feedback=_feedback(attempts)))
        except RuntimeError as e:
            attempts.append(attempt)
            return BuildResult(None, attempts, total, error=str(e))
        spec = extract_json(attempt.artisan)
        if spec is None:
            attempt.errors = ["Artisan's answer had no JSON object"]
        else:
            spec.pop("version", None)
            spec["title"] = naming.clip(spec.get("title", "")) or naming.from_prompt(request, "New building")
            attempt.errors = masonry.validate_spec(spec, repo_root, existing_ids)
        attempts.append(attempt)
        if not attempt.errors:
            return BuildResult(spec, attempts, total)
    return BuildResult(None, attempts, total)


# -- the build wizard: a typed building from the catalog ---------------------------------

RETIRED = ("Custom (panes) buildings are no longer built: pick a camp building, or build one from "
           "scratch (the Builder's Workshop)")

FOREMAN = """You are the Foreman of orkcraft (a terminal town where every building is a typed block on
a map, joined by roads that carry events). The operator wants a new building. {pick}

OPERATOR REQUEST:
{request}

BUILDING TYPES (choose only from these; every event, quick action and config key must be the type's own):
{catalog}

Prefill it so the operator only has to confirm: a plain functional title of at most 4 words (no fantasy), one emoji icon,
a resident ork (a fitting ork name and what it watches), the size (XS S M L — the type's default unless
the request says otherwise), the events this building should send (the ones the request needs; all when
unsure), up to two quick actions that matter most on the map, and the type's config filled from the
request (leave out what you cannot know; never invent passwords or tokens — config only names the
environment variables that hold them). A roof is optional decoration for the hut: one of {roofs},
or leave it out.
{feedback}
Answer with ONE JSON object and nothing else:
{{"type": "<type id>", "id": "<snake_case, 2-32 chars>", "title": "...", "icon": "<emoji>",
  "summary": "<one sentence>", "orc": {{"name": "...", "role": "..."}}, "size": "S",
  "events": ["..."], "quick_actions": ["..."], "config": {{...}}, "roof": "<optional>"}}"""


def propose(request: str, repo_root: Path, type_id: str | None = None,
            existing_ids: set[str] | frozenset[str] = frozenset(),
            runner: Runner = claude_runner, max_attempts: int = MAX_ATTEMPTS) -> BuildResult:
    """The Foreman's prefilled spec for a typed building, checked like any spec; the AI picks the
    type when `type_id` is None. Custom (panes) is retired: none is proposed anew. Never raises."""
    from orkcraft.realm import catalog

    request = request.strip()[:PROMPT_LIMIT]
    type_id = catalog.ALIASES.get(type_id, type_id) if type_id else type_id   # an old id names its camp building
    if type_id in catalog.RETIRED_TYPES:
        return BuildResult(None, [], error=RETIRED)
    types = [catalog.TYPES[type_id]] if type_id in catalog.TYPES else \
        [t for t in catalog.TYPES.values() if t.id != catalog.DEFAULT_TYPE
         and t.id not in catalog.SYSTEM_TYPES | catalog.SCRATCH_TYPES]
    text_catalog = catalog.catalog_text(types)
    pick = f"Its type is fixed: {type_id}." if type_id else "Pick the type that fits the request best."
    attempts: list[Attempt] = []
    total: float | None = None
    for _ in range(max_attempts):
        attempt = Attempt()
        try:
            text, cost = runner(FOREMAN.format(pick=pick, request=request, catalog=text_catalog,
                                               roofs=", ".join(huts.ROOFS), feedback=_feedback(attempts)))
        except RuntimeError as e:
            attempts.append(attempt)
            return BuildResult(None, attempts, total, error=str(e))
        if cost is not None:
            total = (total or 0.0) + cost
        attempt.mason = text
        spec = extract_json(text)
        if spec is None:
            attempt.errors = ["the answer had no JSON object"]
        else:
            spec.pop("version", None)
            spec["title"] = naming.clip(spec.get("title", "")) or naming.from_prompt(request, "New building")
            if type_id:
                spec["type"] = type_id                 # the operator's pick wins over the model's
            if not spec.get("type") or spec["type"] in catalog.RETIRED_TYPES:   # custom (panes) left the catalog
                attempt.errors = [f"type: {spec.get('type') or 'missing'!r} is not offered, pick one of the "
                                  "BUILDING TYPES above"]
            else:
                attempt.errors = masonry.validate_spec(spec, repo_root, existing_ids)
        attempts.append(attempt)
        if not attempt.errors:
            return BuildResult(spec, attempts, total)
    return BuildResult(None, attempts, total)
