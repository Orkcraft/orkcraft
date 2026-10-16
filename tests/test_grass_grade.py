"""Tests for Spec 18: darker, richer grass (tools/grass_grade.py and ground tiles)."""
from __future__ import annotations

import io
from pathlib import Path
import subprocess

from PIL import Image

from tools import grass_grade

ROOT = Path(__file__).resolve().parent.parent
GROUND_DIR = ROOT / "design-system" / "sprites" / "v3" / "ground"
TOKENS_CSS = ROOT / "design-system" / "tokens.css"


def _luminance(r: int, g: int, b: int) -> float:
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def test_script_run_twice_gives_identical_bytes(tmp_path):
    """The script run twice gives identical bytes."""
    dir1 = tmp_path / "run1"
    dir2 = tmp_path / "run2"
    files1 = grass_grade.main(target_dir=dir1, cwd=ROOT)
    files2 = grass_grade.main(target_dir=dir2, cwd=ROOT)

    assert len(files1) == len(grass_grade.WHOLE_TILES) + len(grass_grade.MIXED_TILES)
    assert len(files1) == len(files2)
    for p1, p2 in zip(files1, files2):
        assert p1.name == p2.name
        assert p1.read_bytes() == p2.read_bytes(), f"{p1.name} differs between runs"


def test_earth_pixel_of_rim_n_unchanged_from_base():
    """An earth pixel of rim-n.png is unchanged from 223c414b."""
    data_orig = subprocess.check_output(
        ["git", "show", f"{grass_grade.BASE_COMMIT}:design-system/sprites/v3/ground/rim-n.png"],
        cwd=ROOT,
    )
    orig_im = Image.open(io.BytesIO(data_orig))
    cur_im = Image.open(GROUND_DIR / "rim-n.png")

    assert cur_im.size == orig_im.size
    w, h = orig_im.size

    earth_pixels_checked = 0
    for y in range(h):
        for x in range(w):
            r, g, b, a = orig_im.getpixel((x, y))
            # Earth pixel: not (g > r + 15 and g > b + 15)
            if not (g > r + 15 and g > b + 15):
                cur_pixel = cur_im.getpixel((x, y))
                assert cur_pixel == (r, g, b, a), f"Earth pixel at ({x}, {y}) changed from {r,g,b,a} to {cur_pixel}"
                earth_pixels_checked += 1

    assert earth_pixels_checked > 0, "No earth pixels found in rim-n.png"


def test_grass_pixel_of_grass_1_is_darker_than_base():
    """A grass pixel of grass-1.png is darker than at 223c414b."""
    data_orig = subprocess.check_output(
        ["git", "show", f"{grass_grade.BASE_COMMIT}:design-system/sprites/v3/ground/grass-1.png"],
        cwd=ROOT,
    )
    orig_im = Image.open(io.BytesIO(data_orig))
    cur_im = Image.open(GROUND_DIR / "grass-1.png")

    assert cur_im.size == orig_im.size

    # Check pixel (10, 10), which is a grass pixel
    orig_px = orig_im.getpixel((10, 10))
    cur_px = cur_im.getpixel((10, 10))

    orig_lum = _luminance(orig_px[0], orig_px[1], orig_px[2])
    cur_lum = _luminance(cur_px[0], cur_px[1], cur_px[2])

    assert cur_lum < orig_lum, f"Grass pixel at (10, 10) not darker: before {orig_lum}, after {cur_lum}"


def test_tokens_camp_grass_updated():
    """The tokens in design-system/tokens.css, in the :root, [data-theme="camp"] block only."""
    css = TOKENS_CSS.read_text(encoding="utf-8")
    assert "--world-grass: #589224;" in css
    assert "--world-grass-light: #669b30;" in css
    assert "--world-grass-dark: #2c6835;" in css
