"""What a person's edit of an ork's text says about the text — by a script, no model.

A person who edits what an ork wrote is not always unhappy with it. A daily note the ork laid out
and the person fills in through the day is the text doing its job; a person who renames its
sections, throws half of it away or rewrites it is telling the ork the result was wrong. So an
edit is read by what happened to the ork's own lines:

    same        nothing changed
    filled      every line of the ork is still there, in order — only added to (a heading's body
                written, `Mood:` → `Mood: fine`, a bullet appended): the ork's format is used, no signal
    touched     a few of its lines changed, the structure kept: a small fix
    reshaped    the format changed: a heading of the ork is gone, renamed or moved
    rewritten   most of what the ork wrote is gone or replaced

Blank lines and whitespace at the ends of a line do not count.
"""
from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field

SAME, FILLED, TOUCHED, RESHAPED, REWRITTEN = "same", "filled", "touched", "reshaped", "rewritten"
REWRITE_SHARE = 0.5          # of the ork's lines gone or replaced: a rewrite
DIFF_LIMIT = 1500            # characters of the diff kept with the signal


@dataclass
class Edit:
    kind: str
    lines: int = 0                                  # the ork's lines (not blank)
    removed: int = 0                                # of them, gone or replaced
    added: int = 0                                  # the person's new lines
    headings: list[str] = field(default_factory=list)   # the ork's headings gone, renamed or moved
    diff: str = ""

    @property
    def summary(self) -> str:
        if self.kind == SAME:
            return "not changed"
        if self.kind == FILLED:
            return f"filled in: {self.added} line{'s' if self.added != 1 else ''} added, nothing of the ork's changed"
        what = f"{self.removed} of its {self.lines} lines changed or removed"
        if self.headings:
            what += "; sections changed: " + ", ".join(self.headings[:4])
        return {TOUCHED: "small fixes", RESHAPED: "the format changed", REWRITTEN: "rewritten"}[self.kind] + f" — {what}"


def _lines(text: str) -> list[str]:
    return [ln.rstrip() for ln in (text or "").splitlines() if ln.strip()]


def _is_heading(line: str) -> bool:
    return bool(re.match(r"^#{1,6}\s+\S", line.lstrip()))


def _heading_text(line: str) -> str:
    return line.lstrip().lstrip("#").strip()


def _filled(old: str, new: str) -> bool:
    """`Mood:` → `Mood: fine`, `- [ ] call` → `- [x] call`, `- ` → `- the plan`: the line was filled in."""
    o, n = old.strip(), new.strip()
    if not o:
        return True
    if n.startswith(o.rstrip(".…_ ")) and len(n) >= len(o.rstrip(".…_ ")):
        return True
    box = re.compile(r"\[[ xX]\]")
    return box.search(o) is not None and box.sub("[x]", o) == box.sub("[x]", n)


def classify(before: str, after: str) -> Edit:
    """What the edit from `before` (the ork's text) to `after` (the person's) was."""
    old, new = _lines(before), _lines(after)
    if old == new:
        return Edit(SAME, len(old))
    matcher = difflib.SequenceMatcher(None, old, new, autojunk=False)
    removed = added = 0
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        gone, came = old[i1:i2], new[j1:j2]
        # a line of the ork that was only filled in is kept: pair it with the line that grew out of it
        rest = list(came)
        for line in gone:
            hit = next((k for k, c in enumerate(rest) if _filled(line, c)), None)
            if hit is None:
                removed += 1
            else:
                rest.pop(hit)
                added += 1
        added += len(rest)
    heads_old = [_heading_text(ln) for ln in old if _is_heading(ln)]
    heads_new = [_heading_text(ln) for ln in new if _is_heading(ln)]
    lost = [h for h in heads_old if h not in heads_new]
    now = [h for h in heads_new if h in heads_old]          # the ork's headings that are left, in their new order
    was = [h for h in heads_old if h in now]
    moved = [h for h, w in zip(now, was) if h != w]
    diff = "\n".join(difflib.unified_diff(old, new, "the ork's", "the person's", lineterm="", n=1))[:DIFF_LIMIT]
    headings = lost + [f"{h} (moved)" for h in moved]
    if not removed and not headings:
        return Edit(FILLED, len(old), 0, added, [], diff)
    if old and removed / len(old) >= REWRITE_SHARE:
        kind = REWRITTEN
    elif headings:
        kind = RESHAPED
    else:
        kind = TOUCHED
    return Edit(kind, len(old), removed, added, headings, diff)
