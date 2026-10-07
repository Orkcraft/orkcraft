"""⚙️ The Mill: a map over what arrives — one step per line, strictly in order.

What arrives (text, a file's content, a node id) goes through the steps and comes out changed: one
cart in, one result out (`mill.done`, a map) and, when the result is a list of records, one cart per
record (`mill.item`, a flat map). A value is either text or a list of records; a step turns one into
the other where it says so. The steps are scripts and rules, no model — except `agent:`, the step
for what a script cannot do, and the `|| agent:` fallback of a script that fails.

    lines                       text → one record per line {n, line}
    grep: <regex>               keep lines / records that match        drop: <regex>  the others
    replace: <regex> => <with>  on text (\\1 for groups)
    trim · lower · dedupe       on text lines
    csv · json                  text → records (header row / a JSON list or object)
    extract: <field> = <regex>  first group (or match) of each record's line/text → a field
    pick: a, b                  keep these fields
    sort: <field> [desc] [num|text]   numbers sort as numbers when every value is one (or say num)
    limit: <n>
    filter: <field> <eq|ne|contains|matches|gt|ge|lt|le> <value>
                                gt…le compare numbers, else text (ISO dates and times compare right)
    count                       records → {count: n}
    to_json                     records → JSON text        template: <md with {field}>  → lines
    join[: <sep>]               lines → text (\\n, \\t; "quoted" keeps edge spaces)
    script: <command>           the value on stdin, stdout is the new text (timeout, no shell, and only
                                the safe environment plus the names in the building's `env`)
    script: <command> || agent: <ask>   when the script fails, an agent does the step instead
    agent: <ask>                a read-only agent changes the value as asked, its answer is the new text

`run(steps, text)` never raises: (output text, error). `run_full` also gives the records.
"""
from __future__ import annotations

import csv
import io
import json
import re
import os
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from orkcraft.realm import chains, jobs

MAX_RECORDS = 5000
TRACE_LIMIT = 4000                # what a run keeps of each step's output (`run_full(trace=…)`)
STEP_NAMES = ("lines", "grep", "drop", "replace", "trim", "lower", "dedupe", "csv", "json", "extract", "pick",
              "sort", "limit", "filter", "count", "to_json", "template", "join", "script", "agent")
MODEL_STEPS = ("agent",)
FILTER_OPS = ("eq", "ne", "contains", "matches", "gt", "ge", "lt", "le")
FALLBACK = re.compile(r"\s\|\|\s*agent\s*:")       # `script: cmd || agent: ask` (scripts run without a shell)
# What a script step sees of the environment: enough to run, no tokens. A building adds names in `env`.
SAFE_ENV = ("PATH", "HOME", "USER", "LOGNAME", "SHELL", "LANG", "LANGUAGE", "TERM", "TZ", "TMPDIR", "TEMP", "TMP",
            "SYSTEMROOT", "PYTHONIOENCODING")

Agent = Callable[[str, str], str]        # (ask, input text) → the new text


@dataclass
class Result:
    text: str
    records: list | None = None          # the result as records (a flat map's items), None when it is text
    error: str = ""
    agent_steps: int = 0                 # how many steps an agent did (an `agent:` or a script's fallback)


def _edge(arg: str) -> str:
    """One space after the colon or the arrow is syntax; "quoted" keeps the spaces at the edges."""
    arg = arg[1:] if arg.startswith(" ") else arg
    q = arg.strip()
    return q[1:-1] if len(q) >= 2 and q[0] == q[-1] == '"' else arg


def parse(step: str) -> tuple[str, str]:
    name, _, arg = str(step).partition(":")
    name = name.strip().lower()
    if name not in STEP_NAMES:
        raise ValueError(f"unknown step {name!r}; steps: {', '.join(STEP_NAMES)}")
    if name in ("join", "replace"):                     # "join: , " keeps its spaces
        return name, arg
    return name, arg.strip()


def _replace_parts(arg: str) -> tuple[str, str]:
    if "=>" not in arg:
        raise ValueError("say replace: <regex> => <with> (an empty <with> deletes)")
    pat, _, rep = arg.partition("=>")
    return pat.strip(), _edge(rep.rstrip("\n"))


def _extract_parts(arg: str) -> tuple[str, str]:
    field, eq, rx = arg.partition("=")
    if not eq or not field.strip() or not rx.strip():
        raise ValueError("say extract: <field> = <regex>")
    return field.strip(), rx.strip()


def _filter_parts(arg: str) -> tuple[str, str, str]:
    field, how, value = (arg.split(" ", 2) + ["", ""])[:3]
    if how not in FILTER_OPS:
        raise ValueError(f"say filter: <field> <{'|'.join(FILTER_OPS)}> <value>")
    return field, how, value


def _script_parts(arg: str) -> tuple[str, str]:
    """(command, the agent's ask when the script fails — or '')."""
    m = FALLBACK.search(arg)
    if not m:
        return arg.strip(), ""
    return arg[:m.start()].strip(), arg[m.end():].strip()


def check(steps: list[str]) -> list[str]:
    """Problems of a step list, before it runs (bad names, bad regexes, bad arguments)."""
    out = []
    for i, step in enumerate(steps, 1):
        try:
            name, arg = parse(step)
            if name in ("grep", "drop"):
                re.compile(arg)
            elif name == "replace":
                re.compile(_replace_parts(arg)[0])
            elif name == "extract":
                re.compile(_extract_parts(arg)[1])
            elif name == "filter":
                field, how, value = _filter_parts(arg)
                if how == "matches":
                    re.compile(value)
            elif name == "limit" and arg:
                int(arg)
            elif name == "sort" and not arg:
                raise ValueError("say sort: <field> [desc] [num|text]")
            elif name == "script":
                cmd, ask = _script_parts(arg)
                if not cmd:
                    raise ValueError("say script: <command>")
                if FALLBACK.search(f" {arg}") and not ask:
                    raise ValueError("say what the agent should do after || agent:")
            elif name == "agent" and not arg:
                raise ValueError("say agent: <what to do with the value>")
        except (ValueError, IndexError, re.error) as e:
            out.append(f"step {i} ({step[:30]}): {e}")
    return out


def model_steps(steps: list[str]) -> int:
    """How many steps may call a model: `agent:` and a script's `|| agent:` fallback."""
    n = 0
    for step in steps:
        try:
            name, arg = parse(step)
        except ValueError:
            continue
        n += name in MODEL_STEPS or (name == "script" and bool(_script_parts(arg)[1]))
    return n


def script_env(names: list[str] | tuple[str, ...] = ()) -> dict[str, str]:
    """The environment of a script step: the safe names, the locale, and what the building allows."""
    keep = set(SAFE_ENV) | {str(n) for n in names}
    return {k: v for k, v in os.environ.items() if k in keep or k.startswith("LC_")}


def agent_prompt(ask: str, text: str) -> str:
    return ("You are the Miller of a Mill in Orkcraft: one step of a pipeline that changes what passes "
            "through it. Change the input as asked and answer with the result only — no comments, no code "
            "fences, nothing around it; the next step reads your answer as it is.\n\n"
            f"## What to do\n\n{ask}\n\n## Input\n\n{text}")


def _num(v: Any) -> float | None:
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    try:
        return float(str(v).strip().replace("_", ""))
    except (TypeError, ValueError):
        return None


def _compare(have: Any, how: str, want: str) -> bool:
    if have is None or have == "":
        return False
    a, b = _num(have), _num(want)
    left, right = (a, b) if a is not None and b is not None else (chains._text(have), want)
    return {"gt": left > right, "ge": left >= right, "lt": left < right, "le": left <= right}[how]


def _sort_key(by: str, numeric: bool) -> Callable[[Any], Any]:
    def key(r: Any) -> Any:
        v = r.get(by) if isinstance(r, dict) else r
        if numeric:
            n = _num(v)
            return (n is None, n if n is not None else 0.0)
        return "" if v is None else str(v)
    return key


def _escapes(sep: str) -> str:
    return re.sub(r"\\([nt\\])", lambda m: {"n": "\n", "t": "\t"}.get(m.group(1), "\\"), sep)


def _text(v: Any) -> str:
    if isinstance(v, list):
        return "\n".join(r if isinstance(r, str) else json.dumps(r, ensure_ascii=False) for r in v)
    return "" if v is None else str(v)


def _lines(v: Any) -> list:
    return v if isinstance(v, list) else _text(v).splitlines()


def _hay(r: Any) -> str:
    if isinstance(r, dict):
        return str(r.get("line", r.get("text", json.dumps(r, ensure_ascii=False))))
    return str(r)


def _step(name: str, arg: str, v: Any, script: Callable[[str, str], str], agent: Agent) -> Any:
    if name == "lines":
        return [{"n": i, "line": ln} for i, ln in enumerate(_text(v).splitlines()[:MAX_RECORDS], 1)]
    if name in ("grep", "drop"):
        rx = re.compile(arg)
        keep = name == "grep"
        return [r for r in _lines(v) if bool(rx.search(_hay(r)[:chains.FIELD_CHARS])) == keep]
    if name == "replace":
        pat, rep = _replace_parts(arg)
        return re.sub(pat, rep, _text(v))
    if name == "trim":
        return "\n".join(ln.strip() for ln in _text(v).splitlines() if ln.strip())
    if name == "lower":
        return _text(v).lower()
    if name == "dedupe":
        return "\n".join(dict.fromkeys(_text(v).splitlines()))
    if name == "csv":
        return list(csv.DictReader(io.StringIO(_text(v))))[:MAX_RECORDS]
    if name == "json":
        data = json.loads(_text(v))
        return (data if isinstance(data, list) else [data])[:MAX_RECORDS]
    if name == "extract":
        field, rx = _extract_parts(arg)
        pattern = re.compile(rx)
        out = []
        for r in _lines(v):
            rec = r if isinstance(r, dict) else {"line": r}
            m = pattern.search(_hay(rec)[:chains.FIELD_CHARS])
            out.append({**rec, field: (m.group(1) if m and m.groups() else m.group(0) if m else None)})
        return out
    if name == "pick":
        fields = [f.strip() for f in arg.split(",") if f.strip()]
        return [{f: r.get(f) for f in fields if f in r} for r in _lines(v) if isinstance(r, dict)]
    if name == "sort":
        by, *how = arg.split()
        items = _lines(v)
        if "num" in how:
            numeric = True
        elif "text" in how:
            numeric = False
        else:                                           # numbers when every value is one
            vals = [r.get(by) if isinstance(r, dict) else r for r in items]
            numeric = bool(vals) and all(_num(x) is not None for x in vals if x not in (None, ""))
        return sorted(items, key=_sort_key(by, numeric), reverse="desc" in how)
    if name == "limit":
        return _lines(v)[: int(arg or 10)]
    if name == "filter":
        field, how, value = _filter_parts(arg)
        recs = [r if isinstance(r, dict) else {"line": r} for r in _lines(v)]
        if how in ("gt", "ge", "lt", "le"):
            return [r for r in recs if _compare(r.get(field), how, value)]
        op = {"field": field, "cmp": how, "value": value}
        return [r for r in recs if chains._cmp(r, op)]
    if name == "count":
        return [{"count": len(_lines(v))}]
    if name == "to_json":
        return json.dumps(_lines(v), ensure_ascii=False, indent=2)
    if name == "template":
        return [chains._fill(arg, r if isinstance(r, dict) else {"line": r}) for r in _lines(v)]
    if name == "join":
        sep = _escapes(_edge(arg.rstrip("\n"))) if arg.strip() else "\n"
        return sep.join(_hay(r) if isinstance(r, dict) else str(r) for r in _lines(v))
    if name == "script":
        cmd, ask = _script_parts(arg)
        try:
            return script(cmd, _text(v))
        except InterruptedError:
            raise
        except Exception as e:
            if not ask:
                raise
            try:
                return agent(ask, _text(v))
            except Exception as e2:
                raise RuntimeError(f"the script failed ({e}), then the agent too: {e2}") from e2
    if name == "agent":
        return agent(arg, _text(v))
    raise ValueError(name)


def default_agent(repo_root: Path, cancel: threading.Event, model: str = "",
                  spent: Callable[[float | None], None] | None = None, harness: str = "main") -> Agent:
    """A read-only agent on `harness` (the main tool unless its steward names one; it may read the repository,
    never change it) as the `agent:` step; `spent` hears what each call cost (None when the CLI does not say)."""
    from orkcraft.realm import roads

    def ask(what: str, text: str) -> str:
        out, cost, _ = roads.run_agent(harness, agent_prompt(what, text), repo_root, {}, cancel, model)
        if spent is not None:
            spent(cost)
        return out.strip()
    return ask


def run_full(steps: list[str], text: str, repo_root: Path | None = None, cancel: threading.Event | None = None,
             agent: Agent | None = None, env: list[str] | tuple[str, ...] = (),
             trace: list[dict] | None = None) -> Result:
    """Every step in order; never raises — a failing step is the result's error, with what came before it.
    `trace` gets each step's output (`{"step", "out"}`, cut to TRACE_LIMIT) or its error (`{"step", "error"}`)."""
    cancel = cancel or threading.Event()
    root = repo_root or Path.cwd()
    agent = agent or default_agent(root, cancel)
    used = [0]

    def script(cmd: str, stdin: str) -> str:
        return jobs.run_script(cmd, stdin, root, cancel, base_env=script_env(env))[0]

    def counted(ask: str, stdin: str) -> str:
        used[0] += 1
        return agent(ask, stdin)

    v: Any = text
    for i, step in enumerate(steps, 1):
        try:
            name, arg = parse(step)
            v = _step(name, arg, v, script, counted)
        except Exception as e:  # a failing step is the run's result, never a crash
            if trace is not None:
                trace.append({"step": str(step), "error": str(e)[:TRACE_LIMIT]})
            return Result(_text(v), None, f"step {i} ({str(step)[:40]}): {e}", used[0])
        if trace is not None:
            out = _text(v)
            trace.append({"step": str(step), "out": out[:TRACE_LIMIT] + ("…" if len(out) > TRACE_LIMIT else "")})
    return Result(_text(v), v if isinstance(v, list) else None, "", used[0])


def run(steps: list[str], text: str, repo_root: Path | None = None, cancel: threading.Event | None = None,
        agent: Agent | None = None, env: list[str] | tuple[str, ...] = ()) -> tuple[str, str]:
    """(output, error) — the error names the step that failed."""
    r = run_full(steps, text, repo_root, cancel, agent, env)
    return r.text, r.error


def items(records: list | None) -> list[str]:
    """The flat map: each record of a result as the value of its own cart (a JSON object, or the line)."""
    return [r if isinstance(r, str) else json.dumps(r, ensure_ascii=False) for r in (records or [])[:MAX_RECORDS]]
