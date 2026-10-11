"""📜 Every model call of a Test bench run, kept in its run folder: one line each, and the call itself.

    with call_log.kept(folder / "calls", "building"):   the calls in this block are kept there, as this side's
        …
    call_log.record(env, "work", harness, model, prompt, stdout, stderr, code, seconds, cost, tokens)
    call_log.read(folder / "calls")                      the lines, oldest first
    call_log.totals(lines)                               by side, ork and purpose: calls, seconds, tokens, $

`calls.jsonl` holds one line per call: when, which side, who (an ork, the steward), what it was for, the tool and
model, its seconds, exit code, cost, tokens and the usage the tool printed (input, output, cache). The prompt and
the tool's whole output go gzipped beside it (`<n>-<who>.json.gz`), to read when a line says something odd.

Only the bench keeps calls: outside a `kept` block `record` does nothing. The environment is never written.
"""
from __future__ import annotations

import contextlib
import datetime as dt
import gzip
import json
import re
import threading
from pathlib import Path

from orkcraft.realm import harnesses
from orkcraft.sources import telemetry

LINES = "calls.jsonl"
_LOCK = threading.Lock()
_KEPT: dict = {"folder": None, "side": "", "n": 0}
_SAFE = re.compile(r"[^A-Za-z0-9_-]+")


@contextlib.contextmanager
def kept(folder: Path, side: str = ""):
    """The calls made in this block, on any thread, are kept in `folder` as `side`'s."""
    with _LOCK:
        outer = dict(_KEPT)
        folder.mkdir(parents=True, exist_ok=True)
        _KEPT.update(folder=folder, side=side, n=len(read(folder)))
    try:
        yield folder
    finally:
        with _LOCK:
            _KEPT.update(outer)


def usage_of(stdout: str) -> dict:
    """The token counts the tool printed, as it named them: the envelope's `usage`, else its last event's."""
    found: dict = {}
    try:
        events = [json.loads(stdout)]
    except ValueError:
        events = harnesses.json_lines(stdout)
    for event in events:
        if not isinstance(event, dict):
            continue
        msg = event.get("message")
        for usage in (event.get("usage"), msg.get("usage") if isinstance(msg, dict) else None, event.get("tokens")):
            if isinstance(usage, dict):
                counts = {k: v for k, v in usage.items() if isinstance(v, int) and not isinstance(v, bool)}
                found = counts or found
    return found


def record(env: dict | None, mode: str, harness: str, model: str, prompt: str, stdout: str, stderr: str,
           code: int, seconds: float, cost: float | None = None, tokens: int | None = None) -> None:
    """One call, when the bench keeps calls. Never raises: a call is not lost for its log."""
    with _LOCK:
        folder, side = _KEPT["folder"], _KEPT["side"]
        if folder is None:
            return
        _KEPT["n"] += 1
        n = _KEPT["n"]
    who = str((env or {}).get("ORKCRAFT_ORC") or "").partition("/")[2] or ("" if side == "bare" else "agent")
    raw = f"{n:03d}-{_SAFE.sub('-', who or side or 'call')[:40]}.json.gz"
    line = {"n": n, "at": dt.datetime.now().isoformat(timespec="seconds"), "side": side, "who": who,
            "purpose": telemetry.purpose_now(), "mode": mode, "tool": harness, "model": model,
            "seconds": round(seconds, 1), "code": code, "cost": cost, "tokens": tokens, "usage": usage_of(stdout),
            "prompt_chars": len(prompt or ""), "output_chars": len(stdout or ""), "raw": raw}
    try:
        with gzip.open(folder / raw, "wt", encoding="utf-8") as f:
            json.dump({"prompt": prompt, "stdout": stdout, "stderr": stderr}, f, ensure_ascii=False)
        with _LOCK, (folder / LINES).open("a", encoding="utf-8") as f:
            f.write(json.dumps(line, ensure_ascii=False) + "\n")
    except OSError:
        pass


def read(folder: Path) -> list[dict]:
    try:
        text = (folder / LINES).read_text(encoding="utf-8")
    except OSError:
        return []
    out = []
    for row in text.splitlines():
        try:
            line = json.loads(row)
        except ValueError:
            continue
        if isinstance(line, dict):
            out.append(line)
    return out


def raw(folder: Path, line: dict) -> dict:
    """The call itself: its prompt, the tool's output and its errors ({} when it is gone)."""
    try:
        with gzip.open(folder / str(line.get("raw") or ""), "rt", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def totals(lines: list[dict]) -> list[dict]:
    """The calls by side, then by who and what for: [{side, who, purpose, calls, seconds, tokens, cost, usage}],
    in the order they first came."""
    rows: dict[tuple, dict] = {}
    for line in lines:
        key = (line.get("side") or "", line.get("who") or "", line.get("purpose") or "")
        row = rows.setdefault(key, {"side": key[0], "who": key[1], "purpose": key[2], "calls": 0, "seconds": 0.0,
                                    "tokens": 0, "cost": 0.0, "usage": {}})
        row["calls"] += 1
        row["seconds"] = round(row["seconds"] + float(line.get("seconds") or 0.0), 1)
        row["tokens"] += int(line.get("tokens") or 0)
        row["cost"] = round(row["cost"] + float(line.get("cost") or 0.0), 4)
        for k, v in (line.get("usage") or {}).items():
            if isinstance(v, int):
                row["usage"][k] = row["usage"].get(k, 0) + v
    return list(rows.values())
