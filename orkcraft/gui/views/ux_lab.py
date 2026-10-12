"""⚗️ The UX bench in the GUI (docs/design/improve-buildings.md §6): its card says whose look it works on; its window
is its settings (which building, which image tool) over the gallery of that building's pictures. The page lays the
gallery out (js/buildings/ux_lab.js): it knows the Build icons and the sprites; this says which of them are drawn."""
from __future__ import annotations

import base64

from orkcraft.design import tokens, ui
from orkcraft.gui.views import ActError, text
from orkcraft.realm import biomes, card_docs, catalog, harnesses, motion, painter

SPRITES = {"loot_vault": "loot"}           # a type drawn under another's name (js/icons.js spriteName)
FLAT = ("dirt", "forest")                  # the biomes that wear the plain header.png (js/icons.js DRAWN_FOR)


def drawn_biomes(type_id: str) -> list[str]:
    """The biomes the type's house is drawn for, in the map's order: none when it has no house of its own."""
    folder = tokens.SYSTEM / "sprites" / "buildings" / SPRITES.get(type_id, type_id)
    if not (folder / "header.png").is_file():
        return []
    return [b for b in biomes.ORDER if b in FLAT[:1] or (b not in FLAT and (folder / f"header-{b}.png").is_file())]


def tools(w) -> list[dict]:
    """The AI tools it may paint with: those the machine has on, its own first even when it is off."""
    machine = getattr(w.town, "machine", None)
    on = [t for t, c in (machine.tools.items() if machine is not None else ()) if c.enabled and harnesses.get(t)]
    ids = [w.image_tool] + [t for t in on if t != w.image_tool]
    return [{"id": t, "title": harnesses.need(t).title if harnesses.get(t) else t, "on": t in on} for t in ids]


def card(w) -> dict:
    tid = w.target
    return {"target": tid, "title": catalog.TYPES[tid].title if tid else "", "pictures": 2 + len(drawn_biomes(tid)) if tid else 0}


def detail(w) -> dict:
    tid = w.target
    out = {"target": tid, "title": catalog.TYPES[tid].title if tid else "", "biomes": drawn_biomes(tid) if tid else [],
           "image_tool": w.image_tool, "tools": tools(w), "painting": dict(w.painting),
           "own": {p: int(w.own(p).stat().st_mtime) for p in w.owned()}, "sprite": SPRITES.get(tid, tid)}
    m = motion.MOTIONS.get(out["sprite"]) if tid else None
    if m:                                       # a house that moves at work: its two layers and how (docs/design/building-motion.md)
        still, part = motion.paths(out["sprite"])
        out["motion"] = {**motion.as_data(m), "still": still, "part": part,
                         "brief": {still: m.still, part: m.part}}
    if tid:
        bid = w.first_of_type()
        contract = ui.contract(tid)
        out["window"] = {"panes": sorted(contract.panes) if hasattr(contract, "panes") else [],
                         "doc": ui.current(w.town.scroll.building(bid), tid) if bid else ui.default(tid),
                         "standing": bool(bid), "draft": w.layout}
        out["cards"] = {"doc": w.card_now(), "draft": w.card, "own": card_docs.load(tid) is not None, "building": bid}
    return out


def _pick(w, args: dict) -> bool:
    if not w.pick(text(args, "type", 60)):
        raise ActError("No such building to work on")
    return True


def _tool(w, args: dict) -> bool:
    tool = text(args, "tool", 60)
    if tool and not harnesses.get(tool):
        raise ActError("No such AI tool")
    return w.set_tool(tool)


def _path(args: dict) -> str:
    path = text(args, "path", 200)
    if not painter.kind_of(path) or not ((tokens.SYSTEM / path).is_file() or motion.of_path(path)):
        raise ActError("No such picture")
    return path


def _region(args: dict) -> dict | None:
    r = args.get("region")
    if not isinstance(r, dict):
        return None
    try:
        box = {k: min(max(float(r[k]), 0.0), 1.0) for k in ("x", "y", "w", "h")}
    except (KeyError, TypeError, ValueError):
        raise ActError("A region is x, y, w, h as shares of the picture") from None
    return box if box["w"] > 0.01 and box["h"] > 0.01 else None


def _paint(w, args: dict) -> bool:
    try:
        w.paint(_path(args), text(args, "words", 2000), _region(args))
    except painter.PaintError as e:
        raise ActError(str(e)) from None
    return True


def _draft(w, args: dict) -> dict:
    """What the dialog shows on the left: the draft (a data URL), the shipped one after Reset, or none yet."""
    path = _path(args)
    got = w.draft(path)
    shown = got if isinstance(got, bytes) else w.shipped(path) if got == "shipped" else b""
    src = "data:image/png;base64," + base64.b64encode(shown).decode() if shown else ""
    return {"src": src, "shipped": got == "shipped", "painting": path in w.painting and w.painting[path] == "",
            "error": w.painting.get(path) or ""}


def _reset(w, args: dict) -> bool:
    w.reset(_path(args))
    return True


def _drop(w, args: dict) -> bool:
    w.drop(_path(args))
    return True


def _apply(w, args: dict) -> bool:
    if not w.apply(_path(args)):
        raise ActError("Nothing to apply: paint it first")
    return True


def _layout(w, args: dict) -> bool:
    request = text(args, "words", 1000).strip()
    if len(request) < 3:
        raise ActError("Say what should change in the window")
    try:
        w.lay_out(request)
    except painter.PaintError as e:
        raise ActError(str(e)) from None
    return True


def _layout_apply(w, args: dict) -> bool:
    problems = w.apply_layout()
    if problems:
        raise ActError("; ".join(problems[:3]))
    return True


def _layout_reset(w, args: dict) -> bool:
    w.layout = None
    w.changed()
    return True


def _card(w, args: dict) -> bool:
    words = text(args, "words", 1000).strip()
    if len(words) < 3:
        raise ActError("Say what should change in the card")
    try:
        w.card_ask(words, text(args, "size", 2), text(args, "part", 10))
    except painter.PaintError as e:
        raise ActError(str(e)) from None
    return True


def _card_apply(w, args: dict) -> bool:
    wrong = w.card_apply()
    if wrong:
        raise ActError("; ".join(wrong[:3]))
    return True


def _card_reset(w, args: dict) -> bool:
    w.card_reset()
    return True


def _card_drop(w, args: dict) -> bool:
    w.card = None
    w.changed()
    return True


ACTS = {"card": _card, "card_apply": _card_apply, "card_reset": _card_reset, "card_drop": _card_drop, "pick": _pick, "tool": _tool, "paint": _paint, "draft": _draft, "reset": _reset, "drop": _drop, "apply": _apply,
        "layout": _layout, "layout_apply": _layout_apply, "layout_reset": _layout_reset}
