"""🗑️ Scroll Dump: the project's knowledge from many sources, read-only.

`sources` (and the older `paths`) lists where it reads: folders of notes, folders of code, a git
revision, a Confluence space (see sources/lore.py; default: `docs/`, `notes/`, `wiki/`… whichever
the project has, else the whole project). The open building shows sources → documents → headings;
selecting one reads it. `+` connects one more folder. A document added or changed between two
looks (every 30 s) sends `knowledge.changed` with its path. `/` (or a cart) asks: notes answer by
BM25, code by the code graph (realm/codegraph.py), and the fragments go out as `knowledge.chunks`.
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
from orkcraft.sources import lore

REFRESH_S = 30.0


class KnowledgeView(TypedView):
    TYPE = "scrolls"
    BINDINGS = [Binding("slash", "ask", "Find fragments")]

    def __init__(self, *a, **kw) -> None:
        super().__init__(*a, **kw)
        self.bases: list[shelves.Base] = []
        self.last_query = ""
        self._mtimes: dict[str, str | float] | None = None
        self._library: lore.Library | None = None
        self._library_key: tuple = ()

    @property
    def paths(self) -> list[str]:
        return [s.spec for s in self.library.sources]

    @property
    def library(self) -> lore.Library:
        """The sources, made again only when the config changes (a remote one keeps its fetch state)."""
        key = (tuple(self.config.get("sources") or ()), tuple(self.config.get("paths") or ()))
        if self._library is None or key != self._library_key:
            self._library = lore.Library(lore.from_config(self.config, self._get_repo_root()))
            self._library_key = key
        return self._library

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
        self.bases = self.library.scan()
        for path in shelves.note_changes(self._mtimes, self.bases):
            self.emit("knowledge.changed", path, path)
        self._mtimes = {n.path: n.stamp for b in self.bases for n in b.notes}
        self._render_list()

    def _render_list(self) -> None:
        try:
            head, tree = self.query_one("#kb-head", Static), self.query_one("#kb-tree", Tree)
        except Exception:
            return
        total = sum(len(b.notes) for b in self.bases)
        head.update(Text(f"{len(self.bases)} source{'s' if len(self.bases) != 1 else ''} · {total} scrolls · "
                         "/ asks · + adds a folder", style="dim"))
        open_bases = {n.data for n in tree.root.children if n.is_expanded}
        tree.clear()
        tree.root.expand()
        for b in self.bases:
            label = Text.assemble((f"{lore.ICONS.get(b.kind, '📁')} {b.path}", "bold"), (f"  {len(b.notes)}", "dim"))
            if b.error:
                label.append(f"  ⚠ {b.error}", style="yellow")
            node = tree.root.add(label, data=b.path, expand=b.path in open_bases or len(self.bases) == 1)
            for n in b.notes:
                title = ("🧩 " if n.kind == "code" else "") + n.title
                note = node.add(Text(title, no_wrap=True), data=f"note:{n.path}")
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
        if not self.bases:
            self.bases = self.library.scan()
        found = self.library.search(self._get_repo_root(), query)
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
            text = self.library.read(rel)
        except ValueError as e:
            text = f"_{e}_"
        if lore.kind_of(rel) == "code":
            text = f"```{rel.rpartition('.')[2]}\n{text[:60000]}\n```"
        try:
            self.query_one("#kb-note", Markdown).update(text[:60000])
        except Exception:
            pass

    # -- the hut ----------------------------------------------------------------------------------

    def mini_status(self) -> list[str]:
        if not self.bases:
            return ["no sources yet"]
        lines = [f"{len(b.notes)} {b.path}" + (" ⚠" if b.error else "") for b in self.bases[:3]]
        if len(self.bases) > 3:
            lines.append(f"+{len(self.bases) - 3} more")
        return lines

    def hut_lines(self, widths: list[int]) -> list[str]:
        if not self.bases:
            return ["no sources yet"]
        notes = [n for b in self.bases for n in b.notes]
        code = sum(1 for n in notes if n.kind == "code")
        lines = [f"sources: {len(self.bases)}", f"notes: {len(notes) - code:,}"] + ([f"code: {code:,}"] if code else [])
        lines += [f"{len(b.notes)} {b.path}" + (" ⚠" if b.error else "") for b in self.bases[:3]]
        errors = [b.error for b in self.bases if b.error]
        lines.append("status: " + ("FETCHING" if errors and all(e == lore.FETCHING for e in errors)
                                   else "ERROR" if errors else "SYNCED"))
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
            if self.config.get("sources"):
                self.save_config({"sources": list(dict.fromkeys([*self.config["sources"], rel]))})
            else:
                self.save_config({"paths": list(dict.fromkeys([*(self.config.get("paths") or self.paths), rel]))})
            self.refresh_data()

        self.app.push_screen(TextPrompt("📚 Connect a folder of notes", placeholder="docs/handbook",
                                        help="a folder in the project"), done)
        return True
