"""🪔 Clan Fire: the clan reviews a document, the steward lets it go, sends it back or asks you.

A cart that arrives is a document to review (a Barracks result, a file, text); ▶ asks for a repo
path or the text itself. The review (realm/team.py) runs off the UI thread and shows turn by turn.
Then the steward decides: `team.approved` sends the document on as it is, `team.rework` sends it back
with the comments — straight to the building that wrote it when that one redoes work (a Barracks: the
prepare → review → rework loop needs no road back, which would close a loop) and down its roads — and either way the
full report goes to `loot/` as `team.artifact_ready`. When the steward asks, 🔥 shows on the hut and ▶
takes your answer. Documents that arrive mid-review wait in line.

Briefs live in the building's state folder: `steward.md` (beside `steward_prompt`) and `roles/<role>.md`
per member — written as empty templates when a member joins, so you know where to put the knowledge.
+ adds a member (`Role`, `harness[:model]`).
"""
from __future__ import annotations

import re
import threading
from pathlib import Path

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import Markdown, OptionList, Static
from textual.widgets.option_list import Option

from orkcraft.realm import pipes, roads, shelves
from orkcraft.realm import team as tm
from orkcraft.screens.dialogs import TextPrompt
from orkcraft.screens.typed.base import TypedView

ICON = "🪔"
VERDICT = {"approve": ("✓ approves", "green"), "changes": ("✎ changes", "yellow"), "veto": ("⛔ veto", "red"),
           "rework": ("↩ rework", "yellow"), "ask": ("🔥 asks you", "red")}
OUTCOME = {"approved": "approved ✓", "rework": "sent back ↩", "budget": "stopped: budget", "asked": "🔥 waits for you",
           "error": "failed", "stopped": "stopped", "running": "reviewing…"}
_COMMENT = re.compile(r"<!--.*?-->", re.S)


def _simulated(harness: str, prompt: str, model: str) -> tuple[str, None]:
    """The sandbox: everyone approves and the steward lets it go — no model is called."""
    if prompt.startswith("You are the steward"):
        return "DECISION: approve\n\n_(demo — simulated; agents do not run in the sandbox)_", None
    return "APPROVE — _(demo — simulated)_", None


def _title_of(text: str) -> str:
    for line in text.strip().splitlines():
        line = line.strip().lstrip("#").strip().strip("*").strip()
        if line:
            return line[:80]
    return "document"


class TeamView(TypedView):
    TYPE = "council"
    runner = None              # tests put a (harness, prompt, model) → (text, cost) here

    def __init__(self, *a, **kw) -> None:
        super().__init__(*a, **kw)
        self.current: tm.Discussion | None = None
        self.history: list[tm.Discussion] = []
        self.waiting: list[tuple] = []     # (title, text, path, ref, trail, source) that came mid-review
        self._cart: tuple[str, tuple, str] = ("", (), "")   # the ref, trail and source of the document under review
        self._cancel: threading.Event | None = None
        self._busy = False

    @property
    def team(self) -> list[tm.Member]:
        return tm.members_of(self.config)

    @property
    def veto(self) -> set[str]:
        return tm.veto_of(self.config)

    @property
    def max_cycles(self) -> int:
        return int(self.config.get("max_cycles") or tm.DEFAULT_CYCLES)

    @property
    def budget(self) -> float:
        b = self.config.get("budget_usd")
        return float(tm.DEFAULT_BUDGET if b is None else b)

    # -- the briefs ---------------------------------------------------------------------------------

    def role_file(self, role: str) -> Path:
        return self.state_dir / "roles" / f"{tm.slug(role)}.md"

    @property
    def steward_file(self) -> Path:
        return self.state_dir / "steward.md"

    def _rel(self, path: Path) -> str:
        return shelves.rel_to(self._get_repo_root(), path)

    @staticmethod
    def _knowledge(path: Path) -> str:
        """A brief's text without its template comments; "" when nothing but headings was written."""
        try:
            text = _COMMENT.sub("", path.read_text(encoding="utf-8")).strip()
        except OSError:
            return ""
        return text if any(line.strip() and not line.lstrip().startswith("#") for line in text.splitlines()) else ""

    def ensure_briefs(self) -> None:
        """Empty templates for the steward and every member, so the operator knows where to write."""
        todo = [(self.steward_file, "Steward", "when to let a document go, when to send it back, when to "
                                               "ask the operator; what matters most")]
        todo += [(self.role_file(m.role), m.role, "what this role checks, what it knows, its red lines; "
                                                  "links to the files it should read") for m in self.team]
        for path, who, what in todo:
            if path.exists():
                continue
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(f"# {who}\n\n<!-- {ICON} Clan Fire brief: {what}. Write below; as long as the "
                                f"knowledge needs. -->\n", encoding="utf-8")
            except OSError:
                pass

    def brief_of(self, member: tm.Member) -> tuple[str, str]:
        path = self.role_file(member.role)
        text = self._knowledge(path)
        return (self._rel(path), text) if text else ("", "")

    def steward(self) -> tm.Steward:
        own = str(self.config.get("steward_prompt") or self.config.get("goal") or "").strip()
        known = self._knowledge(self.steward_file)
        harness, _, model = str(self.config.get("moderator") or "claude").partition(":")
        return tm.Steward(own, harness.strip() or "claude", model.strip(), known,
                          self._rel(self.steward_file) if known else "")

    # -- the view ------------------------------------------------------------------------------------

    def compose_body(self) -> ComposeResult:
        yield Static("", id="team-head", classes="typed-head")
        with Horizontal(classes="typed-row"):
            yield OptionList(id="team-turns", classes="typed-list")
            with VerticalScroll(classes="typed-detail"):
                yield Markdown("", id="team-read")

    def refresh_data(self) -> None:
        self.ensure_briefs()
        self.history = tm.load_all(self.state_dir)
        if self.current is None and self.history:
            self.current = self.history[0]
        self._render_list()

    # -- the review ----------------------------------------------------------------------------------

    def start(self, text: str, title: str = "", path: str = "", ref: str = "", trail: tuple = (),
              source: str = "") -> bool:
        """Review a document: its text, and its repo-relative path when it is a file. `ref` and `trail`
        are the cart's: they travel on with what the review sends; a rework goes back to `source`."""
        text = text.strip()
        if not text and path:
            try:
                text = (self._get_repo_root() / path).read_text(encoding="utf-8")
            except OSError:
                text = ""
        if not text:
            self.app.notify("nothing to review", title=f"{ICON} Clan Fire")
            return False
        title = (title or _title_of(text)).strip()
        if self._busy or (self.current is not None and self.current.outcome == "asked"):
            self.waiting.append((title, text, path, ref, tuple(trail), source))
            self._render_list()
            return False
        if getattr(self.app, "gold_exhausted", lambda: False)():
            self.app.notify("🪙 budget exhausted — a review costs model calls", title=f"{ICON} Clan Fire",
                            severity="warning")
            return False
        cycle = tm.cycle_of(tm.load_all(self.state_dir, 200), title)
        d = tm.new(title, text, path, cycle)
        if not path:                       # Claude reads it from disk; the prompt stays small
            try:
                f = self.state_dir / "documents" / f"{d.id}.md"
                f.parent.mkdir(parents=True, exist_ok=True)
                f.write_text(text, encoding="utf-8")
                d.doc_path = self._rel(f)
            except OSError:
                pass
        self.current = d
        self._cart = (ref, tuple(trail), source)     # what came in: travels on with what the review sends
        self._run()
        return True

    def _run(self) -> None:
        d, team = self.current, self.team
        if d is None:
            return
        self.ensure_briefs()
        self._busy, self._cancel = True, threading.Event()
        cancel, app = self._cancel, self.app
        repo, env = self._get_repo_root(), {"ORKCRAFT_ORC": f"{self.building_id}/clan"}
        runner = type(self).runner or (_simulated if self.simulated else
                                       (lambda h, p, m: roads.run_agent(h, p, repo, env, cancel, m, web=True)[:2]))
        steward, veto, cycles, budget = self.steward(), self.veto, self.max_cycles, self.budget
        briefs = {m.role: self.brief_of(m) for m in team}

        def on_turn(_d: tm.Discussion, _t: tm.Turn) -> None:
            try:
                app.call_from_thread(self._render_list)
            except Exception:
                pass

        def work() -> None:
            try:
                tm.run(d, team, steward, veto, cycles, budget, runner, on_turn, cancel,
                       lambda m: briefs.get(m.role, ("", "")))
            except Exception as e:  # the app goes on whatever happens in a review
                d.outcome, d.error = "error", str(e)[:300]
            try:
                app.call_from_thread(self.finish, d)
            except Exception:
                pass

        self._render_list()
        threading.Thread(target=work, daemon=True, name=f"clan-{self.building_id}").start()

    def finish(self, d: tm.Discussion) -> None:
        self._busy, self._cancel = False, None
        try:
            tm.save(self.state_dir, d)
        except OSError:
            pass
        if d.outcome in ("approved", "rework"):
            root = self._get_repo_root()
            path = pipes.write_loot(root, self.building_id, d.title[:80], tm.report_markdown(d, self.team))
            ref, trail, source = self._cart
            ref = ref or f"{self.building_id}:{d.id}"   # the rework comes back under it
            trail = trail + (pipes.hop(self.building_id, "clan", "team", None, d.spent or None, outcome=d.outcome),)
            self.emit("team.artifact_ready", shelves.rel_to(root, path), d.title[:80], trail=trail, ref=ref)
            if d.outcome == "approved":
                self.emit("team.approved", d.doc, d.title, trail=trail, ref=ref)
            else:
                back = tm.rework_markdown(d, self.max_cycles)
                self.emit("team.rework", back, d.title, trail=trail, ref=ref)
                self._send_back(source, pipes.Payload(pipes.TEXT, back, self.building_id, "team.rework", d.title,
                                                      trail, ref))
            self.app.notify(f"{d.title[:60]}: {OUTCOME[d.outcome]}", title=f"{ICON} Clan Fire")
        elif d.outcome == "asked":
            self.app.notify(f"{d.title[:60]}: {d.question[:200]}", title=f"🔥 {ICON} Clan Fire asks")
        on_run = getattr(self.app, "on_handler_run", None)
        if on_run is not None and d.outcome != "asked":
            on_run(roads.HandlerRun(self.building_id, "clan", "team", d.id, 0.0, 0.0,
                                    outcome="error" if d.outcome == "error" else "done",
                                    markdown=d.decision, error=d.error, cost_usd=d.spent or None))
        self.history = tm.load_all(self.state_dir)
        self._render_list()
        if self.waiting and d.outcome != "asked":
            title, text, path, ref, trail, source = self.waiting.pop(0)
            self.start(text, title, path, ref, trail, source)

    def _send_back(self, source: str, payload: pipes.Payload) -> None:
        """A rework goes straight back to the building that wrote the document (a road back would close
        a loop); without one that redoes work, the operator is told."""
        back = getattr(self.app, "return_for_rework", None)
        if source and source != self.building_id and callable(back) and back(source, payload):
            return
        try:
            self.app.notify(f"{payload.title[:60]}: sent back, but no Barracks wrote it — rework it yourself",
                            title=f"{ICON} Clan Fire", severity="warning")
        except Exception:
            pass

    def reply(self, text: str | None) -> None:
        d = self.current
        if not text or d is None or d.outcome != "asked":
            return
        if self.out_of_gold("the review"):
            return
        tm.answer(d, text)
        self._run()

    def receive(self, payload, title: str, markdown: str) -> None:
        if payload.kind == pipes.FILE and (self._get_repo_root() / payload.value).is_file():
            self.start("", payload.title or title, payload.value, payload.ref, payload.trail,
                       payload.source)                                  # members read the file itself
        else:
            self.start(markdown or payload.value, payload.title or title, "", payload.ref, payload.trail,
                       payload.source)

    def on_unmount(self) -> None:
        if self._cancel is not None:
            self._cancel.set()

    def halt(self) -> int:
        """🛑 Halt All: the review stops where it is."""
        if self._cancel is None or self._cancel.is_set() or not self._busy:
            return 0
        self._cancel.set()
        return 1

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

    def _tally(self, d: tm.Discussion) -> str:
        r = d.reviews()
        return " ".join(f"{mark}{n}" for mark, n in (("✓", sum(t.verdict == "approve" for t in r)),
                                                     ("✎", sum(t.verdict == "changes" for t in r)),
                                                     ("⛔", sum(t.verdict == "veto" for t in r))) if n)

    def mini_status(self) -> list[str]:
        d = self.current
        veto = self.veto
        lines = [f"{m.tier_icon + ' ' if m.tier_icon else ''}{m.role}{' ⛔' if m.role.lower() in veto else ''} {m.label}"
                 for m in self.team[:3]]
        if len(self.team) > 3:
            lines.append(f"+{len(self.team) - 3} more")
        if d is not None and d.outcome == "asked":
            lines.insert(0, "🔥 the steward asks")
        elif d is not None and d.outcome == "running":
            lines.append(f"C{d.cycle}/{self.max_cycles} {self._tally(d)} ${d.spent:.2f}".strip())
        elif d is not None:
            lines.append(OUTCOME.get(d.outcome, d.outcome))
        if self.waiting:
            lines.append(f"{len(self.waiting)} queued")
        return lines

    def hut_lines(self, widths: list[int]) -> list[str]:
        d = self.current
        veto = self.veto
        lines = [f"{m.tier_icon + ' ' if m.tier_icon else ''}{m.role}{' ⛔' if m.role.lower() in veto else ''}: {m.label}"
                 for m in self.team[:3]]
        if len(self.team) > 3:
            lines.append(f"+{len(self.team) - 3} more")
        if d is None:
            lines.append("no review yet")
        elif d.outcome == "asked":
            lines.insert(0, "🔥 the steward asks")
        elif d.outcome == "running":
            lines += [f"cycle: {d.cycle}/{self.max_cycles}", f"reviews: {self._tally(d) or '…'}"]
        else:
            lines += [f"last: {OUTCOME.get(d.outcome, d.outcome)}", f"cycle: {d.cycle}/{self.max_cycles}"]
        if self.waiting:
            lines.append(f"queued: {len(self.waiting)}")
        return lines

    def quick_action(self, action_id: str) -> bool:
        if action_id == "team.start":
            d = self.current
            if d is not None and d.outcome == "asked":
                self.app.push_screen(TextPrompt("🔥 The steward asks", placeholder="your answer", help=d.question),
                                     self.reply)
            elif self._busy:
                self.app.notify("a review is under way", title=f"{ICON} Clan Fire")
            else:
                def go(answer: str | None) -> None:
                    if not answer:
                        return
                    answer = answer.strip()
                    if (self._get_repo_root() / answer).is_file():
                        self.start("", "", answer)
                    else:
                        self.start(answer)

                self.app.push_screen(TextPrompt(f"{ICON} What should the clan review?",
                                                placeholder="a repo path, or paste the text"), go)
            return True
        if action_id == "team.add":
            def done(answer: str | None) -> None:
                if not answer:
                    return
                role, harness = (answer.split("\t") + [""])[:2]
                member = tm.parse_member(f"{role.strip()}:{harness.strip() or 'claude'}")
                if member is None:
                    self.app.notify("a member is a role and claude or agy[:model]", title=f"{ICON} Not added",
                                    severity="error")
                    return
                current = [f"{m.role}:{m.label}" for m in self.team]
                if self.save_config({"members": current + [f"{member.role}:{member.label}"]}):
                    self.ensure_briefs()
                    self.app.notify(f"its brief: {self._rel(self.role_file(member.role))}",
                                    title=f"{ICON} {member.role} joined")
                    self._render_list()

            self.app.push_screen(TextPrompt(f"{ICON} Add a member of the clan", placeholder="role, e.g. Marketing",
                                            fields=(("claude · agy · agy:gemini-3.1-pro-high", "claude"),)), done)
            return True
        return False
