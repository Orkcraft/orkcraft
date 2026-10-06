"""🔧 Self-improvement by the orcs themselves, by autonomy level (design: docs/design/onboarding.md).

    evolution.allowed("shrink", level)       may the orcs apply this kind of change on their own?
    evolution.record(root, Change(...))      the ledger of every applied change: .orkcraft/evolution/changes.jsonl
    evolution.unseen(root)                   what the operator has not seen yet (the list after changes)
    evolution.verdict(root, change, now)     on probation: a reason to take it back, or None

The Building retro (daily), the Town retro (weekly) and the stewards keep proposing as before. In 🌙 quiet
hours (nobody to wait for: autonomy.waits), from ⏳ Timer, the orks apply what their level allows —
silence never makes the camp spend more:

    ⏳ Timer (1)      changes that make a building cheaper or simpler: shrink a prompt, an agent made a
                      chain, a steward's demotion (proved on recorded runs), a run policy, a road filter
    ⛓️‍💥 Free orks (2)  also a script instead of an agent (sandbox-proved), a richer prompt for a ⚖️ / 💎
                      building (it spends more), a new plain road, a building's setting, a building
                      from the catalog
    never             removing a road or a building, notes — those stay advice

Each one must pass its own checks (validation, sandbox, replay) and the Council's review with no
block, objection or Warder warning; it gets its own checkpoint (Z takes it back) and 24 hours of
probation: a 👎 on the building, or more failed runs than before, takes it back by itself — and the
operator is told. Every change, by the orcs or by the operator, lands in the ledger, and the list of
the orcs' changes is shown after them (when quiet hours end, and after a probation revert).
"""
from __future__ import annotations

import datetime as dt
import json
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path

from orkcraft import autonomy
from orkcraft.realm import feedback, metrics

LEDGER = Path(".orkcraft") / "evolution" / "changes.jsonl"
PROBATION = dt.timedelta(hours=24)
MAX_PER_NIGHT = 10
FAILED = ("error", "failed", "fail")

# The lowest autonomy level at which the orcs may apply a kind of change themselves.
_T, _F = autonomy.TIMER, autonomy.FREE
LEVEL_FOR: dict[str, int] = {
    "shrink": _T, "chain": _T, "demote": _T, "set_run": _T, "filter": _T,
    "script": _F, "enrich": _F, "new_road": _F, "set_config": _F, "add_building": _F,
}
NEVER = ("remove_road", "remove_building", "note")


def allowed(change: str, level: int) -> bool:
    need = LEVEL_FOR.get(change)
    return need is not None and change not in NEVER and level >= need


@dataclass
class Change:
    building: str
    change: str                  # shrink | chain | script | enrich | demote | set_run | filter | new_road | set_config | …
    source: str                  # daily | weekly | steward
    summary: str
    why: str = ""
    by: str = "orcs"             # orcs | you
    sha: str = ""                # its checkpoint
    key: str = ""                # what it came from (a proposal id), so it is never applied twice
    status: str = "probation"    # probation | kept | reverted | stuck (could not be taken back by itself)
    note: str = ""               # why it was reverted, or why it could not be
    seen: bool = False
    ts: str = field(default_factory=lambda: dt.datetime.now().isoformat(timespec="seconds"))
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:10])

    @property
    def until(self) -> dt.datetime:
        return dt.datetime.fromisoformat(self.ts) + PROBATION


def _path(root: Path) -> Path:
    return Path(root) / LEDGER


def load(root: Path | None) -> list[Change]:
    if root is None:
        return []
    try:
        lines = _path(root).read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    out = []
    for line in lines:
        try:
            out.append(Change(**json.loads(line)))
        except (ValueError, TypeError):
            continue
    return out


def _write(root: Path, changes: list[Change]) -> None:
    path = _path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text("".join(json.dumps(asdict(c), ensure_ascii=False) + "\n" for c in changes), encoding="utf-8")
    tmp.replace(path)


def record(root: Path, change: Change) -> Change:
    if change.by != "orcs":
        change.status, change.seen = "kept", True       # the operator's own: no probation, nothing to show
    try:
        _path(root).parent.mkdir(parents=True, exist_ok=True)
        with _path(root).open("a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(change), ensure_ascii=False) + "\n")
    except OSError:
        pass
    return change


def update(root: Path, change: Change) -> None:
    changes = [change if c.id == change.id else c for c in load(root)]
    try:
        _write(root, changes)
    except OSError:
        pass


def applied_keys(root: Path) -> set[str]:
    return {c.key for c in load(root) if c.key}


def unseen(root: Path) -> list[Change]:
    return [c for c in load(root) if c.by == "orcs" and not c.seen]


def mark_seen(root: Path) -> None:
    changes = load(root)
    if any(not c.seen for c in changes):
        for c in changes:
            c.seen = True
        try:
            _write(root, changes)
        except OSError:
            pass


def since(root: Path, ts: str) -> list[Change]:
    return [c for c in load(root) if c.by == "orcs" and c.ts >= ts]


def on_probation(root: Path) -> list[Change]:
    return [c for c in load(root) if c.status == "probation"]


def _failure_share(rows: list[dict]) -> float:
    return sum(1 for r in rows if r.get("outcome") in FAILED) / len(rows) if rows else 0.0


def verdict(root: Path, change: Change, now: dt.datetime | None = None) -> str | None:
    """A reason to take a change on probation back, or None: a 👎 on its building since, or a failure
    share of its runs since that is higher than in as long a stretch before (with two failures at least)."""
    now = now or dt.datetime.now()
    at = dt.datetime.fromisoformat(change.ts)
    since = feedback.blaming(Path(root), change.building, change.ts, 200)   # its own, and broken inputs it fed on
    if sum(i.share(change.building) for i in since) >= feedback.ENOUGH - 1e-9:   # quiet signals add up to a 👎
        inc = since[0]
        how = "👎" if inc.source == feedback.EXPLICIT else f"👎 ({inc.source})"
        via = f" downstream at {inc.building}" if inc.building != change.building else ""
        return f"{how}{via} at {inc.ts[11:16]}" + (f": {inc.note[:60]}" if inc.note else "")
    span = max(now - at, dt.timedelta(hours=1))
    rows = [r for r in metrics._read(Path(root) / metrics.LEDGER, at - span) if r.get("building") == change.building]
    after = [r for r in rows if r["_at"] >= at]
    before = [r for r in rows if r["_at"] < at]
    fails = sum(1 for r in after if r.get("outcome") in FAILED)
    if fails >= 2 and _failure_share(after) > _failure_share(before):
        return f"{fails} of {len(after)} runs failed since (before: {round(_failure_share(before) * 100)}%)"
    return None
