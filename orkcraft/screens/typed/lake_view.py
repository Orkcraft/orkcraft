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
"""
from __future__ import annotations

import threading
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

from orkcraft.realm import jobs, lake
from orkcraft.screens.typed.base import TypedView

STYLE = {"-": ("red", ""), "+": ("", "green"), "~": ("red", "green"), "@": ("bold cyan", "bold cyan"), " ": ("", "")}
DIFF_ROWS = 2000
AUTOSAVE_S = 5


class LakeView(TypedView):
    TYPE = "lake"
    UI_PANES = {"head": "#lake-head", "view": "#lake-scroll", "editor": "#lake-edit"}
    opener = None                  # tests catch the browser here
    fetcher = None                 # and the network
    BINDINGS = [Binding("e", "edit", "Edit"),
                Binding("ctrl+s", "save(True)", "Save", show=False),
                Binding("escape", "leave_edit", "Done", show=False)]
    DEFAULT_CSS = """
    LakeView #lake-edit { height: 1fr; display: none; }
    """

    def __init__(self, *a, **kw) -> None:
        super().__init__(*a, **kw)
        self.view: lake.View | None = None
        self.draft: lake.Draft | None = None     # the file open in the editor
        self.edit_note = ""                      # saved 12:03 · ● unsaved · ⚠ changed on disk
        self.conflict = False
        self.saved_any = False                   # something was written since the editor opened
        self._autosave: Timer | None = None

    def compose_body(self) -> ComposeResult:
        yield Static("", id="lake-head", classes="typed-head")
        with VerticalScroll(id="lake-scroll"):
            yield Static("", id="lake-plain")
            yield Markdown("", id="lake-md")
        yield TextArea("", id="lake-edit", soft_wrap=True)

    def on_mount(self) -> None:
        url = str(self.config.get("url") or "")
        if url and self.view is None:
            self.show_value("text", url, url)
        else:
            self._render_view()

    def receive(self, payload, title: str, markdown: str) -> None:
        self.show_value(payload.kind, payload.value, payload.title or title)

    def show_value(self, kind: str, value: str, title: str = "") -> None:
        repo, app = self._get_repo_root(), self.app
        fetch = type(self).fetcher

        def work() -> None:
            v = lake.look(repo, kind, value, title, *([fetch] if fetch else []))
            try:
                app.call_from_thread(self.show, v)
            except Exception:
                pass

        threading.Thread(target=work, daemon=True, name=f"lake-{self.building_id}").start()

    def show(self, v: lake.View) -> None:
        if self.draft is not None:               # a new cart: what was typed is saved first
            self.action_leave_edit(reload=False)
            if self.draft is not None:           # a conflict keeps the editor open: the cart is not shown
                self.app.notify(f"{v.title}: not shown — save or leave the file you edit first", title="🌊 Lake")
                return
        self.view = v
        self._render_view()
        self.emit("lake.viewed", v.target or v.title, f"{v.kind}: {v.title}")

    # -- editing a file -----------------------------------------------------------------------------

    @property
    def editing(self) -> bool:
        return self.draft is not None

    @property
    def autosave_s(self) -> int:
        try:
            return max(int(self.config.get("autosave") or AUTOSAVE_S), 1)
        except (TypeError, ValueError):
            return AUTOSAVE_S

    def check_action(self, action: str, parameters: tuple) -> bool | None:
        if action == "edit":
            return not self.editing                  # in the editor `e` is a letter
        if action in ("save", "leave_edit"):
            return self.editing                      # else Esc goes on to the town
        return True

    def action_edit(self) -> None:
        v = self.view
        if v is None or not v.path:
            self.app.notify("only a file on disk is edited here — a road brings one, or Enter on a file "
                            "in a File Forest", title="🌊 Lake")
            return
        try:
            self.draft = lake.read_for_edit(v.path)
        except ValueError as e:
            self.app.notify(f"{v.title}: {e}", title="🌊 Lake", severity="warning")
            return
        self.conflict, self.saved_any, self.edit_note = False, False, ""
        editor = self.query_one("#lake-edit", TextArea)
        editor.load_text(self.draft.text)
        editor.show_line_numbers = v.kind != "markdown"
        self.query_one("#lake-scroll").display = False
        editor.display = True
        editor.focus()
        self._autosave = self.set_interval(self.autosave_s, self._autosave_tick)
        self._render_head()

    def _autosave_tick(self) -> None:
        if self.editing and not self.conflict:
            self.action_save()

    @property
    def dirty(self) -> bool:
        return self.draft is not None and self.query_one("#lake-edit", TextArea).text != self.draft.text

    def action_save(self, force: bool = False) -> bool:
        """Write what the editor holds. False when it could not (a conflict, an error)."""
        if self.draft is None:
            return True
        text = self.query_one("#lake-edit", TextArea).text
        if text == self.draft.text and not (force and self.conflict):
            return True
        try:
            status = lake.save(self.draft, text, force=force)
        except OSError as e:
            self.edit_note = f"⚠ not saved: {e}"
            self._render_head()
            self.app.notify(f"{self.draft.path}: {e}", title="🌊 Lake: not saved", severity="error")
            return False
        if status == "conflict":
            if not self.conflict:
                self.app.notify(f"{self._file_name()} changed on disk since you opened it: nothing was saved. "
                                "ctrl+s writes your text over it", title="🌊 Lake", severity="warning", timeout=10)
            self.conflict, self.edit_note = True, "⚠ changed on disk — ctrl+s overwrites"
            self._render_head()
            return False
        self.conflict = False
        if status == "saved":
            self.saved_any = True
            self.edit_note = f"saved {jobs.now_iso()[11:19]}"
        self._render_head()
        return True

    def on_text_area_changed(self, event: TextArea.Changed) -> None:
        if event.text_area.id == "lake-edit" and self.dirty and not self.conflict:
            self.edit_note = "● unsaved"
            self._render_head()

    def on_descendant_blur(self, event: events.DescendantBlur) -> None:
        if getattr(event.widget, "id", None) == "lake-edit" and self.editing and not self.conflict:
            self.action_save()

    def action_leave_edit(self, reload: bool = True) -> None:
        """Save and go back to the view (a conflict keeps the editor open, so nothing is lost)."""
        if self.draft is None:
            return
        if not self.action_save():
            if self.conflict:
                self.app.notify(f"{self._file_name()} changed on disk: ctrl+s writes your text over it",
                                title="🌊 Lake", severity="warning")
            return
        path, saved = self.draft.path, self.saved_any
        self._close_editor()
        if saved:
            self.emit("lake.saved", self._rel(path), f"edited: {self._file_name(path)}")
        if reload and self.view is not None and self.view.path == path:     # the view shows what is on disk now
            self.show_value("file", path, self.view.title)

    def _close_editor(self) -> None:
        if self._autosave is not None:
            self._autosave.stop()
            self._autosave = None
        self.draft, self.conflict, self.edit_note = None, False, ""
        try:
            self.query_one("#lake-edit", TextArea).display = False
            self.query_one("#lake-scroll").display = True
        except Exception:
            pass

    def on_unmount(self) -> None:
        if self.draft is not None and not self.conflict:
            try:
                lake.save(self.draft, self.query_one("#lake-edit", TextArea).text)
            except Exception:
                pass

    def _file_name(self, path: str = "") -> str:
        return Path(path or (self.draft.path if self.draft else "")).name

    def _rel(self, path: str) -> str:
        try:
            return str(Path(path).resolve().relative_to(self._get_repo_root().resolve()))
        except ValueError:
            return path

    def _render_head(self) -> None:
        try:
            head = self.query_one("#lake-head", Static)
        except Exception:
            return
        if self.draft is None:
            self._render_view()
            return
        style = "yellow" if self.conflict or self.edit_note.startswith(("●", "⚠")) else "dim"
        head.update(Text.assemble(("✎ editing · ", "bold"), (self._rel(self.draft.path), ""),
                                  (f"  {self.edit_note}" if self.edit_note else "", style),
                                  (f"  · saves every {self.autosave_s}s and on leaving · ctrl+s save · Esc done",
                                   "dim")))

    def _render_view(self) -> None:
        try:
            head, plain, md = (self.query_one("#lake-head", Static), self.query_one("#lake-plain", Static),
                               self.query_one("#lake-md", Markdown))
        except Exception:
            return
        v = self.view
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
        if self.draft is not None:
            return [f"✎ {self._file_name()}", self.edit_note or "editing"]
        if self.view is None:
            return ["nothing shown"]
        v = self.view
        lines = [f"{v.kind}: {v.title.rsplit('/', 1)[-1]}"]
        if v.kind == "diff":
            plus = sum(1 for r in v.rows if r[2] in "+~")
            minus = sum(1 for r in v.rows if r[2] in "-~")
            lines.append(f"+{plus} −{minus}")
        return lines

    def hut_lines(self, widths: list[int]) -> list[str]:
        """The panorama: the left pane the diff (or the first lines of what is shown), the right
        one what it is — interleaved, row by row, as the silhouette's slots come."""
        v = self.view
        panes = max((len(widths) - 1) // 2, 1)      # the head is not in `widths`; pane rows come in pairs, then the last line
        if v is None:
            left, right, last = ["nothing shown yet"], [], "open the building to look at something"
        else:
            if v.kind == "diff":
                left = []
                for l, r, c in v.rows:
                    if c == "-":
                        left.append(f"- {l}")
                    elif c == "+":
                        left.append(f"+ {r}")
                    elif c == "~":
                        left += [f"- {l}", f"+ {r}"]
                plus = sum(1 for r in v.rows if r[2] in "+~")
                minus = sum(1 for r in v.rows if r[2] in "-~")
                right = [f"kind: diff", f"+{plus} −{minus}", f"rows: {len(v.rows)}"]
            else:
                left = [ln for ln in v.text.splitlines() if ln.strip()]
                right = [f"kind: {v.kind}", f"lines: {len(v.text.splitlines())}"]
            right.insert(0, v.title.rsplit("/", 1)[-1])
            last = f"{v.kind} · {v.target or v.title}"
        out: list[str] = []
        for i in range(panes):
            out.append(left[i] if i < len(left) else "")
            out.append(right[i] if i < len(right) else "")
        return out + [last]

    def quick_action(self, action_id: str) -> bool:
        if action_id == "lake.edit":
            if self.editing:
                self.action_leave_edit()
            else:
                self.action_edit()
            return True
        if action_id != "lake.open":
            return False
        target = self.view.target if self.view else str(self.config.get("url") or "")
        if not target:
            self.app.notify("nothing to open — a URL or a file shows here first", title="🌊 Lake")
            return True
        url = target if target.startswith(("http://", "https://")) else Path(target).resolve().as_uri()
        try:
            (type(self).opener or webbrowser.open)(url)
        except Exception as e:
            self.app.notify(str(e), title="🌊 Lake", severity="error")
        return True
