"""How a road's handler runs an agent: its prompt, the tool's argv, the run itself (`run_agent`, under
Halt All) and its recorded examples. Split out of `realm/roads.py`, which re-exports it; tests that
fake a run patch `roads.run_agent` (the engine reads it there) or this module's `run_proc` and
`_harness_cmd`.
"""
from __future__ import annotations

import glob
import json
import os
import subprocess
import tempfile
import threading
import time
from pathlib import Path
from typing import Callable

from orkcraft import scroll as ts
from orkcraft.realm import halt, harnesses, tool_errors
from orkcraft.sources import telemetry

AGENT_TIMEOUT_S = 600
SNAPSHOT_CHARS = 4000          # per road, in an agent prompt
EXAMPLES_DIR = Path(".orkcraft") / "history" / "handlers"
IN_REPO = tuple(h.id for h in harnesses.REGISTRY.values() if h.in_repo)

# (harness, prompt, repo, env, cancel[, model]) -> (text, cost USD, tokens) — the tokens may be left out;
# the model comes only when the step has one (its own or its tier's, realm/tiers.py)
AgentRunner = Callable[..., tuple]

ROLE_ASK = {
    "run": "Do what your orders say with this input.",
    "plan": "Write a short plan for the next step; do not do the work yourself.",
    "write": "Produce the result your orders ask for.",
    "review": "Check the previous step's result against your orders and the input; answer with the corrected final result.",
}


PROMPT_DROPS = ("road", "kind", "value")   # a road id, and what `id` / `path` / `text` already say


def prompt_record(rec: dict) -> dict:
    """A road's record as a model reads it: its body once (`text`, `id` or `path`, never `value` too),
    no road id or kind, no empty field, a long text cut at SNAPSHOT_CHARS."""
    has_body = any(k in rec for k in ("text", "id", "path"))
    out = {}
    for k, v in rec.items():
        if (k in PROMPT_DROPS and (k != "value" or has_body)) or v in (None, "", [], {}):
            continue
        out[k] = v[:SNAPSHOT_CHARS] + "…" if isinstance(v, str) and len(v) > SNAPSHOT_CHARS else v
    return out


def _purpose(building: ts.BuildingSpec) -> str:
    """What its steward is for: its role and its orders (the building's purpose), "" when it has none."""
    stew = building.garrison.steward
    if stew is None:
        return ""
    return "\n".join(x for x in (stew.role.strip(), stew.orders.strip()) if x)


def agent_prompt(orc: ts.OrcSpec, building: ts.BuildingSpec, snapshot: list[dict], role: str,
                 previous: str = "", liked: list[str] | None = None) -> str:
    roads = [prompt_record(rec) for rec in snapshot]
    if orc.on_steward:                                 # a road rule: the steward thinks, toward its building's goal
        stew = building.garrison.steward
        purpose = _purpose(building)
        head = [
            f"You are {stew.name if stew else 'the steward'}, the steward of the {building.title} building in "
            f"Orkcraft, a harness for a Markdown knowledge graph (the current directory). You carry out its "
            f"road rule \"{orc.name}\": you are re-run on every new event with the latest payload of each road "
            f"the rule listens to.",
            *([f"What the building is for (every rule works toward it):\n{purpose}"] if purpose else []),
            f"The rule:\n{orc.orders or '(none — summarise the input for the operator)'}",
        ]
    else:
        head = [
            f"You are {orc.name}, a handler ork of the {building.title} building in Orkcraft, a terminal "
            f"harness for a Markdown knowledge graph (the current directory). You are re-run on every new "
            f"event with the latest payload of each of your incoming roads.",
            f"Your orders:\n{orc.orders or '(none — summarise the input for the operator)'}",
        ]
    parts = [
        *head,
        "Incoming roads (latest payload each, one per line; node ids resolve to <ID>.md files):\n"
        + "\n".join(json.dumps(r, ensure_ascii=False, separators=(",", ":")) for r in roads),
    ]
    if previous:
        parts.append(f"The previous step's result:\n{previous}")
    if liked and role != "plan":                       # 👍 references: the shape of a result, not of a plan
        parts.append("Results the operator liked from this building (match their shape):\n"
                     + "\n".join(f"- {x[:600]}" for x in liked[:3]))
    parts.append(f"{ROLE_ASK.get(role, ROLE_ASK['run'])} Answer with the Markdown the operator should "
                 "see and nothing else. Never quote personal context nodes.")
    return "\n\n".join(parts)


def resolve(harness: str) -> str:
    """A step's tool as it runs: `main` (or nothing) is the machine's main tool."""
    if harness and harness != harnesses.MAIN:
        return harness
    from orkcraft.realm import builders
    return builders.main_tool()


def harness_stdin(harness: str, prompt: str) -> str | None:
    """What goes on stdin: a tool that reads its prompt there (Codex: no argv limit, never taken for a
    flag); the others take it as an argument."""
    h = harnesses.get(harness)
    return h.stdin(prompt) if h else None


def _harness_cmd(harness: str, prompt: str, workdir: Path, model: str = "", web: bool = False) -> list[str]:
    h = harnesses.get(harness)
    if h is None:
        raise RuntimeError(f"harness {harness!r} is not wired yet (pipelines come later)")
    return h.read(prompt, workdir, model, web)


def _tokens_of(env: dict) -> int | None:
    """All tokens of a `claude -p --output-format json` answer: input, output and cache."""
    return harnesses._tokens_of(env.get("usage"))


def result_of(harness: str, stdout: str, before: int | dict = 0,
              model: str = "") -> tuple[str, float | None, int | None, str]:
    """(text, cost, tokens, session) of one run of a tool; `model` is what it was asked to run on
    (a tool that prints tokens and no price is priced from it)."""
    h = harnesses.get(harness)
    return h.outcome(stdout, before, model) if h else harnesses.json_result(stdout, before)


def codex_thread_usage(thread: str, env: dict | None = None) -> dict | None:
    """What a Codex thread has used so far: the last `token_count` total in its rollout
    (`$CODEX_HOME/sessions/YYYY/MM/DD/rollout-<ts>-<thread>.jsonl`), which `exec resume` starts its
    running total from. None when there is none (a compressed rollout is not read)."""
    env = os.environ if env is None else env
    if not thread:
        return None
    home = Path(env["CODEX_HOME"]) if env.get("CODEX_HOME") else Path.home() / ".codex"
    usage = None
    for rollout in sorted((home / "sessions").glob(f"*/*/*/rollout-*-{glob.escape(thread)}.jsonl")):
        try:
            lines = rollout.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        for line in lines:
            if '"token_count"' not in line:
                continue
            try:
                payload = json.loads(line).get("payload")
            except (ValueError, AttributeError):
                continue
            info = payload.get("info") if isinstance(payload, dict) and payload.get("type") == "token_count" else None
            total = info.get("total_token_usage") if isinstance(info, dict) else None
            if harnesses._plain_tokens(total) is not None:
                usage = total
    return usage


codex_error = harnesses.codex_error


def run_proc(cmd: list[str], cwd: Path, env: dict, stdin: str | None,
             wait: Callable[[subprocess.Popen], None], harness: str = "") -> tuple[int, str, str]:
    """(exit code, stdout, stderr) of one harness call. Its output goes to temporary files, so a
    long answer or a stream of events never fills a pipe while `wait` polls the process."""
    with tempfile.TemporaryFile("w+") as out, tempfile.TemporaryFile("w+") as err:
        try:
            proc = subprocess.Popen(cmd, cwd=cwd, env=env, stdin=subprocess.PIPE if stdin is not None else None,
                                    stdout=out, stderr=err, text=True, start_new_session=True)
        except FileNotFoundError as e:
            raise tool_errors.missing(harness, cmd[0]) if harness else RuntimeError(f"{cmd[0]} not found") from e
        if stdin is not None:
            try:
                proc.stdin.write(stdin)
                proc.stdin.close()
            except (BrokenPipeError, OSError):
                pass
        wait(proc)
        out.seek(0)
        err.seek(0)
        return proc.returncode, out.read(), err.read()


def failure(harness: str, code: int, stdout: str, stderr: str) -> tool_errors.ToolError:
    """The error of a harness call that exited with `code` (its str(): "<harness> exited with <code>: …")."""
    h = harnesses.get(harness)
    why = (h.error(stdout) if h else "") or (stderr or stdout).strip()
    return tool_errors.ToolError(harness, why, code)


def names_session(harness: str) -> bool:
    """Whether a reading agent of this tool can be given its session's id up front and reopen it later."""
    h = harnesses.get(resolve(harness))
    return bool(h and h.read_session and resolve(harness) in IN_REPO)


def run_agent(harness: str, prompt: str, repo_root: Path, env: dict,
              cancel: threading.Event, model: str = "", web: bool = False, session: str = "",
              reopen: bool = False) -> tuple[str, float | None, int | None]:
    """One harness step. Claude reads the repository (read-only tools, plus web search and fetch
    when `web`), Codex too (a read-only sandbox, live web search when `web`); agy works in an
    empty temp dir. `session` names its session (a tool that `names_session`), `reopen` goes on in it
    with `prompt` as the next message. Raises RuntimeError on failure, InterruptedError when `cancel` is set."""

    def wait(proc: subprocess.Popen) -> None:
        deadline = time.monotonic() + AGENT_TIMEOUT_S
        with halt.running(proc, env.get("ORKCRAFT_ORC") or harness, agent=True):   # 🛑 Halt All kills it: Halted
            while proc.poll() is None:
                if cancel.wait(0.2) or time.monotonic() > deadline:
                    proc.terminate()
                    try:
                        proc.wait(5)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                    if cancel.is_set():
                        raise InterruptedError("restarted by a new event")
                    raise RuntimeError(f"no answer within {AGENT_TIMEOUT_S} s")

    harness = resolve(harness)
    with tempfile.TemporaryDirectory(prefix="orkcraft-handler-") as scratch:
        workdir = repo_root if harness in IN_REPO else Path(scratch)
        cmd = _harness_cmd(harness, prompt, Path(scratch), model, web)
        if session and (h := harnesses.get(harness)) and h.read_session:
            cmd = cmd + h.read_session(session, reopen)
        tool_env = h.env("read", scratch) if (h := harnesses.get(harness)) else {}
        run_env = {**os.environ, **tool_env, **env}
        if telemetry.charged(run_env):                    # the session hook records what it was for
            run_env = {**telemetry.purpose_env(), **run_env}
        code, stdout, stderr = run_proc(cmd, workdir, run_env, harness_stdin(harness, prompt), wait, harness)
    if code != 0:
        raise failure(harness, code, stdout, stderr)
    result = result_of(harness, stdout, model=model)[:3]
    what = dict(tokens=result[2], building=telemetry.building_of(env), model=model)
    if not telemetry.charged(run_env):                    # no ORKCRAFT_RUN: its transcript is not this run's
        telemetry.charge(result[1], f"{harness} agent", **what)
    else:
        telemetry.noted(result[1], f"{harness} agent", **what)
    return result


def examples_file(repo_root: Path, building_id: str, orc_id: str) -> Path:
    return repo_root / EXAMPLES_DIR / building_id / f"{orc_id}.jsonl"


def read_examples(repo_root: Path, building_id: str, orc_id: str, limit: int = 50) -> list[dict]:
    """Newest last; malformed lines are skipped."""
    try:
        lines = examples_file(repo_root, building_id, orc_id).read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    out = []
    for line in lines[-limit:]:
        try:
            e = json.loads(line)
        except ValueError:
            continue
        if isinstance(e, dict) and isinstance(e.get("inputs"), list) and isinstance(e.get("output"), str):
            out.append(e)
    return out


def steward_steps(b: ts.BuildingSpec, goal: str | None = None, own: str = "") -> list[dict]:
    """The one step a road rule runs as: its steward's tool (its first harness step, else the machine's
    main tool) at the tier `steward.pick` names for `listen` under `goal` (the goal in force); `own`, the
    rule's own tier, comes before them all (docs/design/steward-listens.md §7)."""
    from orkcraft.realm import steward          # it imports this module
    tool = steward.harness_for(b) or harnesses.MAIN
    p = steward.pick(b, "listen", tool, goal=goal, own=own)
    step = {"role": "run", "harness": tool}
    if p.tier:
        step["tier"] = p.tier
    elif p.model:
        step["model"] = p.model
    return [step]
