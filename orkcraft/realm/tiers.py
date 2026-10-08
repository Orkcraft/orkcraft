"""Orc tiers: how heavy a model an orc thinks with.

    🔮 elder     the heavy models: opus, gemini pro, gpt astra
    ⚔ warrior    the middle: sonnet, gemini flash with high reasoning, gpt sol
    ⛏ laborer    the light ones: haiku, gemini flash with low reasoning, gpt luna

A harness step picks its tier (`{"role": "run", "harness": "claude", "tier": "elder"}`) and the
model follows from the harness; a step may name its `model` outright, and the tier is read from
it. An orc's tier is its heaviest step. Stewards carry no tier icon: they keep the building.
"""
from __future__ import annotations

from orkcraft.realm import harnesses, model_families

TIERS = ("elder", "warrior", "laborer")          # heaviest first
TIER_ICONS = {"elder": "🔮", "warrior": "⚔", "laborer": "⛏"}
TIER_LABELS = {"elder": "Elder", "warrior": "Warrior", "laborer": "Laborer"}
TIER_STYLES = {"elder": "bold #c084fc", "warrior": "bold #f87171", "laborer": "#a8a29e"}
# The model family of each tier, per harness (realm/harnesses.py holds them; a run names its newest model).
MODELS = {h.id: dict(h.models) for h in harnesses.REGISTRY.values()}
# What a step runs on when it names neither: agy's own default is flash-high.
DEFAULT_MODEL = {h.id: h.default_model for h in harnesses.REGISTRY.values() if h.default_model}


def model_label(model: str) -> str:
    """What a person reads for a model: a family with the version it runs on (`Gemini Flash High (3.8)`)."""
    return model_families.label(model)


def tool_of(step: dict) -> str:
    """The tool a step runs on: `main` (or none) is the machine's main tool, as it is now."""
    harness = str(step.get("harness") or "")
    if harness in ("", harnesses.MAIN):
        from orkcraft.realm import builders
        return builders.main_tool()
    return harness


def tier_of_model(model: str) -> str | None:
    """opus / gemini pro / gpt astra → elder; sonnet / flash-high / gpt sol → warrior;
    haiku / flash-low / gpt luna → laborer (and every tool's own table, realm/harnesses.py)."""
    return harnesses.tier_of_model(model)


def step_model(step: dict) -> str:
    """The model a harness step runs on: its own, else its tier's, else "" (the CLI's default)."""
    if step.get("model"):
        return str(step["model"])
    tier = step.get("tier")
    return MODELS.get(tool_of(step), {}).get(str(tier), "") if tier else ""


def resolve(harness: str, model: str) -> str:
    """`claude:elder` → opus: a tier word in place of a model names its model; anything else stays."""
    return MODELS.get(tool_of({"harness": harness}), {}).get(model, model) if model in TIERS else model


def model_icon(harness: str, model: str) -> str:
    """The tier icon of one harness:model pair (barracks orcs, council members)."""
    return icon(step_tier({"harness": harness, "model": model}))


def step_tier(step: dict) -> str | None:
    model = step_model(step) or DEFAULT_MODEL.get(tool_of(step), "")
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
