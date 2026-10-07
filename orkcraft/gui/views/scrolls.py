"""🗑️ Scroll Dump in the GUI: the librarian's state, the tree of the wiki and its sources, and the
page open. The work (ingest, lint, stop, a folder connected) is the worker's
(core/workers/scrolls.py)."""
from __future__ import annotations

import time

from orkcraft.gui import markdown
from orkcraft.gui.views import ActError, text
from orkcraft.realm import quicknote, shelves, wiki
from orkcraft.sources import lore

REFRESH_S = 30.0              # as the TUI
ITEMS = 2000                  # rows per branch of the tree: a huge source is cut, the window stays quick
RECENT = 5                    # the last changed pages the Command Card shows
LENT_SHOWN_S = 600.0          # how long the card says which notes a task was given


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
    """Closed (docs/design/building-views.md): the pages and what waits to be taken in; the page changed
    last (`last`: its title and when) for the foot."""
    recent = _recent(w)[:1]
    meetings = w.agenda_cache["meetings"]
    nxt = next((m for m in meetings if any(not i["done"] for i in m["items"])), None)
    return {"pages": wiki.page_count(w.pages), "pending": w.pending.count, "running": w.running,
            "error": bool(w.last_error), "lent": _lent(w),
            "quality": w.quality_total,
            "discuss": {"title": nxt["title"][:60], "when": nxt["when"],
                        "count": sum(1 for i in nxt["items"] if not i["done"])} if nxt else None,
            "last": {"title": recent[0]["title"][:60], "mtime": recent[0]["mtime"]} if recent else None}


def _lent(w) -> dict | None:
    """The task it gave notes to lately: its title and the pages named for it."""
    lent = w.lent
    if not lent or time.time() - lent.get("at", 0) > LENT_SHOWN_S:
        return None
    return {"task": lent["task"], "pages": lent["pages"]}


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
        "recent": _recent(w), "lent": _lent(w), "inbox": w.inbox,
        "sections": wiki.sections(w.wiki_root, w.topic), "agenda": w.agenda_view(),
        "quality": w.quality_view(),
    }


def _read(w, args: dict) -> dict:
    path = text(args, "path", 2000)
    if not path:
        raise ActError("Which page?")
    body, meta = _front(w.read(path, page=bool(args.get("page"))))
    return {"path": path, "html": markdown.render(body), "meta": meta}


def _front(text_: str) -> tuple[str, str]:
    """A page's front matter (`---` … `---` on top) taken off its body, as one line `kind: notes · …`: read
    as Markdown it was a heading of its own."""
    lines = text_.split("\n")
    if not lines or lines[0].strip() != "---":
        return text_, ""
    end = next((i for i, ln in enumerate(lines[1:20], 1) if ln.strip() == "---"), 0)
    if not end:
        return text_, ""
    meta = " · ".join(ln.strip() for ln in lines[1:end] if ln.strip())
    return "\n".join(lines[end + 1:]).lstrip("\n"), meta[:400]


def _ingest(w, args: dict) -> bool:
    return w.ingest()


def _lint(w, args: dict) -> bool:
    return w.check_now()


def _fix(w, args: dict) -> bool:
    return w.fix()


def _check(w, args: dict) -> str:
    """How often the quality check runs: weekly, daily, ingest (after each take-in) or off."""
    value = text(args, "check", 20).strip().lower()
    if value not in ("weekly", "daily", "ingest", "off"):
        raise ActError("weekly, daily, ingest or off")
    w.save_config({"check": value})
    w.changed()
    return value


def _stop(w, args: dict) -> None:
    w.stop()


def _add_folder(w, args: dict) -> None:
    problem = w.add_folder(text(args, "path", 2000).strip())
    if problem:
        raise ActError(problem)


def _suggest(w, args: dict) -> dict:
    """What a Quick note should get here, as it is typed: section, tags, links (rules, no model)."""
    return w.suggest(text(args, "text", quicknote.MAX_CHARS)).as_dict()


def _strings(args: dict, key: str, most: int, chars: int = 200) -> list[str]:
    got = args.get(key) or []
    return [str(x)[:chars] for x in got[:most] if str(x).strip()] if isinstance(got, list) else []


def _note(w, args: dict) -> str:
    """Keep a Quick note: its path."""
    body = text(args, "text", quicknote.MAX_CHARS)
    if not body.strip():
        raise ActError("Write the note first.")
    try:
        meeting = args.get("meeting") if isinstance(args.get("meeting"), dict) else None
        if meeting:
            meeting = {k: str(meeting.get(k) or "")[:200] for k in ("id", "title", "when")}
        return w.note(body, text(args, "section", 80).strip(), _strings(args, "tags", 8, 60),
                      _strings(args, "links", 6, 400), text(args, "source", 20) or "quick note",
                      args.get("take_in", True) is not False, meeting, _strings(args, "people", 8, 80))
    except ValueError as e:
        raise ActError(str(e)) from None


ACTS = {"read": _read, "ingest": _ingest, "lint": _lint, "stop": _stop, "add_folder": _add_folder,
        "suggest": _suggest, "note": _note, "fix": _fix, "check": _check}
