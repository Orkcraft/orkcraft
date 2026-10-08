"""A hop's metadata: how long, on what, what the building decided, which round, its own record — short,
and kept through a stored trail."""
from __future__ import annotations

import datetime as dt

from orkcraft.realm import pipes


def test_a_hop_says_how_long_on_what_and_what_it_decided():
    now = dt.datetime(2026, 10, 8, 12, 0, 30)
    h = pipes.hop("council", "clan", "team", cost=0.3, outcome="approved", now=now, since="2026-10-08T11:58:00",
                  model="opus", decision="✓3 ✎1 → barracks\nlong notes that follow", round=2, run="d1")
    assert h.ms == 150_000 and h.started == "2026-10-08T11:58:00" and pipes.took(h.ms) == "2m 30s"
    assert h.decision == "✓3 ✎1 → barracks" and h.round == 2 and h.run == "d1" and h.model == "opus"
    assert pipes.trail_of([h.as_dict()]) == (h,)


def test_a_hop_stays_short():
    h = pipes.hop("b", decision="x" * 500, round=1, since=1.5)
    assert len(h.decision) == pipes.DECISION_CHARS and h.decision.endswith("…")
    assert h.round is None and h.ms == 1500                        # the first round is not said
    assert set(pipes.hop("b").as_dict()) == {"building", "at"}     # nothing said, nothing stored
    assert pipes.hop("b", since="not a time").ms is None and pipes.hop("b").started == ""


def test_took_reads_at_a_glance():
    assert [pipes.took(x) for x in (None, 850, 42_000, 3_600_000 + 600_000)] == ["", "850ms", "42s", "1h 10m"]
