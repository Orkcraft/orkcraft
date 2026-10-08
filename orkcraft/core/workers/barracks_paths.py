"""🛤 The Agent pool's paths by the kind of work (docs/design/barracks-flows.md §5–7; realm/paths.py).

When a cart arrives, the steward picks its way, in this order:

    1. `want` is on the cart     its path: a building named it (no model call)
    2. the pool's table          `want_by_source`: the source's kind (by its id, else its type)
    3. neither                   the light sort, as today; it may name `reply` (a lower path), never more

A kind the pool does not take (`wants`, default change · reply · doc) goes back as *not mine*: the task fails
at once and `pool.failed` tells the road it came by. `change` and `doc` take today's way (the `doc` path of
§6 is not built: a document is written as before).

The `reply` path: one light ork, no plan, no branch, no claim, in harness mode `read` (realm/jobs.py
`run_read`: no terminal, no file edits) in an empty folder of its own — the message is all it reads. Its
draft is never posted by the pool: it leaves as `pool.done`, its hop waiting for the person's approval
(`gate.APPROVAL`), so a Review gate always holds it, and a Publisher asks before it sends one that did not
pass a gate. A reply that reads like a code task (realm/paths.py `looks_like_code`) is still only a reply:
the steward puts a card for the person on the Task board (*Looks like a code task — from …*).

A mixin of BarracksWorker (core/workers/barracks.py).
"""
from __future__ import annotations

import threading
import uuid
from pathlib import Path

from orkcraft.realm import barracks as bk
from orkcraft.realm import catalog, gate, jobs, paths, pipes, tasklist

REPLIES = "replies"              # the state folder's empty folders the reply orks run in, one per task


class PathsMixin:
    read_runner = None           # tests swap the reading agent's call (jobs.run_read) here

    # -- what it takes -----------------------------------------------------------------------------------

    @property
    def wants(self) -> tuple[str, ...]:
        return paths.wants_of(self.config)

    @property
    def want_table(self) -> dict[str, str]:
        return paths.table_of(self.config)

    def _type_of(self, building_id: str) -> str:
        spec = getattr(self.town, "custom_specs", {}).get(building_id)
        return catalog.type_of(spec).id if spec else ""

    def kind_of(self, payload) -> tuple[str, str]:
        """(its kind of work, who named it) for a cart that arrives: the cart's (§5 step 1), else the table's
        (step 2); ("", "") leaves it to the sort."""
        want = pipes.want_of(getattr(payload, "want", ""))
        if want:
            return want, pipes.want_by(payload.trail, want, payload.source)
        if not hasattr(self, "town"):                  # a worker made without its town (a test's) has no table
            return "", ""
        want = paths.by_source(self.want_table, payload.source, self._type_of(payload.source))
        return (want, paths.TABLE) if want else ("", "")

    def not_mine(self, payload, title: str, text: str, want: str) -> bool:
        """A kind it does not take goes back (§5): a failed task in its window, `pool.failed` to the road's
        source. True when it was not its own."""
        if not want or not hasattr(self, "town") or want in self.wants:
            return False
        from orkcraft.realm import lexicon
        took = ", ".join(lexicon.want_word(w) for w in self.wants) or "nothing"
        why = f"Not mine: this pool takes {took}, not {lexicon.want_word(want)}"
        task_id = uuid.uuid4().hex[:8]
        task = bk.PoolTask(task_id, title[:80], text, arrived=bk.now_iso(), status="failed", error=why,
                           ref=payload.ref or f"{self.building_id}:{task_id}", trail=[h.as_dict() for h in payload.trail],
                           want=want, want_by=pipes.want_by(payload.trail, want, payload.source), source=payload.source)
        st = self.state
        st.tasks.append(task)
        st.log(bk.Decision(bk.now_iso(), task.id, "not mine", why=why))
        self.emit("pool.failed", f"**{task.title}** — {why}", task.title, trail=payload.trail, ref=task.ref, want=want)
        self.toast(f"{task.title}: {why}", severity="warning")
        st.save()
        self.changed()
        return True

    # -- the sort names a lower path -----------------------------------------------------------------------

    def sorted_want(self, task: bk.PoolTask, want: str) -> bool:
        """The sort says it is only a reply (§5 step 3): it takes the `reply` path, when the pool takes replies
        and no building named another kind. True when it does."""
        if want != pipes.REPLY or task.want or pipes.REPLY not in self.wants:
            return False
        task.want, task.want_by = pipes.REPLY, paths.SORT
        return True

    # -- the reply path -------------------------------------------------------------------------------------

    def reply_ready(self, task: bk.PoolTask) -> None:
        """A reply goes to one light ork, unplanned; a reply that reads like code leaves a card for the person."""
        if task.kind != "reply":
            task.kind = "reply"
            self._code_card(task)
        task.tier = task.tier or self.goal.simple

    def _code_card(self, task: bk.PoolTask) -> None:
        if not paths.looks_like_code(f"{task.title}\n{task.text}"):
            return
        names = {b.id: b.title for b in getattr(self.town.scroll, "buildings", ())} if self.town.scroll else {}
        who = names.get(task.source, task.source) or "a message"
        title = f"Looks like a code task — from {who}: {task.title}"[:120]
        board = next((self.town.worker(bid) for bid, spec in getattr(self.town, "custom_specs", {}).items()
                      if catalog.type_of(spec).id == "fields" and self.town.worker(bid) is not None), None)
        st = self.state
        if board is not None and board.add(title, tasklist.MINE, task.text[:2000]) is not None:
            task.code_card = title
            st.log(bk.Decision(bk.now_iso(), task.id, "card", why=f"a card for you on {names.get(board.building_id, board.building_id)}: {title}"))
        else:
            st.log(bk.Decision(bk.now_iso(), task.id, "card", why="it reads like a code task; no Task board to put a card on"))

    def reply_prompt(self, task: bk.PoolTask, orc: bk.PoolOrc) -> str:
        return paths.reply_prompt(orc.name, self.keeper, self.orders, task.title, bk.body_of(task))

    def _reply_folder(self, task: bk.PoolTask) -> Path:
        folder = self.state_dir / REPLIES / task.id
        folder.mkdir(parents=True, exist_ok=True)
        return folder

    def _reply_runner(self):
        if type(self).read_runner is not None:
            return type(self).read_runner
        return self._sandbox_work() if self.simulated else jobs.run_read

    def work_reply(self, task: bk.PoolTask, orc: bk.PoolOrc, cancel: threading.Event) -> None:
        """In the ork's thread: one run in `read` mode, in an empty folder; its answer is the draft."""
        from orkcraft.core.workers.barracks import RunOutcome
        out = RunOutcome()
        env = {"ORKCRAFT_ORC": f"{self.building_id}/{orc.name.lower()}"}
        try:
            text, cost, tokens, _ = self._reply_runner()(orc.harness, self.reply_prompt(task, orc),
                                                         self._reply_folder(task), cancel, orc.model, env, "")
            out.text, out.cost, out.tokens = paths.draft_of(text), cost or 0.0, tokens or 0
            out.accepted, out.scope = (True, bk.LOCAL) if out.text else (None, "")
            if not out.text:
                out.error = "the reply came back empty"
        except InterruptedError:
            out.error = "stopped"
        except Exception as e:  # one ork's failure must not take the pool down
            out.error = str(e)[:300]
        self._call(self.finish, task.id, orc.name, out)

    def reply_done(self, task: bk.PoolTask, orc: bk.PoolOrc, out) -> None:
        """The draft leaves for the Review gate: `pool.done` carries the reply itself, its hop waits for the
        person's approval (a gate always holds it); the pool never posts it."""
        st = self.state
        task.status, task.scope, task.feedback, task.draft, task.publish = "done", bk.LOCAL, "", "", ""
        gist = next((ln.strip(" #*") for ln in out.text.splitlines() if ln.strip(" #*")), "")[:160]
        orc.recent = (orc.recent + [f"{task.title} — {gist}" if gist else task.title])[-bk.KEEP_RECENT:]
        st.log(bk.Decision(bk.now_iso(), task.id, "draft", orc.name, "a draft reply, for the Review gate"))
        self.emit("pool.done", out.text, task.title, trail=self._trail(task, orc, gate.APPROVAL), ref=task.ref,
                  want=task.want)
