"""A picture of the design system painted again from a person's words (docs/design/improve-buildings.md §6.2).

One call to the image tool (an AI tool that can make pictures; agy by default) in an empty folder holding the
picture as it is (`reference.png`): the shipped prompt for its kind (design/prompts/<kind>.md) keeps the style, the
person's words say what changes, and a region marked on it says where only. The tool writes `out.png` there; it is
checked to be a PNG of a sane size, and nothing else in the folder is read.

    painter.kind_of("sprites/buildings/barracks/header.png")   → "sprite"
    painter.kind_of("sprites/buildings/mill/work-part.png")    → "motion" (a moving house's layer, realm/motion.py)
    painter.paint(tool, model, path, reference_bytes, words, region) → the new picture's bytes
    painter.mascot(path, grid, words, region) → (the new grid, why, problems): a mascot, drawn as its grid by a text
                                                  model (design/mascots.py), never by the image tool
"""
from __future__ import annotations

import functools
import re
import tempfile
import threading
from pathlib import Path

from orkcraft.design import agents, mascots
from orkcraft.realm import jobs, motion

PROMPTS = Path(__file__).resolve().parent.parent / "design" / "prompts"
KINDS = {"intents": "icon", "buildings": "sprite", "orks": "ork"}       # a sprites/ folder → the prompt it uses
PNG = b"\x89PNG\r\n\x1a\n"
MAX_BYTES = 4_000_000
OUT = "out.png"
PATH = re.compile(r"^sprites/(intents|buildings|orks)/[a-z0-9_./@-]+\.png$")


class PaintError(Exception):
    """A picture that could not be painted; its text is shown to the person."""


def kind_of(path: str) -> str:
    """icon, sprite, ork or motion for a picture of the design system ("" for one the UX bench does not paint)."""
    if not PATH.match(path or "") or ".." in path:
        return ""
    return "motion" if motion.of_path(path) else KINDS[path.split("/")[1]]


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
    # The folder is a throwaway one holding only the reference, so the tool asks nothing there (its sandbox still holds):
    # agy, headless, refuses every command it would ask about and ends its turn with no picture.
    run = runner or functools.partial(jobs.run_work, free=True)
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


MAX_ATTEMPTS = 2             # a mascot's grid: a wrong answer goes back once
MASCOT_PROMPT = """{who}

You draw the operator's mascot of Orkline, a town of AI agents: a pixel head on a grid of {w} columns × {h} rows,
one letter a cell, "." a transparent cell. The head: {what}.
The palette (a letter → its colour and what it is used for):
{palette}
Rules: the same palette only (never a letter of your own), the same head and silhouette unless the words ask
otherwise, readable at 24 × 22 px, never a crown (the crown is the Workchief's).

The grid now:
{grid}

What to change, in the person's words: {words}{where}
{feedback}
Answer with JSON only: {{"grid": ["{w} letters", "... {h} rows in all"], "why": "one short line on what you changed"}}"""


def mascot(p: str, current: list[str], words: str, region: dict | None = None, what: str = "", runner=None
           ) -> tuple[list[str] | None, str, list[str]]:
    """A mascot drawn again (docs/design/improve-buildings.md §6.4): the person's words → a checked grid, by a text
    model and no image tool (a wrong answer goes back once with its problems)."""
    from orkcraft.realm import builders
    run = runner or builders.main_runner
    pal = "\n".join(f"- `{k}` {v}: {mascots.USES.get(k, '')}" for k, v in mascots.palette().items())
    feedback, wrong = "", ["no answer"]
    for _ in range(MAX_ATTEMPTS):
        prompt = MASCOT_PROMPT.format(who=agents.brief("alchemist"), w=mascots.W, h=mascots.H, what=what or p,
                                      palette=pal, grid="\n".join(current), words=words.strip()[:1000],
                                      where=mascots.cells(region), feedback=feedback)
        try:
            text, _cost = run(prompt)
        except RuntimeError as e:
            return None, "", [str(e)]
        doc = builders.extract_json(text) or {}
        g = doc.get("grid")
        wrong = mascots.problems(g)
        if not wrong:
            return list(g), str(doc.get("why") or "")[:300], []
        feedback = "\nYOUR PREVIOUS ANSWER WAS REJECTED. Fix every problem:\n" + "\n".join(f"- {w}" for w in wrong[:10])
    return None, "", wrong
