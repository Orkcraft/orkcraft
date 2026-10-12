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

It also names the orkspace it happened in (`Orkcraft-Orkspace: <id>`, docs/design/projects.md §6), so a map has
a history of its own and goes back as a whole: `history(root, orkspace=…)`, `orkspace_at(root, sha, …)`.
"""
from __future__ import annotations

import datetime as dt
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
ORKSPACE_TRAILER = "Orkcraft-Orkspace"
AT_TRAILER = "Orkcraft-At"          # when, to the microsecond (git keeps seconds): sorts against project snapshots
GIT_TIMEOUT_S = 30
KINDS = ("create", "update", "road", "revert", "auto-improve", "weekly", "remove", "ui", "orkspace")


@dataclass
class Checkpoint:
    sha: str
    at: str
    message: str
    building: str
    orkspace: str = ""


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


def commit(root: Path, kind: str, building: str, reason: str, scroll_path: Path | None = None,
           orkspace: str = "") -> str | None:
    """Commit what changed as `<kind>(<building>): <reason>`, naming the orkspace it happened in; None when
    nothing changed. Never raises."""
    try:
        ensure(root)
        snapshot(root, scroll_path)
        _git(root, "add", "-A")
        if not _git(root, "status", "--porcelain", check=False).stdout.strip():
            return None
        msg = f"{kind}({building or orkspace or 'camp'}): {reason}".strip()
        at = dt.datetime.now(dt.timezone.utc).isoformat()
        trailers = (f"{TRAILER}: {building or 'camp'}" + (f"\n{ORKSPACE_TRAILER}: {orkspace}" if orkspace else "")
                    + f"\n{AT_TRAILER}: {at}")
        _git(root, "commit", "-q", "-m", msg, "-m", trailers)
        return _git(root, "rev-parse", "HEAD").stdout.strip()
    except (RuntimeError, OSError, subprocess.SubprocessError):
        return None


def history(root: Path, building: str | None = None, limit: int = 50, orkspace: str | None = None) -> list[Checkpoint]:
    """The newest checkpoints first: all of them, one building's, or one orkspace's."""
    if not (root / DIR / ".git").exists():
        return []
    args = ["log", f"-{limit}", "--format=%H%x09%cI%x09%s%x09%(trailers:key=" + TRAILER + ",valueonly,separator=)"
            "%x09%(trailers:key=" + ORKSPACE_TRAILER + ",valueonly,separator=)"
            "%x09%(trailers:key=" + AT_TRAILER + ",valueonly,separator=)"]
    if building:
        args += ["--grep", f"^{TRAILER}: {re.escape(building)}$"]
    elif orkspace:
        args += ["--grep", f"^{ORKSPACE_TRAILER}: {re.escape(orkspace)}$"]
    out = _git(root, *args, check=False).stdout
    rows = []
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) >= 3:
            precise = parts[5].strip() if len(parts) > 5 else ""
            rows.append(Checkpoint(parts[0], precise or parts[1], parts[2], parts[3].strip() if len(parts) > 3 else "",
                                   parts[4].strip() if len(parts) > 4 else ""))
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


def at_of(root: Path, sha: str) -> str:
    """When checkpoint `sha` was made (ISO 8601), "" when it is unknown."""
    if not re.fullmatch(r"[0-9a-f]{7,40}", sha or ""):
        return ""
    out = _git(root, "show", "-s", "--format=%cI", sha, check=False)
    return out.stdout.strip() if out.returncode == 0 else ""


def orkspace_at(root: Path, sha: str, orkspace_id: str) -> tuple[dict, dict[str, dict], dict[str, dict | None],
                                                                  dict[str, dict[str, str]]] | None:
    """The orkspace as it was at checkpoint `sha`: (its scroll entry, its buildings' scroll entries by id, their
    specs, their scripts and blueprints) — None when it did not exist then or the commit is unknown."""
    if not re.fullmatch(r"[0-9a-f]{7,40}", sha or ""):
        return None
    snap = _show(root, sha, SNAPSHOT.as_posix())
    try:
        data = json.loads(snap) if snap else None
    except ValueError:
        data = None
    if not isinstance(data, dict):
        return None
    entry = next((o for o in data.get("orkspaces", []) if o.get("id") == orkspace_id), None)
    if entry is None:
        return None
    ids = list(entry.get("buildings", []))
    entries = {b["id"]: b for b in data.get("buildings", []) if b.get("id") in ids}
    specs, files = {}, {}
    for bid in ids:
        text = _show(root, sha, f"buildings/{bid}.json")
        try:
            specs[bid] = json.loads(text) if text else None
        except ValueError:
            specs[bid] = None
        files[bid] = {}
        for prefix in (f"scripts/{bid}", f"blueprints/{bid}"):
            for p in _tree(root, sha, prefix):
                content = _show(root, sha, p)
                if content is not None:
                    files[bid][p] = content
    return entry, entries, specs, files


def can_revert(root: Path, building: str) -> bool:
    """Whether `revert` has somewhere to go: an earlier checkpoint that already had the building —
    `building_before` without reading its files. Never raises."""
    try:
        mine = history(root, building, limit=1)
        if not mine:
            return False
        parent = _git(root, "rev-parse", "--verify", "--quiet", f"{mine[0].sha}^", check=False).stdout.strip()
        if not parent:
            return False
        if _git(root, "cat-file", "-e", f"{parent}:buildings/{building}.json", check=False).returncode == 0:
            return True
        snap = _show(root, parent, SNAPSHOT.as_posix())
        return bool(snap) and any(b.get("id") == building for b in json.loads(snap).get("buildings", []))
    except (ValueError, AttributeError, OSError, subprocess.SubprocessError):
        return False


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
