"""Rich text for the Textual face: what realm/ gives as plain data (strings, (text, style) pairs),
drawn as rich `Text` here so the domain needs no Rich."""
from __future__ import annotations

from rich.text import Text

from orkcraft.realm import lexicon, looks


def scheme_text(harness: list[dict] | None, kind: str = "agent") -> Text:
    t = Text()
    for text, style in looks.scheme_parts(harness, kind):
        t.append(text, style=style)
    return t


def worded_rich(value):
    """A rich Text in today's words (`realm/lexicon.py`), each word keeping the style of the one it
    replaces; a str as `lexicon.words`; anything else as it is. Emoji stay: the terminal keeps the camp's look."""
    if isinstance(value, str):
        return lexicon.words(value)
    if not isinstance(value, Text):
        return value
    found = lexicon.spans(value.plain)
    if not found:
        return value
    out, at = Text(style=value.style, end=value.end, no_wrap=value.no_wrap, overflow=value.overflow), 0
    for a, b, word in found:
        out.append_text(value[at:a])
        styles = [s.style for s in value[a:b].spans]
        out.append(word, style=styles[0] if styles else "")
        at = b
    out.append_text(value[at:])
    return out
