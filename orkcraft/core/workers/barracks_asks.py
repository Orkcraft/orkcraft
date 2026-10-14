"""❓ An Agent pool's way to ask and to mark (docs/design/ork-console.md §4, §20; decisions §8, Claude Code first).

An ork on Claude Code is told to end its run with an `asks` block (realm/asking.py): its questions, each with the
answers to pick from, and the assumptions it made (in the person's working hours: only where a wrong guess costs
more than a day, the rest assumed and marked). Here the block is taken off the ork's report and read:

    questions     the steward answers what its rules settle; the rest wait for the person, pinned on top of the
                  task (`task.questions`, each with its options), until answered
    assumptions   kept on the task (`task.assumptions`) and named on its result: "Done · 2 assumptions"
    gist          what the run did or found (`task.gist`), read before its whole text; the answer's last paragraph
                  when the ork gave none, and the console says so (`task.gist_from`)

Every one is counted into the local event log (realm/event_log.py): a question asked, an assumption marked, an
answer given (by whom, after how long), a run that stopped on a question. Other AI tools keep the one line
`QUESTION: …` for now (Codex and agy later); it is read and counted the same way. Nothing here shows anything.
"""
from __future__ import annotations

import time

from orkcraft import schedule
from orkcraft.realm import asking, event_log
from orkcraft.realm import barracks as bk
from orkcraft.realm.road_agents import resolve

BLOCK_TOOLS = frozenset({"claude"})        # the tools told to end with the block (the rest: `QUESTION: …`)


class AsksMixin:
    def _events_root(self):
        """Where the local event log is written; None in the demo (nothing is counted there)."""
        town = self.town
        return None if getattr(town, "demo", False) or self.simulated else getattr(town, "repo_root", None)

    def _count(self, event: str, **fields) -> None:
        event_log.record(self._events_root(), event, building=self.building_id, **fields)

    def _work_until(self) -> str:
        """"19:00" while the person's working hours hold (schedule.py), else ""."""
        ends = schedule.work_ends(self.town.machine)
        return schedule.fmt(ends.hour * 60 + ends.minute) if ends else ""

    def ask_rule(self, harness: str) -> str:
        """What the ork's prompt says about asking: the block for Claude Code, the one line for the others. In the
        person's working hours both say to assume and mark unless a wrong guess costs more than a day."""
        until = self._work_until()
        if self._block_tool(harness):
            return asking.rule(self.keeper, until)
        return ((asking.at_work(until) if until else "") +
                "If you cannot go on without a decision, stop and end your answer with one line `QUESTION: …`; "
                f"{self.keeper}, the steward, will answer.")

    @staticmethod
    def _block_tool(harness: str) -> bool:
        try:
            return resolve(harness) in BLOCK_TOOLS
        except Exception:      # no main tool known (a town with none on): the plain line
            return False

    def _asks_of(self, out, orc: bk.PoolOrc, task: bk.PoolTask) -> str:
        """In the ork's thread, after each run: the block taken off its report, its assumptions kept on `out`, its
        questions on `out` too; the questions as one paragraph ("" when it asks nothing)."""
        found = asking.parse(out.text)
        out.text = found.body
        out.gist, out.gist_from = asking.gist_of(found)
        who = dict(ork=orc.name, task=task.id, harness=resolve(orc.harness) if orc.harness else "",
                   at_work=schedule.at_work(self.town.machine))
        for a in found.assumptions:
            if a not in out.assumptions:
                out.assumptions.append(a)
                self._count(event_log.ASSUMED, text=a, **who)
        out.questions = [q.as_dict() for q in found.questions]
        for q in found.questions:
            self._count(event_log.ASKED, text=q.text, options=q.options, via=found.via, **who)
        return asking.question_line(found)

    def _note_asks(self, task: bk.PoolTask, orc: bk.PoolOrc, out) -> None:
        """On the town's thread, when a run ends: the assumptions kept, the questions pinned, the steward's answers
        and a run that stopped on a question counted."""
        task.assumptions = task.assumptions + [a for a in out.assumptions if a not in task.assumptions]
        if out.gist:
            task.gist, task.gist_from = out.gist, out.gist_from
        for q, a, _who in out.qa:
            self._count(event_log.ANSWERED, ork=orc.name, task=task.id, who="steward", waited_s=0, text=a)
        if out.asked:
            task.questions = list(out.questions) or [{"text": out.asked, "options": []}]
            self._count(event_log.STOPPED, ork=orc.name, task=task.id, harness=resolve(orc.harness) if orc.harness else "")
        else:
            task.questions = []

    def _answered(self, task: bk.PoolTask, text: str, who: str) -> None:
        """The answer to an ork's question: counted with how long it waited; the pinned questions go."""
        if task.ask_kind in ("question", "deciding"):
            waited = round(time.time() - task.waits_since) if task.waits_since else None
            self._count(event_log.ANSWERED, ork=task.orc, task=task.id, waited_s=waited, text=text,
                        who="person" if who == "operator" else ("timer" if task.ask_kind == "deciding" else "steward"))
        task.questions = []

    def assumptions_md(self, task: bk.PoolTask) -> str:
        """The assumptions on a result, read before its whole text (ork-console.md §20); "" with none."""
        if not task.assumptions:
            return ""
        n = len(task.assumptions)
        return f"**{n} assumption{'' if n == 1 else 's'}**\n\n" + "\n".join(f"- {a}" for a in task.assumptions)
