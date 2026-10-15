"""The sandbox's traffic (orkcraft/demo/traffic.py): demo carts with a trail on the demo town's roads — moving ones
round the roads, one waiting at each Review gate — and two weeks of results that make a lean week; demo data only."""
from __future__ import annotations

import datetime as dt
from pathlib import Path

from orkcraft import demo
from orkcraft.demo import traffic
from orkcraft.realm import score


def test_the_demo_sends_carts_with_trails_and_one_waits_at_each_review_gate(tmp_path: Path, monkeypatch):
    from orkcraft.gui.host import Host
    monkeypatch.setattr(traffic.Traffic, "start", lambda self: None)       # ticked by hand here
    root = demo.build(tmp_path / "d", set_name="dashboard")
    host = Host(root, False, root / ".orkcraft.json", demo=True)
    try:
        t = host.traffic
        for _ in range(6):
            t.tick()
        carts = host.town.roads.carts
        assert len(carts) >= 6 and all(h.model == traffic.DEMO for c in carts for h in c.payload.trail)
        gates = {b.id for b in host.town.scroll.buildings if (host.town.spec_of(b.id) or {}).get("type") == "loot" and b.roads}
        assert gates and gates <= {c.target for c in carts}
        snap = host.snapshot()
        assert any(c["tokens"] for c in snap["carts"])                  # their spend reaches the page
    finally:
        host.close()


def test_the_demo_results_make_a_lean_week():
    now = dt.datetime(2026, 10, 14, 20, 0).astimezone()
    s = score.town(None, now=now, rows=traffic.results(now))
    assert s["results"] > 0 and s["trend"] < 0 and s["tokens"] is not None


def test_a_review_gate_sends_a_cart_back_and_the_snapshot_says_where_it_goes_round(tmp_path: Path, monkeypatch):
    """design-system-v3.md §4c: a rework is handed straight back, not by a road; the snapshot gives its two ends so
    Camp draws it going round again to the building that made it."""
    from orkcraft.gui.host import Host
    monkeypatch.setattr(traffic.Traffic, "start", lambda self: None)
    root = demo.build(tmp_path / "d", set_name="dashboard")
    host = Host(root, False, root / ".orkcraft.json", demo=True)
    try:
        back = host.traffic.send_back()
        assert back and all(c.road_id == "sent-back" for c in back)
        snap = [c for c in host.snapshot()["carts"] if c.get("back")]
        assert snap and {(c["from"], c["to"]) for c in snap} == {(c.source, c.target) for c in back}
        assert all(c["state"] == "moving" and not c["stands"] for c in snap)
    finally:
        host.close()
