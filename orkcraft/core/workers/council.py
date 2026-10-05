"""🪔 Clan Fire's work: the clan reviews a document, the steward lets it go, sends it back or asks you.

A cart that arrives is a document to review (a Barracks result, a file, text). The review
(realm/team.py) runs in a thread of the worker, turn by turn (`changed()` after each). Then the steward
decides: `team.approved` sends the document on as it is, `team.rework` sends it back with the comments —
straight to the building that wrote it when that one redoes work (a Barracks: the prepare → review →
rework loop needs no road back, which would close a loop) and down its roads — and either way the full
report goes to `loot/` as `team.artifact_ready`. When the steward asks, the building burns and `reply`
takes the person's answer. Documents that arrive mid-review wait in line.

Briefs live in the building's state folder: `steward.md` (beside `steward_prompt`) and `roles/<role>.md`
per member — written as empty templates when a member joins, so you know where to put the knowledge.
"""
from __future__ import annotations

import threading
from pathlib import Path

from orkcraft.core import delivery
from orkcraft.core.workers import Worker
from orkcraft.core.workers.barracks import take_back
from orkcraft.realm import pipes, roads, shelves
from orkcraft.realm import team as tm

ICON = "🪔"
OUTCOME = {"approved": "approved ✓", "rework": "sent back ↩", "budget": "stopped: budget", "asked": "🔥 waits for you",
           "error": "failed", "stopped": "stopped", "running": "reviewing…"}
KEEP_HISTORY = 30               # past reviews read back


def title_of(text: str) -> str:
    for line in text.strip().splitlines():
        line = line.strip().lstrip("#").strip().strip("*").strip()
        if line:
            return line[:80]
    return "document"


class CouncilWorker(Worker):
    TYPE = "council"
    runner = None              # tests put a (harness, prompt, model) → (text, cost) here

    def __init__(self, town, building_id: str) -> None:
        super().__init__(town, building_id)
        self.current: tm.Discussion | None = None
        self.history: list[tm.Discussion] = []
        self.waiting: list[tuple] = []     # (title, text, path, ref, trail, source) that came mid-review
        self._cart: tuple[str, tuple, str] = ("", (), "")   # the ref, trail and source of the document under review
        self._cancel: threading.Event | None = None
        self._busy = False

    # -- what it is -----------------------------------------------------------------------------

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

    @property
    def busy(self) -> bool:
        return self._busy

    # -- the briefs ---------------------------------------------------------------------------------

    def role_file(self, role: str) -> Path:
        return self.state_dir / "roles" / f"{tm.slug(role)}.md"

    @property
    def steward_file(self) -> Path:
        return self.state_dir / "steward.md"

    def rel(self, path: Path) -> str:
        return shelves.rel_to(self.repo_root, path)

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
        text = tm.brief_text(path)
        return (self.rel(path), text) if text else ("", "")

    def steward(self) -> tm.Steward:
        own = str(self.config.get("steward_prompt") or self.config.get("goal") or "").strip()
        known = tm.brief_text(self.steward_file)
        harness, _, model = str(self.config.get("moderator") or "claude").partition(":")
        return tm.Steward(own, harness.strip() or "claude", model.strip(), known,
                          self.rel(self.steward_file) if known else "")

    # -- its life -------------------------------------------------------------------------------

    def start(self) -> None:
        self.refresh()

    def refresh(self) -> None:
        """The briefs' templates and the past reviews, read again."""
        self.ensure_briefs()
        self.history = tm.load_all(self.state_dir, KEEP_HISTORY)
        if self.current is None and self.history:
            self.current = self.history[0]
        self.changed()

    def status(self) -> str:
        d = self.current
        if d is not None and d.outcome == "asked":
            return "ASKS"
        return "BUSY" if self._busy else ""

    # -- the review ----------------------------------------------------------------------------------

    def review(self, text: str, title: str = "", path: str = "", ref: str = "", trail: tuple = (),
               source: str = "") -> bool:
        """Review a document: its text, and its repo-relative path when it is a file. `ref` and `trail`
        are the cart's: they travel on with what the review sends; a rework goes back to `source`."""
        text = text.strip()
        if not text and path:
            try:
                text = (self.repo_root / path).read_text(encoding="utf-8")
            except OSError:
                text = ""
        if not text:
            self.toast("nothing to review", title=f"{ICON} Clan Fire")
            return False
        title = (title or title_of(text)).strip()
        if self._busy or (self.current is not None and self.current.outcome == "asked"):
            self.waiting.append((title, text, path, ref, tuple(trail), source))
            self.changed()
            return False
        if not self.town.budget_ok() and not self.simulated:
            self.toast("🪙 budget exhausted — a review costs model calls", title=f"{ICON} Clan Fire",
                       severity="warning")
            return False
        cycle = tm.cycle_of(tm.load_all(self.state_dir, 200), title)
        d = tm.new(title, text, path, cycle)
        if not path:                       # Claude reads it from disk; the prompt stays small
            try:
                f = self.state_dir / "documents" / f"{d.id}.md"
                f.parent.mkdir(parents=True, exist_ok=True)
                f.write_text(text, encoding="utf-8")
                d.doc_path = self.rel(f)
            except OSError:
                pass
        self.current = d
        self._cart = (ref, tuple(trail), source)     # what came in: travels on with what the review sends
        self._run()
        return True

    def review_input(self, answer: str) -> bool:
        """▶ Review: a repo path is a file to review, anything else the text itself."""
        answer = (answer or "").strip()
        if not answer:
            return False
        if "\n" not in answer and len(answer) < 500 and (self.repo_root / answer).is_file():
            return self.review("", "", answer)
        return self.review(answer)

    def _run(self) -> None:
        d, team = self.current, self.team
        if d is None:
            return
        self.ensure_briefs()
        self._busy, self._cancel = True, threading.Event()
        cancel = self._cancel
        repo, env = self.repo_root, {"ORKCRAFT_ORC": f"{self.building_id}/clan"}
        runner = type(self).runner or (tm.simulated if self.simulated else
                                       (lambda h, p, m: roads.run_agent(h, p, repo, env, cancel, m, web=True)[:2]))
        steward, veto, cycles, budget = self.steward(), self.veto, self.max_cycles, self.budget
        briefs = {m.role: self.brief_of(m) for m in team}

        def on_turn(_d: tm.Discussion, _t: tm.Turn) -> None:
            self.changed()

        def work() -> None:
            try:
                tm.run(d, team, steward, veto, cycles, budget, runner, on_turn, cancel,
                       lambda m: briefs.get(m.role, ("", "")))
            except Exception as e:  # the town goes on whatever happens in a review
                d.outcome, d.error = "error", str(e)[:300]
            try:
                self.town.call(self.finish, d)
            except Exception:
                pass

        self.changed()
        threading.Thread(target=work, daemon=True, name=f"clan-{self.building_id}").start()

    def finish(self, d: tm.Discussion) -> None:
        self._busy, self._cancel = False, None
        try:
            tm.save(self.state_dir, d)
        except OSError:
            pass
        if d.outcome in ("approved", "rework"):
            root = self.repo_root
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
            self.toast(f"{d.title[:60]}: {OUTCOME[d.outcome]}", title=f"{ICON} Clan Fire")
        elif d.outcome == "asked":
            self.toast(f"{d.title[:60]}: {d.question[:200]}", title=f"🔥 {ICON} Clan Fire asks")
        if d.outcome != "asked":
            delivery.ran(self.town, roads.HandlerRun(self.building_id, "clan", "team", d.id, 0.0, 0.0,
                                                     outcome="error" if d.outcome == "error" else "done",
                                                     markdown=d.decision, error=d.error, cost_usd=d.spent or None))
        self.history = tm.load_all(self.state_dir, KEEP_HISTORY)
        self.changed()
        if self.waiting and d.outcome not in ("asked", "stopped"):    # after a halt the queue waits for ▶ or a cart
            title, text, path, ref, trail, source = self.waiting.pop(0)
            self.review(text, title, path, ref, trail, source)

    def _send_back(self, source: str, payload: pipes.Payload) -> None:
        """A rework goes straight back to the building that wrote the document (a road back would close
        a loop); without one that redoes work, the operator is told."""
        if source and source != self.building_id and take_back(self.town, source, payload):
            return
        self.toast(f"{payload.title[:60]}: sent back, but no Barracks wrote it — rework it yourself",
                   title=f"{ICON} Clan Fire", severity="warning")

    def reply(self, text: str | None) -> bool:
        """The person's answer to the steward's question: the review goes on."""
        d = self.current
        if not text or d is None or d.outcome != "asked":
            return False
        if self.out_of_gold("the review"):
            return False
        tm.answer(d, text)
        self._run()
        return True

    def add_member(self, role: str, harness: str = "claude") -> tm.Member | None:
        """A new member of the clan (`role`, `harness[:model]`), its brief an empty template."""
        member = tm.parse_member(f"{role.strip()}:{harness.strip() or 'claude'}")
        if member is None:
            self.toast("a member is a role and claude, agy or codex[:model]", title=f"{ICON} Not added",
                       severity="error")
            return None
        current = [f"{m.role}:{m.label}" for m in self.team]
        if not self.save_config({"members": current + [f"{member.role}:{member.label}"]}):
            return None
        self.ensure_briefs()
        self.toast(f"its brief: {self.rel(self.role_file(member.role))}", title=f"{ICON} {member.role} joined")
        self.changed()
        return member

    def receive(self, payload, title: str, markdown: str) -> None:
        if payload.kind == pipes.FILE and (self.repo_root / payload.value).is_file():
            self.review("", payload.title or title, payload.value, payload.ref, payload.trail,
                        payload.source)                                  # members read the file itself
        else:
            self.review(markdown or payload.value, payload.title or title, "", payload.ref, payload.trail,
                        payload.source)

    def halt(self) -> int:
        """🛑 Halt All: the review stops where it is."""
        if self._cancel is None or self._cancel.is_set() or not self._busy:
            return 0
        self._cancel.set()
        return 1

    # -- the hut ----------------------------------------------------------------------------------

    def tally(self, d: tm.Discussion) -> str:
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
            lines.append(f"C{d.cycle}/{self.max_cycles} {self.tally(d)} ${d.spent:.2f}".strip())
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
            lines += [f"cycle: {d.cycle}/{self.max_cycles}", f"reviews: {self.tally(d) or '…'}"]
        else:
            lines += [f"last: {OUTCOME.get(d.outcome, d.outcome)}", f"cycle: {d.cycle}/{self.max_cycles}"]
        if self.waiting:
            lines.append(f"queued: {len(self.waiting)}")
        return lines
