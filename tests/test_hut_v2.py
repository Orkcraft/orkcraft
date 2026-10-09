"""Huts: every camp building has its own silhouette; the name stands above it, the buttons under it."""
from __future__ import annotations


import pytest

from orkcraft import scroll as ts
from orkcraft.realm import catalog, huts

SIZE = (200, 56)

# the design: (footprint width, the widths of the text slots) per building
DESIGN = {
    "mill": (15, [8]), "catapult": (17, [8]), "horn": (14, [8]), "pit": (9, [1]), "signpost": (10, [6, 6]), "watchtower": (18, [16] * 3),
    "fields": (26, [24] * 9), "barracks": (18, [16] * 7), "council": (18, [16] * 7), "forge": (18, [16] * 7),
    "scrolls": (18, [16] * 7), "war_drum": (26, [24] * 9), "forest": (26, [24] * 9), "loot": (26, [24] * 9),
    "crag": (26, [24] * 9), "lake": (60, [58] + [28, 24] * 6 + [58]),
}


@pytest.fixture
def town(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ts, "DEFAULT_VIEW", "town")


async def _settle(pilot, n: int = 4) -> None:
    for _ in range(n):
        await pilot.pause()


def _spec(bid: str, type_: str, **kw) -> dict:
    base = {"id": bid, "title": bid.title(), "icon": "🏗", "orc": {"name": "Peon"}, "type": type_}
    if type_ == "watchtower":
        base["config"] = {"github": "a/b"}
    return {**base, **kw}


def test_ten_roofs_fit_every_frame_size():
    assert len(huts.ROOFS) == 10
    for name in huts.ROOFS:
        for size in catalog.SIZES.values():
            lines = huts.roof(name, size[0] - 4)
            assert 2 <= len(lines) <= 3 and all(len(ln) <= size[0] - 4 for ln in lines), (name, size)
    assert huts.roof("gable", 14)[0].strip() == "/\\" and huts.roof("nope", 14) == ()
    assert catalog.validate(_spec("t", "fields", roof="tower"))[0].startswith("roof: no 'tower'")
