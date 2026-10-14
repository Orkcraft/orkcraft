"""⏳ ! An Agent pool's orks held for a limit, or stopped on an error (docs/design/ork-console.md §5, §19;
town-readability.md §4; town-time.md §4). Data only: the status says it (barracks_status.py), the GUI draws it.

    w.tool_limit(task, orc)    its AI tool said its limit is hit: the task goes back, held until the window resets
    w.town_holds(task, orc)    True: the window of its ork's tool is nearly spent, the town held it (the Treasurer)
    w.run_anyway(task_id)      the way past the hold: it runs now, said and counted
    w.ork_failed(orc, task, why) / w.clear_error(orc_name)     an ork's own `!`, until it works again or you clear it

Until when comes from the quota readers' last read (`town.limits`, sources/limits.py); a reset nobody could read is
tried again after status.UNKNOWN_RESET_S, and the line says it is not known.
"""
from __future__ import annotations

import time

from orkcraft.realm import barracks as bk
from orkcraft.realm import event_log, harnesses, status
from orkcraft.realm.road_agents import resolve


class LimitsMixin:
    def _tool_of(self, orc: bk.PoolOrc | None) -> str:
        return resolve(orc.harness) if orc is not None and orc.harness else ""

    def window_reset(self, orc: bk.PoolOrc | None, below: float = status.SPENT, now: float | None = None) -> float | None:
        """When its ork's tool's window comes back, if the last quota read has it at `below` or less left."""
        tool = self._tool_of(orc)
        return status.reset_of(getattr(self.town, "limits", None) or [], tool, now, below) if tool else None

    def limit_held(self, task: bk.PoolTask, now: float | None = None) -> bool:
        return task.limit_until > (time.time() if now is None else now)

    def _hold(self, task: bk.PoolTask, orc: bk.PoolOrc, by: str, until: float | None, now: float) -> None:
        st = self.state
        if task in st.tasks:
            st.tasks.remove(task)
        known = until is not None
        task.limit_until = until if known else now + status.UNKNOWN_RESET_S
        task.limit_by = by if known or by == status.BY_TOWN else f"{by}?"     # "tool?": its reset was not read
        task.status, task.wait_for, task.error = "queued", orc.name, ""
        if task not in st.queue:
            st.queue.insert(0, task)
        st.log(bk.Decision(bk.now_iso(), task.id, "held", orc.name, self.limit_wait(task, now).line))

    def tool_limit(self, task: bk.PoolTask, orc: bk.PoolOrc, now: float | None = None) -> None:
        """Its AI tool said its limit is hit: not the ork's failure, the work waits for the reset."""
        now = time.time() if now is None else now
        self._hold(task, orc, status.BY_TOOL, self.window_reset(orc, 1.0, now), now)

    def town_holds(self, task: bk.PoolTask, orc: bk.PoolOrc, now: float | None = None) -> bool:
        """Work that would start with its tool's window nearly spent waits for the reset (town-time.md §4), unless
        the person said Run anyway. A rule in code: no session, no slot."""
        if task.limit_skip or self.simulated:
            return False
        now = time.time() if now is None else now
        until = self.window_reset(orc, status.NEARLY, now)
        if until is None:
            return False
        self._hold(task, orc, status.BY_TOWN, until, now)
        return True

    def limit_wait(self, task: bk.PoolTask, now: float | None = None) -> status.Wait:
        tool = harnesses.title(self._tool_of(self.state.orc(task.wait_for))) or "its AI tool"
        by = task.limit_by.rstrip("?") or status.BY_TOOL
        return status.held(tool, task.limit_until, by, status.Skip("run_anyway", "Run anyway", {"task": task.id}),
                           now, known=not task.limit_by.endswith("?"))

    def run_anyway(self, task_id: str, now: float | None = None) -> bool:
        """Run anyway (§19): the held task goes now, over the window; False when it is not held."""
        now = time.time() if now is None else now
        task = self.state.task(task_id)
        if task is None or task not in self.state.queue or not self.limit_held(task, now):
            return False
        left = round(task.limit_until - now)
        task.limit_until, task.limit_skip = 0.0, True
        self.state.log(bk.Decision(bk.now_iso(), task.id, "run anyway", why="you ran it over the limit's window"))
        try:
            self._count(event_log.WAIT_SKIPPED, task=task.id, wait=status.LIMIT, left_s=left)
        except Exception:                  # a count never stops the work
            pass
        self._pump()
        self.state.save()
        self.changed()
        return True

    def ork_failed(self, orc: bk.PoolOrc, task: bk.PoolTask, why: str) -> None:
        """Its run failed: the ork's own `!` with what broke (its building burns only when it is broken itself)."""
        orc.error, orc.error_task = " ".join((why or "it stopped on an error").split())[:300], task.id

    def clear_error(self, orc_name: str) -> bool:
        orc = self.state.orc(orc_name)
        if orc is None or not orc.error:
            return False
        orc.error = orc.error_task = ""
        self.state.save()
        self.changed()
        return True
