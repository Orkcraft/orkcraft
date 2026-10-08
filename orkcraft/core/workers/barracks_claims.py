"""📍 The Barracks sees work that collides and remembers its designs (design: docs/design/barracks-designs.md).

    areas in work   a task claims the files it changes (the sort's guess, the plan's `touches`, then what its
                    branch changed) in the repository's `.orkcraft/claims.json`, shared by every pool on it
                    (realm/claims.py). A newer task on the area of an older one in `work` waits for it (at
                    most `claim_wait` minutes; `claims: flag` never waits); one on an area in `review` goes on,
                    told, and after its work git says whether the two branches would merge
    design brief    a plan of two parts or more leaves a brief on the task's branch before any part starts
                    (realm/briefs.py), from the plan and the steward's `design`
    read against    the plan reads the briefs the task concerns; one it goes against is a question as autonomy
                    says (⛓️ waits for the operator, 🕰 its minutes, ⛓️‍💥 goes on flagged)
    kept true       a change in a merged brief's area that does not change the brief: the review asks the
                    steward to send it back or say `DESIGN: unchanged`

A mixin of BarracksWorker (core/workers/barracks.py). Everything here runs on the town's thread but
`_review_context`, which the review calls in the ork's thread (it reads and runs git, writes nothing).
"""
from __future__ import annotations

import time
from dataclasses import asdict

from orkcraft.realm import barracks as bk
from orkcraft.realm import briefs, claims, plans

STALE_CHECK_S = 3600            # how often stale claims are dropped


class ClaimsMixin:
    # -- what it is -----------------------------------------------------------------------------------

    @property
    def claims_mode(self) -> str:
        """`wait` (default), `flag` or `off`; never in the sandbox."""
        mode = str(self.config.get("claims") or "wait").lower()
        return "off" if self.simulated else mode if mode in claims.MODES else "wait"

    @property
    def briefs_on(self) -> bool:
        return self.config.get("briefs", True) is not False and self.uses_git

    @property
    def briefs_dir(self) -> str:
        return claims.norm(str(self.config.get("briefs_dir") or "")) or briefs.DEFAULT_DIR

    @property
    def claim_wait(self) -> float:
        try:
            return float(self.config.get("claim_wait") or claims.DEFAULT_WAIT_MIN)
        except (TypeError, ValueError):
            return float(claims.DEFAULT_WAIT_MIN)

    def area(self) -> claims.Claims:
        return claims.Claims(self.repo_root)

    def _claim_key(self, task: bk.PoolTask) -> str:
        """A part claims under its parent: one task, one area."""
        return claims.key_of(self.building_id, task.parent or task.id)

    def found_briefs(self) -> list[briefs.Brief]:
        """The briefs merged into the repository (its main checkout)."""
        return briefs.scan(self.repo_root, self.briefs_dir) if self.config.get("briefs", True) is not False else []

    # -- claiming ---------------------------------------------------------------------------------------

    def _claim(self, task: bk.PoolTask, paths: list[str], guessed: bool, status: str = claims.WORK) -> None:
        """Write the task's area in work and see who else is on it."""
        if self.claims_mode == "off" or task.parent:
            return
        narrow = claims.narrow(paths)
        if not narrow:
            if paths and not task.claimed:
                self.state.log(bk.Decision(bk.now_iso(), task.id, "overlap",
                                           why="claims nothing: every path is too wide (" + ", ".join(paths[:5]) + ")"))
            if status == claims.REVIEW and task.claimed:
                narrow = task.claimed                     # keeps what it claimed while its PR waits
            else:
                return
        store = self.area()
        kept = store.put(claims.Claim(self._claim_key(task), self.building_id, task.id, task.title, narrow, guessed,
                                      task.branch, status, task.pr, task.design, claims.now()))
        task.claimed = narrow
        self._see(task, kept, store.load())

    def _see(self, task: bk.PoolTask, mine: claims.Claim, every: list[claims.Claim]) -> None:
        """The other tasks on its area, each said once in the decisions."""
        before = {o.get("key"): o for o in task.overlaps}
        rows = []
        for o in claims.overlaps(every, mine):
            row = {"key": o.key, "title": o.title, "building": o.building, "paths": claims.meets(o.paths, mine.paths),
                   "branch": o.branch, "pr": o.pr, "status": o.status, "brief": o.brief,
                   "conflicts": list(before.get(o.key, {}).get("conflicts") or [])}
            rows.append(row)
            if o.key not in before:
                where = "" if o.building == self.building_id else f" in {o.building}"
                state = "being built" if o.status == claims.WORK else ("PR open" if o.pr else "waits to be merged")
                self.state.log(bk.Decision(bk.now_iso(), task.id, "overlap",
                                           why=f"overlaps “{o.title}”{where} ({', '.join(row['paths'][:4])}) — {state}"))
        task.overlaps = rows

    def refresh_overlaps(self, task: bk.PoolTask) -> None:
        """Before an ork takes it: who is on its area now (a PR opened meanwhile, a task finished)."""
        if self.claims_mode == "off" or task.parent:
            return
        store = self.area()
        every = store.load()
        mine = next((c for c in every if c.key == self._claim_key(task)), None)
        if mine is not None:
            self._see(task, mine, every)

    def _unclaim(self, task: bk.PoolTask) -> None:
        if self.claims_mode == "off" or task.parent:
            return
        self.area().release(self._claim_key(task))
        task.held_since = 0.0

    def _claim_done(self, task: bk.PoolTask) -> None:
        """Done: its area waits to be merged (`review`) while it has a PR or a branch to merge, else it is free."""
        if task.pr or (task.branch and task.files and task.scope != bk.LOCAL):
            self._claim(task, task.files or task.claimed, False, claims.REVIEW)
        else:
            self._unclaim(task)

    def release_settled(self, tasks: list[bk.PoolTask]) -> None:
        """Their pull requests were merged or closed: their areas are free."""
        for t in tasks:
            self._unclaim(t)

    # -- waiting for an older task on the area -------------------------------------------------------------

    def held_by(self, task: bk.PoolTask) -> claims.Claim | None:
        """The older task in `work` this one waits for, or None: it may go. After `claim_wait` minutes it goes
        on flagged (`held_since` -1: it does not wait again)."""
        if self.claims_mode != "wait" or task.held_since < 0 or task.feedback or task.publish or task.qa:
            return None
        store = self.area()
        every = store.load()
        mine = next((c for c in every if c.key == self._claim_key(task)), None)
        if mine is None:
            return None
        if task.parent:                                   # a part: its own files, under its task's claim
            if not task.touches:
                return None
            mine = claims.Claim(mine.key, mine.building, mine.task, mine.title, claims.narrow(task.touches),
                                since=mine.since)
        other = claims.holds(every, mine)
        if other is None:
            if task.held_since > 0:
                self.state.log(bk.Decision(bk.now_iso(), task.id, "overlap", why="the area is free: it goes on"))
            task.held_since = 0.0
            return None
        now = time.time()
        if not task.held_since:
            task.held_since = now
            task.decided = f"overlap: waits for “{other.title}”"
            self.state.log(bk.Decision(bk.now_iso(), task.id, "overlap", why=f"waits for “{other.title}” — it is "
                                       f"being built on {', '.join(claims.meets(other.paths, mine.paths)[:4])}"))
            return other
        if now - task.held_since >= self.claim_wait * 60:
            task.held_since = -1.0
            self.state.log(bk.Decision(bk.now_iso(), task.id, "overlap", why=f"waited {self.claim_wait:.0f} min for "
                                       f"“{other.title}”: goes on, flagged"))
            return None
        return other

    def tick_claims(self, now: float | None = None) -> bool:
        """What waits for an area may go now; the stale claims are dropped now and then. True when it moved."""
        if self.claims_mode == "off":
            return False
        now = time.monotonic() if now is None else now
        if now - getattr(self, "_stale_at", -STALE_CHECK_S) >= STALE_CHECK_S:
            self._stale_at = now
            try:
                days = int(self.config.get("claim_days") or claims.DEFAULT_DAYS)
            except (TypeError, ValueError):
                days = claims.DEFAULT_DAYS
            for c in self.area().drop_stale(days):
                self.state.log(bk.Decision(bk.now_iso(), c.task, "overlap", why=f"“{c.title}”: its area is free "
                                           f"after {days} days (stale)"))
        st = self.state
        held = [t for t in st.queue + st.tasks if t.held_since > 0]
        if not held:
            return False
        for pid in dict.fromkeys(t.parent for t in held if t.parent):
            self._advance(st.task(pid))
        self._pump()
        st.save()
        self.changed()
        return True

    # -- what the ork and the steward read -----------------------------------------------------------------

    def overlap_md(self, task: bk.PoolTask) -> str:
        """*## Work on the same files*: the other tasks on its area (a part: its task's)."""
        parent = self.state.task(task.parent) if task.parent else None
        rows = (parent or task).overlaps
        if not rows:
            return ""
        lines = []
        for o in rows:
            bits = [f"branch `{o['branch']}`" if o.get("branch") else "", f"PR {o['pr']}" if o.get("pr") else "",
                    f"its design brief `{o['brief']}`" if o.get("brief") else "",
                    "being built now" if o.get("status") == claims.WORK else "waits to be merged",
                    "would conflict in " + ", ".join(o["conflicts"]) if o.get("conflicts") else ""]
            lines.append(f"- “{o['title']}” on {', '.join(o.get('paths') or [])} — " + "; ".join(b for b in bits if b))
        return ("## Work on the same files\n\nOther tasks change the same area:\n" + "\n".join(lines) +
                "\n\nKeep your change there small and compatible with theirs; do not redo their work.")

    def designs_md(self, task: bk.PoolTask) -> str:
        """The briefs an ork reads: its task's own (a part) or those its area and words meet (a whole task)."""
        if task.parent:
            parent = self.state.task(task.parent)
            if parent is not None and parent.design:
                return f"## The design brief\n\n`{parent.design}` on your branch: the design of the whole. Keep to it."
            return ""
        found = briefs.relevant(self.found_briefs(), task.claimed, f"{task.title}\n{task.text}")
        return briefs.section(found)

    def plan_designs(self, task: bk.PoolTask) -> str:
        return briefs.section(briefs.relevant(self.found_briefs(), task.claimed, f"{task.title}\n{task.text}"))

    def _review_context(self, task: bk.PoolTask, files: list[str], git, branch: str) -> tuple[str, dict, list]:
        """In the ork's thread, before the steward reads: (what the review prompt adds, conflicts by claim key,
        the merged briefs whose area the change meets). Reads claims and briefs, runs `git merge-tree`; writes nothing. A part: nothing (its
        task's last look does it)."""
        if task.parent:
            return "", {}, []
        parts, clashes, met = [], {}, []
        if self.claims_mode != "off" and files:
            mine = claims.Claim(self._claim_key(task), self.building_id, task.id, task.title, claims.narrow(files))
            for o in claims.overlaps(self.area().load(), mine):
                if o.status != claims.REVIEW or not o.branch or git is None or not branch:
                    continue
                try:
                    found = git.would_conflict(self.repo_root, branch, o.branch)
                except Exception:  # git cannot tell: no mark
                    found = None
                if found:
                    clashes[o.key] = found
            rows = [f"- “{o.title}” ({', '.join(claims.meets(o.paths, mine.paths)[:6])}) — "
                    + ("PR " + o.pr if o.pr else f"branch `{o.branch}`" if o.branch else "being built")
                    + (f"; merged together they conflict in {', '.join(clashes[o.key])}" if o.key in clashes else "")
                    for o in claims.overlaps(self.area().load(), mine)]
            if rows:
                parts.append("## Work on the same files\n\n" + "\n".join(rows) +
                             "\n\nJudge whether this change stays compatible with theirs. A conflict alone is no reason "
                             "to send it back: the other may never be merged.")
        if files:
            met = [b for b in self.found_briefs() if b.touches and claims.meets(files, b.touches)]
            rule = briefs.stale_rule(briefs.stale(met, files))
            if rule:
                parts.append(rule)
        return "\n\n".join(parts), clashes, met

    def _designs_of(self, task: bk.PoolTask, designs: list[dict], accepted: bool) -> None:
        """What became of the briefs the change met (`briefs.states`): kept on the task, in the decisions."""
        task.designs = designs
        lost = [d["path"] for d in designs if d["state"] == "not confirmed"]
        if accepted and lost:
            self.state.log(bk.Decision(bk.now_iso(), task.id, "design", why="design not confirmed: " + ", ".join(lost)))

    def _apply_clashes(self, task: bk.PoolTask, clashes: dict) -> None:
        if not clashes:
            return
        for o in task.overlaps:
            if o.get("key") in clashes:
                o["conflicts"] = clashes[o["key"]]
        for key, files in clashes.items():
            title = next((o["title"] for o in task.overlaps if o.get("key") == key), key)
            self.state.log(bk.Decision(bk.now_iso(), task.id, "overlap",
                                       why=f"merged with “{title}” it conflicts in {', '.join(files[:5])}"))

    # -- the design brief -----------------------------------------------------------------------------------

    def write_brief(self, task: bk.PoolTask, subs: list[plans.Sub], design: dict) -> None:
        """A plan of two parts or more: its design brief, committed on the task's branch before any part starts."""
        if not self.briefs_on or len(subs) < 2 or not task.branch or task.design:
            return
        taken = {b.path for b in self.found_briefs()} | {c.brief for c in self.area().load() if c.brief}
        path = briefs.path_for(self.briefs_dir, task.title, taken)
        text = briefs.render(task.title, task.text, task.id, self.building_id, subs, design)
        try:
            self.task_git.commit_file(self.repo_root, task.branch, path, text, f"Design brief: {task.title}")
        except Exception as e:  # no brief is no reason to stop the plan
            self.state.log(bk.Decision(bk.now_iso(), task.id, "design", why=f"no design brief: {str(e)[:200]}"))
            return
        task.design = path
        self.state.log(bk.Decision(bk.now_iso(), task.id, "design", why=f"design brief `{path}` on {task.branch}"))

    # -- a plan that goes against a design ------------------------------------------------------------------

    def against_md(self, task: bk.PoolTask) -> str:
        return "\n".join(f"- `{c['with']}`: {c.get('why') or 'no reason given'}" for c in task.against)

    def hold_plan(self, task: bk.PoolTask, subs: list[plans.Sub], design: dict) -> None:
        """⛓️ / 🕰: the plan waits for the operator (or its minutes) before any part starts."""
        task.pending = {"subs": [asdict(s) for s in subs], "design": design}
        self._ask(task, f"“{task.title}” goes against a design brief:\n\n{self.against_md(task)}\n\n"
                  "Go on as planned (Enter or yes), or write what to do instead: it is added to the task and it is "
                  "planned again.", f"{self.keeper}: the plan goes against a design", kind="conflict")

    def go_on(self, task: bk.PoolTask, how: str) -> None:
        """The held plan goes on as it was."""
        subs = [plans.Sub(**d) for d in task.pending.get("subs") or []]
        design = dict(task.pending.get("design") or {})
        task.pending, task.question, task.ask_kind, task.status = {}, "", "", "planning"
        self.state.log(bk.Decision(bk.now_iso(), task.id, "design", why=f"goes against a design, goes on: {how}"))
        if len(subs) < 2:
            self._whole(task, self.goal.simple, how)
            return
        self._split(task, subs, design)

    def conflict_answer(self, task: bk.PoolTask, text: str) -> str:
        said = text.strip()
        if not said or said.lower() in bk.APPROVE:
            self.go_on(task, "the operator said go on")
        else:
            task.qa.append([task.question.split("\n\n")[0], said, "operator"])
            task.text = f"{task.text}\n\n---\nThe operator, on the design it went against: {said}"
            task.pending, task.question, task.ask_kind, task.against = {}, "", "", []
            self.state.log(bk.Decision(bk.now_iso(), task.id, "answer", why=f"operator: {said[:200]}"))
            self._plan(task, f"{self.keeper} plans it again with the operator's word")
        self._pump()
        self.state.save()
        self.changed()
        return ""
