"""🌊 Lake in the GUI: what is shown (Markdown rendered, a diff side by side, text) and the file
open in the editor. The page holds the editor's text and sends it with each act; the worker
(core/workers/lake.py) saves, judges and says what changed."""
from __future__ import annotations

import webbrowser
from pathlib import Path

from orkcraft.gui import markdown
from orkcraft.gui.views import ActError, text

DIFF_ROWS = 2000              # as the TUI


def detail(w) -> dict:
    v, out = w.view, {"view": None, "editing": None}
    if v is not None:
        shown = {"kind": v.kind, "title": v.title, "target": v.target, "editable": bool(v.path)}
        if v.kind == "markdown":
            shown["html"] = markdown.render(v.text)
        elif v.kind == "diff":
            shown["rows"] = [list(r) for r in v.rows[:DIFF_ROWS]]
            shown["cut"] = max(len(v.rows) - DIFF_ROWS, 0)
        else:
            shown["text"] = v.text[:markdown.LIMIT]
        out["view"] = shown
    if w.draft is not None:
        out["editing"] = {
            "draft": f"{w.draft.path}:{id(w.draft)}",     # a new draft: the page loads its text again
            "path": w.rel(w.draft.path), "text": w.text, "note": w.edit_note,
            "conflict": w.conflict, "autosave_s": w.autosave_s,
            "markdown": v is not None and v.kind == "markdown",
        }
    return out


def _open(w, args: dict) -> bool:
    return w.open()


def _typed(w, args: dict) -> None:
    w.typed(text(args, "text"))


def _save(w, args: dict) -> bool:
    return w.save(text(args, "text"), force=bool(args.get("force")))


def _autosave(w, args: dict) -> bool:
    return w.autosave(text(args, "text"))


def _close(w, args: dict) -> bool:
    return w.close(True, text(args, "text"))


def _browse(w, args: dict) -> str:
    """What ↗ opens, in the person's browser (a file by its path)."""
    target = w.target()
    if not target:
        raise ActError("Nothing to open: a URL or a file shows here first")
    url = target if "://" in target else Path(target if Path(target).is_absolute() else w.repo_root / target).as_uri()
    webbrowser.open(url)
    return target


ACTS = {"edit": _open, "typed": _typed, "save": _save, "autosave": _autosave, "done": _close, "browse": _browse}


def flush(w) -> None:
    """The window goes: what the editor holds is written, as the TUI does on leaving."""
    if w.draft is not None:
        w.flush()
