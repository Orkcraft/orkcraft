"""Unit card and info panel (T1104 stage 2): building stats, handler costs, picking a burning
orc opens its question, spend math, and the orc's chat column (stage 3)."""
from __future__ import annotations

import json
from pathlib import Path


from orkcraft.realm import unit_info

SIZE = (200, 50)


def test_handler_spend_math(fake_repo: Path):
    assert unit_info.Spend().text() == "🪙 no data yet"
    log = fake_repo / "spend.jsonl"
    log.write_text("\n".join([
        json.dumps({"cost_usd": 0.05, "tokens": 2000}),
        json.dumps({"cost_usd": 0.15, "tokens": 8000}),
        json.dumps({"cost_usd": None, "tokens": 5000}),
    ]) + "\n")
    s = unit_info.handler_spend(log)
    assert (s.runs, round(s.usd, 2), s.tokens) == (3, 0.2, 15000)
    assert s.text() == "🪙 $0.20 · 🪵 15k tokens · 3 runs"
    assert unit_info.Spend(free=True).text() == "🪙 free · never calls a model"
    assert unit_info.Spend(free=True).add(s).usd == s.usd


# -- the orc's chat column (T1104 stage 3) -------------------------------------------------------

async def _settle(pilot, n: int = 4) -> None:
    for _ in range(n):
        await pilot.pause()
