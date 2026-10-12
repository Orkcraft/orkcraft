"""Comments on the interface and fixes of Orkcraft itself (docs/design/improve-buildings.md §14): what the person said
about any part of the window goes to the Alchemist, what the Mechanic found in the logs goes to the Mechanic, and each
writes its fix in a copy of Orkcraft's source (realm/work_copy.py) that goes to Orkcraft as a pull request.

Kept on this machine, not in a town: they are about Orkcraft, whichever town shows it (`<state>/improve/fixes.json`).

    store = fixes.Store(folder)
    store.comment(text, where)                 a comment, waiting for the Alchemist
    store.fix(who, asks, about)                a fix to write: the Alchemist's (comments) or the Mechanic's (a finding)
    fixes.prompt(fix, kind, python)            what the agent is asked, in its copy
    fixes.title(fix), fixes.body(fix, files)   the pull request's

Pure: no face, no process (gui/fixes.py runs the agents and sends the pull requests).
"""
from __future__ import annotations

import datetime as dt
import json
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path

import orkcraft
from orkcraft.design import agents

FILE = "fixes.json"
TITLE_CHARS = 72
WHO = {"alchemist": "the Alchemist", "mechanic": "the Mechanic"}
STATES = ("writing", "ready", "empty", "failed", "sent")
WHERE_KEYS = ("selector", "text", "html", "building", "window", "look", "size", "page")
WHERE_MAX = {"html": 1500, "text": 400}


def _now() -> str:
    return dt.datetime.now().isoformat(timespec="seconds")


@dataclass
class Comment:
    id: str
    at: str
    text: str
    where: dict = field(default_factory=dict)     # what was pressed: its selector, its text, its markup, its window…
    fix: str = ""                                 # the fix it went into; "" while it waits


@dataclass
class Fix:
    id: str
    who: str                                      # alchemist | mechanic
    at: str
    asks: list[str] = field(default_factory=list)  # what it is for: the comments, or the finding, in words
    about: str = ""                               # the context the agent gets beside them (the comments' places…)
    state: str = "writing"
    said: str = ""                                # what the agent said it did
    files: list[str] = field(default_factory=list)
    top: str = ""                                 # its copy
    base: str = ""
    kind: str = ""                                # worktree | package
    pr: str = ""
    error: str = ""
    rounds: int = 0


def clean_where(where: dict | None) -> dict:
    out = {}
    for k in WHERE_KEYS:
        v = (where or {}).get(k)
        if isinstance(v, (str, int, float)) and str(v).strip():
            out[k] = str(v).strip()[:WHERE_MAX.get(k, 200)]
    return out


class Store:
    def __init__(self, folder: Path) -> None:
        self.path = folder / FILE
        self.comments: list[Comment] = []
        self.fixes: list[Fix] = []
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            self.comments = [Comment(**c) for c in data.get("comments") or []]
            self.fixes = [Fix(**f) for f in data.get("fixes") or []]
        except (OSError, ValueError, TypeError):
            pass
        for f in self.fixes:                      # a fix being written when the app closed: its agent is gone
            if f.state == "writing":
                f.state, f.error = "failed", "Orkcraft closed while it was being written: write it again"

    def save(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps({"comments": [asdict(c) for c in self.comments],
                                             "fixes": [asdict(f) for f in self.fixes]}, ensure_ascii=False, indent=1),
                                 encoding="utf-8")
        except OSError:
            pass

    def comment(self, text: str, where: dict | None = None) -> Comment:
        text = text.strip()
        if not text:
            raise ValueError("Write what should change")
        c = Comment(f"c{uuid.uuid4().hex[:8]}", _now(), text[:2000], clean_where(where))
        self.comments.append(c)
        self.save()
        return c

    def waiting(self) -> list[Comment]:
        return [c for c in self.comments if not c.fix]

    def get(self, fid: str) -> Fix:
        for f in self.fixes:
            if f.id == fid:
                return f
        raise KeyError(fid)

    def fix(self, who: str, asks: list[str], about: str = "") -> Fix:
        f = Fix(f"f{uuid.uuid4().hex[:8]}", who, _now(), [a[:2000] for a in asks], about[:20_000])
        self.fixes.insert(0, f)
        self.save()
        return f

    def drop_comment(self, cid: str) -> None:
        self.comments = [c for c in self.comments if c.id != cid]
        self.save()

    def drop(self, fid: str) -> None:
        self.fixes = [f for f in self.fixes if f.id != fid]
        self.comments = [c for c in self.comments if c.fix != fid]
        self.save()


def where_text(where: dict) -> str:
    """A comment's place, for the agent: the window it was in, the element, its text and its markup."""
    lines = []
    for k, word in (("window", "Window"), ("building", "Building"), ("look", "Look"), ("size", "Window size"),
                    ("selector", "Element"), ("text", "Its text")):
        if where.get(k):
            lines.append(f"{word}: {where[k]}")
    if where.get("html"):
        lines.append(f"Its markup:\n```html\n{where['html']}\n```")
    return "\n".join(lines)


def comments_about(comments: list[Comment]) -> str:
    return "\n\n".join(f"### Comment {n}\n“{c.text}”\n{where_text(c.where)}" for n, c in enumerate(comments, 1))


RULES_WORKTREE = """This folder is a git worktree of Orkcraft's repository at the commit this machine runs. Read CLAUDE.md first
and follow it: the wording (ork, orkestration; orks by their orkish names, buildings by what they do), where code goes,
the design system's roles (docs/design-system.md, orkcraft/design/ui.py RULES) — never a raw colour or font.
Run the tests of what you touch and the critical ones from this folder, and keep them green:
`{python} -m pytest -q tests/test_architecture.py tests/test_gui_wording.py <the test files of the modules you change>`.
When behaviour changes, change or add the test that shows it. Do not commit, push or open a pull request: Orkcraft
shows the person your diff and sends it."""

RULES_PACKAGE = """This folder holds Orkcraft's package as installed (`orkcraft/`): no tests, no docs. Change only `orkcraft/`. The
interface is `orkcraft/gui/static` (Preact with `htm`, no build step: js/*.js, *.css) and `orkcraft/gui/*.py` behind
it. Words people read: ork, orkestration; orks by their orkish names, buildings by what they do. A window uses the
design system's roles (orkcraft/design/ui.py RULES), never a raw colour or font. Do not commit or push."""

ASK = {
    "alchemist": """You change Orkcraft's own interface for the person's comments below. Each says what they want different
in the part of the window they pressed; its place says which element (a CSS path, its text and its markup) and
which window. Find the code that draws it (grep its classes and words under orkcraft/gui/static and orkcraft/gui),
make the smallest change that does what each comment asks, in the style of the code around it, and keep every name
other code uses. A comment you cannot do: leave it and say why.""",
    "mechanic": """You fix Orkcraft's own code for a finding in its logs, below: what went wrong or cost too much, and the change
that would fix it. Find the code that makes it, make the smallest change that fixes it, in the style of the code
around it, and keep every name other code uses. Do not run anything that needs the network.""",
}


def prompt(f: Fix, kind: str, python: str, more: str = "") -> str:
    rules = (RULES_WORKTREE if kind == "worktree" else RULES_PACKAGE).format(python=python)
    asks = "\n".join(f"- {a}" for a in f.asks)
    again = (f"\n\nYou changed this copy before (its diff is in the folder: `git diff {f.base[:12]}`); the person "
             f"asks for more now:\n“{more.strip()}”") if more.strip() else ""
    return f"""{agents.persona(f.who)}

---

{ASK[f.who]}

{rules}

What it is for:
{asks}

{f.about}{again}

When done, say in two or three lines what you changed and why, and which tests you ran."""


def title(f: Fix) -> str:
    head = (f.asks[0] if f.asks else "a fix").strip().splitlines()[0].strip("“” ")
    text = f"{'UX' if f.who == 'alchemist' else 'Fix'}: {head}"
    return text if len(text) <= TITLE_CHARS else text[:TITLE_CHARS - 1] + "…"


def body(f: Fix, paths: list[str], comments: list[Comment] | None = None, skipped: list[str] | None = None) -> str:
    made = "a git checkout" if f.kind == "worktree" else "the installed package"
    lines = [f"Written by {WHO[f.who]} in Orkcraft {orkcraft.__version__} (from {made} at `{f.base[:12]}`), "
             "docs/design/improve-buildings.md §14.", ""]
    if comments:
        lines.append("## What the person said")
        for c in comments:
            place = c.where.get("window") or c.where.get("selector") or ""
            lines.append(f"- “{c.text}”" + (f" — on {place}" if place else ""))
    else:
        lines.append("## What it is for")
        lines += [f"- {a}" for a in f.asks]
    if f.said:
        lines += ["", f"## What {WHO[f.who]} did", f.said.strip()[:3000]]
    lines += ["", "## Files", *[f"- `{p}`" for p in paths]]
    if skipped:
        lines += ["", "Deleted in the copy but not sent (a pull request from Orkcraft adds and changes files only): "
                  + ", ".join(f"`{p}`" for p in skipped)]
    lines += ["", "_Sent from Orkcraft by the person who asked for it, after they saw this text and the diff; nothing of "
              "their town, projects or logs._"]
    return "\n".join(lines)
