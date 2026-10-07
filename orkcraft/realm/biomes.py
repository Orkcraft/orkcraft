"""The orkspaces' biomes (docs/design/war-map.md §3): the ground each stands on, so the open one is
known at a glance and two lands that touch on the War Map never share a colour.

    biomes.for_new(scroll)   -> "dust"   the biome a new orkspace gets: the first nobody has, else any
                                         but its upper neighbour's
    biomes.settle(scroll, home="ice")    once per camp: the old default ("forest" everywhere, the GUI showed
                                         dirt) spread over the orkspaces, the first on the operator's home;
                                         True when it changed them
    biomes.home_of(profile)  -> "ice"    the home of the operator's kin (the onboarding's role: a lich's ice)

Pure: no face. The colours of each ground are the face's (`gui/static/js/biomes.js`).
"""
from __future__ import annotations

from orkcraft.scroll import BIOMES

ORDER = ("dirt", "forest", "ice", "dust", "void", "lava", "meadow")     # a new orkspace's biome, in this order
SETTLED = "biomes"          # meta key: the camp's biomes were spread once (the value is the rule's version)
assert set(ORDER) == set(BIOMES)

# Each kin's home ground (docs/design/war-map.md §3.3): the operator's first orkspace stands on it, and their
# mascot stands on it in Settings. The orks keep the camp's dirt; the knights got a field of their own.
HOMES = {"orc": "dirt", "knight": "meadow", "elf": "forest", "lich": "ice", "goblin": "dust", "skeleton": "void",
         "gnome": "lava"}


def home_of(profile: dict | None) -> str:
    """The home biome of the operator's kin, from the role the onboarding asked; dirt for none."""
    from orkcraft.realm import intents
    role_id = str((profile or {}).get("role") or "")
    return HOMES.get(intents.role(role_id).mascot, "dirt") if role_id else "dirt"


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


def settle(scroll, home: str = "dirt") -> bool:
    """Once per camp: every orkspace still on the old default ("forest", which the GUI drew as dirt) gets a
    biome — the first one the operator's `home` (a new camp opens on their kin's ground), the rest by
    `pick`. Biomes chosen on purpose stay."""
    if scroll.meta.get(SETTLED):
        return False
    home = home if home in ORDER else "dirt"
    chosen = [o.biome for o in scroll.orkspaces if o.biome != "forest"]
    for i, o in enumerate(scroll.orkspaces):
        if o.biome == "forest":
            o.biome = home if i == 0 and home not in chosen else pick(chosen, scroll.orkspaces[i - 1].biome if i else None)
            chosen.append(o.biome)
    scroll.meta[SETTLED] = 1
    return True
