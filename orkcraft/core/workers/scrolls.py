"""🗑️ Scroll Dump's work: the librarian ork that keeps one LLM wiki from read-only sources
(realm/wiki.py), and the spot-checks of what it wrote.

`refresh()` looks at the sources and the wiki: what changed goes out as `knowledge.changed`, and
a backlog that has settled for `SETTLE_S` is taken in by itself (`auto_ingest`). `ingest()` and
`lint()` run the librarian in a thread (`running` says which); `finish` puts back the pages
people own, commits the wiki, logs the job, sends `wiki.updated` / `wiki.linted` and asks for a
spot-check: by the Clan Fire named in `council`, else as `wiki.review`. `halt()` stops it all.
A cart of a verdict lands in reviews.md; any other cart is a task, sent on as `knowledge.chunks`
with the wiki's map and the pages that matter most for it (`lend`) — also when a Barracks that
reads it first (`notes`) hands it a task directly. What it lent last shows on its card for a while.
"""
from __future__ import annotations

import os
import random
import threading
import time
import uuid
from pathlib import Path

from orkcraft.core import delivery
from orkcraft.core.workers import Worker
from orkcraft.core.workers.scrolls_meetings import MeetingsMixin
from orkcraft.core.workers.scrolls_quality import QualityMixin
from orkcraft.env import getenv
from orkcraft.core import runners
from orkcraft.realm import agenda, catalog, daybook, jobs, quicknote, roads, shelves, wiki, wikifind
from orkcraft.realm import team as tm
from orkcraft.sources import lore

SETTLE_S = 25.0                 # the sources must stay as they are this long before an ingest starts by itself
REVIEW_SAMPLE = 2
LENT_PAGES = 3                  # the pages a task gets named first
REVIEW_CYCLES, REVIEW_BUDGET = 2, 1.0      # a spot-check is short, whatever the Clan Fire's own limits
REVIEW_BRIEF = ("This is a spot-check of wiki pages its librarian just wrote: approve when every page is fine, "
                "else send it back with what is wrong per page and how to fix it — short. Never ask the operator.")
VERDICT_EVENTS = ("team.artifact_ready", "team.approved", "team.rework")


def _simulated_work(harness, prompt, workdir, cancel, model, env, resume):
    """The sandbox: the librarian 'works' for a moment and says what it would have done."""
    if cancel.wait(1.0):
        raise InterruptedError("stopped")
    return "_(demo — simulated)_ the librarian would have updated the wiki.", None, None, ""


class ScrollsWorker(MeetingsMixin, QualityMixin, Worker):
    TYPE = "scrolls"
    work_runner = None            # tests swap the agent call (jobs.run_work) here
    review_runner = None          # and the Council members' calls (realm/team.py Runner)

    def __init__(self, town, building_id: str) -> None:
        super().__init__(town, building_id)
        self.bases: list[shelves.Base] = []
        self.pages: list[shelves.Note] = []
        self.pending = wiki.Pending()
        self.running = ""                        # "" | ingest | lint
        self.last_error = ""
        self.last_note = ""                      # what the last run left to say (skipped, restored, outside writes)
        self.manual: set[str] = set()            # root-relative pages people own
        self.reviewing = False
        self._fingerprints: dict[str, str] = {}
        self._mtimes: dict[str, str] | None = None
        self._settled: tuple = ((), 0.0)          # (what was pending, since when)
        self._library: lore.Library | None = None
        self._library_key: tuple = ()
        self._prints: wiki.Fingerprints | None = None
        self._cancel: threading.Event | None = None
        self._review_cancel: threading.Event | None = None
        self.lent: dict = {}                     # the last task it gave notes to: {task, pages, by, at}

    # -- what it reads and where it writes ------------------------------------------------------

    @property
    def paths(self) -> list[str]:
        return [s.spec for s in self.library.sources]

    @property
    def library(self) -> lore.Library:
        """The sources, made again only when the config changes (a remote one keeps its fetch state)."""
        key = (tuple(self.config.get("sources") or ()), tuple(self.config.get("paths") or ()))
        if self._library is None or key != self._library_key:
            self._library = lore.Library(lore.from_config(self.config, self.repo_root))
            self._library_key = key
        return self._library

    @property
    def topic(self) -> str:
        return wiki.topic_of(self.config)

    @property
    def wiki_root(self) -> Path:
        return wiki.root_of(self.repo_root, self.config.get("wiki"), self.topic)

    @property
    def log(self) -> jobs.Log:
        return jobs.Log(self.state_dir)

    @property
    def auto(self) -> bool:
        return self.config.get("auto_ingest", True) is not False and getenv("WIKI_AUTO", "1") != "0"

    def source_notes(self) -> list[shelves.Note]:
        """Every document of the sources but the wikis themselves (this one and any other)."""
        notes = [n for b in self.bases for n in b.notes]
        own = shelves.rel_to(self.repo_root, self.wiki_root).rstrip("/")
        skip = tuple(f"{r}/" for r in {own, *wiki.wiki_roots(notes)} if r)
        return [n for n in notes if not n.path.startswith(skip)]

    def _unsure(self) -> callable:
        """A path whose source failed to answer this time: the wiki must not call it gone."""
        failed = [s for s, b in zip(self.library.sources, self.bases) if b.error]
        return lambda path: any(s.owns(path) for s in failed)

    # -- its life -------------------------------------------------------------------------------

    def start(self) -> None:
        self.refresh()

    def halt(self) -> int:
        """🛑 Halt All (and leaving): the librarian and a spot-check stop."""
        n = 0
        for c in (self._cancel, self._review_cancel):
            if c is not None and not c.is_set():
                c.set()
                n += 1
        return n

    def stop(self) -> None:
        """Stop the librarian (a spot-check goes on)."""
        if self._cancel is not None:
            self._cancel.set()

    def refresh(self) -> None:
        """Look at the sources and the wiki again: what changed is sent, and a settled backlog is taken in."""
        repo = self.repo_root
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
        try:
            self.keep_agenda()
        except (OSError, ValueError) as e:                   # the meetings must not stop the wiki
            self.last_note = f"the meetings' pages: {e}"
        self.changed()
        key = (tuple(self.pending.new), tuple(self.pending.changed), tuple(self.pending.gone))
        if key != self._settled[0]:
            self._settled = (key, time.monotonic())
        settled = time.monotonic() - self._settled[1] >= SETTLE_S
        if self.pending and settled and self.auto and not self.running and not self.last_error:
            self.ingest("auto")
        try:
            self.keep_quality()                              # the scheduled quality check, when it is due
        except OSError:
            pass

    def read(self, rel: str, page: bool = False) -> str:
        """A page of the wiki or a document of the sources, as Markdown (code fenced)."""
        try:
            if page:
                text = shelves.inside(self.repo_root, rel).read_text(encoding="utf-8", errors="replace")
            else:
                text = self.library.read(rel)
        except (OSError, ValueError) as e:
            text = f"_{e}_"
        if not page and lore.kind_of(rel) == "code":
            text = f"```{rel.rpartition('.')[2]}\n{text[:60000]}\n```"
        return text[:60000]

    def add_folder(self, path: str) -> str:
        """Connect a folder of the project as a source. What is wrong with it, or ""."""
        try:
            folder = shelves.inside(self.repo_root, path)
        except ValueError as e:
            return str(e)
        if not folder.is_dir():
            return f"{path}: no such folder"
        rel = shelves.rel_to(self.repo_root, folder)
        if self.config.get("sources"):
            self.save_config({"sources": list(dict.fromkeys([*self.config["sources"], rel]))})
        else:
            self.save_config({"paths": list(dict.fromkeys([*(self.config.get("paths") or self.paths), rel]))})
        self.refresh()
        return ""

    # -- Quick note (docs/design/wiki-librarian.md §4) --------------------------------------------

    @property
    def inbox(self) -> str:
        """Where Quick notes are written: a source folder of this wiki."""
        return str(self.config.get("inbox") or quicknote.INBOX).strip().strip("/") or quicknote.INBOX

    def suggest(self, text: str) -> quicknote.Suggestion:
        """The section, tags and links a note should get here, and the meeting it is for (rules, no model)."""
        return quicknote.suggest(text, self.repo_root, self.pages, wiki.sections(self.wiki_root, self.topic),
                                 self.meetings(), self.clock())

    model_hint: dict = {}                       # the light model's word on the note typed last: {text, section, tags, people}
    _asking = False

    def ask_model(self, text: str, hint: quicknote.Suggestion) -> bool:
        """When the rules found nothing for a note, ask the light model once (off the town's thread); its word
        lands in `model_hint`. True when it was asked."""
        if self.config.get("suggest_model", True) is False or self._asking or self.model_hint.get("text") == text \
                or not wikifind.worth_asking(text, hint):
            return False
        runner = runners.FASTPATH_RUNNER
        if runner is None:
            if self.simulated or self.town.demo or not self.town.budget_ok():
                return False
            from orkcraft.realm import fastpath
            runner = fastpath.light_runner(self.repo_root)
        if runner is None:
            return False
        sections = wiki.sections(self.wiki_root, self.topic)
        people = list(agenda.people_of(self.repo_root, self.pages))
        prompt = wikifind.model_prompt(text, self.topic, sections, people)
        self._asking = True

        def work() -> None:
            try:
                answer = runner(prompt)[0]
            except Exception:  # a model that cannot be reached leaves the rules' word
                answer = ""
            try:
                self.town.call(self._model_answered, text, wikifind.parse_model(answer, sections, people))
            except Exception:
                self._asking = False

        threading.Thread(target=work, daemon=True, name=f"wiki-hint-{self.building_id}").start()
        return True

    def _model_answered(self, text: str, got: dict) -> None:
        self._asking = False
        self.model_hint = {"text": text, **got}
        self.changed()

    def find(self, query: str) -> list[dict]:
        """The pages and source notes that match what a person types (no model)."""
        return wikifind.find(self.repo_root, [*self.pages, *self.source_notes()], query)

    def note(self, text: str, section: str = "", tags: list[str] = (), links: list[str] = (),
             source: str = "quick note", take_in: bool = True, meeting: dict | None = None,
             people: list[str] = ()) -> str:
        """Keep a note in the inbox, the inbox a source, and take it in now when asked. Its path;
        ValueError when it cannot be written. A note for a meeting is on its page at once."""
        try:
            path = quicknote.write(self.repo_root, self.inbox, text, section, tags, links, source,
                                   self.clock(), meeting, people)
        except OSError as e:
            raise ValueError(str(e)) from None
        if not any(s.owns(path) for s in self.library.sources):
            problem = self.add_folder(self.inbox)
            if problem:
                raise ValueError(problem)
        else:
            self.refresh()
        self.emit("wiki.noted", path, " ".join(text.split())[:80])
        if take_in and self.pending and not self.running:
            self.ingest("note")
        return path

    # -- the librarian's work -------------------------------------------------------------------

    def items(self) -> tuple[list[wiki.Item], list[str]]:
        """The next batch as the librarian reads it (project files in place, the rest snapshotted),
        and the sources that could not be read now (they wait for the next ingest)."""
        root, repo = self.wiki_root, self.repo_root
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
                self.toast("Nothing new in the sources.", title="📜 Wiki up to date")
            return False
        if not self._prepare():
            return False
        items, unreadable = self.items()
        if unreadable:
            self.last_note = f"{len(unreadable)} source(s) unreadable now, left for later: {', '.join(unreadable[:3])}"
            self.toast(self.last_note, title="📜 Ingest", severity="warning")
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
            self.changed()
            return False

    def _protected(self) -> set[str]:
        """The pages people own, and the ones with edits not yet committed (someone is at work)."""
        return set(wiki.manual_pages(self.wiki_root)) | wiki.uncommitted(self.repo_root, self.wiki_root)

    def _run(self, what: str, prompt: str, summary: str, trigger: str, on_success, message: str) -> bool:
        harness = str(self.config.get("harness") or "main")
        model = str(self.config.get("model") or "")
        root, repo = self.wiki_root, self.repo_root
        job = jobs.Job(uuid.uuid4().hex[:8], f"{what}: {self.spec.get('title', self.building_id)}", harness,
                       summary, model, "librarian", started=jobs.now_iso(), outcome="running", trigger=trigger)
        protected = {rel: text for rel in self._protected()
                     if (text := _read(root / rel)) is not None}
        before = wiki.dirty(repo)
        self.running, self.last_error, self.last_note = what, "", ""
        self._cancel = cancel = threading.Event()
        runner = type(self).work_runner or (_simulated_work if self.simulated else jobs.run_work)
        started = time.time()
        env = {"ORKCRAFT_ORC": f"{self.building_id}/librarian"}
        self.changed()

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
                self.town.call(self.finish, what, job, cost, started, on_success, protected, before, message)
            except Exception:
                self.running = ""

        threading.Thread(target=work, daemon=True, name=f"wiki-{what}-{self.building_id}").start()
        return True

    def finish(self, what: str, job: jobs.Job, cost: float | None, started: float, on_success,
               protected: dict[str, str] | None = None, before: dict | None = None, message: str = "") -> None:
        try:
            root, repo = self.wiki_root, self.repo_root
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
                self.toast(self.last_note, title=f"📜 The {what}", severity="warning")
            if sha:
                job.meta["commit"] = sha
        finally:                                           # done once its job (and cost) is in the log
            try:
                self.log.append(job)
            except OSError:
                pass
            self.running, self._cancel = "", None
        delivery.ran(self.town, roads.HandlerRun(self.building_id, "librarian", "agent", job.id, started, time.time(),
                                                 outcome=job.outcome, markdown=job.result, error=job.error,
                                                 cost_usd=cost))
        if ok:
            self._ingested = self._ingested or what == "ingest"
            self.emit("wiki.updated" if what == "ingest" else "wiki.linted", job.result, job.title)
            if what == "ingest" and sha:
                self.ask_review(sha)
        elif job.outcome != "interrupted":
            self.last_error = job.error
            self.toast(job.error, title=f"📜 The {what} failed", severity="error")
        self.refresh()

    def ask_review(self, sha: str) -> bool:
        """A sample of the pages an ingest wrote, spot-checked: by the Council named in `council`
        (its members, a short discussion, the verdict into reviews.md), else sent out as `wiki.review`."""
        n = int(self.config.get("review_sample", REVIEW_SAMPLE))
        touched = [p for p in wiki.touched_pages(self.repo_root, self.wiki_root, sha) if p not in self.manual]
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
        spec = self.town.custom_specs.get(council_id)
        if not spec or catalog.migrate(spec).get("type") != "council":
            self.last_note = f"no Clan Fire {council_id!r} for the spot-check"
            return False
        if self.reviewing or self.out_of_gold():
            return False
        cfg = dict(spec.get("config") or {})
        team, veto = tm.members_of(cfg), tm.veto_of(cfg)
        budget = min(float(tm.DEFAULT_BUDGET if cfg.get("budget_usd") is None else cfg["budget_usd"]), REVIEW_BUDGET)
        repo = self.repo_root
        self._review_cancel = cancel = threading.Event()
        state = repo / ".orkcraft" / "council" / council_id
        harness, _, model = str(cfg.get("moderator") or "main").partition(":")
        steward = tm.Steward(f"{REVIEW_BRIEF} {str(cfg.get('steward_prompt') or '').strip()}".strip(),
                             harness.strip() or "main", model.strip())

        def brief_of(m: tm.Member) -> tuple[str, str]:
            path = state / "roles" / f"{tm.slug(m.role)}.md"
            text = tm.brief_text(path)
            return (shelves.rel_to(repo, path), text) if text else ("", "")

        d = tm.new(title, request)
        env = {"ORKCRAFT_ORC": f"{council_id}/clan"}
        if type(self).review_runner is not None:
            runner = type(self).review_runner
        elif self.simulated:
            runner = tm.simulated
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
                self.town.call(self.reviewed, d, team, title)
            except Exception:
                self.reviewing = False

        threading.Thread(target=work, daemon=True, name=f"wiki-review-{self.building_id}").start()
        return True

    def reviewed(self, d: tm.Discussion, team: list, title: str) -> None:
        self.reviewing = False
        if d.outcome not in ("approved", "rework"):
            self.last_note = f"the spot-check failed: {d.error or d.outcome}"
            self.changed()
            return
        self.record_verdict(tm.report_markdown(d, team), title)

    def record_verdict(self, verdict: str, title: str) -> None:
        try:
            wiki.record_review(self.wiki_root, verdict, title)
        except (OSError, ValueError):
            return
        if self.config.get("commit", True) is not False and not self.simulated:
            wiki.commit(self.repo_root, self.wiki_root, f"wiki({self.topic}): the Council's review")
        self.refresh()

    # -- roads ----------------------------------------------------------------------------------

    def receive(self, payload, title: str, markdown: str) -> None:
        """The Council's verdict lands in reviews.md; any other cart is a task, sent on with the map."""
        if payload.mode in VERDICT_EVENTS:
            self.record_verdict(markdown or payload.value, payload.title or title)
            return
        self.lend(payload)

    def lend(self, payload, by: str = "") -> bool:
        """A task gets the wiki's map and the pages that matter most for it, sent on as `knowledge.chunks`
        under the task's own title and ref; `by` is the building that asked (a Barracks that reads it
        first). True when a road took it."""
        task = f"{payload.title} {payload.value}".strip()[:500]
        first, links = self.meeting_context(daybook.meet_tag(task))
        found = self.look_up(task, by, payload.title, first=links)
        context = wiki.context(self.wiki_root, self.repo_root, task)
        if first:
            context = f"{first}\n\n{context}"
        if found:
            context += "\n\n**Notes for this task — read these first:**\n" + \
                "\n".join(f"- `{n.path}` — {n.title}" for n in found)
        return self.emit("knowledge.chunks", context, (payload.title or task)[:80], trail=payload.trail,
                         ref=payload.ref)

    def look_up(self, task: str, by: str = "", title: str = "", limit: int = LENT_PAGES,
                first: list[str] = ()) -> list[shelves.Note]:
        """The pages that matter most for `task` (no model: the words they share), after the pages `first`
        names (a meeting's notes link them); what it lent shows on its card. A Task Fields board asks it so
        for a card's context (core/workers/fields.py)."""
        task = task.strip()[:500]
        by_path = {n.path: n for n in self.pages}
        found = [by_path[x] for x in first if x in by_path]
        found += [n for n in wiki.relevant(self.repo_root, self.pages, task, limit) if n not in found]
        found = found[:max(limit, len(first))]
        self.lent = {"task": (title or task)[:80], "pages": [n.title for n in found], "by": by, "at": time.time()}
        self.changed()
        return found

    # -- the hut --------------------------------------------------------------------------------

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


def _read(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return None
