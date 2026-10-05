"""Calibrating the weights of quiet feedback (`feedback.WEIGHTS`) on what the camp kept.

A quiet signal is worth what it agrees with: for each one (an accepted cart, a reshaped file, a
closed pull request…) the 👍 / 👎 the operator pressed on the same building within `WINDOW` of it
are the ground truth — mostly 👍 around it agrees with a good signal, mostly 👎 with a bad one.
The share that agrees is the signal's precision; its weight should say how far that is from a coin
toss: `2p − 1`, taken at the lower bound of its interval (`Z`) so that a handful of matches does
not pass for certainty. A source with fewer than `MIN_MATCHED` matches is left as it is.

It only reports: `orkcraft feedback calibrate` prints the table and the operator decides. A result
nobody opened (`feedback.NOT_QUALITY`) is about use, not quality, and is not judged here.
"""
from __future__ import annotations

import datetime as dt
import math
from dataclasses import dataclass
from pathlib import Path

from orkcraft.realm import feedback

WINDOW = dt.timedelta(days=7)    # a 👍 / 👎 this close to a quiet signal is about the same work
MIN_MATCHED = 5                  # fewer quiet signals with a 👍 / 👎 near them say nothing yet
Z = 1.28                         # the lower bound of an 80 % interval
FLOOR = 0.05                     # the least a source that agrees more than it disagrees weighs


@dataclass
class Row:
    source: str
    weight: float                # what it weighs now
    count: int = 0               # the quiet signals kept
    matched: int = 0             # … with a 👍 / 👎 on the same building near them
    agreed: int = 0              # … which mostly agreed
    per_week: float = 0.0        # what it adds up to on one building in a week, at the weight it has now
    suggested: float | None = None

    @property
    def precision(self) -> float | None:
        return self.agreed / self.matched if self.matched else None


@dataclass
class _Sig:
    ts: dt.datetime
    building: str
    good: bool
    source: str


def _when(ts: str) -> dt.datetime | None:
    try:
        return dt.datetime.fromisoformat(str(ts)[:19])
    except ValueError:
        return None


def _signals(root: Path, since: dt.datetime | None) -> list[_Sig]:
    out: list[_Sig] = []
    for i in feedback.incidents(root, 100_000):
        when = _when(i.ts)
        if when is not None and (since is None or when >= since) and "/" not in i.building:
            out.append(_Sig(when, i.building, False, i.source))
    for path in (root / feedback.DIR).glob("*/references.jsonl"):
        for r in feedback._tail(path, 100_000):
            when = _when(r.get("ts", ""))
            # weight 0: the operator's own version kept as an example after a bad edit — not a 👍
            if when is None or (since is not None and when < since) or feedback._weight(r) <= 0:
                continue
            out.append(_Sig(when, path.parent.name, True, str(r.get("source") or feedback.EXPLICIT)))
    return out


def lower_bound(agreed: int, n: int, z: float = Z) -> float:
    """The Wilson lower bound of `agreed / n`."""
    if n == 0:
        return 0.0
    p = agreed / n
    centre = p + z * z / (2 * n)
    spread = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return max(0.0, (centre - spread) / (1 + z * z / n))


def suggest(agreed: int, matched: int) -> float | None:
    """The weight a source has earned: `2p − 1` at the lower bound of p; None with too few matches."""
    if matched < MIN_MATCHED:
        return None
    return round(min(1.0, max(FLOOR, 2 * lower_bound(agreed, matched) - 1)), 2)


def report(root: Path, days: int | None = None, now: dt.datetime | None = None) -> list[Row]:
    """A row per quiet source the camp kept (and every one `WEIGHTS` knows), most frequent first."""
    now = now or dt.datetime.now()
    since = now - dt.timedelta(days=days) if days else None
    sigs = _signals(root, since)
    truth: dict[str, list[_Sig]] = {}
    for s in sigs:
        if s.source == feedback.EXPLICIT:
            truth.setdefault(s.building, []).append(s)
    rows = {src: Row(src, w) for src, w in feedback.WEIGHTS.items()
            if src != feedback.EXPLICIT and src not in feedback.NOT_QUALITY}
    first: dict[str, dt.datetime] = {}
    buildings: dict[str, set[str]] = {}
    for s in sigs:
        if s.source == feedback.EXPLICIT or s.source in feedback.NOT_QUALITY:
            continue
        row = rows.setdefault(s.source, Row(s.source, feedback.WEIGHTS.get(s.source, 0.5)))
        row.count += 1
        first[s.source] = min(first.get(s.source, s.ts), s.ts)
        buildings.setdefault(s.source, set()).add(s.building)
        near = [t for t in truth.get(s.building, ()) if abs(t.ts - s.ts) <= WINDOW]
        if not near:
            continue
        good = sum(1 for t in near if t.good)
        if good * 2 == len(near):
            continue                                    # as many 👍 as 👎: says nothing
        row.matched += 1
        row.agreed += int((good * 2 > len(near)) == s.good)
    for src, row in rows.items():
        if row.count:
            weeks = max((now - first[src]) / dt.timedelta(days=7), 1.0)
            row.per_week = round(row.count * row.weight / weeks / max(len(buildings[src]), 1), 2)
        row.suggested = suggest(row.agreed, row.matched)
    return sorted(rows.values(), key=lambda r: (-r.count, r.source))


def render(rows: list[Row]) -> str:
    lines = [f"{'source':<20} {'now':>5} {'kept':>5} {'near':>5} {'agree':>6} {'/week':>6} {'suggest':>8}  what"]
    for r in rows:
        p = f"{r.precision:.0%}" if r.precision is not None else "—"
        s = f"{r.suggested:.2f}" if r.suggested is not None else "—"
        lines.append(f"{r.source:<20} {r.weight:>5.2f} {r.count:>5} {r.matched:>5} {p:>6} {r.per_week:>6.2f} {s:>8}  "
                     f"{feedback.LABELS.get(r.source, r.source)}")
    lines += ["",
              "near: the quiet signals with a 👍 / 👎 on the same building within 7 days; agree: how many of",
              "those the buttons agreed with. /week: what the source adds up to on one building in a week now",
              f"(from {feedback.ENOUGH:g} the retros act). suggest: 2p − 1 at the lower bound of p, from "
              f"{MIN_MATCHED} matches up;",
              "nothing is changed — the weights live in realm/feedback.py (WEIGHTS)."]
    return "\n".join(lines)
