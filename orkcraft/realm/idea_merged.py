"""What reached `merge_into` without the person's eyes (spec 29c §1, §4; decisions §44.1, §44.4).

The runner appends each merged task to `<state_dir>/ideas/merged.jsonl`; the board shows the unseen ones until the
person looks (`seen`) or reverts one. The digest says once at each of the person's hours what merged meanwhile.

    add(state_dir, {"idea": "dark-mode", "task": "k1", "title": …, "commit": "ab12…", …})
    unseen(state_dir)                     # (the unseen, newest first, at most 20; how many beyond)
    mark(state_dir, idea="dark-mode", task="k1", seen=True)
    due(state_dir, [9, 13, 18])           # the digest of this hour, once frozen: {"at", "merged", "done", "spent"}

No face, no model; split from realm/ideas.py (its pages and states).
"""
from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path

from orkcraft.realm import ideas

FILE = "merged.jsonl"
DIGEST_FILE = "digest.json"
SHOWN = 20                     # of the unseen, the most the board lists
KEYS = ("idea", "task", "title", "goal", "subject", "commit", "tests", "cost", "estimate", "at", "seen", "reverted")


def _path(state_dir: Path) -> Path:
    return Path(state_dir) / "ideas" / FILE


def tests_line(tail: str) -> str:
    """The gate's count, as pytest ends its output: "14 passed", "14 passed, 1 skipped"; "" when none is there."""
    found = re.findall(r"\b(\d+ passed(?:, \d+ [a-z]+)*)", tail or "")
    return found[-1] if found else ""


def share(estimate: dict | None, weights: list[float], index: int) -> list[float]:
    """A task's share of its plan's estimate, `[low, high]`, by its weight among the plan's tasks."""
    est = estimate if isinstance(estimate, dict) else {}
    total = sum(weights) or 1.0
    part = (weights[index] if 0 <= index < len(weights) else 0.0) / total
    out = []
    for key in ("usd_low", "usd_high"):
        value = est.get(key)
        out.append(round(float(value) * part, 2) if isinstance(value, (int, float)) and not isinstance(value, bool)
                   else 0.0)
    return out


def _clean(row: dict) -> dict:
    out = {k: row.get(k) for k in KEYS}
    out["seen"], out["reverted"] = bool(row.get("seen")), bool(row.get("reverted"))
    for k in ("idea", "task", "title", "goal", "subject", "commit", "tests", "at"):
        out[k] = str(out[k] or "")
    est = row.get("estimate")
    out["estimate"] = est if isinstance(est, list) and len(est) == 2 else [0.0, 0.0]
    if "base" in row:                                  # where `merge_into` stood before: the revert's range
        out["base"] = str(row.get("base") or "")
    return out


def add(state_dir: Path, row: dict) -> dict:
    line = _clean({**row, "seen": False, "reverted": False})
    with ideas.LOCK:
        path = _path(state_dir)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(line, ensure_ascii=False) + "\n")
    return line


def rows(state_dir: Path) -> list[dict]:
    """Every line, oldest first; a broken line is skipped."""
    try:
        lines = _path(state_dir).read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    out = []
    for line in lines:
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict):
            out.append(_clean(row))
    return out


def unseen(state_dir: Path, limit: int = SHOWN) -> tuple[list[dict], int]:
    """The lines nobody looked at and nothing reverted, newest first (at most `limit`), and how many beyond."""
    waiting = [r for r in reversed(rows(state_dir)) if not r["seen"] and not r["reverted"]]
    return waiting[:limit], max(0, len(waiting) - limit)


def find(state_dir: Path, idea: str, task: str) -> dict | None:
    """The newest line of a task."""
    return next((r for r in reversed(rows(state_dir)) if r["idea"] == idea and r["task"] == task), None)


def mark(state_dir: Path, idea: str = "", task: str = "", **changes: object) -> int:
    """Change the lines of a task (both given), of an idea (only `idea`), or every line (neither): how many changed.
    `task` names the newest line of that task only."""
    with ideas.LOCK:
        all_rows = rows(state_dir)
        hit = [r for r in all_rows if (not idea or r["idea"] == idea) and (not task or r["task"] == task)]
        if idea and task:
            hit = hit[-1:]
        changed = 0
        for r in hit:
            if any(r.get(k) != v for k, v in changes.items()):
                r.update(changes)
                changed += 1
        if changed:
            ideas._write(_path(state_dir), "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in all_rows))
    return changed


# -- the digest (§4) --------------------------------------------------------------------------------

def slot(hours: list[int], now: dt.datetime | None = None) -> str:
    """The digest's hour this is ("2026-10-17T09"), or "" when the hour is none of the person's."""
    now = now or dt.datetime.now()
    return f"{now.date().isoformat()}T{now.hour:02d}" if now.hour in (hours or []) else ""


def summary(state_dir: Path) -> dict:
    """What merged unseen: tasks, the ideas among them now done, what they cost ("$0.42")."""
    waiting = [r for r in rows(state_dir) if not r["seen"] and not r["reverted"]]
    done = {r["idea"] for r in waiting if r["idea"] and _state(state_dir, r["idea"]) == "done"}
    spent = sum(float(r["cost"]) for r in waiting
                if isinstance(r["cost"], (int, float)) and not isinstance(r["cost"], bool))
    return {"merged": len(waiting), "done": len(done), "spent": f"${spent:.2f}"}


def _state(state_dir: Path, slug: str) -> str:
    try:
        return ideas.state(state_dir, slug)["state"]
    except ValueError:
        return ""


def due(state_dir: Path, hours: list[int], now: dt.datetime | None = None) -> dict | None:
    """The digest of this hour: frozen the first time it is asked in the hour (kept in `digest.json`, so a restart
    says it no second time), None outside the hours or when nothing was unseen then."""
    at = slot(hours, now)
    if not at:
        return None
    path = Path(state_dir) / "ideas" / DIGEST_FILE
    with ideas.LOCK:
        kept = ideas._json(path) or {}
        if kept.get("at") != at:
            s = summary(state_dir)
            kept = {"at": at, "digest": {"at": at, **s} if s["merged"] else None}
            ideas._write_json(path, kept)
    return kept.get("digest") if isinstance(kept.get("digest"), dict) else None
