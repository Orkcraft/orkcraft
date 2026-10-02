"""Claude token prices — facts, not memory.

Source: https://platform.claude.com/docs/en/about-claude/pricing (read 2026-09-29), first-party
Claude API rates in USD per million tokens. Cache writes are 1.25x (5 min) and 2x (1 h) the base
input price; cache hits are 0.1x, except 0.025x on Claude Fable 5.1 / Claude Mythos 5.1 and 0.05x
on Claude Opus 5.5 — the table below carries the published numbers, not the multipliers.
Fast mode (Opus 5.5 / 5 / 4.8) replaces the base input / output price and the cache multipliers
apply on top; `inference_geo: "us"` multiplies everything by 1.1 on Claude 4.6 and later.

What this is not: a bill. Subscription plans (Claude Pro / Max) do not charge per token, and
Bedrock / Vertex price separately; the costs computed here are API-equivalent estimates. When a
model is not in the table the cost is unknown (None) — never a guess.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

PRICES_SOURCE = "https://platform.claude.com/docs/en/about-claude/pricing"
PRICES_AS_OF = "2026-09-29"
US_GEO_MULTIPLIER = 1.1


@dataclass(frozen=True)
class Price:
    input: float        # $ / MTok
    cache_5m: float     # 5-minute cache write
    cache_1h: float     # 1-hour cache write
    cache_read: float   # cache hit / refresh
    output: float
    fast_input: float | None = None
    fast_output: float | None = None
    geo_us: bool = True  # Claude 4.6+: inference_geo "us" costs 1.1x


# Model id (as the API and Claude Code transcripts spell it, without a date suffix) → price.
PRICES: dict[str, Price] = {
    "claude-fable-5-1": Price(10, 12.50, 20, 0.25, 50),
    "claude-mythos-5-1": Price(10, 12.50, 20, 0.25, 50),
    "claude-fable-5": Price(10, 12.50, 20, 1, 50),
    "claude-mythos-5": Price(10, 12.50, 20, 1, 50),
    "claude-opus-5-5": Price(4, 5, 8, 0.20, 20, fast_input=8, fast_output=40),
    "claude-opus-5": Price(5, 6.25, 10, 0.50, 25, fast_input=10, fast_output=50),
    "claude-opus-4-8": Price(5, 6.25, 10, 0.50, 25, fast_input=10, fast_output=50),
    "claude-opus-4-7": Price(5, 6.25, 10, 0.50, 25),
    "claude-opus-4-6": Price(5, 6.25, 10, 0.50, 25),
    "claude-opus-4-5": Price(5, 6.25, 10, 0.50, 25, geo_us=False),
    "claude-opus-4-1": Price(15, 18.75, 30, 1.50, 75, geo_us=False),
    "claude-opus-4": Price(15, 18.75, 30, 1.50, 75, geo_us=False),
    "claude-sonnet-5-5": Price(2, 2.50, 4, 0.20, 10),
    "claude-sonnet-5": Price(2, 2.50, 4, 0.20, 10),
    "claude-sonnet-4-6": Price(3, 3.75, 6, 0.30, 15),
    "claude-sonnet-4-5": Price(3, 3.75, 6, 0.30, 15, geo_us=False),
    "claude-sonnet-4": Price(3, 3.75, 6, 0.30, 15, geo_us=False),
    "claude-haiku-4-5": Price(1, 1.25, 2, 0.10, 5, geo_us=False),
    "claude-3-5-haiku": Price(0.80, 1, 1.60, 0.08, 4, geo_us=False),
}
# Other spellings of the same models.
ALIASES = {
    "claude-sonnet-4-0": "claude-sonnet-4",
    "claude-opus-4-0": "claude-opus-4",
    "claude-haiku-3-5": "claude-3-5-haiku",
}
_DATE = re.compile(r"-\d{8}$")
_SUFFIX = re.compile(r"\[[^\]]*\]$")  # Claude Code's context-window suffix, e.g. "[1m]"


def normalize(model: str) -> str:
    m = _SUFFIX.sub("", model.strip().lower())
    m = m.split("@", 1)[0]                                   # Vertex "claude-opus-4-5@20251101"
    m = m.removeprefix("anthropic.").removeprefix("us.anthropic.").removeprefix("global.anthropic.")
    m = re.sub(r"-v\d+(:\d+)?$", "", m)                      # Bedrock "-v1:0"
    m = _DATE.sub("", m)
    return ALIASES.get(m, m)


def price_for(model: str | None) -> Price | None:
    if not model:
        return None
    return PRICES.get(normalize(model))


def usage_cost(model: str | None, usage: dict) -> float | None:
    """USD for one assistant message's `usage`; None when the model has no published price.

    `usage.cache_creation` splits writes by TTL; without it every write counts as 5-minute.
    """
    p = price_for(model)
    if p is None:
        return None
    fast = usage.get("speed") == "fast" and p.fast_input is not None
    base_in = p.fast_input if fast else p.input
    out = p.fast_output if fast else p.output
    # Cache prices are multiples of the base input price, so fast mode scales them too.
    scale = base_in / p.input
    creation = usage.get("cache_creation") if isinstance(usage.get("cache_creation"), dict) else None
    total_writes = int(usage.get("cache_creation_input_tokens") or 0)
    if creation:
        w1h = int(creation.get("ephemeral_1h_input_tokens") or 0)
        w5m = int(creation.get("ephemeral_5m_input_tokens") or 0) or max(total_writes - w1h, 0)
    else:
        w1h, w5m = 0, total_writes
    dollars = (
        int(usage.get("input_tokens") or 0) * base_in
        + int(usage.get("output_tokens") or 0) * out
        + int(usage.get("cache_read_input_tokens") or 0) * p.cache_read * scale
        + w5m * p.cache_5m * scale
        + w1h * p.cache_1h * scale
    ) / 1_000_000
    if usage.get("inference_geo") == "us" and p.geo_us:
        dollars *= US_GEO_MULTIPLIER
    return dollars


def context_of(usage: dict) -> int:
    """Tokens the model read on that turn: fresh input plus everything read from / written to cache."""
    return (int(usage.get("input_tokens") or 0) + int(usage.get("cache_read_input_tokens") or 0)
            + int(usage.get("cache_creation_input_tokens") or 0))
