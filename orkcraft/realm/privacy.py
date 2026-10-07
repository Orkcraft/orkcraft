"""What leaves the machine for a model: a person's own text is cleaned of what has a shape before it goes
(an e-mail, a phone, a card or an IBAN, a secret token), and what was taken out comes back into the
answer here.

    s = privacy.scrub("Call Anna +49 151 2345 6789, mail anna@example.org")
    s.text   == "Call Anna [phone-1], mail [email-1]"
    s.found  == {"email": 1, "phone": 1}
    privacy.restore("1. Write to [email-1]", s.table) == "1. Write to anna@example.org"

Only what has a shape is caught: a name, a diagnosis or a sum written in words is not. A card marked
personal never reaches a model at all (core/workers/fields.py); this is the second line, not the first.

Pure module, no face.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# Order matters: an e-mail before a token (its local part may be long), an IBAN and a card before a phone.
# The token pattern is the Warder's (hooks/warder.py `_TOKEN`, which stays standalone: it runs as a hook).
PATTERNS: tuple[tuple[str, re.Pattern], ...] = (
    ("email", re.compile(r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b")),
    ("iban", re.compile(r"\b[A-Z]{2}\d{2}(?:[ ]?[A-Z0-9]{4}){2,7}(?:[ ]?[A-Z0-9]{1,4})?\b")),
    ("card", re.compile(r"\b\d{4}(?:[ -]?\d{4}){2}[ -]?\d{1,7}\b")),
    ("phone", re.compile(r"(?<![\w+])\+?\d[\d ()\-]{7,}\d\b")),
    ("token", re.compile(r"(sk-[A-Za-z0-9_-]{8,}|gh[pousr]_[A-Za-z0-9]{8,}|xox[a-z]-[A-Za-z0-9-]{8,}|AKIA[A-Z0-9]{12,}"
                         r"|[A-Za-z0-9+/_-]{40,})")),
)
LABELS = {"email": ("e-mail", "e-mails"), "iban": ("IBAN", "IBANs"), "card": ("card number", "card numbers"),
          "phone": ("phone number", "phone numbers"), "token": ("secret", "secrets")}
_DIGITS = {"card": (13, 19), "phone": (9, 15)}                # a date or a sum is no phone, an order number no card
_MARK = re.compile(r"\[(?:" + "|".join(k for k, _ in PATTERNS) + r")-\d+\]")


@dataclass
class Scrubbed:
    text: str
    table: dict[str, str] = field(default_factory=dict)       # "[email-1]" → what it stands for
    found: dict[str, int] = field(default_factory=dict)        # kind → how many were taken out


def scrub(text: str, into: Scrubbed | None = None) -> Scrubbed:
    """`text` with what has a shape put as marks. `into`: a scrub to go on with (the same e-mail keeps its
    mark across a to-do and the pages sent with it)."""
    out = into or Scrubbed("")
    seen = {v: k for k, v in out.table.items()}
    clean = text or ""
    for kind, pattern in PATTERNS:
        def mark(m: re.Match, kind=kind) -> str:
            value = m.group(0)
            if _MARK.fullmatch(value) or not _shaped(kind, value):
                return value
            if value not in seen:
                n = out.found.get(kind, 0) + 1
                out.found[kind] = n
                seen[value] = f"[{kind}-{n}]"
                out.table[seen[value]] = value
            return seen[value]
        clean = pattern.sub(mark, clean)
    out.text = clean
    return out


def _shaped(kind: str, value: str) -> bool:
    if kind in _DIGITS:
        low, high = _DIGITS[kind]
        return low <= sum(ch.isdigit() for ch in value) <= high
    if kind == "token" and not value.startswith(("sk-", "gh", "xox", "AKIA")):
        # a long random string: digits and both cases (a long path or a slug is none)
        return any(c.isdigit() for c in value) and any(c.isupper() for c in value) and any(c.islower() for c in value)
    return True


def restore(text: str, table: dict[str, str]) -> str:
    """The model's answer with the marks it kept put back as what they stood for."""
    return _MARK.sub(lambda m: table.get(m.group(0), m.group(0)), text or "") if table else (text or "")


def said(found: dict[str, int]) -> str:
    """What was taken out, in words: "1 e-mail, 2 phone numbers"; "" when nothing was."""
    return ", ".join(f"{n} {LABELS[k][0] if n == 1 else LABELS[k][1]}" for k, n in found.items() if n)
