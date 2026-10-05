"""The Textual view each building names (`Building.view`, realm/buildings.py)."""
from __future__ import annotations

from textual.widget import Widget

from orkcraft.realm.buildings import CUSTOM, TOWN_HALL, Building


def make_view(building: Building) -> Widget:
    """A fresh view for `building`: a built-in's own screen, or a custom building drawn from its spec."""
    if building.view == CUSTOM:
        from orkcraft.screens.typed import view_for
        return view_for(building.spec or {"id": building.id, "title": building.title})
    from orkcraft.screens.loot_view import LootView
    from orkcraft.screens.systems_view import SystemsView
    from orkcraft.screens.town_hall import TownHallView
    views = {"loot": lambda: LootView(id="loot-view"), TOWN_HALL: lambda: TownHallView(id="town-hall-view"),
             "systems": lambda: SystemsView(id="systems-view")}
    return views[building.view]()
