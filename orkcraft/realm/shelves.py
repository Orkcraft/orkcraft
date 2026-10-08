"""Folders the dashboard buildings read: knowledge bases, a file tree, drops.

    knowledge   folders of Markdown notes: each note's title and headings, changes between looks
    file tree   a folder's top entries and what git says changed in it
    drops       paths pasted or dropped on the terminal (quoted, escaped, file:// URLs)
"""
from __future__ import annotations

import os
import re
import shlex
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import unquote, urlparse

SKIP_DIRS = {".git", ".orkcraft", "node_modules", ".venv", "venv", "__pycache__", ".obsidian", "dist", "build"}
MAX_NOTES = 500
DEFAULT_BASES = ("docs", "notes", "wiki", "knowledge", "context")
_H = re.compile(r"^(#{1,3})\s+(.+?)\s*#*\s*$")
_FM_TITLE = re.compile(r"^title:\s*[\"']?(.+?)[\"']?\s*$", re.M)


def inside(repo_root: Path, rel: str) -> Path:
    p = (repo_root / rel).resolve() if not Path(rel).expanduser().is_absolute() else Path(rel).expanduser().resolve()
    root = repo_root.resolve()
    if p != root and root not in p.parents:
        raise ValueError(f"{rel} is outside the repository")
    return p


def rel_to(repo_root: Path, p: Path) -> str:
    try:
        return str(p.resolve().relative_to(repo_root.resolve()))
    except ValueError:
        return str(p)


# -- knowledge ----------------------------------------------------------------------------------------

@dataclass
class Note:
    path: str                         # repo-relative
    title: str
    headings: list[str] = field(default_factory=list)
    mtime: float = 0.0
    kind: str = "doc"                 # doc | code | design
    rev: str = ""                     # a version stamp when there is no mtime (a git blob, a page version)
    url: str = ""                     # where it lives outside the project (a Confluence page)

    @property
    def stamp(self) -> str | float:
        return self.rev or self.mtime


@dataclass
class Base:
    path: str
    notes: list[Note] = field(default_factory=list)
    error: str = ""
    kind: str = "fs"                  # the source it came from (sources/lore.py)


def default_bases(repo_root: Path) -> list[str]:
    found = [d for d in DEFAULT_BASES if (repo_root / d).is_dir()]
    return found or ["."]


def outline(text: str, fallback: str) -> tuple[str, list[str]]:
    """A Markdown note's title (frontmatter `title`, else its H1, else `fallback`) and its H2/H3 headings."""
    text = text[:20000]
    heads = [m.group(2) for line in text.splitlines() if (m := _H.match(line)) and len(m.group(1)) >= 2][:30]
    m = _FM_TITLE.search(text[:2000]) if text.startswith("---") else None
    h1 = next((mm.group(2) for line in text.splitlines() if (mm := _H.match(line)) and len(mm.group(1)) == 1), "")
    return (m.group(1) if m else "") or h1 or fallback, heads


def read_note(path: Path, repo_root: Path) -> Note:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")[:20000]
    except OSError:
        text = ""
    title, heads = outline(text, path.stem)
    try:
        mtime = path.stat().st_mtime
    except OSError:
        mtime = 0.0
    return Note(rel_to(repo_root, path), title, heads, mtime)


def scan_base(repo_root: Path, rel: str) -> Base:
    try:
        root = inside(repo_root, rel)
    except ValueError as e:
        return Base(rel, error=str(e))
    if not root.is_dir():
        return Base(rel, error=f"{rel}: no such folder")
    notes = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS and not d.startswith("."))
        for name in sorted(filenames):
            if name.lower().endswith((".md", ".markdown")):
                notes.append(read_note(Path(dirpath) / name, repo_root))
                if len(notes) >= MAX_NOTES:
                    return Base(rel, notes)
    return Base(rel, notes)


# -- the file tree ------------------------------------------------------------------------------------

def top_entries(root: Path, limit: int = 6) -> list[str]:
    try:
        items = sorted(root.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
    except OSError:
        return []
    out = [f"{p.name}/" if p.is_dir() else p.name for p in items
           if not p.name.startswith(".") and p.name not in SKIP_DIRS]
    return out[:limit]


def changed_files(repo_root: Path, rel: str = ".") -> dict[str, str]:
    """path → git's two-letter status, for the files under `rel` that differ from HEAD."""
    out = subprocess.run(["git", "status", "--porcelain=v1", "--untracked-files=all", "--no-renames", "--", rel],
                         cwd=repo_root, capture_output=True, text=True, timeout=10)
    if out.returncode != 0:
        raise RuntimeError(out.stderr.strip()[:200] or "git status failed")
    rows = {}
    for line in out.stdout.splitlines():
        path = line[3:].strip().strip('"')
        if path and not path.startswith(".orkcraft/"):
            rows[path] = line[:2]
    return rows


def file_changes(before: dict[str, tuple[str, float]] | None, repo_root: Path,
                 now: dict[str, str]) -> tuple[dict[str, tuple[str, float]], list[str]]:
    """The changed files' (status, mtime) and which of them are new or changed again since the last look."""
    cur = {}
    for p, st in now.items():
        try:
            cur[p] = (st, (repo_root / p).stat().st_mtime)
        except OSError:
            cur[p] = (st, 0.0)
    if before is None:
        return cur, []
    gone = [p for p in before if p not in cur]                # reverted or committed
    return cur, [p for p, v in cur.items() if before.get(p) != v] + gone


def preview(path: Path, lines: int = 200) -> str:
    if path.is_dir():
        return "\n".join(top_entries(path, 50)) or "(empty folder)"
    try:
        data = path.read_bytes()[:64000]
    except OSError as e:
        return str(e)
    if b"\0" in data[:4000]:
        return f"(binary, {path.stat().st_size} bytes)"
    return "\n".join(data.decode("utf-8", errors="replace").splitlines()[:lines])


# -- drops ----------------------------------------------------------------------------------------------

def dropped_paths(text: str) -> list[Path]:
    """Paths in what a drag-and-drop or a paste typed: quoted, backslash-escaped or file:// URLs."""
    text = text.strip()
    if not text:
        return []
    try:
        parts = shlex.split(text)
    except ValueError:
        parts = text.split()
    whole = Path(text.strip("'\"")).expanduser()
    if len(parts) > 1 and whole.exists():         # one path with spaces, pasted bare
        parts = [str(whole)]
    out = []
    for part in parts:
        if part.startswith("file://"):
            part = unquote(urlparse(part).path)
        p = Path(part).expanduser()
        if p.exists() and p.is_file():
            out.append(p.resolve())
    return out
