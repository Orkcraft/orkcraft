"""🌲 File Forest: a folder of the project as a tree; Enter picks a target.

The hut shows the folder's top entries and how many files in it git sees changed; the open
building is the whole tree with a preview of the highlighted file. Files that change between two
looks (every 10 s) go out as `files.changed`, one cart per file (at most five a look). ↗ opens the
folder in the system's file manager.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import DirectoryTree, Static

from orkcraft.realm import shelves
from orkcraft.screens.typed.base import TypedView

REFRESH_S = 10.0
MAX_EVENTS = 5


class _Tree(DirectoryTree):
    def filter_paths(self, paths):
        return [p for p in paths if p.name not in shelves.SKIP_DIRS and not p.name.startswith(".")]


class FilesView(TypedView):
    TYPE = "forest"
    opener = None                       # tests catch the "open in the OS" call here

    def __init__(self, *a, **kw) -> None:
        super().__init__(*a, **kw)
        self.changed: dict[str, str] = {}
        self.picked = ""
        self.error = ""
        self._seen: dict | None = None

    @property
    def rel(self) -> str:
        return str(self.config.get("path") or ".")

    @property
    def root(self) -> Path:
        return shelves.inside(self._get_repo_root(), self.rel)

    def compose_body(self) -> ComposeResult:
        yield Static("", id="ft-head", classes="typed-head")
        with Horizontal(classes="typed-row"):
            try:
                root = self.root
            except ValueError:
                root = self._get_repo_root()
            yield _Tree(str(root), id="ft-tree", classes="typed-list")
            with VerticalScroll(classes="typed-detail"):
                yield Static("", id="ft-preview", markup=False, classes="-as-written")

    def on_mount(self) -> None:
        self.refresh_data()
        self.set_interval(REFRESH_S, self.refresh_data)

    def refresh_data(self) -> None:
        repo = self._get_repo_root()
        try:
            self.changed, self.error = shelves.changed_files(repo, self.rel), ""
        except (RuntimeError, OSError, ValueError, subprocess.SubprocessError) as e:
            self.changed, self.error = {}, str(e)[:200]
        self._seen, fresh = shelves.file_changes(self._seen, repo, self.changed)
        for path in fresh[:MAX_EVENTS]:
            self.emit("files.changed", path, path)
        try:
            self.query_one("#ft-head", Static).update(
                Text(f"⚠ {self.error}", style="yellow") if self.error else
                Text(f"{self.rel} · {len(self.changed)} changed · ↗ opens it in the OS", style="dim"))
        except Exception:
            pass

    def on_directory_tree_file_selected(self, event: DirectoryTree.FileSelected) -> None:
        event.stop()
        self.show(Path(event.path))
        self.pick(Path(event.path))

    def on_directory_tree_directory_selected(self, event: DirectoryTree.DirectorySelected) -> None:
        event.stop()
        self.pick(Path(event.path))

    def pick(self, path: Path) -> None:
        """Enter on a file or folder: it is the target — `files.selected` with its path."""
        rel = shelves.rel_to(self._get_repo_root(), path)
        self.picked = rel
        self.emit("files.selected", rel, path.name)

    def on_tree_node_highlighted(self, event) -> None:
        node = getattr(event, "node", None)
        data = getattr(node, "data", None)
        path = getattr(data, "path", None)
        if path is not None and Path(path).is_file():
            self.show(Path(path))

    def show(self, path: Path) -> None:
        rel = shelves.rel_to(self._get_repo_root(), path)
        status = self.changed.get(rel, "")
        head = Text(f"{rel}{'  [' + status.strip() + ']' if status else ''}\n\n", style="bold")
        try:
            self.query_one("#ft-preview", Static).update(head + Text(shelves.preview(path)))
        except Exception:
            pass

    # -- the hut ----------------------------------------------------------------------------------

    def mini_status(self) -> list[str]:
        if self.error:
            return [f"⚠ {self.error[:40]}"]
        try:
            top = shelves.top_entries(self.root, 5)
        except ValueError as e:
            return [f"⚠ {e}"]
        lines = [f"{len(self.changed)} changed" if self.changed else "nothing changed"]
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
        lines = [f"./{self.rel}".rstrip("/.") or "."] + tree
        lines += [""] * (5 - len(lines))
        lines.append(f"changed: {len(self.changed)} files" if self.changed else "changed: nothing")
        lines.append(f"🎯 {self.picked.rsplit('/', 1)[-1]}" if self.picked else "")
        return lines

    def quick_action(self, action_id: str) -> bool:
        if action_id != "files.open":
            return False
        cmd = ["open" if sys.platform == "darwin" else "xdg-open", str(self.root)]
        opener = type(self).opener
        try:
            (opener or (lambda c: subprocess.Popen(c, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                                   start_new_session=True)))(cmd)
        except OSError as e:
            self.app.notify(f"{cmd[0]}: {e}", title="🗂 File Tree", severity="error")
        return True
