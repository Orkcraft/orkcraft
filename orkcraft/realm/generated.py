"""What the File Generator reviews: the files agents changed in the working tree.

`git status` names them; accepting one remembers its content hash (it comes back for review only
when it changes again); rejecting one rolls it back — a new file moves to the building's
`rejected/` folder, a changed or deleted one is restored from HEAD after its current content is
copied there. Nothing is ever thrown away.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

GIT_TIMEOUT_S = 10
PREVIEW_LINES = 200
SKIP = (".orkcraft/", "loot/")           # never up for review: orkcraft's state and Loot's own reports


@dataclass
class Generated:
    path: str             # repo-relative
    change: str           # A (new) | M (changed) | D (deleted) | R (renamed)
    reviewed: str = ""    # "" | accepted


def _git(repo: Path, *args: str, check: bool = True) -> str:
    out = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, timeout=GIT_TIMEOUT_S)
    if check and out.returncode != 0:
        raise RuntimeError(out.stderr.strip() or f"git {args[0]} failed")
    return out.stdout


def _hash(repo: Path, rel: str) -> str:
    p = repo / rel
    if not p.is_file():
        return "-"
    return hashlib.sha1(p.read_bytes()).hexdigest()


def _inside(repo: Path, rel: str) -> Path:
    p = (repo / rel).resolve()
    if repo.resolve() not in p.parents and p != repo.resolve():
        raise ValueError(f"{rel} is outside the repository")
    return p


class Review:
    """The review state of one File Generator building."""

    def __init__(self, repo: Path, state_dir: Path, scope: str = "") -> None:
        self.repo, self.state_dir, self.scope = repo, state_dir, scope.strip("/")
        self.state_file = state_dir / "review.json"

    # -- state --------------------------------------------------------------------------------------

    def _load(self) -> dict:
        try:
            data = json.loads(self.state_file.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}

    def _save(self, data: dict) -> None:
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.state_file.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    # -- what there is ------------------------------------------------------------------------------

    def files(self) -> list[Generated]:
        args = ["status", "--porcelain=v1", "-z", "--untracked-files=all", "--no-renames"]
        if self.scope:
            args += ["--", self.scope]
        out = _git(self.repo, *args)             # -z: paths as they are, never quoted or escaped
        accepted = self._load().get("accepted", {})
        rows = []
        for entry in out.split("\0"):
            if len(entry) < 4:
                continue
            xy, rel = entry[:2], entry[3:]
            if rel.startswith(SKIP) or rel.endswith(".DS_Store"):
                continue                       # orkcraft's own state, the rejects and what Loot keeps
            change = "A" if xy == "??" or "A" in xy else "D" if "D" in xy else "M"
            reviewed = "accepted" if accepted.get(rel) == _hash(self.repo, rel) else ""
            rows.append(Generated(rel, change, reviewed))
        rows.sort(key=lambda g: (g.reviewed != "", g.path))
        return rows

    def pending(self) -> list[Generated]:
        return [g for g in self.files() if not g.reviewed]

    def preview(self, rel: str) -> str:
        p = _inside(self.repo, rel)
        tracked = bool(_git(self.repo, "ls-files", "--", rel, check=False).strip())
        if tracked:
            diff = _git(self.repo, "diff", "HEAD", "--", rel, check=False)
            if diff.strip():
                return "\n".join(diff.splitlines()[:PREVIEW_LINES])
        if not p.is_file():
            return "(deleted)"
        try:
            text = p.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            return f"(binary, {p.stat().st_size} bytes)"
        return "\n".join(text.splitlines()[:PREVIEW_LINES])

    # -- decisions ----------------------------------------------------------------------------------

    def accept(self, rel: str) -> None:
        _inside(self.repo, rel)
        data = self._load()
        data.setdefault("accepted", {})[rel] = _hash(self.repo, rel)
        self._save(data)

    def reject(self, rel: str, now: dt.datetime | None = None) -> Path | None:
        """Roll `rel` back; returns where its rejected content was kept (None for a deletion)."""
        p = _inside(self.repo, rel)
        stamp = (now or dt.datetime.now()).strftime("%Y%m%d-%H%M%S")
        keep = self.state_dir / "rejected" / stamp / rel
        kept = None
        if p.is_file():
            keep.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, keep)
            kept = keep
        tracked = bool(_git(self.repo, "ls-files", "--", rel, check=False).strip())
        in_head = bool(_git(self.repo, "ls-tree", "--name-only", "HEAD", "--", rel, check=False).strip())
        if in_head:
            _git(self.repo, "restore", "--source=HEAD", "--staged", "--worktree", "--", rel)
        else:
            if tracked:
                _git(self.repo, "rm", "--cached", "--quiet", "--", rel, check=False)
            if p.is_file():
                p.unlink()
        data = self._load()
        data.get("accepted", {}).pop(rel, None)
        data.setdefault("rejected", []).append({"path": rel, "at": stamp, "kept": str(kept) if kept else ""})
        data["rejected"] = data["rejected"][-200:]
        self._save(data)
        return kept

    def rejected(self) -> list[dict]:
        """Rejected files whose content is still kept, newest first: {path, at, kept}."""
        return [r for r in reversed(self._load().get("rejected", [])) if r.get("kept") and Path(r["kept"]).is_file()]

    def restore(self, rel: str, at: str = "") -> Path:
        """Bring a rejected file back (the latest rejection of `rel`, or the one at `at`)."""
        p = _inside(self.repo, rel)
        entry = next((r for r in self.rejected() if r["path"] == rel and (not at or r["at"] == at)), None)
        if entry is None:
            raise ValueError(f"no kept copy of {rel}")
        p.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(entry["kept"], p)
        data = self._load()
        data["rejected"] = [r for r in data.get("rejected", []) if r != entry]
        self._save(data)
        return p
