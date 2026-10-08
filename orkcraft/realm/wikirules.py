"""Rules for AI tools: what every AI tool of the machine is told about a Wiki (docs/design/wiki-folders-rules.md §3).

`RULES.md` in the wiki's folder is the one source of truth: where the wiki is, its structure (its
sections, or the usual ones of an LLM wiki when it has none), how to search it, cite it and add to
it. Each tool gets a short block that points to it, between two marker lines of this Wiki's own:

    CLAUDE.md                             Claude Code: imports the file (`@llm-wiki/general/RULES.md`)
    AGENTS.md                             Codex, agy, Hermes, pi, Cursor: names the file, says to read it
    .cursor/rules/orkcraft-wiki-<id>.mdc  Cursor: a file of ours, always applied

Only the block is written or removed; the rest of a file stays as it was. A file left empty once the
block is out is deleted. Pure module, no Textual.
"""
from __future__ import annotations

import re
from pathlib import Path

RULES = "RULES.md"
CLAUDE, AGENTS = "CLAUDE.md", "AGENTS.md"
CURSOR_DIR = Path(".cursor") / "rules"
AGENTS_TOOLS = ("codex", "agy", "hermes", "pi", "cursor")     # the tools that read AGENTS.md
MODES = ("review", "ask", "off")
DEFAULT_MODE = "ask"
# The usual structure of an LLM wiki, for a wiki that has none of its own.
USUAL = (("goals", "what the project is for and what it aims at now"),
         ("context", "the background: the product, the domain, the constraints"),
         ("people", "who is who, what they own, how to reach them"),
         ("events", "meetings, releases, incidents: what happened and when"),
         ("decisions", "what was decided, when, why, and what was rejected"),
         ("glossary", "the terms and names the project uses"),
         ("how-to", "the steps of tasks people repeat"))


def mode_of(config: dict) -> str:
    m = str(config.get("agent_rules") or DEFAULT_MODE)
    return m if m in MODES else DEFAULT_MODE


def _id(building_id: str) -> str:
    return re.sub(r"[^\w.-]+", "-", building_id).strip("-") or "wiki"


def begin(building_id: str) -> str:
    return f"<!-- orkcraft:wiki:{_id(building_id)} -->"


def end(building_id: str) -> str:
    return f"<!-- /orkcraft:wiki:{_id(building_id)} -->"


def cursor_file(building_id: str) -> Path:
    return CURSOR_DIR / f"orkcraft-wiki-{_id(building_id)}.mdc"


def structure(root: Path, known: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """The wiki's sections, each with what it holds: the folders of `pages/` (described as `known` says,
    else by the first line of their index), the usual ones when there are none."""
    what = dict(known)
    folder = root / "pages"
    names = sorted(p.name for p in folder.iterdir() if p.is_dir() and not p.name.startswith(".")) \
        if folder.is_dir() else []
    out = [(n, what.get(n) or _first_line(folder / n / "index.md")) for n in names]
    return out or list(USUAL)


def _first_line(path: Path) -> str:
    try:
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.strip() and not line.startswith("#"):
                return line.strip()[:160]
    except OSError:
        pass
    return ""


def rules_text(wiki_rel: str, sections: list[tuple[str, str]], inbox: str, topic: str = "general") -> str:
    """RULES.md: what an agent in any AI tool needs to use the wiki."""
    rows = "\n".join(f"- `pages/{n}/` — {w}" if w else f"- `pages/{n}/`" for n, w in sections)
    return f"""# Rules for AI tools: the LLM wiki

This project keeps an LLM wiki ({topic}) at `{wiki_rel}/`, kept by Orkcraft's Wiki from the
project's sources and checked by its Review board. These rules are written by Orkcraft after each
approved review: edit the wiki's `WIKI.md`, not this file.

## Where to look

1. `{wiki_rel}/index.md` — the map: read it first.
2. `{wiki_rel}/pages/<section>/index.md` — one line per page: what it answers.
3. The page itself. Its front matter names its `sources` and `aliases`.

## Its structure

{rows}

## How to use it

- Before answering a question about the project, search the wiki (its maps first, then the pages:
  titles, `aliases`, text).
- Cite what you use by the page's path (`{wiki_rel}/pages/<section>/<page>.md`).
- Do not make up what the wiki does not say: when it has no answer, say so, then look in the code
  or the sources.
- The pages of `pages/decisions/` are the project's decisions: follow them; when the task needs
  another way, say which decision it goes against and ask.
- A page marked `> ⚠ Conflict` or `> ⚠ Stale` is not settled: check its sources before relying on it.

## How to add to it

- Never edit the wiki's pages yourself: the Wiki's librarian writes them.
- To add what you learned, leave a Markdown note in `{inbox}/`; the librarian takes it in.
- A page whose front matter says `owner: human` belongs to people.
"""


def claude_body(rules_ref: str) -> str:
    return (f"## LLM wiki\n\nThis project has an LLM wiki: read its rules before answering about the project, "
            f"and use it as they say.\n\n@{rules_ref}")


def agents_body(rules_ref: str) -> str:
    return (f"## LLM wiki\n\nThis project has an LLM wiki. Read `{rules_ref}` before answering about the project: "
            f"where the wiki is, its structure, how to search and cite it, and how to add to it.")


def cursor_body(rules_ref: str) -> str:
    return ("---\ndescription: The project's LLM wiki: where it is and how to use it\nalwaysApply: true\n---\n\n"
            + agents_body(rules_ref) + "\n")


def _span(text: str, building_id: str) -> re.Match | None:
    return re.search(rf"{re.escape(begin(building_id))}\n.*?{re.escape(end(building_id))}\n?", text, re.S)


def merge(text: str, building_id: str, body: str) -> str:
    """`text` with this Wiki's block set to `body`: replaced where it is, else added at the end."""
    block = f"{begin(building_id)}\n{body.strip()}\n{end(building_id)}\n"
    m = _span(text, building_id)
    if m:
        return text[:m.start()] + block + text[m.end():]
    if not text.strip():
        return block
    return text.rstrip("\n") + "\n\n" + block


def strip(text: str, building_id: str) -> tuple[str, bool]:
    """`text` without this Wiki's block (and the blank line before it): (the rest, whether it was there)."""
    m = _span(text, building_id)
    if not m:
        return text, False
    head, tail = text[:m.start()], text[m.end():]
    if head.endswith("\n\n"):                    # the blank line `merge` put before it
        head = head[:-1]
    return head + tail, True


def targets(tools: list[str]) -> list[str]:
    """Which files the tools on read: CLAUDE.md for Claude Code, AGENTS.md for the others, Cursor's rule."""
    on = set(tools) or {"claude"}
    out = []
    if "claude" in on:
        out.append(CLAUDE)
    if on & set(AGENTS_TOOLS):
        out.append(AGENTS)
    if "cursor" in on:
        out.append("cursor")
    return out


def write(folder: Path, building_id: str, tools: list[str], rules_ref: str) -> list[Path]:
    """Set this Wiki's block in the files of `folder` the tools read, and take it out of the ones they no
    longer read. The files changed."""
    wanted = targets(tools)
    changed = []
    for name, body in ((CLAUDE, claude_body(rules_ref)), (AGENTS, agents_body(rules_ref))):
        path = folder / name
        old = path.read_text(encoding="utf-8") if path.exists() else ""
        new = merge(old, building_id, body) if name in wanted else strip(old, building_id)[0]
        if new != old:
            if new.strip():
                path.write_text(new, encoding="utf-8")
            elif path.exists():
                path.unlink()
            changed.append(path)
    cursor = folder / cursor_file(building_id)
    if "cursor" in wanted:
        text = cursor_body(rules_ref)
        if not cursor.exists() or cursor.read_text(encoding="utf-8") != text:
            cursor.parent.mkdir(parents=True, exist_ok=True)
            cursor.write_text(text, encoding="utf-8")
            changed.append(cursor)
    elif cursor.exists():
        cursor.unlink()
        changed.append(cursor)
    return changed


def remove(folder: Path, building_id: str) -> list[Path]:
    """Take this Wiki's block out of `folder`'s files (a file left empty is deleted). The files changed."""
    changed = []
    for name in (CLAUDE, AGENTS):
        path = folder / name
        if not path.exists():
            continue
        new, found = strip(path.read_text(encoding="utf-8"), building_id)
        if not found:
            continue
        if new.strip():
            path.write_text(new, encoding="utf-8")
        else:
            path.unlink()
        changed.append(path)
    cursor = folder / cursor_file(building_id)
    if cursor.exists():
        cursor.unlink()
        changed.append(cursor)
    return changed


def written(folder: Path, building_id: str) -> list[str]:
    """The files of `folder` that carry this Wiki's block now (relative to it)."""
    out = [name for name in (CLAUDE, AGENTS)
           if (folder / name).exists() and begin(building_id) in (folder / name).read_text(encoding="utf-8")]
    if (folder / cursor_file(building_id)).exists():
        out.append(cursor_file(building_id).as_posix())
    return out
