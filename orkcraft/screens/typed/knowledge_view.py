"""🗑️ Scroll Dump: the project's LLM wiki, kept by its orc from read-only sources (realm/wiki.py).

`sources` (and the older `paths`) lists what the wiki is drawn from: folders of notes, folders of
code, a git revision, a Confluence space (sources/lore.py; default: `docs/`, `notes/`, `wiki/`…
whichever the project has). `wiki` is the wiki's folder (default `llm-wiki/`).

The open building shows the wiki's pages and the sources, each source with what the wiki has not
taken in yet (● new or changed); selecting one reads it. `i` ingests (the orc updates the pages,
the index and the log), `l` lints, `+` connects a folder. With `auto_ingest` an ingest starts by
itself when sources change. A cart is a task: it goes on as `knowledge.chunks` with the wiki's
index and where the wiki is — the agent downstream reads the pages it needs with its own tools.
"""
from __future__ import annotations

import os
import threading
import time
import uuid
from pathlib import Path

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import Markdown, Static, Tree

from orkcraft.realm import jobs, roads, shelves, wiki
from orkcraft.screens.dialogs import TextPrompt
from orkcraft.screens.typed.base import TypedView
from orkcraft.sources import lore

REFRESH_S = 30.0


def _simulated_work(harness, prompt, workdir, cancel, model, env, resume):
    """The sandbox: the librarian 'works' for a moment and says what it would have done."""
    if cancel.wait(1.0):
        raise InterruptedError("stopped")
    return "_(demo — simulated)_ the librarian would have updated the wiki.", None, None, ""


class KnowledgeView(TypedView):
    TYPE = "scrolls"
    work_runner = None            # tests swap the agent call (jobs.run_work) here
    BINDINGS = [Binding("i", "ingest", "Ingest"), Binding("l", "lint", "Lint")]

    def __init__(self, *a, **kw) -> None:
        super().__init__(*a, **kw)
        self.bases: list[shelves.Base] = []
        self.pages: list[shelves.Note] = []
        self.pending = wiki.Pending()
        self.running = ""                        # "" | ingest | lint
        self.last_error = ""
        self._mtimes: dict[str, str | float] | None = None
        self._library: lore.Library | None = None
        self._library_key: tuple = ()
        self._cancel: threading.Event | None = None

    # -- what it reads and where it writes ----------------------------------------------------------

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

    @property
    def wiki_root(self) -> Path:
        return wiki.root_of(self._get_repo_root(), self.config.get("wiki"))

    @property
    def log(self) -> jobs.Log:
        return jobs.Log(self.state_dir)

    def source_notes(self) -> list[shelves.Note]:
        """Every document of the sources, but the wiki's own files (a source of `.` holds them too)."""
        inside = shelves.rel_to(self._get_repo_root(), self.wiki_root).rstrip("/") + "/"
        return [n for b in self.bases for n in b.notes if not n.path.startswith(inside)]

    # -- the view -----------------------------------------------------------------------------------

    def compose_body(self) -> ComposeResult:
        yield Static("", id="kb-head", classes="typed-head")
        with Horizontal(classes="typed-row"):
            yield Tree("Wiki", id="kb-tree", classes="typed-list")
            with VerticalScroll(classes="typed-detail"):
                yield Markdown("", id="kb-note")

    def on_mount(self) -> None:
        self.refresh_data()
        self.set_interval(REFRESH_S, self.refresh_data)

    def refresh_data(self) -> None:
        repo = self._get_repo_root()
        self.bases = self.library.scan()
        try:
            root = self.wiki_root
            self.pages = wiki.pages(root, repo)
            manifest = wiki.load_manifest(root)
        except ValueError as e:                               # a wiki folder outside the project
            self.pages, manifest, self.last_error = [], {}, str(e)
        sources = self.source_notes()
        self.pending = wiki.pending(manifest, sources)
        now = sources + self.pages
        for path in shelves.note_changes(self._mtimes, [shelves.Base("", now)]):
            self.emit("knowledge.changed", path, path)
        self._mtimes = {n.path: n.stamp for n in now}
        self._render_list()
        if self.pending and not self.running and self.config.get("auto_ingest") and not self.last_error:
            self.ingest("auto")

    def _render_list(self) -> None:
        try:
            head, tree = self.query_one("#kb-head", Static), self.query_one("#kb-tree", Tree)
        except Exception:
            return
        pages = wiki.page_count(self.pages)
        state = (f"{self.running}…" if self.running else f"⚠ {self.last_error}" if self.last_error
                 else f"{self.pending.count} to take in · i ingests" if self.pending else "up to date")
        head.update(Text(f"{pages} page{'s' if pages != 1 else ''} · {len(self.bases)} source"
                         f"{'s' if len(self.bases) != 1 else ''} · {state} · l lints · + adds a folder", style="dim"))
        opened = {n.data for n in tree.root.children if n.is_expanded}
        tree.clear()
        tree.root.expand()
        rel = shelves.rel_to(self._get_repo_root(), self.wiki_root)
        top = tree.root.add(Text.assemble(("📜 " + rel, "bold"), (f"  {pages}", "dim")), data="wiki",
                            expand="wiki" in opened or not opened)
        if not self.pages:
            top.add_leaf(Text("no wiki yet — i takes the sources in", style="dim"))
        for n in self.pages:
            top.add_leaf(Text(n.title, no_wrap=True), data=f"page:{n.path}")
        fresh = set(self.pending.new) | set(self.pending.changed)
        for b in self.bases:
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
            if page:
                text = shelves.inside(self._get_repo_root(), rel).read_text(encoding="utf-8", errors="replace")
            else:
                text = self.library.read(rel)
        except (OSError, ValueError) as e:
            text = f"_{e}_"
        if not page and lore.kind_of(rel) == "code":
            text = f"```{rel.rpartition('.')[2]}\n{text[:60000]}\n```"
        try:
            self.query_one("#kb-note", Markdown).update(text[:60000])
        except Exception:
            pass

    # -- the orc's work -----------------------------------------------------------------------------

    def items(self) -> list[wiki.Item]:
        """The pending sources as the orc reads them: project files in place, the rest snapshotted."""
        root, repo = self.wiki_root, self._get_repo_root()
        by_path = {n.path: n for n in self.source_notes()}
        out = []
        for status, paths in (("new", self.pending.new), ("changed", self.pending.changed), ("gone", self.pending.gone)):
            for path in paths:
                if len(out) >= wiki.MAX_ITEMS:
                    return out
                note = by_path.get(path)
                if status == "gone" or note is None:
                    out.append(wiki.Item(path, "", "gone"))
                elif self.library.is_project_file(path):
                    out.append(wiki.Item(path, os.path.relpath(repo / path, root), status, note.title))
                else:
                    try:
                        text = self.library.read(path)
                    except ValueError:
                        continue                              # not readable now: it waits for the next ingest
                    out.append(wiki.Item(path, wiki.snapshot(root, path, text, note.title, note.url), status, note.title))
        return out

    def ingest(self, trigger: str = "manual") -> bool:
        if self.running:
            return False
        if not self.pending:
            self.app.notify("Nothing new in the sources.", title="📜 Wiki up to date")
            return False
        try:
            wiki.scaffold(self.wiki_root)
        except (OSError, ValueError) as e:
            self.last_error = str(e)
            self._render_list()
            return False
        items = self.items()
        if not items:
            return False
        stamps = {n.path: str(n.stamp) for n in self.source_notes()}

        def taken() -> None:
            manifest = wiki.load_manifest(self.wiki_root)
            for i in items:
                if i.status == "gone":
                    manifest.pop(i.source, None)
                else:
                    manifest[i.source] = stamps.get(i.source, "")
            wiki.save_manifest(self.wiki_root, manifest)

        return self._run("ingest", wiki.ingest_prompt(items), "\n".join(f"{i.status} {i.source}" for i in items),
                         trigger, taken)

    def lint(self, trigger: str = "manual") -> bool:
        if self.running:
            return False
        try:
            wiki.scaffold(self.wiki_root)
        except (OSError, ValueError) as e:
            self.last_error = str(e)
            self._render_list()
            return False
        return self._run("lint", wiki.lint_prompt(), "lint", trigger, None)

    def _run(self, what: str, prompt: str, summary: str, trigger: str, on_success) -> bool:
        harness = str(self.config.get("harness") or "claude")
        model = str(self.config.get("model") or "")
        job = jobs.Job(uuid.uuid4().hex[:8], f"{what}: {self.spec.get('title', self.building_id)}", harness,
                       summary, model, "librarian", started=jobs.now_iso(), outcome="running", trigger=trigger)
        self.running, self.last_error = what, ""
        self._cancel = cancel = threading.Event()
        runner = type(self).work_runner or (_simulated_work if self.simulated else jobs.run_work)
        workdir, app, started = self.wiki_root, self.app, time.time()
        env = {"ORKCRAFT_ORC": f"{self.building_id}/librarian"}
        self._render_list()

        def work() -> None:
            cost = None
            try:
                text, cost, _tokens, _session = runner(harness, prompt, workdir, cancel, model, env, "")
                job.result, job.outcome, job.cost_usd = text, "done", cost
            except InterruptedError:
                job.error, job.outcome = "stopped", "interrupted"
            except Exception as e:                            # the librarian's failure must not take the camp down
                job.error, job.outcome = str(e)[:300], "error"
            job.ended = jobs.now_iso()
            try:
                app.call_from_thread(self.finish, what, job, cost, started, on_success)
            except Exception:
                self.running = ""

        threading.Thread(target=work, daemon=True, name=f"wiki-{what}-{self.building_id}").start()
        return True

    def finish(self, what: str, job: jobs.Job, cost: float | None, started: float, on_success) -> None:
        self.running, self._cancel = "", None
        ok = job.outcome == "done"
        if ok and on_success is not None:
            try:
                on_success()
            except OSError as e:
                ok, job.error, job.outcome = False, f"manifest: {e}", "error"
        try:
            self.log.append(job)
        except OSError:
            pass
        on_run = getattr(self.app, "on_handler_run", None)
        if on_run is not None:
            on_run(roads.HandlerRun(self.building_id, "librarian", "agent", job.id, started, time.time(),
                                    outcome=job.outcome, markdown=job.result, error=job.error, cost_usd=cost))
        if ok:
            if what == "ingest":
                self.emit("wiki.updated", job.result, job.title)
            else:
                self.emit("wiki.linted", job.result, job.title)
        else:
            self.last_error = job.error
            self.app.notify(job.error, title=f"📜 The {what} failed", severity="error")
        self.refresh_data()

    def action_ingest(self) -> None:
        self.ingest()

    def action_lint(self) -> None:
        self.lint()

    # -- roads --------------------------------------------------------------------------------------

    def receive(self, payload, title: str, markdown: str) -> None:
        """A cart is a task: it goes on with the wiki's index, for the agent downstream to read from."""
        task = f"{payload.title} {payload.value}".strip()[:500]
        self.emit("knowledge.chunks", wiki.context(self.wiki_root, self._get_repo_root(), task), task[:80])

    # -- the hut ----------------------------------------------------------------------------------

    def status(self) -> str:
        if self.running:
            return "WORKING"
        if self.last_error or any(b.error and b.error != lore.FETCHING for b in self.bases):
            return "ERROR"
        if not self.pages:
            return "NO WIKI"
        return "PENDING" if self.pending else "FRESH"

    def mini_status(self) -> list[str]:
        lines = [f"{wiki.page_count(self.pages)} pages"]
        if self.pending:
            lines.append(f"● {self.pending.count} to take in")
        lines.append(self.status().lower())
        return lines

    def hut_lines(self, widths: list[int]) -> list[str]:
        notes = self.source_notes()
        lint = wiki.lint_problems(self.wiki_root) if self.pages else None
        lines = [f"pages: {wiki.page_count(self.pages):,}", f"sources: {len(self.bases)} · {len(notes):,}",
                 f"pending: {self.pending.count:,}"]
        if lint is not None:
            lines.append(f"lint: {lint}")
        lines.append("status: " + self.status())
        return lines

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
