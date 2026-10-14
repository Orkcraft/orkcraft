"""● An Agent pool's one status (docs/design/ork-console.md §5, §19; cart-waybill.md §4), in realm/status.py's
words: each ork's state with the task it works on named, each waiting task's wait with why, until when and the way
past it, and the building's own state. Data only: the view draws it (gui/views/barracks.py).

    w.task_wait(task)      → status.Wait | None     (None: it does not wait — it works, or it is done)
    w.ork_status(orc)      → status.OrkStatus     (asks ❓, held for a limit ⏳, its own error !, at work, at rest)
    w.building_status()    → "working" | "idle" | "burning" | "smouldering"
"""
from __future__ import annotations

import time

from orkcraft import autonomy, schedule
from orkcraft.realm import barracks as bk
from orkcraft.realm import status

WAITING = ("queued", "blocked", "planning", "planned")


class StatusMixin:
    def _ask_minutes(self) -> float | None:
        """How long a question waits for the person before the orks decide it (autonomy); None: as long as it takes."""
        rules = self.rules
        try:
            quiet = schedule.quiet_now(self.town.machine)
        except Exception:
            quiet = False
        return autonomy.waits(rules.level, quiet, rules.wait)

    def task_wait(self, task: bk.PoolTask, now: float | None = None) -> status.Wait | None:
        now = time.time() if now is None else now
        st = self.state
        if task.status == "asked":
            return self._asked_wait(task, now)
        if task.status not in WAITING:
            return None
        if st.paused:
            return status.Wait(status.PAUSED, "paused by you", skip=status.Skip("pause", "Resume"))
        if self.limit_held(task, now):
            return self.limit_wait(task, now)
        if task.decided.startswith("budget"):
            return status.Wait(status.LIMIT, "held: the budget is spent")
        if task.status == "planning":
            return status.Wait(status.STEWARD, f"{self.keeper}, the steward, is planning it")
        if task.persona_waits:
            return status.Wait(status.APPROVAL, f"waits for your yes to a new persona: {task.persona_waits}",
                               skip=status.Skip("answer", "Approve", {"task": task.id, "text": ""}))
        if task.after and (first := self._unmet(task)) is not None:
            return status.Wait(status.AFTER, f"after {status.quoted(first.title)}",
                               skip=status.Skip("open", first.title, {"task": first.id}))
        try:
            held = self.held_by(task)
        except Exception:
            held = None
        if held is not None:
            return status.Wait(status.AREA, f"after {status.quoted(held.title)}, on the same files")
        if task.wait_for:
            return status.Wait(status.ORK, f"waits for {task.wait_for}, who did the earlier part")
        if task.decided.startswith("hire"):
            return status.Wait(status.HIRING, "hiring an ork for it")
        f = self.foreman
        if len(st.orcs) >= f.max_orcs and not any(o.status == "idle" for o in st.orcs):
            return status.Wait(status.SLOT, f"no free slot ({len(st.orcs)}/{f.max_orcs})")
        return status.Wait(status.QUEUE, "next in the queue")

    def _unmet(self, task: bk.PoolTask) -> bk.PoolTask | None:
        """The first part it waits for that is not done yet."""
        parts = [t for t in self.state.queue + self.state.tasks if t.parent == task.parent and t.sub in task.after]
        return next((t for t in parts if t.status != "done"), None)

    def _asked_wait(self, task: bk.PoolTask, now: float) -> status.Wait:
        if task.draft:
            return status.Wait(status.APPROVAL, f"waits for your yes to post it to {task.target or 'its place'}",
                               skip=status.Skip("answer", "Approve", {"task": task.id, "text": ""}))
        if task.persona_waits:
            return status.Wait(status.APPROVAL, f"waits for your yes to a new persona: {task.persona_waits}",
                               skip=status.Skip("answer", "Approve", {"task": task.id, "text": ""}))
        line = {"conflict": "waits for your word: its plan goes against a design brief",
                "rejected": "sent back too often: waits for your word",
                "deciding": f"{self.keeper}, the steward, decides it now"}.get(task.ask_kind, "waits for your answer")
        skip = status.Skip("answer", "Answer", {"task": task.id})
        minutes = self._ask_minutes() if task.ask_kind in ("question", "rejected", "conflict") else None
        if minutes is None or not task.waits_since:
            return status.Wait(status.ANSWER, line, skip=skip)
        left = task.waits_since + minutes * 60 - now
        then = "closes it" if task.ask_kind == "rejected" else "decides it"
        return status.Wait(status.ANSWER, f"{line} · {self.keeper} {then} {status.when(left, now)}",
                           until=now + max(left, 0), skip=skip)

    def ork_status(self, orc: bk.PoolOrc, now: float | None = None) -> status.OrkStatus:
        st = self.state
        title = self._building_title()
        if orc.status == "working" and (task := st.task(orc.task)) is not None:
            what = "in your terminal" if self.taken_over(orc.name) else (
                "its work is in review" if task.status == "reviewing" else "")
            return status.OrkStatus(orc.name, status.THINKING, title, what, task.title, task.id)
        asking = next((t for t in st.asked if t.orc == orc.name and t.ask_kind == "question"), None)
        if asking is not None:
            return status.OrkStatus(orc.name, status.ASKS, title, cart=asking.title, cart_id=asking.id,
                                    assumptions=len(asking.assumptions), wait=self.task_wait(asking, now))
        now = time.time() if now is None else now
        held = next((t for t in st.queue if t.wait_for == orc.name and self.limit_held(t, now)), None)
        if held is not None:
            return status.OrkStatus(orc.name, status.HELD, title, cart=held.title, cart_id=held.id,
                                    wait=self.limit_wait(held, now))
        if orc.error:
            failed = st.task(orc.error_task)
            return status.OrkStatus(orc.name, status.ERROR, title, cart=failed.title if failed else "",
                                    cart_id=failed.id if failed else "", error=orc.error)
        return status.OrkStatus(orc.name, status.RESTING, title)

    def _building_title(self) -> str:
        scroll = getattr(self.town, "scroll", None)
        spec = scroll.building(self.building_id) if scroll is not None else None
        return getattr(spec, "title", "") or "Agent pool"

    def building_status(self) -> str:
        """It burns when a question stands and nothing else moves; it smoulders while the person paused it."""
        st = self.state
        working = any(o.status == "working" for o in st.orcs)
        blocking = bool(st.asked) and not working and not st.queue
        return status.building_state(working, asks_blocking=blocking, stopped=st.paused)

    # -- the 🥩 list (ork-console.md §8): one row per ork at work or asking ----------------------------------

    def started(self, orc_name: str) -> None:
        """An ork's run began now: the 🥩 list says how long it has been at it."""
        if not hasattr(self, "_since"):
            self._since = {}
        self._since[orc_name] = time.time()

    def ork_slots(self, now: float | None = None) -> list[dict]:
        """Each ork at work, asking, held for a limit or stopped on its own error, as the 🥩 list's row: its one
        status, how long, its spend, its tool, the way to stop it softly, to answer it, or to clear its error (a
        held one's way past is its wait's skip: Run anyway)."""
        now = time.time() if now is None else now
        since = getattr(self, "_since", {})
        rows = []
        for orc in self.state.orcs:
            s = self.ork_status(orc, now)
            if s.state not in (status.THINKING, status.TOOL, status.ASKS, status.HELD, status.ERROR):
                continue
            task = self.state.task(s.cart_id) if s.cart_id else None
            at_work = s.state in (status.THINKING, status.TOOL)
            row = {**s.as_dict(now=now), "key": f"{self.building_id}/{orc.name.lower()}", "building_id": self.building_id,
                   "since_s": round(now - since[orc.name]) if at_work and orc.name in since else
                   (round(now - task.waits_since) if s.state == status.ASKS and task is not None and task.waits_since
                    else None),
                   "spend": round((task.cost_usd or 0.0), 2) if task is not None else 0.0,
                   "tool": orc.harness, "stop": None, "answer": None, "clear": None}
            if s.state == status.ERROR:
                row["clear"] = {"command": "act", "args": {"id": self.building_id, "act": "clear_error",
                                                           "args": {"ork": orc.name}}}
            elif s.state == status.ASKS and task is not None:
                row["answer"] = {"kind": "pool", "building": self.building_id, "task": task.id,
                                 "question": task.question, "questions": list(task.questions)}
            elif at_work:                          # a held one's way past is its wait's skip: Run anyway
                row["stop"] = {"command": "act", "args": {"id": self.building_id, "act": "stop_ork",
                                                          "args": {"ork": orc.name}}}
            rows.append(row)
        return rows

    def stop_ork(self, orc_name: str) -> bool:
        """⏹ One ork stops where it is (its task ends as stopped, as Stop does for them all). False when it was not
        at work."""
        cancel = self._cancels.get(orc_name)
        if cancel is None or cancel.is_set():
            return False
        cancel.set()
        return True
