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
"""
from __future__ import annotations

import os
import random
import threading
import time
import uuid
from pathlib import Path

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import Markdown, Static, Tree

from orkcraft.env import getenv
from orkcraft.realm import catalog, jobs, roads, shelves, wiki
from orkcraft.realm import team as tm
from orkcraft.screens.dialogs import TextPrompt
from orkcraft.screens.typed.base import TypedView
from orkcraft.sources import lore

REFRESH_S = 30.0
SETTLE_S = 25.0                 # the sources must stay as they are this long before an ingest starts by itself
REVIEW_SAMPLE = 2
REVIEW_CYCLES, REVIEW_BUDGET = 2, 1.0      # a spot-check is short, whatever the Clan Fire's own limits
REVIEW_BRIEF = ("This is a spot-check of wiki pages its librarian just wrote: approve when every page is fine, "
                "else send it back with what is wrong per page and how to fix it — short. Never ask the operator.")
VERDICT_EVENTS = ("team.artifact_ready", "team.approved", "team.rework")


def _simulated_work(harness, prompt, workdir, cancel, model, env, resume):
    """The sandbox: the librarian 'works' for a moment and says what it would have done."""
    if cancel.wait(1.0):
        raise InterruptedError("stopped")
    return "_(demo — simulated)_ the librarian would have updated the wiki.", None, None, ""


class KnowledgeView(TypedView):
    TYPE = "scrolls"
    UI_PANES = {"head": "#kb-head", "tree": "#kb-tree", "page": "#kb-page"}
    work_runner = None            # tests swap the agent call (jobs.run_work) here
    review_runner = None          # and the Council members' calls (realm/team.py Runner)
    BINDINGS = [Binding("i", "ingest", "Ingest"), Binding("l", "lint", "Lint"), Binding("x", "stop", "Stop")]

    def __init__(self, *a, **kw) -> None:
        super().__init__(*a, **kw)
        self.bases: list[shelves.Base] = []
        self.pages: list[shelves.Note] = []
        self.pending = wiki.Pending()
        self.running = ""                        # "" | ingest | lint
        self.last_error = ""
        self.last_note = ""                      # what the last run left to say (skipped, restored, outside writes)
        self.manual: set[str] = set()            # root-relative pages people own
        self._fingerprints: dict[str, str] = {}
        self._mtimes: dict[str, str] | None = None
        self._settled: tuple = ((), 0.0)          # (what was pending, since when)
        self._library: lore.Library | None = None
        self._library_key: tuple = ()
        self._prints: wiki.Fingerprints | None = None
        self._cancel: threading.Event | None = None
        self.reviewing = False

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
    def topic(self) -> str:
        return wiki.topic_of(self.config)

    @property
    def wiki_root(self) -> Path:
        return wiki.root_of(self._get_repo_root(), self.config.get("wiki"), self.topic)

    @property
    def log(self) -> jobs.Log:
        return jobs.Log(self.state_dir)

    @property
    def auto(self) -> bool:
        return self.config.get("auto_ingest", True) is not False and getenv("WIKI_AUTO", "1") != "0"

    def source_notes(self) -> list[shelves.Note]:
        """Every document of the sources but the wikis themselves (this one and any other)."""
        notes = [n for b in self.bases for n in b.notes]
        own = shelves.rel_to(self._get_repo_root(), self.wiki_root).rstrip("/")
        skip = tuple(f"{r}/" for r in {own, *wiki.wiki_roots(notes)} if r)
        return [n for n in notes if not n.path.startswith(skip)]

    def _unsure(self) -> callable:
        """A path whose source failed to answer this time: the wiki must not call it gone."""
        failed = [s for s, b in zip(self.library.sources, self.bases) if b.error]
        return lambda path: any(s.owns(path) for s in failed)

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
        self.halt()

    def halt(self) -> int:
        """🛑 Halt All (and leaving): the librarian and a spot-check stop."""
        n = 0
        for c in (self._cancel, getattr(self, "_review_cancel", None)):
            if c is not None and not c.is_set():
                c.set()
                n += 1
        return n

    def refresh_data(self) -> None:
        repo = self._get_repo_root()
        if self._prints is None:
            self._prints = wiki.Fingerprints(repo)
        self.bases = self.library.scan()
        try:
            root = self.wiki_root
            self.pages = wiki.pages(root, repo)
            manifest = wiki.load_manifest(root)
            self.manual = set(wiki.manual_pages(root))
        except ValueError as e:                               # a wiki folder outside the project
            self.pages, manifest, self.last_error = [], {}, str(e)
        sources = self.source_notes()
        self._fingerprints = {n.path: self._prints.of(n) for n in sources}
        self.pending = wiki.pending(manifest, self._fingerprints, self._unsure())
        now = {**self._fingerprints, **{n.path: str(n.mtime) for n in self.pages}}
        if self._mtimes is not None:
            for path, stamp in now.items():
                if self._mtimes.get(path) != stamp:
                    self.emit("knowledge.changed", path, path)
        self._mtimes = now
        self._render_list()
        key = (tuple(self.pending.new), tuple(self.pending.changed), tuple(self.pending.gone))
        if key != self._settled[0]:
            self._settled = (key, time.monotonic())
        settled = time.monotonic() - self._settled[1] >= SETTLE_S
        if self.pending and settled and self.auto and not self.running and not self.last_error:
            self.ingest("auto")

    def _render_list(self) -> None:
        try:
            head, tree = self.query_one("#kb-head", Static), self.query_one("#kb-tree", Tree)
        except Exception:
            return
        pages = wiki.page_count(self.pages)
        state = (f"{self.running}…" if self.running else f"⚠ {self.last_error}" if self.last_error
                 else f"{self.pending.count} to take in" + (" (auto)" if self.auto else " · i ingests")
                 if self.pending else "up to date")
        head.update(Text(f"{self.topic} · {pages} page{'s' if pages != 1 else ''} · {len(self.bases)} source"
                         f"{'s' if len(self.bases) != 1 else ''} · {state} · l lints · x stops · + adds a folder",
                         style="dim"))
        opened = {n.data for n in tree.root.children if n.is_expanded}
        tree.clear()
        tree.root.expand()
        root = self.wiki_root
        rel = shelves.rel_to(self._get_repo_root(), root)
        top = tree.root.add(Text.assemble(("📜 " + rel, "bold"), (f"  {pages}", "dim")), data="wiki",
                            expand="wiki" in opened or not opened)
        if not self.pages:
            top.add_leaf(Text("no wiki yet — the first ingest makes it", style="dim"))
        for n in self.pages:
            inner = n.path[len(rel) + 1:] if n.path.startswith(rel + "/") else n.path
            depth = max(inner.count("/") - 1, 0) if inner.startswith(wiki.PAGES + "/") else 0
            mark = "🔒 " if inner in self.manual else ""
            top.add_leaf(Text("  " * depth + mark + n.title, no_wrap=True), data=f"page:{n.path}")
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

    # -- the librarian's work -----------------------------------------------------------------------

    def items(self) -> tuple[list[wiki.Item], list[str]]:
        """The next batch as the librarian reads it (project files in place, the rest snapshotted),
        and the sources that could not be read now (they wait for the next ingest)."""
        root, repo = self.wiki_root, self._get_repo_root()
        by_path = {n.path: n for n in self.source_notes()}
        out, unreadable = [], []
        for status, path in wiki.take_batch(self.pending):
            note = by_path.get(path)
            if status == "gone" or note is None:
                out.append(wiki.Item(path, "", "gone"))
            elif self.library.is_project_file(path):
                out.append(wiki.Item(path, os.path.relpath(repo / path, root), status, note.title))
            else:
                try:
                    text = self.library.read(path)
                except ValueError:
                    unreadable.append(path)
                    continue
                out.append(wiki.Item(path, wiki.snapshot(root, path, text, note.title, note.url), status, note.title))
        return out, unreadable

    def ingest(self, trigger: str = "manual") -> bool:
        if self.running or self.out_of_gold("the ingest" if trigger == "manual" else ""):
            return False
        if not self.pending:
            if trigger == "manual":
                self.app.notify("Nothing new in the sources.", title="📜 Wiki up to date")
            return False
        if not self._prepare():
            return False
        items, unreadable = self.items()
        if unreadable:
            self.last_note = f"{len(unreadable)} source(s) unreadable now, left for later: {', '.join(unreadable[:3])}"
            self.app.notify(self.last_note, title="📜 Ingest", severity="warning")
        if not items:
            return False
        prints = dict(self._fingerprints)
        start = wiki.load_manifest(self.wiki_root)

        def taken() -> None:
            manifest = dict(start)                              # what the librarian may have written to it is ignored
            for i in items:
                if i.status == "gone":
                    manifest.pop(i.source, None)
                else:
                    manifest[i.source] = prints.get(i.source, "")
            wiki.save_manifest(self.wiki_root, manifest)

        message = f"wiki({self.topic}): take in {len(items)} source(s)"
        return self._run("ingest", wiki.ingest_prompt(items, sorted(self._protected())),
                         "\n".join(f"{i.status} {i.source}" for i in items), trigger, taken, message)

    def lint(self, trigger: str = "manual") -> bool:
        if self.running or self.out_of_gold("the lint" if trigger == "manual" else "") or not self._prepare():
            return False
        return self._run("lint", wiki.lint_prompt(sorted(self._protected())), "lint", trigger, None,
                         f"wiki({self.topic}): lint")

    def _prepare(self) -> bool:
        try:
            wiki.scaffold(self.wiki_root, self.topic)
            return True
        except (OSError, ValueError) as e:
            self.last_error = str(e)
            self._render_list()
            return False

    def _protected(self) -> set[str]:
        """The pages people own, and the ones with edits not yet committed (someone is at work)."""
        return set(wiki.manual_pages(self.wiki_root)) | wiki.uncommitted(self._get_repo_root(), self.wiki_root)

    def _run(self, what: str, prompt: str, summary: str, trigger: str, on_success, message: str) -> bool:
        harness = str(self.config.get("harness") or "claude")
        model = str(self.config.get("model") or "")
        root, repo = self.wiki_root, self._get_repo_root()
        job = jobs.Job(uuid.uuid4().hex[:8], f"{what}: {self.spec.get('title', self.building_id)}", harness,
                       summary, model, "librarian", started=jobs.now_iso(), outcome="running", trigger=trigger)
        protected = {rel: text for rel in self._protected()
                     if (text := _read(root / rel)) is not None}
        before = wiki.dirty(repo)
        self.running, self.last_error, self.last_note = what, "", ""
        self._cancel = cancel = threading.Event()
        runner = type(self).work_runner or (_simulated_work if self.simulated else jobs.run_work)
        app, started = self.app, time.time()
        env = {"ORKCRAFT_ORC": f"{self.building_id}/librarian"}
        self._render_list()

        def work() -> None:
            cost = None
            try:
                text, cost, _tokens, _session = runner(harness, prompt, root, cancel, model, env, "")
                job.result, job.outcome, job.cost_usd = text, "done", cost
            except InterruptedError:
                job.error, job.outcome = "stopped", "interrupted"
            except Exception as e:                            # the librarian's failure must not take the camp down
                job.error, job.outcome = str(e)[:300], "error"
            job.ended = jobs.now_iso()
            try:
                app.call_from_thread(self.finish, what, job, cost, started, on_success, protected, before, message)
            except Exception:
                self.running = ""

        threading.Thread(target=work, daemon=True, name=f"wiki-{what}-{self.building_id}").start()
        return True

    def finish(self, what: str, job: jobs.Job, cost: float | None, started: float, on_success,
               protected: dict[str, str] | None = None, before: dict | None = None, message: str = "") -> None:
        self.running, self._cancel = "", None
        root, repo = self.wiki_root, self._get_repo_root()
        notes = []
        put_back = wiki.restore(root, protected or {})
        if put_back:
            notes.append(f"put back {len(put_back)} page(s) people own: {', '.join(put_back[:3])}")
        outside = wiki.outside_changes(before or {}, repo, root)
        if outside:
            notes.append(f"files outside the wiki changed while it worked: {', '.join(outside[:3])}")
        ok = job.outcome == "done"
        if ok and on_success is not None:
            try:
                on_success()
            except OSError as e:
                ok, job.error, job.outcome = False, f"manifest: {e}", "error"
        sha = ""
        if ok and self.config.get("commit", True) is not False and not self.simulated:
            sha, why = wiki.commit(repo, root, message)
            if why:
                notes.append(f"not committed: {why}")
        if notes:
            self.last_note = "; ".join(notes)
            job.meta["notes"] = notes
            self.app.notify(self.last_note, title=f"📜 The {what}", severity="warning")
        if sha:
            job.meta["commit"] = sha
        try:
            self.log.append(job)
        except OSError:
            pass
        on_run = getattr(self.app, "on_handler_run", None)
        if on_run is not None:
            on_run(roads.HandlerRun(self.building_id, "librarian", "agent", job.id, started, time.time(),
                                    outcome=job.outcome, markdown=job.result, error=job.error, cost_usd=cost))
        if ok:
            self.emit("wiki.updated" if what == "ingest" else "wiki.linted", job.result, job.title)
            if what == "ingest" and sha:
                self.ask_review(sha)
        elif job.outcome != "interrupted":
            self.last_error = job.error
            self.app.notify(job.error, title=f"📜 The {what} failed", severity="error")
        self.refresh_data()

    def ask_review(self, sha: str) -> bool:
        """A sample of the pages an ingest wrote, spot-checked: by the Council named in `council`
        (its members, a short discussion, the verdict into reviews.md), else sent out as `wiki.review`."""
        n = int(self.config.get("review_sample", REVIEW_SAMPLE))
        touched = [p for p in wiki.touched_pages(self._get_repo_root(), self.wiki_root, sha) if p not in self.manual]
        if n <= 0 or not touched:
            return False
        sample = sorted(random.sample(touched, min(n, len(touched))))
        request, title = wiki.review_request(self.wiki_root, sample, self.topic), f"spot-check: {', '.join(sample)}"
        council = str(self.config.get("council") or "").strip()
        if council:
            return self.council_review(council, request, title)
        return self.emit("wiki.review", request, title)

    def council_review(self, council_id: str, request: str, title: str) -> bool:
        """The sample goes to the Clan Fire's members and its steward, as a document like any other;
        the review shows in the Clan Fire, and its report lands in reviews.md."""
        spec = (getattr(self.app, "custom_specs", {}) or {}).get(council_id)
        if not spec or catalog.migrate(spec).get("type") != "council":
            self.last_note = f"no Clan Fire {council_id!r} for the spot-check"
            return False
        if self.reviewing or getattr(self.app, "gold_exhausted", lambda: False)():
            return False
        from orkcraft.screens.typed.team_view import TeamView
        cfg = dict(spec.get("config") or {})
        team, veto = tm.members_of(cfg), tm.veto_of(cfg)
        budget = min(float(tm.DEFAULT_BUDGET if cfg.get("budget_usd") is None else cfg["budget_usd"]), REVIEW_BUDGET)
        repo, app = self._get_repo_root(), self.app
        self._review_cancel = cancel = threading.Event()
        state = repo / ".orkcraft" / "council" / council_id
        harness, _, model = str(cfg.get("moderator") or "claude").partition(":")
        steward = tm.Steward(f"{REVIEW_BRIEF} {str(cfg.get('steward_prompt') or '').strip()}".strip(),
                             harness.strip() or "claude", model.strip())

        def brief_of(m: tm.Member) -> tuple[str, str]:
            path = state / "roles" / f"{tm.slug(m.role)}.md"
            text = TeamView._knowledge(path)
            return (shelves.rel_to(repo, path), text) if text else ("", "")

        d = tm.new(title, request)
        env = {"ORKCRAFT_ORC": f"{council_id}/clan"}
        if type(self).review_runner is not None:
            runner = type(self).review_runner
        elif self.simulated:
            from orkcraft.screens.typed.team_view import _simulated as runner
        else:
            def runner(h, p, m):
                return roads.run_agent(h, p, repo, env, cancel, m, web=True)[:2]
        self.reviewing = True

        def work() -> None:
            try:
                tm.run(d, team, steward, veto, REVIEW_CYCLES, budget, runner, None, cancel, brief_of)
            except Exception as e:                            # a failed review must not take the camp down
                d.outcome, d.error = "error", str(e)[:300]
            if d.outcome == "asked":                          # a spot-check never waits for the operator
                d.outcome = "rework"
                d.ended = tm.now_iso()
            try:
                tm.save(state, d)
            except OSError:
                pass
            try:
                app.call_from_thread(self.reviewed, d, team, title)
            except Exception:
                self.reviewing = False

        threading.Thread(target=work, daemon=True, name=f"wiki-review-{self.building_id}").start()
        return True

    def reviewed(self, d: tm.Discussion, team: list, title: str) -> None:
        self.reviewing = False
        if d.outcome not in ("approved", "rework"):
            self.last_note = f"the spot-check failed: {d.error or d.outcome}"
            return
        self.record_verdict(tm.report_markdown(d, team), title)

    def record_verdict(self, verdict: str, title: str) -> None:
        try:
            wiki.record_review(self.wiki_root, verdict, title)
        except (OSError, ValueError):
            return
        if self.config.get("commit", True) is not False and not self.simulated:
            wiki.commit(self._get_repo_root(), self.wiki_root, f"wiki({self.topic}): the Council's review")
        self.refresh_data()

    def action_ingest(self) -> None:
        self.ingest()

    def action_lint(self) -> None:
        self.lint()

    def action_stop(self) -> None:
        if self._cancel is not None:
            self._cancel.set()

    # -- roads --------------------------------------------------------------------------------------

    def receive(self, payload, title: str, markdown: str) -> None:
        """The Council's verdict lands in reviews.md; any other cart is a task, sent on with the map."""
        if payload.mode in VERDICT_EVENTS:
            self.record_verdict(markdown or payload.value, payload.title or title)
            return
        task = f"{payload.title} {payload.value}".strip()[:500]
        self.emit("knowledge.chunks", wiki.context(self.wiki_root, self._get_repo_root(), task), task[:80],
                  trail=payload.trail, ref=payload.ref)

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
        lines = [f"{self.topic}: {wiki.page_count(self.pages):,} pages", f"sources: {len(self.bases)} · {len(notes):,}",
                 f"pending: {self.pending.count:,}"]
        if self.manual:
            lines.append(f"🔒 people's: {len(self.manual)}")
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


def _read(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return None
