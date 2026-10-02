"""The Council at runtime: what the watchers report while orkcraft runs.

Today only Warder is live — `scripts/warder_hook.py` guards every Claude Code tool call and
appends each deny / ask to `.orkcraft/warder.jsonl`. The other Council orcs (Drummer, Taskmaster,
Alchemist, Keeper) are still draft agent definitions in `watchers/`; Taskmaster's budget duty is
partly covered by the 🪙 / 🪵 limits of stage 10.
"""
from __future__ import annotations

import datetime as dt
import json
from dataclasses import dataclass
from pathlib import Path

WARDER_LOG = Path(".orkcraft") / "warder.jsonl"
RECENT_HOURS = 24
TAIL_BYTES = 256 * 1024


@dataclass
class WarderEvent:
    ts: str
    decision: str        # deny | ask | error
    tool: str
    reason: str
    subject: str         # already redacted and cut by the hook

    @property
    def id(self) -> str:
        return f"warder:{self.ts}:{self.decision}:{self.subject[:40]}"


def warder_events(repo_root: Path, hours: int = RECENT_HOURS, now: dt.datetime | None = None) -> list[WarderEvent]:
    """Deny / ask events of the last `hours`, newest first (reads only the log's tail)."""
    path = repo_root / WARDER_LOG
    try:
        size = path.stat().st_size
        with path.open("rb") as f:
            f.seek(max(size - TAIL_BYTES, 0))
            lines = f.read().decode("utf-8", errors="replace").splitlines()
    except OSError:
        return []
    cutoff = (now or dt.datetime.now()) - dt.timedelta(hours=hours)
    out = []
    for line in lines:
        try:
            e = json.loads(line)
            when = dt.datetime.fromisoformat(str(e.get("ts")))
        except (ValueError, TypeError):
            continue
        if when < cutoff or e.get("decision") not in ("deny", "ask"):
            continue
        out.append(WarderEvent(str(e["ts"]), str(e["decision"]), str(e.get("tool", "")),
                               str(e.get("reason", "")), str(e.get("subject", ""))))
    return list(reversed(out))
