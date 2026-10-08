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


# -- stage 5: tokens per 1 % of each quota, from a Tally Crag's samples -------------------------------------

def _sample(root: Path, label: str, used: float, ago: dt.timedelta, crag: str = "crag") -> None:
    metrics.sample(root / ".orkcraft" / "crag" / crag, "limits", used, label, now=NOW - ago)


def _climb(root: Path, label: str, start: float, end: float, hours: float, tokens: int,
           ago: dt.timedelta, crag: str = "crag") -> None:
    """A quota sampled every 10 minutes from `start` to `end` % over `hours`, with `tokens` spent in between."""
    steps = int(hours * 6)
    for i in range(steps + 1):
        _sample(root, label, start + (end - start) * i / steps, ago - dt.timedelta(minutes=10 * i), crag)
    metrics.record_run(root, "a", "done", 0.0, tokens, now=NOW - ago + dt.timedelta(hours=hours / 2))


def test_calibration_divides_the_tokens_spent_by_the_points_climbed(tmp_path: Path):
    _climb(tmp_path, "claude 5h session", 10, 22, 2, 6000, dt.timedelta(hours=30))      # 12 points: 500 per point
    _climb(tmp_path, "claude 5h session", 0, 8, 1, 4000, dt.timedelta(hours=10))        # after a reset: 8 points
    cal = pressure.calibrate(tmp_path, NOW)["claude 5h session"]
    assert cal.stretches == 2 and cal.points == 20 and cal.tokens == 10_000
    assert cal.ready and cal.per_point == 500


def test_a_reset_or_a_gap_in_the_samples_is_never_free_tokens(tmp_path: Path):
    label = "claude 5h session"
    _sample(tmp_path, label, 40, dt.timedelta(hours=6))
    _sample(tmp_path, label, 41, dt.timedelta(hours=5, minutes=50))
    _sample(tmp_path, label, 3, dt.timedelta(hours=5, minutes=40))       # reset: 41 → 3 is no climb of −38
    _sample(tmp_path, label, 5, dt.timedelta(hours=5, minutes=30))
    _sample(tmp_path, label, 30, dt.timedelta(hours=2))                  # the app was closed: a gap
    _sample(tmp_path, label, 31, dt.timedelta(hours=1, minutes=50))
    cal = pressure.calibrate(tmp_path, NOW)[label]
    assert cal.points == 1 + 2 + 1 and cal.stretches == 3 and not cal.ready     # too few points yet
    assert pressure.calibrate(tmp_path / "nowhere", NOW) == {}


def test_a_calibrated_quota_gives_what_is_left_instead_of_the_estimate(tmp_path: Path):
    _climb(tmp_path, "claude 5h session", 10, 30, 2, 10_000, dt.timedelta(hours=40))   # 500 tokens per point
    _spend(tmp_path, "a", 2400, dt.timedelta(hours=2))                   # 100 tok/h over 24 h
    limits = [Limit("claude", "", "5h session", 0.6, NOW + dt.timedelta(hours=3))]
    camp = pressure.measure(tmp_path, limits, NOW)
    # 60 points left × 500 = 30 000 tokens (the estimate from today's spend alone said 3600)
    assert camp.calibrated and camp.left == 30_000
    assert round(camp.buildings["a"].pressure, 4) == round(300 / 30_000, 4)
    assert "measured from the sampled quota" in pressure.describe(camp.buildings["a"], camp)
    assert not pressure.measure(tmp_path, limits, NOW, calibration={}).calibrated          # no calibration: the estimate
    fresh = [Limit("claude", "", "5h session", 1.0, NOW + dt.timedelta(hours=3))]          # nothing used yet
    assert pressure.measure(tmp_path, fresh, NOW).left == 50_000                           # the estimate had nothing to go on


def test_a_quota_is_named_as_the_crag_samples_it():
    assert pressure.quota_label(Limit("claude", "", "5h session", 0.5, None)) == "claude 5h session"
    assert pressure.quota_label(Limit("codex", "gpt-6-astra", "5h", 0.5, None)) == "codex gpt-6-astra"


def test_two_windows_sampled_under_one_name_are_not_calibrated(tmp_path: Path):
    """agy names a group's windows by the group alone on the Crag: their samples are mixed, so neither counts."""
    _climb(tmp_path, "agy gemini", 10, 30, 2, 10_000, dt.timedelta(hours=40))
    _spend(tmp_path, "a", 2400, dt.timedelta(hours=2))
    limits = [Limit("agy", "gemini", "5h", 0.6, NOW + dt.timedelta(hours=3)),
              Limit("agy", "gemini", "weekly", 0.9, NOW + dt.timedelta(days=3))]
    assert not pressure.measure(tmp_path, limits, NOW).calibrated
    assert pressure.measure(tmp_path, limits[:1], NOW).calibrated
