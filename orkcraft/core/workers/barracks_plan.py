"""🧭 The Barracks' steward plans (design: docs/design/barracks-planning.md §3–4; realm/plans.py).

A task that arrives is judged before any ork takes it:

    simple    a follow-up, a rework or an approved post → the whole task goes to the ork that knows it
    sorted    else the steward's light look (its `triage`, realm/steward.py `WORK`): `trivial` → one light ork at once, no
              review but its tests; `single` → one ork of the tier the sort names, then the review;
              `plan` (stages, parallel parts) → the steward plans it on the goal's tier (its `plan`).
              A short task with no steps (`plans.clearly_simple`) is never planned: with a `test_cmd` it
              is not even sorted — one ork of the goal's tier, its tests the review (trivial); without
              one, not trivial, it goes to one ork of the tier the building's goal names, reviewed
    planned   the steward answers `SIMPLE` (one ork, as `simple`) or a plan → the task becomes the parent
              of subtasks: each a task here of its own (`parent`, `sub`), with its tier, its persona, the
              files it touches and the parts it waits for. A part starts when what it waits for is
              merged and nothing running touches its files; accepted, its branch is merged into the
              parent's (`git merge-tree`, no checkout).
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
from orkcraft.realm import barracks as bk
from orkcraft.realm import briefs, claims, personas, pipes, plans, steward, worktrees

NO = frozenset({"no", "n", "nope", "нет", "не"})


class PlanMixin:
    # -- what it is ---------------------------------------------------------------------------------

    @property
    def plan_tier(self) -> str:
        """The tier the steward plans on now: the one picked for it, else its goal's (realm/steward.py)."""
        scroll = getattr(self.town, "scroll", None)
        p = steward.pick(scroll.building(self.building_id) if scroll is not None else None, "plan",
                         type_id=self.TYPE, goal=self.aim_now)
        return p.tier or "the default model"

    @property
    def goal(self) -> plans.Goal:
        """The building's goal for its orks; 🪙 thrift whatever it is while the camp's quota is tight."""
        return plans.goal_of(self.aim_now)

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
        if task.want == pipes.REPLY and not task.publish:   # a reply: one light ork, never planned (§6)
            self.reply_ready(task)
            return True
        if task.tier or task.parent or task.plan:
            return True
        st = self.state
        known = self.foreman.follow_up_of(task, st.orcs)[0] is not None
        if known or task.feedback or task.publish or task.qa or task.branch or self._meeting(task):
            return True
        if not self.plans_on:
            task.tier = self.goal.simple
            return True
        short = plans.clearly_simple(task.title, task.text)
        if short and self.config.get("test_cmd"):         # its tests judge it: no steward call before or after
            task.kind, task.tier = plans.TRIVIAL, self.goal.simple
            st.log(bk.Decision(bk.now_iso(), task.id, "plan", why=f"whole, {task.tier}: short, its tests judge it"))
            return True
        self._triage(task, short=short)
        return False

    def _take(self, task: bk.PoolTask, why: str) -> threading.Event:
        """The task leaves the queue while the steward looks at it (`planning`: a restart sorts it again)."""
        st = self.state
        if task in st.queue:
            st.queue.remove(task)
        task.status = "planning"
        if task not in st.tasks:
            st.tasks.append(task)
        st.log(bk.Decision(bk.now_iso(), task.id, "plan", why=why))
        cancel = threading.Event()
        self._cancels[f"plan:{task.id}"] = cancel
        return cancel

    def _triage(self, task: bk.PoolTask, short: bool = False) -> None:
        """The steward's light look (its `triage`): trivial and single go to one ork at once, a task of
        stages or parallel parts is planned. A sort that does not hold is planned too, as before the triage.
        `short`: the rules are sure it needs no plan — it is only told trivial (no review) from the rest."""
        cancel = self._take(task, f"{self.keeper} sorts it")
        prompt = plans.triage_prompt(self.keeper, self.orders, task.title, bk.body_of(task))

        def work() -> None:
            from orkcraft.core.workers.barracks import RunOutcome
            out, sort = RunOutcome(), None
            try:
                sort = plans.parse_triage(self._steward(prompt, self.code_root, cancel, out, "triage"))
            except InterruptedError:
                out.error = "stopped"
            except Exception:  # a steward that cannot sort never stops the task: it is planned
                sort = None
            self._call(self._sorted, task.id, sort, out, short)

        threading.Thread(target=work, daemon=True, name=f"triage-{self.building_id}-{task.id}").start()

    def _sorted(self, task_id: str, sort: plans.Triage | None, out, short: bool = False) -> None:
        st = self.state
        self._cancels.pop(f"plan:{task_id}", None)
        task = st.task(task_id)
        st.steward_cost = round(st.steward_cost + out.steward_cost, 4)
        if task is None or task.status != "planning":
            return
        task.cost_usd = round((task.cost_usd or 0.0) + out.steward_cost, 4) or None
        if sort is not None and sort.touches:
            task.claimed = claims.narrow(sort.touches)   # its likely area: the briefs it concerns, the claim
        if out.error == "stopped":
            self._whole(task, "", "the sort was stopped")
        elif sort is not None and self.sorted_want(task, sort.want):  # only a reply: a lower path (§5 step 3)
            self.reply_ready(task)
            self._whole(task, task.tier, f"{self.keeper}: a reply" + (f" — {sort.why}" if sort.why else ""))
        elif short and (sort is None or sort.kind != plans.TRIVIAL):     # no plan for it: one light ork, reviewed
            task.kind = plans.SINGLE
            self._claim(task, sort.touches if sort else [], True)
            self._whole(task, self.goal.simple, "short and clear" + (f" — {sort.why}" if sort and sort.why else ""))
        elif sort is None or sort.kind == plans.PLAN:
            task.kind = plans.PLAN
            why = f": {sort.why}" if sort is not None and sort.why else ""
            self._plan(task, f"{self.keeper} plans it ({self.plan_tier}){why}")
        else:
            task.kind = sort.kind
            self._claim(task, sort.touches, True)
            tier = self.goal.simple if sort.kind == plans.TRIVIAL else plans.shift(sort.tier, self.goal.shift)
            self._whole(task, tier, f"{self.keeper}: {sort.kind}" + (f" — {sort.why}" if sort.why else ""))
        st.save()
        self.changed()

    def _plan(self, task: bk.PoolTask, why: str = "") -> None:
        cancel = self._take(task, why or f"{self.keeper} plans it")
        prompt = plans.plan_prompt(self.keeper, self.orders, task.title, bk.body_of(task), self.aim,
                                   self.goal.parallel or self.foreman.max_orcs, personas.listing(self.state_dir),
                                   designs=self.plan_designs(task), brief=self.briefs_on,
                                   short=self.goal == plans.GOALS["thrift"])

        def work() -> None:
            from orkcraft.core.workers.barracks import RunOutcome
            out = RunOutcome()
            subs, errors, extra = None, [], ({}, [])
            try:
                text = self._steward(prompt, self.code_root, cancel, out, "plan")
                subs, errors = plans.parse(text)
                if errors:                                    # once more, with what was wrong
                    text = self._steward(prompt + "\n\n## Your last plan did not hold\n\n" + "\n".join(
                        f"- {e}" for e in errors), self.code_root, cancel, out, "plan")
                    subs, errors = plans.parse(text)
                extra = plans.extras(text)
            except InterruptedError:
                out.error = "stopped"
            except Exception as e:  # the steward that cannot plan never stops the task
                errors = [str(e)[:200]]
            self._call(self._planned, task.id, subs, errors, out, extra)

        threading.Thread(target=work, daemon=True, name=f"plan-{self.building_id}-{task.id}").start()

    def _planned(self, task_id: str, subs: list[plans.Sub] | None, errors: list[str], out,
                 extra: tuple[dict, list[dict]] = ({}, [])) -> None:
        st = self.state
        self._cancels.pop(f"plan:{task_id}", None)
        task = st.task(task_id)
        st.steward_cost = round(st.steward_cost + out.steward_cost, 4)
        if task is None or task.status != "planning":
            return
        task.cost_usd = round((task.cost_usd or 0.0) + out.steward_cost, 4) or None
        design, against = extra
        if against and not out.error and not errors:      # it goes against a design brief: said, maybe asked
            task.against = against
            st.log(bk.Decision(bk.now_iso(), task.id, "design", why="goes against " + "; ".join(
                f"{c['with']}: {c.get('why') or '?'}" for c in against)[:300]))
        if out.error == "stopped":
            self._whole(task, "", "the plan was stopped")
        elif errors:
            self._whole(task, "warrior", "the plan did not hold (" + "; ".join(errors)[:300] + ")")
        elif subs is None:
            self._whole(task, self.goal.simple, f"{self.keeper}: simple")
        elif len(subs) == 1:
            one = subs[0]
            task.claimed = claims.narrow(one.touches) or task.claimed
            task.persona = self._persona_of(one)
            self._whole(task, plans.shift(one.tier, self.goal.shift), f"{self.keeper}: one part")
        elif against and autonomy.waits(self.rules.level, schedule.quiet_now(self.town.machine), self.rules.wait) != 0:
            self.hold_plan(task, subs, design)               # ⛓️ / 🕰: the operator first
        else:
            self._split(task, subs, design)
        self._pump()
        st.save()
        self.changed()

    def _whole(self, task: bk.PoolTask, tier: str, why: str) -> None:
        """The task runs whole, on one ork (of `tier`)."""
        st = self.state
        if task.claimed:                                  # its area: the sort's guess, or its one part's
            self._claim(task, task.claimed, True)
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

    def _split(self, task: bk.PoolTask, subs: list[plans.Sub], design: dict | None = None) -> None:
        st, f, goal, camp = self.state, self.foreman, self.goal, self.quota()
        for s in subs:
            s.tier = plans.shift(s.tier, goal.shift)
        left = round(f.budget - st.spent, 4) if f.budget and f.priced else None
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
            task.base = task.base or self.task_git.base_of(self.code_root, str(self.config.get("base") or ""))
            try:
                self.task_git.cut(self.code_root, task.branch, task.base)
            except Exception as e:  # no branch to merge into: the task runs whole
                self._whole(task, "warrior", f"no branch {task.branch}: {e}")
                return
            self.write_brief(task, subs, design or {})     # before any part is cut from the branch
        task.status, task.plan = "planned", [asdict(s) for s in subs]
        for s in subs:
            cid = uuid.uuid4().hex[:8]
            child = bk.PoolTask(cid, f"{task.title[:50]} · {s.title}"[:80], plans.child_text(task.title, bk.body_of(task), s, subs),
                                arrived=bk.now_iso(), status="blocked", tier=s.tier, persona=self._persona_of(s),
                                parent=task.id, sub=s.id, after=list(s.after), touches=list(s.touches),
                                cheaper_ok=s.cheaper_ok, ref=f"{self.building_id}:{cid}", want=task.want,
                                want_by=task.want_by,
                                branch=f"{task.branch}--{s.id}" if task.branch else "", base=task.branch)
            st.tasks.append(child)
        parts = ", ".join(f"{s.id} ({s.tier}{', ' + s.persona if s.persona else ''})" for s in subs)
        tight = "; the quota is tight: 🪙 thrift" if camp is not None and camp.tight else ""
        st.log(bk.Decision(bk.now_iso(), task.id, "plan", why=f"{len(subs)} parts, {estimate}{tight}: {parts}"))
        self.emit("pool.assigned", f"{self.keeper} planned **{task.title}** in {len(subs)} parts: {parts}",
                  task.title, ref=task.ref, want=task.want)
        self._claim(task, [t for s in subs for t in s.touches] + ([task.design] if task.design else []), False)
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
            self._unclaim(parent)
            parent.error = "; ".join(f"{k.sub}: {k.error or 'failed'}" for k in failed)[:300]
            st.log(bk.Decision(bk.now_iso(), parent.id, "failed", why=parent.error))
            self.emit("pool.failed", f"**{parent.title}** — a part failed: {parent.error}", parent.title,
                      trail=self._plan_trail(parent, "error"), ref=parent.ref, want=parent.want)
            return
        if failed:
            return                                    # what runs finishes; nothing new starts
        for k in plans.ready(kids, self.goal.parallel or self.foreman.max_orcs):
            if self.held_by(k) is not None:               # another task builds its files now
                continue
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
               and (t.ask_kind or ("persona" if t.persona_waits else "")) in ("question", "rejected", "persona",
                                                                              "conflict")]
        why = f"nobody answered in {minutes:.0f} min" if minutes else "the orks decide at once (autonomy)"
        for name in sorted({t.persona_waits for t in due if t.persona_waits}):
            self._approve_persona(name, why)
        for t in due:
            if t.persona_waits:
                continue
            if t.ask_kind == "conflict":
                self.go_on(t, why)
            elif t.ask_kind == "rejected":
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
        self._unclaim(task)
        st.log(bk.Decision(bk.now_iso(), task.id, "close", task.orc, task.error[:300]))
        if task.parent:
            self._advance(st.task(task.parent))
            return
        orc = st.orc(task.orc)
        trail = self._plan_trail(task, "error") if task.plan or orc is None else self._trail(task, orc, "error")
        self.emit("pool.failed", f"**{task.title}** — {task.error}", task.title, trail=trail, ref=task.ref, want=task.want)

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
                answer = bk.steward_answer_of(self._steward(prompt, self.code_root, cancel, out, "answer"))
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
                ok, note = git.merge(self.code_root, task.base, task.branch, f"Merge part `{task.sub}`: {task.title}")
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
        st.log(bk.Decision(bk.now_iso(), parent.id, "review", why=f"every part is in: {self.keeper} looks at the whole"))

        def work() -> None:
            from orkcraft.core.workers.barracks import RunOutcome
            out = RunOutcome()
            try:
                diff, tests, commits = "", "", 0
                if git is not None and parent.branch:
                    commits, diff = git.diff(self.code_root, parent.base, parent.branch)
                    out.files = bk.changed_files(diff)
                    if cmd and commits:
                        where = worktrees.worktree_path(self.code_root, f"pool-{self.building_id}-steward".replace("_", "-"))
                        passed, tail = git.check(self.code_root, parent.branch, cmd, cancel, where)
                        if not passed:
                            out.accepted = False
                            out.notes = f"new: the tests of the merged parts fail (`{cmd}`):\n\n```\n{tail.strip()}\n```"
                            raise _Done
                        tests = f"`{cmd}` passes on the merged branch"
                extra, out.clashes, met = self._review_context(parent, out.files, git, parent.branch)
                verdict = self._steward(plans.final_prompt(self.keeper, self.orders, parent.title, parent.text,
                                                           parent.plan, reports, diff, tests, bk.DIFF_LIMIT, extra),
                                        self.code_root, cancel, out, "final")
                out.accepted, out.notes = bk.verdict_of(verdict)
                out.notes = briefs.strip(out.notes)
                out.designs = briefs.states(met, out.files, verdict)
                if out.accepted and git is not None and commits:
                    body = f"{parent.text}\n\n---\n\n" + "\n\n".join(
                        f"### {sub}\n\n{rep.strip()[:1500]}" for sub, rep in reports) + \
                        f"\n\n_Planned and reviewed by {self.keeper}: {out.notes or 'accepted'}_" + \
                        (f"\n\n_Design brief:_ `{parent.design}`" if parent.design else "") + self.pr_notes(parent, out)
                    out.pr, out.pr_note = git.publish(self.code_root, parent.branch, parent.base, parent.title, body)
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
            self._unclaim(parent)
            self.emit("pool.failed", f"**{parent.title}** — {self.keeper}: {out.error}", parent.title,
                      trail=self._plan_trail(parent, "error"), ref=parent.ref, want=parent.want)
        elif out.accepted:
            parent.status, parent.pr, parent.scope, parent.feedback = "done", out.pr, bk.EXTERNAL, ""
            self._claim_done(parent)
            self._apply_clashes(parent, out.clashes)
            self._designs_of(parent, out.designs, True)
            parent.result = "\n\n".join(f"### {k.title}\n\n{k.result.strip()}" for k in kids)
            st.log(bk.Decision(bk.now_iso(), parent.id, "accept", why=out.notes or "the whole is accepted"))
            orks = ", ".join(dict.fromkeys(k.orc for k in kids if k.orc))
            where = f"\n\n_pull request:_ {out.pr}" if out.pr else (f"\n\n_branch:_ `{parent.branch}`" if parent.branch else "")
            note = f" ({out.pr_note})" if out.pr_note and not out.pr else ""
            self.emit("pool.done", f"**{parent.title}** — {len(kids)} parts by {orks}, planned and reviewed by "
                      f"{self.keeper}\n\n{parent.result}{where}{note}" + self._files_md(parent), parent.title,
                      trail=self._plan_trail(parent, "done"), ref=parent.ref, want=parent.want)
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
        kid = bk.PoolTask(cid, f"{parent.title[:50]} · {sub.title}", plans.child_text(parent.title, bk.body_of(parent), sub, []),
                          arrived=bk.now_iso(), status="blocked", tier=tier, parent=parent.id, sub=sub.id,
                          ref=f"{self.building_id}:{cid}", branch=f"{parent.branch}--{sub.id}" if parent.branch else "",
                          base=parent.branch, want=parent.want, want_by=parent.want_by)
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
        parts = f"planned in {len(parent.plan)} parts" if parent.plan else ""
        return pipes.trail_of(parent.trail) + (pipes.hop(self.building_id, self.keeper, "agent", parent.tokens,
                                                         parent.cost_usd, "", parent.branch, outcome,
                                                         base=parent.base, since=parent.arrived,
                                                         decision=parent.decided or parts,
                                                         round=parent.attempts, run=parent.id),)


class _Done(Exception):
    """The last look ended early (the tests of the whole failed)."""
