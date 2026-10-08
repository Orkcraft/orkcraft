"""What the File Generator reviews: the files agents changed in the working tree.

`git status` names them; accepting one remembers its content hash (it comes back for review only
when it changes again); rejecting one rolls it back — a new file moves to the building's
`rejected/` folder, a changed or deleted one is restored from HEAD after its current content is
copied there. Nothing is ever thrown away.

A task's branch is read the same way (`Branch`): the files it committed since its base, their diff
or content, and a copy of one to open in the system viewer. One of its files is rejected by a commit on
the branch that puts it back as the base has it (its content kept aside first), and brought back by
another; the branch is never checked out for it, and a worktree that has it checked out follows.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import shutil
import struct
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

GIT_TIMEOUT_S = 10
PREVIEW_LINES = 200
SKIP = (".orkcraft/", "loot/")           # never up for review: orkcraft's state and Loot's own reports
OPEN_HINT = "o opens it"


@dataclass
class Generated:
    path: str             # repo-relative
    change: str           # A (new) | M (changed) | D (deleted) | R (renamed)
    reviewed: str = ""    # "" | accepted


def _git(repo: Path, *args: str, check: bool = True, env: dict | None = None) -> str:
    out = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, timeout=GIT_TIMEOUT_S, env=env)
    if check and out.returncode != 0:
        raise RuntimeError(out.stderr.strip() or f"git {args[0]} failed")
    return out.stdout


def _git_bytes(repo: Path, *args: str) -> bytes:
    out = subprocess.run(["git", *args], cwd=repo, capture_output=True, timeout=GIT_TIMEOUT_S)
    if out.returncode != 0:
        raise RuntimeError(out.stderr.decode("utf-8", "replace").strip() or f"git {args[0]} failed")
    return out.stdout


def _size(n: int) -> str:
    return f"{n} bytes" if n < 1024 else f"{n / 1024:.1f} KB" if n < 1024 * 1024 else f"{n / 1024 / 1024:.1f} MB"


def image_info(data: bytes) -> str:
    """`PNG image · 512×512 · 34.2 KB` for a picture (by its first bytes), "" for anything else."""
    kind, dims = "", None
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        kind = "PNG"
        if len(data) >= 24:
            dims = struct.unpack(">II", data[16:24])
    elif data[:6] in (b"GIF87a", b"GIF89a"):
        kind = "GIF"
        if len(data) >= 10:
            dims = struct.unpack("<HH", data[6:10])
    elif data[:3] == b"\xff\xd8\xff":
        kind, dims = "JPEG", _jpeg_dims(data)
    elif data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        kind = "WebP"
    elif data[:2] == b"BM":
        kind = "BMP"
        if len(data) >= 26:
            w, h = struct.unpack("<ii", data[18:26])
            dims = (w, abs(h))
    if not kind:
        return ""
    return " · ".join([f"{kind} image"] + ([f"{dims[0]}×{dims[1]}"] if dims else []) + [_size(len(data))])


def _jpeg_dims(data: bytes) -> tuple[int, int] | None:
    i = 2
    while i + 9 < len(data):                     # walk the markers to the frame header (SOF0…SOF15)
        if data[i] != 0xFF:
            return None
        marker, length = data[i + 1], struct.unpack(">H", data[i + 2:i + 4])[0]
        if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
            h, w = struct.unpack(">HH", data[i + 5:i + 9])
            return w, h
        i += 2 + length
    return None


def binary_note(data: bytes) -> str:
    """What the preview says for a file that is not text."""
    return f"({image_info(data) or f'binary, {_size(len(data))}'} · {OPEN_HINT})"


def opener() -> list[str] | None:
    """The system viewer's command: `open` on macOS, `xdg-open` on Linux; None when there is none."""
    if sys.platform == "darwin":
        return ["open"]
    if sys.platform.startswith("linux") and shutil.which("xdg-open"):
        return ["xdg-open"]
    return None


def open_file(path: Path) -> None:
    """Hand `path` to the system viewer, detached from orkcraft."""
    cmd = opener()
    if cmd is None:
        raise RuntimeError(f"no system viewer here (open / xdg-open) — the file is {path}")
    subprocess.Popen([*cmd, str(path)], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL, start_new_session=True)


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
            return binary_note(p.read_bytes())
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


class Branch:
    """The files a task committed on its branch, read in the worktree it ran in (`base...branch`)."""

    def __init__(self, worktree: Path, branch: str, base: str = "") -> None:
        if not branch or branch.startswith("-") or (base and base.startswith("-")):
            raise ValueError(f"not a branch: {branch!r}")
        self.worktree, self.branch, self.base = worktree, branch, base

    def _since(self) -> str:
        """Where the branch left its base: origin's copy of the base when there is one."""
        for ref in ([f"origin/{self.base}", self.base] if self.base else []):
            if subprocess.run(["git", "rev-parse", "--verify", "--quiet", ref], cwd=self.worktree,
                              capture_output=True, timeout=GIT_TIMEOUT_S).returncode == 0:
                return ref
        raise RuntimeError(f"no base to compare {self.branch} with")

    def files(self) -> list[Generated]:
        out = _git(self.worktree, "diff", "--name-status", "-z", "--no-renames", f"{self._since()}...{self.branch}")
        parts = out.split("\0")
        rows = [Generated(rel, st[:1]) for st, rel in zip(parts[0::2], parts[1::2])
                if st and rel and not rel.startswith(SKIP)]
        return sorted(rows, key=lambda g: g.path)

    def blob(self, rel: str) -> bytes:
        """The file as the branch has it."""
        return _git_bytes(self.worktree, "show", f"{self.branch}:{rel}")

    def preview(self, rel: str) -> str:
        diff = _git(self.worktree, "diff", f"{self._since()}...{self.branch}", "--", rel, check=False)
        if diff.strip() and "\nBinary files " not in diff and "\nGIT binary patch" not in diff:
            return "\n".join(diff.splitlines()[:PREVIEW_LINES])
        try:
            data = self.blob(rel)
        except RuntimeError:
            return "(deleted on the branch)"
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            return binary_note(data)
        return "\n".join(text.splitlines()[:PREVIEW_LINES])

    def export(self, rel: str, into: Path | None = None) -> Path:
        """A copy of the branch's `rel` in a temporary folder (its own name, so the viewer knows its type)."""
        key = hashlib.sha1(f"{self.worktree}\0{self.branch}\0{rel}".encode()).hexdigest()[:12]
        dest = (into or Path(tempfile.gettempdir()) / "orkcraft-loot") / key / Path(rel).name
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(self.blob(rel))
        return dest

    # -- one file decided --------------------------------------------------------------------------

    def _tree_entry(self, rev: str, rel: str) -> tuple[str, str] | None:
        """(mode, blob id) of `rel` in `rev`, None when it is not there."""
        out = _git(self.worktree, "ls-tree", "-z", rev, "--", rel)
        head, _, name = out.split("\0")[0].partition("\t")
        parts = head.split()
        return (parts[0], parts[2]) if name == rel and len(parts) == 3 and parts[1] == "blob" else None

    def _checked_out(self) -> Path | None:
        """The worktree that has the branch checked out, None when none has."""
        here = None
        for ln in _git(self.worktree, "worktree", "list", "--porcelain").splitlines():
            if ln.startswith("worktree "):
                here = Path(ln[len("worktree "):])
            elif ln == f"branch refs/heads/{self.branch}" and here is not None:
                return here
        return None

    def _commit(self, rel: str, entry: tuple[str, str] | None, message: str) -> None:
        """One commit on the branch that sets `rel` to `entry` (mode, blob) or removes it (None). The branch
        is not checked out for it; a worktree that has it checked out gets the file as the commit has it,
        and refuses while the file has changes there nobody committed."""
        there = self._checked_out()
        if there is not None and _git(there, "status", "--porcelain", "--", rel).strip():
            raise RuntimeError(f"{rel} has uncommitted changes in {there.name}: commit or drop them first")
        old = _git(self.worktree, "rev-parse", "--verify", f"refs/heads/{self.branch}").strip()
        with tempfile.TemporaryDirectory() as tmp:
            env = {**os.environ, "GIT_INDEX_FILE": str(Path(tmp) / "index")}
            _git(self.worktree, "read-tree", old, env=env)
            if entry is None:
                _git(self.worktree, "update-index", "--force-remove", "--", rel, env=env)
            else:
                _git(self.worktree, "update-index", "--add", "--cacheinfo", f"{entry[0]},{entry[1]},{rel}", env=env)
            tree = _git(self.worktree, "write-tree", env=env).strip()
        commit = _git(self.worktree, "commit-tree", tree, "-p", old, "-m", message).strip()
        _git(self.worktree, "update-ref", f"refs/heads/{self.branch}", commit, old)
        if there is not None:
            if entry is None:
                _git(there, "rm", "-q", "-f", "--ignore-unmatch", "--", rel)
            else:
                _git(there, "checkout", "HEAD", "--", rel)

    def reject(self, rel: str, keep: Path, now: dt.datetime | None = None) -> dict:
        """Put `rel` back on the branch as its base has it (gone, if the task added it), its content on the
        branch kept under `keep/<stamp>/` first. Returns what `restore` needs: {path, at, change, kept, mode}."""
        change = next((g.change for g in self.files() if g.path == rel), None)
        if change is None:
            raise ValueError(f"{rel} is not changed on {self.branch}")
        stamp = (now or dt.datetime.now()).strftime("%Y%m%d-%H%M%S")
        mine = self._tree_entry(self.branch, rel)
        kept, mode = "", ""
        if mine is not None:
            dest = keep / stamp / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(self.blob(rel))
            kept, mode = str(dest), mine[0]
        since = _git(self.worktree, "merge-base", self._since(), self.branch).strip()
        self._commit(rel, self._tree_entry(since, rel), f"Loot: {rel} rejected")
        return {"path": rel, "at": stamp, "change": change, "kept": kept, "mode": mode}

    def restore(self, entry: dict) -> None:
        """Bring a rejected file back on the branch as the task had it (a deletion: deleted again)."""
        rel = str(entry.get("path") or "")
        if not rel:
            raise ValueError("nothing to bring back")
        if entry.get("kept"):
            kept = Path(entry["kept"])
            if not kept.is_file():
                raise ValueError(f"the kept copy of {rel} is gone")
            blob = _git(self.worktree, "hash-object", "-w", "--", str(kept)).strip()
            self._commit(rel, (entry.get("mode") or "100644", blob), f"Loot: {rel} brought back")
        else:
            self._commit(rel, None, f"Loot: {rel} deleted again")
