"""🪔 Clan Fire: the clan reviews a document, the steward lets it go, sends it back or asks you.

A cart that arrives is a document to review (a Barracks result, a file, text); ▶ asks for a repo
path or the text itself. The review, the steward's decision, the queue and the briefs are the
building's worker's (core/workers/council.py); the view shows the review turn by turn and holds the
dialogs. When the steward asks, 🔥 shows on the hut and ▶ takes your answer.

Briefs live in the building's state folder: `steward.md` (beside `steward_prompt`) and `roles/<role>.md`
per member — written as empty templates when a member joins, so you know where to put the knowledge.
+ adds a member (`Role`, `harness[:model]`).
"""
from __future__ import annotations

from pathlib import Path

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import Markdown, OptionList, Static
from textual.widgets.option_list import Option

from orkcraft.core.workers import council as worker_mod
from orkcraft.core.workers.council import CouncilWorker
from orkcraft.realm import team as tm
from orkcraft.screens.dialogs import TextPrompt
from orkcraft.screens.typed.base import TypedView

ICON = worker_mod.ICON
VERDICT = {"approve": ("✓ approves", "green"), "changes": ("✎ changes", "yellow"), "veto": ("⛔ veto", "red"),
           "rework": ("↩ rework", "yellow"), "ask": ("🔥 asks you", "red")}
OUTCOME = worker_mod.OUTCOME
_title_of = worker_mod.title_of


class TeamView(TypedView):
    TYPE = "council"

    @property
    def worker(self) -> CouncilWorker:
        return super().worker

    # -- the worker's state, as the view's own (tests and other views read these) -------------------

    @property
    def current(self) -> tm.Discussion | None:
        return self.worker.current

    @property
    def history(self) -> list[tm.Discussion]:
        return self.worker.history

    @property
    def waiting(self) -> list[tuple]:
        return self.worker.waiting

    @property
    def _busy(self) -> bool:
        return self.worker.busy

    @property
    def team(self) -> list[tm.Member]:
        return self.worker.team

    @property
    def veto(self) -> set[str]:
        return self.worker.veto

    @property
    def max_cycles(self) -> int:
        return self.worker.max_cycles

    @property
    def budget(self) -> float:
        return self.worker.budget

    def role_file(self, role: str) -> Path:
        return self.worker.role_file(role)

    @property
    def steward_file(self) -> Path:
        return self.worker.steward_file

    def ensure_briefs(self) -> None:
        self.worker.ensure_briefs()

    def brief_of(self, member: tm.Member) -> tuple[str, str]:
        return self.worker.brief_of(member)

    def steward(self) -> tm.Steward:
        return self.worker.steward()

    def start(self, text: str, title: str = "", path: str = "", ref: str = "", trail: tuple = (),
              source: str = "") -> bool:
        return self.worker.review(text, title, path, ref, trail, source)

    def reply(self, text: str | None) -> None:
        self.worker.reply(text)

    def receive(self, payload, title: str, markdown: str) -> None:
        self.worker.receive(payload, title, markdown)

    def halt(self) -> int:
        """🛑 Halt All: the review stops where it is."""
        return self.worker.halt()

    def status(self) -> str:
        return self.worker.status()

    def mini_status(self) -> list[str]:
        return self.worker.mini_status()

    def hut_lines(self, widths: list[int]) -> list[str]:
        return self.worker.hut_lines(widths)

    # -- the view ------------------------------------------------------------------------------------

    def compose_body(self) -> ComposeResult:
        yield Static("", id="team-head", classes="typed-head")
        with Horizontal(classes="typed-row"):
            yield OptionList(id="team-turns", classes="typed-list")
            with VerticalScroll(classes="typed-detail"):
                yield Markdown("", id="team-read")

    def refresh_data(self) -> None:
        self.worker.refresh()
        self._render_list()

    def redraw(self) -> None:
        self._render_list()

    def on_unmount(self) -> None:
        w = self.worker
        if w is not None:
            w.halt()

    # -- the list and the reader ---------------------------------------------------------------------

    def _clan_text(self) -> str:
        veto = self.veto
        return ", ".join(f"{m.tier_icon + ' ' if m.tier_icon else ''}{m.role}{' ⛔' if m.role.lower() in veto else ''}"
                         f" ({m.label})" for m in self.team)

    def _render_list(self) -> None:
        d = self.current
        try:
            head, lst = self.query_one("#team-head", Static), self.query_one("#team-turns", OptionList)
        except Exception:
            return
        limits = f"≤{self.max_cycles} cycles · ≤${self.budget:.2f}" + (f" · {len(self.waiting)} queued"
                                                                       if self.waiting else "")
        if d is None:
            head.update(Text(f"{self._clan_text()} · {limits} · ▶ reviews a document", style="dim"))
            lst.clear_options()
            self._read("_No review yet._ Send a document down a road, or ▶ with a path or the text.")
            return
        head.update(Text.assemble((f"{d.title[:60]} · ", "bold"),
                                  (f"cycle {d.cycle}/{self.max_cycles} · ${d.spent:.2f} · "
                                   f"{OUTCOME.get(d.outcome, d.outcome)} · {self._clan_text()} · {limits}", "dim")))
        keep = lst.highlighted
        lst.clear_options()
        lst.add_option(Option(Text("📜 the report", style="bold"), id="report"))
        lst.add_option(Option(Text("📄 the document", style="bold"), id="doc"))
        for i, t in enumerate(d.turns):
            row = Text(no_wrap=True, overflow="ellipsis")
            if t.kind == "answer":
                row.append("💬 Operator ", style="bold")
                row.append(t.text.splitlines()[0][:60] if t.text else "", style="dim")
            else:
                row.append(f"{'⚖ ' if t.kind == 'decide' else ''}{t.role} ", style="bold")
                label, style = VERDICT.get(t.verdict, (t.verdict, "dim"))
                row.append(label, style=style)
            lst.add_option(Option(row, id=f"t{i}"))
        lst.highlighted = keep if keep is not None and keep < lst.option_count else 0
        self._show(lst.get_option_at_index(lst.highlighted).id)

    def _show(self, oid: str | None) -> None:
        d = self.current
        if d is None or oid is None:
            return
        if oid == "report":
            self._read(tm.report_markdown(d, self.team))
            return
        if oid == "doc":
            self._read((f"_`{d.doc_path}`_\n\n" if d.doc_path else "") + d.doc)
            return
        t = d.turns[int(oid[1:])]
        self._read(f"**{t.role} · {t.verdict or t.kind}**" + (f" · _{t.note}_" if t.note else "") +
                   (f" · ${t.cost:.2f}" if t.cost else "") + f"\n\n{t.text}")

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

    def quick_action(self, action_id: str) -> bool:
        if action_id == "team.start":
            d = self.current
            if d is not None and d.outcome == "asked":
                self.app.push_screen(TextPrompt("🔥 The steward asks", placeholder="your answer", help=d.question),
                                     self.reply)
            elif self._busy:
                self.app.notify("a review is under way", title=f"{ICON} Clan Fire")
            else:
                self.app.push_screen(TextPrompt(f"{ICON} What should the clan review?",
                                                placeholder="a repo path, or paste the text"),
                                     lambda answer: answer and self.worker.review_input(answer))
            return True
        if action_id == "team.add":
            def done(answer: str | None) -> None:
                if not answer:
                    return
                role, harness = (answer.split("\t") + [""])[:2]
                self.worker.add_member(role, harness)

            self.app.push_screen(TextPrompt(f"{ICON} Add a member of the clan", placeholder="role, e.g. Marketing",
                                            fields=(("claude · agy · codex · agy:gemini-3.1-pro-high", "claude"),)), done)
            return True
        return False
