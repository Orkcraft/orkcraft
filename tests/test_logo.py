"""The app's icons (tools/logo.py): cut from the generated sheet, clear behind the head, never nearest-neighbour."""
from __future__ import annotations

import pathlib

import pytest

Image = pytest.importorskip("PIL.Image")       # the logo tool's own dependency, not the app's

ROOT = pathlib.Path(__file__).resolve().parent.parent
PWA = ROOT / "orkcraft" / "gui" / "static" / "pwa"
LOGO = ROOT / "design-system" / "logo"


def _colours(img) -> int:
    return len({p for p in img.convert("RGBA").getdata() if p[3] > 0})


@pytest.mark.parametrize("name,size", [("icon-192.png", 192), ("icon-512.png", 512)])
def test_phone_icons_are_clear_with_transparent_corners(name: str, size: int) -> None:
    img = Image.open(PWA / name)
    assert img.size == (size, size) and img.mode == "RGBA"
    for xy in ((0, 0), (size - 1, 0), (0, size - 1), (size - 1, size - 1)):
        assert img.getpixel(xy)[3] == 0
    box = img.getchannel("A").getbbox()
    assert 0.8 * size <= max(box[2] - box[0], box[3] - box[1]) <= 0.9 * size    # the head fills ~85–90 %


def test_apple_touch_icon_is_opaque_in_one_ground_colour() -> None:
    img = Image.open(PWA / "apple-touch-icon.png").convert("RGBA")
    assert img.size == (180, 180) and img.getchannel("A").getextrema() == (255, 255)
    assert img.getpixel((0, 0)) == img.getpixel((179, 179)) == (0xe3, 0xbf, 0x9a, 255)    # tokens.css --ink-gold


def test_favicons_decode_and_are_clear() -> None:
    for name, size in (("favicon-16.png", 16), ("favicon-32.png", 32), ("ork-mark-256.png", 256)):
        img = Image.open(LOGO / name)
        assert img.size == (size, size) and img.getpixel((0, 0))[3] == 0
    ico = Image.open(LOGO / "favicon.ico")
    assert {(16, 16), (32, 32), (48, 48)} <= set(ico.info["sizes"])


def test_native_mark_is_the_sources_own_size() -> None:
    (path,) = [p for p in LOGO.glob("ork-mark-[0-9]*.png") if p.stem != "ork-mark-256"]
    n = int(path.stem.rsplit("-", 1)[1])
    assert Image.open(path).size == (n, n) and 150 <= n < 1024


def test_512_icon_is_not_a_blocky_nearest_neighbour_cut() -> None:
    icon = Image.open(PWA / "icon-512.png")
    low = Image.open(ROOT / "design-system" / "sprites" / "v3" / "orks" / "roles" / "mechanic.png")
    assert _colours(icon) > 4 * _colours(low)       # smooth edges and shading, not the cut's ten colours in blocks
