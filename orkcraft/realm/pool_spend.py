"""🪙 Where an Agent pool's tokens went, card by card (docs/specs/28-lean-pool.md §6, decisions-2026-10.md §40).

A card's spend is kept by part: the ork's own work, and the steward's calls split by what they were for — its answers
to an ork's question, its review of the work, its planning (the sort and the plan). Only what was counted already
(an ork's run, `RunOutcome.steward_cost` / `steward_tokens` by the use of each call) goes in; nothing is estimated.
The pool's hop carries it on the cart, and the waybill at the Review gate shows it as one line.

    spend = {}
    pool_spend.add(spend, "ork", 12000, 0.4)
    pool_spend.add(spend, pool_spend.part_of("review"), 3000, 0.05)
    pool_spend.rows(spend)          # (("ork", 12000, 0.4), ("review", 3000, 0.05)) in PARTS order
"""
from __future__ import annotations

PARTS = ("ork", "answers", "review", "planning")
PART_OF_USE = {"answer": "answers", "review": "review", "final": "review", "triage": "planning", "plan": "planning"}


def part_of(use: str) -> str:
    """The part a steward's call counts under, by its `use` (core/workers/barracks.py `_steward`)."""
    return PART_OF_USE.get(use, "review")


def add(spend: dict, part: str, tokens: int | None, cost: float | None) -> dict:
    """Adds one call's tokens and cost to `spend` ({part: [tokens, cost]}); nothing when both are none."""
    if not tokens and not cost:
        return spend
    got = spend.setdefault(part, [0, 0.0])
    got[0] = int(got[0] or 0) + int(tokens or 0)
    got[1] = round(float(got[1] or 0.0) + float(cost or 0.0), 6)
    return spend


def merge(spend: dict, *more: dict) -> dict:
    """`spend` with every other's parts added (a plan's whole: its own and its parts')."""
    out = {k: [int(v[0] or 0), float(v[1] or 0.0)] for k, v in (spend or {}).items()}
    for m in more:
        for k, v in (m or {}).items():
            add(out, k, v[0], v[1])
    return out


def rows(spend: dict) -> tuple[tuple[str, int, float], ...]:
    """(part, tokens, cost) of each part spent on, in PARTS order: what a hop carries."""
    return tuple((p, int(spend[p][0] or 0), round(float(spend[p][1] or 0.0), 4)) for p in PARTS if p in (spend or {}))
