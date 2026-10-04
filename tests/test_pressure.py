"""⚖️ Share and pressure: what part of the camp and of the limit a building eats (docs/design/retros-and-goals.md §2)."""
from __future__ import annotations

import datetime as dt
from pathlib import Path

from orkcraft.realm import metrics, optimize, pressure
from orkcraft.sources.limits import Limit

NOW = dt.datetime(2026, 10, 3, 12, 0)


def _spend(root: Path, building: str, tokens: int, ago: dt.timedelta = dt.timedelta(hours=1)) -> None:
    metrics.record_run(root, building, "done", 0.0, tokens, now=NOW - ago)


def test_share_without_a_quota(tmp_path: Path):
    _spend(tmp_path, "a", 300)
    _spend(tmp_path, "b", 100)
    _spend(tmp_path, "a", 5000, dt.timedelta(hours=30))                  # older than the window
    camp = pressure.measure(tmp_path, [], NOW)
    assert camp.tokens == 400 and camp.buildings["a"].share == 0.75 and camp.buildings["a"].pressure is None
    assert camp.buildings["a"].weight == 0.75 and not camp.tight and camp.heaviest(1) == ["a"]
    assert pressure.describe(camp.buildings["a"], camp) == "75 % of the camp's tokens in 24 h"


def test_pressure_against_the_binding_quota(tmp_path: Path):
    _spend(tmp_path, "a", 2400, dt.timedelta(hours=2))                   # 2400 in the 5 h window: 100 tok/h over 24 h
    limits = [Limit("claude", "", "5h session", 0.6, NOW + dt.timedelta(hours=3)),      # 40 % used by 2400 tokens
              Limit("claude", "", "week", 0.99, NOW + dt.timedelta(days=1)),       # looser: 1 % used
              Limit("agy", "", "5h session", None, None, "no data")]
    camp = pressure.measure(tmp_path, limits, NOW)
    # 2400 tokens / 40 % → 6000 per 100 %; 60 % left → 3600 tokens; 100 tok/h × 3 h = 300 → 300 / 3600
    assert camp.limit == "claude 5h session" and camp.left == 3600 and camp.hours == 3
    use = camp.buildings["a"]
    assert round(use.forecast) == 300 and round(use.pressure, 4) == round(300 / 3600, 4) and not camp.tight
    assert "of what is left of claude 5h session" in pressure.describe(use, camp)
    assert pressure.measure(tmp_path, limits, NOW, providers=["agy"]).limit == ""        # a tool not on: no pressure


def test_a_tight_camp(tmp_path: Path):
    _spend(tmp_path, "a", 24_000, dt.timedelta(hours=1))                 # 1000 tok/h
    limits = [Limit("claude", "", "5h session", 0.05, NOW + dt.timedelta(hours=4))]
    camp = pressure.measure(tmp_path, limits, NOW)
    assert camp.tight and camp.buildings["a"].pressure > 1


def test_the_leader_goes_by_pressure_and_tells_the_council(tmp_path: Path):
    _spend(tmp_path, "a", 2400, dt.timedelta(hours=2))
    limits = [Limit("claude", "", "5h session", 0.6, NOW + dt.timedelta(hours=3))]
    cand = optimize.leader(tmp_path, NOW, limits)
    assert cand.building == "a" and "of what is left of claude 5h session" in cand.use
    prompts = []
    optimize.propose(tmp_path, cand, [optimize.Part("orc:x", "agent", "do it")],
                     lambda p: (prompts.append(p) or "nope", None), attempts=1)
    assert "2400 tokens" in prompts[0] and "of what is left" in prompts[0]
