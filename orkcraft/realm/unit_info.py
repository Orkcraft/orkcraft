"""The Info panel: what a selected orc or building does, on which models, at what cost.

Pure: the sentences are put together from what the scroll and the roster already know (role,
kind, roads, trigger, the Recruiter's reason, the current task or question) — no model is called.
The spend is read, never estimated: handler runs from their examples log (`cost_usd`, `tokens`),
live sessions from the telemetry of this run. What is not known is said so, never shown as 0.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from orkcraft.realm import harnesses, model_families, tiers
from orkcraft.realm.looks import HARNESS_LETTER, HARNESS_STYLE
from orkcraft.realm.orcs import COUNCIL, RESIDENT, WORKER, Orc

MAX_SENTENCES = 3
SENTENCE_CHARS = 170
KIND_TEXT = {"chain": "a free chain (no model)", "script": "a script (no model)", "agent": "an agent",
             "steward": "a road rule its steward carries out",
             "hybrid": "a chain with an agent step"}
FREE_KINDS = ("chain", "script")


def _sentence(text: str) -> str:
    text = " ".join(str(text).split()).rstrip(" .")
    if len(text) > SENTENCE_CHARS:
        text = text[:SENTENCE_CHARS - 1].rstrip() + "…"
    return f"{text[:1].upper()}{text[1:]}." if text else ""


def _first_sentence(text: str) -> str:
    text = " ".join(str(text).split())
    for stop in (". ", "! ", "? "):
        if stop in text:
            return text.split(stop, 1)[0]
    return text


def orc_sentences(orc: Orc, building_title: str = "") -> list[str]:
    """Up to three sentences: what it is for, how it runs, what it is doing (or waits for) now."""
    out = [_sentence(f"{orc.name}: {orc.role}" if orc.role else f"{orc.name} has no role yet")]
    kind = KIND_TEXT.get(orc.kind, orc.kind)
    if orc.category == RESIDENT and orc.lead:
        trigger = getattr(orc.trigger, "label", "")
        out.append(_sentence(f"Steward of {building_title or 'its building'}, watches it "
                             f"{trigger or 'on demand'} and proposes cheaper handlers"))
    elif orc.category == RESIDENT and orc.roads:
        more = f" and {len(orc.roads) - 2} more" if len(orc.roads) > 2 else ""
        out.append(_sentence(f"Runs as {kind} on {', '.join(orc.roads[:2])}{more}"))
    elif orc.category == RESIDENT:
        out.append(_sentence(f"{kind} with no road yet — Y on the building gives it work"))
    elif orc.category == WORKER:
        out.append(_sentence("A live session in the War Tent"))
    elif orc.category == COUNCIL:
        out.append(_sentence("A member of the clan at the Clan Fire"))
    if orc.alert is not None:
        out.append(_sentence(f"Waits for you: {orc.alert.title}"))
    elif orc.task:
        out.append(_sentence(f"Working on {orc.task}" if orc.status == "busy" else f"Orders: {orc.task}"))
    elif orc.why:
        out.append(_sentence(_first_sentence(orc.why)))
    return [s for s in out if s][:MAX_SENTENCES]


# -- models -----------------------------------------------------------------------------------------

def short_model(model: str) -> str:
    """A dated Claude id → `opus 4.1`; a Gemini id → `gemini 3.1 pro`; a family (`gemini-flash-high`) →
    `Gemini Flash High (3.8)`, the version it runs on."""
    m = (model or "").lower()
    if not m:
        return ""
    if model_families.is_family(m):
        return model_families.label(m)
    for family in ("opus", "sonnet", "haiku", "fable"):
        if family in m:
            tail = m.split(family, 1)[1].strip("-").split("-")
            nums = [t for t in tail if t.isdigit() and len(t) <= 2][:2]
            return f"{family} {'.'.join(nums)}".strip()
    if m.startswith("gemini"):
        return " ".join(m.split("-")[:3])
    return m[:20]


def models_of(orc: Orc, live_model: str = "") -> list[tuple[str, str, str]]:
    """(letter, style, label) per model the orc runs on; a free chain says so."""
    if orc.kind in FREE_KINDS and orc.category == RESIDENT:
        return [("🪧", "", "no model — free")]
    out = []
    for step in orc.harness or ([{"harness": "main"}] if orc.category == RESIDENT else []):
        harness = tiers.tool_of(step)
        letter = HARNESS_LETTER.get(harness, "P" if harness == "pipeline" else "?")
        model = tiers.step_model(step)
        name = short_model(model) if model else \
            harnesses.title(harness)
        label = f"{step.get('role', '')} · {name}".strip(" ·")
        out.append((letter, HARNESS_STYLE.get(harness, "bold"), label))
    if live_model:
        out.append(("●", "bold green", f"live · {short_model(live_model)}"))
    return out


# -- spend ------------------------------------------------------------------------------------------

@dataclass
class Spend:
    usd: float | None = None      # None: not known
    tokens: int | None = None
    runs: int = 0
    free: bool = False            # a chain or script: never calls a model

    def add(self, other: Spend) -> Spend:
        def plus(a, b):
            return b if a is None else a if b is None else a + b
        return Spend(plus(self.usd, other.usd), plus(self.tokens, other.tokens), self.runs + other.runs,
                     self.free and other.free)

    def text(self) -> str:
        if self.free and not self.runs and self.usd is None:
            return "🪙 free · never calls a model"
        parts = [f"🪙 ${self.usd:.2f}" if self.usd is not None else "🪙 no data yet"]
        if self.tokens is not None:
            parts.append(f"🪵 {fmt_tokens(self.tokens)} tokens")
        if self.runs:
            parts.append(f"{self.runs} run{'s' if self.runs != 1 else ''}")
        return " · ".join(parts)


def fmt_tokens(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1000:
        return f"{round(n / 1000)}k"
    return str(n)


def handler_spend(path: Path) -> Spend:
    """What the handler's model runs cost, from its examples log (one JSON line per run)."""
    spend = Spend()
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return spend
    for line in lines:
        try:
            e = json.loads(line)
        except ValueError:
            continue
        if not isinstance(e, dict):
            continue
        spend.runs += 1
        if isinstance(e.get("cost_usd"), (int, float)):
            spend.usd = (spend.usd or 0.0) + float(e["cost_usd"])
        if isinstance(e.get("tokens"), int):
            spend.tokens = (spend.tokens or 0) + e["tokens"]
    return spend
