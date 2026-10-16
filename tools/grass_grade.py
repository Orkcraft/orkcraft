"""Spec 18 (decisions §29): darker, richer grass (variant B).

Reads each ground tile from git at 223c414b, grades the grass (whole tiles completely, mixed tiles
on grass pixels only, identified by g > r + 15 and g > b + 15), and writes them to
design-system/sprites/v3/ground/.

Grade: ImageEnhance.Color(rgb).enhance(1.30) → ImageEnhance.Brightness(…).enhance(0.75) →
ImageEnhance.Contrast(…).enhance(0.90).
"""
from __future__ import annotations

import io
from pathlib import Path
import subprocess

from PIL import Image, ImageEnhance

ROOT = Path(__file__).resolve().parent.parent
BASE_COMMIT = "223c414b"
GROUND_DIR = Path("design-system/sprites/v3/ground")

WHOLE_TILES = (
    "grass-1.png",
    "grass-2.png",
    "grass-3.png",
    "grass-4.png",
    "grass-tufts-1.png",
    "grass-tufts-2.png",
    "grass-flowers.png",
    "tufts.png",
    "flowers.png",
)

MIXED_TILES = (
    "rim-n.png",
    "rim-s.png",
    "rim-e.png",
    "rim-w.png",
    "corner-ne.png",
    "corner-nw.png",
    "inner-ne.png",
)


def grade_image(img: Image.Image) -> Image.Image:
    """Grade image colours in the exact order specified by Spec 18:
    Color(1.30) -> Brightness(0.75) -> Contrast(0.90). Alpha is kept as it is."""
    alpha = img.getchannel("A") if "A" in img.getbands() else None
    rgb = img.convert("RGB")
    c = ImageEnhance.Color(rgb).enhance(1.30)
    b = ImageEnhance.Brightness(c).enhance(0.75)
    graded_rgb = ImageEnhance.Contrast(b).enhance(0.90)
    if alpha is not None:
        graded = graded_rgb.convert("RGBA")
        graded.putalpha(alpha)
        return graded
    return graded_rgb


def grade_mixed_image(orig: Image.Image) -> Image.Image:
    """Grade only grass pixels (where g > r + 15 and g > b + 15). Earth pixels stay exactly
    as they are, so the path matches earth*.png."""
    graded = grade_image(orig)
    orig_px = orig.load()
    grad_px = graded.load()
    out = orig.copy()
    out_px = out.load()
    w, h = orig.size
    for y in range(h):
        for x in range(w):
            r, g, b, a = orig_px[x, y]
            if g > r + 15 and g > b + 15:
                out_px[x, y] = grad_px[x, y]
    return out


def fetch_from_git(commit: str, rel_path: str, cwd: Path = ROOT) -> Image.Image:
    data = subprocess.check_output(["git", "show", f"{commit}:{rel_path}"], cwd=cwd)
    return Image.open(io.BytesIO(data))


def grade_tile(name: str, commit: str = BASE_COMMIT, cwd: Path = ROOT) -> Image.Image:
    rel_path = f"{GROUND_DIR}/{name}"
    orig = fetch_from_git(commit, rel_path, cwd=cwd)
    if name in WHOLE_TILES:
        return grade_image(orig)
    if name in MIXED_TILES:
        return grade_mixed_image(orig)
    raise ValueError(f"Unknown ground tile: {name}")


def main(target_dir: Path | None = None, commit: str = BASE_COMMIT, cwd: Path = ROOT) -> list[Path]:
    dest = target_dir or (cwd / GROUND_DIR)
    dest.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for name in WHOLE_TILES + MIXED_TILES:
        out_img = grade_tile(name, commit=commit, cwd=cwd)
        out_file = dest / name
        out_img.save(out_file, format="PNG")
        written.append(out_file)
    return written


if __name__ == "__main__":
    files = main()
    print(f"Graded {len(files)} ground tiles from git at {BASE_COMMIT}.")
