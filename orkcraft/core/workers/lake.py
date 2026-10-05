"""🌊 The Lake of Insight's work: what it shows and the file open in its editor.

A cart's file, diff, Markdown, URL or branch name is looked at in a thread (realm/lake.py) and
shown when the look comes back (`lake.viewed`). The setting `url` is shown when nothing else has
arrived. A text file on disk is edited in place: `open()` reads it, `save(text)` writes it (never
over a change on disk unless `force`), `close()` saves and goes back to the view (`lake.saved`
when something was written). The face draws `view` and `draft` and holds the editor; it may set
`reader` so the worker reads what the editor holds right now.

An ork's file (a cart with a trail) is kept as the ork made it (`lake.Origins`). When the person
leaves the editor — or the face goes with it open (`flush`), or an edit was saved and left alone for
`JUDGE_IDLE_S` (`autosave`) — their text is compared with the ork's (`realm/edits.py`): filling it in
— a daily note the ork laid out and the person writes into — says nothing against the ork; fixing
it, changing its format or rewriting it is a 👎 for the building that made it (`feedback.signal`),
with the edit unless the file is personal. A file git tracks unchanged since the last commit was
only pointed at, not written: it is not the ork's. A file that came and was never opened for a day
counts as unused (`feedback.await_view`; selecting this Lake sees it).

The GUI has no Lake building: one Lake is the town's window (`TownLake`, docs/design/building-views.md
§2), its documents in tabs. A tab (`Tab`) edits a file as a Lake building does (`Document`) but has
no roads: saving only writes the file. A source whose road went into an old Lake building opens what
it sends in the town's Lake (`TownLake.follow`, realm/lake.py `retire`).
"""
from __future__ import annotations

import itertools
import threading
import time
from pathlib import Path
from typing import Callable

from orkcraft.core import bus
from orkcraft.core.workers import Worker, state_dir
from orkcraft.realm import feedback, jobs, lake

AUTOSAVE_S = 5
JUDGE_IDLE_S = 600     # an edit saved and left alone this long is judged, the editor still open
TITLE = "🌊 Lake"


class Document:
    """What is shown and the file open in the editor: a Lake building's, or a tab of the town's Lake.
    Who keeps it says how it tells the town (`changed`, `toast`, `emit`) and where it keeps what
    it learns (`state_dir`, `config`, `repo_root`)."""

    def _start_document(self) -> None:
        self.view: lake.View | None = None
        self.draft: lake.Draft | None = None     # the file open in the editor
        self.text = ""                           # what the editor holds (the face keeps it current)
        self.reader: Callable[[], str] | None = None
        self.edit_note = ""                      # saved 12:03 · ● unsaved · ⚠ changed on disk
        self.conflict = False
        self.saved_any = False                   # something was written since the editor opened
        self._typed = 0.0                        # when the editor's text last changed (monotonic)
        self._judged = ""                        # the text last judged while the editor stayed open

    def show_value(self, kind: str, value: str, title: str = "") -> None:
        raise NotImplementedError

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
        self._typed, self._judged = time.monotonic(), ""
        self.changed()
        return True

    def typed(self, text: str) -> None:
        """The editor's text changed."""
        if text != self.text:
            self._typed = time.monotonic()
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
        if text != self.text:
            self._typed = time.monotonic()
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

    def autosave(self, text: str | None = None) -> bool:
        """The editor's timer: save; an edit saved and left alone for `JUDGE_IDLE_S` is as good as
        left, so it is judged (never in the middle of typing, when a heading deleted to be retyped
        would read as a new format)."""
        if self.draft is None or self.conflict or not self.save(text):
            return False
        if self.saved_any and time.monotonic() - self._typed >= JUDGE_IDLE_S and self._judged != self.draft.text:
            self._judged = self.draft.text
            self.judge(self.draft.path, self.draft.text)
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
        path, saved, text = self.draft.path, self.saved_any, self.draft.text
        self.draft, self.conflict, self.edit_note = None, False, ""
        self.changed()
        if saved:
            self.judge(path, text)
            self.emit("lake.saved", self.rel(path), f"edited: {self.file_name(path)}")
        if reload and self.view is not None and self.view.path == path:     # the view shows what is on disk now
            self.show_value("file", path, self.view.title)
        return True

    def flush(self) -> None:
        """The face goes away (the app closes in the editor): what the editor holds is written,
        quietly (never over a change on disk), and judged."""
        if self.draft is not None and not self.conflict:
            try:
                if lake.save(self.draft, self.current()) == "saved" or self.saved_any:
                    self.judge(self.draft.path, self.draft.text)
            except Exception:
                pass

    def judge(self, path: str, text: str) -> None:
        """What the person's edit of an ork's file says about the ork (filling it in says nothing)."""
        judged = lake.Origins(self.state_dir).judge(path, text)
        if judged is None:
            return
        made_by, edit = judged
        if edit.kind in ("touched", "reshaped", "rewritten"):
            private = lake.personal(text)                # a personal note's text never reaches a model
            feedback.signal(self.repo_root, made_by, False, f"lake.{edit.kind}", value=self.rel(path),
                            note=f"{self.rel(path)}: {edit.summary}", tag="format" if edit.kind == "reshaped" else "",
                            edit="" if private else edit.diff)

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


class LakeWorker(Document, Worker):
    """A Lake building (the TUI's): what its roads bring, shown and edited."""
    TYPE = "lake"
    fetcher = None                 # tests catch the network here

    def __init__(self, town, building_id: str) -> None:
        Worker.__init__(self, town, building_id)
        self._start_document()

    def start(self) -> None:
        url = str(self.config.get("url") or "")
        if url and self.view is None:
            self.show_value("text", url, url)

    # -- looking at things ----------------------------------------------------------------------

    def receive(self, payload, title: str, markdown: str) -> None:
        made_by = feedback.maker(payload.trail)          # only what an ork worked on is the ork's
        if made_by:
            if payload.kind == "file":
                path = Path(payload.value)
                path = path if path.is_absolute() else self.repo_root / path
                lake.Origins(self.state_dir).remember(str(path), made_by, jobs.now_iso())
            feedback.await_view(self.repo_root, self.building_id, made_by, payload.title or title)
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


# -- the town's Lake: one window, documents in tabs ------------------------------------------------

MAX_TABS = 12
IMAGES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".gif": "image/gif",
          ".webp": "image/webp", ".svg": "image/svg+xml", ".bmp": "image/bmp", ".ico": "image/x-icon"}
PDF = {".pdf": "application/pdf"}
MEDIA_LIMIT = 15 * 1024 * 1024       # a bigger picture or PDF opens in the browser, not here


def media_type(path: str) -> str:
    """The picture's or the PDF's media type by its name; "" for anything else."""
    suffix = Path(path).suffix.lower()
    return IMAGES.get(suffix) or PDF.get(suffix) or ""


class Tab(Document):
    """One document of the town's Lake: a file of the project, a page, a text. A file is edited in
    place; saving only writes it (no roads)."""

    def __init__(self, lake_: "TownLake", tab_id: str, kind: str, value: str, title: str, source: str) -> None:
        self.lake, self.id = lake_, tab_id
        self.kind, self.value, self.source = kind, value, source      # source: the building it came from
        self.title = title
        self.rev = 0
        self._start_document()

    # what a Lake building has from its spec, a tab has from the town
    @property
    def town(self):
        return self.lake.town

    @property
    def repo_root(self) -> Path:
        return self.town.repo_root

    @property
    def state_dir(self) -> Path:
        return state_dir(self.repo_root, "lake", "_town")

    @property
    def config(self) -> dict:
        return {}

    def changed(self) -> None:
        self.rev += 1
        self.lake.changed()

    def toast(self, message: str, title: str = "", severity: str = "information",
              timeout: float | None = None) -> None:
        self.town.call(self.town.toast, message, title or TITLE, severity, timeout)

    def emit(self, *a, **k) -> bool:
        return False                     # the town's Lake has no roads

    def show_value(self, kind: str, value: str, title: str = "") -> None:
        """Look at it now (a file, a text; a page is the page itself, never fetched)."""
        if kind == "url":
            self.show(lake.View("web", title or value, target=value))
            return
        if kind == "file":
            p = Path(value) if Path(value).is_absolute() else self.repo_root / value
            mime = media_type(str(p))
            if mime:
                kind_ = "pdf" if mime == "application/pdf" else "image"
                self.show(lake.View(kind_, title or value, target=str(p)))
                return
        self.show(lake.look(self.repo_root, kind, value, title))

    @property
    def path(self) -> str:
        """The file it shows on disk ("" for a page or a text)."""
        return self.view.target if self.view is not None and self.kind == "file" else ""

    def media(self) -> tuple[str, bytes] | None:
        """(media type, bytes) of the picture or the PDF it shows; None when it shows something else
        or the file cannot be read (or is too big to send)."""
        v = self.view
        if v is None or v.kind not in ("image", "pdf"):
            return None
        mime = media_type(v.target)
        try:
            p = Path(v.target)
            if p.stat().st_size > MEDIA_LIMIT:
                return None
            return mime, p.read_bytes()
        except OSError:
            return None


class TownLake:
    """The town's one Lake: its tabs, the one shown, and what opens there by itself."""

    def __init__(self, town) -> None:
        self.town = town
        self.tabs: list[Tab] = []
        self.rev = 0
        self._ids = itertools.count(1)

    def changed(self) -> None:
        self.rev += 1
        self.town.call(lambda: self.town.publish(bus.WORKER, building=None, lake=True))

    def tab(self, tab_id: str) -> Tab | None:
        return next((t for t in self.tabs if t.id == tab_id), None)

    def open(self, kind: str, value: str, title: str = "", source: str = "") -> Tab:
        """Open a document in a tab (the one that has it already, looked at again); the oldest tab
        that edits nothing goes when there are too many."""
        if kind not in ("file", "url", "text"):
            raise ValueError(f"Lake opens a file, a page or a text, not {kind!r}")
        if not value:
            raise ValueError("Nothing to open")
        if kind == "file":
            p = Path(value)
            value = str(p if p.is_absolute() else (self.town.repo_root / p))
        title = title or (Path(value).name if kind == "file" else value if kind == "url" else "")
        tab = next((t for t in self.tabs if t.kind == kind and t.value == value), None)
        if tab is None:
            tab = Tab(self, f"t{next(self._ids)}", kind, value, title, source)
            self.tabs.append(tab)
            while len(self.tabs) > MAX_TABS:
                old = next((t for t in self.tabs if t is not tab and not t.editing), None)
                if old is None:
                    break
                self.tabs.remove(old)
        elif source:
            tab.source = source
        if not tab.editing:
            tab.show_value(kind, value, title)
        if tab.view is not None and tab.view.kind == "code" and tab.view.path and not tab.editing:
            tab.open()                   # code is edited where it is shown
        self.changed()
        return tab

    def close(self, tab_id: str, text: str | None = None) -> bool:
        """Close a tab: what its editor holds is saved first (a conflict keeps it open). True when it closed."""
        tab = self.tab(tab_id)
        if tab is None:
            return True
        if tab.editing and not tab.close(reload=False, text=text):
            return False
        self.tabs.remove(tab)
        self.changed()
        return True

    def follow(self, building_id: str, event_id: str, kind: str, value: str, title: str = "") -> bool:
        """A building sent `event_id`: when a road of it once went into a Lake building, what it sent
        opens here (realm/lake.py `retire`). True when it opened."""
        bs = self.town.scroll.building(building_id) if self.town.scroll is not None else None
        if bs is None or not lake.opens_in_lake(bs, event_id) or not value:
            return False
        kind = "file" if kind == "file" else "url" if lake.URL.match(value.strip()) else "text"

        def opened() -> None:
            try:
                self.open(kind, value.strip() if kind == "url" else value, title, building_id)
            except Exception:
                pass

        self.town.call(opened)
        return True

    def flush(self) -> None:
        """The window goes: what every editor holds is written, quietly."""
        for t in self.tabs:
            t.flush()
