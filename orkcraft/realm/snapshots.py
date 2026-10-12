"""Snapshots of a project's files (docs/design/projects.md §7): the working tree as it is, before and after an ork
works in it, kept in hidden refs so the person's branch, index, stash and `git log` never change.

    take(folder, "shop", "before Grom: Login form")    # a Snapshot, or None (no git, or nothing changed)
    listed(folder, "shop")                             # newest first
    restore(folder, "shop", sha)                       # the files as they were; a snapshot of now is taken first

How: a copy of the person's index (so unchanged files are not read again), `git add -A` into it (untracked files
too, .gitignore kept), `write-tree`, `commit-tree` on HEAD, `update-ref refs/orkcraft/snapshots/<orkspace>/<time>`.
Going back reads the snapshot into another temporary index and writes its files out (`checkout-index`), then
removes the files it did not have that git does not ignore: the person's index stays as it was. Old snapshots are
dropped (older than 30 days, beyond the last 200 of an orkspace); git's own gc cleans what they held.

Every git call uses fixed arguments (no shell). Pure module: it never shows anything.
"""
from __future__ import annotations

import datetime as dt
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

REFS = "refs/orkcraft/snapshots"
KEEP_DAYS = 30
KEEP_MAX = 200
GIT_TIMEOUT_S = 120
SUBJECT = "Orkcraft snapshot: "
STAMP = "%Y%m%dT%H%M%S%fZ"                 # a snapshot's ref name: when it was taken, in UTC
# The town's own state is never a project file: `.orkcraft/` (the camp's git, the worktrees) stays out of every
# snapshot and is never touched by going back, whether or not the project's .gitignore says so.
ALL_BUT_TOWN = ("--", ".", ":(exclude).orkcraft")
_ID = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
_SHA = re.compile(r"^[0-9a-f]{7,40}$")
_IDENTITY = {"GIT_AUTHOR_NAME": "Orkcraft", "GIT_AUTHOR_EMAIL": "orkcraft@localhost",
             "GIT_COMMITTER_NAME": "Orkcraft", "GIT_COMMITTER_EMAIL": "orkcraft@localhost"}


class SnapshotError(Exception):
    """Why a snapshot could not be taken or restored: said to the person as it is."""


@dataclass
class Snapshot:
    sha: str
    at: str           # ISO 8601
    why: str
    ref: str


def _git(folder: Path, *args: str, index: Path | None = None, check: bool = True) -> subprocess.CompletedProcess:
    env = {**os.environ, **_IDENTITY}
    if index is not None:
        env["GIT_INDEX_FILE"] = str(index)
    out = subprocess.run(["git", *args], cwd=folder, capture_output=True, text=True, env=env, timeout=GIT_TIMEOUT_S)
    if check and out.returncode != 0:
        raise SnapshotError((out.stderr or out.stdout).strip()[:300] or f"git {args[0]} failed")
    return out


def has_git(folder: Path) -> bool:
    return (folder / ".git").exists()


def _git_dir(folder: Path) -> Path:
    return Path(_git(folder, "rev-parse", "--absolute-git-dir").stdout.strip())


def _head(folder: Path) -> str:
    out = _git(folder, "rev-parse", "--verify", "--quiet", "HEAD", check=False)
    return out.stdout.strip() if out.returncode == 0 else ""


class _Index:
    """A temporary index in the repository's git folder, a copy of the person's when `copy`."""

    def __init__(self, folder: Path, copy: bool) -> None:
        git_dir = _git_dir(folder)
        fd, name = tempfile.mkstemp(prefix="orkcraft-snapshot-", suffix=".index", dir=git_dir)
        os.close(fd)
        self.path = Path(name)
        real = git_dir / "index"
        if copy and real.is_file():
            shutil.copyfile(real, self.path)
        else:
            self.path.unlink()                 # git makes a new one where none is

    def __enter__(self) -> Path:
        return self.path

    def __exit__(self, *exc) -> None:
        self.path.unlink(missing_ok=True)


def _tree_now(folder: Path) -> str:
    with _Index(folder, copy=True) as index:
        _git(folder, "rm", "-r", "--cached", "-q", "--ignore-unmatch", "--", ".orkcraft", index=index)
        _git(folder, "add", "-A", *ALL_BUT_TOWN, index=index)
        return _git(folder, "write-tree", index=index).stdout.strip()


def _ref_prefix(orkspace_id: str) -> str:
    if not _ID.match(orkspace_id or ""):
        raise SnapshotError(f"bad orkspace id {orkspace_id!r}")
    return f"{REFS}/{orkspace_id}/"


def listed(folder: Path, orkspace_id: str, limit: int = KEEP_MAX) -> list[Snapshot]:
    """The orkspace's snapshots in this project, newest first."""
    if not has_git(folder):
        return []
    out = _git(folder, "for-each-ref", "--sort=-refname", f"--count={limit}",
               "--format=%(objectname)%09%(committerdate:iso-strict)%09%(refname)%09%(contents:subject)",
               _ref_prefix(orkspace_id), check=False)
    rows = []
    for line in out.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) == 4:
            sha, at, ref, subject = parts
            rows.append(Snapshot(sha, _at_of(ref) or at, subject.removeprefix(SUBJECT), ref))
    return rows


def _at_of(ref: str) -> str:
    """When a snapshot was taken, to the microsecond, from its ref's name (git keeps seconds)."""
    try:
        t = dt.datetime.strptime(ref.rsplit("/", 1)[-1], STAMP).replace(tzinfo=dt.timezone.utc)
    except ValueError:
        return ""
    return t.isoformat()


def take(folder: Path, orkspace_id: str, why: str) -> Snapshot | None:
    """The working tree as it is now, kept under the orkspace; None when the folder has no git or nothing changed
    since its last snapshot."""
    prefix = _ref_prefix(orkspace_id)
    if not has_git(folder):
        return None
    tree = _tree_now(folder)
    last = listed(folder, orkspace_id, limit=1)
    if last and _git(folder, "rev-parse", f"{last[0].sha}^{{tree}}").stdout.strip() == tree:
        return None
    why = " ".join(why.split())[:200] or "snapshot"
    head = _head(folder)
    sha = _git(folder, "commit-tree", tree, *(("-p", head) if head else ()), "-m", SUBJECT + why).stdout.strip()
    now = dt.datetime.now(dt.timezone.utc)
    name = now.strftime(STAMP)
    ref = prefix + name
    _git(folder, "update-ref", ref, sha)
    prune(folder, orkspace_id)
    return Snapshot(sha, now.isoformat(), why, ref)


def prune(folder: Path, orkspace_id: str, now: dt.datetime | None = None) -> int:
    """Drop the snapshots beyond the last KEEP_MAX and those older than KEEP_DAYS; how many went."""
    rows = listed(folder, orkspace_id, limit=100_000)
    edge = (now or dt.datetime.now(dt.timezone.utc)) - dt.timedelta(days=KEEP_DAYS)
    gone = 0
    for i, s in enumerate(rows):
        try:
            old = dt.datetime.fromisoformat(s.at) < edge
        except ValueError:
            old = False
        if i >= KEEP_MAX or (old and i > 0):
            _git(folder, "update-ref", "-d", s.ref, check=False)
            gone += 1
    return gone


def changed(folder: Path, sha: str, before: str | None = None) -> list[str]:
    """The files that differ between a snapshot and the one before it (or `before`)."""
    if not _SHA.match(sha or "") or (before and not _SHA.match(before)):
        return []
    args = ["diff", "--name-only", before, sha] if before else ["diff-tree", "--no-commit-id", "--name-only", "-r", "--root", sha]
    out = _git(folder, *args, check=False)
    return [p for p in out.stdout.splitlines() if p] if out.returncode == 0 else []


def restore(folder: Path, orkspace_id: str, sha: str) -> Snapshot | None:
    """The project's files as they were at snapshot `sha`. A snapshot of now is taken first (returned), so going
    back can be undone. Files git ignores are never touched; the person's index and branch stay as they are."""
    if not has_git(folder):
        raise SnapshotError("This project has no git: there are no snapshots to go back to")
    if not _SHA.match(sha or "") or _git(folder, "cat-file", "-e", f"{sha}^{{commit}}", check=False).returncode != 0:
        raise SnapshotError("That snapshot is not in this project any more")
    safety = take(folder, orkspace_id, "before going back")
    wanted = set(_git(folder, "ls-tree", "-r", "--name-only", sha).stdout.splitlines())
    wanted = {p for p in wanted if not (p == ".orkcraft" or p.startswith(".orkcraft/"))}
    with _Index(folder, copy=True) as index:
        _git(folder, "add", "-A", *ALL_BUT_TOWN, index=index)
        present = set(_git(folder, "ls-files", *ALL_BUT_TOWN, index=index).stdout.splitlines())
    with _Index(folder, copy=False) as index:
        _git(folder, "read-tree", sha, index=index)
        _git(folder, "rm", "-r", "--cached", "-q", "--ignore-unmatch", "--", ".orkcraft", index=index)
        _git(folder, "checkout-index", "-a", "-f", index=index)
    root = folder.resolve()
    for rel in sorted(present - wanted, reverse=True):
        p = (folder / rel)
        try:
            p.resolve().relative_to(root)
        except ValueError:
            continue
        p.unlink(missing_ok=True)
        parent = p.parent
        while parent != folder and parent.is_dir() and not any(parent.iterdir()):
            parent.rmdir()
            parent = parent.parent
    return safety
