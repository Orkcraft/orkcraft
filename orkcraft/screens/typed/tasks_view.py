"""🌾 Task Fields: a board of cards — tasks in To Do / In Progress / Done, sticky notes in lanes of
their own — kept in `TASKS.md` or a tasks folder (realm/tasklist.py).

`mode` picks what the board shows: `board` (default) every lane, `tasks` the three status lanes
(a kanban), `notes` the lanes of notes (a wall of stickers). `lanes` names lanes of notes that are
always there (`["Ideas", "Questions"]`); any other `##` section of the file is one too.

Keys: `n` a new card in the focused lane · `<` `>` move it · `e` / Enter open it (its first line is
the title, the rest its text) · `c` its colour · `t` a note ⇄ a task · `s` send it down the roads ·
`d` delete it · `N` a new lane of notes. A cart that comes by road becomes a card: a task in To Do
(a note in `notes` mode), its title, else its first line, the rest its text.

Each change — here or in the file by hand (looked at every 10 s) — sends `tasks.created` or
`tasks.status_changed` for a task, `notes.created` for a note; `s` sends `tasks.sent`. The hut
counts the lanes; * marks what is new since the building was last opened.
"""
from __future__ import annotations

import json

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import Label, OptionList
from textual.widgets.option_list import Option

from orkcraft.realm import tasklist
from orkcraft.realm.tasklist import COLUMNS, LABELS, NOTE, TASK
from orkcraft.screens.dialogs import Confirm, TextBlock, TextPrompt
from orkcraft.screens.typed.base import TypedView

REFRESH_S = 10.0
SHORT = {"todo": "To Do", "in_progress": "Doing", "done": "Done"}
MODES = ("board", "tasks", "notes")
NOTE_LINES = 2                       # lines of a note's text shown on the board
COLOR_STYLE = {"🟨": "on #3b3416", "🟩": "on #18301c", "🟦": "on #142a3d", "🟥": "on #3d1a1a", "🟪": "on #2e1d3d"}


class TasksView(TypedView):
    TYPE = "fields"
    BINDINGS = [Binding("n", "new", "New card"), Binding("less_than_sign", "move(-1)", "◀ Move"),
                Binding("greater_than_sign", "move(1)", "Move ▶"), Binding("e", "open", "Open"),
                Binding("enter", "open", "Open", show=False), Binding("c", "color", "Colour"),
                Binding("t", "flip", "Note ⇄ task"), Binding("s", "send", "Send", show=False),
                Binding("d", "delete", "Delete", show=False), Binding("N", "new_lane", "New lane", show=False)]
    DEFAULT_CSS = """
    TasksView .tasks-col { width: 1fr; height: 1fr; border: round $surface-lighten-1; }
    TasksView .tasks-col.notes-col { border: round $warning-darken-2; }
    TasksView .tasks-col Label { padding: 0 1; text-style: bold; color: $accent; }
    TasksView .tasks-col.notes-col Label { color: $warning; }
    TasksView .tasks-col OptionList { height: 1fr; border: none; }
    """

    def __init__(self, *a, **kw) -> None:
        super().__init__(*a, **kw)
        self.cards: list[tasklist.Task] = []
        self.lanes: list[tasklist.Lane] = []
        self.error = ""
        self._last: list[tasklist.Task] | None = None
        self._shown: tuple[str, ...] = ()

    # -- what it is -----------------------------------------------------------------------------------

    @property
    def store(self) -> tasklist.TaskList:
        return tasklist.TaskList(self._get_repo_root(), str(self.config.get("path", "")))

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

    # -- the view -------------------------------------------------------------------------------------

    def compose_body(self) -> ComposeResult:
        yield Horizontal(classes="typed-row", id="tasks-board")

    def on_mount(self) -> None:
        self.refresh_data()
        self.set_interval(REFRESH_S, self.refresh_data)

    def _build_lanes(self) -> bool:
        """One column per visible lane; rebuilt only when the lanes change (True: just rebuilt — the
        new lists are filled once they are mounted)."""
        lanes = self.visible_lanes()
        ids = tuple(ln.id for ln in lanes)
        if ids == self._shown:
            for ln in lanes:
                try:
                    self.query_one(f"#tasks-label-{ln.id}", Label).update(ln.label)
                except Exception:
                    pass
            return False
        try:
            board = self.query_one("#tasks-board", Horizontal)
        except Exception:
            return False
        board.remove_children()
        for ln in lanes:
            col = Vertical(Label(ln.label, id=f"tasks-label-{ln.id}"), OptionList(id=f"tasks-{ln.id}"),
                           classes="tasks-col" + (" notes-col" if ln.kind == NOTE else ""))
            board.mount(col)
        self._shown = ids
        return True

    # -- seen (the hut's *) ---------------------------------------------------------------------------

    def _seen(self) -> set[str]:
        try:
            return set(json.loads((self.state_dir / "seen.json").read_text(encoding="utf-8")))
        except (OSError, ValueError, TypeError):
            return set()

    def mark_seen(self) -> None:
        self.state_dir.mkdir(parents=True, exist_ok=True)
        (self.state_dir / "seen.json").write_text(json.dumps(sorted(t.id for t in self.cards)), encoding="utf-8")

    def on_show(self) -> None:
        if self.cards:
            self.mark_seen()

    # -- data ---------------------------------------------------------------------------------------

    def refresh_data(self) -> None:
        try:
            store = self.store
            self.lanes, self.cards, self.error = store.lanes(), store.load(), ""
        except (OSError, ValueError) as e:
            self.lanes, self.cards, self.error = [], [], str(e)[:200]
        for event_id, card, detail in tasklist.changes(self._last, self.cards):
            self._announce(event_id, card, detail)
        if self._last is None and not (self.state_dir / "seen.json").exists():
            self.mark_seen()                     # the first look: nothing is new yet
        self._last = list(self.cards)
        self._render_list()

    def _announce(self, event_id: str, card: tasklist.Task, detail: str) -> None:
        if event_id == "notes.created":
            self.emit(event_id, self._card_text(card), tasklist.plain(card.title), ref=self._ref(card))
        else:
            self.emit(event_id, card.id, f"{tasklist.plain(card.title)} · {detail}")

    def _ref(self, card: tasklist.Task) -> str:
        return f"{self.building_id}:{card.id}"

    @staticmethod
    def _card_text(card: tasklist.Task) -> str:
        title = tasklist.plain(card.title)
        return f"{title}\n\n{card.body}" if card.body else title

    def _render_list(self) -> None:
        if self._build_lanes():
            self.call_after_refresh(self._fill_lanes)
            return
        self._fill_lanes()

    def _fill_lanes(self) -> None:
        seen = self._seen()
        for ln in self.visible_lanes():
            try:
                lst, label = self.query_one(f"#tasks-{ln.id}", OptionList), self.query_one(f"#tasks-label-{ln.id}", Label)
            except Exception:
                continue
            keep = self._highlighted_id(lst)
            rows = [t for t in self.cards if t.column == ln.id]
            label.update(f"{ln.label} · {len(rows)}")
            lst.clear_options()
            for t in rows:
                lst.add_option(Option(self._card_row(t, t.id not in seen, ln.id == "done"), id=t.id))
            ids = [t.id for t in rows]
            if keep in ids:
                lst.highlighted = ids.index(keep)

    @staticmethod
    def _card_row(t: tasklist.Task, new: bool, done: bool) -> Text:
        row = Text(overflow="ellipsis")
        bg = COLOR_STYLE.get(t.color, "")
        if new:
            row.append("* ", style="bold yellow")
        if t.color:
            row.append(f"{t.color} ")
        row.append(tasklist.plain(t.title), style=("dim strike " if done else "bold " if t.kind == NOTE else "") + bg)
        if t.body and t.kind == TASK:
            row.append(" ✎", style="dim")
        if t.kind == NOTE and t.body:
            for line in [ln for ln in t.body.splitlines() if ln.strip()][:NOTE_LINES]:
                row.append("\n" + line.strip()[:60], style="dim " + bg)
        return row

    @staticmethod
    def _highlighted_id(lst: OptionList) -> str | None:
        if lst.highlighted is None or lst.highlighted >= lst.option_count:
            return None
        return lst.get_option_at_index(lst.highlighted).id

    def _lists(self) -> list[tuple[str, OptionList]]:
        out = []
        for ln in self.visible_lanes():
            try:
                out.append((ln.id, self.query_one(f"#tasks-{ln.id}", OptionList)))
            except Exception:
                pass
        return out

    def focused_lane(self) -> str:
        lists = self._lists()
        return next((c for c, lst in lists if lst.has_focus), lists[0][0] if lists else "todo")

    def selected(self) -> tuple[str, str] | None:
        """(lane, card id) of the highlighted card in the focused lane (else the first with one)."""
        lists = self._lists()
        focused = [(c, lst) for c, lst in lists if lst.has_focus]
        for c, lst in focused + lists:
            tid = self._highlighted_id(lst)
            if tid:
                return c, tid
        return None

    def card(self, card_id: str) -> tasklist.Task | None:
        return next((t for t in self.cards if t.id == card_id), None)

    # -- actions ------------------------------------------------------------------------------------

    def add(self, title: str, lane: str = "todo", body: str = "") -> tasklist.Task | None:
        try:
            card = self.store.add(title, lane, body)
        except (OSError, ValueError) as e:
            self.app.notify(str(e), title="🌾 Task Fields", severity="error")
            return None
        if card.kind == TASK:
            self._announce("tasks.created", card, LABELS[card.column])
        else:
            self._announce("notes.created", card, card.column)
        self._sync_after_own_change()
        return card

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

    def move(self, task_id: str, column: str) -> None:
        card = self.card(task_id)
        try:
            before, after = self.store.move(task_id, column)
        except (OSError, ValueError, KeyError) as e:
            self.app.notify(str(e), title="🌾 Task Fields", severity="error")
            return
        if before != after and card is not None:
            moved = tasklist.Task(card.id, card.title, after, card.body)
            if moved.kind == TASK and card.kind == TASK:
                self._announce("tasks.status_changed", moved, f"{LABELS[before]} → {LABELS[after]}")
            elif moved.kind == TASK:
                self._announce("tasks.created", moved, LABELS[after])
        self._sync_after_own_change()
        self._focus_card(column, task_id)

    def _focus_card(self, lane: str, card_id: str) -> None:
        try:
            lst = self.query_one(f"#tasks-{lane}", OptionList)
        except Exception:
            return
        ids = [t.id for t in self.cards if t.column == lane]
        if card_id in ids:
            lst.focus()
            lst.highlighted = ids.index(card_id)

    def _sync_after_own_change(self) -> None:
        """Reload without re-sending what was just sent."""
        store = self.store
        self.lanes, self.cards = store.lanes(), store.load()
        self._last = list(self.cards)
        self.mark_seen()
        self._render_list()

    def action_new(self) -> None:
        lane = self.focused_lane()
        what = "task" if tasklist.kind_of(lane) == TASK else "note"
        label = next((ln.label for ln in self.visible_lanes() if ln.id == lane), lane)
        self.app.push_screen(TextPrompt(f"🌾 New {what} · {label}",
                                        placeholder="what needs doing" if what == "task" else "a note"),
                             lambda title: self.add(title, lane) if title else None)

    def action_new_lane(self) -> None:
        def done(name: str | None) -> None:
            name = " ".join((name or "").split())
            if not name:
                return
            lid = tasklist.column_of(name) or tasklist.slug(name)
            self.app.push_screen(TextPrompt(f"🌾 The first note in {name}", placeholder="a note"),
                                 lambda title: self.add(title, lid) if title else None)
        self.app.push_screen(TextPrompt("🌾 New lane of notes", placeholder="Ideas, Questions, For the sync…"), done)

    def action_move(self, step: int) -> None:
        sel = self.selected()
        if sel is None:
            return
        lane, tid = sel
        ids = [ln.id for ln in self.visible_lanes()]
        i = ids.index(lane) + int(step) if lane in ids else -1
        if 0 <= i < len(ids):
            self.move(tid, ids[i])

    def action_open(self) -> None:
        """The card in full: its first line is the title, the rest its text."""
        sel = self.selected()
        card = self.card(sel[1]) if sel else None
        if card is None:
            return

        def done(text: str | None) -> None:
            if text is None:
                return
            lines = text.strip().splitlines()
            if not lines:
                return
            try:
                self.store.edit(card.id, lines[0], "\n".join(lines[1:]))
            except (OSError, ValueError, KeyError) as e:
                self.app.notify(str(e), title="🌾 Task Fields", severity="error")
                return
            self._sync_after_own_change()

        self.app.push_screen(TextBlock(f"🌾 {'Task' if card.kind == TASK else 'Note'} · {tasklist.plain(card.title)}",
                                       f"{card.title}\n{card.body}".rstrip(),
                                       "the first line is the title, the rest the card's text · ctrl+s keeps it"), done)

    def action_rename(self) -> None:
        self.action_open()

    def action_color(self) -> None:
        sel = self.selected()
        card = self.card(sel[1]) if sel else None
        if card is None:
            return
        self.store.edit(card.id, tasklist.next_color(card.title))
        self._sync_after_own_change()
        self._focus_card(card.column, card.id)

    def action_flip(self) -> None:
        """A note becomes a task in To Do; a task becomes a note (in the first lane of notes)."""
        sel = self.selected()
        card = self.card(sel[1]) if sel else None
        if card is None:
            return
        if card.kind == NOTE:
            self.move(card.id, "todo")
            return
        notes = [ln.id for ln in self.lanes if ln.kind == NOTE] or \
                [tasklist.slug(str(n)) for n in self.config.get("lanes") or []] or [tasklist.NOTES]
        self.move(card.id, notes[0])

    def action_send(self) -> None:
        """The card goes down the building's roads as it is (`tasks.sent`): a Barracks takes it as a task,
        a Clan Fire reviews it, a Scroll Dump files it."""
        sel = self.selected()
        card = self.card(sel[1]) if sel else None
        if card is None:
            return
        sent = self.emit("tasks.sent", self._card_text(card), tasklist.plain(card.title), ref=self._ref(card))
        self.app.notify(f"{tasklist.plain(card.title)[:60]}: " + ("sent down the roads" if sent else
                                                                  "no road takes tasks.sent from here"),
                        title="🌾 Task Fields", severity="information" if sent else "warning")

    def action_delete(self) -> None:
        sel = self.selected()
        card = self.card(sel[1]) if sel else None
        if card is None:
            return

        def done(yes: bool | None) -> None:
            if yes:
                self.store.remove(card.id)
                self._sync_after_own_change()

        self.app.push_screen(Confirm(f"🌾 Delete “{tasklist.plain(card.title)[:60]}”?",
                                     "It goes from the file too (git keeps it)."), done)

    # -- the hut ----------------------------------------------------------------------------------

    def _note_line(self, seen: set[str]) -> str:
        notes = self.notes
        star = " *" if any(t.id not in seen for t in notes) else ""
        return f"🗒 {len(notes)} note{'s' if len(notes) != 1 else ''}{star}"

    def mini_status(self) -> list[str]:
        if self.error:
            return [f"⚠ {self.error[:40]}"]
        seen = self._seen()
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
        seen, lines = self._seen(), []
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

    def quick_action(self, action_id: str) -> bool:
        if action_id == "tasks.new":
            self.action_new()
            return True
        if action_id == "notes.new":
            lanes = [ln.id for ln in self.visible_lanes() if ln.kind == NOTE] or [tasklist.NOTES]
            self.app.push_screen(TextPrompt("🌾 New note", placeholder="a note"),
                                 lambda title: self.add(title, lanes[0]) if title else None)
            return True
        return False
