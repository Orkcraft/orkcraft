"""🌾 Task Fields in the GUI: the board as lanes of cards. Every act is the worker's
(core/workers/fields.py): it changes the board file and sends what changed down the roads."""
from __future__ import annotations

from orkcraft.gui.views import ActError, text
from orkcraft.realm import tasklist

REFRESH_S = 10.0              # as the TUI: a hand edit of the board file shows within this
COLORS = {"🟨": "yellow", "🟩": "green", "🟦": "blue", "🟥": "red", "🟪": "purple"}


def refresh(w) -> None:
    w.refresh()


def detail(w) -> dict:
    seen = w.seen()
    lanes = []
    for ln in w.visible_lanes():
        cards = [{"id": c.id, "title": tasklist.plain(c.title), "color": COLORS.get(c.color, ""),
                  "body": c.body, "kind": c.kind, "new": c.id not in seen}
                 for c in w.cards if c.column == ln.id]
        lanes.append({"id": ln.id, "label": ln.label, "kind": ln.kind, "cards": cards})
    return {"mode": w.mode, "error": w.error, "lanes": lanes}


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
    lane = text(args, "lane", 200) or "todo"
    card = w.add(_title(args), lane, text(args, "body", 20_000).strip())
    return card.id if card is not None else ""


def _move(w, args: dict) -> bool:
    return w.move(_card(w, args).id, text(args, "lane", 200))


def _edit(w, args: dict) -> str:
    """The card's id after the edit (a card's id follows its title), "" when it was not kept."""
    card = _card(w, args)
    colour = card.color
    title = f"{card.color} {_title(args)}" if colour else _title(args)
    if not w.edit(card.id, title, text(args, "body", 20_000).rstrip()):
        return ""
    return next((c.id for c in w.cards if c.column == card.column and c.title == title), "")


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


def _remove(w, args: dict) -> None:
    w.remove(_card(w, args).id)


def _seen(w, args: dict) -> None:
    if w.cards:
        w.mark_seen()
        w.changed()


ACTS = {"add": _add, "move": _move, "edit": _edit, "color": _color, "flip": _flip, "send": _send,
        "remove": _remove, "seen": _seen}
