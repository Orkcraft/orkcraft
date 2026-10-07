"""🚏 Signpost in the GUI: a counter per road out, each in its road's colour (the town paints the start
of the road the same); the rules as its keeper wrote them, a test of where a text would go, and the
carts that came by. The routing is the worker's (core/workers/signpost.py)."""
from __future__ import annotations

from orkcraft.gui.views import ActError, text
from orkcraft.realm import modes, signpost

# The design system's marks (design-system/tokens.json, `--mark-*`), one per road out, in this order.
MARKS = ("blue", "green", "purple", "yellow", "red")


def _roads(w) -> list[dict]:
    """The roads out with their colours: a road keeps its colour while the others come and go only as
    far as their order allows (by the town-wide key, so the same road gets the same colour on every page)."""
    out = sorted(w.roads_out(), key=lambda r: r["key"])
    for i, r in enumerate(out):
        r["color"] = MARKS[i % len(MARKS)]
    return out


def card(w) -> dict:
    """Closed: how many carts it routed, a counter per road out in its colour, the last cart; `tints` tells
    the town which road starts in which."""
    roads = _roads(w)
    return {"roads": [{"key": r["key"], "label": r["label"], "count": r["count"], "color": r["color"],
                       "unmatched": r["unmatched"]} for r in roads],
            "tints": {r["key"]: r["color"] for r in roads},
            "rules": len(w.rules_text), "total": sum(w.counts.values()),
            "last": ({"title": w.history[0].get("title", ""), "route": w.history[0].get("route", ""),
                      "at": w.history[0].get("at", "")} if w.history else None)}


def detail(w) -> dict:
    rules, problems = signpost.rules_of(w.rules_text)
    roads = _roads(w)
    colour = {}
    for r in roads:
        for route in r["routes"]:
            colour.setdefault(route, r["color"])
        if r["unmatched"]:
            colour.setdefault("", r["color"])
    history = [{"at": h.get("at", ""), "route": h.get("route", ""), "source": h.get("source", ""),
                "source_title": modes.plain(w.town.title_of(h["source"])) if h.get("source") else "",
                "event": h.get("event", ""), "title": h.get("title", ""), "value": h.get("value", "")}
               for h in w.history]
    return {"rules": w.rules_text, "problems": problems, "routes": signpost.routes(w.rules_text),
            "roads": roads, "colors": colour, "history": history, "counts": w.counts}


def _test(w, args: dict) -> dict:
    value = text(args, "text", 100_000)
    if not value.strip():
        raise ActError("Paste a text to test")
    return w.test(value, text(args, "title", 200))


ACTS = {"test": _test}
