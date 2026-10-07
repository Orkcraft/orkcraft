"""The LLM wiki the 🗑️ Scroll Dump keeps: sources in, a structured wiki out, written by its orc.

No retrieval of our own: Claude Code and agy already search files well. What the building adds is
the structure and the harness around it — the idea of an "LLM wiki": an agent turns raw sources
into a wiki of linked pages once, then keeps it current, so knowledge accumulates instead of
being searched for from scratch on every question.

A wiki is one topic, not one building: `codebase` (modules, flows, decisions of the code),
`team` (people and ownership, processes, product, decisions), or `general`. Each lives in its
own folder (default `llm-wiki/<topic>/`) with its own rules:

    WIKI.md            the schema: sections, kinds of pages, front matter, links, conflicts
    index.md           the map: every section with one line and its key pages (agents read it first)
    pages/<section>/   the pages; each section has its own index.md (the map stays short as it grows)
    log.md             one entry per ingest, newest first
    lint.md            the last lint: contradictions, stale facts, orphans, missing pages
    proposals.md       the orc's suggestions for the pages people own (it never edits those)
    raw/               snapshots of sources outside the project (git-ignored) and manifest.json
                       (committed): the fingerprint of every source the wiki has taken in

Pages are shared: a page whose front matter says `owner: human` (or that carries
`<!-- manual -->`) is the people's — the orc reads it and suggests in proposals.md, the harness
puts it back if the orc touched it anyway. A page with edits not yet committed is treated the
same for that run. Everything the orc writes is committed with the librarian as its author.
Pure module, no Textual.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from orkcraft.realm import shelves
from orkcraft.realm.shelves import Note

TOPICS = ("general", "codebase", "team", "design")
WIKI_HOME = "llm-wiki"
SCHEMA, INDEX, LOG, LINT, PROPOSALS = "WIKI.md", "index.md", "log.md", "lint.md", "proposals.md"
PAGES, RAW = "pages", "raw"
MANIFEST = f"{RAW}/manifest.json"
RAW_IGNORE = "*\n!.gitignore\n!manifest.json\n"
MAX_ITEMS = 60                  # sources per ingest: the rest wait for the next one
RAW_CHARS = 200_000
CONTEXT_CHARS = 6000
AUTHOR = "Scroll Scrapper (orkcraft) <librarian@orkcraft.local>"
_MANUAL = re.compile(r"^owner:\s*[\"']?human[\"']?\s*$|<!--\s*manual\s*-->", re.M | re.I)

# -- the rules of each topic ------------------------------------------------------------------------

SECTIONS = {
    "general": [("concepts", "ideas, components and terms: what each is, why it exists, how it relates"),
                ("decisions", "what was decided, when, why, and what was rejected"),
                ("how-to", "the steps of tasks people repeat"),
                ("people", "one page per person: what they own, how to reach them (no private details), open items"),
                ("meetings", "one page per meeting: To discuss (kept by the Wiki from notes), background, outcome")],
    "codebase": [("architecture", "the big picture: layers, boundaries, how data moves"),
                 ("modules", "one page per module or package: purpose, entry points, key files, what it uses"),
                 ("flows", "processes that cross modules: a request, a build, a release, step by step"),
                 ("decisions", "why the code is the way it is (ADRs): context, decision, what was rejected"),
                 ("how-to", "developer tasks: set up, test, debug, release"),
                 ("glossary", "the project's terms and the code names they map to")],
    "team": [("teams", "teams and roles: who owns what and how to reach them (no private details)"),
             ("process", "how work is done: planning, reviews, incidents, releases"),
             ("product", "features, customers, goals and the reasons behind them"),
             ("decisions", "what was decided, by whom, when, why, and what was rejected"),
             ("onboarding", "what a newcomer needs in the first weeks"),
             ("glossary", "the team's terms and abbreviations"),
             ("people", "one page per person: what they own, how to reach them (no private details), open items"),
             ("meetings", "one page per meeting: To discuss (kept by the Wiki from notes), background, outcome")],
    "design": [("components", "one page per component: purpose, variants, states, props, where it is used, "
                              "its name in the code"),
               ("screens", "one page per screen or flow: what the user does there, the components on it, edge states"),
               ("decisions", "design decisions: the problem, the options, what was chosen and why"),
               ("tokens", "colours, type, spacing, radii, motion: each token's name, value, role and code name")],
}

SCHEMA_TEMPLATE = """# The wiki's rules — {topic}

This folder is an LLM wiki on one topic ({about}). The librarian orc of the 🗑️ Scroll Dump keeps
it from the sources; people may write it too. Edit these rules freely — the orc follows them.

## Sections

Pages live in `pages/<section>/`, one topic per page, named in kebab-case
(`pages/{first}/some-topic.md`). Every section has an `index.md` listing its pages and a
`CLAUDE.md` with the section's own rules (agents load it when they work there).

{sections}

Add a section only when a topic fits none of these: add it here, with its index and rules.

## Hierarchy

A wiki may grow to thousands of pages; keep every map short enough to read at a glance.
When a section passes ~40 pages, split it into subfolders (`pages/modules/payments/`), each
with its own `index.md` and, when its pages need rules of their own, its own `CLAUDE.md`.
Every index lists only its own level: pages and subfolders, one line each. An agent walks
`index.md` → section index → subfolder index → page, never the whole tree.

## A page

Every page starts with front matter, then a title, then the content:

    ---
    kind: <the section's kind, e.g. {first}>
    aliases: [<other names it goes by: code names, abbreviations, old names>]
    sources: [<the source paths it is drawn from>]
    updated: <YYYY-MM-DD>
    owner: orc            # or human: then the orc never edits it
    ---
    # Title

    One paragraph that answers "what is this and why does it matter" — agents decide from it
    whether to read on.

The aliases and the first paragraph are what searches hit: put every name people or the code
use for the thing there. Link other pages with relative links (`[release](../how-to/release.md)`); name a thing the
same way everywhere (the glossary wins). A page nothing links to is an orphan.

## Keeping it true

- Prefer updating a page to adding one; merge duplicates.
- When sources disagree, say so on the page (`> ⚠ Conflict: …`) instead of picking a side.
- When a source is gone, keep what is still true and mark the rest `> ⚠ Stale: …`.
- Never edit a page whose owner is human (or that carries `<!-- manual -->`): write what you
  would change in `proposals.md` (page, change, source) instead.
- Never copy secrets, tokens or personal data into the wiki.
- A meeting's page (`kind: meeting`, `calendar: meet:<id>`) has a **To discuss** list under a
  `<!-- to-discuss … -->` marker: the Wiki keeps it from people's notes and people tick it off — never
  edit that list. Write the page's Background from the pages its notes link; a person's page gets a
  line for each meeting with them.

## The maps

`index.md` lists the sections, one line each, and the few pages most people need. Each
`pages/<section>/index.md` lists its pages, one line each: what the page answers. `log.md`
gets one entry per ingest, newest first: the date, the sources taken in, the pages touched.
"""

TOPIC_ABOUT = {"general": "the project's knowledge", "codebase": "the code: how it is built and why",
               "team": "the team and the company: people, process, product",
               "design": "the design: components, screens, decisions and tokens"}

INDEX_TEMPLATE = """# Index — {topic}

The map of this wiki: read it first, then the index of the section you need, then the pages.

_Empty — the first ingest fills it._
"""

SECTION_INDEX = """# {title}

{what}

_Empty — pages land here as sources are taken in._
"""

SECTION_RULES = """# Rules of `{name}/`

This folder is the **{name}** section of an LLM wiki ({topic}): {what}.

- One page per topic, kebab-case names; front matter as `../../WIKI.md` says (`kind: {name}`).
- Keep `index.md` here current: one line per page or subfolder, what it answers.
- Past ~40 pages, group them in subfolders, each with its own `index.md`.
- Pages with `owner: human` are people's: suggest changes in `../../proposals.md`, never edit them.
"""

POINTER = """# LLM wiki

This folder is an LLM wiki ({topic}) kept by orkcraft's 🗑️ Scroll Dump. Start from `index.md`,
then a section's `index.md`, then the pages. The rules are in `WIKI.md`. Pages with
`owner: human` belong to people.
"""

LOG_TEMPLATE = """# Log

Newest first.
"""


def topic_of(config: dict) -> str:
    t = str(config.get("topic") or "general")
    return t if t in TOPICS else "general"


def default_dir(topic: str) -> str:
    return f"{WIKI_HOME}/{topic}"


def root_of(repo_root: Path, rel: str | None, topic: str = "general") -> Path:
    return shelves.inside(repo_root, (rel or "").strip() or default_dir(topic))


def schema_text(topic: str) -> str:
    sections = SECTIONS.get(topic, SECTIONS["general"])
    return SCHEMA_TEMPLATE.format(topic=topic, about=TOPIC_ABOUT.get(topic, topic), first=sections[0][0],
                                  sections="\n".join(f"- **{name}** — {what}" for name, what in sections))


def scaffold(root: Path, topic: str = "general") -> list[str]:
    """Make the wiki's folder and its starting files where they are missing; the ones made."""
    made = []
    files = [(SCHEMA, schema_text(topic)), (INDEX, INDEX_TEMPLATE.format(topic=topic)), (LOG, LOG_TEMPLATE),
             (f"{RAW}/.gitignore", RAW_IGNORE), ("CLAUDE.md", POINTER.format(topic=topic)),
             ("AGENTS.md", POINTER.format(topic=topic))]
    for name, what in SECTIONS.get(topic, SECTIONS["general"]):
        files += [(f"{PAGES}/{name}/{INDEX}", SECTION_INDEX.format(title=name.replace("-", " ").capitalize(), what=what)),
                  (f"{PAGES}/{name}/CLAUDE.md", SECTION_RULES.format(name=name, topic=topic, what=what))]
    for name, text in files:
        path = root / name
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
            made.append(name)
    (root / PAGES).mkdir(parents=True, exist_ok=True)
    return made


def pages(root: Path, repo_root: Path) -> list[Note]:
    """The wiki's files (the maps first, then pages/ by path); raw snapshots are not pages."""
    out = []
    for name in (INDEX, LOG, LINT, REVIEWS, PROPOSALS, SCHEMA):
        if (root / name).is_file():
            out.append(shelves.read_note(root / name, repo_root))
    folder = root / PAGES
    if folder.is_dir():
        for dirpath, dirnames, filenames in os.walk(folder):
            dirnames[:] = sorted(d for d in dirnames if not d.startswith("."))
            for name in sorted(filenames):
                if name.lower().endswith(".md") and name != "CLAUDE.md":
                    out.append(shelves.read_note(Path(dirpath) / name, repo_root))
                    if len(out) >= shelves.MAX_NOTES:
                        return out
    return out


def is_page(path: str) -> bool:
    return f"/{PAGES}/" in f"/{path}" and not path.endswith((f"/{INDEX}", "/CLAUDE.md"))


def page_count(notes: list[Note]) -> int:
    return sum(1 for n in notes if is_page(n.path))


def is_manual(text: str) -> bool:
    head = text[:1500]
    return bool(_MANUAL.search(head))


def manual_pages(root: Path) -> dict[str, str]:
    """root-relative path → text of the pages people own."""
    out = {}
    folder = root / PAGES
    for dirpath, _dirs, filenames in os.walk(folder) if folder.is_dir() else ():
        for name in filenames:
            if name.lower().endswith(".md"):
                p = Path(dirpath) / name
                try:
                    text = p.read_text(encoding="utf-8")
                except OSError:
                    continue
                if is_manual(text):
                    out[p.relative_to(root).as_posix()] = text
    return out


def wiki_roots(notes: list[Note]) -> list[str]:
    """The wiki folders among `notes` (where a WIKI.md is): a wiki is never another wiki's source."""
    return sorted({n.path.rpartition("/")[0] for n in notes if n.path.endswith(SCHEMA) and n.path.count(":") == 0
                   and n.path.rpartition("/")[2] == SCHEMA})


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
    tmp.write_text(json.dumps({"taken": dict(sorted(taken.items()))}, indent=1) + "\n", encoding="utf-8")
    tmp.replace(path)


class Fingerprints:
    """What a source holds, not when it was touched: a git blob or page version as it is, a project
    file by the hash of its bytes (hashed again only when its mtime moves)."""

    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root
        self._cache: dict[str, tuple[float, str]] = {}

    def of(self, note: Note) -> str:
        if note.rev:
            return note.rev
        hit = self._cache.get(note.path)
        if hit and hit[0] == note.mtime:
            return hit[1]
        try:
            digest = hashlib.sha1((self.repo_root / note.path).read_bytes()).hexdigest()[:16]
        except OSError:
            digest = f"mtime:{note.mtime}"
        self._cache[note.path] = (note.mtime, digest)
        return digest


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


def pending(manifest: dict[str, str], now: dict[str, str], unsure=lambda path: False) -> Pending:
    """What the sources hold (`now`: path → fingerprint) that the wiki has not taken in yet. A path
    that is `unsure` (its source failed to answer) is never called gone."""
    return Pending(new=[p for p in now if p not in manifest],
                   changed=[p for p, s in now.items() if p in manifest and manifest[p] != s],
                   gone=[p for p in manifest if p not in now and not unsure(p)])


def group_of(path: str) -> str:
    """The module a source belongs to, for batching: its first two folders (`src/payments`)."""
    body = path.split(":")[-1] if path.count(":") else path
    parts = body.split("/")[:-1]
    return (path.rpartition(":")[0] + ":" if ":" in path else "") + "/".join(parts[:2])


def take_batch(p: Pending, limit: int = MAX_ITEMS) -> list[tuple[str, str]]:
    """The next ingest: (status, path) by module, whole modules while they fit — one run sees a
    module together, the rest wait for the next run."""
    rows = sorted([("new", x) for x in p.new] + [("changed", x) for x in p.changed] + [("gone", x) for x in p.gone],
                  key=lambda r: (group_of(r[1]), r[1]))
    groups: dict[str, list[tuple[str, str]]] = {}
    for r in rows:
        groups.setdefault(group_of(r[1]), []).append(r)
    out: list[tuple[str, str]] = []
    for g in groups.values():
        if out and len(out) + len(g) > limit:
            break
        out += g[:limit - len(out)]
        if len(out) >= limit:
            break
    return out


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


def _protected(manual: list[str]) -> str:
    if not manual:
        return ""
    rows = "\n".join(f"- `{p}`" for p in sorted(manual)[:40])
    return (f"\n\nThese pages belong to people right now — read them, never edit, move or delete them; "
            f"write what you would change in `{PROPOSALS}`:\n\n{rows}")


def ingest_prompt(items: list[Item], manual: list[str] = (), today: dt.date | None = None) -> str:
    today = today or dt.date.today()
    rows = "\n".join(f"- [{i.status}] {i.source}" + (f" — {i.title}" if i.title and i.title != i.source else "")
                     + (f" (read it at `{i.read_at}`)" if i.status != "gone" else "") for i in items)
    return f"""You keep one of this project's LLM wikis. The current directory is the wiki's folder.

Read `{SCHEMA}` first: it is the wiki's rules — its sections, page format and owners — and you
follow them. Then read `{INDEX}`, the index of each section you will touch, and the newest
entries of `{REVIEWS}` if it exists (the Clan Fire's spot-checks: fix what they found).

These sources are new, changed or gone since the wiki last took them in:

{rows}

Take them in:
1. Read each new or changed source. Paths are relative to this folder; sources outside the
   project were snapshotted into `{RAW}/`. Skip what does not belong to this wiki's topic.
2. Update the pages that they touch, or add pages, in the right section, as `{SCHEMA}` says.
   For a gone source, keep what is still true elsewhere and mark the rest stale.
3. Update the index of every section you touched and `{INDEX}`.
4. Add one entry at the top of `{LOG}` for {today.isoformat()}: the sources taken in, the pages touched.

A source whose front matter says `kind: note` is a person's quick note. Its `section`, `tags` and
`links` were confirmed by the person: file it in that section, make the tags aliases of the page it
lands on, and link those pages (their paths are relative to the project's root). Keep the note's
words; a short note may become a line on an existing page rather than a page of its own.{_protected(list(manual))}

Write only inside this folder, never into `{RAW}/`; the sources are read-only. Do not commit.
Finish with a short Markdown summary: the pages added, changed and marked stale."""


def lint_prompt(manual: list[str] = (), today: dt.date | None = None) -> str:
    today = today or dt.date.today()
    return f"""You keep one of this project's LLM wikis. The current directory is the wiki's folder.

Read `{SCHEMA}` (the rules), `{INDEX}`, the section indexes and the pages in `{PAGES}/`, then check:
- contradictions between pages, or between a page and the sources it names
- facts that look stale, pages whose sources are gone
- orphans (no page links to them) and links that lead nowhere
- topics many pages mention that have no page of their own
- pages missing from their section's index or from `{INDEX}`, or listed there but missing
- pages that break the page format of `{SCHEMA}`

Write `{LINT}`: a title `# Lint {today.isoformat()}`, then one line per problem, exactly
`- [kind] pages/<section>/<page>.md — what to do`, the kind one of structure, link, contradiction,
orphan, stale, missing; `- none` when the wiki is clean. You may fix the indexes and broken links
yourself; leave everything else to the next ingest.{_protected(list(manual))}

Write only inside this folder. Do not commit.
Finish with a one-line summary: how many problems, of which kinds."""


REVIEWS = "reviews.md"
REVIEW_CHARS = 3000


def touched_pages(repo_root: Path, root: Path, sha: str) -> list[str]:
    """root-relative pages a commit added or changed (not the maps)."""
    rel = shelves.rel_to(repo_root, root)
    try:
        out = _git(repo_root, "show", "--name-only", "--diff-filter=AM", "--format=", sha, "--", f"{rel}/{PAGES}")
    except (OSError, subprocess.TimeoutExpired):
        return []
    return [p[len(rel) + 1:] for p in out.stdout.split() if p.startswith(rel + "/") and is_page(p)]


def review_request(root: Path, pages_: list[str], topic: str) -> str:
    """What the Clan Fire is asked about a sample of the pages an ingest wrote."""
    parts = [f"Spot-check these pages of the {topic} LLM wiki, just written by its librarian orc from the "
             f"project's sources. For each: is it accurate to its sources (listed in its front matter), "
             f"clear, in the right section, free of secrets? Answer per page: OK, or what is wrong and how to fix it."]
    for rel in pages_:
        try:
            text = (root / rel).read_text(encoding="utf-8")
        except OSError:
            continue
        parts.append(f"## {rel}\n\n{text[:REVIEW_CHARS]}" + ("\n…" if len(text) > REVIEW_CHARS else ""))
    return "\n\n".join(parts)


REVIEWS_HEADER = "# Reviews\n\nThe Council's spot-checks, newest first.\n"


def record_review(root: Path, verdict: str, title: str = "", today: dt.date | None = None) -> None:
    """The Clan Fire's report on top of reviews.md (the next ingest reads it)."""
    today = today or dt.date.today()
    path = root / REVIEWS
    try:
        old = path.read_text(encoding="utf-8")
    except OSError:
        old = ""
    rest = old[len(REVIEWS_HEADER):] if old.startswith(REVIEWS_HEADER) else old
    entry = f"## {today.isoformat()}" + (f" — {title}" if title else "") + f"\n\n{verdict.strip()}\n"
    path.write_text(REVIEWS_HEADER + "\n" + entry + (f"\n{rest.strip()}\n" if rest.strip() else ""), encoding="utf-8")


def lint_problems(root: Path) -> int | None:
    """The problems the last lint found (None when there was none)."""
    try:
        text = (root / LINT).read_text(encoding="utf-8")
    except OSError:
        return None
    return sum(1 for ln in text.splitlines() if ln.startswith("- ") and ln.strip().lower() != "- none")


def context(root: Path, repo_root: Path, task: str = "") -> str:
    """What a task gets: where the wiki is and its map — the agent opens the pages it needs."""
    rel = shelves.rel_to(repo_root, root)
    try:
        index = (root / INDEX).read_text(encoding="utf-8")
    except OSError:
        index = "_No index yet._"
    if len(index) > CONTEXT_CHARS:
        index = index[:CONTEXT_CHARS].rsplit("\n", 1)[0] + f"\n\n_… the rest is in `{rel}/{INDEX}`._"
    head = f"**Project wiki:** `{rel}/` — read the pages that matter for this task before you start" \
           f" (paths in the index are relative to `{rel}/`).\n\n"
    return head + (f"**Task:** {task}\n\n" if task else "") + index


_WORD = re.compile(r"[^\W\d_][\w-]{3,}")        # a word of 4+ characters in any script
STEM = 5                                         # words are compared by their first letters: Сергеем finds Сергей
_COMMON = frozenset("that this with from have will about what when where which there their them they your "
                    "were been into over just like some more than then also only each every page pages "
                    "это этот эта как что чтобы когда где который есть было будет надо нужно можно очень "
                    "после перед между через также".split())


def stems(text: str) -> set[str]:
    """The words of `text` as compared: lower case, cut to `STEM` letters, the common ones left out."""
    return {w.lower()[:STEM] for w in _WORD.findall(text or "") if w.lower() not in _COMMON}


def relevant(repo_root: Path, notes: list[Note], task: str, limit: int = 3) -> list[Note]:
    """The pages that share the most words with `task` (its title and text), best first — at most `limit`,
    none that shares none. A word in a page's title counts three times."""
    words = stems(task)
    scored = []
    for n in notes:
        if not is_page(n.path):
            continue
        try:
            text = (repo_root / n.path).read_text(encoding="utf-8")
        except OSError:
            continue
        hits = len(words & stems(text)) + 3 * len(words & stems(n.title))
        if hits:
            scored.append((-hits, n.path, n))
    return [n for *_, n in sorted(scored)[:limit]]


def sections(root: Path, topic: str = "general") -> list[str]:
    """The wiki's sections: the folders of `pages/`, else the ones its topic starts with."""
    try:
        have = sorted(p.name for p in (root / PAGES).iterdir() if p.is_dir() and not p.name.startswith("."))
    except OSError:
        have = []
    return have or [name for name, _ in SECTIONS.get(topic, SECTIONS["general"])]


# -- after the orc ------------------------------------------------------------------------------------

def restore(root: Path, before: dict[str, str]) -> list[str]:
    """Put back the pages people own that the orc changed, moved or deleted; the ones put back."""
    out = []
    for rel, text in before.items():
        p = root / rel
        try:
            now = p.read_text(encoding="utf-8")
        except OSError:
            now = None
        if now != text:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text, encoding="utf-8")
            out.append(rel)
    return out


def _git(repo_root: Path, *args: str, env: dict | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=repo_root, capture_output=True, text=True, timeout=30,
                          env={**os.environ, **(env or {})})


def uncommitted(repo_root: Path, root: Path) -> set[str]:
    """root-relative paths of the wiki's pages with edits not yet committed (a person at work)."""
    rel = shelves.rel_to(repo_root, root)
    try:
        out = _git(repo_root, "status", "--porcelain=v1", "--untracked-files=all", "--", f"{rel}/{PAGES}")
    except (OSError, subprocess.TimeoutExpired):
        return set()
    if out.returncode != 0:
        return set()
    found = set()
    for line in out.stdout.splitlines():
        path = line[3:].strip().strip('"')
        if path.startswith(rel + "/"):
            found.add(path[len(rel) + 1:])
    return found


def commit(repo_root: Path, root: Path, message: str) -> tuple[str, str]:
    """Commit the wiki's folder alone, authored by the librarian: (sha, "") — ("", "") when nothing
    changed, ("", why) when git refused. Raw snapshots stay out (raw/.gitignore)."""
    rel = shelves.rel_to(repo_root, root)
    try:
        if _git(repo_root, "rev-parse", "--git-dir").returncode != 0:
            return "", "not a git repository"
        add = _git(repo_root, "add", "-A", "--", rel)
        if add.returncode != 0:
            return "", add.stderr.strip()[:200]
        if _git(repo_root, "diff", "--cached", "--quiet", "--", rel).returncode == 0:
            return "", ""
        done = _git(repo_root, "commit", "-q", "--author", AUTHOR, "-m", message, "--", rel,
                    env={"GIT_COMMITTER_NAME": "Scroll Scrapper (orkcraft)",
                         "GIT_COMMITTER_EMAIL": "librarian@orkcraft.local"})
        if done.returncode != 0:
            return "", (done.stderr or done.stdout).strip()[:200]
        sha = _git(repo_root, "rev-parse", "--short", "HEAD").stdout.strip()
        return sha, ""
    except (OSError, subprocess.TimeoutExpired) as e:
        return "", str(e)[:200]


def commit_files(repo_root: Path, paths: list[str], message: str) -> str:
    """Commit these files alone (repo-relative), authored by the librarian: the short sha, "" when nothing
    was committed (no git, nothing changed, git refused)."""
    try:
        if not paths or _git(repo_root, "rev-parse", "--git-dir").returncode != 0:
            return ""
        if _git(repo_root, "add", "--", *paths).returncode != 0:
            return ""
        if _git(repo_root, "diff", "--cached", "--quiet", "--", *paths).returncode == 0:
            return ""
        done = _git(repo_root, "commit", "-q", "--author", AUTHOR, "-m", message, "--", *paths,
                    env={"GIT_COMMITTER_NAME": "Scroll Scrapper (orkcraft)",
                         "GIT_COMMITTER_EMAIL": "librarian@orkcraft.local"})
        return _git(repo_root, "rev-parse", "--short", "HEAD").stdout.strip() if done.returncode == 0 else ""
    except (OSError, subprocess.TimeoutExpired):
        return ""


def outside_changes(before: dict[str, tuple[str, float]], repo_root: Path, root: Path) -> list[str]:
    """Project files that changed while the orc worked, outside the wiki's folder."""
    try:
        _, fresh = shelves.file_changes(before, repo_root, shelves.changed_files(repo_root))
    except (RuntimeError, OSError, subprocess.TimeoutExpired):
        return []
    rel = shelves.rel_to(repo_root, root).rstrip("/") + "/"
    return [p for p in fresh if not p.startswith(rel)]


def dirty(repo_root: Path) -> dict[str, tuple[str, float]]:
    try:
        cur, _ = shelves.file_changes({}, repo_root, shelves.changed_files(repo_root))
        return cur
    except (RuntimeError, OSError, subprocess.TimeoutExpired):
        return {}
