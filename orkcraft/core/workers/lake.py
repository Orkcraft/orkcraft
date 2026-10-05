"""🌊 The Lake of Insight's work: what it shows and the file open in its editor.

A cart's file, diff, Markdown, URL or branch name is looked at in a thread (realm/lake.py) and
shown when the look comes back (`lake.viewed`). The setting `url` is shown when nothing else has
arrived. A text file on disk is edited in place: `open()` reads it, `save(text)` writes it (never
over a change on disk unless `force`), `close()` saves and goes back to the view (`lake.saved`
when something was written). The face draws `view` and `draft` and holds the editor; it may set
`reader` so the worker reads what the editor holds right now.
"""
from __future__ import annotations

import threading
from pathlib import Path
from typing import Callable

from orkcraft.core.workers import Worker
from orkcraft.realm import jobs, lake

AUTOSAVE_S = 5
TITLE = "🌊 Lake"


class LakeWorker(Worker):
    TYPE = "lake"
    fetcher = None                 # tests catch the network here

    def __init__(self, town, building_id: str) -> None:
        super().__init__(town, building_id)
        self.view: lake.View | None = None
        self.draft: lake.Draft | None = None     # the file open in the editor
        self.text = ""                           # what the editor holds (the face keeps it current)
        self.reader: Callable[[], str] | None = None
        self.edit_note = ""                      # saved 12:03 · ● unsaved · ⚠ changed on disk
        self.conflict = False
        self.saved_any = False                   # something was written since the editor opened

    def start(self) -> None:
        url = str(self.config.get("url") or "")
        if url and self.view is None:
            self.show_value("text", url, url)

    # -- looking at things ----------------------------------------------------------------------

    def receive(self, payload, title: str, markdown: str) -> None:
        self.show_value(payload.kind, payload.value, payload.title or title)

    def show_value(self, kind: str, value: str, title: str = "") -> None:
        """Look at it in a thread; it is shown once the look comes back."""
        repo, fetch = self.repo_root, type(self).fetcher

        def work() -> None:
            v = lake.look(repo, kind, value, title, *([fetch] if fetch else []))
            try:
                self.town.call(self.show, v)
            except Exception:
                pass

        threading.Thread(target=work, daemon=True, name=f"lake-{self.building_id}").start()

    def show(self, v: lake.View) -> None:
        if self.draft is not None:               # a new cart: what was typed is saved first
            self.close(reload=False)
            if self.draft is not None:           # a conflict keeps the editor open: the cart is not shown
                self.toast(f"{v.title}: not shown — save or leave the file you edit first", title=TITLE)
                return
        self.view = v
        self.changed()
        self.emit("lake.viewed", v.target or v.title, f"{v.kind}: {v.title}")

    # -- editing a file -------------------------------------------------------------------------

    @property
    def editing(self) -> bool:
        return self.draft is not None

    @property
    def autosave_s(self) -> int:
        try:
            return max(int(self.config.get("autosave") or AUTOSAVE_S), 1)
        except (TypeError, ValueError):
            return AUTOSAVE_S

    def current(self) -> str:
        """What the editor holds now."""
        if self.reader is not None:
            try:
                return self.reader()
            except Exception:
                pass
        return self.text

    @property
    def dirty(self) -> bool:
        return self.draft is not None and self.current() != self.draft.text

    def open(self) -> bool:
        """Open the file shown in the editor. False when what is shown is not a text file on disk."""
        v = self.view
        if v is None or not v.path:
            self.toast("only a file on disk is edited here — a road brings one, or Enter on a file "
                       "in a File Forest", title=TITLE)
            return False
        try:
            self.draft = lake.read_for_edit(v.path)
        except ValueError as e:
            self.toast(f"{v.title}: {e}", title=TITLE, severity="warning")
            return False
        self.text = self.draft.text
        self.conflict, self.saved_any, self.edit_note = False, False, ""
        self.changed()
        return True

    def typed(self, text: str) -> None:
        """The editor's text changed."""
        self.text = text
        if self.draft is not None and text != self.draft.text and not self.conflict:
            self.edit_note = "● unsaved"
            self.changed()

    def save(self, text: str | None = None, force: bool = False) -> bool:
        """Write what the editor holds. False when it could not (a conflict, an error)."""
        if self.draft is None:
            return True
        if text is None:
            text = self.current()
        self.text = text
        if text == self.draft.text and not (force and self.conflict):
            return True
        try:
            status = lake.save(self.draft, text, force=force)
        except OSError as e:
            self.edit_note = f"⚠ not saved: {e}"
            self.changed()
            self.toast(f"{self.draft.path}: {e}", title=f"{TITLE}: not saved", severity="error")
            return False
        if status == "conflict":
            if not self.conflict:
                self.toast(f"{self.file_name()} changed on disk since you opened it: nothing was saved. "
                           "ctrl+s writes your text over it", title=TITLE, severity="warning", timeout=10)
            self.conflict, self.edit_note = True, "⚠ changed on disk — ctrl+s overwrites"
            self.changed()
            return False
        self.conflict = False
        if status == "saved":
            self.saved_any = True
            self.edit_note = f"saved {jobs.now_iso()[11:19]}"
        self.changed()
        return True

    def close(self, reload: bool = True, text: str | None = None) -> bool:
        """Save and go back to the view (a conflict keeps the editor open, so nothing is lost).
        True when the editor closed."""
        if self.draft is None:
            return True
        if not self.save(text):
            if self.conflict:
                self.toast(f"{self.file_name()} changed on disk: ctrl+s writes your text over it",
                           title=TITLE, severity="warning")
            return False
        path, saved = self.draft.path, self.saved_any
        self.draft, self.conflict, self.edit_note = None, False, ""
        self.changed()
        if saved:
            self.emit("lake.saved", self.rel(path), f"edited: {self.file_name(path)}")
        if reload and self.view is not None and self.view.path == path:     # the view shows what is on disk now
            self.show_value("file", path, self.view.title)
        return True

    def flush(self) -> None:
        """The face goes away: what the editor holds is written, quietly (never over a change on disk)."""
        if self.draft is not None and not self.conflict:
            try:
                lake.save(self.draft, self.current())
            except Exception:
                pass

    def file_name(self, path: str = "") -> str:
        return Path(path or (self.draft.path if self.draft else "")).name

    def rel(self, path: str) -> str:
        try:
            return str(Path(path).resolve().relative_to(self.repo_root.resolve()))
        except ValueError:
            return path

    def target(self) -> str:
        """What ↗ opens: what is shown, else the setting `url`."""
        return self.view.target if self.view else str(self.config.get("url") or "")

    # -- the hut --------------------------------------------------------------------------------

    def status(self) -> str:
        return "EDITING" if self.draft is not None else "SHOWING" if self.view is not None else ""

    def mini_status(self) -> list[str]:
        if self.draft is not None:
            return [f"✎ {self.file_name()}", self.edit_note or "editing"]
        if self.view is None:
            return ["nothing shown"]
        v = self.view
        lines = [f"{v.kind}: {v.title.rsplit('/', 1)[-1]}"]
        if v.kind == "diff":
            plus, minus = _counts(v)
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
                plus, minus = _counts(v)
                right = ["kind: diff", f"+{plus} −{minus}", f"rows: {len(v.rows)}"]
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


def _counts(v: lake.View) -> tuple[int, int]:
    return sum(1 for r in v.rows if r[2] in "+~"), sum(1 for r in v.rows if r[2] in "-~")
