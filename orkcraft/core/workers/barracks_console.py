"""▸ An Agent pool ork's console, unfolded (docs/design/ork-console.md §7, §9, §14, §19–§21): everything the
console shows of one ork, from the pool's state. Data only: the GUI draws it (js/slots.js `OrkConsole`), core/slots.py
asks for it by the ork's key.

    w.ork_console("Ugluk")    → {role, sessions, cart, answer, terminal, history, totals} | None
    w.run_again(task_id)      the stopped task goes back to the front of the queue, to the same ork (its session goes on)
    w.drop(task_id)           the stopped task is closed as dropped

The answer is read in the order of §20: its questions pinned on top, the gist, its assumptions, the whole text
(folded by the face). A role's sessions are the orks hired as the same persona (§2, decision 5), a chip each, the
asking one first. The history is the ork's runs, newest first, each with its cost where it is known.
"""
from __future__ import annotations

import time

from orkcraft.realm import barracks as bk
from orkcraft.realm import lexicon, status

HISTORY_MAX = 20
TEXT_MAX = 20_000
STOPPED = "stopped"


def _cost(x: float | None) -> float | None:
    return round(x, 4) if x else None


class ConsoleMixin:
    def _role_of(self, orc: bk.PoolOrc) -> str:
        return f"{lexicon.term('orc.barracks')} · {orc.persona or 'any work'}"

    def _console_cart(self, orc: bk.PoolOrc) -> bk.PoolTask | None:
        """What the console is about: the task it works on, else the one it asks on, else its last run."""
        st = self.state
        if orc.task and (t := st.task(orc.task)) is not None:
            return t
        asking = next((t for t in st.asked if t.orc == orc.name), None)
        if asking is not None:
            return asking
        return next((t for t in reversed(st.tasks) if t.orc == orc.name), None)

    def _answer_of(self, task: bk.PoolTask) -> dict:
        """§20's order: the questions pinned on top, the gist, the assumptions, the whole text."""
        asks = task.status == "asked"
        return {"questions": [dict(q) for q in task.questions] if asks else [],
                "question": task.question if asks else "", "draft": bool(task.draft) and asks,
                "draft_text": task.draft[:TEXT_MAX] if asks else "", "target": task.target if asks else "",
                "gist": task.gist, "gist_from": task.gist_from, "assumptions": list(task.assumptions),
                "text": (task.result or "")[:TEXT_MAX], "error": task.error}

    def _sessions_of(self, orc: bk.PoolOrc, now: float) -> list[dict]:
        """The role's sessions, a chip each (§14): the asking one first, then those at work, then the resting."""
        order = {status.ASKS: 0, status.THINKING: 1, status.TOOL: 1, status.RESTING: 2}
        same = [o for o in self.state.orcs if (o.persona or "") == (orc.persona or "")]
        found = [(o, self.ork_status(o, now)) for o in same]
        found.sort(key=lambda x: order.get(x[1].state, 3))
        return [{"key": f"{self.building_id}/{o.name.lower()}", "name": o.name, "state": s.state,
                 "mark": s.mark("camp"), "word": s.mark("office"), "line": s.line(), "cart": s.cart,
                 "tool": o.harness, "this": o.name == orc.name} for o, s in found]

    def _history_of(self, orc: bk.PoolOrc) -> list[dict]:
        runs = [t for t in reversed(self.state.tasks) if t.orc == orc.name][:HISTORY_MAX]
        return [{"id": t.id, "title": t.title, "status": t.status, "cost": _cost(t.cost_usd), "tokens": t.tokens,
                 "assumptions": len(t.assumptions), "warm": t.warm, "pr": t.pr, "stopped": t.error == STOPPED,
                 "dropped": t.decided == "dropped by you", "gist": t.gist.split("\n")[0][:160]} for t in runs]

    def ork_console(self, orc_name: str, now: float | None = None) -> dict | None:
        now = time.time() if now is None else now
        orc = self.state.orc(orc_name)
        if orc is None:
            return None
        task = self._console_cart(orc)
        s = self.ork_status(orc, now)
        cart = None
        if task is not None:
            wait = self.task_wait(task, now)
            cart = {"id": task.id, "title": task.title, "status": task.status, "branch": task.branch, "pr": task.pr,
                    "cost": _cost(task.cost_usd), "wait": wait.as_dict(now) if wait is not None else None,
                    "stopped": task.status == "failed" and task.error == STOPPED and task.decided != "dropped by you",
                    "from": task.source}
        working = orc.status == "working"
        return {"role": self._role_of(orc), "state": s.as_dict(now=now), "tool": orc.harness, "tier": orc.tier or "",
                "sessions": self._sessions_of(orc, now), "cart": cart,
                "answer": self._answer_of(task) if task is not None else None,
                "terminal": {"key": f"pool:{self.building_id}/{orc.name.lower()}", "by_hand": self.taken_over(orc.name),
                             "working": working, "resumable": bool(orc.session)},
                "history": self._history_of(orc),
                "totals": {"done": orc.done, "failed": orc.failed, "cost": _cost(orc.cost_usd), "tokens": orc.tokens}}

    # -- after a stop (ork-console.md §9): Run again or Drop --------------------------------------------------

    def _stopped(self, task_id: str) -> bk.PoolTask | None:
        task = self.state.task(task_id)
        if task is None or task.status != "failed" or task.error != STOPPED or task.decided == "dropped by you":
            return None
        return task

    def run_again(self, task_id: str) -> bool:
        """The stopped task goes on: first in the queue, for the ork that ran it, so its session is resumed."""
        task = self._stopped(task_id)
        if task is None:
            return False
        st = self.state
        st.tasks.remove(task)
        task.status, task.error, task.wait_for = "queued", "", task.orc
        st.queue.insert(0, task)
        st.log(bk.Decision(bk.now_iso(), task.id, "again", task.orc, "run again by you after a stop"))
        if not st.paused:
            self._pump()
        st.save()
        self.changed()
        return True

    def drop(self, task_id: str) -> bool:
        """The stopped task is closed as dropped: it stays in the history, it never runs again."""
        task = self._stopped(task_id)
        if task is None:
            return False
        task.decided = "dropped by you"
        self.state.log(bk.Decision(bk.now_iso(), task.id, "dropped", task.orc, "dropped by you after a stop"))
        self.state.save()
        self.changed()
        return True
