"""🌾 Task Fields in the GUI: one board, three parts — the orks' tasks as lanes of cards (a kanban), the
person's own to-dos (a checklist) and the notes (ideas, questions). Every act is the worker's
(core/workers/fields.py): it changes the board file and sends what changed down the roads."""
from __future__ import annotations

from orkcraft.core.workers.fields import card_text
from orkcraft.gui.views import ActError, text
from orkcraft.realm import catalog, tasklist

REFRESH_S = 10.0              # as the TUI: a hand edit of the board file shows within this
COLORS = {"🟨": "yellow", "🟩": "green", "🟦": "blue", "🟥": "red", "🟪": "purple"}
TOP = 2                       # titles a part shows on the closed card


def refresh(w) -> None:
    w.refresh()


def _short(title: str) -> str:
    return tasklist.plain(title)[:60]


def card(w) -> dict:
    """Closed (docs/design/building-views.md): a counter per status lane with its top cards, then the
    note folders with theirs (`notes`), each `new` when it holds unseen cards; in notes mode only the
    folders (`mode` says which). In board mode also the person's open to-dos (`todos`) and the latest notes (`ideas`)."""
    if w.error:
        return {"error": w.error[:60], "mode": w.mode, "lanes": [], "notes": [], "todos": None, "ideas": None}
    seen = w.seen()
    lanes, notes = [], []
    for ln in w.visible_lanes():
        rows = [c for c in w.cards if c.column == ln.id]
        count = {"id": ln.id, "label": ln.label, "count": len(rows), "new": any(c.id not in seen for c in rows),
                 "top": [_short(c.title) for c in rows[:TOP]] if ln.id != "done" else []}
        (notes if ln.kind == tasklist.NOTE else lanes).append(count)
    if w.mode == "notes":
        lanes, notes = notes, []
    todos = ideas = None
    if w.shows_todos:
        mine = w.todos
        open_ = [c for c in mine if not c.checked]
        todos = {"open": len(open_), "count": len(mine), "top": [_short(c.title) for c in open_[:TOP + 1]]}
        latest = w.notes[::-1]
        ideas = {"count": len(latest), "new": any(c.id not in seen for c in latest),
                 "top": [_short(c.title) for c in latest[:TOP + 1]]}
    return {"error": "", "mode": w.mode, "lanes": lanes, "notes": notes, "todos": todos, "ideas": ideas}


def _lore(w, c) -> dict:
    """What the board keeps beside the card: personal, its context's pages (stale when one changed), its plan."""
    pages = w.lore.context(c.id)
    return {"private": w.private(c.id), "pages": [{"path": p.path, "title": p.title} for p in pages],
            "stale": bool(pages) and w.lore.stale(c.id, w.repo_root), "plan": w.lore.plan(c.id),
            "planning": c.id in w.planning}


def detail(w) -> dict:
    seen = w.seen()
    lanes = []
    for ln in w.visible_lanes():
        cards = [{"id": c.id, "title": tasklist.plain(c.title), "color": COLORS.get(c.color, ""),
                  "body": c.body, "kind": c.kind, "new": c.id not in seen, **_lore(w, c)}
                 for c in w.cards if c.column == ln.id]
        lanes.append({"id": ln.id, "label": ln.label, "kind": ln.kind, "cards": cards})
    todos = None
    if w.shows_todos:
        lane = w.todo_lane()
        todos = {"id": lane.id, "label": lane.label,
                 "cards": [{"id": c.id, "title": tasklist.plain(c.title), "color": COLORS.get(c.color, ""),
                            "body": c.body, "kind": c.kind, "done": c.checked, "new": c.id not in seen, **_lore(w, c)}
                           for c in w.todos]}
    return {"mode": w.mode, "error": w.error, "lanes": lanes, "todos": todos, "plan_ok": w.lore.plan_ok,
            "wiki": _wiki_of(w) is not None}


def _card(w, args: dict) -> tasklist.Task:
    card = w.card(text(args, "card", 200))
    if card is None:
        raise ActError("That card is gone from the board")
    return card


def _title(args: dict) -> str:
    title = " ".join(text(args, "title", 500).split())
    if not title:
        raise ActError("A card needs a title")
    return title


def _add(w, args: dict) -> str:
    """A card written as one `text` (its title a few words a light model picks; "" back while it does), or
    a `title` with a `body` (a to-do of the person's own)."""
    lane = text(args, "lane", 200) or "todo"
    written = text(args, "text", 20_000).strip()
    if written:
        card = w.write(written, lane, private=bool(args.get("private")))
    elif "text" in args:
        raise ActError("A card needs some text")
    else:
        card = w.add(_title(args), lane, text(args, "body", 20_000).strip())
        if card is not None and args.get("private"):
            w.set_private(card.id, True)
    return card.id if card is not None else ""


def _move(w, args: dict) -> bool:
    return w.move(_card(w, args).id, text(args, "lane", 200))


def _edit(w, args: dict) -> str:
    """The card's id after the edit (a card's id follows its title), "" when it was not kept."""
    card = _card(w, args)
    if "text" in args:            # one text: the card's text (its title kept); a title-only card's short line renames it
        written = text(args, "text", 20_000).strip()
        if not written:
            raise ActError("A card needs some text")
        name = tasklist.plain(card.title).strip()
        if " ".join(written.split()) == name:
            body = ""
        elif card.body.strip() or tasklist.needs_title(written):
            body = written
        else:
            name, body = " ".join(written.split()), ""
    else:
        name, body = _title(args), text(args, "body", 20_000).rstrip()
    title = f"{card.color} {name}" if card.color else name
    if not w.edit(card.id, title, body):
        return ""
    return next((c.id for c in w.cards if c.column == card.column and c.title == title), "")


def _check(w, args: dict) -> bool:
    done = args.get("done")
    return w.check(_card(w, args).id, None if done is None else bool(done))


def _mine(w, args: dict) -> bool:
    return w.to_mine(_card(w, args).id)


def _color(w, args: dict) -> bool:
    return w.color(_card(w, args).id)


def _flip(w, args: dict) -> str:
    return w.flip(_card(w, args).id)


def _send(w, args: dict) -> bool:
    card = _card(w, args)
    sent = w.send(card.id)
    w.toast(f"{tasklist.plain(card.title)[:60]}: " + ("sent down the roads" if sent else "no road takes tasks.sent from here"),
            severity="information" if sent else "warning")
    return sent


def _wiki_of(w):
    """The Wiki a note of the board goes to (docs/design/wiki-librarian.md §4): one whose topic is team
    or general first, else the first; None when the town has none."""
    found = []
    for bid, spec in w.town.custom_specs.items():
        if catalog.migrate(spec).get("type") == "scrolls":
            topic = str((spec.get("config") or {}).get("topic") or "general")
            found.append((topic not in ("team", "general"), bid))
    return w.town.worker(min(found)[1]) if found else None


def _to_wiki(w, args: dict) -> str:
    """The card kept as a Quick note in the Wiki, with what the Wiki suggests for it: the note's path."""
    card = _card(w, args)
    if w.private(card.id):
        raise ActError("A personal card never reaches a model: it stays on the board.")
    librarian = _wiki_of(w)
    if librarian is None:
        raise ActError("No Wiki in the town yet.")
    body = card_text(card)
    hint = librarian.suggest(body)
    try:
        path = librarian.note(body, hint.section, hint.tags, [x["path"] for x in hint.links], "task board",
                              meeting=hint.meeting, people=hint.people)
    except ValueError as e:
        raise ActError(str(e)) from None
    w.toast(f"{tasklist.plain(card.title)[:60]}: kept in the Wiki ({path})")
    return path


def _remove(w, args: dict) -> None:
    w.remove(_card(w, args).id)


def _add_lane(w, args: dict) -> str:
    """A new folder of notes (a lane of its own); its id, "" when it was not made (the worker said why)."""
    name = " ".join(text(args, "name", 200).split())
    if not name:
        raise ActError("A folder of notes needs a name")
    return w.add_lane(name)


def _seen(w, args: dict) -> None:
    if w.cards:
        w.mark_seen()
        w.changed()


def _private(w, args: dict) -> bool:
    """Mark a card personal (`on`), or not; without `on` it flips. What it is now."""
    on = args.get("on")
    return w.set_private(_card(w, args).id, None if on is None else bool(on))


def _context(w, args: dict) -> int:
    """Ask the wikis again for the card's context: how many pages it found."""
    return w.find_context(_card(w, args).id)


def _plan_preview(w, args: dict) -> dict:
    return w.plan_preview(_card(w, args).id)


def _plan(w, args: dict) -> bool:
    """Ask for the to-do's plan with the `pages` of its context the person kept (all when not given);
    `trust`: don't show what leaves before the next one."""
    card = _card(w, args)
    pages = args.get("pages")
    if pages is not None and not (isinstance(pages, list) and all(isinstance(p, str) for p in pages)):
        raise ActError("pages must be a list of paths")
    preview = w.plan_preview(card.id)
    if not preview.get("allowed"):
        raise ActError(preview.get("why") or "No plan for this card")
    return w.plan(card.id, pages, trust=bool(args.get("trust")))


def _plan_steps(w, args: dict) -> int:
    return w.plan_to_todos(_card(w, args).id)


ACTS = {"add": _add, "move": _move, "edit": _edit, "color": _color, "flip": _flip, "send": _send,
        "remove": _remove, "seen": _seen, "add_lane": _add_lane, "check": _check, "mine": _mine,
        "private": _private, "context": _context, "plan_preview": _plan_preview, "plan": _plan,
        "plan_steps": _plan_steps, "to_wiki": _to_wiki}
