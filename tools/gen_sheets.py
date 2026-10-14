"""Generate v3's sprite sheets through the Gemini API, so the owner only picks among candidates (design-system-v3.md §8).

    python tools/gen_sheets.py --list                        the sheets it knows, their references and expected pieces
    python tools/gen_sheets.py --prompt b2-town              print the prompt a sheet is asked with (no call)
    python tools/gen_sheets.py b1-catapult b2-town           generate N candidates of each (default 3)
    python tools/gen_sheets.py --all -n 2 --max-calls 30     every sheet it knows
    python tools/gen_sheets.py --check                       re-check every candidate and rebuild the index
    python tools/gen_sheets.py --pick b2-town 2              copy candidate 2 to b2-town.png and cut it (--v3)

An internal tool, never shipped and never imported by `orkcraft/`. It speaks only to the official Gemini API over
HTTPS (generativelanguage.googleapis.com) with the key in `GEMINI_API_KEY` (an environment secret: never printed,
logged or written); it never calls or wraps the `agy` CLI or any Google login (decisions-2026-10.md §5).

Each prompt is the shared head of v3-prompts §3, the sheet's own prompt, and the lines the reviews (§5–§11) added:
front-on, never isometric; no frames, boxes or grid lines; no shadows, smoke or glow; no ground under a building;
F1's colours; no yellow, orange or red outside the signals' sheet; "the same orc as the attached sheets" on an ork
sheet. F1 is always attached; b1-core for buildings, o1 and o2 for orks, c2 for the track.

Candidates go to `docs/design/img/references/v3/candidates/<sheet>/<n>.png` with `<n>.json` beside each: the checks of
the cutter's own code (`tools/camp_sheet.py`: the pieces it finds against those expected, the art pixel pitch, the
pixels in a signal's hue, the magenta cast). `candidates/index.html` shows them side by side. Nothing here writes a
cut sheet's name except `--pick`.

The key is on the free tier: calls are throttled (`--interval`), a 429 waits as long as the API says and retries,
a daily quota stops the run and says so, and a run makes at most `--max-calls` calls (default 20).
"""
from __future__ import annotations

import argparse
import base64
import html
import json
import os
import pathlib
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
REFS = ROOT / "docs" / "design" / "img" / "references" / "v3"
CANDIDATES = REFS / "candidates"
SPEC = ROOT / "tools" / "camp_sheets_v3.json"
API = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
MODEL = "gemini-3.1-flash-image"           # Nano Banana 2, listed by the API's models endpoint (2026-10-14)

# --- the prompt ---------------------------------------------------------------------------------------------------

HEAD = ("No shadows. Pixel-art sprite sheet in exactly the style and palette of the attached image. Crisp hard pixels "
        "on a strict grid, no anti-aliasing, no blur, no gradients, each sprite with a dark 1-pixel outline, drawn at "
        "its final size with no finer detail than that size can hold. One three-quarter top-down projection, never "
        "isometric. Sprites in a neat grid with even spacing on a flat solid #FF00FF magenta background, nothing "
        "touching, no ground under them, no text unless asked. Bright yellow and bright red appear nowhere.")

# what the rounds of review added (v3-prompts §5–§11), to every sheet or to one kind
ALL = [
    "No frames, no boxes, no grid lines, no borders between sprites; each sprite floats alone on the magenta.",
    "No shadows, no smoke, no glow.",
    "Keep exactly the colours of the attached frame F1: the grass as saturated and bright as in it (about #7cbd40), "
    "the paths warm sand (about #e4b469); warm honey wood, light cool stone, teal and plum cloth, cream bone.",
    "No yellow, no orange and no red anywhere: those colours are reserved for the product's signals. The wood a "
    "muted honey brown, never orange.",
    "Output the sheet as a PNG image.",
]
ALONE = ("Draw it small, at the pixel size of the attached sheet b1-core: the building takes about a third of the "
         "image's width, with wide magenta all round; never filling the frame.")
BUILDING = [
    "Every building faces the viewer: its front wall parallel to the bottom edge of the image, the door in the middle "
    "of the front, seen slightly from above, exactly like the task board in the attached sheet b1-core. Never turned "
    "at an angle, never isometric.",
    "No ground under the building: no patch of grass, no base square, no plinth of earth.",
]
ORK = [
    "The same orc as the attached sheets o1 and o2: bald, round, big head, short body, olive-moss skin, small tusks, a "
    "leather apron, the same pixel size and proportions (32 × 32), the same outline. Not a taller orc, no cap, no "
    "shirt and trousers.",
    "Legs and arms clearly swing in every walk; the same facing in every frame of a row.",
]
CAPPED = [                                  # the main ork since v3-prompts §12: the capped ork of the 0.3 sheets
    "The same orc as the attached sheets roles-2 and o3-states-r1: a cloth cap, a leather apron over a shirt, a tool "
    "belt, olive-moss skin, small tusks; the same pixel size and proportions as in them, the same outline.",
    "The same facing in every frame; each frame a clear step of the movement.",
]
TRACK = [
    "Flat from above, exactly like the attached track sheet c2: dark iron rails on honey-wood ties, the ties evenly "
    "spaced.",
]
SIGNALS = "Bright yellow and bright red appear ONLY on the signal markers asked below."

# the reference images, by name (a JPEG or a PNG under REFS)
REF = {"f1": "f1-town.jpg", "b1": "b1-core.jpg", "o1": "o1-body.jpg", "o2": "o2-roles.jpg", "c1": "c1-carts.jpg",
       "c2": "c2-track.jpg", "g2": "g2-decor.jpg",
       "g3": "g3-palisade.jpg", "tb": "b1-taskboard.jpg",       # the owner's picks of round 7
       "r03": "../0.3/roles-2.jpg", "o3r": "o3-states-r1.jpg"}  # the capped ork (§12)

# the sheets: kind (building, ork, track, edge, signals), the prompt (v3-prompts §3, as the reviews redid it), the
# pieces the cutter should find, the image's aspect, and the cut name `--pick` copies it to
SHEETS: dict[str, dict] = {
    "b1-catapult": {
        "kind": "building", "expect": 4, "aspect": "16:9",
        "prompt": "A crude orc wooden catapult in side view, facing right, standing against a low wall of rounded "
                  "logs on its right, at a log buffer stop where a mine-cart track ends coming in from the left, a "
                  "cow skull on its frame, bone tusks on the base, its arm and bucket with a scroll; four frames in "
                  "one row: resting; pulled back; mid-throw; the scroll flying up and to the right over the wall. "
                  "About 160 px wide. The frame of the catapult drawn with its front parallel to the image's bottom "
                  "edge (the one side view of the camp).",
        "about": "v3-prompts §8: the Publisher in side view against a low log wall; overrides B1's catapult",
    },
    "b1-lookout": {
        "kind": "building", "expect": 1, "aspect": "1:1",
        "prompt": "External listeners: a wooden lookout tower with a hide roof, a bone horn on a stand and a little "
                  "ladder, built INTO a low palisade of rounded logs (not sharpened): its legs stand in the wall, the "
                  "wall runs out to the left and right of it for a short stretch, and at the tower's foot a wooden "
                  "gate in the wall, open, where a mine-cart track passes through. About 128 px wide, 160 tall. One "
                  "picture, alone on the magenta.",
        "about": "v3-prompts §7.3: the lookout built into the wall; overrides B1's watchtower",
    },
    "b1-taskboard": {
        "kind": "building", "expect": 1, "aspect": "4:3",
        "prompt": "Task board: the task board as large as the work hall of the attached sheet, about 160–192 px "
                  "wide: a broad notice board under a shingle roof on two posts, big parchment scrolls and light "
                  "stone slabs pinned to it with bone pins, a door-sized gap below for its keeper. One picture, alone "
                  "on the magenta.",
        "about": "v3-prompts §9: the Task board at core size; overrides B1's",
    },
    "b2-town": {
        "kind": "building", "expect": 6, "aspect": "16:9",
        "prompt": "Six buildings in one row, 96–128 px wide each, the door in the lower middle of each front: "
                  "1. Town Hall: a big long house with a carved totem and a plum banner, 128 × 128. 2. Review board: "
                  "an open ring of stones round one calm campfire with teal flames, logs to sit on, 112 × 96. "
                  "3. Research: a round timber-and-stone tower with a big open book on a lectern at its top, no "
                  "crenellations, 96 × 128. 4. Wiki: a hut stacked with scrolls and shelves, 96 × 96. 5. Test bench: a "
                  "workshop with a small anvil and gears on a bench, 96 × 96. 6. UX bench: a painter's hut with an "
                  "easel and colour pots in teal, plum and sky blue (no yellow or orange banner), 96 × 96.",
        "about": "v3-prompts §3a B2, redrawn front-on (§7.1, §7.4, §7.5)",
    },
    "b3-plumbing": {
        "kind": "building", "expect": 6, "aspect": "16:9",
        "prompt": "Six small buildings in one row, 64–96 px wide each: 1. Router: a wooden signpost with three arms on "
                  "a small plinth, 64 × 80. 2. Transformer: a small water mill with a turning wheel, 96 × 96. "
                  "3. Script: a tinker's workbench with cogs and a crank, 80 × 80. 4. Drop file here: a wooden chute "
                  "into an open crate, 64 × 64. 5. output: a covered storehouse with crates at the door, 96 × 80. "
                  "6. Branches & PRs: a smithy with a forge glowing teal, not red, 96 × 96. Exactly six, no extra "
                  "piece.",
        "about": "v3-prompts §3a B3, redrawn front-on (§7.1)",
    },
    "b4-others": {
        "kind": "building", "expect": 6, "aspect": "16:9",
        "prompt": "Six small buildings in one row, 64–96 px wide each: 1. Metrics: a carved stone with a chart "
                  "scratched on it, 64 × 80. 2. Calendar: a big drum on a frame with a sundial beside it, 80 × 80. "
                  "3. File tree: a small grove of three trees with labelled stakes, 96 × 96. 4. Audio briefing: a "
                  "small stage with a horn speaker made of bone, 80 × 80. 5. Sound alerts: a horn on a post, 64 × 80. "
                  "6. A building of one's own: a plain empty hut with a blank sign, 80 × 80. Not a workbench: none of "
                  "these is the Script bench.",
        "about": "v3-prompts §3a B4, redrawn front-on (§9.6)",
    },
    "o3-states": {
        "kind": "ork", "expect": 5, "aspect": "21:9",
        "prompt": "The worker orc, 32 × 32, five poses in one row: working with a calm face; waiting with one hand "
                  "raised and a curious face; slumped with a frown (no smoke puff); sitting with arms crossed; dozing "
                  "with a small \"z z\".",
        "about": "v3-prompts §3b.3 regenerated on the o1/o2 ork (§9.2, §10)",
    },
    "o5-inside": {
        "kind": "ork", "expect": 18, "aspect": "4:3",
        "prompt": "The worker orc, 32 × 32, four rows: row 1, carrying a light stone slab, 6 frames walking right; "
                  "row 2, holding a big magnifying glass up, 4 frames; row 3, writing with a quill at a lectern, "
                  "4 frames; row 4, pinning a parchment to a board, 4 frames, every frame a step of the action. The "
                  "lens of the glass pale blue, not magenta.",
        "about": "v3-prompts §3b.5 regenerated on the o1/o2 ork (§10)",
    },
    "g3-palisade": {
        "kind": "edge", "expect": 6, "aspect": "21:9", "refs": ["g2"],
        "prompt": "A low wooden palisade of rounded logs (not sharpened), 32-px pieces, six in one row: a straight "
                  "run; a corner turning down on the left; a corner turning down on the right; an end post on the "
                  "left; an end post on the right; a gap where a track passes. No track drawn, no rail fence: only "
                  "the palisade of rounded logs, the same logs as the attached decor sheet.",
        "about": "v3-prompts §3d.3 redone (§11): no smoke, no track",
    },
    "g3-sides": {
        "kind": "edge", "expect": 6, "aspect": "21:9", "refs": ["g3"],
        "prompt": "The same low palisade of rounded logs as the attached sheet g3-palisade, the same log size and the "
                  "same pixel size, six pieces in one row: a vertical run (the wall going down the right edge of the "
                  "camp, seen front-on: a column of log tops one behind the other); the four outer corners "
                  "(north-west, north-east, south-west, south-east), each where a horizontal run meets a vertical "
                  "one; an end post. No track, no gate.",
        "about": "the palisade's missing pieces (round 7): the side wall, the four corners, an end post",
    },
    "c2-more": {
        "kind": "track", "expect": 6, "aspect": "3:2",
        "prompt": "Track tiles that match the attached track sheet c2 exactly: the same rail gauge and the same tie "
                  "spacing as its straight pieces. The last curves came with the rails 41 px apart where c2's are 32: "
                  "keep the rails exactly as far apart as on the attached straights. Six pieces in a row with "
                  "magenta round each: a curve joining the top and the left sides (north–west); a T-junction with "
                  "exits north, east and south; then the four curves again: north–east, east–south, south–west, "
                  "west–north. Every tile the same square size as c2's, the rails crossing each edge at its middle.",
        "about": "c2's north-west curve, the T with exits N/E/S, the curves again at c2's gauge (round 7)",
    },
    "b1-taskboard-s": {
        "kind": "building", "expect": 1, "aspect": "4:3", "refs": ["tb"], "cut": "b1-taskboard.png",
        "prompt": "Task board: the attached task board b1-taskboard, the same design (shingle roof on posts, scrolls "
                  "and stone slabs pinned with bone pins, the door-sized gap below), redrawn smaller: about 0.8 of "
                  "the width of the work hall with the teal roof in the attached sheet b1-core, at exactly the same "
                  "pixel size as that work hall. The wood a muted honey brown, as in b1-core. One picture, alone on "
                  "the magenta.",
        "about": "the picked Task board at 0.8 of the work hall (round 7); --pick replaces b1-taskboard",
    },
    "o6-door": {
        "kind": "ork-capped", "expect": 4, "aspect": "21:9", "refs": ["r03", "o3r"],
        "prompt": "The worker orc, 32 × 32, stepping out of a wooden door, four frames in one row, the same door in "
                  "each: the door closed with the orc behind it (only the door seen); the door opening, the orc's "
                  "face in the gap; the orc half out of the doorway; the orc out in front of the door, facing the "
                  "viewer.",
        "about": "v3-prompts §12: the capped ork stepping out of a door (o1 had it), 4 frames",
    },
    "c2-curves": {
        "kind": "track", "expect": 6, "aspect": "3:2",
        "prompt": "A wooden mine-cart track, 64 × 64 tiles, six pieces in a row with magenta round each: four curves, "
                  "one for each pair of sides: north–east, east–south, south–west, west–north; then a merge (two "
                  "lines joining into one, two tiles long) and a crossing, drawn apart, not touching. Every tile "
                  "exactly the same square size, drawn on the same pixel grid as the attached track sheet; the rails "
                  "and the earth bed cross the tile's edge at exactly the same place on every tile and stop flush "
                  "with the edge; the rails sit in the middle of the tile, the same distance apart on every piece.",
        "about": "c2's missing curves (§10): one per pair of sides, the merge and the crossing apart",
    },
}


def refs_for(name: str) -> list[str]:
    """The reference images a sheet is asked with: F1 always, then its kind's taken sheets, then its own."""
    sh = SHEETS[name]
    kind = {"building": ["b1"], "ork": ["o1", "o2"], "track": ["c2"]}.get(sh["kind"], [])
    out = ["f1"] + kind + sh.get("refs", [])
    return [REF[r] for r in dict.fromkeys(out)]


def build_prompt(name: str) -> str:
    sh = SHEETS[name]
    head = HEAD
    if sh["kind"] == "signals":                  # the one sheet that may have them
        head = head.replace("Bright yellow and bright red appear nowhere.", SIGNALS)
    lines = [head, sh["prompt"]]
    lines += {"building": BUILDING, "ork": ORK, "ork-capped": CAPPED, "track": TRACK}.get(sh["kind"], [])
    if sh["expect"] == 1:                       # one building alone: the model draws it as large as the image
        lines.append(ALONE)
    lines += [s for s in ALL if not (sh["kind"] == "signals" and s.startswith("No yellow"))]
    names = ", ".join(pathlib.Path(r).stem for r in refs_for(name))
    lines.append(f"Attached, in order: {names}. F1 is the approved frame: its style and colours rule.")
    return "\n\n".join(lines)


# --- the API --------------------------------------------------------------------------------------------------------

class Stop(Exception):
    """The run must end: no key, the free tier refuses, a daily quota is spent, the call cap reached."""


def api_key() -> str:
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        raise Stop("GEMINI_API_KEY is not set: add it as an environment secret; nothing was generated.")
    return key


def _inline(path: pathlib.Path) -> dict:
    mime = "image/png" if path.suffix == ".png" else "image/jpeg"
    return {"inline_data": {"mime_type": mime, "data": base64.b64encode(path.read_bytes()).decode()}}


def request_body(name: str, size: str | None = "2K") -> dict:
    parts = [{"text": build_prompt(name)}] + [_inline(REFS / r) for r in refs_for(name)]
    config: dict = {"aspectRatio": SHEETS[name]["aspect"]}
    if size:
        config["imageSize"] = size
    return {"contents": [{"role": "user", "parts": parts}],
            "generationConfig": {"responseModalities": ["TEXT", "IMAGE"], "imageConfig": config}}


def _error(raw: bytes) -> dict:
    try:
        return json.loads(raw).get("error", {})
    except ValueError:
        return {"message": raw[:500].decode(errors="replace")}


def daily(err: dict) -> bool:
    """A 429 that waiting will not cure today: a per-day quota, or a quota of zero (the free tier has none)."""
    for d in err.get("details", []):
        for v in d.get("violations", []):
            q = (v.get("quotaId", "") + v.get("quotaMetric", "")).lower()
            if "perday" in q or "per_day" in q or str(v.get("quotaValue", "")) == "0":
                return True
    return "limit: 0" in err.get("message", "")


def retry_after(err: dict, default: float) -> float:
    for d in err.get("details", []):
        if d.get("@type", "").endswith("RetryInfo"):
            try:
                return float(str(d.get("retryDelay", "")).rstrip("s")) + 1
            except ValueError:
                pass
    return default


class Client:
    def __init__(self, model: str, max_calls: int, interval: float, opener=urllib.request.urlopen,
                 sleep=time.sleep):
        self.model, self.max_calls, self.interval = model, max_calls, interval
        self.calls, self._last = 0, 0.0
        self._open, self._sleep = opener, sleep

    def _post(self, body: dict) -> tuple[int, bytes]:
        if self.calls >= self.max_calls:
            raise Stop(f"the cap of {self.max_calls} calls for this run is reached (--max-calls to change it)")
        wait = self._last + self.interval - time.monotonic()
        if wait > 0:
            self._sleep(wait)
        self.calls += 1
        self._last = time.monotonic()
        req = urllib.request.Request(API.format(model=self.model), data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json", "x-goog-api-key": api_key()})
        try:
            with self._open(req, timeout=300) as r:
                return r.status, r.read()
        except urllib.error.HTTPError as e:
            return e.code, e.read()
        except OSError as e:                        # a reset or a timeout on the way: retried like a 5xx
            return 0, json.dumps({"error": {"message": f"network: {e}"}}).encode()

    def generate(self, body: dict) -> tuple[bytes, str, str]:
        """One image: its bytes, its mime type, and any text the model said. Backs off on a 429."""
        backoff = 20.0
        for _ in range(5):
            status, raw = self._post(body)
            if status == 200:
                data = json.loads(raw)
                text, img = [], None
                for cand in data.get("candidates", []):
                    for p in cand.get("content", {}).get("parts", []):
                        blob = p.get("inlineData") or p.get("inline_data")
                        if blob and img is None:
                            img = (base64.b64decode(blob["data"]), blob.get("mimeType") or blob.get("mime_type"))
                        elif p.get("text"):
                            text.append(p["text"])
                if img is None:
                    reason = data.get("promptFeedback") or [c.get("finishReason") for c in data.get("candidates", [])]
                    raise RuntimeError(f"no image in the answer ({reason}); the model said: {' '.join(text)[:300]}")
                return img[0], img[1], " ".join(text)
            err = _error(raw)
            if status == 429:
                if daily(err):
                    raise Stop(f"a daily quota is spent; the API said: {err.get('message', '')[:600]}")
                wait = retry_after(err, backoff)
                print(f"  429, waiting {wait:.0f} s: {err.get('message', '')[:160]}")
                self._sleep(wait)
                backoff *= 2
                continue
            if status == 400 and "imageSize" in json.dumps(body) and "image" in err.get("message", "").lower() \
                    and "size" in err.get("message", "").lower():
                body["generationConfig"]["imageConfig"].pop("imageSize", None)      # the free tier's own size
                continue
            if status in (401, 403) or (status == 400 and self.calls == 1):
                raise Stop(f"the API refused (HTTP {status}): {err.get('message', '')[:600]}")
            if status >= 500 or status == 0:
                self._sleep(backoff)
                backoff *= 2
                continue
            raise RuntimeError(f"HTTP {status}: {err.get('message', '')[:600]}")
        raise RuntimeError("gave up after repeated 429/5xx")


# --- the checks (the cutter's own code) ----------------------------------------------------------------------------

def _cutter():
    sys.path.insert(0, str(ROOT / "tools"))
    import camp_sheet
    return camp_sheet


def _spec_sheet(name: str) -> dict:
    spec = json.loads(SPEC.read_text(encoding="utf-8"))
    return next((s for s in spec["sheets"] if s["name"] == name), {})


def degrid_of(name: str) -> bool:
    return bool(_spec_sheet(name).get("degrid", SHEETS.get(name, {}).get("kind") in ("ork", "ork-capped", "track")))


def check(path: pathlib.Path, name: str) -> dict:
    """What the cutter reads on a candidate: pieces found against expected, the art pixel, the signal hues, the cast."""
    import numpy as np
    cs = _cutter()
    sp = _spec_sheet(name)
    sheet = cs.Sheet(path, sp.get("fringe", 60), sp.get("close", 1), degrid_of(name))
    art = sheet.art
    opaque = art[..., 3] > 0
    cols, counts = np.unique(art[..., :3][opaque].reshape(-1, 3), axis=0, return_counts=True)
    signal = int(sum(int(n) for c, n in zip(cols, counts) if cs.signal_hue(tuple(int(v) for v in c))))
    rgb = art[..., :3].astype(int)
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    cast = opaque & (r - g > 25) & (b - g > 25) & (b * 4 >= r * 3) & cs._grow(~opaque, 3)   # decast()'s rule
    found = len(sheet.boxes)
    expected = SHEETS[name]["expect"]
    sizes = [[int(b_[2] - b_[0]), int(b_[3] - b_[1])] for b_ in sheet.ordered()]
    side = float(np.median([max(w, h) for w, h in sizes])) if sizes else 0.0
    lo, hi = art_range(SHEETS[name]["kind"])
    n_op = max(int(opaque.sum()), 1)
    issues = []
    if found != expected:
        issues.append(f"{found} pieces found, {expected} expected")
    if signal >= 8 and SHEETS[name]["kind"] != "signals":
        issues.append(f"{signal} px in a signal's hue")
    if sizes and not lo <= side <= hi:
        issues.append(f"pieces about {side:.0f} art px, the taken sheets' {lo:.0f}–{hi:.0f}: another pixel size")
    if cast.sum() / n_op > 0.01:
        issues.append(f"magenta cast on {100 * cast.sum() / n_op:.1f} % of the art")
    return {"sheet": name, "file": path.name, "image": list(Image_size(path)), "pitch": round(float(sheet.pitch), 2),
            "art_px": round(side), "art_range": [round(lo), round(hi)] if hi != float("inf") else None,
            "grid": [sheet.w, sheet.h], "pieces": found, "expected": expected, "sizes": sizes,
            "degrid": degrid_of(name), "signal_px": signal, "signal_pct": round(100 * signal / n_op, 2),
            "cast_px": int(cast.sum()), "cast_pct": round(100 * float(cast.sum()) / n_op, 2),
            "ok": not issues, "issues": issues}


_SIDE: dict[str, float] = {}

# the art px (a piece's longer side) a kind is drawn at: buildings as B1–B3 were taken (the Agent pool 193 wide, a
# signpost about 64), the palisade's 32-px pieces; orks and the track measured on o1 and c2 (±30 %)
SIZES = {"building": (48.0, 260.0), "edge": (20.0, 96.0)}


def art_range(kind: str) -> tuple[float, float]:
    """How large a piece of this kind is drawn, in the sheet's own art px: a candidate outside it comes at another
    pixel size (round 4's o3 was drawn at 8.3 image px per art px against o1's 5, a blockier orc)."""
    if kind in SIZES:
        return SIZES[kind]
    ref = {"ork": "o1", "track": "c2"}.get(kind)
    if not ref:
        return (0.0, float("inf"))
    if kind not in _SIDE:
        import numpy as np
        cs = _cutter()
        sheet = cs.Sheet(REFS / REF[ref], grid_lines=True)
        _SIDE[kind] = float(np.median([max(b[2] - b[0], b[3] - b[1]) for b in sheet.boxes]))
    return (_SIDE[kind] * 0.7, _SIDE[kind] * 1.3)


def Image_size(path: pathlib.Path) -> tuple[int, int]:
    from PIL import Image
    with Image.open(path) as im:
        return im.size


# --- candidates, the index, the pick --------------------------------------------------------------------------------

def images(folder: pathlib.Path) -> list[pathlib.Path]:
    """A sheet's candidates, by number: `<n>.png`, or `<n>.jpg` when the model answered with a JPEG."""
    found = [p for p in folder.glob("*") if p.suffix in (".png", ".jpg") and p.stem.isdigit()] \
        if folder.is_dir() else []
    return sorted(found, key=lambda p: int(p.stem))


def next_number(folder: pathlib.Path) -> int:
    return max((int(p.stem) for p in images(folder)), default=0) + 1


def save_image(data: bytes, mime: str, folder: pathlib.Path, k: int) -> pathlib.Path:
    """The image exactly as the API sent it: `<k>.png` for a PNG; a JPEG (what the image model sends, whatever the
    prompt asks) keeps its bytes as `<k>.jpg` — turned into a PNG it would only grow fivefold, the JPEG's noise kept."""
    dest = folder / f"{k}{'.png' if 'png' in mime else '.jpg'}"
    assert CANDIDATES in dest.parents, dest          # a generated image never lands on a cut sheet's name
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    return dest


def generate(names: list[str], n: int, client: Client, size: str | None) -> list[str]:
    done = []
    for name in names:
        folder = CANDIDATES / name
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "prompt.txt").write_text(build_prompt(name) + "\n\nReferences: " + ", ".join(refs_for(name)) + "\n",
                                           encoding="utf-8")
        for _ in range(n):
            k = next_number(folder)
            print(f"{name} #{k} (call {client.calls + 1} of at most {client.max_calls})")
            try:
                data, mime, text = client.generate(request_body(name, size))
            except RuntimeError as e:
                print(f"  failed: {e}")
                continue
            dest = save_image(data, mime, folder, k)
            report = {"returned": mime, "model": client.model, "said": text[:400], "prompt": build_prompt(name)}
            try:
                report.update(check(dest, name))
            except Exception as e:                    # noqa: BLE001 — a sheet the cutter cannot read is a finding
                report.update({"ok": False, "issues": [f"the cutter could not read it: {e}"]})
            (folder / f"{k}.json").write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
            print(f"  {dest.relative_to(ROOT)}: " + ("ok" if report.get("ok") else "; ".join(report["issues"])))
            done.append(f"{name}/{k}")
    return done


def recheck() -> None:
    for folder in sorted(p for p in CANDIDATES.iterdir() if p.is_dir() and p.name in SHEETS):
        for img in images(folder):
            rep_path = img.with_suffix(".json")
            old = json.loads(rep_path.read_text(encoding="utf-8")) if rep_path.exists() else {}
            old.update(check(img, folder.name))
            rep_path.write_text(json.dumps(old, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


def build_index() -> pathlib.Path:
    rows = []
    for name in SHEETS:
        folder = CANDIDATES / name
        imgs = images(folder)
        if not imgs:
            continue
        sh = SHEETS[name]
        cards = []
        for img in imgs:
            rep = json.loads(img.with_suffix(".json").read_text(encoding="utf-8")) if img.with_suffix(".json").exists() \
                else {}
            verdict = "ok" if rep.get("ok") else "check"
            facts = (f"pieces {rep.get('pieces', '?')} / {rep.get('expected', sh['expect'])} · pitch "
                     f"{rep.get('pitch', '?')} px · signal {rep.get('signal_px', '?')} px · cast "
                     f"{rep.get('cast_pct', '?')} %")
            issues = "".join(f"<li>{html.escape(i)}</li>" for i in rep.get("issues", []))
            cards.append(
                f'<figure class="{verdict}"><a href="{name}/{img.name}"><img src="{name}/{img.name}" loading="lazy" '
                f'alt="{name} candidate {img.stem}"></a><figcaption><b>#{img.stem}</b> <span class="v">{verdict}'
                f'</span><br>{html.escape(facts)}<ul>{issues}</ul><code>python tools/gen_sheets.py --pick {name} '
                f'{img.stem}</code></figcaption></figure>')
        prompt = (folder / "prompt.txt").read_text(encoding="utf-8") if (folder / "prompt.txt").exists() else ""
        rows.append(f'<section><h2>{name} <small>→ {html.escape(cut_name(name))} · {html.escape(sh["about"])}'
                    f'</small></h2><div class="row">{"".join(cards)}</div><details><summary>prompt</summary>'
                    f'<pre>{html.escape(prompt)}</pre></details></section>')
    page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>v3 candidates</title>
<style>
:root {{ --bg: #f6f1e4; --ink: #2b2118; --card: #fffaf0; --ok: #2f7d6d; --bad: #8a3b6b; }}
@media (prefers-color-scheme: dark) {{ :root {{ --bg: #1d1915; --ink: #eee4d0; --card: #2a241e; }} }}
body {{ background: var(--bg); color: var(--ink); font: 14px/1.4 system-ui, sans-serif; margin: 0 16px 40px; }}
h1 {{ font-size: 20px; }} h2 {{ font-size: 16px; margin: 28px 0 8px; }} small {{ font-weight: normal; opacity: .7; }}
.row {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 12px; }}
figure {{ margin: 0; background: var(--card); border-radius: 6px; padding: 8px; border-left: 4px solid var(--bad); }}
figure.ok {{ border-left-color: var(--ok); }}
img {{ width: 100%; image-rendering: pixelated; background: #ff00ff; display: block; }}
figcaption {{ margin-top: 6px; font-size: 12px; }} .v {{ text-transform: uppercase; font-size: 11px; }}
ul {{ margin: 4px 0; padding-left: 18px; }} code {{ font-size: 11px; opacity: .8; }}
pre {{ white-space: pre-wrap; font-size: 12px; }}
</style></head><body>
<h1>v3 sprite sheet candidates</h1>
<p>Generated by <code>tools/gen_sheets.py</code> (Gemini API). Each is checked with the cutter's own code
(<code>tools/camp_sheet.py</code>): the pieces it finds against those expected, the art pixel pitch, pixels in a
signal's yellow/orange/red, the magenta cast. Projection (front-on, never isometric) is for the eye. Pick one with
the command under it.</p>
{"".join(rows) or "<p>No candidates yet.</p>"}
</body></html>
"""
    out = CANDIDATES / "index.html"
    CANDIDATES.mkdir(parents=True, exist_ok=True)
    out.write_text(page, encoding="utf-8")
    return out


def cut_name(name: str) -> str:
    """The sheet's name under docs/design/img/references/v3/: its own, or the one it redraws (`cut`)."""
    return SHEETS.get(name, {}).get("cut") or _spec_sheet(name).get("file") or f"{name}.png"


def pick(name: str, n: int, run=subprocess.run) -> pathlib.Path:
    """The owner's choice: candidate n becomes the sheet under its cut name, then `camp_sheet.py --v3` cuts it. The
    only way this tool writes a cut sheet."""
    if name not in SHEETS:
        raise Stop(f"unknown sheet {name!r} (see --list)")
    src = next((p for p in images(CANDIDATES / name) if int(p.stem) == n), None)
    if src is None:
        raise Stop(f"no candidate {n} of {name} in {(CANDIDATES / name).relative_to(ROOT)}")
    dest = REFS / cut_name(name)                    # the cutter takes the .png, else a .jpg under the same name
    if src.suffix == ".jpg" and not dest.exists():
        dest = dest.with_suffix(".jpg")
    if src.suffix == dest.suffix:
        shutil.copyfile(src, dest)
    else:                                           # a JPEG where a .png must win: the same pixels as a PNG
        from PIL import Image
        with Image.open(src) as im:
            im.convert("RGB").save(dest, "PNG")
    print(f"{src.relative_to(ROOT)} → {dest.relative_to(ROOT)}")
    run([sys.executable, str(ROOT / "tools" / "camp_sheet.py"), "--v3"], check=True, cwd=ROOT)
    return dest


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("sheets", nargs="*", help="the sheets to generate (see --list)")
    ap.add_argument("--all", action="store_true", help="every sheet it knows")
    ap.add_argument("-n", type=int, default=3, help="candidates per sheet (default 3)")
    ap.add_argument("--max-calls", type=int, default=20, help="the most calls this run makes (default 20)")
    ap.add_argument("--interval", type=float, default=12.0, help="seconds between calls (free tier: default 12)")
    ap.add_argument("--model", default=MODEL)
    ap.add_argument("--size", default="2K", help="imageSize asked (1K, 2K, 4K; 'none' to leave it to the model)")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--prompt", metavar="SHEET")
    ap.add_argument("--check", action="store_true", help="re-check every candidate and rebuild the index")
    ap.add_argument("--pick", nargs=2, metavar=("SHEET", "N"))
    a = ap.parse_args(argv)
    try:
        if a.list:
            for name, sh in SHEETS.items():
                print(f"{name:13} → {cut_name(name):18} {sh['expect']:2} pieces  refs {', '.join(refs_for(name))}")
            return 0
        if a.prompt:
            print(build_prompt(a.prompt))
            return 0
        if a.pick:
            pick(a.pick[0], int(a.pick[1]))
            return 0
        if a.check:
            recheck()
            print(build_index().relative_to(ROOT))
            return 0
        names = list(SHEETS) if a.all else a.sheets
        unknown = [s for s in names if s not in SHEETS]
        if unknown or not names:
            raise Stop(f"name sheets to generate (unknown: {unknown}); --list shows them")
        api_key()
        client = Client(a.model, a.max_calls, a.interval)
        try:
            generate(names, a.n, client, None if a.size == "none" else a.size)
        finally:
            print(f"{client.calls} calls made; index: {build_index().relative_to(ROOT)}")
    except Stop as e:
        print(f"stopped: {e}")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
