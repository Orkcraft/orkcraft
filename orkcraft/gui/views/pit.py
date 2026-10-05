"""🕳️ The Pit in the GUI: its card is the drop zone; its window the history of what was dropped and,
for each drop, where its carts went and what the chain cost. The sorting and sending are the
worker's (core/workers/pit.py)."""
from __future__ import annotations

import base64
import binascii

from orkcraft.core.workers.pit import item_id
from orkcraft.gui.views import ActError, text
from orkcraft.realm import modes

ITEMS = 100                    # drops the window lists
FILE_LIMIT = 5 * 1024 * 1024   # a file dropped on the page comes over the socket (8 MB a frame, base64)


def card(w) -> dict:
    """Closed: only the drop zone (the page says "drag & drop"); `n` lets it say there is history."""
    return {"n": len(w.items)}


def detail(w) -> dict:
    town = w.town
    items = []
    for it in w.items[:ITEMS]:
        chain = w.chains.get(item_id(it)) or {}
        stops = [{**s, "building_title": town.title_of(s.get("building", "")),
                  "building_title_plain": modes.text(town.title_of(s.get("building", "")), modes.OFFICE)}
                 for s in chain.get("stops") or []]
        items.append({
            "id": item_id(it), "at": it.at, "kind": it.kind, "title": it.title, "value": it.value,
            "file": it.is_file or it.kind == "text", "link": it.kind == "link", "copied": it.copied,
            "cost": round(float(chain.get("cost") or 0.0), 4), "stops": stops, "followed": bool(chain),
        })
    return {"items": items, "count": len(w.items), "file_limit": FILE_LIMIT}


def _drop(w, args: dict) -> int:
    value = text(args, "text", 200_000)
    if not value.strip():
        raise ActError("Nothing to drop")
    return w.drop(value)


def _drop_file(w, args: dict) -> int:
    name = text(args, "name", 300).strip()
    raw = text(args, "data", FILE_LIMIT * 4 // 3 + 8)
    try:
        data = base64.b64decode(raw, validate=True)
    except (binascii.Error, ValueError):
        raise ActError("That file did not come through") from None
    if not name:
        raise ActError("A dropped file needs its name")
    if len(data) > FILE_LIMIT:
        raise ActError(f"{name}: larger than {FILE_LIMIT // (1024 * 1024)} MB — put it in the project and drop its path")
    return w.drop_file(name, data)


def _paste(w, args: dict) -> int:
    return w.paste()


ACTS = {"drop": _drop, "drop_file": _drop_file, "paste": _paste}
