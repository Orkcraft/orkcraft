"""🧭 The Barracks' steward plans (design: docs/design/barracks-planning.md §3–4; realm/plans.py).

A task that arrives is judged before any ork takes it:

    simple    the rules are sure (a short task, a follow-up, a rework, an approved post) or the steward
              answers `SIMPLE` → the whole task goes to one ork of the tier the building's goal names
    planned   the steward answers a plan → the task becomes the parent of subtasks: each a task here of
              its own (`parent`, `sub`), with its tier, its persona, the files it touches and the parts it
              waits for. A part starts when what it waits for is merged and nothing running touches its
              files; accepted, its branch is merged into the parent's (`git merge-tree`, no checkout).
              When every part is in, the steward looks at the whole against the request: ACCEPT → one
              pull request; `REWORK: <part>: …` → that part goes back to its ork, `REWORK: new: …` → a
              new part; past `max_reworks` → 🔥 the operator.

A new persona the steward wrote waits as the autonomy level says (autonomy.waits): ⛓️ until the
operator answers, ⏳ the timer (none in quiet hours), ⛓️‍💥 not at all. Only its part waits.

A mixin of BarracksWorker (core/workers/barracks.py): the steward's calls run in threads, what they
come to is applied on the town's thread.
"""
from __future__ import annotations

import threading
import time
import uuid
from dataclasses import asdict

from orkcraft import autonomy, schedule
from orkcraft.core import treasury
from orkcraft.realm import barracks as bk
from orkcraft.realm import personas, pipes, plans, pressure, worktrees

NO = frozenset({"no", "n", "nope", "нет", "не"})
QUOTA_READ_S = 60.0                 # how long one measure of the quota is good for


class PlanMixin:
    # -- what it is ---------------------------------------------------------------------------------

    @property
    def aim(self) -> str:
        b = self.town.scroll.building(self.building_id)
        return b.aim if b is not None else "balance"

    @property
    def goal(self) -> plans.Goal:
        """The building's goal; 🪙 thrift whatever it is while the camp's quota is tight."""
        camp = self.quota()
        return plans.goal_of("thrift" if camp is not None and camp.tight else self.aim)

    def quota(self) -> pressure.Camp | None:
        """What is left of the binding subscription quota (realm/pressure.py, from the town's last quota
        read); None with no read, no subscription or nothing spent yet. Measured once a minute."""
        now = time.monotonic()
        cached = getattr(self, "_quota_cache", None)
        if cached is not None and now - cached[0] < QUOTA_READ_S:
            return cached[1]
        camp = None
        subs = treasury.subscriptions(self.town.machine)
        limits = getattr(self.town, "limits", None) or []
        if subs and limits and not self.simulated:
            try:
                camp = pressure.measure(self.repo_root, limits, providers=subs)
            except Exception:  # a quota that cannot be measured never stops a plan
                camp = None
        camp = camp if camp is not None and camp.left is not None else None
        self._quota_cache = (now, camp)
        return camp

    @property
    def rules(self) -> autonomy.Rules:
        """Its autonomy: its own level and waits (its steward's window), else the town's."""
        m = self.town.machine
        return autonomy.rules_of(self.town.scroll.building(self.building_id), m.autonomy, m.autonomy_wait,
                                 m.rebuild_wait)

    @property
    def plans_on(self) -> bool:
        """The steward plans hard tasks (config `plan`, on by default); never in the sandbox."""
        return self.config.get("plan", True) is not False and not self.simulated

    def children(self, parent: bk.PoolTask) -> list[bk.PoolTask]:
        st = self.state
        return [t for t in st.queue + st.tasks if t.parent == parent.id]

    # -- the triage -----------------------------------------------------------------------------------

    def _triaged(self, task: bk.PoolTask) -> bool:
        """True when the task can go to the foreman now; False when the steward plans it first. A simple
        one gets the tier its goal names; a follow-up, a rework or a post keeps its ork's."""
        if task.tier or task.parent or task.plan:
            return True
        st = self.state
        known = self.foreman.follow_up_of(task, st.orcs)[0] is not None
        if known or task.feedback or task.publish or task.qa or task.branch or self._meeting(task):
            return True
        if not self.plans_on or plans.clearly_simple(task.title, task.text):
            task.tier = self.goal.simple
            return True
        self._plan(task)
        return False

    def _plan(self, task: bk.PoolTask) -> None:
        st = self.state
        if task in st.queue:
            st.queue.remove(task)
        task.status = "planning"
        if task not in st.tasks:
            st.tasks.append(task)
        st.log(bk.Decision(bk.now_iso(), task.id, "plan", why=f"{self.keeper} plans it"))
        prompt = plans.plan_prompt(self.keeper, self.orders, task.title, task.text, self.aim,
                                   self.goal.parallel or self.foreman.max_orcs, personas.listing(self.state_dir))
        cancel = threading.Event()
        self._cancels[f"plan:{task.id}"] = cancel

        def work() -> None:
            from orkcraft.core.workers.barracks import RunOutcome
            out = RunOutcome()
            subs, errors = None, []
            try:
                text = self._steward(prompt, self.repo_root, cancel, out, "plan", plans.PLAN_TIER)
                subs, errors = plans.parse(text)
                if errors:                                    # once more, with what was wrong
                    text = self._steward(prompt + "\n\n## Your last plan did not hold\n\n" + "\n".join(
                        f"- {e}" for e in errors), self.repo_root, cancel, out, "plan", plans.PLAN_TIER)
                    subs, errors = plans.parse(text)
            except InterruptedError:
                out.error = "stopped"
            except Exception as e:  # the steward that cannot plan never stops the task
                errors = [str(e)[:200]]
            self._call(self._planned, task.id, subs, errors, out)

        threading.Thread(target=work, daemon=True, name=f"plan-{self.building_id}-{task.id}").start()

    def _planned(self, task_id: str, subs: list[plans.Sub] | None, errors: list[str], out) -> None:
        st = self.state
        self._cancels.pop(f"plan:{task_id}", None)
        task = st.task(task_id)
        st.steward_cost = round(st.steward_cost + out.steward_cost, 4)
        if task is None or task.status != "planning":
            return
        task.cost_usd = round((task.cost_usd or 0.0) + out.steward_cost, 4) or None
        if out.error == "stopped":
            self._whole(task, "", "the plan was stopped")
        elif errors:
            self._whole(task, "warrior", "the plan did not hold (" + "; ".join(errors)[:300] + ")")
        elif subs is None:
            self._whole(task, self.goal.simple, f"{self.keeper}: simple")
        elif len(subs) == 1:
            one = subs[0]
            task.persona = self._persona_of(one)
            self._whole(task, plans.shift(one.tier, self.goal.shift), f"{self.keeper}: one part")
        else:
            self._split(task, subs)
        self._pump()
        st.save()
        self.changed()

    def _whole(self, task: bk.PoolTask, tier: str, why: str) -> None:
        """The task runs whole, on one ork (of `tier`)."""
        st = self.state
        task.tier = tier or self.goal.simple
        task.status = "queued"
        if task in st.tasks:
            st.tasks.remove(task)
        st.queue.insert(0, task)
        st.log(bk.Decision(bk.now_iso(), task.id, "plan", why=f"whole, {task.tier}: {why}"))
        self._dispatch(task)

    def _persona_of(self, sub: plans.Sub) -> str:
        """The persona a part names, kept or written now (unapproved); "" when it names none it can have."""
        if not sub.persona:
            return ""
        if personas.load(self.state_dir, sub.persona) is not None:
            return sub.persona
        if not sub.persona_prompt:
            return ""
        personas.save(self.state_dir, personas.Persona(sub.persona, sub.persona_prompt, sub.tier))
        self.state.log(bk.Decision(bk.now_iso(), "", "persona", why=f"{self.keeper} wrote `{sub.persona}` ({sub.tier})"))
        return sub.persona

    def _split(self, task: bk.PoolTask, subs: list[plans.Sub]) -> None:
        st, f, goal, camp = self.state, self.foreman, self.goal, self.quota()
        for s in subs:
            s.tier = plans.shift(s.tier, goal.shift)
        left = round(f.budget - st.spent, 4) if f.budget else None
        tokens_left = camp.left * plans.QUOTA_SHARE if camp is not None else None
        costs, per = plans.tier_costs(st.stats), plans.tier_tokens(st.stats)
        limits = " · ".join(x for x in (f"${left:.2f} left" if left is not None else "",
                                        f"~{camp.left / 1000:.0f}k tokens left of {camp.limit} (a plan takes at most "
                                        f"{plans.QUOTA_SHARE:.0%})" if camp is not None else "") if x)
        fits, lowered = plans.trim(subs, left, costs, tokens_left, per)
        if lowered:
            st.log(bk.Decision(bk.now_iso(), task.id, "trim", why=f"{limits}: " + ", ".join(lowered)))
        estimate = f"≈{plans.tokens(subs, per) / 1000:.0f}k tokens, ${plans.cost(subs, costs):.2f}"
        if not fits:
            self._whole(task, goal.simple, f"the plan of {len(subs)} parts ({estimate}) does not fit: {limits}")
            return
        if self.uses_git:
            task.branch = task.branch or bk.task_branch(self.building_id, task)
            task.base = task.base or self.task_git.base_of(self.repo_root, str(self.config.get("base") or ""))
            try:
                self.task_git.cut(self.repo_root, task.branch, task.base)
            except Exception as e:  # no branch to merge into: the task runs whole
                self._whole(task, "warrior", f"no branch {task.branch}: {e}")
                return
        task.status, task.plan = "planned", [asdict(s) for s in subs]
        for s in subs:
            cid = uuid.uuid4().hex[:8]
            child = bk.PoolTask(cid, f"{task.title[:50]} · {s.title}"[:80], plans.child_text(task.title, task.text, s, subs),
                                arrived=bk.now_iso(), status="blocked", tier=s.tier, persona=self._persona_of(s),
                                parent=task.id, sub=s.id, after=list(s.after), touches=list(s.touches),
                                cheaper_ok=s.cheaper_ok, ref=f"{self.building_id}:{cid}",
                                branch=f"{task.branch}--{s.id}" if task.branch else "", base=task.branch)
            st.tasks.append(child)
        parts = ", ".join(f"{s.id} ({s.tier}{', ' + s.persona if s.persona else ''})" for s in subs)
        tight = "; the quota is tight: 🪙 thrift" if camp is not None and camp.tight else ""
        st.log(bk.Decision(bk.now_iso(), task.id, "plan", why=f"{len(subs)} parts, {estimate}{tight}: {parts}"))
        self.emit("pool.assigned", f"{self.keeper} planned **{task.title}** in {len(subs)} parts: {parts}",
                  task.title, ref=task.ref)
        self._advance(task)

    # -- the parts --------------------------------------------------------------------------------------

    def _advance(self, parent: bk.PoolTask | None) -> None:
        """Start the parts that may start; when every part is in, the steward's last look; when a part
        failed and nothing runs any more, the task fails."""
        if parent is None or parent.status != "planned":
            return
        st, kids = self.state, self.children(parent)
        running = [k for k in kids if k.status in ("queued", "working", "reviewing", "asked")]
        if kids and all(k.status == "done" for k in kids):
            self._final(parent)
            return
        failed = [k for k in kids if k.status == "failed"]
        if failed and not running:
            parent.status = "failed"
            parent.error = "; ".join(f"{k.sub}: {k.error or 'failed'}" for k in failed)[:300]
            st.log(bk.Decision(bk.now_iso(), parent.id, "failed", why=parent.error))
            self.emit("pool.failed", f"**{parent.title}** — a part failed: {parent.error}", parent.title,
                      trail=self._plan_trail(parent, "error"), ref=parent.ref)
            return
        if failed:
            return                                    # what runs finishes; nothing new starts
        for k in plans.ready(kids, self.goal.parallel or self.foreman.max_orcs):
            p = personas.load(self.state_dir, k.persona) if k.persona else None
            if p is not None and not p.approved:
                self._persona_waits(k, p)
                continue
            self._release(k)

    def _release(self, kid: bk.PoolTask) -> None:
        st = self.state
        if kid in st.tasks:
            st.tasks.remove(kid)
        kid.status, kid.question, kid.persona_waits, kid.waits_since = "queued", "", "", 0.0
        st.queue.append(kid)

    def _persona_waits(self, kid: bk.PoolTask, p: personas.Persona) -> None:
        """A part whose new persona is not approved yet: at once at ⛓️‍💥 (and ⏳ in quiet hours), else 🔥."""
        machine, rules = self.town.machine, self.rules
        if autonomy.waits(rules.level, schedule.quiet_now(machine), rules.wait) == 0:
            self._approve_persona(p.name, "the orks took it (autonomy)", advance=False)
            self._release(kid)
            return
        kid.persona_waits = p.name
        timer = autonomy.waits(rules.level, False, rules.wait)
        when = f" — approved by itself in {timer:.0f} min" if timer else ""
        self._ask(kid, f"New persona `{p.name}` ({p.tier}) for “{kid.title}”{when}:\n\n{p.prompt}\n\nApprove it "
                  "(Enter or yes), write a better one, or `no` to run this part without a persona.",
                  f"{self.keeper} wrote a new persona", kind="persona")

    def _approve_persona(self, name: str, how: str, prompt: str = "", advance: bool = True) -> None:
        """The persona is approved (`prompt`: the operator's own); every part that waited for it goes on."""
        p = personas.load(self.state_dir, name)
        if p is not None:
            p.approved = True
            if prompt:
                p.prompt, p.by = prompt, "operator"
            personas.save(self.state_dir, p)
        self.state.log(bk.Decision(bk.now_iso(), "", "persona", why=f"`{name}` approved: {how}"))
        for kid in [t for t in self.state.tasks if t.persona_waits == name]:
            self._release(kid)
        if advance:
            for pid in dict.fromkeys(t.parent for t in self.state.tasks if t.parent):
                self._advance(self.state.task(pid))

    def tick_asks(self, now: float | None = None) -> bool:
        """🕰 What waited for the operator its minutes (at once in quiet hours, or unchained): the orks decide —
        a new persona is approved, a question the steward answers itself, a task sent back too often is
        closed as failed. A draft to post outside always waits for the operator."""
        rules = self.rules
        minutes = autonomy.waits(rules.level, schedule.quiet_now(self.town.machine), rules.wait)
        if minutes is None:
            return False
        now = time.time() if now is None else now
        due = [t for t in self.state.tasks if t.status == "asked" and now - t.waits_since >= minutes * 60
               and (t.ask_kind or ("persona" if t.persona_waits else "")) in ("question", "rejected", "persona")]
        why = f"nobody answered in {minutes:.0f} min" if minutes else "the orks decide at once (autonomy)"
        for name in sorted({t.persona_waits for t in due if t.persona_waits}):
            self._approve_persona(name, why)
        for t in due:
            if t.persona_waits:
                continue
            if t.ask_kind == "rejected":
                self._give_up(t, why)
            else:
                self._steward_decides(t, why)
        if due:
            self._pump()
            self.state.save()
            self.changed()
        return bool(due)


    def _give_up(self, task: bk.PoolTask, why: str) -> None:
        """A task sent back too often that nobody answered: closed as failed, with what was wrong."""
        st = self.state
        last = task.question.split("Last notes: ", 1)[-1].split("\n\n")[0][:300]
        task.status, task.question, task.ask_kind = "failed", "", ""
        task.error = f"sent back too often and {why}: closed by {self.keeper}. Last notes: {last}"
        st.log(bk.Decision(bk.now_iso(), task.id, "close", task.orc, task.error[:300]))
        if task.parent:
            self._advance(st.task(task.parent))
            return
        orc = st.orc(task.orc)
        trail = self._plan_trail(task, "error") if task.plan or orc is None else self._trail(task, orc, "error")
        self.emit("pool.failed", f"**{task.title}** — {task.error}", task.title, trail=trail, ref=task.ref)

    def _steward_decides(self, task: bk.PoolTask, why: str) -> None:
        """A question nobody answered: the steward decides it by its rules; when it cannot, the task is closed."""
        task.ask_kind = "deciding"
        question = task.question.split("\n\n")[0]
        prompt = bk.steward_question_prompt(self.keeper, self.orders, task, question) + (
            f"\n\nThe operator was asked and {why}: decide it yourself now, by your rules and good practice. "
            "`ASK` is not possible — answer `ANSWER: …`.")
        cancel = threading.Event()
        self._cancels[f"decide:{task.id}"] = cancel

        def work() -> None:
            from orkcraft.core.workers.barracks import RunOutcome
            out = RunOutcome()
            answer = ""
            try:
                answer = bk.steward_answer_of(self._steward(prompt, self.repo_root, cancel, out, "answer"))
            except Exception:  # a steward that cannot answer closes the task, never the barracks
                answer = ""
            self._call(self._decided, task.id, answer, why, out)

        threading.Thread(target=work, daemon=True, name=f"decide-{self.building_id}-{task.id}").start()

    def _decided(self, task_id: str, answer: str, why: str, out) -> None:
        st = self.state
        self._cancels.pop(f"decide:{task_id}", None)
        st.steward_cost = round(st.steward_cost + out.steward_cost, 4)
        task = st.task(task_id)
        if task is None or task.status != "asked":          # the operator answered meanwhile
            return
        if answer:
            self.answer(task.id, answer, who=self.keeper)
            return
        task.ask_kind = "rejected"
        self._give_up(task, f"{why} and {self.keeper} could not decide")
        self._pump()
        st.save()
        self.changed()

    def _persona_answer(self, task: bk.PoolTask, text: str) -> None:
        """The operator on a new persona: Enter / yes approves it, `no` drops it from this part, anything
        else is the persona's prompt in their words."""
        said = text.strip()
        if not said or said.lower() in bk.APPROVE:
            self._approve_persona(task.persona_waits, "the operator approved it")
        elif said.lower() in NO:
            self.state.log(bk.Decision(bk.now_iso(), task.id, "persona", why=f"`{task.persona_waits}` refused"))
            task.persona = ""
            self._release(task)
        else:
            self._approve_persona(task.persona_waits, "the operator rewrote it", said)
        self._pump()
        self.state.save()
        self.changed()

    def _merge_part(self, task: bk.PoolTask, out) -> None:
        """In the ork's thread, after the part was accepted: its branch into the parent's."""
        git = self.task_git
        with self._merge_lock:
            try:
                ok, note = git.merge(self.repo_root, task.base, task.branch, f"Merge part `{task.sub}`: {task.title}")
            except Exception as e:  # a merge that cannot run is the steward's to report, not a crash
                ok, note = False, str(e)[:300]
        if not ok:
            out.accepted = False
            out.notes = (f"Your branch does not merge into `{task.base}` ({note}): the other parts are merged there. "
                         f"Merge `{task.base}` into your branch, resolve the conflicts, keep both sides' intent, commit.")

    def _part_done(self, task: bk.PoolTask, orc: bk.PoolOrc, out) -> None:
        """A part accepted and merged: no pull request of its own — the whole gets one."""
        st = self.state
        task.status, task.feedback = "done", ""
        task.files = out.files or task.files
        gist = next((ln.strip(" #*") for ln in out.text.splitlines() if ln.strip(" #*")), "")[:160]
        orc.recent = (orc.recent + [f"{task.title} — {gist}" if gist else task.title])[-bk.KEEP_RECENT:]
        st.log(bk.Decision(bk.now_iso(), task.id, "merge", orc.name,
                           f"part `{task.sub}` accepted" + (f", merged into {task.base}" if task.base else "")
                           + (f": {out.notes}" if out.notes else "")))

    # -- the whole ------------------------------------------------------------------------------------

    def _final(self, parent: bk.PoolTask) -> None:
        """Every part is in: in a thread, the tests of the merged branch and the steward's last look."""
        st = self.state
        parent.status = "reviewing"
        kids = self.children(parent)
        reports = [(k.sub, k.result) for k in kids]
        cancel = threading.Event()
        self._cancels[f"final:{parent.id}"] = cancel
        git = self.task_git if self.uses_git else None
        cmd = str(self.config.get("test_cmd") or "")
        goal = self.goal
        st.log(bk.Decision(bk.now_iso(), parent.id, "review", why=f"every part is in: {self.keeper} looks at the whole"))

        def work() -> None:
            from orkcraft.core.workers.barracks import RunOutcome
            out = RunOutcome()
            try:
                diff, tests, commits = "", "", 0
                if git is not None and parent.branch:
                    commits, diff = git.diff(self.repo_root, parent.base, parent.branch)
                    out.files = bk.changed_files(diff)
                    if cmd and commits:
                        where = worktrees.worktree_path(self.repo_root, f"pool-{self.building_id}-steward".replace("_", "-"))
                        passed, tail = git.check(self.repo_root, parent.branch, cmd, cancel, where)
                        if not passed:
                            out.accepted = False
                            out.notes = f"new: the tests of the merged parts fail (`{cmd}`):\n\n```\n{tail.strip()}\n```"
                            raise _Done
                        tests = f"`{cmd}` passes on the merged branch"
                verdict = self._steward(plans.final_prompt(self.keeper, self.orders, parent.title, parent.text,
                                                           parent.plan, reports, diff, tests, bk.DIFF_LIMIT),
                                        self.repo_root, cancel, out, "final", goal.final)
                out.accepted, out.notes = bk.verdict_of(verdict)
                if out.accepted and git is not None and commits:
                    body = f"{parent.text}\n\n---\n\n" + "\n\n".join(
                        f"### {sub}\n\n{rep.strip()[:1500]}" for sub, rep in reports) + \
                        f"\n\n_Planned and reviewed by {self.keeper}: {out.notes or 'accepted'}_"
                    out.pr, out.pr_note = git.publish(self.repo_root, parent.branch, parent.base, parent.title, body)
            except _Done:
                pass
            except InterruptedError:
                out.error = "stopped"
            except Exception as e:  # the steward's failure fails the task, never the barracks
                out.error = str(e)[:300]
            self._call(self._finalized, parent.id, out)

        threading.Thread(target=work, daemon=True, name=f"final-{self.building_id}-{parent.id}").start()

    def _finalized(self, parent_id: str, out) -> None:
        st = self.state
        self._cancels.pop(f"final:{parent_id}", None)
        parent = st.task(parent_id)
        st.steward_cost = round(st.steward_cost + out.steward_cost, 4)
        if parent is None or parent.status != "reviewing":
            return
        kids = self.children(parent)
        parent.cost_usd = round((parent.cost_usd or 0.0) + out.steward_cost + sum(k.cost_usd or 0.0 for k in kids), 4)
        parent.files = out.files or parent.files
        if out.error:
            parent.status, parent.error = "failed", out.error
            self.emit("pool.failed", f"**{parent.title}** — {self.keeper}: {out.error}", parent.title,
                      trail=self._plan_trail(parent, "error"), ref=parent.ref)
        elif out.accepted:
            parent.status, parent.pr, parent.scope, parent.feedback = "done", out.pr, bk.EXTERNAL, ""
            parent.result = "\n\n".join(f"### {k.title}\n\n{k.result.strip()}" for k in kids)
            st.log(bk.Decision(bk.now_iso(), parent.id, "accept", why=out.notes or "the whole is accepted"))
            orks = ", ".join(dict.fromkeys(k.orc for k in kids if k.orc))
            where = f"\n\n_pull request:_ {out.pr}" if out.pr else (f"\n\n_branch:_ `{parent.branch}`" if parent.branch else "")
            note = f" ({out.pr_note})" if out.pr_note and not out.pr else ""
            self.emit("pool.done", f"**{parent.title}** — {len(kids)} parts by {orks}, planned and reviewed by "
                      f"{self.keeper}\n\n{parent.result}{where}{note}" + self._files_md(parent), parent.title,
                      trail=self._plan_trail(parent, "done"), ref=parent.ref)
        else:
            self._rework_whole(parent, kids, out.notes)
        self._pump()
        st.save()
        self.changed()

    def _rework_whole(self, parent: bk.PoolTask, kids: list[bk.PoolTask], notes: str) -> None:
        """The whole is sent back: the part it names goes back to its ork, or a new part is added; past
        `max_reworks` the operator decides."""
        st, limit = self.state, self.foreman.max_reworks
        parent.attempts += 1
        parent.status = "planned"
        if parent.attempts > limit:
            self._ask(parent, f"The whole was sent back {parent.attempts - 1} times. Last notes: {notes[:500]}\n\n"
                      "What should be done? Your answer becomes a new part.", "rejected", kind="rejected")
            return
        sub, why = plans.rework_of(notes, [k.sub for k in kids])
        st.log(bk.Decision(bk.now_iso(), parent.id, "rework", why=f"{parent.attempts}/{limit}: "
                           + (f"part `{sub}`: " if sub else "a new part: ") + why[:200]))
        kid = next((k for k in kids if k.sub == sub), None)
        if kid is not None:
            st.tasks.remove(kid)
            kid.status, kid.feedback = "queued", why
            kid.wait_for = kid.orc if st.orc(kid.orc) is not None else ""
            st.queue.insert(0, kid)
        else:
            self._add_part(parent, why, "warrior")
        self._advance(parent)

    def _add_part(self, parent: bk.PoolTask, brief: str, tier: str) -> bk.PoolTask:
        """A part nobody planned: what the last look found missing, or the operator's word."""
        st = self.state
        n = sum(1 for k in self.children(parent) if k.sub.startswith("fix")) + 1
        sub = plans.Sub(f"fix{n}", f"Fix {n}", brief, tier)
        parent.plan = parent.plan + [asdict(sub)]
        cid = uuid.uuid4().hex[:8]
        kid = bk.PoolTask(cid, f"{parent.title[:50]} · {sub.title}", plans.child_text(parent.title, parent.text, sub, []),
                          arrived=bk.now_iso(), status="blocked", tier=tier, parent=parent.id, sub=sub.id,
                          ref=f"{self.building_id}:{cid}", branch=f"{parent.branch}--{sub.id}" if parent.branch else "",
                          base=parent.branch)
        st.tasks.append(kid)
        return kid

    def _plan_answer(self, parent: bk.PoolTask, text: str) -> str:
        """The operator's word on a whole sent back too often: a new part, and a new round of reworks."""
        question = parent.question.split("\n\n")[0]
        parent.qa.append([question, text.strip(), "operator"])
        parent.question, parent.status, parent.attempts = "", "planned", 0
        self._add_part(parent, text.strip(), "warrior")
        self.state.log(bk.Decision(bk.now_iso(), parent.id, "answer", why=f"operator: {text.strip()[:200]}"))
        self._advance(parent)
        self._pump()
        self.state.save()
        self.changed()
        return f"- {question.strip()[:200]} → {text.strip()[:300]}"

    def _plan_trail(self, parent: bk.PoolTask, outcome: str) -> tuple:
        return pipes.trail_of(parent.trail) + (pipes.hop(self.building_id, self.keeper, "agent", parent.tokens,
                                                         parent.cost_usd, "", parent.branch, outcome,
                                                         base=parent.base),)


class _Done(Exception):
    """The last look ended early (the tests of the whole failed)."""
