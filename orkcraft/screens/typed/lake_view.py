"""🌊 The Lake of Insight: the inspector.

A cart's file, diff, Markdown, URL or branch name is shown the way it reads best (realm/lake.py):
a diff side by side, Markdown rendered, a page as text. The setting `url` (a local dev server)
is shown when nothing else has arrived; ↗ opens what is shown in the browser. Each view sends
`lake.viewed`.

A text file on disk (Markdown, code, a patch) is edited in place: `e` (or ✎) opens it in an editor,
which saves by itself every `autosave` seconds while there are changes and whenever it loses focus;
`ctrl+s` saves at once, `Esc` saves and goes back to the view. A file changed on disk meanwhile is
never overwritten by an autosave: the Lake says so, and `ctrl+s` writes your text over it. Leaving
the editor after a save sends `lake.saved` with the file.

An edit of a file an ork wrote is feedback for that ork (filling it in says nothing). The work — what
is shown, the file open, saving it, judging the edit — is the building's worker's
(core/workers/lake.py). The view draws it and holds the editor, its autosave timer and the keys.
"""
from __future__ import annotations

import webbrowser
from pathlib import Path

from rich.table import Table
from rich.text import Text
from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.timer import Timer
from textual.widgets import Markdown, Static, TextArea

from orkcraft.core.workers.lake import LakeWorker
from orkcraft.realm import lake
from orkcraft.screens.typed.base import TypedView

STYLE = {"-": ("red", ""), "+": ("", "green"), "~": ("red", "green"), "@": ("bold cyan", "bold cyan"), " ": ("", "")}
DIFF_ROWS = 2000


class LakeView(TypedView):
    TYPE = "lake"
    UI_PANES = {"head": "#lake-head", "view": "#lake-scroll", "editor": "#lake-edit"}
    opener = None                  # tests catch the browser here
    BINDINGS = [Binding("e", "edit", "Edit"),
                Binding("ctrl+s", "save(True)", "Save", show=False),
                Binding("escape", "leave_edit", "Done", show=False)]
    DEFAULT_CSS = """
    LakeView #lake-edit { height: 1fr; display: none; }
    """

    def __init__(self, *a, **kw) -> None:
        super().__init__(*a, **kw)
        self._autosave: Timer | None = None
        self._open_draft: lake.Draft | None = None     # the draft the editor shows

    @property
    def worker(self) -> LakeWorker:
        return super().worker

    def compose_body(self) -> ComposeResult:
        yield Static("", id="lake-head", classes="typed-head")
        with VerticalScroll(id="lake-scroll"):
            yield Static("", id="lake-plain")
            yield Markdown("", id="lake-md")
        yield TextArea("", id="lake-edit", soft_wrap=True)

    def on_mount(self) -> None:
        self.worker.reader = self._editor_text
        self.redraw()

    # -- the worker's state, as the view's own (tests and other views read these) ------------------

    @property
    def view(self) -> lake.View | None:
        return self.worker.view

    @property
    def draft(self) -> lake.Draft | None:
        return self.worker.draft

    @property
    def edit_note(self) -> str:
        return self.worker.edit_note

    @property
    def conflict(self) -> bool:
        return self.worker.conflict

    @property
    def saved_any(self) -> bool:
        return self.worker.saved_any

    @property
    def editing(self) -> bool:
        return self.worker.editing

    @property
    def dirty(self) -> bool:
        return self.worker.dirty

    @property
    def autosave_s(self) -> int:
        return self.worker.autosave_s

    def receive(self, payload, title: str, markdown: str) -> None:
        self.worker.receive(payload, title, markdown)

    def show_value(self, kind: str, value: str, title: str = "") -> None:
        self.worker.show_value(kind, value, title)

    def show(self, v: lake.View) -> None:
        self.worker.show(v)

    # -- editing a file -----------------------------------------------------------------------------

    def check_action(self, action: str, parameters: tuple) -> bool | None:
        if action == "edit":
            return not self.editing                  # in the editor `e` is a letter
        if action in ("save", "leave_edit"):
            return self.editing                      # else Esc goes on to the town
        return True

    def _editor(self) -> TextArea | None:
        try:
            return self.query_one("#lake-edit", TextArea)
        except Exception:
            return None

    def _editor_text(self) -> str:
        editor = self._editor()
        return editor.text if editor is not None else self.worker.text

    def action_edit(self) -> None:
        if self.worker.open():
            self.redraw()

    def _autosave_tick(self) -> None:
        if self.editing and not self.conflict:
            self.worker.autosave(self._editor_text())

    def action_save(self, force: bool = False) -> bool:
        """Write what the editor holds. False when it could not (a conflict, an error)."""
        return self.worker.save(self._editor_text() if self.editing else None, force=force)

    def on_text_area_changed(self, event: TextArea.Changed) -> None:
        if event.text_area.id == "lake-edit" and self.editing:
            self.worker.typed(event.text_area.text)

    def on_descendant_blur(self, event: events.DescendantBlur) -> None:
        if getattr(event.widget, "id", None) == "lake-edit" and self.editing and not self.conflict:
            self.action_save()

    def action_leave_edit(self, reload: bool = True) -> None:
        """Save and go back to the view (a conflict keeps the editor open, so nothing is lost)."""
        if self.editing:
            self.worker.close(reload, self._editor_text())
            self.redraw()

    def on_unmount(self) -> None:
        w = self.worker
        if w is None:
            return
        if w.editing:
            w.text = self._editor_text()
            w.flush()
        if w.reader == self._editor_text:
            w.reader = None

    # -- drawing the worker -------------------------------------------------------------------------

    def redraw(self) -> None:
        """The editor opens and closes with the worker's draft; the head and the view follow it."""
        w, editor = self.worker, self._editor()
        if w is None or editor is None:
            return
        if w.draft is not None and w.draft is not self._open_draft:
            self._open_draft = w.draft
            editor.load_text(w.text)
            editor.show_line_numbers = w.view is None or w.view.kind != "markdown"
            self.query_one("#lake-scroll").display = False
            editor.display = True
            editor.focus()
            if self._autosave is not None:
                self._autosave.stop()
            self._autosave = self.set_interval(w.autosave_s, self._autosave_tick)
        elif w.draft is None and self._open_draft is not None:
            self._open_draft = None
            if self._autosave is not None:
                self._autosave.stop()
                self._autosave = None
            editor.display = False
            self.query_one("#lake-scroll").display = True
        self._render_head()

    def _render_head(self) -> None:
        try:
            head = self.query_one("#lake-head", Static)
        except Exception:
            return
        w = self.worker
        if w.draft is None:
            self._render_view()
            return
        style = "yellow" if w.conflict or w.edit_note.startswith(("●", "⚠")) else "dim"
        head.update(Text.assemble(("✎ editing · ", "bold"), (w.rel(w.draft.path), ""),
                                  (f"  {w.edit_note}" if w.edit_note else "", style),
                                  (f"  · saves every {w.autosave_s}s and on leaving · ctrl+s save · Esc done",
                                   "dim")))

    def _render_view(self) -> None:
        try:
            head, plain, md = (self.query_one("#lake-head", Static), self.query_one("#lake-plain", Static),
                               self.query_one("#lake-md", Markdown))
        except Exception:
            return
        v = self.worker.view
        if v is None:
            head.update(Text("nothing to look at yet — a road brings a file, a diff, a URL or a branch", style="dim"))
            plain.update("")
            md.update("")
            return
        head.update(Text.assemble((f"{v.kind} · ", "bold"), (v.title, ""),
                                  ("  e edits it" if v.path else "", "dim"),
                                  ("  ↗ opens it in the browser" if v.target else "", "dim")))
        md.display = v.kind == "markdown"
        plain.display = v.kind != "markdown"
        if v.kind == "markdown":
            md.update(v.text)
        elif v.kind == "diff":
            table = Table(show_header=True, header_style="bold", expand=True, box=None, pad_edge=False)
            table.add_column("before", ratio=1, overflow="fold")
            table.add_column("after", ratio=1, overflow="fold")
            for left, right, change in v.rows[:DIFF_ROWS]:
                ls, rs = STYLE.get(change, ("", ""))
                table.add_row(Text(left, style=ls), Text(right, style=rs))
            plain.update(table)
        else:
            plain.update(Text(v.text))

    # -- the hut ----------------------------------------------------------------------------------

    def mini_status(self) -> list[str]:
        return self.worker.mini_status()

    def hut_lines(self, widths: list[int]) -> list[str]:
        return self.worker.hut_lines(widths)

    def quick_action(self, action_id: str) -> bool:
        if action_id == "lake.edit":
            if self.editing:
                self.action_leave_edit()
            else:
                self.action_edit()
            return True
        if action_id != "lake.open":
            return False
        target = self.worker.target()
        if not target:
            self.app.notify("nothing to open — a URL or a file shows here first", title="🌊 Lake")
            return True
        url = target if target.startswith(("http://", "https://")) else Path(target).resolve().as_uri()
        try:
            (type(self).opener or webbrowser.open)(url)
        except Exception as e:
            self.app.notify(str(e), title="🌊 Lake", severity="error")
        return True
