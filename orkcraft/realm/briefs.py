"""📐 Design briefs: the short design a planned task leaves in its pull request, read back by the next task
on the same area (design: docs/design/barracks-designs.md §5–7).

    render(...)              the brief, from the plan and the steward's `design` (plans.extras): Markdown
                             with a front matter the pool reads back (`orkcraft: brief`, `touches`)
    scan(root, folder)       the briefs merged into the repository: the Markdown files there that are briefs
    relevant(briefs, ...)    at most three a task concerns: by its paths first, then by shared words
    section(briefs)          what the steward's plan (or an ork) reads of them
    stale(briefs, files)     the merged briefs a diff changes the area of without changing the brief
    confirmed(verdict)       the steward's `DESIGN: unchanged` line

A brief is the steward's text built from the request: written as a file, never run, never read as settings.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from orkcraft.realm import barracks as bk
from orkcraft.realm import claims

DEFAULT_DIR = "docs/design"
MAX_RELEVANT = 3
CUT = 3000                       # characters of a brief a prompt gets
MAX_FILES = 200                  # briefs read from the folder at most
WORDS_SHARE = 0.4                # a brief with this share of a task's words concerns it
_FRONT = re.compile(r"\A---\n(.*?)\n---\n", re.S)
DESIGN_LINE = re.compile(r"^\s*\**\s*DESIGN\b\s*:?\s*\**\s*unchanged\b.*$", re.I | re.M)
SECTIONS = (("why", "Why"), ("decisions", "Decisions"), ("invariants", "Invariants"), ("out_of_scope", "Out of scope"))


@dataclass
class Brief:
    path: str                    # relative to the repository
    title: str
    touches: list[str] = field(default_factory=list)
    text: str = ""


def slug(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:50] or "brief"


def path_for(folder: str, title: str, taken: set[str]) -> str:
    """`docs/design/build-the-export.md`; `-2`, `-3` when the name is taken."""
    folder = claims.norm(folder) or DEFAULT_DIR
    base, n = f"{folder}/{slug(title)}", 1
    path = f"{base}.md"
    while path in taken:
        n += 1
        path = f"{base}-{n}.md"
    return path


def _list(items) -> str:
    return "\n".join(f"- {x}" for x in items)


def render(title: str, request: str, task_id: str, pool: str, subs: list, design: dict) -> str:
    """`subs`: the plan's parts (plans.Sub). Only what the plan holds and the steward's `design` strings."""
    touches = claims.narrow([t for s in subs for t in s.touches]) or [t for s in subs for t in s.touches]
    touches = list(dict.fromkeys(claims.norm(t) for t in touches if claims.norm(t)))
    head = ["---", "orkcraft: brief", f"task: {task_id}", f"pool: {pool}",
            "touches: [" + ", ".join(touches) + "]", "---", f"# {title.strip() or 'Design brief'}"]
    body = []
    for key, label in SECTIONS:
        v = design.get(key)
        if v:
            body += [f"## {label}", v if isinstance(v, str) else _list(v)]
    body += ["## Parts", "\n".join(
        f"- `{s.id}` {s.title} ({s.tier})" + (f" — touches {', '.join(s.touches)}" if s.touches else "")
        + (f"; after {', '.join(s.after)}" if s.after else "") for s in subs)]
    cut = request.strip() if len(request) <= CUT else request.strip()[:CUT] + "\n… (cut)"
    body += ["## The request", "\n".join(f"> {ln}" if ln else ">" for ln in cut.splitlines())]
    return "\n".join(head) + "\n\n" + "\n\n".join(body) + "\n"


def front(text: str) -> dict[str, object]:
    """The front matter of a brief: {} when the file is not one."""
    m = _FRONT.match(text or "")
    if m is None:
        return {}
    out: dict[str, object] = {}
    for line in m.group(1).splitlines():
        k, _, v = line.partition(":")
        k, v = k.strip(), v.strip()
        if v.startswith("[") and v.endswith("]"):
            out[k] = [x.strip() for x in v[1:-1].split(",") if x.strip()]
        elif k:
            out[k] = v
    return out if out.get("orkcraft") == "brief" else {}


def read(path: str, text: str) -> Brief | None:
    meta = front(text)
    if not meta:
        return None
    m = re.search(r"^# (.+)$", text, re.M)
    touches = meta.get("touches")
    return Brief(path, m.group(1).strip() if m else path, list(touches) if isinstance(touches, list) else [], text)


def scan(root: Path, folder: str = DEFAULT_DIR) -> list[Brief]:
    """The briefs in `folder` of the checkout at `root` (what is merged)."""
    where = Path(root) / (claims.norm(folder) or DEFAULT_DIR)
    out: list[Brief] = []
    try:
        files = sorted(where.glob("*.md"))[:MAX_FILES]
    except OSError:
        return []
    for f in files:
        try:
            text = f.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        b = read(f.relative_to(root).as_posix(), text)
        if b is not None:
            out.append(b)
    return out


def relevant(found: list[Brief], paths: list[str], text: str, limit: int = MAX_RELEVANT) -> list[Brief]:
    """The briefs a task concerns: those whose `touches` meet its paths, then those sharing its words."""
    by_path = [b for b in found if paths and b.touches and claims.meets(paths, b.touches)]
    mine = bk.words(text[:2000])

    def close(b: Brief) -> float:
        """The share of the task's words the brief has (two at least): a long brief is not penalised."""
        shared = mine & bk.words(f"{b.title} {b.text[:4000]}")
        return len(shared) / len(mine) if mine and len(shared) >= 2 else 0.0
    by_words = sorted((b for b in found if b not in by_path and close(b) >= WORDS_SHARE), key=close, reverse=True)
    return (by_path + by_words)[:limit]


def _cut(text: str) -> str:
    body = _FRONT.sub("", text or "", count=1).strip()
    return body if len(body) <= CUT else body[:CUT] + "\n… (cut)"


def section(found: list[Brief]) -> str:
    """*## Designs this touches*: each brief, cut."""
    if not found:
        return ""
    return "## Designs this touches\n\n" + "\n\n".join(
        f"### `{b.path}`" + (f" (touches {', '.join(b.touches)})" if b.touches else "") + f"\n\n{_cut(b.text)}"
        for b in found)


def stale(found: list[Brief], files: list[str]) -> list[Brief]:
    """The briefs whose area the change meets and that it does not change itself."""
    return [b for b in found if b.touches and b.path not in files and claims.meets(files, b.touches)]


def stale_rule(found: list[Brief]) -> str:
    """What the review prompt adds for `stale` briefs (§7)."""
    if not found:
        return ""
    paths = ", ".join(f"`{b.path}`" for b in found)
    return (section(found) + "\n\n"
            f"This change touches the area of {paths}. If it changes what a brief says, answer "
            f"`REWORK: update <its path>: …`; if every brief still holds, add the line `DESIGN: unchanged` after ACCEPT.")


def states(found: list[Brief], files: list[str], verdict: str) -> list[dict]:
    """What became of the briefs whose area a change met: `updated` (the change has the brief in it),
    `unchanged` (the steward said so), `not confirmed`."""
    said = confirmed(verdict)
    return [{"path": b.path, "state": "updated" if b.path in files else "unchanged" if said else "not confirmed"}
            for b in found]


def pr_line(designs: list[dict]) -> str:
    return "Design briefs: " + ", ".join(f"`{d['path']}` ({d['state']})" for d in designs) if designs else ""


def confirmed(verdict: str) -> bool:
    return bool(DESIGN_LINE.search(verdict or ""))


def strip(notes: str) -> str:
    return DESIGN_LINE.sub("", notes or "").strip()
