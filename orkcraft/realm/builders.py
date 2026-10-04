"""Mason & Artisan: a prompt becomes a validated custom building spec.

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

from orkcraft.realm import huts, masonry
from orkcraft.sources import telemetry
from orkcraft.sources.sessions import claude_bin

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
{{"id": "<snake_case, 2-32 chars>", "title": "<plain functional title, max 40 chars>", "icon": "<one emoji>",
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


def claude_runner(prompt: str, model: str | None = None) -> tuple[str, float | None]:
    """One non-interactive Claude Code call in an empty folder (`model`: an alias such as haiku or
    opus; None keeps the operator's default). Raises RuntimeError on failure."""
    with tempfile.TemporaryDirectory(prefix="orkcraft-mason-") as empty:
        env = {k: v for k, v in os.environ.items() if not k.startswith("ORKCRAFT_")}
        try:
            proc = subprocess.run(
                [claude_bin(), "-p", prompt, "--output-format", "json", *(["--model", model] if model else [])],
                cwd=empty, env=env, capture_output=True, text=True, timeout=CALL_TIMEOUT_S,
            )
        except FileNotFoundError as e:
            raise RuntimeError(f"Claude Code CLI not found ({claude_bin()}) — install it or set ORKCRAFT_CLAUDE_BIN") from e
        except subprocess.TimeoutExpired as e:
            raise RuntimeError(f"no answer within {CALL_TIMEOUT_S} s") from e
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
            attempt.errors = masonry.validate_spec(spec, repo_root, existing_ids)
        attempts.append(attempt)
        if not attempt.errors:
            return BuildResult(spec, attempts, total)
    return BuildResult(None, attempts, total)


# -- the build wizard: a typed building from the catalog ---------------------------------

FOREMAN = """You are the Foreman of orkcraft (a terminal town where every building is a typed block on
a map, joined by roads that carry events). The operator wants a new building. {pick}

OPERATOR REQUEST:
{request}

BUILDING TYPES (choose only from these; every event, quick action and config key must be the type's own):
{catalog}

Prefill it so the operator only has to confirm: a plain functional title (no fantasy), one emoji icon,
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
    type when `type_id` is None. A custom (panes) building goes to Mason & Artisan. Never raises."""
    from orkcraft.realm import catalog

    request = request.strip()[:PROMPT_LIMIT]
    type_id = catalog.ALIASES.get(type_id, type_id) if type_id else type_id   # an old id names its camp building
    if type_id == catalog.DEFAULT_TYPE:
        return build(request, repo_root, existing_ids, runner, max_attempts)
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
            if type_id:
                spec["type"] = type_id                 # the operator's pick wins over the model's
            if spec.get("type") == catalog.DEFAULT_TYPE:
                attempts.append(attempt)               # the model asks for panes: Mason & Artisan
                result = build(request, repo_root, existing_ids, runner, max_attempts)
                result.attempts[:0] = attempts
                return result
            attempt.errors = masonry.validate_spec(spec, repo_root, existing_ids)
        attempts.append(attempt)
        if not attempt.errors:
            return BuildResult(spec, attempts, total)
    return BuildResult(None, attempts, total)
