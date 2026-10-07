"""Finding in the Wiki (docs/design/wiki-librarian.md §7), and the light model's word on a Quick note
(§4) when the rules found nothing.

`find` looks for what a person types over the wiki's pages and the notes of its sources: a page whose
title or aliases hold the query comes first, then the pages that share the most words with it (in any
script and inflection), each with the line that says it. No model.

`model_prompt` / `parse_model`: one call to the light model with the note, the wiki's sections and the
people it knows; it answers one line of JSON, and only what fits (a known section, known people, short
tags) is kept.

Pure module, no Textual.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from orkcraft.realm import quicknote, wiki
from orkcraft.realm.shelves import Note

LIMIT = 30
LINE_CHARS = 160
MIN_WORDS = 4                    # a note shorter than this is not worth a model call
_JSON = re.compile(r"\{.*\}", re.S)


def _line(text: str, words: set[str], query: str) -> str:
    """The first line of the body that says the query, or one of its words; else its first line."""
    body = quicknote.body_of(text)
    lines = [ln.strip(" >-*") for ln in body.splitlines() if ln.strip(" >-*") and not ln.lstrip().startswith("#")]
    q = query.lower()
    for ln in lines:
        if q in ln.lower() or words & wiki.stems(ln):
            return ln[:LINE_CHARS]
    return (lines[0] if lines else "")[:LINE_CHARS]


def find(repo_root: Path, notes: list[Note], query: str, limit: int = LIMIT) -> list[dict]:
    """The pages and notes that match `query`, best first: {path, title, line, page}."""
    query = " ".join((query or "").split())[:200]
    words = wiki.stems(query)
    if not query:
        return []
    q = query.lower()
    scored = []
    for n in notes:
        try:
            text = (repo_root / n.path).read_text(encoding="utf-8")
        except OSError:
            continue
        names = quicknote.names_of(text, n.title)
        name_hit = any(q in name.lower() for name in names)
        hits = len(words & wiki.stems(text)) + 3 * len(words & wiki.stems(" ".join(names)))
        if not name_hit and not hits and q not in text.lower():
            continue
        score = (10 if name_hit else 0) + hits + (1 if q in text.lower() else 0)
        scored.append((-score, n.path, {"path": n.path, "title": n.title, "line": _line(text, words, query),
                                        "page": wiki.is_page(n.path)}))
    return [x for *_, x in sorted(scored)[:limit]]


def worth_asking(text: str, hint: quicknote.Suggestion) -> bool:
    """Ask the light model only when the rules found nothing and the note says something."""
    return not hint.links and not hint.meeting and not hint.people and len((text or "").split()) >= MIN_WORDS


def model_prompt(text: str, topic: str, sections: list[str], people: list[str]) -> str:
    return (f"A person left a short note for a wiki about {topic}. Read it and answer with ONE line of JSON, "
            f'nothing else: {{"section": one of {json.dumps(sections, ensure_ascii=False)} or "", '
            f'"tags": up to 4 short lowercase tags, in the note\'s language, '
            f'"people": the names from {json.dumps(people, ensure_ascii=False)} the note mentions, in any form}}.\n\n'
            f"The note:\n{(text or '')[:2000]}")


def parse_model(answer: str, sections: list[str], people: list[str]) -> dict:
    """What fits of the model's answer: {section, tags, people}; empty when it said nothing usable."""
    m = _JSON.search(answer or "")
    try:
        data = json.loads(m.group(0)) if m else {}
    except ValueError:
        data = {}
    if not isinstance(data, dict):
        data = {}
    section = str(data.get("section") or "")
    tags = data.get("tags") if isinstance(data.get("tags"), list) else []
    named = data.get("people") if isinstance(data.get("people"), list) else []
    return {"section": section if section in sections else "",
            "tags": [t for t in (" ".join(str(x).lower().split())[:40] for x in tags[:4]) if t],
            "people": [p for p in people if p in {str(x) for x in named}]}
