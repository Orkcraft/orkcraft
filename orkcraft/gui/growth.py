"""Growth and the biomes in the GUI (docs/design/growth.md, docs/design/war-map.md): the host's clock
settles the buildings' levels, the operator's deeds and mascot stage (realm/growth.py); the snapshot
carries the news the Warchief's line says and the operator's mascot for the head of Settings; the War
Map's lands get their commands (biome, rename, remove).

    g = Growth(host)                 # once: the camp's biomes spread (realm/biomes.py)
    host.commands.update(g.commands())
    g.tick(now)                      # from the host's clock: settles once a minute, or soon after a rating
    g.snapshot()                     # {"news": [...], "you": {...}}
"""
from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any, Callable

from orkcraft import scroll as ts
from orkcraft import settings
from orkcraft.realm import biomes, growth, intents

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
            fresh = growth.settle(town.scroll, town.repo_root, machine)
        except Exception as e:                  # growth never stops the clock
            town.toast(f"{type(e).__name__}: {e}", title="Growth", severity="error")
            return
        if [b.level for b in town.scroll.buildings] != levels_before:
            town.save()
        if json.dumps(machine.growth, sort_keys=True) != grown_before:
            settings.save(machine)
        if fresh:
            self._news = [asdict(n) for n in growth.news(town.repo_root)][-NEWS_SHOWN:]
            self.host.on_change()

    # -- what the page sees -----------------------------------------------------------------------------

    def you(self) -> dict[str, Any]:
        """The operator's mascot (its kin and stage, from the onboarding's role) and their deeds."""
        machine = self.host.town.machine
        profile = machine.profile or {}
        grown = machine.growth or {}
        stage = int(grown.get("stage") or 1)
        done = grown.get("deeds") or {}
        role = intents.role(str(profile.get("role") or ""))
        return {"kin": growth.kin_of(profile), "home": biomes.home_of(profile), "stage": stage, "name": growth.stage_name(profile, stage),
                "role": role.title, "next": growth.STAGE_NEXT.get(stage, ""),
                "deeds": [{"id": d.id, "icon": d.icon, "title": d.title, "hint": d.hint, "done": done.get(d.id, "")}
                          for d in growth.DEEDS]}

    def snapshot(self) -> dict[str, Any]:
        return {"news": list(self._news), "you": self.you()}

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
        self.host.on_change()

    def _rename(self, args: dict) -> None:
        ork = self._orkspace(args)
        name = str(args.get("name", "")).strip()[:60]
        if not name:
            raise GrowthError("An orkspace needs a name")
        ork.name = name
        self.host.town.save()
        self.host.on_change()

    def _remove(self, args: dict) -> None:
        try:
            ts.remove_orkspace(self.host.town.scroll, self._orkspace(args).id)
        except ValueError as e:
            raise GrowthError(str(e)) from None
        self.host.town.save()
        self.host.on_change()

    def commands(self) -> dict[str, Callable[[dict], Any]]:
        return {"growth.seen": self._seen, "orkspace.biome": self._biome, "orkspace.rename": self._rename,
                "orkspace.remove": self._remove}
