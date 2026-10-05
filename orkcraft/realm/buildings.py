"""Buildings registry: every window type orkcraft can raise, with its resident orc.

Core presets come from the spec; "migrated" buildings are the mg-tui screens that
are not part of the core. A building is *built* when its window is shown and
*demolished* when it is hidden — its slot (and pin) survive in the Town Scroll.
"""
from __future__ import annotations

from dataclasses import dataclass, field

CORE = "core"
MIGRATED = "migrated"
CUSTOM = "custom"          # the view of a custom building: drawn from its spec


@dataclass(frozen=True)
class Building:
    id: str
    title: str
    icon: str
    category: str
    orc: str          # resident orc name
    role: str         # what the resident orc looks after
    view: str         # which view a face opens for it: the id of a built-in, or CUSTOM (drawn from `spec`)
    built_by_default: bool = True
    spec: dict | None = field(default=None, compare=False, hash=False)   # a custom building's spec

    @property
    def label(self) -> str:
        return f"{self.icon} {self.title}"


def registry() -> list[Building]:
    """In number order: key N / alt+N focuses building N (1–9). Plain data: each face draws the view
    a building names (the TUI in `tui/views.py`)."""
    return [
        Building("loot", "Artifacts", "📦", CORE, "Quartermaster", "wiki and generated artifacts (./loot/)", "loot"),
        # T1105: the hall holds the live sessions (Chat of old) and the quotas (Limits of old).
        Building(TOWN_HALL, "Town Hall", "🏰", CORE, "Chieftain", "builds, audits, sessions and quotas", TOWN_HALL),
        Building("systems", "Systems", "🏛️", CORE, "Engineer", "multi-agent pipelines", "systems",
                 built_by_default=False),
    ]


TOWN_HALL = "town_hall"
# Built-in buildings that wear a catalog type: their hut's size and quick actions come from it.
BUILTIN_SPECS: dict[str, dict] = {TOWN_HALL: {"id": TOWN_HALL, "type": "town_hall"}}



def presets(buildings: list[Building]) -> dict[str, dict[str, str]]:
    """The registry as plain data for the Town Scroll (`orkcraft.scroll`)."""
    return {b.id: {"title": b.title, "icon": b.icon, "orc": b.orc, "role": b.role, "category": b.category}
            for b in buildings}


def custom_building(spec: dict) -> Building:
    """A Building instance for a validated custom building spec."""
    orc_info = spec.get("orc") or {}
    return Building(
        id=str(spec["id"]),
        title=str(spec["title"]),
        icon=str(spec.get("icon", "🏗️")),
        category="custom",
        orc=str(orc_info.get("name") or "Peon"),
        role=str(orc_info.get("role") or ""),
        view=CUSTOM,
        spec=spec,
    )
