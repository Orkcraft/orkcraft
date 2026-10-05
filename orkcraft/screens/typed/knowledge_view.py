"""🗑️ Scroll Dump: one LLM wiki, kept by its librarian orc from read-only sources (realm/wiki.py).

`topic` is what the wiki is about (`general`, `codebase`, `team`, `design`: the sections and
rules it starts with); `wiki` its folder (default `llm-wiki/<topic>/`); `sources` (and the older
`paths`) what it is drawn from: folders of notes, folders of code, a git revision, a Confluence
space (sources/lore.py). A project may have several: one Scroll Dump per wiki.

The open building shows the wiki's pages and the sources, each source with what the wiki has not
taken in yet (● new or changed); 🔒 marks the pages people own. Ingest runs by itself once the
sources have settled for `SETTLE_S` (`auto_ingest`, default on; `$ORKCRAFT_WIKI_AUTO=0` turns it off
everywhere), a module at a time; `i` ingests now, `l` lints, `x` stops the librarian, `+`
connects a folder. After each ingest the wiki is committed (`commit`, default on), the pages
people own are put back if the librarian touched them, and `review_sample` of the pages it wrote
are spot-checked: by the Clan Fire named in `council` (its members review the sample, its steward
approves it or sends it back; the review shows in the Clan Fire, the report lands in reviews.md — no
road needed, so no loop),
else sent out as `wiki.review` for whatever is on that road. A cart of a task goes on as `knowledge.chunks` with the wiki's map.

The librarian's work — the sources, the wiki, the ingests and the spot-checks — is the
building's worker's (core/workers/scrolls.py). The view draws the tree and the page and holds the
keys and the timer.
"""
from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import Markdown, Static, Tree

from orkcraft.core.workers.scrolls import ScrollsWorker
from orkcraft.realm import jobs, shelves, wiki
from orkcraft.screens.dialogs import TextPrompt
from orkcraft.screens.typed.base import TypedView
from orkcraft.sources import lore

REFRESH_S = 30.0


class KnowledgeView(TypedView):
    TYPE = "scrolls"
    UI_PANES = {"head": "#kb-head", "tree": "#kb-tree", "page": "#kb-page"}
    BINDINGS = [Binding("i", "ingest", "Ingest"), Binding("l", "lint", "Lint"), Binding("x", "stop", "Stop")]

    @property
    def worker(self) -> ScrollsWorker:
        return super().worker

    # -- the worker's state, as the view's own (tests and other views read these) -------------------

    @property
    def bases(self) -> list[shelves.Base]:
        return self.worker.bases

    @property
    def pages(self) -> list[shelves.Note]:
        return self.worker.pages

    @property
    def pending(self) -> wiki.Pending:
        return self.worker.pending

    @property
    def running(self) -> str:
        return self.worker.running

    @property
    def reviewing(self) -> bool:
        return self.worker.reviewing

    @property
    def last_error(self) -> str:
        return self.worker.last_error

    @last_error.setter
    def last_error(self, value: str) -> None:
        self.worker.last_error = value

    @property
    def last_note(self) -> str:
        return self.worker.last_note

    @property
    def manual(self) -> set[str]:
        return self.worker.manual

    @property
    def _fingerprints(self) -> dict[str, str]:
        return self.worker._fingerprints

    @property
    def paths(self) -> list[str]:
        return self.worker.paths

    @property
    def library(self) -> lore.Library:
        return self.worker.library

    @property
    def topic(self) -> str:
        return self.worker.topic

    @property
    def wiki_root(self):
        return self.worker.wiki_root

    @property
    def log(self) -> jobs.Log:
        return self.worker.log

    @property
    def auto(self) -> bool:
        return self.worker.auto

    def source_notes(self) -> list[shelves.Note]:
        return self.worker.source_notes()

    def ingest(self, trigger: str = "manual") -> bool:
        return self.worker.ingest(trigger)

    def lint(self, trigger: str = "manual") -> bool:
        return self.worker.lint(trigger)

    def halt(self) -> int:
        """🛑 Halt All (and leaving): the librarian and a spot-check stop."""
        return self.worker.halt()

    def receive(self, payload, title: str, markdown: str) -> None:
        self.worker.receive(payload, title, markdown)

    def status(self) -> str:
        return self.worker.status()

    # -- the view -----------------------------------------------------------------------------------

    def compose_body(self) -> ComposeResult:
        yield Static("", id="kb-head", classes="typed-head")
        with Horizontal(classes="typed-row"):
            yield Tree("Wiki", id="kb-tree", classes="typed-list")
            with VerticalScroll(classes="typed-detail", id="kb-page"):
                yield Markdown("", id="kb-note")

    def on_mount(self) -> None:
        self.refresh_data()
        self.set_interval(REFRESH_S, self.refresh_data)

    def on_unmount(self) -> None:
        w = self.worker
        if w is not None:
            w.halt()

    def refresh_data(self) -> None:
        """A look at the sources and the wiki; the worker redraws the tree."""
        self.worker.refresh()

    def redraw(self) -> None:
        self._render_list()

    def _render_list(self) -> None:
        try:
            head, tree = self.query_one("#kb-head", Static), self.query_one("#kb-tree", Tree)
        except Exception:
            return
        w = self.worker
        pages = wiki.page_count(w.pages)
        state = (f"{w.running}…" if w.running else f"⚠ {w.last_error}" if w.last_error
                 else f"{w.pending.count} to take in" + (" (auto)" if w.auto else " · i ingests")
                 if w.pending else "up to date")
        head.update(Text(f"{w.topic} · {pages} page{'s' if pages != 1 else ''} · {len(w.bases)} source"
                         f"{'s' if len(w.bases) != 1 else ''} · {state} · l lints · x stops · + adds a folder",
                         style="dim"))
        opened = {n.data for n in tree.root.children if n.is_expanded}
        tree.clear()
        tree.root.expand()
        root = w.wiki_root
        rel = shelves.rel_to(w.repo_root, root)
        top = tree.root.add(Text.assemble(("📜 " + rel, "bold"), (f"  {pages}", "dim")), data="wiki",
                            expand="wiki" in opened or not opened)
        if not w.pages:
            top.add_leaf(Text("no wiki yet — the first ingest makes it", style="dim"))
        for n in w.pages:
            inner = n.path[len(rel) + 1:] if n.path.startswith(rel + "/") else n.path
            depth = max(inner.count("/") - 1, 0) if inner.startswith(wiki.PAGES + "/") else 0
            mark = "🔒 " if inner in w.manual else ""
            top.add_leaf(Text("  " * depth + mark + n.title, no_wrap=True), data=f"page:{n.path}")
        fresh = set(w.pending.new) | set(w.pending.changed)
        for b in w.bases:
            todo = sum(1 for n in b.notes if n.path in fresh)
            label = Text.assemble((f"{lore.ICONS.get(b.kind, '📁')} {b.path}", "bold"), (f"  {len(b.notes)}", "dim"))
            if todo:
                label.append(f"  ● {todo}", style="yellow")
            if b.error:
                label.append(f"  ⚠ {b.error}", style="yellow")
            node = tree.root.add(label, data=b.path, expand=b.path in opened)
            for n in b.notes:
                title = Text(("● " if n.path in fresh else "") + ("🧩 " if n.kind == "code" else "") + n.title,
                             no_wrap=True)
                node.add_leaf(title, data=f"note:{n.path}")

    def on_tree_node_highlighted(self, event: Tree.NodeHighlighted) -> None:
        data = event.node.data
        if isinstance(data, str) and data.startswith(("note:", "page:")):
            event.stop()
            self.read(data[5:], page=data.startswith("page:"))

    def read(self, rel: str, page: bool = False) -> None:
        try:
            self.query_one("#kb-note", Markdown).update(self.worker.read(rel, page))
        except Exception:
            pass

    def action_ingest(self) -> None:
        self.ingest()

    def action_lint(self) -> None:
        self.lint()

    def action_stop(self) -> None:
        self.worker.stop()

    # -- the hut ----------------------------------------------------------------------------------

    def mini_status(self) -> list[str]:
        return self.worker.mini_status()

    def hut_lines(self, widths: list[int]) -> list[str]:
        return self.worker.hut_lines(widths)

    def quick_action(self, action_id: str) -> bool:
        if action_id == "wiki.ingest":
            self.ingest()
            return True
        if action_id == "wiki.lint":
            self.lint()
            return True
        if action_id != "knowledge.add":
            return False

        def done(path: str | None) -> None:
            problem = self.worker.add_folder(path) if path else ""
            if problem:
                self.app.notify(problem, title="📚 Not added", severity="error")

        self.app.push_screen(TextPrompt("📚 Connect a folder of notes", placeholder="docs/handbook",
                                        help="a folder in the project"), done)
        return True
