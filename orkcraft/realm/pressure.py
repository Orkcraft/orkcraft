"""⚖️ How much of the camp and of the limit a building eats (design: docs/design/retros-and-goals.md §2).

    share     the building's tokens in the window / the camp's tokens in the window
    rate      the building's tokens per hour over the window
    forecast  rate × hours until the binding quota resets
    pressure  forecast / what the camp can still spend before that reset

Subscription quotas come as a share used, not tokens: until there is a calibration, the camp's tokens
per 100 % are estimated from its own spend in the quota's window (tokens in it / the share used), so
"what is left" is that times the remaining share. Other use of the same quota makes the estimate
cautious (fewer tokens per 100 %, a higher pressure), never reckless. With no quota read, an API key
or nothing spent in the quota's window there is no pressure — share only.

    camp = pressure.measure(repo_root, limits)
    camp.buildings["brief"].share, camp.buildings["brief"].pressure, camp.tight
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from orkcraft.realm import metrics

WINDOW = dt.timedelta(hours=24)


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


def _tokens(rows: Iterable[dict]) -> dict[str, int]:
    out: dict[str, int] = {}
    for r in rows:
        bid = str(r.get("building") or "")
        if bid:
            out[bid] = out.get(bid, 0) + int(r.get("tokens") or 0)
    return out


def measure(repo_root: Path, limits: Iterable | None = None, now: dt.datetime | None = None,
            providers: Iterable[str] | None = None) -> Camp:
    """Share and pressure of every building that spent tokens in the last 24 h. `limits` are the
    quota reads (`sources.limits.Limit`); `providers` keeps only those tools (the enabled
    subscriptions). Never raises."""
    now = now or dt.datetime.now()
    rows = metrics._read(repo_root / metrics.LEDGER, now - max(WINDOW, dt.timedelta(days=7)))
    day = _tokens(r for r in rows if r["_at"] > now - WINDOW)
    total = sum(day.values())
    hours = WINDOW.total_seconds() / 3600
    camp = Camp(total, {b: Use(t, t / total if total else 0.0, t / hours) for b, t in day.items() if t > 0})
    camp_rate = total / hours
    keep = set(providers) if providers is not None else None
    best: tuple[float, object, float, float] | None = None        # (camp pressure, limit, left, hours)
    for lim in limits or ():
        remaining, reset = getattr(lim, "remaining", None), getattr(lim, "reset", None)
        if remaining is None or reset is None or (keep is not None and lim.provider not in keep):
            continue
        used = 1.0 - max(0.0, min(1.0, float(remaining)))
        until = (reset - now).total_seconds() / 3600 if reset > now else 0.0
        spent = sum(int(r.get("tokens") or 0) for r in rows if r["_at"] >= now - quota_span(lim.window))
        if used <= 0 or spent <= 0 or until <= 0:
            continue
        left = spent / used * (1.0 - used)
        p = camp_rate * until / left if left > 0 else float("inf")
        if best is None or p > best[0]:
            best = (p, lim, left, until)
    if best is not None:
        p, lim, left, until = best
        camp.limit = " ".join(x for x in (lim.provider, lim.window) if x)
        camp.left, camp.hours, camp.tight = round(left), round(until, 2), p > 1.0
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
    return text
