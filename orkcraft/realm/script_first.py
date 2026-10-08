"""Script-first buildings: their work is code, their ork wakes only on an error or a 👎
(docs/design/script-first.md).

    is_script_first(spec, b)        a type whose work is code, and no part of it that thinks
    thinking(spec, b)               what in it still calls a model: ["agent: step 3", "handler Boss's mail", …]
    log(repo, building, why, detail)   a wake, kept in `.orkcraft/script_first/wakes.jsonl`
    state(repo) / save_state(repo, s)  what the wakes remember: per building, ill since, the last 👎 woken on

No face, no model: the town (core/wakes.py) decides when a wake is due, a face runs it.
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

from orkcraft.realm import catalog, mill

DIR = Path(".orkcraft") / "script_first"
KEEP = 500                     # wakes the log keeps
# Types whose work is code by construction (their workers call no model).
TYPES = frozenset({"pit", "horn", "signpost", "forest", "crag", "war_drum", "loot", "forge"})
# Types that are script-first when their parts are code: a Transformer without an `agent:` step, a Script
# that hands nothing to its steward.
WHEN_CODE = frozenset({"mill", "workshop"})


def type_id(spec: dict | None) -> str:
    return catalog.type_of(spec).id if spec else ""


def thinking(spec: dict | None, b=None) -> list[str]:
    """What still calls a model in the building, in plain words; [] for none."""
    out: list[str] = []
    cfg = (spec or {}).get("config") or {}
    kind = type_id(spec)
    if kind == "mill":
        for i, step in enumerate(cfg.get("steps") or [], 1):
            text = str(step)
            try:
                name, _ = mill.parse(text)
            except ValueError:
                continue
            if name in mill.MODEL_STEPS or (name == "script" and mill.FALLBACK.search(text)):
                out.append(f"agent: step {i}")
    if kind == "workshop" and str(cfg.get("steward_prompt") or "").strip():
        out.append("its steward takes what the script hands over")
    for orc in (b.garrison.handlers if b is not None else []):
        if orc.uses_model:
            out.append(f"{'road rule' if orc.kind == 'steward' else orc.kind} {orc.name}")
    return out


def is_script_first(spec: dict | None, b=None) -> bool:
    """A building whose work is code: its type is one, and nothing in it thinks."""
    kind = type_id(spec)
    return kind in TYPES | WHEN_CODE and not thinking(spec, b)


# -- what the wakes remember ------------------------------------------------------------------------------

def _dir(repo_root: Path) -> Path:
    return repo_root / DIR


def state(repo_root: Path) -> dict[str, dict]:
    """{building: {"ill": bool, "disliked": the last 👎 woken on (its ts)}}."""
    try:
        data = json.loads((_dir(repo_root) / "state.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return {str(k): dict(v) for k, v in data.items() if isinstance(v, dict)} if isinstance(data, dict) else {}


def save_state(repo_root: Path, data: dict[str, dict]) -> None:
    path = _dir(repo_root) / "state.json"
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    except OSError:
        pass


def log(repo_root: Path, building: str, why: str, detail: str, now: dt.datetime | None = None) -> dict:
    """A wake in the log (newest last, the last `KEEP`)."""
    entry = {"ts": (now or dt.datetime.now()).isoformat(timespec="seconds"), "building": building,
             "why": why, "detail": detail[:1000]}
    path = _dir(repo_root) / "wakes.jsonl"
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
        lines = (lines + [json.dumps(entry, ensure_ascii=False)])[-KEEP:]
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    except OSError:
        pass
    return entry


def wakes(repo_root: Path, building: str = "", limit: int = 20) -> list[dict]:
    """The latest wakes, newest first (of one building when `building` is given)."""
    try:
        lines = (_dir(repo_root) / "wakes.jsonl").read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    out: list[dict] = []
    for line in reversed(lines):
        try:
            e = json.loads(line)
        except ValueError:
            continue
        if isinstance(e, dict) and (not building or e.get("building") == building):
            out.append(e)
            if len(out) >= limit:
                break
    return out
