"""⚗️ The UX bench's work (docs/design/improve-buildings.md §6): the look of one type of building.

Its settings say which type (`target`, picked from a list laid out as Build is, never from the map: a look is a
type's, not one building's) and which AI tool paints (`image_tool`, agy by default). It lays no road and takes none
(catalog `roads = "none"`). The gallery of the type's pictures is the view's (gui/views/ux_lab.py); painting them
again and laying the window out again come next (stage 6).
"""
from __future__ import annotations

from orkcraft.core.workers import Worker
from orkcraft.realm import catalog

IMAGE_TOOL = "agy"            # paints unless its settings name another (asked 2026-10-11)


class UxLabWorker(Worker):
    TYPE = "ux_lab"

    @property
    def target(self) -> str:
        """The type whose look it works on, "" until one is picked (or when the one picked is gone)."""
        tid = str(self.config.get("target") or "")
        return tid if tid in catalog.TYPES and tid != self.TYPE else ""

    @property
    def image_tool(self) -> str:
        return str(self.config.get("image_tool") or IMAGE_TOOL)

    def pick(self, type_id: str) -> bool:
        """Work on `type_id`'s look; False for a type the catalog has not (or itself)."""
        tid = catalog.ALIASES.get(type_id, type_id)
        if tid not in catalog.TYPES or tid == self.TYPE:
            return False
        return self.save_config({"target": tid})

    def set_tool(self, tool: str) -> bool:
        return self.save_config({"image_tool": tool or None})
