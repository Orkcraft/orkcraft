"""🌲 File Forest: a folder of the project as a tree; Enter picks a target.

The hut shows the folder's top entries and how many files in it git sees changed; the open
building is the whole tree with a preview of the highlighted file. The work — what changed, the
target, `files.changed` / `files.selected`, ↗ — is the building's worker's (core/workers/forest.py);
the view draws it and holds the tree.
"""
from __future__ import annotations

from pathlib import Path

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import DirectoryTree, Static

from orkcraft.core.workers.forest import TITLE, ForestWorker
from orkcraft.realm import shelves
from orkcraft.screens.typed.base import TypedView

REFRESH_S = 10.0


class _Tree(DirectoryTree):
    def filter_paths(self, paths):
        return [p for p in paths if p.name not in shelves.SKIP_DIRS and not p.name.startswith(".")]


class FilesView(TypedView):
    TYPE = "forest"
    opener = None                       # tests catch the "open in the OS" call here

    @property
    def worker(self) -> ForestWorker:
        return super().worker

    # -- the worker's state, as the view's own (tests and other views read these) -------------------

    @property
    def changed(self) -> dict[str, str]:
        return self.worker.changes

    @property
    def picked(self) -> str:
        return self.worker.picked

    @property
    def error(self) -> str:
        return self.worker.error

    @property
    def rel(self) -> str:
        return self.worker.rel

    @property
    def root(self) -> Path:
        return self.worker.root

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
        """A look at git (the worker sends what changed and says so: `redraw`)."""
        self.worker.refresh()
        self.redraw()

    def redraw(self) -> None:
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
        self.worker.pick(path)

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
        return self.worker.mini_status()

    def hut_lines(self, widths: list[int]) -> list[str]:
        return self.worker.hut_lines(widths)

    def quick_action(self, action_id: str) -> bool:
        if action_id != "files.open":
            return False
        problem = self.worker.open_in_os(type(self).opener)
        if problem:
            self.app.notify(problem, title=TITLE, severity="error")
        return True
