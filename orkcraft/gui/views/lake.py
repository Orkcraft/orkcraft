"""🌊 Lake in the GUI: the town's one Lake window (docs/design/building-views.md §2) — its documents in
tabs, each shown as it reads best (Markdown rendered, code, a diff side by side, a picture, a PDF, a
page) and a file edited in place. The page holds the editor's text and sends it with each act; the
tab (core/workers/lake.py `Tab`) saves and says what changed.

The snapshot carries only the tabs' heads (`summary`); the page asks for the one it shows
(`lake.doc`) when its `rev` moved. An old Lake building (a scroll from before, a TUI's) still draws
through `detail` / `ACTS`, but the GUI takes it off the map when the town opens (`attach`).
"""
from __future__ import annotations

import base64
import webbrowser
from pathlib import Path
from typing import Any, Callable

from orkcraft.core.workers.lake import TITLE, TownLake
from orkcraft.gui import markdown
from orkcraft.gui.views import ActError, text
from orkcraft.realm import catalog, lake

DIFF_ROWS = 2000              # as the TUI


def _shown(v) -> dict:
    shown = {"kind": v.kind, "title": v.title, "target": v.target, "editable": bool(v.path)}
    if v.kind == "markdown":
        shown["html"] = markdown.render(v.text)
    elif v.kind == "diff":
        shown["rows"] = [list(r) for r in v.rows[:DIFF_ROWS]]
        shown["cut"] = max(len(v.rows) - DIFF_ROWS, 0)
    elif v.kind not in ("image", "pdf", "web"):
        shown["text"] = v.text[:markdown.LIMIT]
    return shown


def detail(w) -> dict:
    v, out = w.view, {"view": None, "editing": None}
    if v is not None:
        out["view"] = _shown(v)
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


# -- the town's Lake window --------------------------------------------------------------------------

def attach(town) -> list[str]:
    """The town gets its one Lake; an old scroll's Lake buildings leave the map (realm/lake.py
    `retire`) and the scroll is kept so. The ids that left."""
    town.lake = TownLake(town)
    gone = lake.retire(town.scroll, lambda bid: catalog.type_of(town.spec_of(bid)).id)
    if gone:
        town.save()
        town.toast(f"Lake is the town's window now: {len(gone)} Lake building{'s' if len(gone) != 1 else ''} "
                   "left the map; what went into one opens in Lake", title=TITLE)
    return gone


def summary(town_lake: TownLake | None) -> dict:
    """The tabs' heads, for the snapshot (small: the page asks for a document's body itself)."""
    if town_lake is None:
        return {"tabs": [], "rev": 0}
    tabs = []
    for t in town_lake.tabs:
        v = t.view
        tabs.append({"id": t.id, "title": t.title or (v.title if v else t.value[:80]), "kind": v.kind if v else t.kind,
                     "from": t.source, "rev": t.rev, "editing": t.editing, "conflict": t.conflict,
                     "note": t.edit_note})
    return {"tabs": tabs, "rev": town_lake.rev}


def doc(t) -> dict:
    """What a tab draws: what it shows and its editor, as `detail`; a picture or a PDF with its bytes."""
    out = detail(t)
    out.update({"id": t.id, "rev": t.rev, "from": t.source, "path": t.rel(t.path) if t.path else "",
                "url": t.value if t.kind == "url" else ""})
    media = t.media()
    if media is not None and out["view"] is not None:
        mime, data = media
        out["view"]["media"] = {"type": mime, "data": base64.b64encode(data).decode("ascii")}
    elif out["view"] is not None and out["view"]["kind"] in ("image", "pdf"):
        out["view"]["missing"] = True
    return out


def _lake(town) -> TownLake:
    if town.lake is None:
        town.lake = TownLake(town)
    return town.lake


def _tab(town, args: dict):
    t = _lake(town).tab(str(args.get("tab") or ""))
    if t is None:
        raise ActError("That document is not open in Lake any more")
    return t


def open_doc(town, args: dict) -> str:
    """`lake.open`: a document in a tab — `kind` file | url | text, `value`, `title`, `from` (the building
    it came from; its keeper answers on a selection). The tab's id."""
    kind = str(args.get("kind") or "text")
    value = args.get("value")
    value = value[:2_000_000] if isinstance(value, str) else ""
    title, source = text(args, "title")[:200], text(args, "from")[:200]
    if kind == "text" and lake.URL.match(value.strip()):
        kind, value = "url", value.strip()
    if kind == "file" and value.strip():
        try:
            (town.repo_root / value.strip()).resolve().relative_to(town.repo_root.resolve())
        except (ValueError, OSError):
            raise ActError("Lake opens the project's own files") from None
    try:
        return _lake(town).open(kind, value.strip() if kind != "text" else value, title, source).id
    except ValueError as e:
        raise ActError(str(e)) from None


def _close(town, args: dict) -> bool:
    raw = args.get("text")
    return _lake(town).close(str(args.get("tab") or ""), raw if isinstance(raw, str) else None)


def _act(town, args: dict) -> Any:
    """One of a tab's acts (`ACTS`): edit, typed, save, autosave, done, browse."""
    t = _tab(town, args)
    fn = ACTS.get(str(args.get("act") or ""))
    if fn is None:
        raise ActError(f"Lake cannot {args.get('act')!r}")
    return fn(t, dict(args.get("args") or {}))


def commands(town) -> dict[str, Callable[[dict], Any]]:
    """The Lake window's host commands besides `lake.open` (gui/console.py)."""
    return {
        "lake.doc": lambda a: doc(_tab(town, a)),
        "lake.close": lambda a: _close(town, a),
        "lake.act": lambda a: _act(town, a),
    }


def flush_town(town_lake: TownLake | None) -> None:
    if town_lake is not None:
        town_lake.flush()
