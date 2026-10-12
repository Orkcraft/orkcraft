"""A copy of Orkcraft's source that an agent changes for one fix (docs/design/improve-buildings.md §14): the installed
app is never changed, and each fix is a pull request of its own.

- **From a git checkout** (bin/orkcraft, `pip install -e`): a `git worktree` of the checkout at the commit it runs —
  the whole repository, its CLAUDE.md and its tests, so the agent follows the rules and runs the tests.
- **Else** (brew, uv, pipx): a copy of the `orkcraft` package as installed, a git repository of its own whose first
  commit is the package; the design system's sprites linked, never copied.

Either way the paths are the repository's (`orkcraft/gui/static/js/…`), and what changed is told against the commit
the copy started from (`base`).

    copy = work_copy.make(dest, checkout)     {"top", "base", "kind": worktree | package}
    work_copy.changed(top, base)              the paths changed (added and changed; a deleted one is not sent)
    work_copy.diff(top, base)                 a unified diff
    work_copy.files(top, base)                {path: (as at base, as now)}: text, or bytes for a picture
    work_copy.drop(top, checkout)             the copy gone
    work_copy.allow_tests(top, python)        Claude Code may run the tests there (and only read git)

The copy's own `.claude/settings.local.json` (what `allow_tests` writes) is never a change of it.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import orkcraft
from orkcraft.realm import bench

DIFF_MAX = 200_000
SETTINGS = ".claude/settings.local.json"
NOT_MINE = (".", f":(exclude){SETTINGS}")          # the pathspec of what a change is: all but the copy's own settings


def package() -> Path:
    return Path(orkcraft.__file__).resolve().parent


def make(dest: Path, checkout: Path | None = None) -> dict:
    """The copy at `dest` (made fresh): a worktree of `checkout` at its HEAD, else the installed package."""
    if dest.exists():
        drop(dest, checkout)
    dest.parent.mkdir(parents=True, exist_ok=True)
    if checkout is not None:
        base = bench.git(checkout, "rev-parse", "HEAD")
        bench.git(checkout, "worktree", "add", "--detach", str(dest), base, timeout=120)
        return {"top": str(dest), "base": base, "kind": "worktree"}
    src = package()
    shutil.copytree(src, dest / "orkcraft", ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "system"))
    system = src / "design" / "system"
    if system.exists():                           # the sprites and fonts: linked, never copied
        (dest / "orkcraft" / "design" / "system").symlink_to(system.resolve(), target_is_directory=True)
    (dest / ".gitignore").write_text("__pycache__/\n*.pyc\norkcraft/design/system\n", encoding="utf-8")
    bench.git(dest, "init", "-q", "-b", "main")
    bench.git(dest, "add", "-A")
    bench.git(dest, *bench.AUTHOR, "commit", "-q", "-m", f"orkcraft {orkcraft.__version__} as installed")
    return {"top": str(dest), "base": bench.git(dest, "rev-parse", "HEAD"), "kind": "package"}


def _staged(top: Path, *args: str) -> str:
    bench.git(top, "add", "-A")
    return bench.git(top, "diff", "--cached", *args, "--", *NOT_MINE)


def allow_tests(top: Path, python: str) -> None:
    """Claude Code, working in the copy with its edits accepted, may also run pytest and read git there; it asks for
    nothing else (it cannot: a run has no one to ask)."""
    path = top / SETTINGS
    path.parent.mkdir(parents=True, exist_ok=True)
    allow = [f"Bash({python} -m pytest:*)", "Bash(python -m pytest:*)", "Bash(uv run pytest:*)",
             "Bash(git diff:*)", "Bash(git status:*)", "Bash(git log:*)", "Bash(git show:*)"]
    path.write_text(json.dumps({"permissions": {"allow": allow, "deny": ["Bash(git push:*)", "Bash(git commit:*)"]}},
                               indent=1), encoding="utf-8")


def changed(top: Path, base: str) -> list[str]:
    if not (top / ".git").exists():
        return []
    out = _staged(top, "--name-only", "--diff-filter=d", base)
    return [line for line in out.splitlines() if line.strip()]


def deleted(top: Path, base: str) -> list[str]:
    if not (top / ".git").exists():
        return []
    return [line for line in _staged(top, "--name-only", "--diff-filter=D", base).splitlines() if line.strip()]


def diff(top: Path, base: str) -> str:
    if not (top / ".git").exists():
        return ""
    return _staged(top, base)[:DIFF_MAX]


def _text(data: bytes) -> str | None:
    try:
        return data.decode("utf-8") if b"\0" not in data else None
    except UnicodeDecodeError:
        return None


def files(top: Path, base: str) -> dict[str, tuple]:
    """Each changed path as at `base` and as now: both text, or both bytes when either is not text."""
    out: dict[str, tuple] = {}
    for path in changed(top, base):
        shown = subprocess.run(["git", "show", f"{base}:{path}"], cwd=top, capture_output=True)
        was = shown.stdout if shown.returncode == 0 else b""       # b"": a file the change added
        now = (top / path).read_bytes() if (top / path).is_file() else b""
        a, b = _text(was), _text(now)
        out[path] = (a, b) if a is not None and b is not None else (was, now)
    return out


def drop(top: Path, checkout: Path | None = None) -> None:
    if checkout is not None and (top / ".git").is_file():          # a worktree's .git is a file
        try:
            bench.git(checkout, "worktree", "remove", "--force", str(top), timeout=120)
        except RuntimeError:
            pass
    shutil.rmtree(top, ignore_errors=True)
    if checkout is not None:
        try:
            bench.git(checkout, "worktree", "prune")
        except RuntimeError:
            pass
