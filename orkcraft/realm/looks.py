"""How an orc looks: the icon tells its kind, colour + mark its harness scheme (✻ Claude, ✦ agy, ⌬ Codex).

    kind_icon("chain") == "🪧"; kind_icon("agent") == "🧌"; kind_icon("hybrid") == "🪧🧌"
    scheme_plain([{"role": "write", "harness": "agy"}, {"role": "review", "harness": "claude"}]) == "✦→✻"
    scheme_parts(steps)  # (text, style) pairs: Claude orange, agy blue, Codex green, pipelines magenta
"""
from __future__ import annotations

from orkcraft.realm import harnesses

KIND_ICONS = {"chain": "🪧", "script": "🪧", "agent": "🧌", "hybrid": "🪧🧌"}
OLD_ICONS = {"🗿": "🪧", "🗿🧌": "🪧🧌"}     # a scroll saved before the 🪧 keeps loading with it
KIND_LABELS = {"chain": "chain", "script": "script (runs later)", "agent": "agent", "hybrid": "hybrid (script + agent)"}
# One cell each, from the registry (Claude's spark, Gemini's sparkle, OpenAI's hexagon…)
HARNESS_LETTER = {h.id: h.mark for h in harnesses.REGISTRY.values()}
HARNESS_STYLE = {**{h.id: h.color for h in harnesses.REGISTRY.values()}, "pipeline": "bold #e879f9"}
LONG_SCHEME = 3          # longer schemes read as first→last·N


def kind_icon(kind: str) -> str:
    return KIND_ICONS.get(kind, "🧌")


def _letter(harness: str) -> tuple[str, str]:
    if harness.startswith("pipeline:"):
        return "P", HARNESS_STYLE["pipeline"]
    if harness in ("", harnesses.MAIN):                   # the machine's main tool, as it is now
        from orkcraft.realm import builders
        harness = builders.main_tool()
    return HARNESS_LETTER.get(harness, "?"), HARNESS_STYLE.get(harness, "bold")


def _steps(harness: list[dict] | None, kind: str) -> list[dict]:
    if kind in ("chain", "script"):
        return []
    return list(harness or [])


def scheme_parts(harness: list[dict] | None, kind: str = "agent") -> list[tuple[str, str]]:
    """[(text, style)] of the scheme; empty for chains and scripts (no harness)."""
    steps = _steps(harness, kind)
    if not steps:
        return []
    letters = [_letter(str(s.get("harness", ""))) for s in steps]
    if len(letters) > LONG_SCHEME:
        return [letters[0], ("→", "dim"), letters[-1], (f"·{len(letters)}", "dim")]
    out: list[tuple[str, str]] = []
    for i, part in enumerate(letters):
        if i:
            out.append(("→", "dim"))
        out.append(part)
    return out


def scheme_plain(harness: list[dict] | None, kind: str = "agent") -> str:
    return "".join(t for t, _ in scheme_parts(harness, kind))


def scheme_long(harness: list[dict] | None, kind: str = "agent") -> str:
    """`write: agy → review: claude` for cards."""
    steps = _steps(harness, kind)
    return " → ".join(f"{s.get('role', 'run')}: {s.get('harness', '?')}" for s in steps) or "—"
