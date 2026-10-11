"""⚗️ The UX bench in the GUI (docs/design/improve-buildings.md §6): its card says whose look it works on; its window
is its settings (which building, which image tool) over the gallery of that building's pictures. The page lays the
gallery out (js/buildings/ux_lab.js): it knows the Build icons and the sprites; this says which of them are drawn."""
from __future__ import annotations

from orkcraft.design import tokens
from orkcraft.gui.views import ActError, text
from orkcraft.realm import biomes, catalog, harnesses

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
    return {"target": tid, "title": catalog.TYPES[tid].title if tid else "", "biomes": drawn_biomes(tid) if tid else [],
            "image_tool": w.image_tool, "tools": tools(w)}


def _pick(w, args: dict) -> bool:
    if not w.pick(text(args, "type", 60)):
        raise ActError("No such building to work on")
    return True


def _tool(w, args: dict) -> bool:
    tool = text(args, "tool", 60)
    if tool and not harnesses.get(tool):
        raise ActError("No such AI tool")
    return w.set_tool(tool)


ACTS = {"pick": _pick, "tool": _tool}
