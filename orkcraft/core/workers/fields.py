"""🌾 Task Fields' work: the board — its cards and lanes, kept in `TASKS.md` or a tasks folder
(realm/tasklist.py) — and what each change sends.

`refresh()` reads the board (the face calls it on a timer: a hand edit of the file is seen
there) and sends `tasks.created` / `tasks.status_changed` for a task, `notes.created` for a note.
The acts (add, move, edit, colour, flip, send, remove) change the file and send the same events
for what they changed. A cart is a new card. The hut's * marks what is new since the board was
last looked at (`seen.json`).
"""
from __future__ import annotations

import json

from orkcraft.core.workers import Worker
from orkcraft.realm import tasklist
from orkcraft.realm.tasklist import COLUMNS, LABELS, NOTE, TASK

TITLE = "🌾 Task Fields"
SHORT = {"todo": "To Do", "in_progress": "Doing", "done": "Done"}
MODES = ("board", "tasks", "notes")


class FieldsWorker(Worker):
    TYPE = "fields"

    def __init__(self, town, building_id: str) -> None:
        super().__init__(town, building_id)
        self.cards: list[tasklist.Task] = []
        self.lanes: list[tasklist.Lane] = []
        self.error = ""
        self._last: list[tasklist.Task] | None = None

    def start(self) -> None:
        self.refresh()

    # -- what it is -----------------------------------------------------------------------------

    @property
    def store(self) -> tasklist.TaskList:
        return tasklist.TaskList(self.repo_root, str(self.config.get("path", "")))

    @property
    def mode(self) -> str:
        m = str(self.config.get("mode") or "board")
        return m if m in MODES else "board"

    @property
    def tasks(self) -> list[tasklist.Task]:
        """The task cards (what the status events and other buildings count)."""
        return [c for c in self.cards if c.kind == TASK]

    @property
    def notes(self) -> list[tasklist.Task]:
        return [c for c in self.cards if c.kind == NOTE]

    def card(self, card_id: str) -> tasklist.Task | None:
        return next((t for t in self.cards if t.id == card_id), None)

    def visible_lanes(self) -> list[tasklist.Lane]:
        lanes = list(self.lanes) or [tasklist.Lane(c, LABELS[c]) for c in COLUMNS]
        for name in self.config.get("lanes") or []:                 # lanes of notes always there
            lid = tasklist.slug(str(name))
            if lid not in COLUMNS and not any(ln.id == lid for ln in lanes):
                lanes.append(tasklist.Lane(lid, str(name)))
        if self.mode == "tasks":
            return [ln for ln in lanes if ln.kind == TASK]
        if self.mode == "notes":
            notes = [ln for ln in lanes if ln.kind == NOTE]
            return notes or [tasklist.Lane(tasklist.NOTES, "Notes")]
        return lanes

    def note_lanes(self) -> list[str]:
        """Where a task goes when it becomes a note: the board's lanes of notes, else the configured ones."""
        return [ln.id for ln in self.lanes if ln.kind == NOTE] or \
               [tasklist.slug(str(n)) for n in self.config.get("lanes") or []] or [tasklist.NOTES]

    # -- seen (the hut's *) ---------------------------------------------------------------------

    def seen(self) -> set[str]:
        try:
            return set(json.loads((self.state_dir / "seen.json").read_text(encoding="utf-8")))
        except (OSError, ValueError, TypeError):
            return set()

    def mark_seen(self) -> None:
        try:
            self.state_dir.mkdir(parents=True, exist_ok=True)
            (self.state_dir / "seen.json").write_text(json.dumps(sorted(t.id for t in self.cards)), encoding="utf-8")
        except OSError:
            pass

    # -- reading the board ----------------------------------------------------------------------

    def refresh(self) -> None:
        """Read the board again; what changed since the last look is sent down the roads."""
        try:
            store = self.store
            self.lanes, self.cards, self.error = store.lanes(), store.load(), ""
        except (OSError, ValueError) as e:
            self.lanes, self.cards, self.error = [], [], str(e)[:200]
        for event_id, card, detail in tasklist.changes(self._last, self.cards):
            self.announce(event_id, card, detail)
        if self._last is None and not (self.state_dir / "seen.json").exists():
            self.mark_seen()                     # the first look: nothing is new yet
        self._last = list(self.cards)
        self.changed()

    def _sync(self) -> None:
        """Reload after its own change, without sending again what was just sent."""
        store = self.store
        self.lanes, self.cards = store.lanes(), store.load()
        self._last = list(self.cards)
        self.mark_seen()
        self.changed()

    def announce(self, event_id: str, card: tasklist.Task, detail: str) -> None:
        if event_id == "notes.created":
            self.emit(event_id, card_text(card), tasklist.plain(card.title), ref=self.ref(card))
        else:
            self.emit(event_id, card.id, f"{tasklist.plain(card.title)} · {detail}")

    def ref(self, card: tasklist.Task) -> str:
        return f"{self.building_id}:{card.id}"

    # -- acts -----------------------------------------------------------------------------------

    def add(self, title: str, lane: str = "todo", body: str = "") -> tasklist.Task | None:
        try:
            card = self.store.add(title, lane, body)
        except (OSError, ValueError) as e:
            self.toast(str(e), title=TITLE, severity="error")
            return None
        if card.kind == TASK:
            self.announce("tasks.created", card, LABELS[card.column])
        else:
            self.announce("notes.created", card, card.column)
        self._sync()
        return card

    def add_lane(self, name: str) -> str:
        """A new lane of notes on the board (a folder of notes). Its id, "" when it was not made."""
        try:
            lane = self.store.add_lane(name)
        except (OSError, ValueError) as e:
            self.toast(str(e), title=TITLE, severity="error")
            return ""
        self._sync()
        return lane.id

    def receive(self, payload, title: str, markdown: str) -> None:
        """A cart is a new card — a task in To Do (a note in `notes` mode): its title, else its first
        line; the rest of what it carries is the card's text."""
        lines = (markdown or str(payload.value or "")).splitlines()
        first_i = next((i for i, ln in enumerate(lines) if ln.strip(" #*-")), None)
        first = " ".join(lines[first_i].strip(" #*-").split()) if first_i is not None else ""
        name = " ".join((payload.title or title or first).split())[:120]
        if not name:
            return
        rest = lines[first_i + 1:] if first_i is not None and first == name else lines
        lane = self.visible_lanes()[0].id if self.mode == "notes" else "todo"
        self.add(name, lane, "\n".join(rest).strip()[:2000])

    def move(self, card_id: str, column: str) -> bool:
        card = self.card(card_id)
        try:
            before, after = self.store.move(card_id, column)
        except (OSError, ValueError, KeyError) as e:
            self.toast(str(e), title=TITLE, severity="error")
            return False
        if before != after and card is not None:
            moved = tasklist.Task(card.id, card.title, after, card.body)
            if moved.kind == TASK and card.kind == TASK:
                self.announce("tasks.status_changed", moved, f"{LABELS[before]} → {LABELS[after]}")
            elif moved.kind == TASK:
                self.announce("tasks.created", moved, LABELS[after])
        self._sync()
        return True

    def edit(self, card_id: str, title: str, body: str | None = None) -> bool:
        try:
            self.store.edit(card_id, title, body)
        except (OSError, ValueError, KeyError) as e:
            self.toast(str(e), title=TITLE, severity="error")
            return False
        self._sync()
        return True

    def color(self, card_id: str) -> bool:
        card = self.card(card_id)
        return card is not None and self.edit(card.id, tasklist.next_color(card.title))

    def flip(self, card_id: str) -> str:
        """A note becomes a task in To Do; a task becomes a note (in the first lane of notes).
        The lane it went to ("" when it did not move)."""
        card = self.card(card_id)
        if card is None:
            return ""
        lane = "todo" if card.kind == NOTE else self.note_lanes()[0]
        return lane if self.move(card.id, lane) else ""

    def send(self, card_id: str) -> bool:
        """The card goes down the roads as it is (`tasks.sent`). True when a road took it."""
        card = self.card(card_id)
        return card is not None and self.emit("tasks.sent", card_text(card), tasklist.plain(card.title),
                                              ref=self.ref(card))

    def remove(self, card_id: str) -> None:
        self.store.remove(card_id)
        self._sync()

    # -- the hut --------------------------------------------------------------------------------

    def status(self) -> str:
        return "ERROR" if self.error else ""

    def _note_line(self, seen: set[str]) -> str:
        notes = self.notes
        star = " *" if any(t.id not in seen for t in notes) else ""
        return f"🗒 {len(notes)} note{'s' if len(notes) != 1 else ''}{star}"

    def mini_status(self) -> list[str]:
        if self.error:
            return [f"⚠ {self.error[:40]}"]
        seen = self.seen()
        if self.mode == "notes":
            return [self._note_line(seen)] + [
                f"{ln.label} {sum(1 for t in self.cards if t.column == ln.id)}" for ln in self.visible_lanes()[:3]]
        lines = []
        for col in COLUMNS:
            rows = [t for t in self.cards if t.column == col]
            star = " *" if any(t.id not in seen for t in rows) else ""
            lines.append(f"{SHORT[col]} {len(rows)}{star}")
        doing = [t for t in self.cards if t.column == "in_progress"]
        if doing:
            lines.append(f"⚒ {tasklist.plain(doing[0].title)}")
        if self.mode == "board" and self.notes:
            lines.append(self._note_line(seen))
        return lines

    def hut_lines(self, widths: list[int]) -> list[str]:
        if self.error:
            return [f"⚠ {self.error[:40]}"]
        seen, lines = self.seen(), []
        if self.mode == "notes":
            lines.append(self._note_line(seen))
            for ln in self.visible_lanes()[:3]:
                rows = [t for t in self.cards if t.column == ln.id]
                lines.append(f"{ln.label[:10]}: {len(rows)}" + (" *" if any(t.id not in seen for t in rows) else ""))
            last = self.notes[-1:] if self.notes else []
            lines.append(f"✎ {tasklist.plain(last[0].title)}" if last else "no notes yet")
            return lines
        for col, tag in zip(COLUMNS, ("TODO", "PROG", "DONE")):
            rows = [t for t in self.cards if t.column == col]
            lines.append(f"[{tag}] {len(rows)} task{'s' if len(rows) != 1 else ''}"
                         + (" *" if any(t.id not in seen for t in rows) else ""))
        doing = [t for t in self.cards if t.column == "in_progress"]
        lines.append(f"⚒ {tasklist.plain(doing[0].title)}" if doing else "nothing in progress")
        if self.mode == "board" and self.notes:
            lines.append(self._note_line(seen))
        return lines


def card_text(card: tasklist.Task) -> str:
    title = tasklist.plain(card.title)
    return f"{title}\n\n{card.body}" if card.body else title
