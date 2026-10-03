"""Orc tiers: how heavy a model an orc thinks with.

    🔮 elder     the heavy models: opus, gemini pro
    ⚔ warrior    the middle: sonnet, gemini flash with high reasoning
    ⛏ laborer    the light ones: haiku, gemini flash with low reasoning

A harness step picks its tier (`{"role": "run", "harness": "claude", "tier": "elder"}`) and the
model follows from the harness; a step may name its `model` outright, and the tier is read from
it. An orc's tier is its heaviest step. Stewards carry no tier icon: they keep the building.
"""
from __future__ import annotations

TIERS = ("elder", "warrior", "laborer")          # heaviest first
TIER_ICONS = {"elder": "🔮", "warrior": "⚔", "laborer": "⛏"}
TIER_LABELS = {"elder": "Elder", "warrior": "Warrior", "laborer": "Laborer"}
TIER_STYLES = {"elder": "bold #c084fc", "warrior": "bold #f87171", "laborer": "#a8a29e"}
# The model of each tier, per harness.
MODELS = {
    "claude": {"elder": "opus", "warrior": "sonnet", "laborer": "haiku"},
    "agy": {"elder": "gemini-3.1-pro-high", "warrior": "gemini-3.8-flash-high", "laborer": "gemini-3.8-flash-low"},
}
# What a step runs on when it names neither: agy's own default is flash-high.
DEFAULT_MODEL = {"agy": MODELS["agy"]["warrior"]}


def tier_of_model(model: str) -> str | None:
    """opus / gemini pro → elder; sonnet / flash-high → warrior; haiku / flash-low → laborer."""
    m = (model or "").lower()
    if not m:
        return None
    if "opus" in m or "fable" in m or ("gemini" in m and "pro" in m):
        return "elder"
    if "haiku" in m or ("flash" in m and ("low" in m or "lite" in m)):
        return "laborer"
    if "sonnet" in m or "flash" in m:
        return "warrior"
    return None


def step_model(step: dict) -> str:
    """The model a harness step runs on: its own, else its tier's, else "" (the CLI's default)."""
    if step.get("model"):
        return str(step["model"])
    tier = step.get("tier")
    return MODELS.get(str(step.get("harness", "")), {}).get(str(tier), "") if tier else ""


def resolve(harness: str, model: str) -> str:
    """`claude:elder` → opus: a tier word in place of a model names its model; anything else stays."""
    return MODELS.get(harness, {}).get(model, model) if model in TIERS else model


def model_icon(harness: str, model: str) -> str:
    """The tier icon of one harness:model pair (barracks orcs, council members)."""
    return icon(step_tier({"harness": harness, "model": model}))


def step_tier(step: dict) -> str | None:
    model = step_model(step) or DEFAULT_MODEL.get(str(step.get("harness", "")), "")
    return tier_of_model(model) or (step.get("tier") if step.get("tier") in TIERS else None)


def orc_tier(harness: list[dict] | None, kind: str = "agent") -> str | None:
    """The heaviest tier among the steps; None for chains, scripts and unknown models."""
    if kind in ("chain", "script"):
        return None
    found = {t for t in (step_tier(s) for s in harness or []) if t}
    return next((t for t in TIERS if t in found), None)


def icon(tier: str | None) -> str:
    return TIER_ICONS.get(tier or "", "")


def label(tier: str | None) -> str:
    return f"{TIER_ICONS[tier]} {TIER_LABELS[tier]}" if tier in TIER_ICONS else ""


def with_tier(harness: list[dict], tier: str | None) -> list[dict]:
    """The steps moved to `tier` (None: back to the CLI's default); a named model gives way."""
    out = []
    for s in harness:
        step = {k: v for k, v in s.items() if k not in ("tier", "model")}
        if tier in TIERS:
            step["tier"] = tier
        out.append(step)
    return out
