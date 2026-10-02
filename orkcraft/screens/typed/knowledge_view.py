"""📚 Knowledge Base: folders of notes, each note with its headings.

`paths` lists the bases (default: `docs/`, `notes/`, `wiki/`… whichever the project has, else the
whole project). The open building shows bases → notes → headings; selecting a note reads it.
`+` connects one more folder. A note added or changed between two looks (every 30 s) sends
`knowledge.changed` with its path.
"""
from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import Markdown, Static, Tree

from orkcraft.realm import shelves
from orkcraft.screens.dialogs import TextPrompt
from orkcraft.screens.typed.base import TypedView

REFRESH_S = 30.0


class KnowledgeView(TypedView):
    TYPE = "scrolls"
    BINDINGS = [Binding("slash", "ask", "Find fragments")]

    def __init__(self, *a, **kw) -> None:
        super().__init__(*a, **kw)
        self.bases: list[shelves.Base] = []
        self.last_query = ""
        self._mtimes: dict[str, float] | None = None

    @property
    def paths(self) -> list[str]:
        configured = [str(p) for p in (self.config.get("paths") or []) if str(p).strip()]
        return configured or shelves.default_bases(self._get_repo_root())

    def compose_body(self) -> ComposeResult:
        yield Static("", id="kb-head", classes="typed-head")
        with Horizontal(classes="typed-row"):
            yield Tree("Knowledge", id="kb-tree", classes="typed-list")
            with VerticalScroll(classes="typed-detail"):
                yield Markdown("", id="kb-note")

    def on_mount(self) -> None:
        self.refresh_data()
        self.set_interval(REFRESH_S, self.refresh_data)

    def refresh_data(self) -> None:
        repo = self._get_repo_root()
        self.bases = [shelves.scan_base(repo, p) for p in self.paths]
        for path in shelves.note_changes(self._mtimes, self.bases):
            self.emit("knowledge.changed", path, path)
        self._mtimes = {n.path: n.mtime for b in self.bases for n in b.notes}
        self._render_list()

    def _render_list(self) -> None:
        try:
            head, tree = self.query_one("#kb-head", Static), self.query_one("#kb-tree", Tree)
        except Exception:
            return
        total = sum(len(b.notes) for b in self.bases)
        head.update(Text(f"{len(self.bases)} base{'s' if len(self.bases) != 1 else ''} · {total} notes · + adds a base",
                         style="dim"))
        open_bases = {n.data for n in tree.root.children if n.is_expanded}
        tree.clear()
        tree.root.expand()
        for b in self.bases:
            label = Text.assemble((f"📁 {b.path}", "bold"), (f"  {len(b.notes)}", "dim"))
            if b.error:
                label.append(f"  ⚠ {b.error}", style="yellow")
            node = tree.root.add(label, data=b.path, expand=b.path in open_bases or len(self.bases) == 1)
            for n in b.notes:
                note = node.add(Text(n.title, no_wrap=True), data=f"note:{n.path}")
                for h in n.headings:
                    note.add_leaf(Text(f"§ {h}", style="dim"), data=f"note:{n.path}")

    def on_tree_node_highlighted(self, event: Tree.NodeHighlighted) -> None:
        data = event.node.data
        if isinstance(data, str) and data.startswith("note:"):
            event.stop()
            self.read(data[5:])

    # -- fragments (the Scroll Scrapper, T1107) -------------------------------------------------------

    def find(self, query: str) -> str:
        """The fragments that answer `query`: shown here and sent as `knowledge.chunks`."""
        found = shelves.search(self._get_repo_root(), self.bases or [shelves.scan_base(self._get_repo_root(), p)
                                                                     for p in self.paths], query)
        md = shelves.fragments_markdown(query, found)
        self.last_query = query
        try:
            self.query_one("#kb-note", Markdown).update(f"**🔎 {query}** — {len(found)} fragment"
                                                         f"{'s' if len(found) != 1 else ''}\n\n{md}")
        except Exception:
            pass
        if found:
            self.emit("knowledge.chunks", md, query[:80])
        return md

    def receive(self, payload, title: str, markdown: str) -> None:
        """A cart is a question: its title and text are the query."""
        self.find(f"{payload.title} {payload.value}"[:500])

    def action_ask(self) -> None:
        self.app.push_screen(TextPrompt("🗑️ What do you need from the scrolls?", placeholder="release checklist"),
                             lambda q: self.find(q) if q else None)

    def read(self, rel: str) -> None:
        try:
            text = shelves.inside(self._get_repo_root(), rel).read_text(encoding="utf-8", errors="replace")
        except (OSError, ValueError) as e:
            text = f"_{e}_"
        try:
            self.query_one("#kb-note", Markdown).update(text[:60000])
        except Exception:
            pass

    # -- the hut ----------------------------------------------------------------------------------

    def mini_status(self) -> list[str]:
        if not self.bases:
            return ["no bases yet"]
        lines = [f"{len(b.notes)} {b.path}" + (" ⚠" if b.error else "") for b in self.bases[:3]]
        if len(self.bases) > 3:
            lines.append(f"+{len(self.bases) - 3} more")
        return lines

    def hut_lines(self, widths: list[int]) -> list[str]:
        if not self.bases:
            return ["no bases yet"]
        notes = sum(len(b.notes) for b in self.bases)
        lines = [f"bases: {len(self.bases)}", f"notes: {notes:,}"]
        lines += [f"{len(b.notes)} {b.path}" + (" ⚠" if b.error else "") for b in self.bases[:3]]
        lines.append("status: " + ("ERROR" if any(b.error for b in self.bases) else "SYNCED"))
        return lines

    def quick_action(self, action_id: str) -> bool:
        if action_id != "knowledge.add":
            return False

        def done(path: str | None) -> None:
            if not path:
                return
            try:
                folder = shelves.inside(self._get_repo_root(), path)
            except ValueError as e:
                self.app.notify(str(e), title="📚 Not added", severity="error")
                return
            if not folder.is_dir():
                self.app.notify(f"{path}: no such folder", title="📚 Not added", severity="error")
                return
            rel = shelves.rel_to(self._get_repo_root(), folder)
            paths = list(dict.fromkeys([*(self.config.get("paths") or self.paths), rel]))
            self.save_config({"paths": paths})
            self.refresh_data()

        self.app.push_screen(TextPrompt("📚 Connect a folder of notes", placeholder="docs/handbook",
                                        help="a folder in the project"), done)
        return True
