"""Tests for canvas biomes, deterministic terrain generation, and alt+t toggle."""
from __future__ import annotations

from pathlib import Path
import pytest
from rich.cells import cell_len
from textual.color import Color

from orkcraft import theme
from orkcraft.app import OrkcraftApp
from orkcraft.widgets.terrain import Terrain

SIZE = (120, 40)


def test_density_and_void():
    """Density <= MAX_DENSITY on 200x60 for forest/ice; void has no glyphs."""
    width, height = 200, 60
    total_cells = width * height

    # Void biome: exactly height rows of width spaces
    void_rows = theme.terrain_rows(width, height, theme.BIOMES["void"])
    assert len(void_rows) == height
    assert all(len(row) == width for row in void_rows)
    assert all(row == " " * width for row in void_rows)
    assert sum(1 for row in void_rows for ch in row if ch != " ") == 0

    # Forest biome: density <= MAX_DENSITY (0.12)
    forest_rows = theme.terrain_rows(width, height, theme.BIOMES["forest"])
    forest_count = sum(1 for row in forest_rows for ch in row if ch != " ")
    forest_density = forest_count / total_cells
    assert 0 < forest_density <= theme.MAX_DENSITY

    # Ice biome: density <= MAX_DENSITY (0.12)
    ice_rows = theme.terrain_rows(width, height, theme.BIOMES["ice"])
    ice_count = sum(1 for row in ice_rows for ch in row if ch != " ")
    ice_density = ice_count / total_cells
    assert 0 < ice_density <= theme.MAX_DENSITY


def test_glyphs_are_single_cell_and_belong_to_biome():
    """Every glyph is 1 terminal cell wide and belongs to its biome."""
    for name, biome in theme.BIOMES.items():
        for g in biome.glyphs:
            assert cell_len(g) == 1

    width, height = 100, 40
    for name in ("forest", "ice"):
        biome = theme.BIOMES[name]
        rows = theme.terrain_rows(width, height, biome, seed=42)
        assert len(rows) == height
        for row in rows:
            assert len(row) == width
            for ch in row:
                if ch != " ":
                    assert cell_len(ch) == 1
                    assert ch in biome.glyphs


def test_terrain_determinism():
    """Identical size and seed generate identical rows."""
    for name in ("forest", "ice"):
        biome = theme.BIOMES[name]
        rows1 = theme.terrain_rows(80, 25, biome, seed=123)
        rows2 = theme.terrain_rows(80, 25, biome, seed=123)
        assert rows1 == rows2

        rows_diff_seed = theme.terrain_rows(80, 25, biome, seed=999)
        assert rows1 != rows_diff_seed


@pytest.mark.asyncio
async def test_window_background_per_biome(fake_repo: Path):
    """In running app, window background matches biome (opaque) and updates on set_biome."""
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        desktop = app.desktop
        window = desktop.windows[0]

        # Default biome is forest -> #0e1611
        assert desktop.biome == "forest"
        assert window.styles.background == Color.parse("#0e1611")

        # Switch to ice -> #090f14
        desktop.set_biome("ice")
        await pilot.pause()
        assert desktop.biome == "ice"
        assert window.styles.background == Color.parse("#090f14")

        # Switch to void -> #0e1611
        desktop.set_biome("void")
        await pilot.pause()
        assert desktop.biome == "void"
        assert window.styles.background == Color.parse("#0e1611")

        # Switch back to forest -> #0e1611
        desktop.set_biome("forest")
        await pilot.pause()
        assert desktop.biome == "forest"
        assert window.styles.background == Color.parse("#0e1611")


@pytest.mark.asyncio
async def test_toggle_terrain_solid_black_and_persists(fake_repo: Path, isolated_layout_file: Path):
    """alt+t flips solid_black, desktop becomes #000000, and value survives restart."""
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        desktop = app.desktop
        assert desktop.solid_black is False
        assert desktop.styles.background == Color.parse(theme.BIOMES[theme.DEFAULT_BIOME].canvas)

        # Toggle terrain off with alt+t
        await pilot.press("alt+t")
        await pilot.pause()
        assert desktop.solid_black is True
        assert desktop.has_class("-solid-black")
        assert desktop.styles.background == Color.parse("#000000")

    # Restart app on same repo and layout file
    app2 = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app2.run_test(size=SIZE) as pilot2:
        await pilot2.pause()
        desktop2 = app2.desktop
        assert desktop2.solid_black is True
        assert desktop2.has_class("-solid-black")
        assert desktop2.styles.background == Color.parse("#000000")

        # Toggle back to normal biome background
        await pilot2.press("alt+t")
        await pilot2.pause()
        assert desktop2.solid_black is False
        assert not desktop2.has_class("-solid-black")
        assert desktop2.styles.background == Color.parse(theme.BIOMES[theme.DEFAULT_BIOME].canvas)


def test_terrain_widget_render_and_cache():
    """Terrain widget renders correct colors and respects solid_black."""
    forest = theme.BIOMES["forest"]
    terrain = Terrain(biome=forest)
    # Simulate widget size
    terrain._size = type("Size", (), {"width": 40, "height": 10})()

    strip = terrain.render_line(0)
    assert strip is not None
    # All segments should have canvas background
    for seg in strip:
        assert seg.style is not None
        assert seg.style.bgcolor is not None
        assert seg.style.bgcolor.name == forest.canvas
        if seg.text.strip():
            # Glyph segment
            assert seg.style.color is not None
            assert seg.style.color.name == forest.terrain

    # Set solid black
    terrain.set_biome(forest, solid_black=True)
    strip_black = terrain.render_line(0)
    for seg in strip_black:
        assert seg.style is not None
        assert seg.style.bgcolor is not None
        assert seg.style.bgcolor.name == theme.SOLID_BLACK
