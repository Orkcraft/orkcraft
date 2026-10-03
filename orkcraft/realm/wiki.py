"""The LLM wiki the 🗑️ Scroll Dump keeps: sources in, a structured wiki out, written by its orc.

No retrieval of our own: Claude Code and agy already search files well. What the building adds is
the structure and the harness around it — the idea of an "LLM wiki": an agent turns raw sources
into a wiki of linked pages once, then keeps it current, so knowledge accumulates instead of
being searched for from scratch on every question.

    <wiki>/WIKI.md     the schema: the kinds of pages, how they link, how stale facts are marked
    <wiki>/index.md    the map of the wiki: every page with one line (agents read it first)
    <wiki>/log.md      what changed and why, newest first
    <wiki>/lint.md     the last lint: contradictions, stale facts, orphans, missing pages
    <wiki>/pages/…     the pages, written by the orc
    <wiki>/raw/…       snapshots of sources outside the project (a git revision, Confluence pages),
                       with raw/manifest.json: what the wiki has already taken in

    ingest   the sources that are new, changed or gone since the manifest → the orc updates the
             pages, the index and the log (only inside the wiki folder); the manifest moves on
             only when it succeeds
    lint     the orc checks the wiki against itself and its sources and writes lint.md
    context  what a task gets: the index and where the wiki is — the agent reads the pages itself

The sources stay read-only: the orc reads them, writes only the wiki. Pure module, no Textual.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from orkcraft.realm import shelves
from orkcraft.realm.shelves import Note

DEFAULT_DIR = "llm-wiki"
SCHEMA, INDEX, LOG, LINT = "WIKI.md", "index.md", "log.md", "lint.md"
PAGES, RAW = "pages", "raw"
MANIFEST = f"{RAW}/manifest.json"
MAX_ITEMS = 60                  # sources per ingest: the rest wait for the next one
RAW_CHARS = 200_000

SCHEMA_TEMPLATE = """# The wiki's rules

This folder is an LLM wiki: the orc of the 🗑️ Scroll Dump keeps it from the project's sources.
People and agents read it; the orc writes it. Edit these rules freely — the orc follows them.

## Pages

Pages live in `pages/`, one topic per page, named in kebab-case (`pages/release-process.md`).

- **concept** — an idea, a component, a term: what it is, why it exists, how it relates to others
- **decision** — what was decided, when, why, and what was rejected
- **how-to** — the steps of a task people repeat
- **person / team** — who owns what (no private details)

Every page starts with a title (`# …`), then a line `Sources:` listing the sources it is drawn
from (their paths), then the content. Link other pages with relative links
(`[release](release-process.md)`); a page nothing links to is an orphan.

## Keeping it true

- Prefer updating a page to adding a new one; merge duplicates.
- When sources disagree, say so on the page (`> ⚠ Conflict: …`) instead of picking a side.
- When a source is gone, keep what is still true and mark the rest `> ⚠ Stale: …`.
- Never copy secrets, tokens or personal data into the wiki.

## The index and the log

`index.md` lists every page with one line on what it answers, grouped by kind. `log.md` gets
one entry per ingest, newest first: the date, the sources taken in, the pages touched.
"""

INDEX_TEMPLATE = """# Index

The map of this wiki: read it first, then open the pages you need.

_Empty — the first ingest fills it._
"""

LOG_TEMPLATE = """# Log

Newest first.
"""


def root_of(repo_root: Path, rel: str | None) -> Path:
    return shelves.inside(repo_root, (rel or DEFAULT_DIR).strip() or DEFAULT_DIR)


def scaffold(root: Path) -> list[str]:
    """Make the wiki's folder and its starting files where they are missing; the ones made."""
    made = []
    for name, text in ((SCHEMA, SCHEMA_TEMPLATE), (INDEX, INDEX_TEMPLATE), (LOG, LOG_TEMPLATE)):
        path = root / name
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
            made.append(name)
    (root / PAGES).mkdir(parents=True, exist_ok=True)
    return made


def pages(root: Path, repo_root: Path) -> list[Note]:
    """The wiki's pages (the index first, then pages/ by path); raw snapshots are not pages."""
    out = []
    for name in (INDEX, LOG, LINT, SCHEMA):
        if (root / name).is_file():
            out.append(shelves.read_note(root / name, repo_root))
    folder = root / PAGES
    if folder.is_dir():
        for dirpath, dirnames, filenames in os.walk(folder):
            dirnames[:] = sorted(d for d in dirnames if not d.startswith("."))
            for name in sorted(filenames):
                if name.lower().endswith(".md"):
                    out.append(shelves.read_note(Path(dirpath) / name, repo_root))
                    if len(out) >= shelves.MAX_NOTES:
                        return out
    return out


def page_count(notes: list[Note]) -> int:
    return sum(1 for n in notes if f"/{PAGES}/" in f"/{n.path}")


# -- what the wiki has taken in -----------------------------------------------------------------------

def load_manifest(root: Path) -> dict[str, str]:
    try:
        data = json.loads((root / MANIFEST).read_text(encoding="utf-8"))
        return {str(k): str(v) for k, v in (data.get("taken") or {}).items()}
    except (OSError, ValueError, AttributeError):
        return {}


def save_manifest(root: Path, taken: dict[str, str]) -> None:
    path = root / MANIFEST
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps({"taken": dict(sorted(taken.items()))}, indent=1), encoding="utf-8")
    tmp.replace(path)


@dataclass
class Pending:
    new: list[str] = field(default_factory=list)
    changed: list[str] = field(default_factory=list)
    gone: list[str] = field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self.new) + len(self.changed) + len(self.gone)

    def __bool__(self) -> bool:
        return self.count > 0


def pending(manifest: dict[str, str], notes: list[Note]) -> Pending:
    """What the sources hold that the wiki has not taken in yet."""
    now = {n.path: str(n.stamp) for n in notes}
    return Pending(new=[p for p in now if p not in manifest],
                   changed=[p for p, s in now.items() if p in manifest and manifest[p] != s],
                   gone=[p for p in manifest if p not in now])


def raw_path(path: str) -> str:
    """Where a source outside the project is snapshotted: `confluence:123` → raw/confluence/123.md."""
    kind, _, rest = path.partition(":")
    safe = re.sub(r"[^\w.\-/]+", "_", rest).strip("/").replace("..", "_") or "doc"
    return f"{RAW}/{kind}/{safe}" + ("" if safe.endswith(".md") else ".md")


def snapshot(root: Path, path: str, text: str, title: str = "", url: str = "") -> str:
    """Write a source outside the project into raw/ (the orc reads it there); its path in the wiki."""
    rel = raw_path(path)
    head = f"<!-- source: {path}" + (f" · {url}" if url else "") + " -->\n"
    if title and not text.lstrip().startswith("#"):
        head += f"# {title}\n\n"
    target = root / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(head + text[:RAW_CHARS], encoding="utf-8")
    return rel


# -- what the orc is asked -------------------------------------------------------------------------------

@dataclass
class Item:
    source: str                  # the source's path (`docs/a.md`, `confluence:12`)
    read_at: str                 # where the orc reads it, relative to the wiki folder
    status: str                  # new | changed | gone
    title: str = ""


def ingest_prompt(items: list[Item], today: dt.date | None = None) -> str:
    today = today or dt.date.today()
    rows = "\n".join(f"- [{i.status}] {i.source}" + (f" — {i.title}" if i.title and i.title != i.source else "")
                     + (f" (read it at `{i.read_at}`)" if i.status != "gone" else "") for i in items)
    return f"""You keep this project's LLM wiki. The current directory is the wiki's folder.

Read `{SCHEMA}` first: it is the wiki's rules and you follow them. Then read `{INDEX}`.

These sources are new, changed or gone since the wiki last took them in:

{rows}

Take them in:
1. Read each new or changed source. Paths are relative to this folder; sources outside the
   project were snapshotted into `{RAW}/`.
2. Update the pages in `{PAGES}/` that they touch, or add pages, as `{SCHEMA}` says. For a gone
   source, keep what is still true elsewhere and mark the rest stale.
3. Update `{INDEX}` so it lists every page with one line.
4. Add one entry at the top of `{LOG}` for {today.isoformat()}: the sources taken in, the pages touched.

Write only inside this folder, and never into `{RAW}/` or `{MANIFEST}`; the sources are read-only.
Finish with a short Markdown summary: the pages added, changed and marked stale."""


def lint_prompt(today: dt.date | None = None) -> str:
    today = today or dt.date.today()
    return f"""You keep this project's LLM wiki. The current directory is the wiki's folder.

Read `{SCHEMA}` (the rules), `{INDEX}` and the pages in `{PAGES}/`, then check the wiki:
- contradictions between pages, or between a page and the sources it names
- facts that look stale, pages whose sources are gone
- orphans (no page links to them) and links that lead nowhere
- topics many pages mention that have no page of their own
- pages missing from `{INDEX}`, or listed there but missing

Write `{LINT}`: a title `# Lint {today.isoformat()}`, then one `- ` line per problem, naming the
page and what to do; `- none` when the wiki is clean. You may fix the index and broken links
yourself; leave everything else to the next ingest. Write only inside this folder.
Finish with a one-line summary: how many problems, of which kinds."""


def lint_problems(root: Path) -> int | None:
    """The problems the last lint found (None when there was none)."""
    try:
        text = (root / LINT).read_text(encoding="utf-8")
    except OSError:
        return None
    return sum(1 for ln in text.splitlines() if ln.startswith("- ") and ln.strip().lower() != "- none")


def context(root: Path, repo_root: Path, task: str = "") -> str:
    """What a task gets: where the wiki is and its index — the agent opens the pages it needs."""
    rel = shelves.rel_to(repo_root, root)
    try:
        index = (root / INDEX).read_text(encoding="utf-8")[:6000]
    except OSError:
        index = "_No index yet._"
    head = f"**Project wiki:** `{rel}/` — read the pages that matter for this task before you start" \
           f" (paths in the index are relative to `{rel}/`).\n\n"
    return head + (f"**Task:** {task}\n\n" if task else "") + index
