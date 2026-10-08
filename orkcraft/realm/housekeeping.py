"""⛏ The Peon's housekeeping: what piles up in `.orkcraft/` and what keeps running.

    logs       a `*.jsonl` log over LOG_LIMIT → keep its last KEEP_LINES lines
    orphans    state of a building no Town Scroll knows any more (`.orkcraft/<type>/<id>/`) → remove
    worktrees  git's prunable worktrees → `git worktree prune`; folders under `.orkcraft/worktrees/`
               git does not know → remove
    daemons    a demolished building still listening (a Watchtower's webhook) → stop (done by the app)

`scan` only looks; `clean` changes nothing outside `.orkcraft/` and never touches the camp's git
(`buildings/`, `scripts/`, `blueprints/`, `town/`, `.git`).
"""
from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(".orkcraft")
LOG_LIMIT = 1_000_000
KEEP_LINES = 2000
STATE_TYPES = ("pit", "watchtower", "signpost", "mill", "fields", "barracks", "war_drum", "forest", "scrolls",
               "lake", "forge", "loot", "crag", "catapult", "workshop", "horn", "mine")


@dataclass
class Chore:
    kind: str            # log | orphan | worktree | prune | daemon
    path: str            # relative to the repository (or a building id for a daemon)
    detail: str
    size: int = 0


def _size(p: Path) -> int:
    if p.is_file():
        return p.stat().st_size
    return sum(f.stat().st_size for f in p.rglob("*") if f.is_file())


def scan(repo_root: Path, known: set[str]) -> list[Chore]:
    """Everything the Peon would clean; `known` are the building ids of the Town Scroll."""
    root = repo_root / ROOT
    chores: list[Chore] = []
    if not root.is_dir():
        return chores
    for log in sorted(root.rglob("*.jsonl")):
        if ".git" in log.parts:
            continue
        size = log.stat().st_size
        if size > LOG_LIMIT:
            chores.append(Chore("log", str(log.relative_to(repo_root)), f"{size // 1024} KB log", size))
    for t in STATE_TYPES:
        for d in sorted((root / t).glob("*")) if (root / t).is_dir() else []:
            if d.is_dir() and d.name not in known:
                chores.append(Chore("orphan", str(d.relative_to(repo_root)), f"state of a gone building {d.name}",
                                    _size(d)))
    try:
        out = subprocess.run(["git", "-C", str(repo_root), "worktree", "list", "--porcelain"], capture_output=True,
                             text=True, timeout=10).stdout
    except (OSError, subprocess.SubprocessError):
        out = ""
    listed = {line.split(" ", 1)[1] for line in out.splitlines() if line.startswith("worktree ")}
    if "prunable" in out:
        chores.append(Chore("prune", ".git/worktrees", "git keeps worktrees whose folders are gone"))
    wt = root / "worktrees"
    for d in sorted(wt.glob("*")) if wt.is_dir() else []:
        if d.is_dir() and str(d.resolve()) not in {str(Path(p).resolve()) for p in listed}:
            chores.append(Chore("worktree", str(d.relative_to(repo_root)), "a worktree folder git does not know",
                                _size(d)))
    return chores


def _inside(repo_root: Path, p: Path) -> bool:
    root = (repo_root / ROOT).resolve()
    try:
        rel = p.resolve().relative_to(root)
    except ValueError:
        return False
    return bool(rel.parts) and rel.parts[0] not in ("buildings", "scripts", "blueprints", "town", ".git")


def clean(repo_root: Path, chores: list[Chore]) -> list[str]:
    """Do the chores (daemons are the app's); what was done, one line each."""
    done = []
    for c in chores:
        p = repo_root / c.path
        try:
            if c.kind == "log" and _inside(repo_root, p) and p.is_file():
                lines = p.read_text(encoding="utf-8", errors="replace").splitlines()[-KEEP_LINES:]
                p.write_text("\n".join(lines) + "\n", encoding="utf-8")
                done.append(f"rotated {c.path} (kept {len(lines)} lines)")
            elif c.kind in ("orphan", "worktree") and _inside(repo_root, p) and p.is_dir():
                shutil.rmtree(p)
                done.append(f"removed {c.path}")
            elif c.kind == "prune":
                subprocess.run(["git", "-C", str(repo_root), "worktree", "prune"], capture_output=True, timeout=20)
                done.append("pruned git's stale worktrees")
        except (OSError, subprocess.SubprocessError) as e:
            done.append(f"could not clean {c.path}: {e}")
    return done
