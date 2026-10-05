"""📦 Loot Vault's work: the review checkpoint on a road (realm/gate.py), the files agents changed,
and what passed (realm/vault.py).

A cart that arrives is checked against the building's rules: it passes at once (`loot.passed`
carries it on, it is kept in the vault) or it is held in the queue. The person accepts a held
cart (as it is, or their edit of it), sends it back to its source for rework — after
`max_rework` rounds it stays here as *needs you* — or drops it. Every decision is also what the
person thinks of the building that made the cart (`feedback.signal`): accepted as it was is a
light 👍, an edit is judged by `realm/edits.py`, a rework or a drop is a 👎.

A cart goes back (and an approved draft is told so) directly, not by a road: the face says how
(`rework_back`, `approved_back`, which the TUI points at its views); without one, the building
whose worker takes rework is the one in the cart's trail. The changed files of the working tree
(or of its `path`) are reviewed one by one: accepted, rejected (rolled back, kept aside) and
restored. A held text cart is edited in a draft file (`draft_path`) the person opens in Lake;
`accept_draft` accepts what the file says.
"""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Callable

from orkcraft.core.workers import Worker
from orkcraft.realm import catalog, edits, feedback, gate, generated, jobs, lake, pipes, vault

EGRESS = ("catapult",)                   # types that send things out of the town
STATUS = {gate.NEEDS_YOU: "🔥", gate.HELD: "⏸", gate.REWORK: "↩"}


def label(item: gate.Item) -> str:
    first = item.value.strip().splitlines()[0][:60] if item.value.strip() else ""
    return item.title or first or item.ref


class LootWorker(Worker):
    TYPE = "loot"

    def __init__(self, town, building_id: str) -> None:
        super().__init__(town, building_id)
        self.rows: list[generated.Generated] = []
        self.stored: list[vault.Stored] = []
        self.rejected: list[dict] = []
        self.branches: dict[str, tuple[generated.Branch, list[generated.Generated]]] = {}   # item id → its branch files
        self.error = ""
        self.rework_back: Callable[[str, pipes.Payload], str] | None = None    # the face's way back
        self.approved_back: Callable[[str, pipes.Payload], str] | None = None
        self._queue: gate.Queue | None = None

    # -- what it is -------------------------------------------------------------------------------

    @property
    def review(self) -> generated.Review:
        return generated.Review(self.repo_root, self.state_dir, str(self.config.get("path", "")))

    @property
    def queue(self) -> gate.Queue:
        if self._queue is None:
            self._queue = gate.Queue(self.state_dir)
        return self._queue

    def names(self) -> dict[str, str]:
        """Building ids → titles, for the chain line."""
        scroll = self.town.scroll
        return {b.id: b.title for b in getattr(scroll, "buildings", ())} if scroll is not None else {}

    # -- its life ---------------------------------------------------------------------------------

    def start(self) -> None:
        self.refresh()

    def refresh(self) -> None:
        """Look again: the changed files, what passed, the branches of the waiting carts."""
        try:
            self.rows, self.error = self.review.files(), ""
        except (RuntimeError, OSError, ValueError) as e:
            self.rows, self.error = [], str(e)[:200]
        self.stored = vault.stored(self.state_dir)
        self.branches = {it.id: found for it in self.queue.open() if (found := self.branch(it.hops)) is not None}
        try:
            self.rejected = self.review.rejected()
        except (OSError, ValueError):
            self.rejected = []
        self.changed()

    def status(self) -> str:
        return "ERROR" if self.error else ""

    def burning(self) -> bool:
        """A cart waits for the person: the hut burns."""
        return any(i.status in (gate.HELD, gate.NEEDS_YOU) for i in self.queue.items)

    # -- the checkpoint ---------------------------------------------------------------------------

    def receive(self, payload, title: str, markdown: str) -> None:
        """A cart came by road: it passes by the rules, or waits in the queue."""
        if payload.kind == pipes.TEXT and markdown and markdown != payload.value:
            payload = pipes.Payload(payload.kind, markdown, payload.source, payload.mode, payload.title or title,
                                    payload.trail, payload.ref)
        back = self.queue.by_ref(payload.ref)
        why = gate.reasons(payload, self.config, self._rule_context(payload))
        if back is not None:
            why = [f"back from rework (round {back.attempts})"] + why
        if not why:
            if not self._pass(payload):              # it stays here: someone should read it
                feedback.await_view(self.repo_root, self.building_id, feedback.maker(payload.trail),
                                    payload.title or title)
        else:
            item = self.queue.arrive(payload, why)
            self.toast(f"{item.title or item.value[:60]} — {'; '.join(why)}", title=f"📦 {self.btype.title}: held")
        self.refresh()

    def _rule_context(self, payload: pipes.Payload) -> gate.Context:
        files: list[str] = []
        wt = gate.worktree_of(payload)
        if wt and (self.repo_root / wt).is_dir():
            try:
                files = [g.path for g in generated.Review(self.repo_root / wt, self.state_dir / "wt").files()]
            except (RuntimeError, OSError, ValueError):
                pass
        if (found := self.branch(payload.trail)) is not None:       # and what it committed on its branch
            files += [g.path for g in found[1] if g.path not in files]
        return gate.Context(files, self._leaves_town())

    def branch(self, trail: tuple) -> tuple[generated.Branch, list[generated.Generated]] | None:
        """The branch a cart's work was committed on, with its files; None without one (or no git)."""
        h = gate.branch_of(trail)
        if h is None or not (wt := self.repo_root / h.worktree).is_dir():
            return None
        try:
            br = generated.Branch(wt, h.branch, h.base or jobs.TaskGit().base_of(self.repo_root))
            return br, br.files()
        except (RuntimeError, OSError, ValueError, subprocess.SubprocessError):
            return None

    def _leaves_town(self) -> bool:
        scroll = self.town.scroll
        if scroll is None:
            return False
        for b in getattr(scroll, "buildings", ()):
            spec = self.town.custom_specs.get(b.id)
            t = catalog.type_of(spec) if spec else None
            if t and t.id in EGRESS and any(r.source == self.building_id and r.event == "loot.passed" for r in b.roads):
                return True
        return False

    def _pass(self, payload: pipes.Payload) -> bool:
        """Carry the cart on, and keep it in the vault (the history of what passed). True when a
        road took it on."""
        item = vault.store(self.repo_root, self.building_id, self.state_dir, payload.kind, payload.value,
                           payload.title, payload.source, trail=payload.trail, ref=payload.ref)
        went = self.emit("loot.passed", payload.value, payload.title, trail=payload.trail, ref=payload.ref)
        return self.emit("loot.stored", item.path, item.title, trail=payload.trail, ref=payload.ref) or went

    def maker(self, item: gate.Item) -> str:
        """The building whose ork wrote the cart: what the person's decision is about. "" for a cart
        no ork worked on (a file dropped in a Pit): then the decision teaches nobody."""
        return feedback.maker(item.trail)

    def _give_back(self, how: str, source: str, payload: pipes.Payload) -> str:
        """Hand a cart straight back to a building (a rework, an approval): the face's way when it has
        one, else the worker in its trail that takes it. Its id, or "" when nobody does."""
        hook = self.rework_back if how == "rework" else self.approved_back
        if hook is not None:
            return hook(source, payload)
        for bid in [source] + [h.building for h in reversed(payload.trail) if h.building != source]:
            w = self.town.workers.get(bid) or self.town.worker(bid)
            if how == "rework" and getattr(w, "TAKES_REWORK", False):
                self.town.deliver(bid, payload, payload.title, payload.value)
                return bid
            approved = getattr(w, "approved", None) if how == "approved" else None
            if callable(approved) and approved(payload):
                return bid
        return ""

    # -- decisions on carts -----------------------------------------------------------------------

    def accept_item(self, item: gate.Item, value: str | None = None, source: str = "loot.accepted") -> None:
        """Accept a held cart — as it is, or `value`, the person's edit of it — and say so to its maker."""
        before, gave_up = item.value, item.status == gate.NEEDS_YOU
        self.queue.accept(item, value)
        payload = item.payload()
        self._pass(payload)
        self._judge_accept(item, before, value, source, gave_up)
        last = payload.trail[-1] if payload.trail else None
        if last is not None and last.outcome == gate.APPROVAL and (to := self._give_back("approved", item.source, payload)):
            self.toast(f"approved: {to} may publish {item.title or item.ref}", title="📦 Loot")
        self.draft_path(item, make=False).unlink(missing_ok=True)
        self.refresh()

    def _judge_accept(self, item: gate.Item, before: str, value: str | None, source: str,
                      gave_up: bool = False) -> None:
        """What accepting says about the maker. Past the rework limit (`gave_up`) the person takes the
        cart as it is to be done with it: that is no 👍 (the rounds were already 👎), only an edit
        still says what was wrong."""
        root, made_by = self.repo_root, self.maker(item)
        if not made_by:
            return
        edit = edits.classify(before, value) if value is not None and item.kind == pipes.TEXT else None
        if edit is None or edit.kind == edits.SAME:
            if not gave_up:
                feedback.signal(root, made_by, True, source, value=before)
        elif edit.kind == edits.FILLED:
            if not gave_up:
                feedback.signal(root, made_by, True, "loot.filled", value=before, note=edit.summary)
        else:
            private = lake.personal(value or "")                 # a personal note's text never reaches a model
            feedback.signal(root, made_by, False, f"loot.{edit.kind}", value=before, note=edit.summary,
                            tag="format" if edit.kind == edits.RESHAPED else "", edit="" if private else edit.diff)
            if not private:
                feedback.signal(root, made_by, True, f"loot.{edit.kind}", value=value, weight=0.0,
                                note="the person's version: what it should have been")

    def rework_item(self, item: gate.Item, reason: str, tag: str = "") -> str:
        """Send `item` back with `reason` (`tag`: the chip picked, `feedback.REASONS`); past the limit
        (or with nobody to take it) it needs you. Returns its status."""
        tag, kind = (tag, next((k for t, _, k in feedback.REASONS if t == tag), "logic")) if tag else \
            feedback.reason_tag(reason)
        made_by = self.maker(item)                                 # "" when no ork made it: nothing is kept
        feedback.signal(self.repo_root, made_by, False, "loot.rework", value=item.value, note=reason, tag=tag,
                        kind=kind, blamed=feedback.trail_blame(item.trail, made_by, kind))
        ok, why = self.queue.can_rework(item, self.config)
        if not ok:
            feedback.signal(self.repo_root, made_by, False, "loot.needs_you", value=item.value,
                            note=f"{why}: {reason}", tag=tag)
        if ok:
            self.queue.rework(item, reason)
            md = gate.rework_markdown(item, reason, self.spec.get("title") or self.btype.title)
            back = pipes.Payload(pipes.TEXT, md, self.building_id, "loot.rework",
                                 f"rework: {item.title or item.ref}", item.hops, item.ref)
            if to := self._give_back("rework", item.source, back):
                self.emit("loot.rework", md, back.title, trail=item.hops, ref=item.ref)
                self.toast(f"sent back to {to} (round {item.attempts}): {reason}", title="📦 Loot")
                self.refresh()
                return item.status
            item.attempts -= 1
            item.notes.pop()
            why = f"{item.source} cannot take work back"
        self.queue.needs_you(item, f"{reason} — not sent back: {why}")
        self.emit("loot.needs_you", f"**{item.title or item.ref}** needs you: {why}\n\n{reason}", item.title,
                  trail=item.hops, ref=item.ref)
        self.toast(f"{item.title or item.ref}: {why} — it waits for you", title="🔥 Loot", severity="warning")
        self.refresh()
        return item.status

    def drop(self, item: gate.Item) -> None:
        if item.status in (gate.HELD, gate.NEEDS_YOU):
            feedback.signal(self.repo_root, self.maker(item), False, "loot.dropped", value=item.value,
                            note=f"dropped: {item.title or item.ref}")
        self.queue.drop(item)
        self.draft_path(item, make=False).unlink(missing_ok=True)
        self.refresh()

    def accept_all(self) -> int:
        """Accept every held cart (not the ones that need you). How many passed."""
        held = [i for i in self.queue.items if i.status == gate.HELD]
        for item in held:
            self.queue.accept(item)
            self._pass(item.payload())
            self._judge_accept(item, item.value, None, "loot.accepted_all")
        self.refresh()
        self.toast(f"{len(held)} cart{'s' if len(held) != 1 else ''} passed", title="📦 Loot")
        return len(held)

    # -- a cart edited in Lake --------------------------------------------------------------------

    def draft_path(self, item: gate.Item, make: bool = True) -> Path:
        """The file a held text cart is edited in (`.orkcraft/loot/<id>/drafts/<item>.md`), written with
        the cart's text the first time (`make`)."""
        path = self.state_dir / "drafts" / f"{item.id}.md"
        if make and not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(item.value, encoding="utf-8")
        return path

    def edited(self, item: gate.Item) -> bool:
        p = self.draft_path(item, make=False)
        try:
            return p.is_file() and p.read_text(encoding="utf-8") != item.value
        except OSError:
            return False

    def accept_draft(self, item: gate.Item) -> None:
        """Accept the person's version: what the draft file says now."""
        p = self.draft_path(item, make=False)
        value = p.read_text(encoding="utf-8") if p.is_file() else None
        self.accept_item(item, value if value is not None and value != item.value else None)

    # -- decisions on files -----------------------------------------------------------------------

    def accept(self, rel: str) -> None:
        self.review.accept(rel)
        self.emit("generator.accepted", rel, rel)

    def reject(self, rel: str) -> None:
        self.review.reject(rel)
        self.emit("generator.rejected", rel, rel)

    def restore(self, rel: str, at: str) -> None:
        self.review.restore(rel, at)

    def accept_files(self) -> int:
        """Accept every changed file still waiting. How many."""
        waiting = [g.path for g in self.rows if not g.reviewed]
        for rel in waiting:
            self.accept(rel)
        self.refresh()
        self.toast(f"{len(waiting)} file{'s' if len(waiting) != 1 else ''} accepted", title="🛠 File Generator")
        return len(waiting)

    # -- the hut ----------------------------------------------------------------------------------

    def _queue_lines(self) -> list[str]:
        q = self.queue
        held, you = q.count(gate.HELD), q.count(gate.NEEDS_YOU)
        if not held and not you and not q.count(gate.REWORK):
            return []
        parts = [f"{held} held"] + ([f"{you} needs you"] if you else []) + \
            ([f"{q.count(gate.REWORK)} in rework"] if q.count(gate.REWORK) else [])
        lines = [" · ".join(parts)]
        lines += [f"{STATUS[i.status]} {label(i)[:40]}" for i in q.open()[:3]]
        return lines

    def mini_status(self) -> list[str]:
        if self.error:
            return [f"⚠ {self.error[:40]}"]
        queue = self._queue_lines()
        waiting = [g for g in self.rows if not g.reviewed]
        stored = [f"📦 {len(self.stored)} stored"] if self.stored else []
        if not self.rows:
            return queue + stored or ["nothing generated"]
        lines = queue + [f"{len(waiting)} to review" if waiting else "all reviewed ✓"] + stored
        lines += [f"* {g.path.rsplit('/', 1)[-1]}" for g in waiting[:3]]
        return lines

    def hut_lines(self, widths: list[int]) -> list[str]:
        if self.error:
            return [f"⚠ {self.error[:40]}"]
        waiting = [g for g in self.rows if not g.reviewed]
        files = [f"{len(waiting)} files to review" if waiting else "all reviewed ✓" if self.rows else ""]
        files += [f"* {g.path.rsplit('/', 1)[-1]}" for g in waiting]
        lines = [ln for ln in self._queue_lines() + files if ln][:6] or ["nothing held"]
        return lines + [""] * (6 - len(lines)) + [f"passed: {len(self.stored)}"]
