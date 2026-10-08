"""What a meeting should cover, kept by the Wiki (docs/design/wiki-librarian.md §5–6): a Quick note that
names a meeting, or a person and a day, lands under **To discuss** on the meeting's page in the wiki;
the page goes first into the meeting's brief; after the meeting what was not ticked off moves on to
the next meeting with the same person.

Everything here is rules, no model: the day a note names (`day_of`, English and Russian), the people
the wiki has pages for (`people_of`, `who`), the meeting it is for (`match`, `next_with`), and the
meeting's page (`page_text`, `with_items`, `ticked`). The block under To discuss between its marker
and the next heading is the Wiki's; a person ticks items there.

Pure module, no Textual.
"""
from __future__ import annotations

import datetime as dt
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from orkcraft.realm import quicknote, wiki

SECTION = "meetings"
PEOPLE = "people"
MARK = "<!-- to-discuss: kept by the Wiki from its notes; tick what was covered -->"
_ITEM = re.compile(r"^- \[([ xX])\] .*<!-- note:(\S+) -->\s*$", re.M)
_NAME = re.compile(r"[^\W\d_]{3,}")
_WEEKDAYS = {"monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3, "friday": 4, "saturday": 5, "sunday": 6,
             "понед": 0, "вторн": 1, "сред": 2, "среду": 2, "четве": 3, "пятни": 4, "суббо": 5, "воскр": 6}
_REL_DAYS = {"today": 0, "tonight": 0, "сегодня": 0, "tomorrow": 1, "завтра": 1, "послезавтра": 2}


@dataclass(frozen=True)
class Meeting:
    id: str
    title: str
    start: dt.datetime
    end: dt.datetime | None = None

    @property
    def when(self) -> str:
        return f"{self.start:%Y-%m-%d %H:%M}"

    def as_dict(self) -> dict:
        return {"id": self.id, "title": self.title, "when": self.when}


@dataclass
class Item:
    note: str                  # the note's repo-relative path
    line: str                  # its words, on one line
    done: bool = False


@dataclass
class Found:
    meeting: Meeting | None = None
    people: list[str] = field(default_factory=list)


# -- reading a note -----------------------------------------------------------------------------------

def day_of(text: str, today: dt.date) -> dt.date | None:
    """The day a note names: today / tomorrow / the day after tomorrow, a weekday (the next one), an ISO date —
    in English or Russian; None when it names none."""
    low = (text or "").lower()
    m = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", low)
    if m:
        try:
            return dt.date.fromisoformat(m.group(1))
        except ValueError:
            pass
    if "day after tomorrow" in low:
        return today + dt.timedelta(days=2)
    words = _NAME.findall(low)
    for w in words:
        if w in _REL_DAYS:
            return today + dt.timedelta(days=_REL_DAYS[w])
    for w in words:
        for key, wd in _WEEKDAYS.items():
            if w == key or (len(key) == 5 and w.startswith(key)):
                return today + dt.timedelta(days=(wd - today.weekday()) % 7 or 7)
    return None


def people_of(repo_root: Path, pages: list) -> dict[str, list[str]]:
    """The people the wiki has pages for (`pages/people/`): each page's title → every name it goes by."""
    out: dict[str, list[str]] = {}
    for n in pages:
        if quicknote.section_of(n.path) != PEOPLE or n.path.endswith(("/index.md", "/CLAUDE.md")):
            continue
        try:
            body = (repo_root / n.path).read_text(encoding="utf-8")
        except OSError:
            body = ""
        out[n.title] = quicknote.names_of(body, n.title)
    return out


def says_name(text: str, name: str) -> bool:
    """Does the text say the name, in any inflection? Each word of the name, cut to its stem (all but its
    last letter, 3 to 5 letters), begins a word of the text: Сергеем says Сергей, Анне says Анна."""
    words = [w.lower() for w in _NAME.findall(text or "")]
    parts = [w.lower()[:max(3, min(wiki.STEM, len(w) - 1))] for w in _NAME.findall(name or "")]
    return bool(parts) and all(any(w.startswith(p) for w in words) for p in parts)


def who(text: str, people: dict[str, list[str]]) -> list[str]:
    """The people a text names, in any inflection (Сергеем → Sergey when the page says `aliases: [Сергей]`)."""
    return [title for title, names in people.items() if any(says_name(text, n) for n in names)]


def _names(person: str, people: dict[str, list[str]]) -> list[str]:
    return people.get(person) or [person]


def names_person(title: str, person: str, people: dict[str, list[str]]) -> bool:
    """Does a meeting's title name the person (by any name of theirs)?"""
    return any(says_name(title, n) for n in _names(person, people))


def match(text: str, meetings: list[Meeting], people: dict[str, list[str]], now: dt.datetime) -> Found:
    """The meeting a note is for, and the people it names. A meeting wins on the day the note names (2),
    each person it names in its title (2) — a person the wiki has a page for, or a capitalised name the
    title says too (Ann, Сергей) — and the words they share (1 each, 2 at most); it needs 2, the nearest
    wins a tie. Only meetings not over yet."""
    named = who(text, people)
    day = day_of(text, now.date())
    words = wiki.stems(text)
    known = {n.lower() for names in people.values() for n in names}
    names = [w for i, w in enumerate(_NAME.findall(text or "")) if i and w[0].isupper() and w.lower() not in known]
    best, score = None, 1
    for m in sorted(meetings, key=lambda m: m.start):
        if (m.end or m.start) < now:
            continue
        s = (2 if day and m.start.date() == day else 0) \
            + 2 * sum(1 for p in named if names_person(m.title, p, people)) \
            + 2 * sum(1 for n in names if says_name(m.title, n)) \
            + min(2, len(words & wiki.stems(m.title)))
        if day and m.start.date() != day:
            continue                                      # a note that names a day is for that day
        if s > score:
            best, score = m, s
    return Found(best, named)


def next_with(person: str, meetings: list[Meeting], people: dict[str, list[str]], now: dt.datetime,
              skip: set[str] = frozenset()) -> Meeting | None:
    """The next meeting that names the person, not over yet (none of `skip`)."""
    ahead = sorted((m for m in meetings if m.start > now and m.id not in skip), key=lambda m: m.start)
    return next((m for m in ahead if names_person(m.title, person, people)), None)


# -- the meeting's page -------------------------------------------------------------------------------

def page_path(root: Path, m: Meeting) -> Path:
    slug = quicknote.file_name(m.title, m.start.date())
    return root / wiki.PAGES / SECTION / slug


def item_line(repo_root: Path, page: Path, item: Item) -> str:
    rel = os.path.relpath(repo_root / item.note, page.parent).replace(os.sep, "/")
    words = " ".join(item.line.split())[:200] or item.note
    return f"- [{'x' if item.done else ' '}] {words} — [note]({rel}) <!-- note:{item.note} -->"


def ticked(text: str) -> dict[str, bool]:
    """The items on a meeting's page: note path → ticked off."""
    return {m.group(2): m.group(1) != " " for m in _ITEM.finditer(text or "")}


def page_text(repo_root: Path, page: Path, m: Meeting, people: list[str], items: list[Item], after: str = "") -> str:
    """A new meeting page."""
    head = ["---", "kind: meeting", f"calendar: meet:{m.id}", f"when: {m.when}"]
    if people:
        head.append(f"with: [{', '.join(people)}]")
    head += ["owner: ork", "---", "", f"# {m.title}", ""]
    body = ["## To discuss", MARK, *(item_line(repo_root, page, i) for i in items), "", "## Background", "",
            "## After the meeting", ""]
    if after:
        body.insert(len(body) - 1, after)
    return "\n".join(head + body) + "\n"


def with_items(repo_root: Path, page: Path, text: str, items: list[Item]) -> str:
    """The page with its To discuss block made of `items` (ticks kept from what the page says now); the rest
    of the page as it is. A page without the marker gets the block before its first `## ` heading."""
    done = ticked(text)
    for i in items:
        i.done = i.done or done.get(i.note, False)
    block = "\n".join([MARK, *(item_line(repo_root, page, i) for i in items)])
    if MARK in text:
        start = text.index(MARK)
        rest = text[start + len(MARK):]
        nxt = re.search(r"^## ", rest, re.M)
        tail = rest[nxt.start():] if nxt else ""
        return text[:start] + block + "\n\n" + tail if tail else text[:start] + block + "\n"
    first = re.search(r"^## ", text, re.M)
    section = f"## To discuss\n{block}\n\n"
    return text[:first.start()] + section + text[first.start():] if first else text.rstrip("\n") + "\n\n" + section


def with_after(text: str, line: str) -> str:
    """The page with a line added under After the meeting (made when missing)."""
    if not line or line in text:
        return text
    m = re.search(r"^## After the meeting\s*\n", text, re.M)
    if not m:
        return text.rstrip("\n") + f"\n\n## After the meeting\n{line}\n"
    return text[:m.end()] + line + "\n" + text[m.end():]
