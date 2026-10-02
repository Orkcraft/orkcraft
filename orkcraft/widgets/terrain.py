"""Terrain widget: background ASCII canvas for the desktop."""
from __future__ import annotations

from rich.segment import Segment
from rich.style import Style
from textual.strip import Strip
from textual.widget import Widget

from orkcraft.theme import BIOMES, DEFAULT_BIOME, SOLID_BLACK, Biome, terrain_rows


class Terrain(Widget):
    """Background canvas displaying sparse ASCII terrain for the active biome."""

    DEFAULT_CSS = """
    Terrain {
        position: absolute;
        width: 100%;
        height: 100%;
    }
    """

    def __init__(
        self,
        biome: Biome | None = None,
        solid_black: bool = False,
        *,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__(id=id, classes=classes)
        self.can_focus = False
        self.biome = biome or BIOMES[DEFAULT_BIOME]
        self.solid_black = solid_black
        self._cache_key: tuple | None = None
        self._cached_strips: list[Strip] = []
        # Road cells in the gaps between windows: (x, y) → (glyph, "faint" | "bright").
        self.road_cells: dict[tuple[int, int], tuple[str, str]] = {}
        self._roads_version = 0

    def set_roads(self, cells: dict[tuple[int, int], tuple[str, str]]) -> None:
        if cells == self.road_cells:
            return
        self.road_cells = dict(cells)
        self._roads_version += 1
        self.refresh()

    def set_biome(self, biome: Biome, solid_black: bool = False) -> None:
        """Update active biome and solid black mode, clear row cache and refresh."""
        self.biome = biome
        self.solid_black = solid_black
        self._cache_key = None
        self._cached_strips.clear()
        self.refresh()

    def _road_styles(self, bg: str) -> dict[str, Style]:
        from orkcraft.widgets.road_layer import ROAD_BRIGHT, ROAD_FAINT, ROAD_SELECTED
        return {"faint": Style(color=ROAD_FAINT, bgcolor=bg),
                "bright": Style(color=ROAD_BRIGHT, bgcolor=bg, bold=True),
                "selected": Style(color=ROAD_SELECTED, bgcolor=bg, bold=True)}

    def _build_strips(self, width: int, height: int) -> list[Strip]:
        strips = self._build_terrain(width, height)
        if not self.road_cells:
            return strips
        bg = SOLID_BLACK if self.solid_black else self.biome.canvas
        styles = self._road_styles(bg)
        rows: dict[int, dict[int, tuple[str, str]]] = {}
        for (x, y), cell in self.road_cells.items():
            if 0 <= x < width and 0 <= y < height:
                rows.setdefault(y, {})[x] = cell
        for y, cells in rows.items():
            segs = list(strips[y])
            line: list[tuple[str, Style]] = []
            for seg in segs:
                line.extend((ch, seg.style) for ch in seg.text)
            for x, (ch, kind) in cells.items():
                if x < len(line):
                    line[x] = (ch, styles.get(kind, styles["faint"]))
            out: list[Segment] = []
            for ch, st in line:
                if out and out[-1].style == st:
                    out[-1] = Segment(out[-1].text + ch, st)
                else:
                    out.append(Segment(ch, st))
            strips[y] = Strip(out)
        return strips

    def _build_terrain(self, width: int, height: int) -> list[Strip]:
        if self.solid_black:
            style = Style(bgcolor=SOLID_BLACK)
            seg = Segment(" " * width, style)
            return [Strip([seg]) for _ in range(height)]

        canvas = self.biome.canvas
        terrain_color = self.biome.terrain
        space_style = Style(bgcolor=canvas)
        glyph_style = Style(color=terrain_color, bgcolor=canvas) if terrain_color else space_style

        if not self.biome.glyphs or terrain_color is None:
            seg = Segment(" " * width, space_style)
            return [Strip([seg]) for _ in range(height)]

        rows = terrain_rows(width, height, self.biome, seed=0)
        strips: list[Strip] = []
        for row in rows:
            segments: list[Segment] = []
            curr_text: list[str] = []
            curr_style: Style = space_style
            for ch in row:
                st = glyph_style if ch != " " else space_style
                if not curr_text:
                    curr_text.append(ch)
                    curr_style = st
                elif st == curr_style:
                    curr_text.append(ch)
                else:
                    segments.append(Segment("".join(curr_text), curr_style))
                    curr_text = [ch]
                    curr_style = st
            if curr_text:
                segments.append(Segment("".join(curr_text), curr_style))
            strips.append(Strip(segments))
        return strips

    def render_line(self, y: int) -> Strip:
        width = self.size.width
        height = self.size.height
        if width <= 0 or height <= 0:
            return Strip([])
        key = (width, height, self.biome, self.solid_black, self._roads_version)
        if self._cache_key != key:
            self._cached_strips = self._build_strips(width, height)
            self._cache_key = key
        if 0 <= y < len(self._cached_strips):
            return self._cached_strips[y]
        bg = SOLID_BLACK if self.solid_black else self.biome.canvas
        return Strip([Segment(" " * width, Style(bgcolor=bg))])
