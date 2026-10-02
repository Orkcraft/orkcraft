"""⚙️ The Mill: deterministic work, no model — one step per line.

What arrives (text, a file's content, a node id) goes through the steps in order. A value is
either text or a list of records; a step turns one into the other where it says so.

    lines                       text → one record per line {n, line}
    grep: <regex>               keep lines / records that match        drop: <regex>  the others
    replace: <regex> => <with>  on text (\\1 for groups)
    trim · lower · dedupe       on text lines
    csv · json                  text → records (header row / a JSON list or object)
    extract: <field> = <regex>  first group (or match) of each record's line/text → a field
    pick: a, b                  keep these fields          sort: <field> [desc]     limit: <n>
    filter: <field> <eq|ne|contains|matches> <value>
    count                       records → {count: n}
    to_json                     records → JSON text        template: <md with {field}>  → lines
    join[: <sep>]               lines → text
    script: <command>           the value on stdin, stdout is the new text (timeout, no shell)

`run(steps, text)` never raises: (output text, error).
"""
from __future__ import annotations

import csv
import io
import json
import re
import threading
from pathlib import Path
from typing import Any, Callable

from orkcraft.realm import chains, jobs

MAX_RECORDS = 5000
STEP_NAMES = ("lines", "grep", "drop", "replace", "trim", "lower", "dedupe", "csv", "json", "extract", "pick",
              "sort", "limit", "filter", "count", "to_json", "template", "join", "script")


def parse(step: str) -> tuple[str, str]:
    name, _, arg = str(step).partition(":")
    name = name.strip().lower()
    if name not in STEP_NAMES:
        raise ValueError(f"unknown step {name!r}; steps: {', '.join(STEP_NAMES)}")
    if name == "join":                                  # "join: , " keeps its spaces
        return name, arg[1:] if arg.startswith(" ") else arg
    return name, arg.strip()


def check(steps: list[str]) -> list[str]:
    """Problems of a step list, before it runs (bad names, bad regexes)."""
    out = []
    for i, step in enumerate(steps, 1):
        try:
            name, arg = parse(step)
            if name in ("grep", "drop"):
                re.compile(arg)
            elif name == "replace":
                re.compile(arg.split("=>", 1)[0].strip())
            elif name == "extract":
                re.compile(arg.split("=", 1)[1].strip())
        except (ValueError, IndexError, re.error) as e:
            out.append(f"step {i} ({step[:30]}): {e}")
    return out


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


def _step(name: str, arg: str, v: Any, script: Callable[[str, str], str]) -> Any:
    if name == "lines":
        return [{"n": i, "line": ln} for i, ln in enumerate(_text(v).splitlines(), 1)]
    if name in ("grep", "drop"):
        rx = re.compile(arg)
        keep = name == "grep"
        return [r for r in _lines(v) if bool(rx.search(_hay(r)[:chains.FIELD_CHARS])) == keep]
    if name == "replace":
        pat, _, rep = arg.partition("=>")
        return re.sub(pat.strip(), rep.strip(), _text(v))
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
        field, _, rx = arg.partition("=")
        pattern, field = re.compile(rx.strip()), field.strip()
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
        by, _, how = arg.partition(" ")
        return sorted(_lines(v), key=lambda r: str(r.get(by, "")) if isinstance(r, dict) else str(r),
                      reverse=how.strip() == "desc")
    if name == "limit":
        return _lines(v)[: int(arg or 10)]
    if name == "filter":
        field, how, value = (arg.split(" ", 2) + ["", ""])[:3]
        op = {"field": field, "cmp": how, "value": value}
        return [r for r in _lines(v) if chains._cmp(r if isinstance(r, dict) else {"line": r}, op)]
    if name == "count":
        return [{"count": len(_lines(v))}]
    if name == "to_json":
        return json.dumps(_lines(v), ensure_ascii=False, indent=2)
    if name == "template":
        return [chains._fill(arg, r if isinstance(r, dict) else {"line": r}) for r in _lines(v)]
    if name == "join":
        sep = arg.encode().decode("unicode_escape") if arg else "\n"
        return sep.join(_hay(r) if isinstance(r, dict) else str(r) for r in _lines(v))
    if name == "script":
        return script(arg, _text(v))
    raise ValueError(name)


def run(steps: list[str], text: str, repo_root: Path | None = None,
        cancel: threading.Event | None = None) -> tuple[str, str]:
    """(output, error) — the error names the step that failed."""
    cancel = cancel or threading.Event()

    def script(cmd: str, stdin: str) -> str:
        return jobs.run_script(cmd, stdin, repo_root or Path.cwd(), cancel)[0]

    v: Any = text
    for i, step in enumerate(steps, 1):
        try:
            name, arg = parse(step)
            v = _step(name, arg, v, script)
        except Exception as e:  # a failing step is the run's result, never a crash
            return _text(v), f"step {i} ({str(step)[:40]}): {e}"
    return _text(v), ""
