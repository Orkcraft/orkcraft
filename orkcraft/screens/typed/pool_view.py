"""🏕 Barracks: the steward runs incoming tasks with a pool of orcs and judges their work.

A cart that arrives is a task — the unit of work. The foreman's rules (realm/barracks.py) give it
to the orc that did the earlier part (a follow-up), to an idle orc, to a newly hired one (picking
its provider and model), or queue it. Orcs are only a pool of agents: each has a worktree of its
own, and every task gets its own branch `pool/<building>/<task>` cut from a fresh base there.

The steward — the building's own orc — keeps the rules (`orders`) and judges:

    a question   the orc stops with `QUESTION: …`; the steward answers from its rules and the orc
                 goes on in its session, or the question waits for the operator: 🔥 on the steward
                 (the orc only shows a quiet `?`); the answer may become a rule
    the review   the tests (`test_cmd`) first, then the steward reads the diff: `ACCEPT` → the branch
                 is pushed and a pull request opened (`pool.done`), `REWORK: …` → back to the same orc,
                 at most `max_reworks` times, then 🔥 for the operator

Tokens: a follow-up, a rework or a related task resumes the orc's session and sends only what is new
(♻ warm); a cold start sends the briefing, plus a handoff of the orc's recent work only when related.
A `[meet:<id>]` tag in the cart (a War Drum's meeting) stays in the task's title, so `pool.done`
finds its way back to the meeting even when a Signpost renamed the cart to its route.
"""
from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import OptionList, Static
from textual.widgets.option_list import Option

from orkcraft.realm import barracks as bk
from orkcraft.realm import daybook, feedback, gitinfo, jobs, pipes, roads
from orkcraft.screens.dialogs import TextPrompt
from orkcraft.screens.typed.base import TypedView

ICON = {"idle": "💤", "working": "⚒"}
TASK_ICON = {"queued": "·", "working": "⚒", "reviewing": "🔎", "asked": "🔥", "done": "✓", "failed": "✗"}
STEWARD = "steward"
PR_CHECK_S = 600                  # how often the pull requests of done tasks are looked at
DUPLICATE_LABELS = frozenset({"duplicate", "superseded"})   # a closed pull request so labelled is no 👎


def _simulated_work(harness, prompt, workdir, cancel, model, env, resume):
    """The sandbox: an orc 'works' for a moment and reports what it would have done."""
    if cancel.wait(1.5):
        raise InterruptedError("stopped")
    task = prompt.split("## Task", 1)[-1].splitlines()[0].lstrip(": ")
    return f"_(demo — simulated)_ {harness} would have worked on: {task}", None, None, ""


def _simulated_steward(harness, prompt, workdir, cancel, model):
    return "ACCEPT\n_(demo — simulated review)_", None


@dataclass
class RunOutcome:
    """What one run of an orc came to, judged by the steward — made off the UI thread, applied on it."""
    text: str = ""
    error: str = ""
    cost: float = 0.0
    tokens: int = 0
    session: str = ""
    steward_cost: float = 0.0
    qa: list[list[str]] = field(default_factory=list)   # questions the steward answered in this run
    asked: str = ""                                      # a question for the operator
    accepted: bool | None = None                         # None: never reviewed (an error, a question)
    notes: str = ""
    pr: str = ""
    pr_note: str = ""
    scope: str = ""                                      # local: no pull request · external: reviewed and sent


class PoolView(TypedView):
    TYPE = "barracks"
    TAKES_REWORK = True
    work_runner = None            # tests swap the agent call (jobs.run_work) here
    worktree_maker = None         # and the worktree maker (jobs.add_worktree)
    steward_runner = None         # and the steward's model call: (harness, prompt, workdir, cancel, model) → (text, cost)
    git = None                    # and the task's git (jobs.TaskGit)
    pr_reader = None              # and `gh` (gitinfo.pull_requests: head branch → PR)

    def __init__(self, *a, **kw) -> None:
        super().__init__(*a, **kw)
        self.bk: bk.Barracks | None = None
        self._cancels: dict[str, threading.Event] = {}
        self._pumped = False
        self._shown = ""

    @property
    def foreman(self) -> bk.Foreman:
        return bk.Foreman(self.config, self.state.stats)

    @property
    def state(self) -> bk.Barracks:
        if self.bk is None:
            self.bk = bk.Barracks(self.state_dir)
        return self.bk

    @property
    def worktrees(self) -> bool:
        return self.config.get("worktrees", True) is not False

    @property
    def keeper(self) -> str:
        """The steward's name: the building's own orc."""
        return str((self.spec.get("orc") or {}).get("name") or "Steward")

    @property
    def orders(self) -> str:
        return str(self.config.get("orders") or "")

    @property
    def uses_git(self) -> bool:
        """Task branches, the diff, the tests and the PR — only in worktrees, never in the sandbox."""
        return self.worktrees and not self.simulated

    @property
    def task_git(self) -> jobs.TaskGit:
        return type(self).git or jobs.TaskGit()

    def compose_body(self) -> ComposeResult:
        yield Static("", id="pool-head", classes="typed-head")
        with Horizontal(classes="typed-row"):
            yield OptionList(id="pool-orcs", classes="typed-list")
            with VerticalScroll(classes="typed-detail"):
                yield Static("", id="pool-detail")

    def on_mount(self) -> None:                           # TypedView's on_mount runs too (Textual walks the MRO)
        self.set_timer(30, self.check_prs)                # what happened while the camp was closed
        self.set_interval(PR_CHECK_S, self.check_prs)

    # -- what became of the pull requests -----------------------------------------------------------

    def check_prs(self) -> None:
        """Look (off the UI thread) at the pull requests of done tasks not settled yet."""
        if self.simulated or not any(t.status == "done" and t.pr and not t.pr_state for t in self.state.tasks):
            return
        reader, repo, app = type(self).pr_reader or gitinfo.pull_requests, self._get_repo_root(), self.app

        def work() -> None:
            prs = reader(repo)
            if prs:
                try:
                    app.call_from_thread(self.settle_prs, prs)
                except Exception:
                    pass

        threading.Thread(target=work, daemon=True, name=f"prs-{self.building_id}").start()

    def settle_prs(self, prs: dict) -> int:
        """A pull request merged is a 👍 for this Barracks, one closed without merging a 👎 — what the
        operator thought of the work, without pressing anything. A closed one that was a duplicate
        says nothing: labelled so (`DUPLICATE_LABELS`), or another task of the same title merged — and
        while that one is still open, the closed one waits. Returns how many were settled."""
        by_url = {getattr(pr, "url", ""): pr for pr in prs.values()}

        def pr_of(task):
            return by_url.get(task.pr) or prs.get(task.branch)

        def state_of(task) -> str:
            return task.pr_state or str(getattr(pr_of(task), "state", "")).upper()

        def twins(task) -> list[str]:
            title = task.title.strip().lower()
            return [state_of(t) for t in self.state.tasks
                    if t is not task and t.pr and t.title.strip().lower() == title]

        settled = 0
        for task in self.state.tasks:
            if task.status != "done" or not task.pr or task.pr_state:
                continue
            pr = pr_of(task)
            state = str(getattr(pr, "state", "")).upper()
            if state not in ("MERGED", "CLOSED"):
                continue
            good = state == "MERGED"
            duplicate = False
            if not good:
                others = twins(task)
                if any(s in ("OPEN", "DRAFT") for s in others):
                    continue                                    # wait: it may be the twin that merges
                duplicate = "MERGED" in others or bool(set(getattr(pr, "labels", ())) & DUPLICATE_LABELS)
            task.pr_state, settled = state, settled + 1
            if duplicate:
                continue
            feedback.signal(self._get_repo_root(), self.building_id, good, "pr.merged" if good else "pr.closed",
                            value=task.result or task.title,
                            note=f"{task.title}: pull request {'merged' if good else 'closed without merging'} {task.pr}")
        if settled:
            self.state.save()
        return settled

    def refresh_data(self) -> None:
        self.state            # loads once; a restart puts interrupted work back in the queue …
        if not self._pumped:  # … and the orcs pick it up again
            self._pumped = True
            self._pump()
            self.state.save()
        self._render_list()

    # -- tasks in -----------------------------------------------------------------------------------

    def receive(self, payload, title: str, markdown: str) -> None:
        text = markdown or payload.value
        first = text.strip().splitlines()[0][:60] if text.strip() else "task"
        title = payload.title or first
        meet = daybook.meet_tag(title) or daybook.meet_tag(text)
        if meet and daybook.meet_tag(title[:80]) != meet:          # the task keeps 80 characters
            title = f"{title.replace(f'[meet:{meet}]', '').strip()[:80 - len(meet) - 8]} [meet:{meet}]"
        self.add_task(title, text, bk.task_key(payload.kind, payload.value, payload.title),
                      ref=payload.ref, trail=payload.trail)

    def add_task(self, title: str, text: str, key: str = "", ref: str = "", trail: tuple = ()) -> bk.PoolTask:
        """A rework sent back (by a Loot or a Clan Fire) keeps the `ref` of the work: it becomes a follow-up
        of that task — the same orc, the same branch."""
        key = key or bk.task_key("text", text, title)
        prior = next((t for t in reversed(self.state.tasks) if ref and t.ref == ref), None)
        if prior is not None and not key:
            key = prior.key or prior.id               # the orc that did it knows it by that
        task_id = uuid.uuid4().hex[:8]
        task = bk.PoolTask(task_id, title[:80], text, key, bk.now_iso(), ref=ref or f"{self.building_id}:{task_id}",
                           trail=[h.as_dict() for h in trail])
        if prior is not None:
            task.branch, task.base = prior.branch, prior.base
        st = self.state
        st.queue.append(task)
        self._dispatch(task)
        st.save()
        self._render_list()
        return task

    def _dispatch(self, task: bk.PoolTask) -> None:
        st = self.state
        if self.out_of_gold():                       # the run's 🪙 limit: the task waits in the queue
            d = bk.Decision(bk.now_iso(), task.id, "budget", why="the run's 🪙 budget is exhausted")
            task.decided = f"{d.action}: {d.why}"
            st.log(d)
            return
        d = self.foreman.decide(task, st.orcs, [t for t in st.queue if t is not task], st.spent, st.paused)
        task.decided = f"{d.action}: {d.why}"
        st.log(d)
        if d.action in ("follow-up", "reuse"):
            self._assign(task, st.orc(d.orc), d.action)
        elif d.action == "hire":
            harness, model, _ = self.foreman.choose_model(task)
            orc = self.hire(d.orc, harness, model)
            if orc is not None:
                self._assign(task, orc, "new")
        elif d.action == "wait":
            task.wait_for = d.orc

    def _pump(self) -> None:
        """Put idle orcs to work on what waits, then hire for the rest — within the budget, unless paused."""
        st, f = self.state, self.foreman
        if st.paused:
            return
        for o in st.orcs:
            if o.status != "idle" or not st.queue:
                continue
            if f.over_budget(st.spent):
                return
            nxt = f.next_for(o, st.queue)
            if nxt is not None:
                st.log(bk.Decision(bk.now_iso(), nxt.id, "follow-up" if nxt.wait_for else "reuse", o.name,
                                   f"{o.name} is free" + (" — its follow-up" if nxt.wait_for else "")))
                self._assign(nxt, o, "follow-up" if nxt.wait_for else "reuse")
        for q in [q for q in st.queue if not q.wait_for]:
            if q in st.queue and len(st.orcs) < f.max_orcs and not f.over_budget(st.spent):
                self._dispatch(q)

    def hire(self, name: str, harness: str, model: str) -> bk.PoolOrc | None:
        st = self.state
        orc = bk.PoolOrc(name, harness, model, hired=bk.now_iso())
        if self.worktrees and not self.simulated:          # the sandbox describes worktrees, it does not make them
            maker = type(self).worktree_maker or jobs.add_worktree
            try:
                path, _branch = maker(self._get_repo_root(), self.building_id, name)
            except (RuntimeError, OSError) as e:
                self.app.notify(f"{name}: no worktree — {e}", title="🏕 Barracks", severity="error")
                return None
            orc.worktree = str(path)
        st.orcs.append(orc)
        return orc

    # -- work ---------------------------------------------------------------------------------------

    def _assign(self, task: bk.PoolTask, orc: bk.PoolOrc | None, how: str) -> None:
        if orc is None:
            return
        st = self.state
        if task in st.queue:
            st.queue.remove(task)
        task.status, task.orc, task.wait_for = "working", orc.name, ""
        task.attempts += 1
        if task not in st.tasks:
            st.tasks.append(task)
        foreman = self.foreman
        follow = how == "follow-up"
        related = follow or foreman.related(task, orc)
        task.warm = related and foreman.can_resume(orc)
        orc.status, orc.task = "working", task.id
        if (task.key or task.id) not in orc.keys:     # a rework of a task without a ticket comes back by its id
            orc.keys.append(task.key or task.id)
        repo = self._get_repo_root()
        if self.uses_git:
            task.branch = task.branch or bk.task_branch(self.building_id, task)
            task.base = task.base or self.task_git.base_of(repo, str(self.config.get("base") or ""))
        orc.branch = task.branch
        rework = f" [rework {task.attempts - 1}]" if task.feedback else ""
        self.emit("pool.assigned", f"{orc.name} ({orc.label}) ← {task.title}" + (" [follow-up]" if follow else "")
                  + rework + (" ♻" if task.warm else ""), task.title)
        cancel = threading.Event()
        self._cancels[orc.name] = cancel
        workdir = Path(orc.worktree) if orc.worktree else repo
        prompt = self._prompt(task, orc, follow, related)
        resume = orc.session if task.warm else ""
        args = (task, orc, workdir, prompt, resume, cancel)
        threading.Thread(target=self._work, args=args, daemon=True,
                         name=f"pool-{self.building_id}-{orc.name}").start()

    def _work(self, task: bk.PoolTask, orc: bk.PoolOrc, workdir: Path, prompt: str, resume: str,
              cancel: threading.Event) -> None:
        """Off the UI thread: the branch, the orc's run, the steward's answers and its review."""
        out = RunOutcome()
        runner = type(self).work_runner or (_simulated_work if self.simulated else jobs.run_work)
        env = {"ORKCRAFT_ORC": f"{self.building_id}/{orc.name.lower()}"}
        git = self.task_git if self.uses_git else None

        def run(p: str, r: str) -> None:
            text, cost, tokens, session = runner(orc.harness, p, workdir, cancel, orc.model, env, r)
            out.text, out.cost, out.tokens = text, out.cost + (cost or 0.0), out.tokens + (tokens or 0)
            out.session = session or out.session

        try:
            if git is not None:
                git.prepare(workdir, task.branch, task.base)
            run(prompt, resume)
            for _ in range(bk.MAX_STEWARD_ANSWERS + 1):
                question = bk.question_of(out.text)
                if not question:
                    break
                answer = "" if len(out.qa) >= bk.MAX_STEWARD_ANSWERS else self._steward_answer(task, question, workdir,
                                                                                                 cancel, out)
                if not answer:
                    out.asked = question
                    break
                out.qa.append([question, answer, self.keeper])
                if orc.harness in bk.RESUMABLE and out.session:
                    run(f"{self.keeper}, the steward, answers your question: {answer}\n\nGo on with the task and "
                        "finish as before.", out.session)
                else:                            # no session to go back to: the whole briefing with the answers
                    run(self._prompt(task, orc, True, True, extra_qa=out.qa), "")
            if not out.asked:
                self._call(self._mark, task.id, "reviewing")
                self._review(task, workdir, git, cancel, out)
        except InterruptedError:
            out.error = "stopped"
        except Exception as e:  # one orc's failure must not take the barracks down
            out.error = str(e)[:300]
        self._call(self.finish, task.id, orc.name, out)

    def _call(self, fn, *args) -> None:
        try:
            self.app.call_from_thread(fn, *args)
        except Exception:
            pass

    def _mark(self, task_id: str, status: str) -> None:
        task = self.state.task(task_id)
        if task is not None and task.status == "working":
            task.status = status
            self._render_list()

    def _steward(self, prompt: str, workdir: Path, cancel: threading.Event, out: RunOutcome) -> str:
        harness, model = bk.parse_provider(str(self.config.get("steward") or "claude"))
        if type(self).steward_runner is not None:
            runner = type(self).steward_runner
        elif self.simulated:
            runner = _simulated_steward
        else:
            env = {"ORKCRAFT_ORC": f"{self.building_id}/steward"}
            runner = lambda h, p, w, c, m: roads.run_agent(h, p, w, env, c, m)[:2]      # noqa: E731
        text, cost = runner(harness, prompt, workdir, cancel, model)
        out.steward_cost += cost or 0.0
        return text or ""

    def _steward_answer(self, task: bk.PoolTask, question: str, workdir: Path, cancel: threading.Event,
                        out: RunOutcome) -> str:
        prompt = bk.steward_question_prompt(self.keeper, self.orders, task, question)
        return bk.steward_answer_of(self._steward(prompt, workdir, cancel, out))

    def _review(self, task: bk.PoolTask, workdir: Path, git: jobs.TaskGit | None, cancel: threading.Event,
                out: RunOutcome) -> None:
        """The tests first (cheap and strict), then the steward reads the diff; accepted → the PR — for code
        and documents that go out. A local document (a meeting's prep, notes for the operator) gets no PR."""
        meeting = self._meeting(task)
        diff, tests, files, commits = "", "", [], 0
        if git is not None:
            commits, diff = git.diff(workdir, task.base, task.branch)
            files = bk.changed_files(diff)
            if commits == 0 and not meeting:
                out.accepted, out.notes = False, "nothing was committed on the branch — commit your work"
                return
        rule = bk.scope_rule(files, meeting)
        cmd = str(self.config.get("test_cmd") or "") if git is not None and commits and rule != bk.LOCAL else ""
        if cmd:
            passed, tail = git.test(workdir, cmd, cancel)
            if not passed:
                out.accepted, out.notes = False, f"the tests fail (`{cmd}`):\n\n```\n{tail.strip()}\n```"
                return
            tests = f"`{cmd}` passes"
        verdict = self._steward(bk.review_prompt(self.keeper, self.orders, task, out.text, diff, tests, rule),
                                workdir, cancel, out)
        out.accepted, out.notes = bk.verdict_of(verdict)
        out.notes = bk.SCOPE.sub("", out.notes).strip()
        out.scope = rule or bk.scope_of(verdict)
        if out.accepted and git is not None and commits and out.scope == bk.EXTERNAL:
            body = f"{task.text}\n\n---\n\n{out.text}\n\n_Reviewed by {self.keeper}: {out.notes or 'accepted'}_"
            out.pr, out.pr_note = git.publish(workdir, task.branch, task.base, task.title, body)

    @staticmethod
    def _meeting(task: bk.PoolTask) -> bool:
        """A War Drum's meeting asked for it: a local document, no pull request."""
        return bool(daybook.meet_tag(task.title) or daybook.meet_tag(task.text))

    def _prompt(self, task: bk.PoolTask, orc: bk.PoolOrc, follow: bool, related: bool,
                extra_qa: list[list[str]] | None = None) -> str:
        sent_back = f"## {self.keeper}, the steward, sent it back\n\n{task.feedback}" if task.feedback else ""
        ask = ("If you cannot go on without a decision, stop and end your answer with one line `QUESTION: …`; "
               f"{self.keeper}, the steward, will answer.")
        qa = task.qa + (extra_qa or [])
        decisions = "## Decisions so far\n\n" + "\n".join(f"- {q} → {a}" for q, a, *_ in qa) if qa else ""
        if task.warm:                    # the session already holds the briefing, the rules and the earlier work
            return "\n\n".join(p for p in [
                f"## Task{' (a follow-up of your earlier work)' if follow else ''}: {task.title}", task.text, decisions,
                sent_back,
                f"Your branch is now `{task.branch}`." if task.branch else "",
                "Same rules as before: commit on your branch, then a short Markdown report."] if p)
        parts = [f"You are {orc.name}, one of several agents working in parallel, each in its own git worktree.",
                 f"Work on the branch `{task.branch}` (it is checked out)." if task.branch else "",
                 "Do the task below in this directory. Commit your work on the branch with a clear message; do not "
                 f"push and do not open a pull request — {self.keeper}, the steward, reviews it and does that.",
                 f"## {self.keeper}'s rules\n\n{self.orders}" if self.orders else "",
                 f"## Task{' (a follow-up of your earlier work)' if follow else ''}: {task.title}", task.text,
                 decisions, sent_back, ask,
                 "This is a local document for a meeting: write it as your report (a commit is optional); it gets "
                 "no pull request." if self._meeting(task) else "",
                 "Finish with a short Markdown report: what you changed, what is left."]
        if related and orc.recent:       # a fresh session on related work: a handoff instead of the whole history
            parts.append("## Your recent work\n\n" + "\n".join(f"- {r}" for r in orc.recent))
        return "\n\n".join(p for p in parts if p)

    def _trail(self, task: bk.PoolTask, orc: bk.PoolOrc, outcome: str) -> tuple:
        """The task's trail with this building's hop: the whole task (every run and review) as one."""
        return pipes.trail_of(task.trail) + (pipes.hop(self.building_id, orc.name, "agent", task.tokens,
                                                       task.cost_usd, orc.worktree, task.branch, outcome),)

    def finish(self, task_id: str, orc_name: str, out: RunOutcome) -> None:
        st = self.state
        task, orc = st.task(task_id), st.orc(orc_name)
        self._cancels.pop(orc_name, None)
        if task is None or orc is None:
            return
        f = self.foreman
        task.result, task.error = out.text, out.error
        task.cost_usd = round((task.cost_usd or 0.0) + out.cost + out.steward_cost, 4)
        task.tokens = (task.tokens or 0) + out.tokens if out.tokens else task.tokens
        task.qa += out.qa
        orc.status, orc.task, orc.last = "idle", "", bk.now_iso()
        orc.cost_usd = round(orc.cost_usd + out.cost, 4)
        orc.tokens += out.tokens
        st.steward_cost = round(st.steward_cost + out.steward_cost, 4)
        if out.session:
            orc.session_tasks = orc.session_tasks + 1 if task.warm else 1
            orc.session = out.session
        elif not out.error:              # a harness without sessions: nothing to resume
            orc.session, orc.session_tasks = "", 0
        ok = out.accepted is True
        orc.done, orc.failed = orc.done + int(ok), orc.failed + int(out.accepted is False or bool(out.error))
        f.learn(orc, ok, out.cost, out.tokens or None)
        st.stats = f.stats
        for q, a, _who in out.qa:
            st.log(bk.Decision(bk.now_iso(), task.id, "answer", orc.name, f"{q} → {a}"))
        if out.error:
            task.status = "failed"
            self.emit("pool.failed", f"**{task.title}** — {orc.name}: {out.error}", task.title,
                      trail=self._trail(task, orc, "error"), ref=task.ref)
        elif out.asked:
            self._ask(task, out.asked, f"{orc.name} asks")
        elif ok:
            task.status, task.pr, task.feedback, task.scope = "done", out.pr, "", out.scope
            gist = next((ln.strip(" #*") for ln in out.text.splitlines() if ln.strip(" #*")), "")[:160]
            orc.recent = (orc.recent + [f"{task.title} — {gist}" if gist else task.title])[-bk.KEEP_RECENT:]
            local = out.scope == bk.LOCAL
            st.log(bk.Decision(bk.now_iso(), task.id, "accept", orc.name,
                               ("local, no pull request: " if local else "") + (out.notes or "accepted")))
            where = f"\n\n_pull request:_ {out.pr}" if out.pr else (f"\n\n_branch:_ `{task.branch}`" if task.branch else "")
            note = " (a local document: no pull request)" if local else \
                (f" ({out.pr_note})" if out.pr_note and not out.pr else "")
            self.emit("pool.done", f"**{task.title}** — {orc.name} ({orc.label})\n\n{out.text}{where}{note}", task.title,
                      trail=self._trail(task, orc, "done"), ref=task.ref)
        else:
            self._rework(task, orc, out.notes)
        on_run = getattr(self.app, "on_handler_run", None)
        if on_run is not None and out.error != "stopped" and not out.asked:
            on_run(roads.HandlerRun(self.building_id, orc.name.lower(), orc.harness, task.id, 0.0, 0.0,
                                    outcome="done" if ok else "error", markdown=out.text,
                                    error=out.error or ("" if ok else out.notes), cost_usd=out.cost or None))
        self._pump()
        if not st.queue and all(o.status == "idle" for o in st.orcs):
            self.emit("pool.idle", "every task is done" + (f"; {len(st.asked)} wait for you" if st.asked else ""),
                      "queue empty")
        st.save()
        self._render_list()

    def _rework(self, task: bk.PoolTask, orc: bk.PoolOrc, notes: str) -> None:
        """Rejected: back to the same orc (in its session) while reworks are left, else to the operator."""
        st, limit = self.state, self.foreman.max_reworks
        task.feedback = notes
        reworks = task.attempts - 1
        st.log(bk.Decision(bk.now_iso(), task.id, "rework", orc.name, f"{reworks + 1}/{limit}: {notes[:200]}"
                           if reworks < limit else f"rejected after {reworks} reworks: {notes[:200]}"))
        if reworks < limit:
            st.tasks.remove(task)
            task.status, task.wait_for = "queued", orc.name
            st.queue.insert(0, task)
            return
        self.emit("pool.failed", f"**{task.title}** — rejected after {reworks} reworks: {notes}", task.title,
                  trail=self._trail(task, orc, "error"), ref=task.ref)
        self._ask(task, f"Rejected after {reworks} reworks. Last notes: {notes[:500]}\n\nWhat should {orc.name} do?",
                  "rejected")

    def _ask(self, task: bk.PoolTask, question: str, why: str) -> None:
        st = self.state
        task.status, task.question = "asked", question
        st.log(bk.Decision(bk.now_iso(), task.id, "ask", task.orc, f"{why}: {question[:200]}"))
        self.emit("pool.question", f"**{task.title}** — {why}:\n\n{question}", task.title)
        try:
            self.app.notify(f"{task.title}: {question[:160]}", title=f"🔥 {self.keeper} asks")
        except Exception:
            pass

    # -- the operator's answers ------------------------------------------------------------------------

    def ask_operator(self, task: bk.PoolTask | None = None) -> bool:
        """Open the steward's 🔥: the operator answers the oldest question (or `task`'s)."""
        task = task or next(iter(self.state.asked), None)
        if task is None:
            return False
        self.app.push_screen(TextPrompt(f"🔥 {self.keeper} asks — {task.title}", placeholder="your answer",
                                        help=task.question), lambda text: self.answer(task.id, text))
        return True

    def answer(self, task_id: str, text: str | None, propose: bool = True) -> None:
        """The operator's answer goes back to the orc that asked (the task returns to its queue); the
        steward proposes it as a rule."""
        st = self.state
        task = st.task(task_id)
        if not text or task is None or task.status != "asked":
            return
        question = task.question.split("\n\n")[0]
        task.qa.append([question, text.strip(), "operator"])
        if task.attempts - 1 >= self.foreman.max_reworks:
            task.attempts = 0                       # the operator's word opens a new round of reworks
        task.question, task.status, task.wait_for = "", "queued", task.orc
        st.tasks.remove(task)
        st.queue.insert(0, task)
        st.log(bk.Decision(bk.now_iso(), task.id, "answer", task.orc, f"operator: {text.strip()[:200]}"))
        self._pump()
        st.save()
        self._render_list()
        if propose:
            rule = f"- {question.strip()[:200]} → {text.strip()[:300]}"
            self.app.push_screen(TextPrompt(f"📜 Add to {self.keeper}'s rules?", value=rule,
                                            help="Enter keeps it as a rule for every ork; Esc — only this once"),
                                 self.add_rule)

    def add_rule(self, rule: str | None) -> bool:
        if not rule or not rule.strip():
            return False
        orders = self.orders.rstrip()
        return self.save_config({"orders": f"{orders}\n{rule.strip()}" if orders else rule.strip()})

    def on_unmount(self) -> None:
        for c in self._cancels.values():
            c.set()

    def halt(self) -> int:
        """🛑 Halt All: every orc and the steward stop; the barracks pauses (⏸ resumes it)."""
        running = [c for c in self._cancels.values() if not c.is_set()]
        for c in running:
            c.set()
        self.state.paused = True
        self.state.save()
        self._render_list()
        return len(running)

    # -- the view -----------------------------------------------------------------------------------

    def _render_list(self) -> None:
        st = self.state
        try:
            head, lst = self.query_one("#pool-head", Static), self.query_one("#pool-orcs", OptionList)
        except Exception:
            return
        f = self.foreman
        budget = f" · ${st.spent:.2f}/{f.budget:.0f}" if f.budget else (f" · ${st.spent:.2f}" if st.spent else "")
        head.update(Text.assemble(("⏸ paused · " if st.paused else "", "yellow"),
                                  (f"{len(st.orcs)}/{f.max_orcs} orcs · {len(st.queue)} queued{budget} · "
                                   f"providers {', '.join(h + (':' + m if m else '') for h, m in f.providers)}",
                                   "dim")))
        keep = lst.highlighted
        lst.clear_options()
        row = Text(no_wrap=True, overflow="ellipsis")
        rules = len([ln for ln in self.orders.splitlines() if ln.strip()])
        row.append(f"🛡 {self.keeper} ", style="bold")
        row.append(f"steward · {rules} rules", style="dim")
        if st.asked:
            row.append(f" · 🔥 {len(st.asked)} asks", style="bold red")
        lst.add_option(Option(row, id=STEWARD))
        asking = {t.orc for t in st.asked}
        for o in st.orcs:
            task = st.task(o.task) if o.task else None
            row = Text(no_wrap=True, overflow="ellipsis")
            row.append(f"{ICON.get(o.status, '·')} {o.tier_icon + ' ' if o.tier_icon else ''}{o.name} ", style="bold")
            row.append(f"{o.label} ", style="cyan")
            if task is not None:
                row.append(("🔎 " if task.status == "reviewing" else "") + task.title)
            else:
                row.append(f"✓{o.done} ✗{o.failed}", style="dim")
            if o.name in asking:
                row.append(" ?", style="dim")          # its question waits at the steward
            if o.tokens:
                row.append(f" · {o.tokens / 1000:.0f}k tok", style="dim")
            lst.add_option(Option(row, id=o.name))
        if keep is not None and keep < lst.option_count:
            lst.highlighted = keep
        self._detail()

    def on_option_list_option_highlighted(self, event: OptionList.OptionHighlighted) -> None:
        if event.option_list.id == "pool-orcs":
            event.stop()
            self._shown = event.option.id or ""
            self._detail()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        if event.option_list.id == "pool-orcs":
            event.stop()
            if event.option.id == STEWARD:
                self.ask_operator()

    def _detail(self) -> None:
        t = Text()
        if self._shown == STEWARD:
            self._steward_detail(t)
        else:
            self._tasks_detail(t)
        try:
            self.query_one("#pool-detail", Static).update(t)
        except Exception:
            pass

    def _steward_detail(self, t: Text) -> None:
        st = self.state
        t.append(f"🛡 {self.keeper} — the steward\n", style="bold")
        t.append(f"answers the orks' questions from the rules, reviews every task (≤{self.foreman.max_reworks} "
                 "reworks), opens the pull request\n\n", style="dim")
        if st.asked:
            t.append("🔥 Waiting for you (Enter answers)\n", style="bold red")
            for x in st.asked:
                t.append(f"· {x.title} — {x.orc}\n", style="bold")
                t.append(f"  {x.question[:300]}\n", style="")
            t.append("\n")
        t.append("Rules\n", style="bold")
        t.append((self.orders.strip() or "none yet — answers you give can become rules") + "\n\n",
                 style="" if self.orders.strip() else "dim")
        cmd = str(self.config.get("test_cmd") or "")
        t.append(f"tests: {cmd or 'none — the review reads the diff only'} · steward: "
                 f"{self.config.get('steward') or 'claude'} · spent ${st.steward_cost:.2f}\n", style="dim")

    def _tasks_detail(self, t: Text) -> None:
        st = self.state
        if st.asked:
            t.append(f"🔥 {self.keeper} asks — {len(st.asked)} waiting (select 🛡)\n\n", style="bold red")
        if st.queue:
            t.append("Queue\n", style="bold")
            for q in st.queue:
                t.append(f"· {q.title}", style="")
                t.append(f"  rework for {q.wait_for}\n" if q.feedback and q.wait_for else
                         f"  waits for {q.wait_for}\n" if q.wait_for else "\n", style="dim")
            t.append("\n")
        recent = [x for x in st.tasks if x.status in ("done", "failed")][-5:]
        if recent:
            t.append("Finished\n", style="bold")
            for x in reversed(recent):
                t.append(f"{TASK_ICON[x.status]} {'♻ ' if x.warm else ''}{x.title} — {x.orc}",
                         style="green" if x.status == "done" else "red")
                tries = f" · {x.attempts} runs" if x.attempts > 1 else ""
                t.append(f"{tries}{' · ' + x.pr if x.pr else ''}\n", style="dim")
            t.append("\n")
        t.append("Decisions\n", style="bold")
        for d in st.decisions(12):
            t.append(f"{d.at[11:16]} {d.action}", style="yellow")
            t.append(f" {d.orc} " if d.orc else " ")
            t.append(f"{d.why}\n", style="dim")
        if not st.decisions(1):
            t.append("none yet — a road brings tasks here\n", style="dim")

    # -- the hut ----------------------------------------------------------------------------------

    def mini_status(self) -> list[str]:
        st = self.state
        fire = [f"🔥 {self.keeper} asks"] if st.asked else []
        if not st.orcs and not st.queue:
            return fire + ["no orks yet", "⏸ paused" if st.paused else "waiting for tasks"]
        lines = [f"{ICON.get(o.status, '·')} {o.tier_icon + ' ' if o.tier_icon else ''}{o.name} {o.label}" for o in st.orcs[:3]]
        if len(st.orcs) > 3:
            lines.append(f"+{len(st.orcs) - 3} more")
        lines.append(("⏸ " if st.paused else "") + f"queue {len(st.queue)}")
        return fire + lines

    def hut_lines(self, widths: list[int]) -> list[str]:
        st, f = self.state, self.foreman
        busy = sum(1 for o in st.orcs if o.status == "working")
        review = sum(1 for t in st.tasks if t.status == "reviewing")
        done = sum(1 for t in st.tasks if t.status == "done")
        failed = sum(1 for t in st.tasks if t.status == "failed")
        state = "PAUSED" if st.paused else "BUSY" if busy else "READY"
        lines = [f"active: {busy}/{f.max_orcs}", f"queue: {len(st.queue)} wait", f"review: {review}",
                 f"✓{done} ✗{failed}", f"spent: ${st.spent:.2f}", f"status: {state}"]
        return ([f"🔥 {self.keeper} asks"] + lines[:5]) if st.asked else lines

    def quick_action(self, action_id: str) -> bool:
        st = self.state
        if action_id == "pool.hire":
            if st.asked:                     # the steward's question comes first
                return self.ask_operator()
            f = self.foreman
            if len(st.orcs) >= f.max_orcs:
                self.app.notify(f"already {len(st.orcs)}/{f.max_orcs} orks", title="🏕 Barracks")
                return True
            name = next((n for n in bk.NAMES if n not in {o.name for o in st.orcs}), f"Ork{len(st.orcs) + 1}")
            harness, model, why = f.choose_model(bk.PoolTask("", "", ""))
            orc = self.hire(name, harness, model)
            if orc is not None:
                st.log(bk.Decision(bk.now_iso(), "", "hire", name, f"hired by hand; {why}"))
                self._pump()
            st.save()
            self._render_list()
            return True
        if action_id == "pool.pause":
            st.paused = not st.paused
            if not st.paused:                 # resumed: idle orcs pick up what waited
                self._pump()
            st.save()
            self._render_list()
            self.app.notify("paused" if st.paused else "taking tasks again", title="🏕 Barracks")
            return True
        return False
