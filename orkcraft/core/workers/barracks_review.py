"""🔎 The Barracks' judgement of the work (design: the docstring of core/workers/barracks.py).

What the steward and the operator say about a task once its ork is done: the review (the tests, then
the steward reads the diff), a draft that waits for the operator's approval before it is posted, the
operator's answers to a question, and what became of the pull requests (merged 👍, closed 👎).

A mixin of BarracksWorker (core/workers/barracks.py): the steward's calls run in threads, what they
come to is applied on the town's thread.
"""
from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import TYPE_CHECKING

from orkcraft.realm import barracks as bk
from orkcraft.realm import briefs, daybook, feedback, gitinfo, jobs, pipes, plans

if TYPE_CHECKING:
    from orkcraft.core.workers.barracks import RunOutcome

DUPLICATE_LABELS = frozenset({"duplicate", "superseded"})   # a closed pull request so labelled is no 👎


class ReviewMixin:
    # -- what became of the pull requests -----------------------------------------------------------

    def check_prs(self) -> None:
        """Look (in a thread) at the pull requests of done tasks not settled yet."""
        if self.simulated or not any(t.status == "done" and t.pr and not t.pr_state for t in self.state.tasks):
            return
        reader, repo = type(self).pr_reader or gitinfo.pull_requests, self.code_root

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

        settled, done = 0, []
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
            done.append(task)
            if duplicate:
                continue
            feedback.signal(self.repo_root, self.building_id, good, "pr.merged" if good else "pr.closed",
                            value=task.result or task.title,
                            note=f"{task.title}: pull request {'merged' if good else 'closed without merging'} {task.pr}")
        self.release_settled(done)                  # merged or closed: its area is free
        if settled:
            self.state.save()
            self.changed()
        return settled

    # -- the review ---------------------------------------------------------------------------------------

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
            if commits == 0 and not meeting and not draft and not out.text.strip():
                out.accepted, out.notes = False, "nothing was committed on the branch and there is no report"
                return
        rule = bk.scope_rule(files, meeting) or (bk.EXTERNAL if draft else "")
        if git is not None and commits == 0 and not draft:   # an answer, not a change: the report is the work
            rule = bk.LOCAL
        cmd = str(self.config.get("test_cmd") or "") if git is not None and commits and rule != bk.LOCAL else ""
        if cmd:
            passed, tail = git.test(workdir, cmd, cancel)
            alone = task.parent and not plans.holds_all(self.children(self.state.task(task.parent) or task), task.sub)
            if not passed and alone:     # the other parts' code is not on its branch: the whole is tested merged
                tests = (f"`{cmd}` fails on this part alone, without the other parts' work; the merged whole is "
                         f"tested once every part is in:\n\n```\n{tail.strip()[-1500:]}\n```")
            elif not passed:
                out.accepted, out.notes = False, f"the tests fail (`{cmd}`):\n\n```\n{tail.strip()}\n```"
                return
            else:
                tests = f"`{cmd}` passes: the barracks ran it on the branch itself, after the ork"
        extra, out.clashes, met = self._review_context(task, files, git, task.branch)
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
        if task.kind == plans.TRIVIAL and not task.feedback and not self.goal.review_trivial:
            out.accepted, out.notes = True, tests or "trivial: no review"   # the tests, when there are, were it
            out.scope = rule or (bk.EXTERNAL if commits else bk.LOCAL)
            if git is not None and commits and out.scope == bk.EXTERNAL:
                body = f"{task.text}\n\n---\n\n{out.text}\n\n_Trivial: not reviewed by {self.keeper}_"
                out.pr, out.pr_note = git.publish(workdir, task.branch, task.base, task.title, body)
            return
        verdict = self._steward(bk.review_prompt(self.keeper, self.orders, task, out.text, diff, tests, rule, extra),
                                workdir, cancel, out, light=meeting)
        out.accepted, out.notes = bk.verdict_of(verdict)
        out.notes = briefs.strip(bk.SCOPE.sub("", out.notes)).strip()
        out.scope = rule or bk.scope_of(verdict)
        out.designs = briefs.states(met, files, verdict)
        if out.accepted and git is not None and commits and out.scope == bk.EXTERNAL:
            body = f"{task.text}\n\n---\n\n{out.text}\n\n_Reviewed by {self.keeper}: {out.notes or 'accepted'}_" \
                + self.pr_notes(task, out)
            out.pr, out.pr_note = git.publish(workdir, task.branch, task.base, task.title, body)

    def pr_notes(self, task: bk.PoolTask, out: RunOutcome) -> str:
        """What the pull request's body adds: the briefs the change met, the branches it would conflict with."""
        titles = {o.get("key"): o.get("title") for o in task.overlaps}
        lines = [briefs.pr_line(out.designs)] + [
            f"Overlaps “{titles.get(k) or k}”: merged together they conflict in {', '.join(f)}" for k, f in out.clashes.items()]
        lines = [ln for ln in lines if ln]
        return ("\n\n" + "\n".join(f"- {ln}" for ln in lines)) if lines else ""

    @staticmethod
    def _meeting(task: bk.PoolTask) -> bool:
        """A War Drum's meeting asked for it: a local document, no pull request."""
        return bool(daybook.meet_tag(task.title) or daybook.meet_tag(task.text))

    # -- a draft waits for the operator ------------------------------------------------------------------

    def _draft_of(self, ref: str) -> bk.PoolTask | None:
        """The task whose draft waits for approval under this `ref`."""
        return next((t for t in self.state.tasks if ref and t.ref == ref and t.status == "asked" and t.draft), None)

    def _wants_approval(self, task: bk.PoolTask, orc: bk.PoolOrc, report: str, target: str, draft: str) -> None:
        """The orc prepared something to go out: nothing is posted until the operator approves it — here (🔥)
        or in a Loot that `pool.question` runs through (accept → it is posted, rework → what to change)."""
        task.target, task.draft = target, draft
        where = bk.publish_kind(target)[1]
        md = (f"**{task.title}** — {orc.name} wants to publish to {where or 'a service'} and waits for your "
              f"approval (accept: it is posted as below, your edits included · send back: what to change)\n\n"
              f"{report.strip()}{self._files_md(task)}\n\n## To publish\n\nPUBLISH: {target}\n\n{draft}")
        self._ask(task, f"Publish to {where or 'a service'}?\n\n{draft}", f"{orc.name} wants to publish", md,
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
                  trail=trail, ref=task.ref, want=task.want)
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
        if task.ask_kind == "conflict":             # its plan goes against a design brief
            return self.conflict_answer(task, text)
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
