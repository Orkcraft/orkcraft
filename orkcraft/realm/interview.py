"""The Town Builder's order when none of the ready towns fits: who the operator is, what is in the
project, and what the town should do — in their own words, one phrase.

    summary(profile, wish, signs)   everything said, as the Town Builder's order

The onboarding asks nothing else for now: the role is an indie maker's (intents.FOUNDER), the
project shows the rest (intents.project_signs).
"""
from __future__ import annotations

from orkcraft.realm import intents


def who(profile: dict) -> str:
    """"Founder / indie maker" — the role, as the operator is known."""
    return intents.role(profile.get("role", "")).title


def summary(profile: dict, wish: str, signs: str = "") -> str:
    """The order, one line each: who, what the project shows, what the town should do."""
    lines = [f"I am {who(profile)}, and I already work with AI agents."]
    if signs:
        lines.append(f"In this project: {signs}.")
    wish = wish.strip()
    if wish:
        lines.append(f"The town should: {wish.rstrip('.')}.")
    return "\n".join(lines)
