"""🏕 Barracks: the steward runs incoming tasks with a pool of orcs and judges their work.

The work — the tasks, the orcs and their runs, the steward's answers and reviews, the pull
requests — is the building's worker's (core/workers/barracks.py). The view draws the steward and the
orcs, the queue and the decisions, and holds the dialogs: a new task, the steward's question, a rule.
"""
from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import OptionList, Static
from textual.widgets.option_list import Option

from orkcraft.core.workers import barracks as worker_mod
from orkcraft.core.workers.barracks import BarracksWorker
from orkcraft.realm import barracks as bk
from orkcraft.realm import pipes
from orkcraft.screens.dialogs import TextPrompt
from orkcraft.screens.typed.base import TypedView

ICON = worker_mod.ICON
TASK_ICON = worker_mod.TASK_ICON
STEWARD = "steward"
PR_CHECK_S = worker_mod.PR_CHECK_S
TICK_S = 15.0


class PoolView(TypedView):
    TYPE = "barracks"
    UI_PANES = {"head": "#pool-head"}       # the TUI keeps its orks' list and the detail as they are
    TAKES_REWORK = True

    def __init__(self, *a, **kw) -> None:
        super().__init__(*a, **kw)
        self._shown = ""

    @property
    def worker(self) -> BarracksWorker:
        return super().worker

    # -- the worker's state, as the view's own (tests and other views read these) -------------------

    @property
    def state(self) -> bk.Barracks:
        return self.worker.state

    @property
    def foreman(self) -> bk.Foreman:
        return self.worker.foreman

    @property
    def keeper(self) -> str:
        return self.worker.keeper

    @property
    def orders(self) -> str:
        return self.worker.orders

    def check_prs(self) -> None:
        self.worker.check_prs()

    def settle_prs(self, prs: dict) -> int:
        return self.worker.settle_prs(prs)

    def receive(self, payload, title: str, markdown: str) -> None:
        self.worker.receive(payload, title, markdown)

    def add_task(self, title: str, text: str, key: str = "", ref: str = "", trail: tuple = ()) -> bk.PoolTask:
        return self.worker.add_task(title, text, key, ref, trail)

    def approved(self, payload: pipes.Payload) -> bool:
        return self.worker.approved(payload)

    def halt(self) -> int:
        """🛑 Halt All: every orc and the steward stop; the barracks pauses (⏸ resumes it)."""
        return self.worker.halt()

    def status(self) -> str:
        return self.worker.status()

    def add_rule(self, rule: str | None) -> bool:
        return self.worker.add_rule(rule)

    def mini_status(self) -> list[str]:
        return self.worker.mini_status()

    def hut_lines(self, widths: list[int]) -> list[str]:
        return self.worker.hut_lines(widths)

    # -- the view -----------------------------------------------------------------------------------

    def compose_body(self) -> ComposeResult:
        yield Static("", id="pool-head", classes="typed-head")
        with Horizontal(classes="typed-row"):
            yield OptionList(id="pool-orcs", classes="typed-list")
            with VerticalScroll(classes="typed-detail"):
                yield Static("", id="pool-detail", classes="-as-written")

    def on_mount(self) -> None:                           # TypedView's on_mount runs too (Textual walks the MRO)
        self.set_interval(TICK_S, self.tick)      # the worker's pace: personas' timers, the queue, the PRs

    def tick(self) -> None:
        w = self.worker
        if w is not None:
            w.tick()

    def on_unmount(self) -> None:
        w = self.worker
        if w is not None:
            w.stop()

    def refresh_data(self) -> None:
        self.worker.start()   # loads once; a restart puts interrupted work back in the queue
        self._render_list()

    def redraw(self) -> None:
        self._render_list()

    # -- the operator's answers ------------------------------------------------------------------------

    def ask_operator(self, task: bk.PoolTask | None = None) -> bool:
        """Open the steward's 🔥: the operator answers the oldest question (or `task`'s)."""
        task = task or next(iter(self.state.asked), None)
        if task is None:
            return False
        if task.draft:
            self.app.push_screen(TextPrompt(f"📤 {task.orc} wants to publish to {task.target or 'a service'} — {task.title}",
                                            placeholder="Enter: publish it as is · or write what to change",
                                            help=task.draft[:1500]), lambda text: self.answer(task.id, text))
            return True
        self.app.push_screen(TextPrompt(f"🔥 {self.keeper} asks — {task.title}", placeholder="your answer",
                                        help=task.question), lambda text: self.answer(task.id, text))
        return True

    def answer(self, task_id: str, text: str | None, propose: bool = True) -> None:
        """The operator's answer goes back to the orc that asked; the steward proposes it as a rule."""
        rule = self.worker.answer(task_id, text)
        if rule and propose:
            self.app.push_screen(TextPrompt(f"📜 Add to {self.keeper}'s rules?", value=rule,
                                            help="Enter keeps it as a rule for every ork; Esc — only this once"),
                                 self.add_rule)

    # -- drawing it ---------------------------------------------------------------------------------

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
        keep = lst.highlighted
        lst.clear_options()
        row = Text(no_wrap=True, overflow="ellipsis")
        rules = len([ln for ln in self.orders.splitlines() if ln.strip()])
        row.append(f"🛡 {self.keeper} ", style="bold")
        row.append(f"steward · {rules} rules", style="dim")
        if st.asked:
            row.append(f" · 🔥 {len(st.asked)} asks", style="bold red")
        lst.add_option(Option(row, id=STEWARD))
        asking = {t.orc for t in st.asked}
        for o in st.orcs:
            task = st.task(o.task) if o.task else None
            row = Text(no_wrap=True, overflow="ellipsis")
            row.append(f"{ICON.get(o.status, '·')} {o.tier_icon + ' ' if o.tier_icon else ''}{o.name} ", style="bold")
            row.append(f"{o.label} ", style="cyan")
            if task is not None:
                row.append(("🔎 " if task.status == "reviewing" else "") + task.title)
            else:
                row.append(f"✓{o.done} ✗{o.failed}", style="dim")
            if o.name in asking:
                row.append(" ?", style="dim")          # its question waits at the steward
            if o.tokens:
                row.append(f" · {o.tokens / 1000:.0f}k tok", style="dim")
            lst.add_option(Option(row, id=o.name))
        if keep is not None and keep < lst.option_count:
            lst.highlighted = keep
        self._detail()

    def on_option_list_option_highlighted(self, event: OptionList.OptionHighlighted) -> None:
        if event.option_list.id == "pool-orcs":
            event.stop()
            self._shown = event.option.id or ""
            self._detail()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        if event.option_list.id == "pool-orcs":
            event.stop()
            if event.option.id == STEWARD:
                self.ask_operator()

    def _detail(self) -> None:
        t = Text()
        if self._shown == STEWARD:
            self._steward_detail(t)
        else:
            self._tasks_detail(t)
        try:
            self.query_one("#pool-detail", Static).update(t)
        except Exception:
            pass

    def _steward_detail(self, t: Text) -> None:
        st = self.state
        t.append(f"🛡 {self.keeper} — the steward\n", style="bold")
        t.append(f"answers the orks' questions from the rules, reviews every task (≤{self.foreman.max_reworks} "
                 "reworks), opens the pull request\n\n", style="dim")
        if st.asked:
            t.append("🔥 Waiting for you (Enter answers)\n", style="bold red")
            for x in st.asked:
                t.append(f"· {x.title} — {x.orc}\n", style="bold")
                t.append(f"  {x.question[:300]}\n", style="")
            t.append("\n")
        t.append("Rules\n", style="bold")
        t.append((self.orders.strip() or "none yet — answers you give can become rules") + "\n\n",
                 style="" if self.orders.strip() else "dim")
        cmd = str(self.config.get("test_cmd") or "")
        t.append(f"tests: {cmd or 'none — the review reads the diff only'} · steward: "
                 f"{self.config.get('steward') or 'claude'} · spent ${st.steward_cost:.2f}\n", style="dim")

    def _tasks_detail(self, t: Text) -> None:
        st = self.state
        if st.asked:
            t.append(f"🔥 {self.keeper} asks — {len(st.asked)} waiting (select 🛡)\n\n", style="bold red")
        if st.queue:
            t.append("Queue\n", style="bold")
            for q in st.queue:
                t.append(f"· {q.title}", style="")
                t.append(f"  rework for {q.wait_for}\n" if q.feedback and q.wait_for else
                         f"  waits for {q.wait_for}\n" if q.wait_for else "\n", style="dim")
            t.append("\n")
        for parent in [x for x in st.tasks if x.plan and x.status in ("planning", "planned", "reviewing", "asked")] + \
                [x for x in st.tasks if x.status == "planning"]:
            t.append(f"🧭 {parent.title}", style="bold")
            t.append(f"  {'planning…' if parent.status == 'planning' else parent.status}\n", style="dim")
            for k in self.worker.children(parent):
                t.append(f"  {TASK_ICON.get(k.status, '·')} {k.sub} · {k.tier}"
                         + (f" · {k.persona}" if k.persona else "") + (f" — {k.orc}" if k.orc else ""), style="")
                t.append(f"  after {', '.join(k.after)}\n" if k.status == "blocked" and k.after else "\n", style="dim")
            t.append("\n")
        recent = [x for x in st.tasks if x.status in ("done", "failed") and not x.parent][-5:]
        if recent:
            t.append("Finished\n", style="bold")
            for x in reversed(recent):
                t.append(f"{TASK_ICON[x.status]} {'♻ ' if x.warm else ''}{x.title} — {x.orc or self.keeper}",
                         style="green" if x.status == "done" else "red")
                tries = f" · {x.attempts} runs" if x.attempts > 1 else ""
                t.append(f"{tries}{' · ' + x.pr if x.pr else ''}\n", style="dim")
            t.append("\n")
        t.append("Decisions\n", style="bold")
        for d in st.decisions(12):
            t.append(f"{d.at[11:16]} {d.action}", style="yellow")
            t.append(f" {d.orc} " if d.orc else " ")
            t.append(f"{d.why}\n", style="dim")
        if not st.decisions(1):
            t.append("none yet — a road brings tasks here\n", style="dim")

    def new_task(self, answer: str | None) -> bk.PoolTask | None:
        """✍ New task: the operator writes to the barracks directly — the title, then the brief (the title
        alone when it is empty)."""
        title, _, brief = (answer or "").partition("\t")
        return self.worker.new_task(title, brief)

    def quick_action(self, action_id: str) -> bool:
        st = self.state
        if action_id == "pool.task":
            self.app.push_screen(TextPrompt("✍ New task for the barracks", placeholder="the task's title",
                                            fields=(("the brief: what to do, where, what done looks like", ""),),
                                            help="Enter goes to the next line, then sends the task to the foreman"),
                                 self.new_task)
            return True
        if action_id in ("pool.answer", "pool.hire"):     # pool.hire: the old id of the key
            return self.ask_operator()
        if action_id == "pool.pause":
            self.worker.pause()
            return True
        return False
