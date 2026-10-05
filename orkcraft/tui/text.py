"""Rich text for the Textual face: what realm/ gives as plain data (strings, (text, style) pairs),
drawn as rich `Text` here so the domain needs no Rich."""
from __future__ import annotations

import re

from rich.text import Text

from orkcraft.realm import looks, modes


def scheme_text(harness: list[dict] | None, kind: str = "agent") -> Text:
    t = Text()
    for text, style in looks.scheme_parts(harness, kind):
        t.append(text, style=style)
    return t


def strip_rich(value):
    """A rich Text without emoji, its styles kept (an icon goes with the space after it); a str as
    `modes.strip_emoji`; anything else as it is."""
    if isinstance(value, str):
        return modes.strip_emoji(value)
    if not isinstance(value, Text):
        return value
    plain = value.plain
    if plain.strip() in modes._WORDS or re.search(r"[👍👎]\s*\d", plain):
        return Text(modes.strip_emoji(plain), style=value.style)
    cuts = []
    for m in modes._EMOJI.finditer(plain):
        a, b = m.start(), m.end()
        while b < len(plain) and plain[b] == " " and (a == 0 or plain[a - 1] in " [(" or b + 1 == len(plain)):
            b += 1
        cuts.append((a, b))
    if not cuts:
        return value
    out, at = Text(style=value.style, end=value.end, no_wrap=value.no_wrap, overflow=value.overflow), 0
    for a, b in cuts:
        if a > at:
            out.append_text(value[at:a])
        at = max(at, b)
    if at < len(plain):
        out.append_text(value[at:])
    return out
