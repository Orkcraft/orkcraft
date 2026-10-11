"""📜 Every model call, kept: a Test bench run's in its run folder, the town's by day and building.

    with call_log.kept(folder / "calls", "building"):   the calls in this block are kept there, as this side's
        …
    call_log.keep_days(root)                             from now on, every other call goes to the day's log
    call_log.record(env, "work", harness, model, prompt, stdout, stderr, code, seconds, cost, tokens, …)
    call_log.read(folder)                                the lines, oldest first
    call_log.totals(lines)                               by side, ork and purpose: calls, seconds, tokens, $

`calls.jsonl` holds one line per call: when, which side, who (an ork, the steward), what it was for, the tool and
model, its seconds, exit code, cost, tokens and the usage the tool printed (input, output, cache). The call itself
goes gzipped beside it (`<n>-<who>.json.gz`): the prompt, the tool's whole output, its errors, and the way it worked
when the tool keeps one (`trail`: Claude Code's transcript of the session, with its thinking and tool calls; agy's
brain folder). The environment is never written.

A bench run's calls go to its `calls/` (`kept`). Outside one, once the town said where (`keep_days`), a call goes to
`.orkcraft/logs/<day>/<building>/` (realm/day_log.py keeps and clears those days); else it is not kept.

The calls come from every seam that starts an AI tool: an ork's work and a reader (realm/jobs.py), a road's agent
(realm/road_agents.py), a one-off answer (realm/builders.py `ask`: a steward's, the retros', the Council's) and a
connector's look (realm/feeds_agent.py).
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
DAYS = Path(".orkcraft") / "logs"
TOWN = "town"                     # the day's folder of a call no building made
TRAIL_MAX = 8 * 1024 * 1024       # characters of a session's trail kept with a call (its end)
_LOCK = threading.Lock()
_KEPT: dict = {"folder": None, "side": "", "days": None}
_COUNT: dict[Path, int] = {}
_SAFE = re.compile(r"[^A-Za-z0-9_-]+")


@contextlib.contextmanager
def kept(folder: Path, side: str = ""):
    """The calls made in this block, on any thread, are kept in `folder` as `side`'s."""
    with _LOCK:
        outer = {k: _KEPT[k] for k in ("folder", "side")}
        folder.mkdir(parents=True, exist_ok=True)
        _KEPT.update(folder=folder, side=side)
    try:
        yield folder
    finally:
        with _LOCK:
            _KEPT.update(outer)


def keep_days(root: Path | None) -> None:
    """Every call outside a bench run goes to `root`'s day log from now on (None: none is kept)."""
    with _LOCK:
        _KEPT["days"] = root


def day_folder(root: Path, day: str, building: str) -> Path:
    return root / DAYS / day / (_SAFE.sub("-", building)[:80] or TOWN)


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


def session_of(stdout: str) -> str:
    """The session the tool says it ran in ("" when it says none)."""
    try:
        return harnesses.json_result(stdout)[3]
    except (ValueError, TypeError, IndexError):
        return ""


def trail(harness: str, session: str, workdir: Path | None) -> str:
    """How the call went, where the tool keeps it: Claude Code's transcript of the session (its thinking, every tool
    call and result), agy's brain folder; "" for a tool whose output already holds it (codex) or keeps none."""
    from orkcraft.sources import sessions
    if not session or _SAFE.search(session):
        return ""                                            # a session id is a name, never a path
    try:
        if harness == "claude" and workdir is not None:
            path = sessions.claude_projects_dir(workdir) / f"{session}.jsonl"
            return path.read_text(encoding="utf-8", errors="replace")[-TRAIL_MAX:] if path.is_file() else ""
        if harness == "agy":
            folder = sessions.agy_brain_dir() / session
            parts = [f"## {p.relative_to(folder)}\n{p.read_text(encoding='utf-8', errors='replace')}"
                     for p in sorted(folder.rglob("*")) if p.is_file()] if folder.is_dir() else []
            return "\n\n".join(parts)[-TRAIL_MAX:]
    except OSError:
        return ""
    return ""


def record(env: dict | None, mode: str, harness: str, model: str, prompt: str, stdout: str, stderr: str,
           code: int, seconds: float, cost: float | None = None, tokens: int | None = None,
           session: str = "", workdir: Path | None = None, who: str = "", purpose: str = "") -> None:
    """One call, where calls are kept now. Never raises: a call is not lost for its log. `who` and `purpose` name
    a call that carries no ork (`ORKCRAFT_ORC`) or was not tagged (a one-off `-p`, a connector's look)."""
    orc = str((env or {}).get("ORKCRAFT_ORC") or "")
    building, _, ork = orc.partition("/")
    with _LOCK:
        folder, side, days = _KEPT["folder"], _KEPT["side"], _KEPT["days"]
        if folder is None and days is None:
            return
        if folder is None:
            side = ""
            folder = day_folder(days, dt.date.today().isoformat(), building or telemetry.building_now() or TOWN)
        if folder not in _COUNT:
            _COUNT[folder] = len(read(folder))
        _COUNT[folder] += 1
        n = _COUNT[folder]
    who = ork or who or ("" if side == "bare" else "agent")
    raw = f"{n:03d}-{_SAFE.sub('-', who or side or 'call')[:40]}.json.gz"
    session = session or session_of(stdout)
    line = {"n": n, "at": dt.datetime.now().isoformat(timespec="seconds"), "side": side, "who": who,
            "purpose": purpose or telemetry.purpose_now(), "mode": mode, "tool": harness, "model": model,
            "seconds": round(seconds, 1), "code": code, "cost": cost, "tokens": tokens, "usage": usage_of(stdout),
            "session": session, "prompt_chars": len(prompt or ""), "output_chars": len(stdout or ""), "raw": raw}
    try:
        folder.mkdir(parents=True, exist_ok=True)
        with gzip.open(folder / raw, "wt", encoding="utf-8") as f:
            json.dump({"prompt": prompt, "stdout": stdout, "stderr": stderr,
                       "trail": trail(harness, session, workdir)}, f, ensure_ascii=False)
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
    """The call itself: its prompt, the tool's output, its errors and its trail ({} when it is gone)."""
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
