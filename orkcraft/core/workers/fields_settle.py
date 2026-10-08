"""🌾 Task Fields: a task settles before it goes, related ones go together (docs/design/settle-and-join.md).
A part of `FieldsWorker` (core/workers/fields.py), its methods run with the worker as `self`; what it keeps
lives beside the board (realm/cardlore.py), what is related is realm/settle.py's.

On a board that sends its tasks by itself (`send_new`), a new task in To Do is held for `settle` seconds
(120 by default; 0 sends at once, as before). A related task that comes meanwhile joins it — the cards stay
apart on the board, ↳ marks the join — and both go as one task when the first one's time comes. A task
marked Not urgent waits `later_minutes`. A related task that comes after its task went joins it and goes at
once as an addition (`tasks.sent` with the first card's `ref`: a Barracks adds it to that task).

    held      `hold` (when it goes), `came` (when it was first held), `later` (Not urgent)
    joined    `into` (the first card of its task); a near one keeps `hint` (it asks: Join · Keep apart)
    sent      `sent` (when it went)
"""
from __future__ import annotations

import time

from orkcraft.core.workers.fields_lore import card_text
from orkcraft.realm import settle, tasklist
from orkcraft.realm.tasklist import TASK

TITLE = "🌾 Task Fields"


class Settle:
    # -- what it is -----------------------------------------------------------------------------

    @property
    def settle_s(self) -> float:
        """How long a new task waits before it goes; 0 when it goes at once (or the board sends none by itself)."""
        if not self.config.get("send_new"):
            return 0.0
        try:
            return max(0.0, float(self.config.get("settle", settle.SETTLE_S)))
        except (TypeError, ValueError):
            return float(settle.SETTLE_S)

    @property
    def later_s(self) -> float:
        try:
            return max(1.0, float(self.config.get("later_minutes", settle.LATER_MIN))) * 60
        except (TypeError, ValueError):
            return settle.LATER_MIN * 60.0

    def first_of(self, card_id: str) -> str:
        """The first card of the task this card is a part of (itself when it is its own)."""
        first = self.lore.into(card_id)
        return first if first and self.card(first) is not None else card_id

    def joined_cards(self, first: str) -> list[tasklist.Task]:
        """The cards joined to `first`, in the board's order."""
        ids = set(self.lore.joined(first))
        return [c for c in self.cards if c.id in ids]

    def held(self, card_id: str) -> bool:
        return self.lore.hold(card_id) is not None

    def waiting(self) -> list[tasklist.Task]:
        """The tasks held on the board, the soonest first."""
        held = [c for c in self.cards if c.kind == TASK and self.held(c.id)]
        return sorted(held, key=lambda c: self.lore.hold(c.id) or 0.0)

    def _open_tasks(self, but: str) -> list[tasklist.Task]:
        """What a new task may join: a task of its own (joined to none) that waits, or went and is not done."""
        return [c for c in self.cards if c.kind == TASK and c.id != but and c.column != "done"
                and not self.lore.into(c.id) and (self.held(c.id) or self.lore.sent(c.id))]

    # -- a task comes ---------------------------------------------------------------------------

    def arrived(self, card: tasklist.Task) -> None:
        """A new task in To Do on a board that sends by itself: it goes at once (`settle` 0), joins a related
        task, or is held."""
        if self.settle_s <= 0:
            self._emit_sent(card, card_text(card))
            return
        others = self._open_tasks(card.id)
        first, how = settle.best(card_text(card), [(c.id, card_text(c)) for c in others])
        if how == settle.CLOSE:
            self._join(card.id, first)
            return
        now = time.time()
        self.lore.set_hold(card.id, now + self.settle_s, came=now)
        if how == settle.NEAR:
            self.lore.set_hint(card.id, first)
        self.changed()

    def _join(self, card_id: str, first: str) -> None:
        """`card_id` becomes a part of `first`'s task: it waits with it, or goes at once as an addition
        when the task went."""
        lore = self.lore
        for m in lore.joined(card_id):           # what was joined to it goes along to its new first card
            lore.set_into(m, first)
        lore.set_into(card_id, first)
        lore.set_hint(card_id, "")
        lore.set_hold(card_id, None)
        at = lore.hold(first)
        if at is not None:
            if not lore.later(first):
                now = time.time()
                lore.set_hold(first, max(at, settle.goes_at(lore.came(first) or now, now, self.settle_s)))
        elif lore.sent(first):
            card, head = self.card(card_id), self.card(first)
            if card is not None and head is not None:
                self._emit_sent(head, settle.added(card_text(card)))
                lore.set_sent(card_id)
        self.changed()

    # -- a task goes ----------------------------------------------------------------------------

    def release_due(self, now: float | None = None) -> int:
        """Send the held tasks whose time came. How many went."""
        now = time.time() if now is None else now
        due = [c for c in self.waiting() if (self.lore.hold(c.id) or 0.0) <= now and c.column == "todo"]
        for card in due:
            self._go(card)
        return len(due)

    def _go(self, first: tasklist.Task) -> bool:
        """The held task goes: its first card's text and every joined card's under it, as one task."""
        parts = self.joined_cards(first.id)
        sent = self._emit_sent(first, settle.combined(card_text(first), [card_text(c) for c in parts]))
        for c in [first] + parts:
            self.lore.set_sent(c.id)
        self.changed()
        return sent

    def _emit_sent(self, card: tasklist.Task, text: str) -> bool:
        return self.emit("tasks.sent", text, tasklist.plain(card.title), ref=self.ref(card))

    def send_now(self, card_id: str) -> bool:
        """Send: a held task (or the task a card is joined to) goes now with all its cards; any other card
        goes as it is. True when a road took it."""
        first = self.card(self.first_of(card_id))
        if first is None:
            return False
        if self.held(first.id):
            return self._go(first)
        card = self.card(card_id)
        sent = card is not None and self._emit_sent(card, card_text(card))
        if sent and card.kind == TASK:
            self.lore.set_sent(card.id)
        return sent

    # -- the person's say -----------------------------------------------------------------------

    def set_later(self, card_id: str, later: bool | None = None) -> bool:
        """Not urgent (or Urgent again; None flips it): the task waits `later_minutes`, else `settle` from now.
        A joined card speaks for its whole task. What it is now."""
        first = self.first_of(card_id)
        if not self.held(first):
            return False
        lore, now = self.lore, time.time()
        on = (not lore.later(first)) if later is None else bool(later)
        lore.set_hold(first, now + (self.later_s if on else self.settle_s))
        lore.set_later(first, on)
        self.changed()
        return on

    def join(self, card_id: str, first: str) -> bool:
        """Join a task to another one by hand (Join, Join with…). True when it joined."""
        card, head = self.card(card_id), self.card(self.first_of(first))
        if card is None or head is None or card.id == head.id or card.kind != TASK or head.kind != TASK:
            return False
        if card.column == "done" or head.column == "done":
            return False
        self._join(card.id, head.id)
        return True

    def split(self, card_id: str) -> bool:
        """Split off: the card is a task of its own again, held while it waits (one that went with its task
        stays as it is: the orks have it already)."""
        card = self.card(card_id)
        if card is None or not self.lore.into(card_id):
            return False
        self.lore.set_into(card_id, "")
        self._own(card)
        self.changed()
        return True

    def keep_apart(self, card_id: str) -> bool:
        """Keep apart: the card stops asking whether to join the one it looks like."""
        if not self.lore.hint(card_id):
            return False
        self.lore.set_hint(card_id, "")
        self.changed()
        return True

    def _own(self, card: tasklist.Task) -> None:
        """A card on its own again: held while it waits in To Do and has not gone, else left as it is."""
        if card.kind != TASK or card.column != "todo" or self.settle_s <= 0 or self.lore.sent(card.id):
            return
        now = time.time()
        self.lore.set_hold(card.id, now + self.settle_s, came=now)

    # -- keeping it straight --------------------------------------------------------------------

    def left_todo(self, card_id: str) -> None:
        """The card left To Do by the person's hand: it is not going anywhere by itself."""
        lore = self.lore
        if lore.hold(card_id) is not None or lore.hint(card_id):
            lore.set_hold(card_id, None)
            lore.set_hint(card_id, "")

    def tidy(self) -> None:
        """A card joined to one gone from the board is its own again; a hint at one gone is dropped; a held
        card out of To Do (a hand edit moved it) is not held any more."""
        lore = self.lore
        for card in self.cards:
            if card.column != "todo" and lore.hold(card.id) is not None:
                lore.set_hold(card.id, None)
            first = lore.into(card.id)
            if first and self.card(first) is None:
                lore.set_into(card.id, "")
                self._own(card)
            hint = lore.hint(card.id)
            if hint and (self.card(hint) is None or not self.held(hint)):
                lore.set_hint(card.id, "")

    def follow_first(self, first: tasklist.Task, lane: str) -> None:
        """The work on a task came back (assigned, done, failed): its joined cards move with its first card."""
        for c in self.joined_cards(first.id):
            if c.kind == TASK and c.column != lane:
                self.move(c.id, lane)
