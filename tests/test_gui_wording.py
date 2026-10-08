"""The GUI's templates are written in today's words (CLAUDE.md → Wording): no `html` template's own text
says an old Camp spelling, since the page no longer rewrites them. What the town's data says goes through
`say()` in the page, and is not checked here."""
from __future__ import annotations

import re
from pathlib import Path

from orkcraft.realm import lexicon

STATIC = Path(__file__).resolve().parent.parent / "orkcraft" / "gui" / "static"


def _skip_string(src: str, i: int, quote: str) -> int:
    i += 1
    while src[i] != quote:
        i += 2 if src[i] == "\\" else 1
    return i + 1


def _skip_expr(src: str, i: int) -> int:
    """From just inside `${`, past its closing `}` (strings and nested templates skipped)."""
    depth = 1
    while depth:
        c = src[i]
        if c in "'\"":
            i = _skip_string(src, i, c)
            continue
        if c == "`":
            i = _template(src, i + 1)[1]
            continue
        depth += {"{": 1, "}": -1}.get(c, 0)
        i += 1
    return i


def _template(src: str, i: int) -> tuple[list[str], int]:
    """A template literal's strings from just past its opening backtick, and where it ends."""
    parts, cur = [], ""
    while True:
        c = src[i]
        if c == "\\":
            cur += src[i:i + 2]
            i += 2
        elif c == "`":
            parts.append(cur)
            return parts, i + 1
        elif src.startswith("${", i):
            parts.append(cur)
            cur = ""
            i = _skip_expr(src, i + 2)
        else:
            cur += c
            i += 1


def _texts(parts: list[str]):
    """The text between tags, as htm renders it: never a tag, an attribute or an interpolated value."""
    in_tag, quote = False, None
    for s in parts:
        text = ""
        for ch in s:
            if in_tag:
                if quote:
                    quote = None if ch == quote else quote
                elif ch in "\"'":
                    quote = ch
                elif ch == ">":
                    in_tag = False
            elif ch == "<":
                yield text
                text, in_tag = "", True
            else:
                text += ch
        yield text


def _templates():
    for path in sorted(STATIC.rglob("*.js")):
        src = path.read_text(encoding="utf-8")
        for m in re.finditer(r"(?<![\w$.])html`", src):
            yield path, src.count("\n", 0, m.start()) + 1, _template(src, m.end())[0]


def test_the_scanner_reads_every_template():
    found = list(_templates())
    assert len(found) > 1000
    assert not [(p, n) for p, n, parts in found if any("html`" in s for s in parts)]   # none swallowed the next
    probe = 'html`<b title="Garrison">Halt All ${x ? html`<i>Lake</i>` : "keeper"}</b>`'
    texts = [t for t in _texts(_template(probe, 5)[0]) if t.strip()]
    assert [w.group(0) for t in texts for w in lexicon._WORD.finditer(t)] == ["Halt All"]


def test_no_template_says_an_old_camp_spelling():
    old = [f"{path.relative_to(STATIC)}:{line} {w.group(0)!r} → {lexicon.words(w.group(0))!r}"
           for path, line, parts in _templates() for text in _texts(parts)
           for w in lexicon._WORD.finditer(text)]
    assert not old, "write today's word in the template:\n" + "\n".join(old)
