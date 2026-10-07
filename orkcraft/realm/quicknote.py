"""A Quick note for the Wiki (docs/design/wiki-librarian.md §4): a few lines a person leaves with one
click, kept as a Markdown file in the Wiki's inbox — a source folder of its wiki — with the section,
the tags and the links it was given in its front matter, so the librarian keeps them at take-in.

`suggest` reads the text against the wiki, by rules and no model: the pages that share its words
(`wiki.relevant`), the section of the best of them, and as tags the names of those pages (their
titles and `aliases`) the text says. `note_text` writes the file, `file_name` names it.

Pure module, no Textual.
"""
from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass, field
from pathlib import Path

from orkcraft.realm import shelves, wiki
from orkcraft.realm.shelves import Note

INBOX = "notes/inbox"           # where the notes go unless the Wiki's `inbox` says otherwise
LINKS = 3                       # pages suggested to link to
TAGS = 4                        # tags suggested
MAX_CHARS = 20_000              # a note is a note: longer text is cut
SOURCES = ("quick note", "warchief", "task board")
_FRONT = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.S)
_SLUG = re.compile(r"[^\w]+")


@dataclass
class Suggestion:
    section: str = ""
    tags: list[str] = field(default_factory=list)
    links: list[dict] = field(default_factory=list)     # {path, title}: repo-relative
    meeting: dict | None = None                         # {id, title, when}: the Calendar's meeting it is for
    people: list[str] = field(default_factory=list)     # the people it names (their pages' titles)

    def as_dict(self) -> dict:
        return {"section": self.section, "tags": list(self.tags), "links": [dict(x) for x in self.links],
                "meeting": dict(self.meeting) if self.meeting else None, "people": list(self.people)}


def front_matter(text: str) -> dict[str, str | list[str]]:
    """The `key: value` lines of a page's front matter; `[a, b]` and `- a` lines as lists."""
    m = _FRONT.match(text or "")
    if not m:
        return {}
    out: dict[str, str | list[str]] = {}
    key = ""
    for line in m.group(1).splitlines():
        if line.startswith(("  -", "- ")) and key:
            items = out.get(key)
            out[key] = (items if isinstance(items, list) else []) + [_unquote(line.strip()[1:])]
            continue
        k, sep, v = line.partition(":")
        if not sep or not k.strip() or k.startswith(" "):
            continue
        key, v = k.strip(), v.split(" #")[0].strip()
        out[key] = [_unquote(x) for x in v[1:-1].split(",") if x.strip()] if v.startswith("[") and v.endswith("]") \
            else ([] if not v else _unquote(v))
    return out


def _unquote(s: str) -> str:
    s = s.strip()
    return s[1:-1] if len(s) > 1 and s[0] == s[-1] and s[0] in "\"'" else s


def names_of(page_text: str, title: str) -> list[str]:
    """What a page is called: its title and its `aliases`."""
    aliases = front_matter(page_text).get("aliases") or []
    return [n for n in dict.fromkeys([title, *(aliases if isinstance(aliases, list) else [aliases])]) if n.strip()]


def body_of(text: str) -> str:
    """A note's words without its front matter."""
    m = _FRONT.match(text or "")
    return (text[m.end():] if m else text or "").strip()


def section_of(path: str) -> str:
    """The section of a wiki page: the folder under `pages/`."""
    parts = path.split("/")
    i = parts.index(wiki.PAGES) if wiki.PAGES in parts else -1
    return parts[i + 1] if 0 <= i < len(parts) - 2 else ""


def suggest(text: str, repo_root: Path, pages: list[Note], sections: list[str], meetings: list = (),
            now: dt.datetime | None = None) -> Suggestion:
    """The section, tags and links a note should get, from the wiki it goes to, and the meeting it is for
    among `meetings` (realm/agenda.py), by rules, no model."""
    from orkcraft.realm import agenda                    # it reads notes as this module writes them
    text = (text or "")[:MAX_CHARS]
    if not wiki.stems(text) and not text.strip():
        return Suggestion()
    people = agenda.people_of(repo_root, pages)
    found = agenda.match(text, list(meetings), people, now or dt.datetime.now())
    hint = _suggest(text, repo_root, pages, sections)
    for person in found.people:
        tag = person.lower()
        if tag not in hint.tags:
            hint.tags.insert(0, tag)
    if found.meeting or found.people:
        if "to discuss" not in hint.tags:
            hint.tags.append("to discuss")
        if found.meeting:
            hint.section = agenda.SECTION                 # its page is a meeting's
    hint.tags = hint.tags[:TAGS + 1]
    hint.meeting = found.meeting.as_dict() if found.meeting else None
    hint.people = found.people
    return hint


def _suggest(text: str, repo_root: Path, pages: list[Note], sections: list[str]) -> Suggestion:
    if not wiki.stems(text):
        return Suggestion()
    found = wiki.relevant(repo_root, pages, text, LINKS)
    said = wiki.stems(text)
    tags: list[str] = []
    for n in found:
        try:
            body = (repo_root / n.path).read_text(encoding="utf-8")
        except OSError:
            body = ""
        for name in names_of(body, n.title):
            words = wiki.stems(name)
            if words and words <= said and name.lower() not in (t.lower() for t in tags):
                tags.append(name.lower() if len(name) <= 40 else name[:40].lower())
    section = next((s for s in (section_of(n.path) for n in found) if s in sections), "")
    return Suggestion(section, tags[:TAGS], [{"path": n.path, "title": n.title} for n in found])


def file_name(text: str, today: dt.date) -> str:
    """`<date>-<the first words>.md`."""
    words = _SLUG.sub("-", " ".join((text or "").split()[:6]).lower()).strip("-")[:48].strip("-")
    return f"{today.isoformat()}-{words or 'note'}.md"


def note_text(text: str, section: str = "", tags: list[str] = (), links: list[str] = (),
              source: str = "quick note", written: dt.datetime | None = None, meeting: dict | None = None,
              people: list[str] = ()) -> str:
    """The note's file: its front matter, then the text as it was written."""
    written = written or dt.datetime.now()
    clean = lambda s: " ".join(str(s).replace(",", " ").replace("[", " ").replace("]", " ").split())  # noqa: E731
    people = [clean(p) for p in people if clean(p)]
    lines = ["---", f"kind: {'to-discuss' if meeting or people else 'note'}"]
    if meeting and clean(meeting.get("id", "")):
        lines += [f"meeting: {clean(meeting['id'])}", f"meeting_title: {clean(meeting.get('title', ''))}",
                  f"when: {clean(meeting.get('when', ''))}"]
    if people:
        lines.append(f"with: [{', '.join(people)}]")
    if section:
        lines.append(f"section: {clean(section)}")
    tags = [clean(t) for t in tags if clean(t)]
    if tags:
        lines.append(f"tags: [{', '.join(tags)}]")
    links = [clean(x) for x in links if clean(x)]
    if links:
        lines.append(f"links: [{', '.join(links)}]")
    lines += [f"from: {source if source in SOURCES else SOURCES[0]}", f"written: {written:%Y-%m-%d %H:%M}", "---", ""]
    return "\n".join(lines) + "\n" + (text or "").strip()[:MAX_CHARS] + "\n"


def write(repo_root: Path, inbox: str, text: str, section: str = "", tags: list[str] = (), links: list[str] = (),
          source: str = "quick note", now: dt.datetime | None = None, meeting: dict | None = None,
          people: list[str] = ()) -> str:
    """Write a note into the inbox (made when missing); its repo-relative path. ValueError on an empty note
    or an inbox outside the project."""
    if not (text or "").strip():
        raise ValueError("an empty note")
    now = now or dt.datetime.now()
    folder = shelves.inside(repo_root, inbox or INBOX)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / file_name(text, now.date())
    n = 2
    while path.exists():
        path = folder / f"{path.stem.rsplit('~', 1)[0]}~{n}.md"
        n += 1
    path.write_text(note_text(text, section, tags, links, source, now, meeting, people), encoding="utf-8")
    return shelves.rel_to(repo_root, path)
