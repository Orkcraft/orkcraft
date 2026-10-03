"""🏕 Barracks: the foreman runs incoming tasks with several orcs at once.

A cart that arrives is a task. The foreman (realm/barracks.py) gives it to the orc that did the
earlier part (a follow-up), to an idle orc, to a newly hired one (picking its provider and model),
or queues it. Each orc works in its own worktree on `pool/<building>/<orc>`; a finished task sends
`pool.done` with the result and the branch — no pull request is opened for it. The hut shows the
orcs and the queue; the open building also shows the foreman's decisions and their reasons.

Tokens: a follow-up or related task resumes the orc's session and sends only the task (♻ warm);
a cold start sends the briefing, plus a handoff of the orc's recent work only when it is related.
"""
from __future__ import annotations

import threading
import uuid
from pathlib import Path

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import OptionList, Static
from textual.widgets.option_list import Option

from orkcraft.realm import barracks as bk
from orkcraft.realm import jobs, roads
from orkcraft.screens.typed.base import TypedView

ICON = {"idle": "💤", "working": "⚒"}


def _simulated_work(harness, prompt, workdir, cancel, model, env, resume):
    """The sandbox: an orc 'works' for a moment and reports what it would have done."""
    if cancel.wait(1.5):
        raise InterruptedError("stopped")
    task = prompt.split("## Task", 1)[-1].splitlines()[0].lstrip(": ")
    return f"_(demo — simulated)_ {harness} would have worked on: {task}", None, None, ""


class PoolView(TypedView):
    TYPE = "barracks"
    work_runner = None            # tests swap the agent call (jobs.run_work) here
    worktree_maker = None         # and the worktree maker (jobs.add_worktree)

    def __init__(self, *a, **kw) -> None:
        super().__init__(*a, **kw)
        self.bk: bk.Barracks | None = None
        self._cancels: dict[str, threading.Event] = {}

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

    def compose_body(self) -> ComposeResult:
        yield Static("", id="pool-head", classes="typed-head")
        with Horizontal(classes="typed-row"):
            yield OptionList(id="pool-orcs", classes="typed-list")
            with VerticalScroll(classes="typed-detail"):
                yield Static("", id="pool-detail")

    def refresh_data(self) -> None:
        self.state            # loads once; a restart puts interrupted work back in the queue
        self._render_list()

    # -- tasks in -----------------------------------------------------------------------------------

    def receive(self, payload, title: str, markdown: str) -> None:
        text = markdown or payload.value
        first = text.strip().splitlines()[0][:60] if text.strip() else "task"
        self.add_task(payload.title or first, text, bk.task_key(payload.kind, payload.value, payload.title))

    def add_task(self, title: str, text: str, key: str = "") -> bk.PoolTask:
        task = bk.PoolTask(uuid.uuid4().hex[:8], title[:80], text, key or bk.task_key("text", text, title),
                           bk.now_iso())
        st = self.state
        st.queue.append(task)
        self._dispatch(task)
        st.save()
        self._render_list()
        return task

    def _dispatch(self, task: bk.PoolTask) -> None:
        st = self.state
        d = self.foreman.decide(task, st.orcs, [t for t in st.queue if t is not task], st.spent, st.paused)
        task.decided = f"{d.action}: {d.why}"
        st.log(d)
        if d.action in ("follow-up", "reuse"):
            self._assign(task, st.orc(d.orc), d.action)
        elif d.action == "hire":
            harness, model, _ = self.foreman.choose_model(task)
            orc = self.hire(d.orc, harness, model)
            if orc is not None:
                self._assign(task, orc, "new")
        elif d.action == "wait":
            task.wait_for = d.orc

    def hire(self, name: str, harness: str, model: str) -> bk.PoolOrc | None:
        st = self.state
        orc = bk.PoolOrc(name, harness, model, hired=bk.now_iso())
        if self.worktrees and not self.simulated:          # the sandbox describes worktrees, it does not make them
            maker = type(self).worktree_maker or jobs.add_worktree
            try:
                path, branch = maker(self._get_repo_root(), self.building_id, name)
            except (RuntimeError, OSError) as e:
                self.app.notify(f"{name}: no worktree — {e}", title="🏕 Barracks", severity="error")
                return None
            orc.worktree, orc.branch = str(path), branch
        st.orcs.append(orc)
        return orc

    # -- work ---------------------------------------------------------------------------------------

    def _assign(self, task: bk.PoolTask, orc: bk.PoolOrc | None, how: str) -> None:
        if orc is None:
            return
        st = self.state
        if task in st.queue:
            st.queue.remove(task)
        task.status, task.orc, task.wait_for = "working", orc.name, ""
        st.tasks.append(task)
        foreman = self.foreman
        related = how == "follow-up" or foreman.related(task, orc)
        task.warm = related and foreman.can_resume(orc)
        orc.status, orc.task = "working", task.id
        if task.key and task.key not in orc.keys:
            orc.keys.append(task.key)
        self.emit("pool.assigned", f"{orc.name} ({orc.label}) ← {task.title}"
                  + (" [follow-up]" if how == "follow-up" else "") + (" ♻" if task.warm else ""), task.title)
        cancel = threading.Event()
        self._cancels[orc.name] = cancel
        repo = self._get_repo_root()
        workdir = Path(orc.worktree) if orc.worktree else repo
        prompt = self._prompt(task, orc, how == "follow-up", related)
        runner = type(self).work_runner or (_simulated_work if self.simulated else jobs.run_work)
        resume = orc.session if task.warm else ""
        env = {"ORKCRAFT_ORC": f"{self.building_id}/{orc.name.lower()}"}
        app = self.app

        def work() -> None:
            ok, text, error, cost, tokens, session = False, "", "", None, None, ""
            try:
                text, cost, tokens, session = runner(orc.harness, prompt, workdir, cancel, orc.model, env, resume)
                ok = True
            except InterruptedError:
                error = "stopped"
            except Exception as e:  # one orc's failure must not take the barracks down
                error = str(e)[:300]
            try:
                app.call_from_thread(self.finish, task.id, orc.name, ok, text, error, cost, session, tokens)
            except Exception:
                pass

        threading.Thread(target=work, daemon=True, name=f"pool-{self.building_id}-{orc.name}").start()

    def _prompt(self, task: bk.PoolTask, orc: bk.PoolOrc, follow: bool, related: bool) -> str:
        if task.warm:                    # the session already holds the briefing, the orders and the earlier work
            return "\n\n".join([f"## Task{' (a follow-up of your earlier work)' if follow else ''}: {task.title}",
                                task.text, "Same rules as before: commit on your branch, then a short Markdown report."])
        parts = [f"You are {orc.name}, one of several agents working in parallel, each in its own git worktree.",
                 f"Your worktree is on branch `{orc.branch}`." if orc.branch else "",
                 "Do the task below in this directory. Commit your work on your branch with a clear message; "
                 "do not push and do not open a pull request.",
                 f"## Standing orders\n\n{self.config['orders']}" if self.config.get("orders") else "",
                 f"## Task{' (a follow-up of your earlier work)' if follow else ''}: {task.title}", task.text,
                 "Finish with a short Markdown report: what you changed, what is left."]
        if related and orc.recent:       # a fresh session on related work: a handoff instead of the whole history
            parts.append("## Your recent work (the commits are on your branch)\n\n"
                         + "\n".join(f"- {r}" for r in orc.recent))
        return "\n\n".join(p for p in parts if p)

    def finish(self, task_id: str, orc_name: str, ok: bool, text: str, error: str, cost: float | None,
               session: str, tokens: int | None = None) -> None:
        st = self.state
        task, orc = st.task(task_id), st.orc(orc_name)
        self._cancels.pop(orc_name, None)
        if task is None or orc is None:
            return
        task.status = "done" if ok else "failed"
        task.result, task.error, task.cost_usd, task.tokens = text, error, cost, tokens
        orc.tokens += tokens or 0
        orc.status, orc.task, orc.last = "idle", "", bk.now_iso()
        orc.cost_usd = round(orc.cost_usd + (cost or 0.0), 4)
        orc.done, orc.failed = orc.done + int(ok), orc.failed + int(not ok)
        if session:
            orc.session_tasks = orc.session_tasks + 1 if task.warm else 1
            orc.session = session
        elif ok:                         # a harness without sessions: nothing to resume
            orc.session, orc.session_tasks = "", 0
        if ok:
            gist = next((ln.strip(" #*") for ln in text.splitlines() if ln.strip(" #*")), "")[:160]
            orc.recent = (orc.recent + [f"{task.title} — {gist}" if gist else task.title])[-bk.KEEP_RECENT:]
        foreman = self.foreman
        foreman.learn(orc, ok, cost, tokens)
        st.stats = foreman.stats
        branch = f"\n\n_branch:_ `{orc.branch}`" if orc.branch else ""
        if ok:
            self.emit("pool.done", f"**{task.title}** — {orc.name} ({orc.label})\n\n{text}{branch}", task.title)
        else:
            self.emit("pool.failed", f"**{task.title}** — {orc.name}: {error}", task.title)
        on_run = getattr(self.app, "on_handler_run", None)
        if on_run is not None and error != "stopped":
            on_run(roads.HandlerRun(self.building_id, orc.name.lower(), orc.harness, task.id, 0.0, 0.0,
                                    outcome="done" if ok else "error", markdown=text, error=error, cost_usd=cost))
        nxt = None if st.paused else foreman.next_for(orc, st.queue)
        if nxt is not None:
            st.log(bk.Decision(bk.now_iso(), nxt.id, "follow-up" if nxt.wait_for else "reuse", orc.name,
                               f"{orc.name} is free" + (" — its follow-up" if nxt.wait_for else "")))
            self._assign(nxt, orc, "follow-up" if nxt.wait_for else "reuse")
        elif not st.queue and all(o.status == "idle" for o in st.orcs):
            self.emit("pool.idle", "every task is done", "queue empty")
        st.save()
        self._render_list()

    def on_unmount(self) -> None:
        for c in self._cancels.values():
            c.set()

    # -- the view -----------------------------------------------------------------------------------

    def _render_list(self) -> None:
        st = self.state
        try:
            head, lst = self.query_one("#pool-head", Static), self.query_one("#pool-orcs", OptionList)
        except Exception:
            return
        f = self.foreman
        budget = f" · ${st.spent:.2f}/{f.budget:.0f}" if f.budget else (f" · ${st.spent:.2f}" if st.spent else "")
        head.update(Text.assemble(("⏸ paused · " if st.paused else "", "yellow"),
                                  (f"{len(st.orcs)}/{f.max_orcs} orcs · {len(st.queue)} queued{budget} · "
                                   f"providers {', '.join(h + (':' + m if m else '') for h, m in f.providers)}",
                                   "dim")))
        lst.clear_options()
        for o in st.orcs:
            task = st.task(o.task) if o.task else None
            row = Text(no_wrap=True, overflow="ellipsis")
            row.append(f"{ICON.get(o.status, '·')} {o.tier_icon + ' ' if o.tier_icon else ''}{o.name} ", style="bold")
            row.append(f"{o.label} ", style="cyan")
            row.append(task.title if task else f"✓{o.done} ✗{o.failed}", style="" if task else "dim")
            if o.tokens:
                row.append(f" · {o.tokens / 1000:.0f}k tok", style="dim")
            lst.add_option(Option(row, id=o.name))
        self._detail()

    def _detail(self) -> None:
        st = self.state
        t = Text()
        if st.queue:
            t.append("Queue\n", style="bold")
            for q in st.queue:
                t.append(f"· {q.title}", style="")
                t.append(f"  waits for {q.wait_for}\n" if q.wait_for else "\n", style="dim")
            t.append("\n")
        recent = [x for x in st.tasks if x.status in ("done", "failed")][-5:]
        if recent:
            t.append("Finished\n", style="bold")
            for x in reversed(recent):
                t.append(f"{'✓' if x.status == 'done' else '✗'} {'♻ ' if x.warm else ''}{x.title} — {x.orc}\n",
                         style="green" if x.status == "done" else "red")
            t.append("\n")
        t.append("Foreman's decisions\n", style="bold")
        for d in st.decisions(12):
            t.append(f"{d.at[11:16]} {d.action}", style="yellow")
            t.append(f" {d.orc} " if d.orc else " ")
            t.append(f"{d.why}\n", style="dim")
        if not st.decisions(1):
            t.append("none yet — a road brings tasks here\n", style="dim")
        try:
            self.query_one("#pool-detail", Static).update(t)
        except Exception:
            pass

    # -- the hut ----------------------------------------------------------------------------------

    def mini_status(self) -> list[str]:
        st = self.state
        if not st.orcs and not st.queue:
            return ["no orcs yet", "⏸ paused" if st.paused else "waiting for tasks"]
        lines = [f"{ICON.get(o.status, '·')} {o.tier_icon + ' ' if o.tier_icon else ''}{o.name} {o.label}" for o in st.orcs[:3]]
        if len(st.orcs) > 3:
            lines.append(f"+{len(st.orcs) - 3} more")
        lines.append(("⏸ " if st.paused else "") + f"queue {len(st.queue)}")
        return lines

    def hut_lines(self, widths: list[int]) -> list[str]:
        st, f = self.state, self.foreman
        busy = sum(1 for o in st.orcs if o.status == "working")
        done = sum(1 for t in st.tasks if t.status == "done")
        failed = sum(1 for t in st.tasks if t.status == "failed")
        spent = sum(float((v or {}).get("cost") or 0) for v in st.stats.values())
        state = "PAUSED" if st.paused else "BUSY" if busy else "READY"
        return [f"active: {busy}/{f.max_orcs}", f"idle: {len(st.orcs) - busy} orcs", f"queue: {len(st.queue)} wait",
                f"done {done} · failed {failed}", f"spent: ${spent:.2f}", f"status: {state}"]

    def quick_action(self, action_id: str) -> bool:
        st = self.state
        if action_id == "pool.hire":
            f = self.foreman
            if len(st.orcs) >= f.max_orcs:
                self.app.notify(f"already {len(st.orcs)}/{f.max_orcs} orcs", title="🏕 Barracks")
                return True
            name = next((n for n in bk.NAMES if n not in {o.name for o in st.orcs}), f"Orc{len(st.orcs) + 1}")
            harness, model, why = f.choose_model(bk.PoolTask("", "", ""))
            orc = self.hire(name, harness, model)
            if orc is not None:
                st.log(bk.Decision(bk.now_iso(), "", "hire", name, f"hired by hand; {why}"))
                nxt = f.next_for(orc, st.queue)
                if nxt is not None and not st.paused:
                    self._assign(nxt, orc, "reuse")
            st.save()
            self._render_list()
            return True
        if action_id == "pool.pause":
            st.paused = not st.paused
            if not st.paused:                 # resumed: idle orcs pick up what waited
                for o in st.orcs:
                    nxt = self.foreman.next_for(o, st.queue) if o.status == "idle" else None
                    if nxt is not None:
                        self._assign(nxt, o, "follow-up" if nxt.wait_for else "reuse")
                for q in [q for q in st.queue if not q.wait_for]:
                    if q in st.queue:
                        self._dispatch(q)
            st.save()
            self._render_list()
            self.app.notify("paused" if st.paused else "taking tasks again", title="🏕 Barracks")
            return True
        return False
