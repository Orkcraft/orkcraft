"""A picture of the design system painted again from a person's words (docs/design/improve-buildings.md §6.2).

One call to the image tool (an AI tool that can make pictures; agy by default) in an empty folder holding the
picture as it is (`reference.png`): the shipped prompt for its kind (design/prompts/<kind>.md) keeps the style, the
person's words say what changes, and a region marked on it says where only. The tool writes `out.png` there; it is
checked to be a PNG of a sane size, and nothing else in the folder is read.

    painter.kind_of("sprites/buildings/barracks/header.png")   → "sprite"
    painter.paint(tool, model, path, reference_bytes, words, region) → the new picture's bytes
"""
from __future__ import annotations

import re
import tempfile
import threading
from pathlib import Path

from orkcraft.design import agents
from orkcraft.realm import jobs

PROMPTS = Path(__file__).resolve().parent.parent / "design" / "prompts"
KINDS = {"intents": "icon", "buildings": "sprite", "orks": "ork"}       # a sprites/ folder → the prompt it uses
PNG = b"\x89PNG\r\n\x1a\n"
MAX_BYTES = 4_000_000
OUT = "out.png"
PATH = re.compile(r"^sprites/(intents|buildings|orks)/[a-z0-9_./@-]+\.png$")


class PaintError(Exception):
    """A picture that could not be painted; its text is shown to the person."""


def kind_of(path: str) -> str:
    """icon, sprite or ork for a picture of the design system ("" for one the UX bench does not paint)."""
    if not PATH.match(path or "") or ".." in path:
        return ""
    return KINDS[path.split("/")[1]]


def prompt(kind: str, what: str, words: str, region: dict | None = None) -> str:
    system = (PROMPTS / f"{kind}.md").read_text(encoding="utf-8").strip()
    where = ""
    if region:
        where = (f"\nChange ONLY the region from {region['x']:.0%} to {region['x'] + region['w']:.0%} of the width and "
                 f"from {region['y']:.0%} to {region['y'] + region['h']:.0%} of the height (from the top left) of "
                 "reference.png; keep every other pixel exactly as it is.")
    return f"""{agents.brief("alchemist")}

{system}

The picture: {what}. `reference.png` in this folder is how it is now.
What to change, in the person's words: {words.strip()}{where}

Make the picture with your image tool and save it as `{OUT}` in this folder (PNG). Write no other file. Say in one
line what you changed."""


def paint(tool: str, model: str, path: str, reference: bytes, words: str, region: dict | None = None,
          runner=None, cancel: threading.Event | None = None) -> bytes:
    kind = kind_of(path)
    if not kind:
        raise PaintError("The UX bench paints the Build icons, the houses and the orks")
    if len(words.strip()) < 3:
        raise PaintError("Say what to change")
    run = runner or jobs.run_work
    with tempfile.TemporaryDirectory(prefix="orkcraft-paint-") as tmp:
        folder = Path(tmp)
        (folder / "reference.png").write_bytes(reference)
        try:
            run(tool, prompt(kind, path, words, region), folder, cancel or threading.Event(), model)
        except (RuntimeError, OSError) as e:
            raise PaintError(f"The image tool failed: {str(e)[:300]}") from None
        out = folder / OUT
        if not out.is_file():
            raise PaintError(f"The image tool made no picture: does {tool} make pictures here? Pick another in its "
                             "settings")
        data = out.read_bytes()
    if not data.startswith(PNG) or len(data) > MAX_BYTES:
        raise PaintError("What the image tool made is not a PNG picture of a sane size")
    return data
