"""Git worktrees for orkspaces: each orkspace can work on its own branch in its own folder.

    <repo>/.orkcraft/worktrees/<orkspace_id>   (git-ignored, like all of .orkcraft/)

`create` checks the branch name with `git check-ref-format`, reuses an existing branch or starts
a new one from `base`; `remove` refuses while the worktree has uncommitted or untracked work
unless forced, and keeps the branch. `link` / `unlink` record it in the orkspace's `git` block of
the Town Scroll. Every git call uses fixed arguments (no shell) and runs in the repository.
"""
from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from orkcraft import scroll as ts

WORKTREES_DIR = Path(".orkcraft") / "worktrees"
_ID = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
GIT_TIMEOUT_S = 60


class WorktreeError(Exception):
    """A git refusal, with git's own message."""


@dataclass
class Status:
    dirty: bool
    changes: int         # porcelain lines: modified, staged, untracked
    branch: str


def _git(repo_root: Path, *args: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=cwd or repo_root, capture_output=True, text=True, timeout=GIT_TIMEOUT_S)


def worktree_path(repo_root: Path, orkspace_id: str) -> Path:
    if not _ID.match(orkspace_id):
        raise WorktreeError(f"bad orkspace id {orkspace_id!r}")
    return repo_root / WORKTREES_DIR / orkspace_id


def valid_branch(repo_root: Path, name: str) -> bool:
    if not name or name.startswith("-") or len(name) > 200:
        return False
    return _git(repo_root, "check-ref-format", "--branch", name).returncode == 0


def branch_exists(repo_root: Path, name: str) -> bool:
    return _git(repo_root, "show-ref", "--verify", "--quiet", f"refs/heads/{name}").returncode == 0


def create(repo_root: Path, orkspace_id: str, branch: str, base: str = "HEAD") -> Path:
    """A worktree for the orkspace on `branch` (existing, or new from `base`). Raises WorktreeError."""
    path = worktree_path(repo_root, orkspace_id)
    if path.exists():
        raise WorktreeError(f"{path.relative_to(repo_root)} already exists")
    if not valid_branch(repo_root, branch):
        raise WorktreeError(f"{branch!r} is not a valid branch name")
    if base.startswith("-"):
        raise WorktreeError(f"bad base {base!r}")
    path.parent.mkdir(parents=True, exist_ok=True)
    if branch_exists(repo_root, branch):
        proc = _git(repo_root, "worktree", "add", str(path), branch)
    else:
        proc = _git(repo_root, "worktree", "add", "-b", branch, str(path), base)
    if proc.returncode != 0:
        raise WorktreeError((proc.stderr or proc.stdout).strip() or f"git worktree add failed ({proc.returncode})")
    return path


def status(path: Path) -> Status:
    proc = subprocess.run(["git", "status", "--porcelain", "--branch"], cwd=path, capture_output=True, text=True,
                          timeout=GIT_TIMEOUT_S)
    if proc.returncode != 0:
        raise WorktreeError((proc.stderr or "").strip() or "not a git worktree")
    lines = proc.stdout.splitlines()
    head = lines[0][3:] if lines and lines[0].startswith("## ") else ""
    branch = head.split("...", 1)[0].split(" ", 1)[0]
    changes = [l for l in lines if not l.startswith("## ")]
    return Status(bool(changes), len(changes), "" if branch.startswith("HEAD") else branch)


def remove(repo_root: Path, path: Path, force: bool = False) -> None:
    """Remove a worktree folder (the branch stays). Refuses with pending work unless forced."""
    root = (repo_root / WORKTREES_DIR).resolve()
    try:
        path.resolve().relative_to(root)
    except ValueError:
        raise WorktreeError(f"{path} is not an orkcraft worktree") from None
    if not force and path.exists() and status(path).dirty:
        raise WorktreeError(f"{path.name} has uncommitted or untracked work — commit it or remove with force")
    args = ["worktree", "remove", *(["--force"] if force else []), str(path)]
    proc = _git(repo_root, *args)
    if proc.returncode != 0:
        raise WorktreeError((proc.stderr or proc.stdout).strip() or "git worktree remove failed")


def link(scroll: ts.TownScroll, orkspace_id: str, repo_root: Path, path: Path, branch: str) -> None:
    """Record the worktree in the orkspace's `git` block (path relative to the repository)."""
    ork = scroll.orkspace(orkspace_id)
    if ork is None:
        raise WorktreeError(f"unknown orkspace {orkspace_id!r}")
    ork.git = ts.GitLink(True, "worktree", "./" + path.resolve().relative_to(repo_root.resolve()).as_posix(), branch)


def unlink(scroll: ts.TownScroll, orkspace_id: str) -> None:
    ork = scroll.orkspace(orkspace_id)
    if ork is not None:
        ork.git = ts.GitLink(False)


def cwd_for(scroll: ts.TownScroll, orkspace_id: str, repo_root: Path) -> Path:
    """Where the orkspace's sessions run: its worktree when linked and present, else the repository."""
    ork = scroll.orkspace(orkspace_id)
    if ork is None or not ork.git.enabled or ork.git.mode != "worktree":
        return repo_root
    target = (repo_root / ork.git.path).resolve()
    try:
        target.relative_to((repo_root / WORKTREES_DIR).resolve())
    except ValueError:
        return repo_root
    return target if target.is_dir() else repo_root
