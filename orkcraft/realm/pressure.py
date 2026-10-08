"""⚖️ How much of the camp and of the limit a building eats (design: docs/design/retros-and-goals.md §2).

    share     the building's tokens in the window / the camp's tokens in the window
    rate      the building's tokens per hour over the window
    forecast  rate × hours until the binding quota resets
    pressure  forecast / what the camp can still spend before that reset

Subscription quotas come as a share used, not tokens. The calibration turns one into the other: a
🪨 Tally Crag samples every quota's `% used` once a minute (`.orkcraft/crag/<id>/samples.jsonl`), and
the ledger's tokens spent while a quota climbed, divided by the points it climbed, are that quota's
tokens per 1 % (`calibrate`). A stretch ends where the quota resets (it drops) or the sampling
stopped (a gap), so a reset nobody saw is never read as free tokens. Once a quota climbed
`CALIBRATE_MIN_PCT` points under sampling in the last week, "what is left" is its tokens per 1 % times
the points left. Until then it is estimated from the camp's own spend in the quota's window (tokens
in it / the share used). Either way, other use of the same quota (a person's own sessions, another
tool's runs) means fewer tokens per 1 % and a higher pressure: cautious, never reckless. With no
quota read, an API key or nothing spent in the quota's window there is no pressure, only share.

    camp = pressure.measure(repo_root, limits)
    camp.buildings["brief"].share, camp.buildings["brief"].pressure, camp.tight, camp.calibrated
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from orkcraft.realm import metrics

WINDOW = dt.timedelta(hours=24)
CALIBRATE_SPAN = dt.timedelta(days=7)    # the samples a calibration reads
CALIBRATE_MIN_PCT = 10.0                 # points a quota climbed under sampling before its calibration counts
GAP = dt.timedelta(minutes=15)           # samples further apart than this: the sampling stopped in between
RESET_DROP = 1.0                         # a fall of more points than this is a reset, not rounding


@dataclass
class Use:
    tokens: int = 0
    share: float = 0.0               # 0..1 of the camp's tokens in the window
    rate: float = 0.0                # tokens per hour
    forecast: float = 0.0            # tokens until the binding quota resets (0 with no quota)
    pressure: float | None = None    # forecast / what is left; None with no quota known

    @property
    def weight(self) -> float:
        """What ranks buildings for thrift: the pressure when it is known, else the share."""
        return self.pressure if self.pressure is not None else self.share


@dataclass
class Camp:
    tokens: int = 0
    buildings: dict[str, Use] = field(default_factory=dict)
    limit: str = ""                  # the binding quota, e.g. "claude 5h session"
    left: float | None = None        # tokens the camp can still spend before it resets (estimated)
    hours: float | None = None       # until it resets
    tight: bool = False              # the camp's forecast passes what is left
    calibrated: bool = False         # what is left comes from the quota's calibration, not the estimate

    def use(self, building: str) -> Use:
        return self.buildings.get(building) or Use()

    def heaviest(self, n: int = 3) -> list[str]:
        return [b for b, _ in sorted(self.buildings.items(), key=lambda kv: kv[1].weight, reverse=True)[:n]]


def quota_span(window: str) -> dt.timedelta:
    """The length of a quota's window from its label: 5h, a week, else a day."""
    w = (window or "").lower()
    if "5h" in w or "5 h" in w or "session" in w:
        return dt.timedelta(hours=5)
    if "week" in w or "7d" in w or "7 d" in w:
        return dt.timedelta(days=7)
    return dt.timedelta(hours=24)


@dataclass
class Calibration:
    """One quota's tokens per 1 %: the ledger's tokens spent while it climbed, over the points it climbed."""
    label: str                       # as a Tally Crag samples it: "claude 5h", "codex weekly"
    tokens: int = 0
    points: float = 0.0
    stretches: int = 0

    @property
    def ready(self) -> bool:
        return self.points >= CALIBRATE_MIN_PCT and self.tokens > 0

    @property
    def per_point(self) -> float:
        return self.tokens / self.points if self.points > 0 else 0.0


def quota_label(lim) -> str:
    """A quota's name as a Tally Crag samples it (gui/views/crag.py `probe`, metrics.sample's 24 characters)."""
    return f"{lim.provider} {lim.group or lim.window}"[:24]


def _stretches(points: list[tuple[dt.datetime, float]]) -> list[list[tuple[dt.datetime, float]]]:
    """Runs of samples with no reset (a drop) and no gap in them."""
    out: list[list[tuple[dt.datetime, float]]] = []
    for at, used in points:
        last = out[-1][-1] if out else None
        if last is None or at - last[0] > GAP or used < last[1] - RESET_DROP:
            out.append([(at, used)])
        else:
            out[-1].append((at, used))
    return out


def calibrate(repo_root: Path, now: dt.datetime | None = None) -> dict[str, Calibration]:
    """Tokens per 1 % of each quota a Tally Crag sampled in the last week; every Crag of the town counts
    (two Crags sample the same quota: both the tokens and the points double, the ratio stays). Never raises."""
    now = now or dt.datetime.now()
    since = now - CALIBRATE_SPAN
    ledger = sorted((r["_at"], int(r.get("tokens") or 0)) for r in metrics._read(repo_root / metrics.LEDGER, since))
    out: dict[str, Calibration] = {}
    try:
        files = sorted((repo_root / ".orkcraft" / "crag").glob("*/samples.jsonl"))
    except OSError:
        files = []
    for path in files:
        series: dict[str, list[tuple[dt.datetime, float]]] = {}
        for r in metrics._read(path, since):
            if r.get("source") == "limits" and r.get("by") and isinstance(r.get("value"), (int, float)):
                series.setdefault(str(r["by"]), []).append((r["_at"], float(r["value"])))
        for label, points in series.items():
            cal = out.setdefault(label, Calibration(label))
            for run in _stretches(sorted(points)):
                (t0, u0), (t1, u1) = run[0], run[-1]
                climbed = u1 - u0
                if climbed <= 0:
                    continue
                cal.points += climbed
                cal.tokens += sum(n for at, n in ledger if t0 < at <= t1)
                cal.stretches += 1
    return out


def _tokens(rows: Iterable[dict]) -> dict[str, int]:
    out: dict[str, int] = {}
    for r in rows:
        bid = str(r.get("building") or "")
        if bid:
            out[bid] = out.get(bid, 0) + int(r.get("tokens") or 0)
    return out


def measure(repo_root: Path, limits: Iterable | None = None, now: dt.datetime | None = None,
            providers: Iterable[str] | None = None,
            calibration: dict[str, Calibration] | None = None) -> Camp:
    """Share and pressure of every building that spent tokens in the last 24 h. `limits` are the
    quota reads (`sources.limits.Limit`); `providers` keeps only those tools (the enabled
    subscriptions); `calibration` is each quota's tokens per 1 % (None: `calibrate` reads the
    Tally Crags' samples). Never raises."""
    now = now or dt.datetime.now()
    rows = metrics._read(repo_root / metrics.LEDGER, now - max(WINDOW, dt.timedelta(days=7)))
    day = _tokens(r for r in rows if r["_at"] > now - WINDOW)
    total = sum(day.values())
    hours = WINDOW.total_seconds() / 3600
    camp = Camp(total, {b: Use(t, t / total if total else 0.0, t / hours) for b, t in day.items() if t > 0})
    camp_rate = total / hours
    keep = set(providers) if providers is not None else None
    limits = [lim for lim in limits or () if keep is None or getattr(lim, "provider", None) in keep]
    if calibration is None:
        calibration = calibrate(repo_root, now) if limits else {}
    best: tuple[float, object, float, float, bool] | None = None   # (camp pressure, limit, left, hours, calibrated)
    labels = [quota_label(lim) for lim in limits]
    for lim in limits:
        remaining, reset = getattr(lim, "remaining", None), getattr(lim, "reset", None)
        if remaining is None or reset is None:
            continue
        used = 1.0 - max(0.0, min(1.0, float(remaining)))
        until = (reset - now).total_seconds() / 3600 if reset > now else 0.0
        if until <= 0:
            continue
        label = quota_label(lim)
        cal = calibration.get(label) if labels.count(label) == 1 else None    # two windows sampled as one: not theirs
        if cal is not None and cal.ready:
            left, measured = cal.per_point * (1.0 - used) * 100, True
        else:
            spent = sum(int(r.get("tokens") or 0) for r in rows if r["_at"] >= now - quota_span(lim.window))
            if used <= 0 or spent <= 0:
                continue
            left, measured = spent / used * (1.0 - used), False
        p = camp_rate * until / left if left > 0 else float("inf")
        if best is None or p > best[0]:
            best = (p, lim, left, until, measured)
    if best is not None:
        p, lim, left, until, measured = best
        camp.limit = " ".join(x for x in (lim.provider, lim.window) if x)
        camp.left, camp.hours, camp.tight, camp.calibrated = round(left), round(until, 2), p > 1.0, measured
        for u in camp.buildings.values():
            u.forecast = u.rate * until
            u.pressure = u.forecast / left if left > 0 else float("inf")
    return camp


def describe(use: Use, camp: Camp) -> str:
    """One line for the Council and the Info panel: 42 % of the camp · 60 % of what is left of claude 5h."""
    text = f"{round(use.share * 100)} % of the camp's tokens in 24 h"
    if use.pressure is not None and camp.limit:
        text += (f" · at this rate {round(use.pressure * 100)} % of what is left of {camp.limit} "
                 f"before it resets in {camp.hours:g} h")
        if camp.calibrated:
            text += " (what is left measured from the sampled quota)"
    return text
