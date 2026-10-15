"""The switch stand's stand-in (design-system-v3.md §4c rule 6), drawn until the art session draws the real one.

    python tools/switch_standin.py

A post, a lever at its foot and a target arm on top, 16 × 24 art px, in two positions read by position, never by
colour: `track/switch-still.png` (the arm along the track, the lever back: a cart goes on) and
`track/switch-thrown.png` (the arm turned to face the way, the lever over: a cart turns). Its colours are picked from
c2's own track (the ties' honey wood, the rails' iron, the outline), so it sits on the track as if cut from it. Writes
the two PNGs into design-system/sprites/v3/track/ and their rows into the manifest, marked `stand_in` (the cutter keeps
rows whose source is not a sheet it cuts). Needs `pip install pillow`.
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "design-system" / "sprites" / "v3"
W, H = 16, 24
SOURCE = "stand-in (tools/switch_standin.py)"


def _colours() -> dict[str, tuple[int, int, int, int]]:
    """The track's own: its darkest (the outline), its brightest warm (the ties' wood), its iron grey."""
    im = Image.open(OUT / "track" / "stop-e.png").convert("RGBA")
    seen = Counter(p for p in im.getdata() if p[3] > 200)
    by_light = sorted(seen, key=lambda p: sum(p[:3]))
    outline = by_light[0]
    wood = max(seen, key=lambda p: (p[0] - p[2]) * (seen[p] > 40))
    iron = min((p for p in seen if seen[p] > 30), key=lambda p: abs(p[0] - p[2]) * 4 + abs(sum(p[:3]) - 330))
    shade = tuple(int(c * 0.6) for c in wood[:3]) + (255,)
    return {"o": outline, "w": wood, "i": iron, "d": shade}


# Two positions: a cart goes on (still) or turns (thrown). `.` clear; o outline, w wood, d wood in shade, i iron.
STILL = [
    "................",
    "................",
    "................",
    "..oooooooooooo..",
    "..oiiiiiiiiiio..",
    "..oooooooooooo..",
    ".......owo......",
    ".......owo......",
    ".......owo......",
    ".......owo......",
    ".......owo......",
    ".......owo......",
    ".......owo......",
    ".......owo......",
    ".......owo......",
    "...o...owo......",
    "...oo..owo......",
    "....oo.owo......",
    ".....oowwo......",
    "......owdo......",
    "....oooooooo....",
    "....oddddddo....",
    "....oooooooo....",
    "................",
]
THROWN = [
    "................",
    "....oooooooo....",
    "....oiiiiiio....",
    "....oiooooio....",
    "....oioiwoio....",
    "....oiooooio....",
    "....oiiiiiio....",
    "....oooooooo....",
    ".......owo......",
    ".......owo......",
    ".......owo......",
    ".......owo......",
    ".......owo......",
    ".......owo......",
    ".......owo......",
    ".......owo...o..",
    ".......owo..oo..",
    ".......owo.oo...",
    ".......owwoo....",
    ".......odwo.....",
    "....oooooooo....",
    "....oddddddo....",
    "....oooooooo....",
    "................",
]


def draw(rows: list[str], colours: dict) -> Image.Image:
    assert len(rows) == H and all(len(r) == W for r in rows)
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            if ch != ".":
                im.putpixel((x, y), colours[ch])
    return im


def main() -> None:
    colours = _colours()
    rows = []
    for name, art in (("switch-still", STILL), ("switch-thrown", THROWN)):
        file = f"track/{name}.png"
        draw(art, colours).save(OUT / file)
        rows.append({"file": file, "size": [W, H], "frame": [W, H], "frames": 1, "show": 1, "anchor": "feet",
                     "placeholder": True, "stand_in": True, "source": SOURCE,
                     "licence": "stand-in drawn in code from the track's colours until the art session draws the "
                                "switch stand (design-system-v3.md §4c)",
                     "author": "tools/switch_standin.py"})
    manifest = OUT / "manifest.json"
    data = json.loads(manifest.read_text(encoding="utf-8"))
    keep = [r for r in data["sprites"] if r["file"] not in {x["file"] for x in rows}]
    data["sprites"] = sorted(keep + rows, key=lambda r: r["file"])
    manifest.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{len(rows)} stand-ins in {manifest}")


if __name__ == "__main__":
    main()
