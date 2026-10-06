"""🌾 Task Fields' work: the board — its cards and lanes, kept in `TASKS.md` or a tasks folder
(realm/tasklist.py) — and what each change sends. One board, three parts: the orks' tasks (the status
lanes, a kanban), the person's own to-dos (a checklist, `My to-dos`) and the notes (ideas, questions).

`refresh()` reads the board (the face calls it on a timer: a hand edit of the file is seen
there) and sends `tasks.created` / `tasks.status_changed` for a task, `notes.created` for a note.
The acts (add, move, edit, colour, flip, check, send, remove) change the file and send the same events
for what they changed; the person's to-dos send none (they are not the orks' work). The hut's * marks what is new
since the board was last looked at (`seen.json`).

What comes by road:

    a cart                 a new task in To Do (a note in `notes` mode)
    … routed to the person a new to-do of the person's own, when its route is one of `mine_routes` (a Clan Fire
                           that triages: `["human"]`)
    … about its own card   a cart whose `ref` names one of this board's cards (a Barracks' result on a return
                           road) moves that card: `*.assigned` → In Progress with who works it, `*.done` → Done
                           with the result, `*.failed` → back to To Do with why

`send_new`: every new task goes down the roads as it is (`tasks.sent`, its text and ref), as if `s` were
pressed — a Barracks takes it, and its results come back to the card.
"""
from __future__ import annotations

import json

from orkcraft.core.workers import Worker
from orkcraft.realm import tasklist
from orkcraft.realm.tasklist import COLUMNS, LABELS, MINE, NOTE, TASK

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

    @property
    def todos(self) -> list[tasklist.Task]:
        """The person's own to-dos (the checklist), open ones first."""
        mine = [c for c in self.cards if c.kind == MINE]
        return [c for c in mine if not c.checked] + [c for c in mine if c.checked]

    @property
    def shows_todos(self) -> bool:
        """The person's checklist stands on the board in `board` mode (the kanban and the wall keep theirs)."""
        return self.mode == "board"

    def todo_lane(self) -> tasklist.Lane:
        return next((ln for ln in self.lanes if ln.kind == MINE), tasklist.Lane(MINE, tasklist.MINE_LABEL))

    def card(self, card_id: str) -> tasklist.Task | None:
        return next((t for t in self.cards if t.id == card_id), None)

    def visible_lanes(self) -> list[tasklist.Lane]:
        lanes = [ln for ln in self.lanes if ln.kind != MINE] or [tasklist.Lane(c, LABELS[c]) for c in COLUMNS]
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

    def _sync(self, seen: bool = True) -> None:
        """Reload after its own change, without sending again what was just sent. `seen`: the person made
        the change (nothing on the board is new to them); a cart's card stays new till they look."""
        store = self.store
        self.lanes, self.cards = store.lanes(), store.load()
        self._last = list(self.cards)
        if seen:
            self.mark_seen()
        self.changed()

    def announce(self, event_id: str, card: tasklist.Task, detail: str) -> None:
        if event_id == "notes.created":
            self.emit(event_id, card_text(card), tasklist.plain(card.title), ref=self.ref(card))
        else:
            self.emit(event_id, card.id, f"{tasklist.plain(card.title)} · {detail}")
        if event_id == "tasks.created" and card.column == "todo" and self.config.get("send_new"):
            self.emit("tasks.sent", card_text(card), tasklist.plain(card.title), ref=self.ref(card))

    def ref(self, card: tasklist.Task) -> str:
        return f"{self.building_id}:{card.id}"

    # -- acts -----------------------------------------------------------------------------------

    def add(self, title: str, lane: str = "todo", body: str = "", seen: bool = True) -> tasklist.Task | None:
        try:
            card = self.store.add(title, lane, body)
        except (OSError, ValueError) as e:
            self.toast(str(e), title=TITLE, severity="error")
            return None
        self._sync(seen)                  # first: what the roads bring back about it finds it on the board
        if card.kind == TASK:
            self.announce("tasks.created", card, LABELS[card.column])
        elif card.kind == NOTE:
            self.announce("notes.created", card, card.column)
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
        """A cart is a new card — a task in To Do (a note in `notes` mode; a to-do of the person's when its
        route is one of `mine_routes`): its title, else its first line; the rest of what it carries is the
        card's text. A cart about one of its own cards (its `ref`) moves that card instead."""
        if self.update_own(payload, markdown):
            return
        lines = (markdown or str(payload.value or "")).splitlines()
        first_i = next((i for i, ln in enumerate(lines) if ln.strip(" #*-")), None)
        first = " ".join(lines[first_i].strip(" #*-").split()) if first_i is not None else ""
        name = " ".join((payload.title or title or first).split())[:120]
        if not name:
            return
        rest = lines[first_i + 1:] if first_i is not None and first == name else lines
        lane = self.visible_lanes()[0].id if self.mode == "notes" else "todo"
        if payload.route and payload.route in [str(r).strip().lower() for r in self.config.get("mine_routes") or []]:
            lane = MINE
        self.add(name, lane, "\n".join(rest).strip()[:2000], seen=False)

    def update_own(self, payload, markdown: str = "") -> bool:
        """A cart about one of this board's cards (its `ref` is `<this building>:<card id>`): the work on it
        started, ended or failed elsewhere — the card moves and says so. False when the cart names none."""
        prefix = f"{self.building_id}:"
        ref = str(getattr(payload, "ref", "") or "")
        what = str(payload.mode or "").rsplit(".", 1)[-1]
        if not ref.startswith(prefix) or what not in ("assigned", "done", "failed"):
            return False
        card = self.card(ref[len(prefix):])
        if card is None:
            return True                       # its card is gone from the board: nothing to move, nothing to add
        text = (markdown or str(payload.value or "")).strip()
        if what == "assigned":
            who = text.split(" ← ", 1)[0].strip()
            body, lane = (f"⚒ {who} is on it" if who else card.body), "in_progress"
        elif what == "done":
            body, lane = result_of(text), "done"
        else:
            body, lane = f"✗ {result_of(text)}", "todo"
        if card.kind != TASK:
            return True                       # a card that is no task any more stays where the person put it
        self.edit(card.id, card.title, body[:2000])
        if card.column != lane:
            self.move(card.id, lane)
        return True

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

    def check(self, card_id: str, done: bool | None = None) -> bool:
        """Tick one of the person's to-dos off (or back on)."""
        try:
            self.store.check(card_id, done)
        except (OSError, ValueError, KeyError) as e:
            self.toast(str(e), title=TITLE, severity="error")
            return False
        self._sync()
        return True

    def to_mine(self, card_id: str) -> bool:
        """A note (an idea) or a task becomes a to-do of the person's own."""
        card = self.card(card_id)
        return card is not None and card.kind != MINE and self.move(card.id, MINE)

    def color(self, card_id: str) -> bool:
        card = self.card(card_id)
        return card is not None and self.edit(card.id, tasklist.next_color(card.title))

    def flip(self, card_id: str) -> str:
        """A note or a to-do of the person's becomes a task for the orks in To Do; a task becomes a note
        (in the first lane of notes). The lane it went to ("" when it did not move)."""
        card = self.card(card_id)
        if card is None:
            return ""
        lane = "todo" if card.kind != TASK else self.note_lanes()[0]
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
        if self.mode == "board" and self.todos:
            lines.append(self._todo_line())
        if self.mode == "board" and self.notes:
            lines.append(self._note_line(seen))
        return lines

    def _todo_line(self) -> str:
        todos = self.todos
        return f"☐ My chores {sum(1 for t in todos if not t.checked)}/{len(todos)}"

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
        if self.mode == "board":
            return self._board_lines(seen)
        for col, tag in zip(COLUMNS, ("TODO", "PROG", "DONE")):
            rows = [t for t in self.cards if t.column == col]
            lines.append(f"[{tag}] {len(rows)} task{'s' if len(rows) != 1 else ''}"
                         + (" *" if any(t.id not in seen for t in rows) else ""))
        doing = [t for t in self.cards if t.column == "in_progress"]
        lines.append(f"⚒ {tasklist.plain(doing[0].title)}" if doing else "nothing in progress")
        return lines

    def _board_lines(self, seen: set[str]) -> list[str]:
        """The board's three parts in nine rows: the orks' lanes (counts, what is in work, what is
        next), the person's open to-dos, the latest notes."""
        counts = []
        for col, tag in zip(COLUMNS, ("TODO", "PROG", "DONE")):
            rows = [t for t in self.cards if t.column == col]
            counts.append(f"{tag} {len(rows)}" + ("*" if any(t.id not in seen for t in rows) else ""))
        doing = [t for t in self.cards if t.column == "in_progress"][:1]
        nxt = [t for t in self.cards if t.column == "todo"][:2 - len(doing)]
        lines = [" ".join(counts)]
        lines += [f"⚒ {tasklist.plain(t.title)}" for t in doing] + [f"▸ {tasklist.plain(t.title)}" for t in nxt]
        lines += [""] * (3 - len(lines))
        todos = self.todos
        open_ = [t for t in todos if not t.checked]
        lines.append(f"My chores {len(open_)}/{len(todos)}" if todos else "My chores: none yet")
        lines += [f"☐ {tasklist.plain(t.title)}" for t in open_[:2]]
        lines += [""] * (6 - len(lines))
        notes = self.notes
        star = "*" if any(t.id not in seen for t in notes) else ""
        lines.append(f"Scribbles {len(notes)}{star}" if notes else "Scribbles: none yet")
        lines += [f"✎ {tasklist.plain(t.title)}" for t in notes[::-1][:2]]
        return lines


def result_of(text: str) -> str:
    """What a result says, without its first line when that only names the task and who did it
    (`**Title** — Grub (claude)`)."""
    lines = text.strip().splitlines()
    if lines and lines[0].startswith("**") and " — " in lines[0]:
        lines = lines[1:]
    return "\n".join(lines).strip() or text.strip()


def card_text(card: tasklist.Task) -> str:
    title = tasklist.plain(card.title)
    return f"{title}\n\n{card.body}" if card.body else title
