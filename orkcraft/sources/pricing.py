"""Claude token prices — facts, not memory.

Source: https://platform.claude.com/docs/en/about-claude/pricing (read 2026-09-29), first-party
Claude API rates in USD per million tokens. Cache writes are 1.25x (5 min) and 2x (1 h) the base
input price; cache hits are 0.1x, except 0.025x on Claude Fable 5.1 / Claude Mythos 5.1 and 0.05x
on Claude Opus 5.5 — the table below carries the published numbers, not the multipliers.
Fast mode (Opus 5.5 / 5 / 4.8) replaces the base input / output price and the cache multipliers
apply on top; `inference_geo: "us"` multiplies everything by 1.1 on Claude 4.6 and later.

What this is not: a bill. Subscription plans (Claude Pro / Max) do not charge per token, and
Bedrock / Vertex price separately; the costs computed here are API-equivalent estimates. A model
not in the table is priced as the nearest version of its family that is (`claude-opus-5-7` as
`claude-opus-5-5`; a version-less name, `opus` or `gpt-astra`, as the newest); a model of no family
in the table is unknown (None) — never $0.

OpenAI's prices (Codex runs) are a second table, `OPENAI_PRICES`, with its own source and date. It is
filled only from OpenAI's pricing page read first-hand by a person; until then it stays empty and
every Codex run is unpriced (docs/design/codex-limits.md §4, §5.2).
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


_CLAUDE = re.compile(r"^claude-(?:(?P<fam>[a-z]+)-(?P<v>\d+(?:-\d{1,2})?)|(?P<v2>\d+(?:-\d{1,2})?)-(?P<fam2>[a-z]+))$")


def _claude_family(model: str) -> tuple[str, tuple[int, ...] | None] | None:
    """`claude-opus-5-5` → ("opus", (5, 5)); `opus` → ("opus", None); None when it names no family."""
    if re.fullmatch(r"[a-z]+", model):
        return model, None
    m = _CLAUDE.match(model)
    if not m:
        return None
    v = m.group("v") or m.group("v2")
    return m.group("fam") or m.group("fam2"), tuple(int(p) for p in v.split("-"))


def nearest(table: dict, key: str, family_of) -> str | None:
    """The key of `table` nearest to `key` in its family: the same family, the closest version (the newer
    on a tie), the newest when `key` names no version; None when its family is not in the table."""
    want = family_of(key)
    if want is None:
        return None
    fam, version = want
    same = [(k, kv[1]) for k in table if (kv := family_of(k)) is not None and kv[0] == fam and kv[1] is not None]
    if not same:
        return None

    def num(v: tuple[int, ...]) -> float:
        return v[0] + (v[1] / 100 if len(v) > 1 else 0)

    if version is None:
        return max(same, key=lambda kv: num(kv[1]))[0]
    return min(same, key=lambda kv: (abs(num(kv[1]) - num(version)), -num(kv[1])))[0]


def price_for(model: str | None) -> Price | None:
    if not model:
        return None
    m = normalize(model)
    if m in PRICES:
        return PRICES[m]
    near = nearest(PRICES, m, _claude_family)
    return PRICES[near] if near else None


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


# -- OpenAI (Codex) ---------------------------------------------------------------------------------
# Read first-hand from the page below, with the date it was read. Empty: not read yet (openai.com
# could not be reached from where this was built), so Codex runs stay unpriced (`+`), never guessed.
OPENAI_PRICES_SOURCE = "https://developers.openai.com/api/docs/pricing"
OPENAI_PRICES_AS_OF = ""


@dataclass(frozen=True)
class OpenAIPrice:
    input: float                         # $ / MTok, standard tier, short context
    cached_input: float
    output: float                        # reasoning tokens are part of the output
    cache_write: float | None = None     # None: a cache write costs the input price
    long_input: float | None = None      # long context, from `long_from_tokens` input tokens per request
    long_cached: float | None = None
    long_output: float | None = None
    long_from_tokens: int | None = None


# Model id as Codex spells it (`gpt-6-astra`) → price.
OPENAI_PRICES: dict[str, OpenAIPrice] = {}


_OPENAI = re.compile(r"^(?P<first>[a-z]+)-(?P<v>\d+(?:\.\d+)?)(?:-(?P<rest>[a-z][a-z-]*))?$")


def _openai_family(model: str) -> tuple[str, tuple[int, ...] | None] | None:
    """`gpt-6.1-sol` → ("gpt-sol", (6, 1)); `gpt-sol` → ("gpt-sol", None)."""
    if re.fullmatch(r"[a-z]+(?:-[a-z]+)+", model):
        return model, None
    m = _OPENAI.match(model)
    if not m:
        return None
    fam = m.group("first") + (f"-{m.group('rest')}" if m.group("rest") else "")
    return fam, tuple(int(p) for p in m.group("v").split("."))


def openai_price_for(model: str | None) -> OpenAIPrice | None:
    if not model:
        return None
    m = model.strip().lower().removeprefix("openai/")
    if m in OPENAI_PRICES:
        return OPENAI_PRICES[m]
    near = nearest(OPENAI_PRICES, m, _openai_family)
    return OPENAI_PRICES[near] if near else None


def codex_usage_cost(model: str | None, usage: dict, one_request: bool = False) -> float | None:
    """USD for a Codex token usage block (`input_tokens`, `cached_input_tokens`,
    `cache_write_input_tokens`, `output_tokens`); None when the model has no price.

    Codex's input counts its cached reads and its cache writes (openai/codex `codex-api`
    `parses_cache_write_token_usage`: 100 in = 40 cached + 60 written), so the fresh input is what is
    left. Long-context prices apply only to `one_request` usage past the threshold: a run's total
    sums many requests and is priced at the short-context rates.
    """
    p = openai_price_for(model)
    if p is None or not isinstance(usage, dict):
        return None

    def n(key: str) -> int:
        v = usage.get(key)
        return max(int(v), 0) if isinstance(v, (int, float)) else 0

    total_in, cached, written, out = n("input_tokens"), n("cached_input_tokens"), n("cache_write_input_tokens"), n("output_tokens")
    fresh = max(total_in - cached - written, 0)
    long = (one_request and p.long_from_tokens is not None and total_in > p.long_from_tokens
            and None not in (p.long_input, p.long_cached, p.long_output))
    rate_in = p.long_input if long else p.input
    rate_cached = p.long_cached if long else p.cached_input
    rate_out = p.long_output if long else p.output
    rate_write = p.cache_write if p.cache_write is not None else rate_in
    return (fresh * rate_in + cached * rate_cached + written * rate_write + out * rate_out) / 1_000_000
