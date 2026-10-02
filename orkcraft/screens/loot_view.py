"""📦 Artifacts — generated artifacts (./loot/) and the project's docs (./docs/)."""
from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Container, Vertical
from textual.widget import Widget
from textual.widgets import DirectoryTree, Static

LOOT_DIR = "loot"
WIKI_DIR = "docs"


class LootView(Container):
    DEFAULT_CSS = """
    LootView { height: 100%; width: 100%; layout: vertical; }
    LootView .loot-title { height: 1; padding: 0 1; text-style: bold; background: $surface; }
    LootView .loot-empty { padding: 0 2; color: $text-muted; }
    LootView DirectoryTree { height: 1fr; background: transparent; }
    """

    def __init__(self, *children: Widget, name: str | None = None, id: str | None = None,
                 classes: str | None = None, disabled: bool = False) -> None:
        super().__init__(*children, name=name, id=id, classes=classes, disabled=disabled)

    def compose(self) -> ComposeResult:
        root = self.app.repo_root  # type: ignore[attr-defined]
        for label, rel, empty in (
            ("🪙 ./loot/ — generated artifacts", LOOT_DIR, "empty — agents drop their artifacts here"),
            ("📚 Docs — ./docs/", WIKI_DIR, "no docs folder yet"),
        ):
            with Vertical():
                yield Static(label, classes="loot-title")
                path = root / rel
                if path.is_dir() and any(path.iterdir()):
                    yield DirectoryTree(str(path))
                else:
                    yield Static(Text(empty, style="dim italic"), classes="loot-empty")

    def mini_status(self) -> list[str]:
        """Hut lines: artifacts and wiki notes on disk."""
        root = self.app.repo_root  # type: ignore[attr-defined]
        count = lambda rel: sum(1 for p in (root / rel).rglob("*") if p.is_file()) if (root / rel).is_dir() else 0
        return [f"🪙 {count(LOOT_DIR)} artifacts", f"📚 {count(WIKI_DIR)} wiki notes"]

    def refresh_view(self) -> None:
        for tree in self.query(DirectoryTree):
            tree.reload()
