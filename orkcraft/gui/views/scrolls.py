"""🗑️ Scroll Dump in the GUI: the librarian's state, the tree of the wiki and its sources, and the
page open. The work (ingest, lint, stop, a folder connected) is the worker's
(core/workers/scrolls.py)."""
from __future__ import annotations

from orkcraft.gui import markdown
from orkcraft.gui.views import ActError, text
from orkcraft.realm import shelves, wiki
from orkcraft.sources import lore

REFRESH_S = 30.0              # as the TUI
ITEMS = 2000                  # rows per branch of the tree: a huge source is cut, the window stays quick
RECENT = 5                    # the last changed pages the Command Card shows


def refresh(w) -> None:
    w.refresh()


def _state(w) -> str:
    if w.running:
        return f"{w.running}…"
    if w.last_error:
        return f"⚠ {w.last_error}"
    if w.pending:
        return f"{w.pending.count} to take in" + (" (by itself)" if w.auto else "")
    return "up to date"


def card(w) -> dict:
    """Closed (docs/design/building-views.md): the pages and what waits to be taken in, nothing more."""
    return {"pages": wiki.page_count(w.pages), "pending": w.pending.count, "running": w.running,
            "error": bool(w.last_error)}


def _recent(w) -> list[dict]:
    pages = sorted((n for n in w.pages if wiki.is_page(n.path)), key=lambda n: n.mtime, reverse=True)
    return [{"path": n.path, "title": n.title, "mtime": n.mtime} for n in pages[:RECENT]]


def detail(w) -> dict:
    rel = shelves.rel_to(w.repo_root, w.wiki_root)
    pages = []
    for n in w.pages[:ITEMS]:
        inner = n.path[len(rel) + 1:] if n.path.startswith(rel + "/") else n.path
        depth = max(inner.count("/") - 1, 0) if inner.startswith(wiki.PAGES + "/") else 0
        pages.append({"path": n.path, "title": n.title, "depth": depth, "locked": inner in w.manual})
    fresh = set(w.pending.new) | set(w.pending.changed)
    sources = []
    for b in w.bases:
        notes = b.notes[:ITEMS]
        sources.append({
            "path": b.path, "kind": b.kind, "icon": lore.ICONS.get(b.kind, "📁"), "count": len(b.notes),
            "todo": sum(1 for n in b.notes if n.path in fresh), "error": b.error,
            "items": [{"path": n.path, "title": n.title, "fresh": n.path in fresh, "code": n.kind == "code"}
                      for n in notes],
        })
    count = wiki.page_count(w.pages)
    return {
        "topic": w.topic, "root": rel, "pages_count": count, "state": _state(w),
        "state_plain": _state(w).replace("⚠ ", ""), "running": w.running, "error": bool(w.last_error),
        "pending": w.pending.count, "note": w.last_note, "pages": pages, "sources": sources,
        "recent": _recent(w),
    }


def _read(w, args: dict) -> dict:
    path = text(args, "path", 2000)
    if not path:
        raise ActError("Which page?")
    return {"path": path, "html": markdown.render(w.read(path, page=bool(args.get("page"))))}


def _ingest(w, args: dict) -> bool:
    return w.ingest()


def _lint(w, args: dict) -> bool:
    return w.lint()


def _stop(w, args: dict) -> None:
    w.stop()


def _add_folder(w, args: dict) -> None:
    problem = w.add_folder(text(args, "path", 2000).strip())
    if problem:
        raise ActError(problem)


ACTS = {"read": _read, "ingest": _ingest, "lint": _lint, "stop": _stop, "add_folder": _add_folder}
