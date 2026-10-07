"""The Wiki's quality check (docs/design/wiki-librarian.md §8): what is wrong with a wiki, by rules at
every look (`rule_problems`: links to nowhere, pages missing from their section's index, pages with no
front matter or no `kind`) and by the librarian's lint on a schedule (`lint_problems`: the lines of
`lint.md`, `- [kind] page — what to do`). `due` says when the next scheduled check is.

Pure module, no Textual.
"""
from __future__ import annotations

import datetime as dt
import os
import re
from dataclasses import dataclass
from pathlib import Path

from orkcraft.realm import quicknote, wiki

KINDS = ("structure", "link", "contradiction", "orphan", "stale", "missing", "other")
CHECKS = {"weekly": dt.timedelta(days=7), "daily": dt.timedelta(days=1)}    # and `ingest`, `off`
MAX_PAGES = 3000                 # pages the rules read at one look
_LINK = re.compile(r"\]\(([^)\s]+)\)")
_LINE = re.compile(r"^- \[([a-z-]+)\]\s+`?([^`—]+?)`?\s+—\s+(.+)$")


@dataclass(frozen=True)
class Problem:
    kind: str
    page: str            # wiki-root-relative
    text: str
    by: str = "rules"    # rules | lint

    def as_dict(self) -> dict:
        return {"kind": self.kind, "page": self.page, "text": self.text, "by": self.by}


def schedule_of(config: dict) -> str:
    value = str(config.get("check") or "weekly").strip().lower()
    return value if value in (*CHECKS, "ingest", "off") else "weekly"


def due(check: str, last: dt.datetime | None, now: dt.datetime) -> bool:
    """Is a scheduled check due? `ingest` runs after a take-in and `off` never; without a last check none is
    due (the clock starts when the wiki is first seen, so no surprise spend)."""
    period = CHECKS.get(check)
    return period is not None and last is not None and now - last >= period


def next_at(check: str, last: dt.datetime | None) -> dt.datetime | None:
    period = CHECKS.get(check)
    return last + period if period is not None and last is not None else None


def _section_index(page: Path) -> Path:
    return page.parent / wiki.INDEX


def rule_problems(root: Path) -> list[Problem]:
    """What rules find in the wiki's pages, no model."""
    out: list[Problem] = []
    folder = root / wiki.PAGES
    if not folder.is_dir():
        return out
    indexes: dict[Path, str] = {}
    seen = 0
    for dirpath, dirnames, filenames in os.walk(folder):
        dirnames[:] = sorted(d for d in dirnames if not d.startswith("."))
        for name in sorted(filenames):
            if not name.endswith(".md") or name in (wiki.INDEX, "CLAUDE.md"):
                continue
            seen += 1
            if seen > MAX_PAGES:
                return out
            page = Path(dirpath) / name
            rel = page.relative_to(root).as_posix()
            try:
                text = page.read_text(encoding="utf-8")
            except OSError:
                continue
            meta = quicknote.front_matter(text)
            if not meta:
                out.append(Problem("structure", rel, "no front matter: add kind, aliases, sources, updated"))
            elif not meta.get("kind"):
                out.append(Problem("structure", rel, "no `kind` in its front matter"))
            index = _section_index(page)
            if index not in indexes:
                try:
                    indexes[index] = index.read_text(encoding="utf-8")
                except OSError:
                    indexes[index] = ""
            if name not in indexes[index]:
                out.append(Problem("structure", rel, f"missing from `{index.relative_to(root).as_posix()}`"))
            for target in _LINK.findall(text):
                if "://" in target or target.startswith(("#", "mailto:")):
                    continue
                path = target.split("#", 1)[0]
                if path and not (page.parent / path).exists():
                    out.append(Problem("link", rel, f"links to `{path}`, which is not there"))
    return out


def lint_problems(root: Path) -> list[Problem]:
    """The problems the last lint wrote in `lint.md`, one per `- ` line (`- none`: none)."""
    try:
        text = (root / wiki.LINT).read_text(encoding="utf-8")
    except OSError:
        return []
    out = []
    for line in text.splitlines():
        if not line.startswith("- ") or line.strip().lower() == "- none":
            continue
        m = _LINE.match(line.strip())
        if m:
            kind = m.group(1) if m.group(1) in KINDS else "other"
            out.append(Problem(kind, m.group(2).strip(), m.group(3).strip(), "lint"))
        else:
            out.append(Problem("other", "", line[2:].strip(), "lint"))
    return out


def counts(problems: list[Problem]) -> dict[str, int]:
    out = {k: 0 for k in KINDS}
    for p in problems:
        out[p.kind] = out.get(p.kind, 0) + 1
    return out


def fix_prompt(problems: list[Problem], manual: list[str] = ()) -> str:
    """The librarian asked to fix what rules found: links and indexes, nothing else."""
    rows = "\n".join(f"- [{p.kind}] `{p.page}` — {p.text}" for p in problems[:80]) or "- none"
    keep = "\n".join(f"- `{p}`" for p in sorted(manual)[:40])
    return f"""You keep one of this project's LLM wikis. The current directory is the wiki's folder.
Read `{wiki.SCHEMA}` first. Fix these problems and nothing else:

{rows}

- A link to a page that is not there: point it at the page that is meant, or remove the link.
- A page missing from its section's `{wiki.INDEX}`: add one line for it there.
- A page without front matter or without `kind`: add it as `{wiki.SCHEMA}` says.
""" + (f"\nNever edit these pages (people own them):\n{keep}\n" if keep else "") + """
Write only inside this folder. Do not commit. Finish with one line: what you fixed."""
