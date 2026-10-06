"""The orkspaces' biomes (docs/design/war-map.md §3): the ground each stands on, so the open one is
known at a glance and two lands that touch on the War Map never share a colour.

    biomes.for_new(scroll)   -> "dust"   the biome a new orkspace gets: the first nobody has, else any
                                         but its upper neighbour's
    biomes.settle(scroll)    -> True     once per camp: the old default ("forest" everywhere, the GUI
                                         showed dirt) spread over the orkspaces; True when it changed them

Pure: no face. The colours of each ground are the face's (`gui/static/js/biomes.js`).
"""
from __future__ import annotations

from orkcraft.scroll import BIOMES

ORDER = ("dirt", "forest", "ice", "dust", "void", "lava")     # a new orkspace's biome, in this order
SETTLED = "biomes"          # meta key: the camp's biomes were spread once (the value is the rule's version)
assert set(ORDER) == set(BIOMES)


def pick(taken: list[str], upper: str | None = None) -> str:
    """The first biome not in `taken`; with all taken, the first that is not `upper`'s (the land it will
    touch, by default the last taken)."""
    free = next((b for b in ORDER if b not in taken), None)
    if free:
        return free
    upper = upper if upper is not None else (taken[-1] if taken else "")
    others = [b for b in ORDER if b != upper]
    return others[len(taken) % len(others)]


def for_new(scroll) -> str:
    """The biome a new orkspace gets, below the last one."""
    return pick([o.biome for o in scroll.orkspaces])


def settle(scroll) -> bool:
    """Once per camp: every orkspace still on the old default ("forest", which the GUI drew as dirt) gets a
    biome by `pick`, the first keeping today's look (dirt). Biomes chosen on purpose stay."""
    if scroll.meta.get(SETTLED):
        return False
    chosen = [o.biome for o in scroll.orkspaces if o.biome != "forest"]
    for i, o in enumerate(scroll.orkspaces):
        if o.biome == "forest":
            o.biome = pick(chosen, scroll.orkspaces[i - 1].biome if i else None)
            chosen.append(o.biome)
    scroll.meta[SETTLED] = 1
    return True
