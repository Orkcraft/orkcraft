"""Snapshots of an orkspace's project around an ork's work (docs/design/projects.md §7.1): before a War Tent
session starts and after it ends, before and after an Agent pool ork works in the project itself. Not in a
worktree (a worktree is its own branch already), never in the demo, never when the project has no git.

    folder_for(town, "shop", cwd)          # the project folder, when `cwd` is it and it has git; else None
    take(town, "shop", folder, "before …") # now, on the caller's thread (an ork's thread)
    later(town, "shop", folder, "after …") # on a thread of its own (the window's thread never waits for git)

Publishes `bus.SNAPSHOT` (orkspace, sha, why). A snapshot that fails is skipped: it never stops the work.
"""
from __future__ import annotations

import threading
from pathlib import Path

from orkcraft.core import bus
from orkcraft.realm import projects, snapshots


def folder_for(town, orkspace_id: str | None, cwd: Path | str | None = None) -> Path | None:
    """The orkspace's project folder, when the work happens there (not in a worktree) and it has git."""
    if getattr(town, "demo", False) or not orkspace_id or getattr(town, "scroll", None) is None:
        return None
    root = projects.root_of(town.scroll, orkspace_id, town.repo_root)
    if cwd is not None:
        try:
            if Path(cwd).resolve() != root.resolve():
                return None
        except OSError:
            return None
    return root if snapshots.has_git(root) else None


def take(town, orkspace_id: str, folder: Path | None, why: str) -> snapshots.Snapshot | None:
    if folder is None:
        return None
    try:
        snap = snapshots.take(folder, orkspace_id, why)
    except Exception:                                  # a snapshot never stops the work it surrounds
        return None
    if snap is not None:
        try:
            town.call(town.publish, bus.SNAPSHOT, orkspace=orkspace_id, sha=snap.sha, why=snap.why)
        except Exception:
            pass
    return snap


def later(town, orkspace_id: str, folder: Path | None, why: str) -> None:
    if folder is None:
        return
    threading.Thread(target=take, args=(town, orkspace_id, folder, why), daemon=True,
                     name=f"snapshot-{orkspace_id}").start()


def for_building(town, building_id: str, workdir: Path | str) -> tuple[str, Path | None]:
    """(the building's orkspace, its project folder when `workdir` is it): where an ork's work is snapshotted."""
    scroll = getattr(town, "scroll", None)
    ork = scroll.orkspace_of(building_id) if scroll is not None else None
    oid = ork.id if ork is not None else ""
    return oid, folder_for(town, oid, workdir)
