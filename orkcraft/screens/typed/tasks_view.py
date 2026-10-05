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

The board's work — reading it, the acts, the events — is the building's worker's
(core/workers/fields.py). The view draws the lanes and holds the keys and the dialogs.
"""
from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import Label, OptionList
from textual.widgets.option_list import Option

from orkcraft.core.workers.fields import TITLE, FieldsWorker
from orkcraft.realm import tasklist
from orkcraft.realm.tasklist import NOTE, TASK
from orkcraft.screens.dialogs import Confirm, TextBlock, TextPrompt
from orkcraft.screens.typed.base import TypedView

REFRESH_S = 10.0
NOTE_LINES = 2                       # lines of a note's text shown on the board
COLOR_STYLE = {"🟨": "on #3b3416", "🟩": "on #18301c", "🟦": "on #142a3d", "🟥": "on #3d1a1a", "🟪": "on #2e1d3d"}


class TasksView(TypedView):
    TYPE = "fields"
    UI_PANES = {"board": "#tasks-board"}
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
        self._shown: tuple[str, ...] = ()

    @property
    def worker(self) -> FieldsWorker:
        return super().worker

    # -- the worker's board, as the view's own (tests and other views read these) -------------------

    @property
    def cards(self) -> list[tasklist.Task]:
        return self.worker.cards

    @property
    def lanes(self) -> list[tasklist.Lane]:
        return self.worker.lanes

    @property
    def error(self) -> str:
        return self.worker.error

    @property
    def store(self) -> tasklist.TaskList:
        return self.worker.store

    @property
    def mode(self) -> str:
        return self.worker.mode

    @property
    def tasks(self) -> list[tasklist.Task]:
        return self.worker.tasks

    @property
    def notes(self) -> list[tasklist.Task]:
        return self.worker.notes

    def visible_lanes(self) -> list[tasklist.Lane]:
        return self.worker.visible_lanes()

    def card(self, card_id: str) -> tasklist.Task | None:
        return self.worker.card(card_id)

    def add(self, title: str, lane: str = "todo", body: str = "") -> tasklist.Task | None:
        return self.worker.add(title, lane, body)

    def receive(self, payload, title: str, markdown: str) -> None:
        self.worker.receive(payload, title, markdown)

    def mark_seen(self) -> None:
        self.worker.mark_seen()

    # -- the view -------------------------------------------------------------------------------------

    def compose_body(self) -> ComposeResult:
        yield Horizontal(classes="typed-row", id="tasks-board")

    def on_mount(self) -> None:
        self.refresh_data()
        self.set_interval(REFRESH_S, self.refresh_data)

    def refresh_data(self) -> None:
        """A look at the file (a hand edit is seen here); the worker redraws the board."""
        self.worker.refresh()

    def redraw(self) -> None:
        self._render_list()

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

    def on_show(self) -> None:
        if self.cards:
            self.mark_seen()

    def _render_list(self) -> None:
        if self._build_lanes():
            self.call_after_refresh(self._fill_lanes)
            return
        self._fill_lanes()

    def _fill_lanes(self) -> None:
        seen = self.worker.seen()
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

    # -- actions ------------------------------------------------------------------------------------

    def move(self, task_id: str, column: str) -> None:
        if self.worker.move(task_id, column):
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

    def _selected_card(self) -> tasklist.Task | None:
        sel = self.selected()
        return self.card(sel[1]) if sel else None

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
        card = self._selected_card()
        if card is None:
            return

        def done(text: str | None) -> None:
            lines = (text or "").strip().splitlines()
            if lines:
                self.worker.edit(card.id, lines[0], "\n".join(lines[1:]))

        self.app.push_screen(TextBlock(f"🌾 {'Task' if card.kind == TASK else 'Note'} · {tasklist.plain(card.title)}",
                                       f"{card.title}\n{card.body}".rstrip(),
                                       "the first line is the title, the rest the card's text · ctrl+s keeps it"), done)

    def action_rename(self) -> None:
        self.action_open()

    def action_color(self) -> None:
        card = self._selected_card()
        if card is not None and self.worker.color(card.id):
            self._focus_card(card.column, card.id)

    def action_flip(self) -> None:
        """A note becomes a task in To Do; a task becomes a note (in the first lane of notes)."""
        card = self._selected_card()
        lane = self.worker.flip(card.id) if card is not None else ""
        if lane:
            self._focus_card(lane, card.id)

    def action_send(self) -> None:
        """The card goes down the building's roads as it is (`tasks.sent`): a Barracks takes it as a task,
        a Clan Fire reviews it, a Scroll Dump files it."""
        card = self._selected_card()
        if card is None:
            return
        sent = self.worker.send(card.id)
        self.app.notify(f"{tasklist.plain(card.title)[:60]}: " + ("sent down the roads" if sent else
                                                                  "no road takes tasks.sent from here"),
                        title=TITLE, severity="information" if sent else "warning")

    def action_delete(self) -> None:
        card = self._selected_card()
        if card is None:
            return

        def done(yes: bool | None) -> None:
            if yes:
                self.worker.remove(card.id)

        self.app.push_screen(Confirm(f"🌾 Delete “{tasklist.plain(card.title)[:60]}”?",
                                     "It goes from the file too (git keeps it)."), done)

    # -- the hut ----------------------------------------------------------------------------------

    def mini_status(self) -> list[str]:
        return self.worker.mini_status()

    def hut_lines(self, widths: list[int]) -> list[str]:
        return self.worker.hut_lines(widths)

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
