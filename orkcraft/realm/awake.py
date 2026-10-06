"""⏱ The hours the operator is around: the camp open, outside quiet hours (design:
docs/design/barracks-planning.md §2). A rebuild waits so many of these, not of the clock's: a night
asleep, a weekend away, the camp closed — none of it counts.

    awake.note(root, now)                 the camp is open and it is not quiet: this minute counts
    awake.hours_since(root, since, now)   how many such hours passed since `since`

Kept as spans in `.orkcraft/autonomy/awake.json`; a gap longer than `GAP` starts a new span, spans
older than `KEEP` are dropped.
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

FILE = Path(".orkcraft") / "autonomy" / "awake.json"
GAP = dt.timedelta(minutes=5)            # a face notes at least every minute; longer: the camp was closed
KEEP = dt.timedelta(days=30)


def _load(root: Path) -> list[list[str]]:
    try:
        spans = json.loads((root / FILE).read_text(encoding="utf-8")).get("spans") or []
        return [s for s in spans if isinstance(s, list) and len(s) == 2]
    except (OSError, ValueError, AttributeError):
        return []


def note(root: Path, now: dt.datetime | None = None) -> None:
    """This moment the operator is around: the last span grows to it, or a new one starts."""
    now = (now or dt.datetime.now()).replace(microsecond=0)
    spans = _load(root)
    if spans:
        try:
            end = dt.datetime.fromisoformat(spans[-1][1])
        except ValueError:
            end = None
        if end is not None and dt.timedelta(0) <= now - end <= GAP:
            spans[-1][1] = now.isoformat()
        elif end is None or now > end:
            spans.append([now.isoformat(), now.isoformat()])
    else:
        spans.append([now.isoformat(), now.isoformat()])
    cut = (now - KEEP).isoformat()
    spans = [s for s in spans if s[1] >= cut]
    f = root / FILE
    try:
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps({"spans": spans}), encoding="utf-8")
    except OSError:
        pass


def hours_since(root: Path, since: str | dt.datetime, now: dt.datetime | None = None) -> float:
    """Hours the operator was around between `since` and `now` (0 for a time that cannot be read)."""
    try:
        start = since if isinstance(since, dt.datetime) else dt.datetime.fromisoformat(since)
    except (TypeError, ValueError):
        return 0.0
    start = start.replace(tzinfo=None)
    now = now or dt.datetime.now()
    total = 0.0
    for a, b in _load(root):
        try:
            lo, hi = max(dt.datetime.fromisoformat(a), start), min(dt.datetime.fromisoformat(b), now)
        except ValueError:
            continue
        if hi > lo:
            total += (hi - lo).total_seconds()
    return total / 3600
