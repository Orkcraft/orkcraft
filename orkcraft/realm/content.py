"""What a cart is, before anyone opens it: a message, a doc, a ticket, code, an image, data or text
(docs/design/loot-checkpoint.md §5).

Nothing in a cart says so on its own, so it is read off what the cart already carries:

- a draft waiting for approval names where it goes out (`PUBLISH: Slack #release`,
  `PUBLISH: Jira, project APP, a new Bug`): the place says what it is;
- a file cart, by its name;
- the files the cart's work committed on its branch (the trail's worktree and branch);
- a text cart, by its text: JSON is data, Markdown with a heading a doc, anything else text.

`of` gives the type, where it goes, the part a person reviews (`body`, the draft without the ork's
report), its first lines and the images worth a thumbnail.
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import PurePosixPath

from orkcraft.realm import barracks, pipes

MESSAGE, DOC, TICKET, CODE, IMAGE, DATA, TEXT = "message", "doc", "ticket", "code", "image", "data", "text"
TYPES = (MESSAGE, DOC, TICKET, CODE, IMAGE, DATA, TEXT)

IMAGES = frozenset((".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".bmp", ".avif"))
DOCS = frozenset((".md", ".markdown", ".rst", ".txt", ".adoc", ".pdf", ".docx", ".odt", ".html", ".htm"))
DATAS = frozenset((".json", ".jsonl", ".csv", ".tsv", ".yaml", ".yml", ".toml", ".xml", ".xlsx"))
CODES = frozenset((".py", ".js", ".mjs", ".ts", ".tsx", ".jsx", ".css", ".scss", ".go", ".rs", ".java", ".kt",
                   ".swift", ".c", ".h", ".cc", ".cpp", ".hpp", ".cs", ".rb", ".php", ".sh", ".sql", ".vue",
                   ".svelte", ".lua", ".dart", ".scala", ".ex", ".exs", ".zig"))

# Where a draft goes out → what it is: the first type with a word in the place wins, in this order. A word
# matches from its start ("mail" in "mailing list", "почт" in "почта"); `\b` ends one that must stand alone.
PLACES: tuple[tuple[str, tuple[str, ...]], ...] = (
    (MESSAGE, ("slack", "telegram", "teams", "discord", "mattermost", "whatsapp", "chat", "e-?mail", "mail",
               "gmail", "outlook", r"sms\b", r"dm\b", "почт", "письм", "слак", "телеграм", "чат")),
    (TICKET, ("jira", "linear", "youtrack", "trello", "asana", "clickup", "issue", "ticket", r"bugs?\b", "тикет",
              "задач")),
    (CODE, ("pull request", "merge request", r"pr\b", r"mr\b", "commit")),
    (DOC, ("confluence", "notion", "wiki", "google doc", "gdoc", "sharepoint", "coda", "page", r"docs?\b",
           "вики", "документ", "страниц")),
)
LINES = 3
SNIPPET = 160
MAX_IMAGES = 4


@dataclass
class Content:
    type: str = TEXT
    where: str = ""                  # where it goes out ("Slack #release") or the branch it is on
    body: str = ""                   # what a person reviews
    lines: list[str] = field(default_factory=list)   # the body's first lines, Markdown marks aside
    images: list[str] = field(default_factory=list)  # paths worth a thumbnail (a file cart's, a branch's)
    files: int = 0                   # files of its work (a file cart: 1)

    def as_dict(self) -> dict:
        return asdict(self)


def _ext(path: str) -> str:
    return PurePosixPath(path).suffix.lower()


def is_image(path: str) -> bool:
    return _ext(path) in IMAGES


def of_file(path: str) -> str:
    """A file's type by its name."""
    ext = _ext(path)
    return IMAGE if ext in IMAGES else CODE if ext in CODES else DATA if ext in DATAS else DOC if ext in DOCS else TEXT


def of_place(place: str) -> str:
    """What goes out to `place` (the `PUBLISH:` line); TEXT when the place says nothing of it."""
    p = place.lower()
    for kind, words in PLACES:
        if any(re.search(rf"(?<!\w){w}", p) for w in words):
            return kind
    return TEXT


def _of_files(paths: list[str]) -> str:
    kinds = [of_file(p) for p in paths]
    if all(k == IMAGE for k in kinds):
        return IMAGE
    if all(k == DOC for k in kinds):
        return DOC
    return CODE


def _of_text(text: str) -> str:
    s = text.strip()
    if s[:1] in ("[", "{"):
        try:
            json.loads(s)
            return DATA
        except ValueError:
            pass
    return DOC if re.search(r"^#{1,3} \S", s, re.M) else TEXT


def lines_of(text: str, n: int = LINES) -> list[str]:
    """The first lines worth reading: no blank ones, no fences or rules, Markdown marks stripped."""
    out: list[str] = []
    for ln in text.splitlines():
        s = ln.strip()
        if not s or s.startswith(("```", "---", "PUBLISH:")):
            continue
        s = re.sub(r"^(#{1,6}\s+|[-*+]\s+|>\s*|\d+\.\s+)", "", s)
        s = re.sub(r"\*\*|__|`", "", s).strip()
        if s:
            out.append(s[:SNIPPET])
        if len(out) >= n:
            break
    return out


def _images(files: list[str]) -> list[str]:
    return [f for f in files if is_image(f)][:MAX_IMAGES]


def of(kind: str, value: str, trail: tuple = (), files: list[str] | None = None) -> Content:
    """What a cart is: `kind` and `value` as its payload has them, `files` its work committed on its branch
    (the branch is named by the trail)."""
    files = list(files or [])
    if kind == pipes.FILE:
        t = of_file(value)
        return Content(t, "", value, [PurePosixPath(value).name], [value] if t == IMAGE else [], 1)
    _report, place, draft = barracks.publish_of(value) if kind == pipes.TEXT else (value, "", "")
    if place:
        body = draft or value
        return Content(of_place(place), place[:80], body, lines_of(body), _images(files), len(files))
    if files:
        branch = next((h.branch for h in reversed(trail) if h.worktree and h.branch), "")
        return Content(_of_files(files), branch, value, lines_of(value), _images(files), len(files))
    return Content(_of_text(value), "", value, lines_of(value))
