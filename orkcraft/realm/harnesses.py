"""The AI tools orks think with — one registry, so nothing else names a CLI.

    h = harnesses.get("codex")               # None for an unknown id
    h.ask(prompt, folder, model)             # argv of a one-shot answer in an empty folder (no edits)
    h.read(prompt, workdir, model, web)      # argv of an agent that reads (the repository when `in_repo`)
    h.work(prompt, workdir, model, resume)   # argv of an agent that may change files in `workdir`
    h.result(stdout, before)                 # (text, cost USD | None, tokens | None, session id)
    harnesses.main(enabled, chosen)          # the tool decisions run on: the chosen one, else the first on
    harnesses.model_on("agy", "haiku")       # a model or tier of any tool, on this one

A step names its tool (`{"harness": "codex"}`); `MAIN` ("main") means the machine's main tool,
resolved when it runs. The prompt goes in as one argv item (or on stdin, `stdin_prompt`), never
through a shell. A tool that prints no price reports a cost of None, never $0.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable

from orkcraft.env import getenv

MAIN = "main"                  # a step on the machine's main tool
TIERS = ("elder", "warrior", "laborer")


# -- output ---------------------------------------------------------------------------------------

def _tokens_of(usage) -> int | None:
    """All tokens of a usage block: input, output and cache (Claude's names, and the plain ones)."""
    if not isinstance(usage, dict):
        return None
    keys = ("input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")
    vals = [usage[k] for k in keys if isinstance(usage.get(k), int)]
    return sum(vals) if vals else None


def json_result(stdout: str, before: int = 0) -> tuple[str, float | None, int | None, str]:
    """One JSON envelope (`claude -p --output-format json`, agy's): the answer under result / response
    / text / output, `total_cost_usd`, `usage` and `session_id`; plain text when it is not JSON."""
    out = stdout.strip()
    try:
        env = json.loads(out)
    except ValueError:
        return out, None, None, ""
    if not isinstance(env, dict):
        return out, None, None, ""
    cost = env.get("total_cost_usd")
    session = str(env.get("session_id") or "")
    for key in ("result", "response", "text", "output"):
        if isinstance(env.get(key), str):
            return env[key], float(cost) if isinstance(cost, (int, float)) else None, _tokens_of(env.get("usage")), session
    return out, None, None, session


def json_lines(stdout: str) -> list[dict]:
    events = []
    for line in stdout.splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if isinstance(event, dict):
            events.append(event)
    return events


def _plain_tokens(usage) -> int | None:
    vals = [usage[k] for k in ("input_tokens", "output_tokens") if isinstance(usage.get(k), int)] \
        if isinstance(usage, dict) else []
    return sum(vals) if vals else None


def codex_result(stdout: str, before: int = 0) -> tuple[str, float | None, int | None, str]:
    """(text, cost, tokens, session) of `codex exec --json`: the last agent message, the tokens of this
    run (cached input is part of the input) and the thread id. Codex prints no price: the cost is None,
    never $0. Each `turn.completed.usage` is the thread's running total (openai/codex
    `usage_from_last_total`), so the last one counts, less `before`: what the thread had already used
    when this run resumed it (`roads.codex_thread_total`)."""
    text, total, session = "", None, ""
    for event in json_lines(stdout):
        kind, item = event.get("type"), event.get("item")
        if kind == "thread.started":
            session = str(event.get("thread_id") or "")
        elif kind == "item.completed" and isinstance(item, dict) and item.get("type") == "agent_message":
            text = str(item.get("text") or "")
        elif kind == "turn.completed" and (tokens := _plain_tokens(event.get("usage"))) is not None:
            total = tokens
    return text.strip(), None, None if total is None else max(total - before, 0), session


def codex_error(stdout: str) -> str:
    """Why a `codex exec --json` run failed, from its events ("" when they do not say)."""
    for event in reversed(json_lines(stdout)):
        error = event.get("error")
        if event.get("type") == "turn.failed" and isinstance(error, dict) and error.get("message"):
            return str(error["message"])
        if event.get("type") == "error" and event.get("message"):
            return str(event["message"])
    return ""


# -- the tools ------------------------------------------------------------------------------------

Cmd = Callable[..., list[str]]


@dataclass(frozen=True)
class Harness:
    id: str
    title: str                       # what a person reads: "Claude Code"
    default_bin: str
    install: str                     # how to get it, shown when it is missing
    login: str                       # how to log in, shown when it is not
    models: dict[str, str]           # tier → model
    ask_cmd: Cmd                     # (h, prompt, folder, model) → argv: a one-shot answer
    read_cmd: Cmd                    # (h, prompt, workdir, model, web) → argv: an agent that reads
    work_cmd: Cmd                    # (h, prompt, workdir, model, resume) → argv: an agent that edits workdir
    result: Callable[[str, int], tuple[str, float | None, int | None, str]] = json_result
    error: Callable[[str], str] = lambda stdout: ""
    in_repo: bool = True             # a reading agent runs in the repository (else in an empty folder)
    resumable: bool = False          # `work(resume=…)` continues a session
    stdin_prompt: bool = False       # the prompt goes on stdin, not argv
    default_model: str = ""          # what it runs on when a step names no model ("" its own default)
    new_cmd: Callable[["Harness"], list[str]] | None = None          # an interactive session
    resume_cmd: Callable[["Harness", str], list[str]] | None = None  # … reopened
    deploys: bool = False            # an interactive session can start on a first prompt (argv)
    web: bool = False                # its reading agent can search the web on request
    fits: tuple[str, ...] = ("code",)   # the work it is liked for in the Barracks: "code", "docs"
    task_models: dict = field(default_factory=dict)   # "code" / "docs" → model, when a step names none
    mark: str = "?"                  # one cell on the map and in schemes (realm/looks.py)
    color: str = "bold"              # … in its colour
    extra: dict = field(default_factory=dict)

    @property
    def bin(self) -> str:
        return getenv(f"{self.id.upper()}_BIN") or self.default_bin

    def ask(self, prompt: str, folder: str | Path, model: str = "") -> list[str]:
        return self.ask_cmd(self, prompt, str(folder), model_on(self.id, model))

    def read(self, prompt: str, workdir: str | Path, model: str = "", web: bool = False) -> list[str]:
        return self.read_cmd(self, prompt, str(workdir), model_on(self.id, model), web)

    def work(self, prompt: str, workdir: str | Path, model: str = "", resume: str = "") -> list[str]:
        return self.work_cmd(self, prompt, str(workdir), model_on(self.id, model), resume)

    def stdin(self, prompt: str) -> str | None:
        return prompt if self.stdin_prompt else None

    def interactive(self, prompt: str = "", resume: str = "") -> list[str] | None:
        """An interactive session: new, reopened (`resume`) or starting on `prompt`; None when it cannot."""
        if resume:
            return self.resume_cmd(self, resume) if self.resume_cmd else None
        cli = self.new_cmd(self) if self.new_cmd else [self.bin]
        prompt = prompt.strip()
        if not prompt:
            return cli
        if not self.deploys:
            return None
        return cli + ["Orders: " + prompt if prompt.startswith("-") else prompt]


# Claude Code ---------------------------------------------------------------------------------------

CLAUDE_READ_ONLY = ["--allowedTools", "Read,Grep,Glob",
                    "--disallowedTools", "Bash,Edit,Write,MultiEdit,NotebookEdit,WebFetch,WebSearch"]
CLAUDE_READ_WEB = ["--allowedTools", "Read,Grep,Glob,WebSearch,WebFetch",
                   "--disallowedTools", "Bash,Edit,Write,MultiEdit,NotebookEdit"]


def _model(flag: str, model: str) -> list[str]:
    return [flag, model] if model else []


def _claude_ask(h, prompt, folder, model):
    return [h.bin, "-p", prompt, "--output-format", "json", *_model("--model", model)]


def _claude_read(h, prompt, workdir, model, web):
    return [h.bin, "-p", prompt, "--output-format", "json", *(CLAUDE_READ_WEB if web else CLAUDE_READ_ONLY),
            *_model("--model", model)]


def _claude_work(h, prompt, workdir, model, resume):
    return [h.bin, "-p", prompt, "--output-format", "json", "--permission-mode", "acceptEdits",
            *_model("--model", model), *(["--resume", resume] if resume else [])]


# agy (Antigravity) -------------------------------------------------------------------------------

def _agy(h, prompt, workdir, model):
    return [h.bin, "--print", prompt, "--model", model or h.default_model, "--mode", "accept-edits", "--sandbox",
            "--add-dir", workdir, "--output-format", "json"]


# Codex -------------------------------------------------------------------------------------------

CODEX_WEB = {False: 'web_search="disabled"', True: 'web_search="live"'}   # Codex searches by default


def codex_exec(h, sandbox: str, model: str = "", web: bool = False, resume: str = "") -> list[str]:
    """`codex exec` with its prompt on stdin (`-`) and JSONL events on stdout, in the folder it is
    started in. The sandbox goes in as config: `exec resume` takes no `--sandbox`."""
    return [h.bin, "exec", *(["resume", resume] if resume else []), "-", "--json", "--skip-git-repo-check",
            "-c", f'sandbox_mode="{sandbox}"', "-c", CODEX_WEB[web], *_model("--model", model)]


REGISTRY: dict[str, Harness] = {}


def register(h: Harness) -> Harness:
    REGISTRY[h.id] = h
    return h


register(Harness(
    "claude", "Claude Code", "claude", "npm i -g @anthropic-ai/claude-code", "claude  (then /login)",
    {"elder": "opus", "warrior": "sonnet", "laborer": "haiku"},
    _claude_ask, _claude_read, _claude_work,
    resumable=True, deploys=True, web=True, mark="✻", color="bold #f59e0b",
    resume_cmd=lambda h, sid: [h.bin, "--resume", sid]))
register(Harness(
    "agy", "Antigravity", "agy", "see antigravity.google", "agy login",
    {"elder": "gemini-3.1-pro-high", "warrior": "gemini-3.8-flash-high", "laborer": "gemini-3.8-flash-low"},
    lambda h, p, f, m: _agy(h, p, f, m),
    lambda h, p, w, m, web: _agy(h, p, w, m),
    lambda h, p, w, m, r: _agy(h, p, w, m),
    in_repo=False, default_model="gemini-3.8-flash-high", mark="✦", color="bold #3b82f6", fits=("docs",),
    task_models={"code": "gemini-3.8-flash-high", "docs": "gemini-3.1-pro-high"},
    resume_cmd=lambda h, sid: [h.bin, "--conversation", sid]))
register(Harness(
    "codex", "Codex", "codex", "npm i -g @openai/codex", "codex login",
    {"elder": "gpt-6-astra", "warrior": "gpt-6.1-sol", "laborer": "gpt-6-luna"},
    lambda h, p, f, m: codex_exec(h, "read-only", m),
    lambda h, p, w, m, web: codex_exec(h, "read-only", m, web),
    lambda h, p, w, m, r: codex_exec(h, "workspace-write", m, resume=r),
    result=codex_result, error=codex_error, resumable=True, stdin_prompt=True, deploys=True, web=True,
    mark="⌬", color="bold #10a37f",
    resume_cmd=lambda h, sid: [h.bin, "resume", sid]))


# -- lookups --------------------------------------------------------------------------------------

def ids() -> tuple[str, ...]:
    """Every tool, in the order the main one is picked when none is chosen."""
    return tuple(REGISTRY)


def get(harness_id: str) -> Harness | None:
    return REGISTRY.get(harness_id)


def need(harness_id: str) -> Harness:
    h = REGISTRY.get(harness_id)
    if h is None:
        raise RuntimeError(f"harness {harness_id!r} is not one of {', '.join(REGISTRY)}")
    return h


def title(harness_id: str) -> str:
    h = REGISTRY.get(harness_id)
    return h.title if h else harness_id


def main(enabled: Iterable[str] = (), chosen: str = "") -> str | None:
    """The tool decisions run on: `chosen` when it is on, else the first tool on; None when none is."""
    on = [t for t in enabled if t in REGISTRY]
    if chosen in on:
        return chosen
    return next((t for t in REGISTRY if t in on), None)


def tier_of_model(model: str) -> str | None:
    """Which tier a model of any tool is: its own table first, then the families' words."""
    m = (model or "").lower()
    if not m:
        return None
    if m in TIERS:
        return m
    for h in REGISTRY.values():
        for tier, name in h.models.items():
            if m == name.lower():
                return tier
    if "opus" in m or "fable" in m or ("gemini" in m and "pro" in m) or ("gpt" in m and "astra" in m):
        return "elder"
    if "haiku" in m or ("flash" in m and ("low" in m or "lite" in m)) or ("gpt" in m and "luna" in m):
        return "laborer"
    if "sonnet" in m or "flash" in m or ("gpt" in m and ("sol" in m or "terra" in m)):
        return "warrior"
    return None


def _owner(model: str) -> str | None:
    """The tool whose tier table names `model`."""
    m = model.lower()
    return next((h.id for h in REGISTRY.values() if m in (v.lower() for v in h.models.values())), None)


def model_on(harness_id: str, model: str) -> str:
    """`model` as `harness_id` runs it: a tier word names its model there; a model another tool's
    table names becomes that tier's model here; anything else (its own, or one we do not know) stays."""
    h = REGISTRY.get(harness_id)
    if not model or h is None:
        return model or ""
    if model in TIERS:
        return h.models.get(model, "")
    owner = _owner(model)
    if owner is not None and owner != harness_id:
        tier = tier_of_model(model)
        return h.models.get(tier, "") if tier else ""
    return model
