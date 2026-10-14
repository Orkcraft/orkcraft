"""Growth and the biomes in the GUI (docs/design/growth.md, docs/design/war-map.md): the host's clock
settles the buildings' levels, the operator's deeds and mascot stage (realm/growth.py); the snapshot
carries the news the Warchief's line says and the operator's mascot for the head of Settings; the War
Map's lands get their commands (biome, rename, remove).

    g = Growth(host)                 # once: the camp's biomes spread (realm/biomes.py)
    host.commands.update(g.commands())
    g.tick(now)                      # from the host's clock: settles once a minute, or soon after a rating
    g.snapshot()                     # {"news": [...], "you": {...}, "items": {...}}

The items the person places in Camp (realm/items.py, v3-prompts.md §14) settle with the rest, quietly; the page
places, moves and puts them back (`items.place`, `items.move`, `items.remove`), saved in the town file.
"""
from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any, Callable

from orkcraft import scroll as ts
from orkcraft import settings
from orkcraft.core import buildings
from orkcraft.realm import biomes, catalog, growth, intents, items

SETTLE_S = 60.0          # how often the levels, deeds and stage are looked at again
NEWS_SHOWN = 5


class GrowthError(Exception):
    """A command about the War Map's lands the host refuses; its text is shown to the person."""


class Growth:
    def __init__(self, host) -> None:
        self.host = host
        self._at: float | None = None          # when it last settled (None: at the next tick)
        self._news: list[dict] = [asdict(n) for n in growth.news(host.town.repo_root)][-NEWS_SHOWN:]
        # once per camp: the old default spread over its orkspaces, the first on the operator's home ground
        if biomes.settle(host.town.scroll, biomes.home_of(host.town.machine.profile)):
            host.town.save()

    # -- the clock --------------------------------------------------------------------------------------

    def soon(self) -> None:
        """Something was rated or changed: look again at the next tick."""
        self._at = None

    def tick(self, now: float) -> None:
        if self._at is not None and now - self._at < SETTLE_S:
            return
        self._at = now
        self.settle()

    def settle(self) -> None:
        town = self.host.town
        machine = town.machine
        grown_before = json.dumps(machine.growth, sort_keys=True)
        levels_before = [b.level for b in town.scroll.buildings]
        try:
            growth.settle(town.scroll, town.repo_root, machine)
        except Exception as e:                  # growth never stops the clock
            town.toast(f"{type(e).__name__}: {e}", title="Growth", severity="error")
            return
        try:
            got = items.settle(town.scroll, town.repo_root, machine,
                               type_of=lambda b: catalog.type_of(town.spec_of(b.id)).id)
        except Exception as e:                  # neither does an item
            town.toast(f"{type(e).__name__}: {e}", title="Items", severity="error")
            got = []
        if [b.level for b in town.scroll.buildings] != levels_before:
            town.save()
        if got:                                 # it lands in the inventory quietly: no news, no badge
            self.host.on_change()
        if json.dumps(machine.growth, sort_keys=True) != grown_before:
            settings.save(machine)
            self._count(json.loads(grown_before), machine.growth)
        news = [asdict(n) for n in growth.news(town.repo_root)][-NEWS_SHOWN:]
        if news != self._news:                  # what grew, or news told from elsewhere (the Night round)
            self._news = news
            self.host.on_change()

    def _count(self, before: dict, after: dict) -> None:
        """The deeds earned and the stage reached just now, for the usage stats (core/usage.py)."""
        for deed in sorted(set(after.get("deeds") or {}) - set(before.get("deeds") or {})):
            self.host.usage.track("deed_earned", deed=deed)
        if (after.get("stage") or 1) > (before.get("stage") or 1):
            self.host.usage.track("stage_reached", stage=after["stage"])

    # -- what the page sees -----------------------------------------------------------------------------

    def you(self) -> dict[str, Any]:
        """The operator's mascot (its kin, sprite and stage, from the onboarding's role) and their deeds."""
        machine = self.host.town.machine
        profile = machine.profile or {}
        grown = machine.growth or {}
        stage = int(grown.get("stage") or 1)
        done = grown.get("deeds") or {}
        role = intents.role(str(profile.get("role") or ""))
        return {"kin": growth.kin_of(profile), "sprite": role.id, "home": biomes.home_of(profile), "stage": stage,
                "name": growth.stage_name(profile, stage),
                "role": role.title, "next": growth.STAGE_NEXT.get(stage, ""),
                "deeds": [{"id": d.id, "icon": d.icon, "title": d.title, "hint": d.hint, "done": done.get(d.id, "")}
                          for d in growth.DEEDS]}

    def items(self) -> dict[str, Any]:
        """The inventory (what the person may place) and what stands on the open orkspace's grass."""
        town = self.host.town
        here = town.scroll.active_orkspace.id
        return {"inventory": items.inventory(town.scroll, town.repo_root), "notes": items.notes(town.repo_root),
                "placed": [dict(p) for p in town.scroll.items if p["orkspace"] == here]}

    def snapshot(self) -> dict[str, Any]:
        return {"news": list(self._news), "you": self.you(), "items": self.items()}

    # -- the page's commands ----------------------------------------------------------------------------

    def _seen(self, args: dict) -> None:
        growth.seen(self.host.town.repo_root, str(args.get("id", "")))
        self._news = [n for n in self._news if n.get("id") != args.get("id")]
        self.host.on_change()

    def _orkspace(self, args: dict):
        ork = self.host.town.scroll.orkspace(str(args.get("id", "")))
        if ork is None:
            raise GrowthError(f"No orkspace {args.get('id')!r}")
        return ork

    def _biome(self, args: dict) -> None:
        ork = self._orkspace(args)
        biome = str(args.get("biome", ""))
        if biome not in ts.BIOMES:
            raise GrowthError(f"No biome {biome!r}")
        ork.biome = biome
        self.host.town.save()
        self.host.town.checkpoint("orkspace", "", f"biome {biome}", orkspace=ork.id)
        self.host.on_change()

    def _rename(self, args: dict) -> None:
        ork = self._orkspace(args)
        name = str(args.get("name", "")).strip()[:60]
        if not name:
            raise GrowthError("An orkspace needs a name")
        ork.name = name
        self.host.town.save()
        self.host.town.checkpoint("orkspace", "", f"renamed {name}", orkspace=ork.id)
        self.host.on_change()

    def _remove(self, args: dict) -> None:
        """Remove a land. One with buildings standing in it is removed only with `demolish` (the War Map asks
        first, naming them): they come down with it, as Demolish takes one (their specs and history stay)."""
        town = self.host.town
        ork = self._orkspace(args)
        if len(town.scroll.orkspaces) == 1:
            raise GrowthError("the last orkspace cannot be removed")
        standing = ts.standing_in(town.scroll, ork.id)
        if standing and not args.get("demolish"):
            raise GrowthError(f"{ork.name} still holds {len(standing)} building{'s' if len(standing) != 1 else ''}: "
                              + ", ".join(town.title_of(b.id) for b in standing))
        for b in standing:
            buildings.demolish(town, b.id)
        try:
            ts.remove_orkspace(town.scroll, ork.id)
        except ValueError as e:
            raise GrowthError(str(e)) from None
        town.save()
        town.checkpoint("orkspace", "", f"removed {ork.name}" + (f" and {len(standing)} buildings" if standing else ""),
                        orkspace=ork.id)
        if standing:
            self.host.refresh_roster()
        self.host.on_change()

    def _items(self, change: Callable[[], Any]) -> Any:
        try:
            out = change()
        except ValueError as e:
            raise GrowthError(str(e)) from None
        self.host.town.save()
        self.host.on_change()
        return out

    def _place(self, args: dict) -> dict:
        town = self.host.town
        return self._items(lambda: items.place(town.scroll, town.repo_root, str(args.get("item", "")),
                                               town.scroll.active_orkspace.id, args.get("x"), args.get("y")))

    def _move(self, args: dict) -> dict:
        return self._items(lambda: items.move(self.host.town.scroll, str(args.get("id", "")), args.get("x"), args.get("y")))

    def _put_back(self, args: dict) -> None:
        self._items(lambda: items.remove(self.host.town.scroll, str(args.get("id", ""))))

    def _back(self, args: dict) -> str:
        town = self.host.town
        because = str(args.get("because", ""))[:80]
        return self._items(lambda: items.back(town.scroll, town.repo_root, str(args.get("id", "")), because))

    def _seen_items(self, args: dict) -> None:
        items.seen(self.host.town.repo_root)
        self.host.on_change()

    def commands(self) -> dict[str, Callable[[dict], Any]]:
        return {"growth.seen": self._seen, "orkspace.biome": self._biome, "orkspace.rename": self._rename,
                "orkspace.remove": self._remove, "items.place": self._place, "items.move": self._move,
                "items.remove": self._put_back, "items.back": self._back, "items.seen": self._seen_items}
