"""A building type's card as a document (docs/design/improve-buildings.md §6.3): for each size of the card — small,
medium, large (js/hut.js `levelOf`) — which of its parts show, in which order, in which font and tone role.

Every card is drawn by its type's own code from the same parts: `big` (its one number or word), `text` (a line of
what it says), `foot` (what it works on, its roads) and `when` (when it last did something). A card document lays
those out; it never adds a colour or a font of its own (roles only, design/tokens.py), and a part it leaves out is
hidden. A type with none keeps its card as its code draws it.

The documents are this machine's look, like its pictures: one file per type under design/tokens.py `assets_dir`,
`cards/<type>.json`. The UX bench writes them (one checked model call from the person's words), the hut applies them.

    card_docs.load("barracks")            → the document, or None
    card_docs.ask(type, title, current, words, size, part, runner) → (document, problems, cost)
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

from orkcraft.design import tokens

VERSION = 1
SIZES = ("s", "m", "l")
SIZE_WORDS = {"s": "small", "m": "medium", "l": "large"}
PARTS = {"big": "the card's headline: its one number or word, large",
         "text": "a line of what it says now",
         "foot": "the bottom line: what it works on, where it sends",
         "when": "when it last did something"}
MAX_ATTEMPTS = 2


def default(type_id: str) -> dict:
    """Every part, in the order the cards draw them, at every size: the card as its code draws it."""
    return {"version": VERSION, "type": type_id,
            "sizes": {s: {"parts": [{"id": p} for p in PARTS]} for s in SIZES}}


def problems(doc, type_id: str) -> list[str]:
    if not isinstance(doc, dict):
        return ["a card document is an object"]
    out = []
    if doc.get("type") != type_id:
        out.append(f"type must be {type_id!r}")
    sizes = doc.get("sizes")
    if not isinstance(sizes, dict) or set(sizes) != set(SIZES):
        return out + [f"sizes must be exactly {', '.join(SIZES)}"]
    for s in SIZES:
        parts = (sizes[s] or {}).get("parts") if isinstance(sizes[s], dict) else None
        if not isinstance(parts, list):
            out.append(f"sizes.{s}.parts must be a list")
            continue
        seen = set()
        for p in parts:
            if not isinstance(p, dict) or p.get("id") not in PARTS:
                out.append(f"sizes.{s}: a part is one of {', '.join(PARTS)}")
                continue
            if p["id"] in seen:
                out.append(f"sizes.{s}: {p['id']} twice")
            seen.add(p["id"])
            if p.get("font") not in (None, "") and p["font"] not in tokens.FONTS:
                out.append(f"sizes.{s}.{p['id']}: font is a role: {', '.join(tokens.FONTS)}")
            if p.get("tone") not in (None, "") and p["tone"] not in tokens.TONES:
                out.append(f"sizes.{s}.{p['id']}: tone is a role: {', '.join(tokens.TONES)}")
            extra = set(p) - {"id", "font", "tone"}
            if extra:
                out.append(f"sizes.{s}.{p['id']}: no {', '.join(sorted(extra))} (roles only)")
        if not seen:
            out.append(f"sizes.{s}: show at least one part")
    return out


def path(type_id: str) -> Path:
    return tokens.assets_dir() / "cards" / f"{type_id}.json"


_READ: dict[Path, tuple[float, dict | None]] = {}     # a file → (its mtime, what it said): the snapshot asks often


def load(type_id: str) -> dict | None:
    p = path(type_id)
    try:
        mtime = p.stat().st_mtime
    except OSError:
        return None
    if (got := _READ.get(p)) is not None and got[0] == mtime:
        return copy.deepcopy(got[1])
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        doc = None
    doc = doc if doc is not None and not problems(doc, type_id) else None
    _READ[p] = (mtime, doc)
    return copy.deepcopy(doc)


def save(type_id: str, doc: dict) -> list[str]:
    wrong = problems(doc, type_id)
    if wrong:
        return wrong
    p = path(type_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    return []


def remove(type_id: str) -> None:
    path(type_id).unlink(missing_ok=True)


PROMPT = """You lay out the card of a building of Orkcraft, a town of AI agents: the small card under its house on the map.
The building: {title} ({type}).
A card has three sizes — small, medium, large — and is drawn from these parts:
{parts}
For each size say which parts show, top to bottom, and for each part optionally a font role ({fonts}) and a tone role
({tones}). Roles only: never a colour, a font name or a size of your own. A part left out is hidden at that size.
A small card says the one thing that matters; a large one may say everything.

The card now:
{current}

What to change, in the person's words: {request}{where}
{feedback}
Answer with JSON only: the whole new document, as {{"version": 1, "type": "{type}", "sizes": {{"s": {{"parts": [{{"id": "big", "font": "...", "tone": "..."}}]}}, "m": {{...}}, "l": {{...}}}}}}"""


def ask(type_id: str, title: str, current: dict, request: str, size: str = "", part: str = "", runner=None
        ) -> tuple[dict | None, list[str], float | None]:
    """The person's words → a checked card document (a wrong answer goes back once with its problems)."""
    from orkcraft.realm import builders
    run = runner or builders.main_runner
    where = ""
    if size in SIZES:
        where = f"\nChange the {SIZE_WORDS[size]} card" + (f", its `{part}` part only" if part in PARTS else "") + \
                "; keep the other sizes as they are."
    feedback, cost, wrong = "", None, ["no answer"]
    for _ in range(MAX_ATTEMPTS):
        prompt = PROMPT.format(title=title, type=type_id, parts="\n".join(f"- `{k}`: {v}" for k, v in PARTS.items()),
                               fonts=", ".join(tokens.FONTS), tones=", ".join(tokens.TONES),
                               current=json.dumps(current, ensure_ascii=False, indent=1), request=request.strip()[:1000],
                               where=where, feedback=feedback)
        try:
            text, c = run(prompt)
        except RuntimeError as e:
            return None, [str(e)], cost
        cost = (cost or 0.0) + (c or 0.0) if c is not None else cost
        doc = builders.extract_json(text)
        wrong = problems(doc, type_id)
        if not wrong:
            return copy.deepcopy(doc), [], cost
        feedback = "\nYOUR PREVIOUS ANSWER WAS REJECTED. Fix every problem:\n" + "\n".join(f"- {w}" for w in wrong[:10])
    return None, wrong, cost
