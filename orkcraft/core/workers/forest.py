"""🌲 File Forest's work: a folder of the project, the files git sees changed in it, and the target
the person picked.

`refresh()` asks git what changed (the face calls it on a timer); files that changed since the last
look go out as `files.changed`, one cart per file (at most `MAX_EVENTS` a look). `pick()` makes a
file or folder the target and sends it as `files.selected`; `send()` sends the target again.
`listing()` is one folder of the tree, `open_in_os()` opens the folder in the system's file manager.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from orkcraft.core.workers import Worker
from orkcraft.realm import gitinfo, shelves

TITLE = "🌲 File Forest"
MAX_EVENTS = 5
MAX_ENTRIES = 500                     # rows of one folder: a huge one is cut, the tree stays quick
IMAGES = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".bmp", ".ico", ".avif")
VIDEOS = (".mp4", ".webm", ".mov", ".m4v", ".ogv")


def media_of(name: str) -> str:
    """`image`, `video` or "" by the file's name."""
    low = name.lower()
    return "image" if low.endswith(IMAGES) else "video" if low.endswith(VIDEOS) else ""


class ForestWorker(Worker):
    TYPE = "forest"
    opener = None                       # tests catch the "open in the OS" call here

    def __init__(self, town, building_id: str) -> None:
        super().__init__(town, building_id)
        self.changes: dict[str, str] = {}        # path → git's two-letter status
        self.picked = ""                         # the target, relative to the project
        self.error = ""
        self._seen: dict | None = None

    def start(self) -> None:
        self.refresh()

    # -- what it is -----------------------------------------------------------------------------

    @property
    def rel(self) -> str:
        return str(self.config.get("path") or ".")

    @property
    def root(self) -> Path:
        return shelves.inside(self.repo_root, self.rel)

    def safe_root(self) -> Path:
        """Its folder, or the project's root when the setting points outside it."""
        try:
            return self.root
        except ValueError:
            return self.repo_root.resolve()

    # -- looking --------------------------------------------------------------------------------

    def refresh(self) -> None:
        """Ask git again; files that changed since the last look go down the roads."""
        before = (dict(self.changes), self.error)
        try:
            self.changes, self.error = shelves.changed_files(self.repo_root, self.rel), ""
        except (RuntimeError, OSError, ValueError, subprocess.SubprocessError) as e:
            self.changes, self.error = {}, gitinfo.plain_error(str(e))[:200]
        self._seen, fresh = shelves.file_changes(self._seen, self.repo_root, self.changes)
        for path in fresh[:MAX_EVENTS]:
            self.emit("files.changed", path, path)
        if (self.changes, self.error) != before:
            self.changed()

    def listing(self, rel: str = "") -> list[dict]:
        """One folder of the tree (`rel` from the project; "" is its own folder): folders first, each
        row with its git status — a folder's says whether something under it changed."""
        folder = self.path(rel) if rel else self.safe_root()
        try:
            items = sorted(folder.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
        except OSError as e:
            raise ValueError(str(e)) from None
        rows = []
        for p in items:
            if p.name.startswith(".") or p.name in shelves.SKIP_DIRS:
                continue
            path = shelves.rel_to(self.repo_root, p)
            is_dir = p.is_dir()
            status = (("M" if any(c.startswith(path + "/") for c in self.changes) else "") if is_dir
                      else self.changes.get(path, "").strip())
            rows.append({"name": p.name, "path": path, "dir": is_dir, "status": status,
                         "media": "" if is_dir else media_of(p.name)})
            if len(rows) >= MAX_ENTRIES:
                break
        return rows

    def path(self, rel: str) -> Path:
        """A path in its folder (the folder itself too), or ValueError."""
        p = shelves.inside(self.repo_root, rel)
        top = self.safe_root()
        if p != top and top not in p.parents:
            raise ValueError(f"{rel} is outside {self.rel}")
        return p

    def file(self, rel: str) -> Path:
        """A file in its folder, or ValueError."""
        p = self.path(rel)
        if not p.is_file():
            raise ValueError(f"{rel} is not a file")
        return p

    # -- acts -----------------------------------------------------------------------------------

    def pick(self, path: Path | str, send: bool = True) -> str:
        """A file or folder is the target (`send`: it goes out as `files.selected` at once)."""
        p = Path(path) if Path(path).is_absolute() else self.repo_root / path
        self.picked = shelves.rel_to(self.repo_root, p)
        if send:
            self.emit("files.selected", self.picked, p.name)
        self.changed()
        return self.picked

    def send(self) -> bool:
        """The target goes down its roads (`files.selected`). True when a road took it."""
        if not self.picked:
            return False
        return self.emit("files.selected", self.picked, self.picked.rsplit("/", 1)[-1])

    def open_in_os(self, opener=None) -> str:
        """Its folder in the system's file manager; what went wrong, else ""."""
        cmd = ["open" if sys.platform == "darwin" else "xdg-open", str(self.safe_root())]
        run = opener or type(self).opener or (lambda c: subprocess.Popen(
            c, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True))
        try:
            run(cmd)
        except OSError as e:
            return f"{cmd[0]}: {e}"
        return ""

    # -- the hut --------------------------------------------------------------------------------

    def status(self) -> str:
        return "ERROR" if self.error else ""

    def mini_status(self) -> list[str]:
        if self.error:
            return [f"⚠ {self.error[:40]}"]
        try:
            top = shelves.top_entries(self.root, 5)
        except ValueError as e:
            return [f"⚠ {e}"]
        lines = [f"{len(self.changes)} changed" if self.changes else "nothing changed"]
        if self.picked:
            lines.append(f"🎯 {self.picked.rsplit('/', 1)[-1]}")
        return lines + top

    def hut_lines(self, widths: list[int]) -> list[str]:
        if self.error:
            return [f"⚠ {self.error[:40]}"]
        try:
            top = shelves.top_entries(self.root, 4)
        except ValueError as e:
            return [f"⚠ {e}"]
        tree = [f" {'└──' if i == len(top) - 1 else '├──'} {name}" for i, name in enumerate(top)]
        lines = [self.folder_label()] + tree
        lines += [""] * (5 - len(lines))
        lines.append(f"changed: {len(self.changes)} files" if self.changes else "changed: nothing")
        lines.append(f"🎯 {self.picked.rsplit('/', 1)[-1]}" if self.picked else "")
        return lines

    def folder_label(self) -> str:
        return f"./{self.rel}".rstrip("/.") or "."
