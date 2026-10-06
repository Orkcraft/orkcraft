"""A building's name from what the person asked for when it was built: at most four words.

`from_prompt` reads the request itself (no model): it drops the asking ("What should I build?",
"I need", "please"), the small words (articles, pronouns, most prepositions), and keeps the first
four words that carry the meaning, the first one capitalised: "sort my inbox into tasks" → "Sort
inbox into tasks". `clip` keeps any title — one a model proposed too — to four words.
"""
from __future__ import annotations

import re

MAX_WORDS = 4
MAX_CHARS = 40

# Whole openings that only ask: cut before the words are read.
_ASKING = re.compile(
    r"^\s*(?:what should i build\??|can you|could you|would you|please|i (?:want|need|would like)(?: to)?|"
    r"i'd like(?: to)?|we need(?: to)?|help me(?: to)?|build (?:me )?(?:a |an |the )?|make (?:me )?(?:a |an |the )?|"
    r"create (?:a |an |the )?|something (?:that|to)|a building (?:that|to)|one (?:that|to))\s*",
    re.IGNORECASE)

_SMALL = frozenset("""
a an the my our your their his her its me us them i we you it this that these those some any
please just also really very so and or but then than of for from with by at on in to as
which who whom whose what when where how is are be been being do does did can could should would will
let lets let's get gets got all every each into onto
""".split())
# Words that carry the meaning even when small: kept wherever they stand after the first word.
_KEEP_INSIDE = frozenset({"into", "to", "from", "on", "for"})

_WORD = re.compile(r"[\w][\w'+#./-]*", re.UNICODE)


def _words(text: str) -> list[str]:
    return _WORD.findall(text or "")


def clip(title: str, words: int = MAX_WORDS) -> str:
    """At most `words` words of `title`, at most MAX_CHARS characters; "" when it had none."""
    kept = " ".join(str(title or "").split()[:words]).strip(" .,;:-–—")
    return kept[:MAX_CHARS].rstrip()


def from_prompt(prompt: str, fallback: str = "") -> str:
    """A short title (≤ four words) from the request a building was built for; `fallback` when the
    request says nothing a name can be made of."""
    text = str(prompt or "").strip()
    for _ in range(3):                                   # "Please, I need to build a …"
        cut = _ASKING.sub("", text, count=1).lstrip(" ,.:;-")
        if cut == text:
            break
        text = cut
    text = re.split(r"[.!?;\n]", text, maxsplit=1)[0]     # the first sentence names it
    out: list[str] = []
    for w in _words(text):
        low = w.lower()
        if low in _SMALL and not (out and low in _KEEP_INSIDE):
            continue
        out.append(w)
        if len(out) == MAX_WORDS:
            break
    while out and out[-1].lower() in _KEEP_INSIDE:       # never end on "into"
        out.pop()
    if not out:
        return clip(fallback)
    out[0] = out[0][:1].upper() + out[0][1:]
    return clip(" ".join(out))
