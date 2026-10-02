"""⚔ Agent Team: agents with roles discuss until they agree on one artifact.

▶ Start asks for the topic (the goal is the default); a cart that arrives starts one with what it
carries. The discussion (realm/team.py) runs off the UI thread and shows round by round; when the
team agrees — or the moderator decides at the last round — the artifact goes to `loot/` and out
as `team.artifact_ready`. A member's QUESTION pauses it: 🔥 on the hut, and ▶ asks the operator.
+ adds a member (`Role`, `harness[:model]`).
"""
from __future__ import annotations

import threading

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import Markdown, OptionList, Static
from textual.widgets.option_list import Option

from orkcraft.realm import pipes, roads, shelves
from orkcraft.realm import team as tm
from orkcraft.screens.dialogs import TextPrompt
from orkcraft.screens.typed.base import TypedView

KIND = {"draft": "✍", "review": "🔎", "revise": "⚖", "decide": "⚖", "question": "🔥", "answer": "💬"}
def _simulated(harness: str, prompt: str, model: str) -> tuple[str, None]:
    """The sandbox: a draft, then everyone agrees — no model is called."""
    if "Review it from your role" in prompt:
        return "AGREE — _(demo — simulated)_", None
    topic = prompt.split("Topic: ", 1)[-1].splitlines()[0]
    return f"# {topic}\n\n_(demo — simulated draft; agents do not run in the sandbox)_", None


OUTCOME = {"agreed": "agreed ✓", "no_consensus": "decided (no consensus)", "budget": "stopped: budget",
           "asked": "🔥 waits for you", "error": "failed", "stopped": "stopped", "running": "discussing…"}


class TeamView(TypedView):
    TYPE = "council"
    runner = None              # tests put a (harness, prompt, model) → (text, cost) here

    def __init__(self, *a, **kw) -> None:
        super().__init__(*a, **kw)
        self.current: tm.Discussion | None = None
        self.history: list[tm.Discussion] = []
        self.waiting: str | None = None           # a topic that arrived while one ran
        self._cancel: threading.Event | None = None
        self._busy = False

    @property
    def team(self) -> list[tm.Member]:
        return tm.members_of(self.config)

    @property
    def max_rounds(self) -> int:
        return int(self.config.get("max_rounds") or tm.DEFAULT_ROUNDS)

    @property
    def budget(self) -> float:
        b = self.config.get("budget_usd")
        return float(tm.DEFAULT_BUDGET if b is None else b)

    def compose_body(self) -> ComposeResult:
        yield Static("", id="team-head", classes="typed-head")
        with Horizontal(classes="typed-row"):
            yield OptionList(id="team-turns", classes="typed-list")
            with VerticalScroll(classes="typed-detail"):
                yield Markdown("", id="team-read")

    def refresh_data(self) -> None:
        self.history = tm.load_all(self.state_dir)
        if self.current is None and self.history:
            last = self.history[0]
            self.current = last
        self._render_list()

    # -- the discussion -----------------------------------------------------------------------------

    def start(self, topic: str) -> bool:
        topic = topic.strip() or str(self.config.get("goal", "")).strip()
        if not topic:
            self.app.notify("a discussion needs a topic (or a goal in the settings)", title="⚔ Agent Team")
            return False
        if self._busy:
            self.waiting = topic
            return False
        if getattr(self.app, "gold_exhausted", lambda: False)():
            self.app.notify("🪙 budget exhausted — a discussion costs model calls", title="⚔ Agent Team",
                            severity="warning")
            return False
        self.current = tm.new(topic, str(self.config.get("goal", "")))
        self._run()
        return True

    def _run(self) -> None:
        d, team = self.current, self.team
        if d is None:
            return
        self._busy, self._cancel = True, threading.Event()
        cancel, app = self._cancel, self.app
        repo, env = self._get_repo_root(), {"ORKCRAFT_ORC": f"{self.building_id}/team"}
        runner = type(self).runner or (_simulated if self.simulated else
                                       (lambda h, p, m: roads.run_agent(h, p, repo, env, cancel, m)[:2]))
        moderator, rounds, budget = str(self.config.get("moderator") or "claude"), self.max_rounds, self.budget

        def on_turn(_d: tm.Discussion, _t: tm.Turn) -> None:
            try:
                app.call_from_thread(self._render_list)
            except Exception:
                pass

        def work() -> None:
            try:
                tm.run(d, team, moderator, rounds, budget, runner, on_turn, cancel)
            except Exception as e:  # the app goes on whatever happens in a discussion
                d.outcome, d.error = "error", str(e)[:300]
            try:
                app.call_from_thread(self.finish, d)
            except Exception:
                pass

        self._render_list()
        threading.Thread(target=work, daemon=True, name=f"team-{self.building_id}").start()

    def finish(self, d: tm.Discussion) -> None:
        self._busy, self._cancel = False, None
        try:
            tm.save(self.state_dir, d)
        except OSError:
            pass
        if d.outcome in ("agreed", "no_consensus"):
            path = pipes.write_loot(self._get_repo_root(), self.building_id, d.topic[:80],
                                    tm.artifact_markdown(d, self.team))
            rel = shelves.rel_to(self._get_repo_root(), path)
            self.emit("team.artifact_ready", rel, d.topic[:80])
            self.app.notify(f"{OUTCOME[d.outcome]} — {rel}", title="⚔ Agent Team")
        elif d.outcome == "asked":
            self.app.notify(f"{d.asking} asks: {d.question}", title="🔥 Agent Team")
        on_run = getattr(self.app, "on_handler_run", None)
        if on_run is not None and d.outcome != "asked":
            on_run(roads.HandlerRun(self.building_id, "team", "team", d.id, 0.0, 0.0,
                                    outcome="error" if d.outcome == "error" else "done",
                                    markdown=d.draft, error=d.error, cost_usd=d.spent or None))
        self.history = tm.load_all(self.state_dir)
        self._render_list()
        if self.waiting and d.outcome != "asked":
            nxt, self.waiting = self.waiting, None
            self.start(nxt)

    def reply(self, text: str | None) -> None:
        d = self.current
        if not text or d is None or d.outcome != "asked":
            return
        tm.answer(d, text)
        self._run()

    def receive(self, payload, title: str, markdown: str) -> None:
        self.start(markdown or payload.value)

    def on_unmount(self) -> None:
        if self._cancel is not None:
            self._cancel.set()

    # -- the view -----------------------------------------------------------------------------------

    def _render_list(self) -> None:
        d = self.current
        try:
            head, lst = self.query_one("#team-head", Static), self.query_one("#team-turns", OptionList)
        except Exception:
            return
        team = ", ".join(f"{m.role} ({m.label})" for m in self.team)
        limits = f"≤{self.max_rounds} rounds · ≤${self.budget:.2f}"
        if d is None:
            head.update(Text(f"{team} · {limits} · ▶ starts a discussion", style="dim"))
            lst.clear_options()
            self._read("_No discussion yet._")
            return
        head.update(Text.assemble((f"{d.topic[:60]} · ", "bold"),
                                  (f"round {d.round}/{self.max_rounds} · ${d.spent:.2f} · {OUTCOME.get(d.outcome, d.outcome)}"
                                   f" · {team}", "dim")))
        keep = lst.highlighted
        lst.clear_options()
        lst.add_option(Option(Text("📜 the artifact", style="bold"), id="artifact"))
        for i, t in enumerate(d.turns):
            row = Text(no_wrap=True, overflow="ellipsis")
            row.append(f"R{t.round} {KIND.get(t.kind, '·')} {t.role} ", style="bold")
            if t.kind == "review":
                row.append("agrees" if t.agree else "objects", style="green" if t.agree else "yellow")
            else:
                row.append(t.text.splitlines()[0][:60] if t.text else "", style="dim")
            lst.add_option(Option(row, id=f"t{i}"))
        lst.highlighted = keep if keep is not None and keep < lst.option_count else 0
        self._show(lst.get_option_at_index(lst.highlighted).id)

    def _show(self, oid: str | None) -> None:
        d = self.current
        if d is None or oid is None:
            return
        if oid == "artifact":
            self._read(tm.artifact_markdown(d, self.team) if d.draft else "_no draft yet_")
            return
        t = d.turns[int(oid[1:])]
        self._read(f"**R{t.round} · {t.role} · {t.kind}**" + (f" · ${t.cost:.2f}" if t.cost else "") + f"\n\n{t.text}")

    def _read(self, md: str) -> None:
        try:
            self.query_one("#team-read", Markdown).update(md)
        except Exception:
            pass

    def on_option_list_option_highlighted(self, event: OptionList.OptionHighlighted) -> None:
        if event.option_list.id == "team-turns":
            event.stop()
            self._show(event.option.id)

    # -- the hut ----------------------------------------------------------------------------------

    def mini_status(self) -> list[str]:
        d = self.current
        lines = [f"{m.role} {m.label}" for m in self.team[:3]]
        if len(self.team) > 3:
            lines.append(f"+{len(self.team) - 3} more")
        if d is not None and d.outcome == "asked":
            lines.insert(0, f"🔥 {d.asking} asks")
        elif d is not None and d.outcome == "running":
            lines.append(f"R{d.round}/{self.max_rounds} ${d.spent:.2f}")
        elif d is not None:
            lines.append(OUTCOME.get(d.outcome, d.outcome))
        return lines

    def hut_lines(self, widths: list[int]) -> list[str]:
        d = self.current
        lines = [f"{m.role}: {m.label}" for m in self.team[:3]]
        if len(self.team) > 3:
            lines.append(f"+{len(self.team) - 3} more")
        if d is None:
            lines.append("no debate yet")
        elif d.outcome == "asked":
            lines.insert(0, f"🔥 {d.asking} asks")
        elif d.outcome == "running":
            lines += [f"round: {d.round}/{self.max_rounds}", f"spent: ${d.spent:.2f}"]
        else:
            lines += [f"outcome: {OUTCOME.get(d.outcome, d.outcome)}", f"rounds: {d.round}/{self.max_rounds}"]
        return lines

    def quick_action(self, action_id: str) -> bool:
        if action_id == "team.start":
            d = self.current
            if d is not None and d.outcome == "asked":
                self.app.push_screen(TextPrompt(f"🔥 {d.asking} asks", placeholder="your answer", help=d.question),
                                     self.reply)
            elif self._busy:
                self.app.notify("a discussion is under way", title="⚔ Agent Team")
            else:
                self.app.push_screen(TextPrompt("⚔ What should the team agree on?",
                                                value=str(self.config.get("goal", ""))),
                                     lambda topic: self.start(topic) if topic else None)
            return True
        if action_id == "team.add":
            def done(answer: str | None) -> None:
                if not answer:
                    return
                role, harness = (answer.split("\t") + [""])[:2]
                member = tm.parse_member(f"{role.strip()}:{harness.strip() or 'claude'}")
                if member is None:
                    self.app.notify("a member is a role and claude or agy[:model]", title="⚔ Not added",
                                    severity="error")
                    return
                current = [f"{m.role}:{m.label}" for m in self.team]
                if self.save_config({"members": current + [f"{member.role}:{member.label}"]}):
                    self._render_list()

            self.app.push_screen(TextPrompt("⚔ Add an agent", placeholder="role, e.g. Security reviewer",
                                            fields=(("claude · agy · agy:gemini-3.1-pro-high", "claude"),)), done)
            return True
        return False
