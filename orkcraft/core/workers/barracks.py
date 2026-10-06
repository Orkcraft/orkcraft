"""🏕 Barracks' work: the steward runs incoming tasks with a pool of orcs and judges their work.

A cart that arrives is a task — the unit of work. The steward judges it first (core/workers/
barracks_plan.py): a simple one goes whole to an ork of the light tier the building's goal names, a
hard one is planned into parts that run in parallel and are merged into one branch. The foreman's
rules (realm/barracks.py) give a task to the orc that did the earlier part (a follow-up), to an idle
orc of its tier and persona, to a newly hired one, or queue it; nobody hires by hand. Orcs are only a pool of agents: each has a worktree of its
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

The orcs run in threads of the worker; what they come to is applied on the town's thread
(`town.call`). `tick()` looks at the pull requests of done tasks now and then (a face calls it).

`pool.assigned`, `pool.done` and `pool.failed` carry the task's `ref`: a board that sent the task gets its
card moved by them over a return road. In the sandbox no model runs: an ork's report comes from
`simulated.json` in the state folder when the demo wrote one (`{"work": [{"match", "say", "seconds"}]}`).
"""
from __future__ import annotations

import threading
import time
import uuid
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from orkcraft.core import delivery
from orkcraft.core.workers import Worker
from orkcraft.core.workers.barracks_plan import PlanMixin
from orkcraft.realm import barracks as bk
from orkcraft.realm import daybook, feedback, gate, gitinfo, jobs, personas, pipes, plans, roads, steward, tiers

ICON = {"idle": "💤", "working": "⚒"}
TASK_ICON = {"queued": "·", "working": "⚒", "reviewing": "🔎", "asked": "🔥", "done": "✓", "failed": "✗",
             "planning": "🧭", "planned": "🧭", "blocked": "⏸"}
PR_FIRST_S = 30                   # the first look at the pull requests: what happened while the camp was closed
PR_CHECK_S = 600                  # how often the pull requests of done tasks are looked at
DUPLICATE_LABELS = frozenset({"duplicate", "superseded"})   # a closed pull request so labelled is no 👎


def _simulated_work(harness, prompt, workdir, cancel, model, env, resume):
    """The sandbox: an orc 'works' for a moment and reports what it would have done."""
    if cancel.wait(1.5):
        raise InterruptedError("stopped")
    task = prompt.split("## Task", 1)[-1].splitlines()[0].lstrip(": ")
    return f"_(demo — simulated)_ {harness} would have worked on: {task}", None, None, ""


def _scripted_work(rules: list):
    """The sandbox's orks with their reports written beforehand: the first rule whose `match` is found in
    the prompt says `say` after `seconds`; no rule → the plain simulated report."""
    def run(harness, prompt, workdir, cancel, model, env, resume):
        for rule in rules:
            try:
                hit = re.search(str(rule.get("match") or ""), prompt, re.I | re.S)
            except re.error:
                hit = None
            if hit is None:
                continue
            if cancel.wait(float(rule.get("seconds") or 1.5)):
                raise InterruptedError("stopped")
            return str(rule.get("say") or ""), None, None, ""
        return _simulated_work(harness, prompt, workdir, cancel, model, env, resume)
    return run


def _simulated_steward(harness, prompt, workdir, cancel, model):
    return "ACCEPT\n_(demo — simulated review)_", None


TITLE_WORDS = 4                 # a task written without a title is named by its brief's first words


def title_from(brief: str) -> str:
    """`Fix the login page` from `fix the login page: it hangs on …` — its first few words, no trailing
    punctuation."""
    title = " ".join(brief.split()[:TITLE_WORDS]).rstrip(".,:;!?—-")[:60]
    return title[:1].upper() + title[1:] or "Task"


@dataclass
class RunOutcome:
    """What one run of an orc came to, judged by the steward — made in the orc's thread, applied on the town's."""
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
    files: list[str] = field(default_factory=list)       # what the branch changed


def take_back(town, source_id: str, payload: pipes.Payload) -> str:
    """A Loot checkpoint or a Clan Fire sends a cart back to the building that made it — directly, not
    by a road (a road back would close a loop). The building whose worker redoes delivered work
    (`TAKES_REWORK`: a Barracks queues the task again) is the source, else the latest one in the cart's
    trail (past a Signpost or a Mill on the way). Its id, or "" when nobody can take it back."""
    for bid in [source_id] + [h.building for h in reversed(payload.trail) if h.building != source_id]:
        if getattr(town.worker(bid), "TAKES_REWORK", False):
            town.deliver(bid, payload, payload.title, payload.value)
            return bid
    return ""


class BarracksWorker(PlanMixin, Worker):
    TYPE = "barracks"
    TAKES_REWORK = True
    APPROVAL = gate.APPROVAL      # the hop's outcome on a draft that waits for the operator (a Loot always holds it)
    work_runner = None            # tests swap the agent call (jobs.run_work) here
    worktree_maker = None         # and the worktree maker (jobs.add_worktree)
    steward_runner = None         # and the steward's model call: (harness, prompt, workdir, cancel, model) → (text, cost)
    git = None                    # and the task's git (jobs.TaskGit)
    pr_reader = None              # and `gh` (gitinfo.pull_requests: head branch → PR)

    def __init__(self, town, building_id: str) -> None:
        super().__init__(town, building_id)
        self.bk: bk.Barracks | None = None
        self._cancels: dict[str, threading.Event] = {}
        self._pumped = False
        self._merge_lock = threading.Lock()     # one part at a time is merged into its parent's branch
        self._prs_at = time.monotonic() - PR_CHECK_S + PR_FIRST_S

    # -- what it is -----------------------------------------------------------------------------

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

    # -- its life -------------------------------------------------------------------------------

    def start(self) -> None:
        """Loads once; a restart puts interrupted work back in the queue and the orcs pick it up again."""
        if self._pumped:
            return
        self._pumped = True
        st = self.state
        for parent in [t for t in st.tasks if t.plan and t.status == "planned"]:
            self._advance(parent)
        self._pump()
        self.state.save()

    def status(self) -> str:
        st = self.state
        if st.asked:
            return "ASKS"
        if st.paused:
            return "PAUSED"
        return "BUSY" if any(o.status == "working" for o in st.orcs) else ""

    def tick(self, now: float | None = None) -> None:
        """Now and then: what waited for the operator its time (the orks decide); what waits in the queue with
        nobody on it (an orc that could not be hired is tried again); what became of the pull requests."""
        self.tick_asks()
        st = self.state
        if st.queue and not st.paused and not any(o.status == "working" for o in st.orcs):
            self._pump()
            st.save()
            self.changed()
        now = time.monotonic() if now is None else now
        if now - self._prs_at >= PR_CHECK_S:
            self._prs_at = now
            self.check_prs()

    # -- what became of the pull requests -----------------------------------------------------------

    def check_prs(self) -> None:
        """Look (in a thread) at the pull requests of done tasks not settled yet."""
        if self.simulated or not any(t.status == "done" and t.pr and not t.pr_state for t in self.state.tasks):
            return
        reader, repo = type(self).pr_reader or gitinfo.pull_requests, self.repo_root

        def work() -> None:
            prs = reader(repo)
            if prs:
                self._call(self.settle_prs, prs)

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
            feedback.signal(self.repo_root, self.building_id, good, "pr.merged" if good else "pr.closed",
                            value=task.result or task.title,
                            note=f"{task.title}: pull request {'merged' if good else 'closed without merging'} {task.pr}")
        if settled:
            self.state.save()
            self.changed()
        return settled

    # -- tasks in -----------------------------------------------------------------------------------

    def receive(self, payload, title: str, markdown: str) -> None:
        draft = self._draft_of(payload.ref) if payload.mode.endswith("rework") else None
        if draft is not None:                   # a Loot or a Clan Fire sent the draft back: what to change
            self.answer(draft.id, markdown or payload.value or "the review sent it back")
            return
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
        self.changed()
        return task

    def new_task(self, title: str, brief: str = "") -> bk.PoolTask | None:
        """✍ New task: the operator writes to the barracks directly — the title and the brief (the title
        alone when it is empty; without a title, the brief's first words are one)."""
        title, brief = title.strip(), brief.strip()
        if not title and not brief:
            return None
        return self.add_task(title or title_from(brief), brief or title)

    def _dispatch(self, task: bk.PoolTask) -> None:
        st = self.state
        if self.out_of_gold():                       # the run's 🪙 limit: the task waits in the queue
            d = bk.Decision(bk.now_iso(), task.id, "budget", why="the run's 🪙 budget is exhausted")
            task.decided = f"{d.action}: {d.why}"
            st.log(d)
            return
        if not st.paused and not self._triaged(task):    # the steward plans it first
            return
        d = self.foreman.decide(task, st.orcs, [t for t in st.queue if t is not task], st.spent, st.paused)
        task.decided = f"{d.action}: {d.why}"
        st.log(d)
        if d.action in ("follow-up", "reuse", "retier"):
            self._assign(task, st.orc(d.orc), d.action)
        elif d.action == "hire":
            harness, model, _ = self.foreman.choose_model(task)
            orc = self.hire(d.orc, harness, model, task.persona)
            if orc is not None:
                self._assign(task, orc, "new")
        elif d.action == "wait":
            task.wait_for = d.orc

    def _pump(self) -> None:
        """Put idle orcs to work on what waits, then hire for the rest — within the budget, unless paused."""
        st, f = self.state, self.foreman
        if st.paused:
            return
        for q in [q for q in st.queue if not q.wait_for]:     # judged before any orc takes it
            if q in st.queue and not self.out_of_gold():
                self._triaged(q)
        for o in st.orcs:
            if o.status != "idle" or not st.queue:
                continue
            if f.over_budget(st.spent):
                return
            nxt = f.next_for(o, st.queue, room=len(st.orcs) < f.max_orcs)
            if nxt is not None:
                st.log(bk.Decision(bk.now_iso(), nxt.id, "follow-up" if nxt.wait_for else "reuse", o.name,
                                   f"{o.name} is free" + (" — its follow-up" if nxt.wait_for else "")))
                self._assign(nxt, o, "follow-up" if nxt.wait_for else "reuse")
        for q in [q for q in st.queue if not q.wait_for]:
            if q in st.queue and len(st.orcs) < f.max_orcs and not f.over_budget(st.spent):
                self._dispatch(q)

    def hire(self, name: str, harness: str, model: str, persona: str = "") -> bk.PoolOrc | None:
        st = self.state
        orc = bk.PoolOrc(name, harness, model, hired=bk.now_iso(), persona=persona)
        if self.worktrees and not self.simulated:          # the sandbox describes worktrees, it does not make them
            maker = type(self).worktree_maker or jobs.add_worktree
            try:
                path, _branch = maker(self.repo_root, self.building_id, name)
            except (RuntimeError, OSError) as e:
                self.toast(f"{name}: no worktree — {e}", title="🏕 Barracks", severity="error")
                return None
            orc.worktree = str(path)
        st.orcs.append(orc)
        return orc

    def pause(self) -> bool:
        """⏸ / ▶: stop or resume taking tasks. True when it is paused now."""
        st = self.state
        st.paused = not st.paused
        if not st.paused:                 # resumed: idle orcs pick up what waited
            self._pump()
        st.save()
        self.changed()
        self.toast("paused" if st.paused else "taking tasks again", title="🏕 Barracks")
        return st.paused

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
        if task.tier and orc.tier != task.tier:           # the task's tier: the orc thinks with its model now
            model = foreman.model_for(orc.harness, task.tier)
            if model is not None:
                st.log(bk.Decision(bk.now_iso(), task.id, "retier", orc.name, f"{orc.label} → {orc.harness}:{model}"))
                orc.model = model
        if task.persona and orc.persona != task.persona:  # a new role: a fresh session
            orc.persona, orc.session, orc.session_tasks = task.persona, "", 0
        related = follow or foreman.related(task, orc)
        task.warm = related and foreman.can_resume(orc)
        orc.status, orc.task = "working", task.id
        if (task.key or task.id) not in orc.keys:     # a rework of a task without a ticket comes back by its id
            orc.keys.append(task.key or task.id)
        repo = self.repo_root
        if self.uses_git:
            task.branch = task.branch or bk.task_branch(self.building_id, task)
            task.base = task.base or self.task_git.base_of(repo, str(self.config.get("base") or ""))
        orc.branch = task.branch
        rework = f" [rework {task.attempts - 1}]" if task.feedback else ""
        self.emit("pool.assigned", f"{orc.name} ({orc.label}) ← {task.title}" + (" [follow-up]" if follow else "")
                  + rework + (" ♻" if task.warm else ""), task.title, ref=task.ref)
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
        """In the orc's thread: the branch, the orc's run, the steward's answers and its review."""
        out = RunOutcome()
        runner = type(self).work_runner or (self._sandbox_work() if self.simulated else jobs.run_work)
        env = {"ORKCRAFT_ORC": f"{self.building_id}/{orc.name.lower()}"}
        git = self.task_git if self.uses_git else None

        def run(p: str, r: str) -> None:
            text, cost, tokens, session = runner(orc.harness, p, workdir, cancel, orc.model, env, r)
            out.text, out.cost, out.tokens = text, out.cost + (cost or 0.0), out.tokens + (tokens or 0)
            out.session = session or out.session

        if task.publish:                         # the approved post: no branch, no review — the operator decided
            git = None
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
            if not out.asked and task.publish:
                out.accepted = True
            elif not out.asked:
                self._call(self._mark, task.id, "reviewing")
                self._review(task, workdir, git, cancel, out)
        except InterruptedError:
            out.error = "stopped"
        except Exception as e:  # one orc's failure must not take the barracks down
            out.error = str(e)[:300]
        self._call(self.finish, task.id, orc.name, out)

    def _sandbox_work(self):
        """The sandbox's ork: its report from `simulated.json` (what the demo wrote), else the plain one."""
        try:
            rules = json.loads((self.state_dir / "simulated.json").read_text(encoding="utf-8")).get("work")
        except (OSError, ValueError, AttributeError):
            rules = None
        return _scripted_work(rules) if isinstance(rules, list) and rules else _simulated_work

    def _call(self, fn, *args) -> None:
        try:
            self.town.call(fn, *args)
        except Exception:
            pass

    def _mark(self, task_id: str, status: str) -> None:
        task = self.state.task(task_id)
        if task is not None and task.status == "working":
            task.status = status
            self.changed()

    def _steward(self, prompt: str, workdir: Path, cancel: threading.Event, out: RunOutcome,
                 use: str = "review", tier: str = plans.REVIEW_TIER) -> str:
        """One model call of the steward's: `use` is its task (plan | answer | review | final), whose tier its
        spec may set (realm/steward.py); else the model of its `steward` setting, else `tier`'s."""
        harness, model = bk.parse_provider(str(self.config.get("steward") or "claude"))
        scroll = getattr(self.town, "scroll", None)
        chosen = steward.tier_for(scroll.building(self.building_id) if scroll is not None else None, use)
        if chosen:
            model = tiers.resolve(harness, chosen)
        elif not model:
            model = tiers.MODELS.get(harness, {}).get(tier, "")
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
        return bk.steward_answer_of(self._steward(prompt, workdir, cancel, out, use="answer"))

    def _review(self, task: bk.PoolTask, workdir: Path, git: jobs.TaskGit | None, cancel: threading.Event,
                out: RunOutcome) -> None:
        """The tests first (cheap and strict), then the steward reads the diff; accepted → the PR — for code
        and documents that go out. A local document (a meeting's prep, notes for the operator) gets no PR."""
        meeting = self._meeting(task)
        draft = bool(bk.publish_of(out.text)[2])          # a post prepared for a service: the report is the work
        diff, tests, files, commits = "", "", [], 0
        if git is not None:
            commits, diff = git.diff(workdir, task.base, task.branch)
            files = out.files = bk.changed_files(diff)
            if commits == 0 and not meeting and not draft:
                out.accepted, out.notes = False, "nothing was committed on the branch — commit your work"
                return
        rule = bk.scope_rule(files, meeting) or (bk.EXTERNAL if draft else "")
        cmd = str(self.config.get("test_cmd") or "") if git is not None and commits and rule != bk.LOCAL else ""
        if cmd:
            passed, tail = git.test(workdir, cmd, cancel)
            if not passed:
                out.accepted, out.notes = False, f"the tests fail (`{cmd}`):\n\n```\n{tail.strip()}\n```"
                return
            tests = f"`{cmd}` passes"
        if task.parent:                                   # a part: no pull request of its own
            if self.goal.sub_review:
                verdict = self._steward(bk.review_prompt(self.keeper, self.orders, task, out.text, diff, tests, bk.LOCAL),
                                        workdir, cancel, out)
                out.accepted, out.notes = bk.verdict_of(verdict)
            else:                                         # 🪙 thrift: the tests are the review
                out.accepted, out.notes = True, tests or "no tests to run"
            if out.accepted and git is not None and commits and task.base:
                self._merge_part(task, out)
            return
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
        if task.publish:                 # the approved draft goes out
            intro = [] if task.warm else [
                f"You are {orc.name}, one of several agents of a barracks.",
                f"## {self.keeper}'s rules\n\n{self.orders}" if self.orders else ""]
            return "\n\n".join(p for p in intro + [bk.publish_prompt(task), ask] if p)
        qa = task.qa + (extra_qa or [])
        decisions = "## Decisions so far\n\n" + "\n".join(f"- {q} → {a}" for q, a, *_ in qa) if qa else ""
        if task.warm:                    # the session already holds the briefing, the rules and the earlier work
            return "\n\n".join(p for p in [
                f"## Task{' (a follow-up of your earlier work)' if follow else ''}: {task.title}", task.text, decisions,
                sent_back,
                f"Your branch is now `{task.branch}`." if task.branch else "",
                "Same rules as before: commit on your branch, then a short Markdown report."] if p)
        persona = personas.load(self.state_dir, orc.persona) if orc.persona else None
        parts = [f"You are {orc.name}, one of several agents working in parallel, each in its own git worktree.",
                 f"## Who you are: {persona.name}\n\n{persona.prompt}" if persona is not None else "",
                 f"Work on the branch `{task.branch}` (it is checked out)." if task.branch else "",
                 "Do the task below in this directory. Commit your work on the branch with a clear message; do not "
                 f"push and do not open a pull request — {self.keeper}, the steward, reviews it and does that.",
                 f"## {self.keeper}'s rules\n\n{self.orders}" if self.orders else "",
                 f"## Task{' (a follow-up of your earlier work)' if follow else ''}: {task.title}", task.text,
                 decisions, sent_back, ask, bk.OUTSIDE_RULE,
                 "This is a local document for a meeting: write it as your report (a commit is optional); it gets "
                 "no pull request." if self._meeting(task) else "",
                 "Finish with a short Markdown report: what you changed, what is left."]
        if related and orc.recent:       # a fresh session on related work: a handoff instead of the whole history
            parts.append("## Your recent work\n\n" + "\n".join(f"- {r}" for r in orc.recent))
        return "\n\n".join(p for p in parts if p)

    def _trail(self, task: bk.PoolTask, orc: bk.PoolOrc, outcome: str) -> tuple:
        """The task's trail with this building's hop: the whole task (every run and review) as one."""
        return pipes.trail_of(task.trail) + (pipes.hop(self.building_id, orc.name, "agent", task.tokens,
                                                       task.cost_usd, orc.worktree, task.branch, outcome,
                                                       base=task.base),)

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
        if out.error and out.error != "stopped" and not task.retried and not task.publish:
            task.retried = True                           # a crash is tried once more, by itself
            st.log(bk.Decision(bk.now_iso(), task.id, "retry", orc.name, f"once more after: {out.error[:200]}"))
            st.tasks.remove(task)
            task.status, task.wait_for, task.error = "queued", orc.name, ""
            st.queue.insert(0, task)
        elif out.error:
            task.status = "failed"
            if task.parent:                               # the whole fails when nothing else runs (_advance)
                st.log(bk.Decision(bk.now_iso(), task.id, "failed", orc.name, f"part `{task.sub}`: {out.error}"))
            else:
                self.emit("pool.failed", f"**{task.title}** — {orc.name}: {out.error}", task.title,
                          trail=self._trail(task, orc, "error"), ref=task.ref)
        elif out.asked:
            self._ask(task, out.asked, f"{orc.name} asks", kind="question")
        elif ok and task.parent:
            self._part_done(task, orc, out)
        elif ok and not task.publish and (draft := bk.publish_of(out.text))[2]:
            task.files = out.files or task.files
            self._wants_approval(task, orc, *draft)
        elif ok:
            published = task.publish
            task.status, task.pr, task.feedback, task.scope = "done", out.pr, "", out.scope
            task.files = out.files or task.files
            task.draft, task.publish = "", ""
            gist = next((ln.strip(" #*") for ln in out.text.splitlines() if ln.strip(" #*")), "")[:160]
            orc.recent = (orc.recent + [f"{task.title} — {gist}" if gist else task.title])[-bk.KEEP_RECENT:]
            local = out.scope == bk.LOCAL
            st.log(bk.Decision(bk.now_iso(), task.id, "publish" if published else "accept", orc.name,
                               f"posted to {task.target or 'its place'} after the operator's approval" if published
                               else ("local, no pull request: " if local else "") + (out.notes or "accepted")))
            where = f"\n\n_pull request:_ {out.pr}" if out.pr else (f"\n\n_branch:_ `{task.branch}`" if task.branch else "")
            note = f" (published to {task.target or 'its place'} after your approval)" if published else \
                " (a local document: no pull request)" if local else \
                (f" ({out.pr_note})" if out.pr_note and not out.pr else "")
            self.emit("pool.done", f"**{task.title}** — {orc.name} ({orc.label})\n\n{out.text}{where}{note}"
                      + self._files_md(task), task.title, trail=self._trail(task, orc, "done"), ref=task.ref)
        else:
            self._rework(task, orc, out.notes)
        if out.error != "stopped" and not out.asked:
            delivery.ran(self.town, roads.HandlerRun(self.building_id, orc.name.lower(), orc.harness, task.id, 0.0, 0.0,
                                                     outcome="done" if ok else "error", markdown=out.text,
                                                     error=out.error or ("" if ok else out.notes),
                                                     cost_usd=out.cost or None))
        if task.parent:
            self._advance(st.task(task.parent))
        self._pump()
        if not st.queue and all(o.status == "idle" for o in st.orcs):
            self.emit("pool.idle", "every task is done" + (f"; {len(st.asked)} wait for you" if st.asked else ""),
                      "queue empty")
        st.save()
        self.changed()

    def _rework(self, task: bk.PoolTask, orc: bk.PoolOrc, notes: str) -> None:
        """Rejected: back to the same orc (in its session) while reworks are left, else to the operator."""
        st, limit = self.state, self.foreman.max_reworks
        task.feedback = notes
        reworks = task.attempts - 1
        st.log(bk.Decision(bk.now_iso(), task.id, "rework", orc.name, f"{reworks + 1}/{limit}: {notes[:200]}"
                           if reworks < limit else f"rejected after {reworks} reworks: {notes[:200]}"))
        if reworks < limit:
            heavier = plans.up(task.tier or orc.tier or "")
            if heavier and self.config.get("escalate", True) is not False and \
                    self.foreman.model_for(orc.harness, heavier) is not None:
                st.log(bk.Decision(bk.now_iso(), task.id, "escalate", orc.name,
                                   f"{task.tier or orc.tier} → {heavier}: a failed try goes up one tier"))
                task.tier = heavier
            st.tasks.remove(task)
            task.status, task.wait_for = "queued", orc.name
            st.queue.insert(0, task)
            return
        self.emit("pool.failed", f"**{task.title}** — rejected after {reworks} reworks: {notes}", task.title,
                  trail=self._trail(task, orc, "error"), ref=task.ref)
        self._ask(task, f"Rejected after {reworks} reworks. Last notes: {notes[:500]}\n\nWhat should {orc.name} do?",
                  "rejected", kind="rejected")

    def _files_md(self, task: bk.PoolTask) -> str:
        if not task.files:
            return ""
        on = f" on `{task.branch}`" if task.branch else ""
        return f"\n\n## Files{on}\n\n" + "\n".join(f"- `{f}`" for f in task.files)

    def _draft_of(self, ref: str) -> bk.PoolTask | None:
        """The task whose draft waits for approval under this `ref`."""
        return next((t for t in self.state.tasks if ref and t.ref == ref and t.status == "asked" and t.draft), None)

    def _wants_approval(self, task: bk.PoolTask, orc: bk.PoolOrc, report: str, target: str, draft: str) -> None:
        """The orc prepared something to go out: nothing is posted until the operator approves it — here (🔥)
        or in a Loot that `pool.question` runs through (accept → it is posted, rework → what to change)."""
        task.target, task.draft = target, draft
        md = (f"**{task.title}** — {orc.name} wants to publish to {target or 'a service'} and waits for your "
              f"approval (accept: it is posted as below, your edits included · send back: what to change)\n\n"
              f"{report.strip()}{self._files_md(task)}\n\n## To publish\n\nPUBLISH: {target}\n\n{draft}")
        self._ask(task, f"Publish to {target or 'a service'}?\n\n{draft}", f"{orc.name} wants to publish", md,
                  trail=self._trail(task, orc, self.APPROVAL), kind="draft")

    def approved(self, payload: pipes.Payload) -> bool:
        """A Loot accepted a waiting draft (perhaps edited there): the orc posts it. False when none waits."""
        task = self._draft_of(payload.ref)
        if task is None:
            return False
        _report, target, draft = bk.publish_of(payload.value)
        self._publish(task, draft or task.draft, target or task.target, "accepted in the review")
        return True

    def _publish(self, task: bk.PoolTask, draft: str, target: str, how: str) -> None:
        st = self.state
        task.publish, task.target, task.draft, task.question = draft, target, "", ""
        task.status, task.wait_for = "queued", task.orc
        st.tasks.remove(task)
        st.queue.insert(0, task)
        st.log(bk.Decision(bk.now_iso(), task.id, "approve", task.orc, f"{how}: publish to {target or 'its place'}"))
        self._pump()
        st.save()
        self.changed()

    def _ask(self, task: bk.PoolTask, question: str, why: str, markdown: str = "", trail: tuple = (),
             kind: str = "question") -> None:
        """🔥 It waits for the operator — or, by its autonomy, for its time (tick_asks): `kind` says what it is."""
        st = self.state
        task.status, task.question = "asked", question
        task.ask_kind, task.waits_since = kind, time.time()
        st.log(bk.Decision(bk.now_iso(), task.id, "ask", task.orc, f"{why}: {question[:200]}"))
        self.emit("pool.question", markdown or f"**{task.title}** — {why}:\n\n{question}", task.title,
                  trail=trail, ref=task.ref)
        self.toast(f"{task.title}: {question[:160]}", title=f"🔥 {self.keeper} asks")

    # -- the operator's answers ------------------------------------------------------------------------

    def answer(self, task_id: str, text: str | None, who: str = "operator") -> str:
        """The operator's answer goes back to the orc that asked (the task returns to its queue). The rule
        the steward proposes from it (a face asks whether to keep it: `add_rule`), "" when none."""
        st = self.state
        task = st.task(task_id)
        if text is None or task is None or task.status != "asked":
            return ""
        if task.persona_waits:                      # a new persona waits for its approval
            self._persona_answer(task, text)
            return ""
        if task.plan:                               # the whole was sent back too often: the operator's word
            return self._plan_answer(task, text) if text.strip() else ""
        if task.draft:                              # a draft waits: nothing typed approves it, else what to change
            if not text.strip() or text.strip().lower() in bk.APPROVE:
                self._publish(task, task.draft, task.target, "the operator approved")
                return ""
            task.feedback, task.draft, task.question = f"Do not post it yet. Change the draft: {text.strip()}", "", ""
            task.status, task.wait_for = "queued", task.orc
            st.tasks.remove(task)
            st.queue.insert(0, task)
            st.log(bk.Decision(bk.now_iso(), task.id, "rework", task.orc, f"draft sent back: {text.strip()[:200]}"))
            self._pump()
            st.save()
            self.changed()
            return ""
        if not text:
            return ""
        question = task.question.split("\n\n")[0]
        task.qa.append([question, text.strip(), who])
        task.ask_kind = ""
        if task.attempts - 1 >= self.foreman.max_reworks:
            task.attempts = 0                       # the operator's word opens a new round of reworks
        task.question, task.status, task.wait_for = "", "queued", task.orc
        st.tasks.remove(task)
        st.queue.insert(0, task)
        st.log(bk.Decision(bk.now_iso(), task.id, "answer", task.orc, f"{who}: {text.strip()[:200]}"))
        self._pump()
        st.save()
        self.changed()
        return f"- {question.strip()[:200]} → {text.strip()[:300]}"

    def add_rule(self, rule: str | None) -> bool:
        if not rule or not rule.strip():
            return False
        orders = self.orders.rstrip()
        ok = self.save_config({"orders": f"{orders}\n{rule.strip()}" if orders else rule.strip()})
        if ok:
            self.changed()
        return ok

    def stop(self) -> int:
        """Every orc and the steward stop where they are (their tasks fail as `stopped`). How many."""
        running = [c for c in self._cancels.values() if not c.is_set()]
        for c in running:
            c.set()
        return len(running)

    def halt(self) -> int:
        """🛑 Halt All: every orc and the steward stop; the barracks pauses (⏸ resumes it)."""
        running = self.stop()
        self.state.paused = True
        self.state.save()
        self.changed()
        return running

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
