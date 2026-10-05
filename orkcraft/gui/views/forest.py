"""🌲 File Forest in the GUI: the folder as a tree that opens folder by folder, the changed files
marked, the target picked. Every act is the worker's (core/workers/forest.py)."""
from __future__ import annotations

import base64
import mimetypes

from orkcraft.core.workers.forest import media_of
from orkcraft.gui.views import ActError, text

REFRESH_S = 10.0              # as the TUI: git is asked this often
THUMB_BYTES = {"image": 2_000_000, "video": 6_000_000}     # a larger file shows its name only
VIDEO_TYPES = {".mov": "video/quicktime", ".m4v": "video/mp4", ".ogv": "video/ogg", ".webm": "video/webm"}


def refresh(w) -> None:
    w.refresh()


def card(w) -> dict:
    """Closed (docs/design/building-views.md): `./<folder>`, how many files changed, the target."""
    return {"folder": w.folder_label(), "changed": len(w.changes), "picked": w.picked.rsplit("/", 1)[-1],
            "error": w.error[:60]}


def detail(w) -> dict:
    """The top of the tree; a folder's rows come with `list` when it is opened."""
    try:
        top, problem = w.listing(), ""
    except ValueError as e:
        top, problem = [], str(e)[:200]
    return {"folder": w.folder_label(), "root": w.rel, "changed": len(w.changes), "picked": w.picked,
            "error": w.error or problem, "top": top}


def _list(w, args: dict) -> list[dict]:
    try:
        return w.listing(text(args, "path", 2000))
    except ValueError as e:
        raise ActError(str(e)) from None


def _pick(w, args: dict) -> str:
    path = text(args, "path", 2000)
    if not path:
        raise ActError("Which file?")
    try:
        if not w.path(path).exists():
            raise ValueError(f"{path} is gone")
    except ValueError as e:
        raise ActError(str(e)) from None
    return w.pick(path, send=False)


def _send(w, args: dict) -> bool:
    if not w.picked:
        raise ActError("Pick a file first")
    sent = w.send()
    w.toast(f"{w.picked.rsplit('/', 1)[-1]}: " + ("sent down its roads" if sent else "no road takes files.selected from here"),
            severity="information" if sent else "warning")
    return sent


def _open(w, args: dict) -> None:
    problem = w.open_in_os()
    if problem:
        raise ActError(problem)


def _thumb(w, args: dict) -> str:
    """A small preview of an image or a video as a data: URL ("" when it is too large to send)."""
    try:
        p = w.file(text(args, "path", 2000))
    except ValueError as e:
        raise ActError(str(e)) from None
    media = media_of(p.name)
    if not media or p.stat().st_size > THUMB_BYTES[media]:
        return ""
    kind = VIDEO_TYPES.get(p.suffix.lower()) or mimetypes.guess_type(p.name)[0] or "application/octet-stream"
    return f"data:{kind};base64," + base64.b64encode(p.read_bytes()).decode("ascii")


ACTS = {"list": _list, "pick": _pick, "send": _send, "open": _open, "thumb": _thumb}
