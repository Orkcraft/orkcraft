"""✅ The `pictures` scenario of `orkcraft check` (docs/design/check.md §2): the Alchemist paints a picture of the design
system again from a person's words (realm/painter.py), and a judge looks at both. No face.

    check_pictures.CASES                                   what is painted, and what the words ask
    check_pictures.run(case, tool, model, folder)          one painting and its judging → a result dict

A run passes when the tool made a PNG of the reference's size (or twice it), not the same picture again, and the judge
— the same AI tool, reading both files — scores it at least the budget's `picture_score` of 10 for doing what the words
ask while keeping the style. Everything is kept in `folder`: reference.png, out.png, judge.json.
"""
from __future__ import annotations

import json
import re
import struct
import tempfile
import threading
import time
from pathlib import Path

from orkcraft.design import tokens
from orkcraft.realm import jobs, painter

CASES: tuple[dict, ...] = (
    {"id": "roof-red", "path": "sprites/buildings/barracks/header-meadow.png",
     "words": "Make the roof red, keep everything else as it is"},
    {"id": "ork-hat", "path": "sprites/orks/hat-captain.png",
     "words": "Give the hat a small white feather on its left side"},
    {"id": "icon-bolder", "path": "sprites/intents/calendar.png",
     "words": "Make the icon read better at small size: thicker outlines, the same colours"},
)
_JSON = re.compile(r"\{.*\}", re.S)


def size(data: bytes) -> tuple[int, int] | None:
    """A PNG's width and height, from its header; None for anything else."""
    if not data.startswith(painter.PNG) or len(data) < 24:
        return None
    return struct.unpack(">II", data[16:24])


def judge_prompt(words: str) -> str:
    return f"""Two pictures are in this folder: `reference.png` (before) and `out.png` (after an artist changed it).
The artist was asked: "{words}"

Look at both. Score the change from 0 to 10: 10 when it does exactly what was asked, keeps the style, the colours and
the outline of the original everywhere else, and would sit next to the original set unnoticed; 0 when it ignores
the ask or breaks the style. Answer with JSON only:
{{"score": 0-10, "did_what_was_asked": true|false, "kept_the_style": true|false, "notes": "what is good and what is off"}}"""


def run(case: dict, tool: str, model: str, folder: Path, runner=None, judge=None) -> dict:
    """Paint, check the file, judge it; everything kept in `folder`. `runner`/`judge`: fakes for tests."""
    folder.mkdir(parents=True, exist_ok=True)
    reference = (tokens.SYSTEM / case["path"]).read_bytes()
    (folder / "reference.png").write_bytes(reference)
    out = {"seconds": 0.0, "error": "", "png": False, "size_ok": False, "changed": False, "score": None, "notes": ""}
    start = time.monotonic()
    try:
        data = painter.paint(tool, model, case["path"], reference, case["words"], runner=runner)
    except painter.PaintError as e:
        out.update(error=str(e), seconds=round(time.monotonic() - start, 1))
        return out
    out["seconds"] = round(time.monotonic() - start, 1)
    (folder / "out.png").write_bytes(data)
    want, got = size(reference), size(data)
    out.update(png=got is not None, changed=data != reference,
               size_ok=bool(want and got and (got == want or got == (want[0] * 2, want[1] * 2))),
               size=list(got) if got else None, reference_size=list(want) if want else None)
    with tempfile.TemporaryDirectory(prefix="orkcraft-judge-") as tmp:
        for name in ("reference.png", "out.png"):
            (Path(tmp) / name).write_bytes((folder / name).read_bytes())
        try:
            text = (judge or (lambda p, w: jobs.run_read(tool, p, w, threading.Event(), model)[0]))(
                judge_prompt(case["words"]), Path(tmp))
        except (RuntimeError, OSError) as e:
            out["notes"] = f"the judge failed: {e}"[:300]
            return out
    m = _JSON.search(text or "")
    try:
        verdict = json.loads(m.group(0)) if m else {}
    except ValueError:
        verdict = {}
    (folder / "judge.json").write_text(json.dumps({"answer": text, **verdict}, indent=2, ensure_ascii=False),
                                       encoding="utf-8")
    score = verdict.get("score")
    out.update(score=float(score) if isinstance(score, (int, float)) else None, notes=str(verdict.get("notes") or "")[:600])
    return out


def passed(r: dict, min_score: float) -> bool:
    return not r["error"] and r["png"] and r["size_ok"] and r["changed"] and (r["score"] or 0) >= min_score
