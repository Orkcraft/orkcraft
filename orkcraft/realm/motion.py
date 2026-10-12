"""Buildings at work (docs/design/building-motion.md): what moves on a house while its ork works, and how.

A house that moves is two pictures beside its `header.png`, painted by the UX bench's Alchemist from the house as it
is (realm/painter.py, design/prompts/motion.md): `work-still.png`, the house without the part that moves, and
`work-part.png`, that part alone, both on the house's canvas so they lie over it pixel for pixel. The town turns or
swings the part around its pivot while the building is busy (js/icons.js `HutSprite`); the painting is the model's,
the motion is the code's, so the house never jumps between frames.

    motion.MOTIONS["mill"].move     → "turn"
    motion.paths("mill")           → ("sprites/buildings/mill/work-still.png", "sprites/buildings/mill/work-part.png")
"""
from __future__ import annotations

from dataclasses import dataclass

STILL, PART = "still", "part"


@dataclass(frozen=True)
class Motion:
    still: str                         # the house without its moving part, in words for the image tool
    part: str                          # the moving part alone, in words
    move: str                          # "turn": round and round · "swing": out by `degrees` and back
    pivot: tuple[float, float]         # what it moves around: shares of the house's width and height, from the top left
    degrees: float                     # a turn's quarter of symmetry (four sails: 90) · a swing's arc (+ is clockwise)
    steps: int = 4                     # frames a turn or a swing takes


# Keyed by the house's sprite folder (js/icons.js spriteName). The pivots were read off the shipped headers
# (2026-10-12): the mill's hub, the catapult's gold pivot block.
MOTIONS: dict[str, Motion] = {
    "mill": Motion(
        still="The same windmill with the four sails and the round dark-green cap with the hub REMOVED. Keep only the "
              "tower, its top, the door and the base. Where the sails used to cover the tower, paint the tower as it "
              "looks behind them, continuing its shading and its outline.",
        part="ONLY the four sails together with the dark-green cap and the hub, exactly as in the reference, in the same "
             "X shape and position. Remove the tower, the door and the base completely.",
        move="turn", pivot=(0.477, 0.399), degrees=90),
    "catapult": Motion(
        still="The same catapult with the long throwing arm, its bucket and the gold stone REMOVED. Keep the wheels, the "
              "frame, the skull, the small block on the left and the gold pivot block where the arm was attached.",
        part="ONLY the long throwing arm with its bucket, exactly as in the reference, in the same position and angle, "
             "with the gold stone in the bucket. Remove the wheels, the frame, the skull and everything else.",
        move="swing", pivot=(0.5, 0.427), degrees=70),
}


def paths(sprite: str) -> tuple[str, str]:
    """The two pictures a moving house is made of, as design-system paths (`/ds/<path>`)."""
    folder = f"sprites/buildings/{sprite}"
    return f"{folder}/work-{STILL}.png", f"{folder}/work-{PART}.png"


def of_path(path: str) -> tuple[str, str] | None:
    """(sprite, still | part) for a moving house's picture, None for any other path."""
    bits = (path or "").split("/")
    if len(bits) != 4 or bits[:2] != ["sprites", "buildings"] or bits[2] not in MOTIONS:
        return None
    which = {f"work-{STILL}.png": STILL, f"work-{PART}.png": PART}.get(bits[3])
    return (bits[2], which) if which else None


def brief(path: str) -> str:
    """What the Alchemist is asked to paint for a moving house's picture, "" for any other."""
    got = of_path(path)
    if not got:
        return ""
    m = MOTIONS[got[0]]
    return m.still if got[1] == STILL else m.part


def as_data(m: Motion) -> dict:
    return {"move": m.move, "pivot": list(m.pivot), "degrees": m.degrees, "steps": m.steps}
