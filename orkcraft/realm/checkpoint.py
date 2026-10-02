"""Checkpoints: every change of the camp is a commit in its own git, `.orkcraft/`.

The service repository lives inside the project's `.orkcraft/` folder and is separate from the
project's history. It keeps only what defines the camp:

    buildings/<id>.json       the specs
    scripts/<id>/…            the scripts buildings run (blueprints of T1108 stage 5)
    blueprints/<id>/…         what the Builder designed
    town/scroll.json          a snapshot of the Town Scroll (`.orkcraft.json`) at the commit

Logs, ledgers, samples, worktrees and the pit stay out (`.gitignore` is a whitelist). A commit
names its building in a trailer (`Orkcraft-Building: <id>`), so one building's history — and its
revert — never touches the others:

    revert(<id>)  puts back that building's files and its entry in the scroll (its incoming roads,
                  its garrison and orders) as they were before its last change, then commits that.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

DIR = Path(".orkcraft")
SNAPSHOT = Path("town") / "scroll.json"
GITIGNORE = "\n".join([
    "# the camp's service repository: only what defines the camp is tracked",
    "*", "!.gitignore", "!buildings/", "!buildings/*.json", "!scripts/", "!scripts/**", "!blueprints/",
    "!blueprints/**", "!town/", "!town/scroll.json", "",
])
TRAILER = "Orkcraft-Building"
GIT_TIMEOUT_S = 30
KINDS = ("create", "update", "road", "revert", "auto-improve", "weekly", "remove")


@dataclass
class Checkpoint:
    sha: str
    at: str
    message: str
    building: str


def _git(root: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    out = subprocess.run(["git", "-C", str(root / DIR), *args], capture_output=True, text=True, timeout=GIT_TIMEOUT_S)
    if check and out.returncode != 0:
        raise RuntimeError((out.stderr or out.stdout).strip()[:300] or f"git {args[0]} failed")
    return out


def ensure(root: Path) -> Path:
    """The service repository, created on first use (its own identity, its own .gitignore)."""
    folder = root / DIR
    folder.mkdir(parents=True, exist_ok=True)
    if not (folder / ".git").exists():
        _git(root, "init", "-q", "-b", "camp")
        _git(root, "config", "user.name", "Orkcraft")
        _git(root, "config", "user.email", "orkcraft@localhost")
        _git(root, "config", "commit.gpgsign", "false")
    gi = folder / ".gitignore"
    if not gi.exists() or gi.read_text(encoding="utf-8") != GITIGNORE:
        gi.write_text(GITIGNORE, encoding="utf-8")
    return folder


def snapshot(root: Path, scroll_path: Path | None) -> None:
    if scroll_path is None or not Path(scroll_path).is_file():
        return
    dst = root / DIR / SNAPSHOT
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(scroll_path, dst)


def commit(root: Path, kind: str, building: str, reason: str, scroll_path: Path | None = None) -> str | None:
    """Commit what changed as `<kind>(<building>): <reason>`; None when nothing changed. Never raises."""
    try:
        ensure(root)
        snapshot(root, scroll_path)
        _git(root, "add", "-A")
        if not _git(root, "status", "--porcelain", check=False).stdout.strip():
            return None
        msg = f"{kind}({building or 'camp'}): {reason}".strip()
        _git(root, "commit", "-q", "-m", msg, "-m", f"{TRAILER}: {building or 'camp'}")
        return _git(root, "rev-parse", "HEAD").stdout.strip()
    except (RuntimeError, OSError, subprocess.SubprocessError):
        return None


def history(root: Path, building: str | None = None, limit: int = 50) -> list[Checkpoint]:
    if not (root / DIR / ".git").exists():
        return []
    args = ["log", f"-{limit}", "--format=%H%x09%cI%x09%s%x09%(trailers:key=" + TRAILER + ",valueonly,separator=)"]
    if building:
        args += ["--grep", f"^{TRAILER}: {re.escape(building)}$"]
    out = _git(root, *args, check=False).stdout
    rows = []
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) >= 3:
            rows.append(Checkpoint(parts[0], parts[1], parts[2], parts[3].strip() if len(parts) > 3 else ""))
    return rows


def _show(root: Path, rev: str, path: str) -> str | None:
    out = _git(root, "show", f"{rev}:{path}", check=False)
    return out.stdout if out.returncode == 0 else None


def _tree(root: Path, rev: str, prefix: str) -> list[str]:
    out = _git(root, "ls-tree", "-r", "--name-only", rev, "--", prefix, check=False)
    return [p for p in out.stdout.splitlines() if p]


def building_before(root: Path, building: str) -> tuple[str, dict | None, dict | None, dict[str, str]] | None:
    """(the commit to go back to, its spec, its scroll entry, its scripts/blueprints) — the state
    before the building's last checkpoint; None when it has no earlier one."""
    mine = history(root, building, limit=2)
    if not mine:
        return None
    parent = _git(root, "rev-parse", "--verify", "--quiet", f"{mine[0].sha}^", check=False).stdout.strip()
    if not parent:
        return None
    spec_text = _show(root, parent, f"buildings/{building}.json")
    spec = json.loads(spec_text) if spec_text else None
    entry = None
    snap = _show(root, parent, SNAPSHOT.as_posix())
    if snap:
        try:
            entry = next((b for b in json.loads(snap).get("buildings", []) if b.get("id") == building), None)
        except ValueError:
            entry = None
    files = {}
    for prefix in (f"scripts/{building}", f"blueprints/{building}"):
        for p in _tree(root, parent, prefix):
            text = _show(root, parent, p)
            if text is not None:
                files[p] = text
    return parent, spec, entry, files


def restore_files(root: Path, building: str, spec: dict | None, files: dict[str, str]) -> None:
    """Put the building's own files back as they were (a spec it did not have yet is removed)."""
    folder = root / DIR
    spec_path = folder / "buildings" / f"{building}.json"
    if spec is None:
        spec_path.unlink(missing_ok=True)
    else:
        spec_path.parent.mkdir(parents=True, exist_ok=True)
        spec_path.write_text(json.dumps(spec, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    for prefix in (f"scripts/{building}", f"blueprints/{building}"):
        shutil.rmtree(folder / prefix, ignore_errors=True)
    for rel, text in files.items():
        p = folder / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
