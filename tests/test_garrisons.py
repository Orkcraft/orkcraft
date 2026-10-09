"""Tests for garrisons: persistent orcs, garrison badges, recruiting, deployment and dismissal."""
from __future__ import annotations



from orkcraft.realm.orcs import RESIDENT, Orc, Trigger, garrison_badge

SIZE = (200, 50)


def garrison_orcs(b: dict) -> list[dict]:
    """Steward first, then handlers — the v3 file layout of a garrison."""
    g = b["garrison"]
    return ([g["steward"]] if g.get("steward") else []) + g.get("handlers", [])


def test_garrison_badge():
    """1. garrison_badge: lead only → 🧌 Smith 🔨 💤; lead + 2 idle → Smith+2;
    one member in alert → ends with 🔥; one busy, none in alert → ⚙."""
    lead = Orc("Smith", "blacksmith", RESIDENT, Trigger(), "idle", lead=True)
    assert garrison_badge([lead]) == "🧌 Smith 🔨 💤"

    m1 = Orc("Coder", "tickets", RESIDENT, Trigger(), "idle")
    m2 = Orc("Tester", "qa", RESIDENT, Trigger(), "idle")
    badge_idle = garrison_badge([lead, m1, m2])
    assert "Smith+2" in badge_idle
    assert badge_idle == "🧌 Smith+2 🔨 💤"

    m1.status = "alert"
    badge_alert = garrison_badge([lead, m1, m2])
    assert badge_alert.endswith("🔥")

    m1.status = "busy"
    badge_busy = garrison_badge([lead, m1, m2])
    assert badge_busy.endswith("⚙")
