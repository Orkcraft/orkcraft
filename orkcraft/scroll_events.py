"""Building Chronicles (event sourcing): one JSONL file of mutations per building, kept beside the Town Scroll
(`scroll.append_event`; realm/chronicles.py says what they are)."""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Any

from orkcraft.scroll import HISTORY_DIR


def events_file(repo_root: Path, building_id: str) -> Path:
    return repo_root / HISTORY_DIR / f"{building_id}.events.jsonl"


def append_event(repo_root: Path, building_id: str, event: dict[str, Any]) -> Path:
    """Append one mutation, e.g. {"type": "card_moved", "id": "T1001", "to": "done", "by": "operator"}."""
    path = events_file(repo_root, building_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    entry = {"ts": dt.datetime.now().isoformat(timespec="seconds"), "building": building_id, **event}
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return path


def read_events(repo_root: Path, building_id: str, limit: int = 200) -> list[dict[str, Any]]:
    """Newest last; malformed lines are skipped."""
    try:
        lines = events_file(repo_root, building_id).read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    out = []
    for line in lines[-limit:]:
        try:
            out.append(json.loads(line))
        except ValueError:
            continue
    return out
