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

from orkcraft.realm import halt, harnesses, huts, masonry, naming, tool_errors
from orkcraft.sources import telemetry

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


def _call(h: harnesses.Harness, prompt: str, model: str | None) -> subprocess.CompletedProcess:
    """One non-interactive answer of `h` in an empty temporary folder, without orkcraft's own
    variables. Raises RuntimeError when the CLI is missing or silent, Stopped on 🛑 Halt All."""
    with tempfile.TemporaryDirectory(prefix="orkcraft-mason-") as empty:
        env = {**{k: v for k, v in os.environ.items() if not k.startswith("ORKCRAFT_")}, **h.env("ask", empty)}
        cmd = h.ask(prompt, empty, model or "")
        try:
            return halt.run(cmd, input=h.stdin(prompt), cwd=empty, env=env, timeout=CALL_TIMEOUT_S,   # 🛑 Halt All
                            who=h.id, agent=True)
        except FileNotFoundError as e:
            raise tool_errors.ToolError(h.id, f"{h.title} CLI not found ({cmd[0]}) — install it or set "
                                        f"ORKCRAFT_{h.id.upper()}_BIN", kind=tool_errors.MISSING) from e
        except subprocess.TimeoutExpired as e:
            raise RuntimeError(f"no answer within {CALL_TIMEOUT_S} s") from e
        except halt.Halted as e:
            raise halt.Stopped() from e


def ask(harness_id: str, prompt: str, model: str | None = None) -> tuple[str, float | None]:
    """One answer of a tool in an empty folder (`model`: its own, a tier word, or another tool's model
    — harnesses.model_on; None keeps its default). Raises RuntimeError on failure."""
    h = harnesses.need(harness_id)
    proc = _call(h, prompt, model)
    if proc.returncode != 0:
        why = h.error(proc.stdout) or (proc.stderr or proc.stdout).strip()
        raise tool_errors.ToolError(h.id, why, proc.returncode)
    text, cost, _, _ = h.outcome(proc.stdout, 0, model or "")
    if not text.strip() and (why := h.error(proc.stdout)):
        raise tool_errors.ToolError(h.id, f"{h.id} gave no answer: {why}")
    telemetry.charge(cost, f"{h.id} -p {model or 'default'}")    # no transcript of this run: 🪙 here
    return text, cost


def claude_runner(prompt: str, model: str | None = None) -> tuple[str, float | None]:
    """One non-interactive Claude Code call in an empty folder (`model`: an alias such as haiku or
    opus; None keeps the operator's default). Raises RuntimeError on failure."""
    return ask("claude", prompt, model)


def runner_on(harness_id: str, model: str | None = None) -> Runner:
    """The model call of one tool (a step's or a building's own choice)."""
    return lambda prompt, m=None: ask(harness_id, prompt, m or model)


def main_tool(machine=None) -> str:
    """The machine's main tool (settings.MachineSettings, read from disk when not given: the chosen one
    if it is on, else the first on); Claude Code when none is on, as before there was a choice."""
    if machine is None:
        machine = _machine()
    return harnesses.main([t for t, c in machine.tools.items() if c.enabled], machine.main_tool) or "claude"


_SETTINGS: dict = {}


def _machine():
    """The machine settings on disk, read again only when the file changed (the map asks often)."""
    from orkcraft import settings
    file = settings.path()
    try:
        key = (str(file), file.stat().st_mtime_ns)
    except OSError:
        key = (str(file), None)
    if _SETTINGS.get("key") != key:
        _SETTINGS.update(key=key, machine=settings.load(file))
    return _SETTINGS["machine"]


def main_runner_of(machine) -> Runner:
    """Decisions on the main tool of this machine's settings as a face holds them."""
    return runner_on(main_tool(machine))


def main_runner(prompt: str, model: str | None = None) -> tuple[str, float | None]:
    """A decision on the machine's main tool, read when it is asked (`model`: a tier word or any
    tool's model, harnesses.model_on)."""
    return ask(main_tool(), prompt, model)


def runner_for(harness_id: str = "", model: str | None = None) -> Runner:
    """A building's or step's tool when it names one (not `main`), else the main tool's."""
    if harness_id and harness_id != harnesses.MAIN and harnesses.get(harness_id):
        return runner_on(harness_id, model)
    return (lambda prompt, m=None: main_runner(prompt, m or model)) if model else main_runner


def planner_tool(enabled, chosen: str = "") -> str | None:
    """The tool a planner calls: the chosen main one when it is on, else the first on; None when none is."""
    return harnesses.main(list(enabled), chosen)


def planner_runner(enabled, chosen: str = "") -> Runner | None:
    """`planner_tool`'s model call, None when no tool is on."""
    tool = planner_tool(enabled, chosen)
    return runner_on(tool) if tool else None


def _feedback(attempts: list[Attempt]) -> str:
    if not attempts:
        return ""
    last = attempts[-1]
    lines = "\n".join(f"- {e}" for e in last.errors[:12])
    return f"\nYOUR PREVIOUS SPEC WAS REJECTED. Fix every problem:\n{lines}\n"


def build(request: str, repo_root: Path, existing_ids: set[str] | frozenset[str] = frozenset(),
          runner: Runner = main_runner, max_attempts: int = MAX_ATTEMPTS) -> BuildResult:
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
            runner: Runner = main_runner, max_attempts: int = MAX_ATTEMPTS) -> BuildResult:
    """The Foreman's prefilled spec for a typed building, checked like any spec; the AI picks the
    type when `type_id` is None. Custom (panes) is retired: none is proposed anew. Never raises."""
    from orkcraft.realm import catalog

    request = request.strip()[:PROMPT_LIMIT]
    type_id = catalog.ALIASES.get(type_id, type_id) if type_id else type_id   # an old id names its camp building
    if type_id in catalog.RETIRED_TYPES:
        return BuildResult(None, [], error=RETIRED)
    types = [catalog.TYPES[type_id]] if type_id in catalog.TYPES else \
        [t for t in catalog.TYPES.values()
         if t.id not in catalog.SYSTEM_TYPES | catalog.SCRATCH_TYPES | catalog.RETIRED_TYPES]
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
            if not spec.get("type") or spec["type"] in catalog.RETIRED_TYPES:   # a retired type left the catalog
                attempt.errors = [f"type: {spec.get('type') or 'missing'!r} is not offered, pick one of the "
                                  "BUILDING TYPES above"]
            else:
                attempt.errors = masonry.validate_spec(spec, repo_root, existing_ids)
        attempts.append(attempt)
        if not attempt.errors:
            return BuildResult(spec, attempts, total)
    return BuildResult(None, attempts, total)
