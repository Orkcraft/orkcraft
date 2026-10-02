"""📋 Tasks: to do, in progress, done — kept in `TASKS.md` or a tasks folder.

Three columns; `n` adds a task, `<` / `>` move the highlighted one, `e` renames it. Each change —
here or in the file by hand (looked at every 10 s) — sends `tasks.created` or
`tasks.status_changed` with the task's id. The hut counts the columns; * marks what is new since
the building was last opened.
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
from orkcraft.realm.tasklist import COLUMNS, LABELS
from orkcraft.screens.dialogs import TextPrompt
from orkcraft.screens.typed.base import TypedView

REFRESH_S = 10.0
SHORT = {"todo": "To Do", "in_progress": "Doing", "done": "Done"}


class TasksView(TypedView):
    TYPE = "fields"
    BINDINGS = [Binding("n", "new", "New task"), Binding("less_than_sign", "move(-1)", "◀ Move"),
                Binding("greater_than_sign", "move(1)", "Move ▶"), Binding("e", "rename", "Rename")]
    DEFAULT_CSS = """
    TasksView .tasks-col { width: 1fr; height: 1fr; border: round $surface-lighten-1; }
    TasksView .tasks-col Label { padding: 0 1; text-style: bold; color: $accent; }
    TasksView .tasks-col OptionList { height: 1fr; border: none; }
    """

    def __init__(self, *a, **kw) -> None:
        super().__init__(*a, **kw)
        self.tasks: list[tasklist.Task] = []
        self.error = ""
        self._last: list[tasklist.Task] | None = None

    @property
    def store(self) -> tasklist.TaskList:
        return tasklist.TaskList(self._get_repo_root(), str(self.config.get("path", "")))

    def compose_body(self) -> ComposeResult:
        with Horizontal(classes="typed-row"):
            for col in COLUMNS:
                with Vertical(classes="tasks-col"):
                    yield Label(LABELS[col], id=f"tasks-label-{col}")
                    yield OptionList(id=f"tasks-{col}")

    def on_mount(self) -> None:
        self.refresh_data()
        self.set_interval(REFRESH_S, self.refresh_data)

    # -- seen (the hut's *) ---------------------------------------------------------------------------

    def _seen(self) -> set[str]:
        try:
            return set(json.loads((self.state_dir / "seen.json").read_text(encoding="utf-8")))
        except (OSError, ValueError, TypeError):
            return set()

    def mark_seen(self) -> None:
        self.state_dir.mkdir(parents=True, exist_ok=True)
        (self.state_dir / "seen.json").write_text(json.dumps(sorted(t.id for t in self.tasks)), encoding="utf-8")

    def on_show(self) -> None:
        if self.tasks:
            self.mark_seen()

    # -- data ---------------------------------------------------------------------------------------

    def refresh_data(self) -> None:
        try:
            self.tasks, self.error = self.store.load(), ""
        except (OSError, ValueError) as e:
            self.tasks, self.error = [], str(e)[:200]
        for event_id, task, detail in tasklist.changes(self._last, self.tasks):
            self.emit(event_id, task.id, f"{task.title} · {detail}")
        if self._last is None and not (self.state_dir / "seen.json").exists():
            self.mark_seen()                     # the first look: nothing is new yet
        self._last = list(self.tasks)
        self._render_list()

    def _render_list(self) -> None:
        seen = self._seen()
        for col in COLUMNS:
            try:
                lst, label = self.query_one(f"#tasks-{col}", OptionList), self.query_one(f"#tasks-label-{col}", Label)
            except Exception:
                return
            keep = self._highlighted_id(lst)
            rows = [t for t in self.tasks if t.column == col]
            label.update(f"{LABELS[col]} · {len(rows)}")
            lst.clear_options()
            for t in rows:
                row = Text(no_wrap=True, overflow="ellipsis")
                if t.id not in seen:
                    row.append("* ", style="bold yellow")
                row.append(t.title, style="dim strike" if col == "done" else "")
                lst.add_option(Option(row, id=t.id))
            ids = [t.id for t in rows]
            if keep in ids:
                lst.highlighted = ids.index(keep)

    @staticmethod
    def _highlighted_id(lst: OptionList) -> str | None:
        if lst.highlighted is None or lst.highlighted >= lst.option_count:
            return None
        return lst.get_option_at_index(lst.highlighted).id

    def selected(self) -> tuple[str, str] | None:
        """(column, task id) of the highlighted task in the focused column (else the first with one)."""
        lists = [(c, self.query_one(f"#tasks-{c}", OptionList)) for c in COLUMNS]
        focused = [(c, lst) for c, lst in lists if lst.has_focus]
        for c, lst in focused + lists:
            tid = self._highlighted_id(lst)
            if tid:
                return c, tid
        return None

    # -- actions ------------------------------------------------------------------------------------

    def add(self, title: str) -> None:
        try:
            task = self.store.add(title)
        except (OSError, ValueError) as e:
            self.app.notify(str(e), title="📋 Tasks", severity="error")
            return
        self.emit("tasks.created", task.id, f"{task.title} · {LABELS['todo']}")
        self._sync_after_own_change()

    def move(self, task_id: str, column: str) -> None:
        before, after = self.store.move(task_id, column)
        if before != after:
            title = next((t.title for t in self.tasks if t.id == task_id), task_id)
            self.emit("tasks.status_changed", task_id, f"{title} · {LABELS[before]} → {LABELS[after]}")
        self._sync_after_own_change()
        lst = self.query_one(f"#tasks-{column}", OptionList)
        ids = [t.id for t in self.tasks if t.column == column]
        if task_id in ids:
            lst.focus()
            lst.highlighted = ids.index(task_id)

    def _sync_after_own_change(self) -> None:
        """Reload without re-sending what was just sent."""
        self.tasks = self.store.load()
        self._last = list(self.tasks)
        self.mark_seen()
        self._render_list()

    def action_new(self) -> None:
        self.app.push_screen(TextPrompt("📋 New task", placeholder="what needs doing"),
                             lambda title: self.add(title) if title else None)

    def action_move(self, step: int) -> None:
        sel = self.selected()
        if sel is None:
            return
        col, tid = sel
        i = COLUMNS.index(col) + int(step)
        if 0 <= i < len(COLUMNS):
            self.move(tid, COLUMNS[i])

    def action_rename(self) -> None:
        sel = self.selected()
        if sel is None:
            return
        _, tid = sel
        title = next((t.title for t in self.tasks if t.id == tid), "")

        def done(new: str | None) -> None:
            if new:
                self.store.rename(tid, new)
                self._sync_after_own_change()

        self.app.push_screen(TextPrompt("📋 Rename task", value=title), done)

    # -- the hut ----------------------------------------------------------------------------------

    def mini_status(self) -> list[str]:
        if self.error:
            return [f"⚠ {self.error[:40]}"]
        seen = self._seen()
        lines = []
        for col in COLUMNS:
            rows = [t for t in self.tasks if t.column == col]
            star = " *" if any(t.id not in seen for t in rows) else ""
            lines.append(f"{SHORT[col]} {len(rows)}{star}")
        doing = [t for t in self.tasks if t.column == "in_progress"]
        if doing:
            lines.append(f"⚒ {doing[0].title}")
        return lines

    def quick_action(self, action_id: str) -> bool:
        if action_id == "tasks.new":
            self.action_new()
            return True
        return False
