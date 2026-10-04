"""Shoot one building as its hut on the town map (ice biome), alone in the middle of the frame,
in Camp and in Office, from a fresh copy of the class sandbox. The crop is the real screen around
the hut (terrain and all), 2.3:1."""
from __future__ import annotations
import asyncio, json, shutil, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent)); sys.path.insert(0, str(Path(__file__).parent.parent))
import shotlib
import shootlib                       # the frozen clock, the slow simulated orcs
from shootlib import settle, pad_to_ratio, _freeze_clock
from orkcraft.app import OrkcraftApp
from orkcraft.screens.typed.base import TypedView

W, H = 200, 60
shotlib.SCALE = 8          # large pictures: one terminal cell is ~98 × 195 px
shotlib.MARGIN = 2         # ×8 → 16 px
SPOTS = [(0.0, 0.0), (1.0, 0.0), (0.0, 1.0), (1.0, 1.0), (0.0, 0.5), (1.0, 0.5), (0.18, 1.0), (0.82, 0.0),
         (0.18, 0.0), (0.82, 1.0)]


def layout(root: Path, target: str) -> None:
    p = root / ".orkcraft.json"
    d = json.loads(p.read_text())
    for o in d["orkspaces"]:
        o["biome"] = "ice"
    others = [b for b in d["buildings"] if b["id"] != target and not b.get("demolished")]
    for b in d["buildings"]:
        if b["id"] == target:
            b["hut"] = [0.5, 0.45]
    for b, spot in zip(others, SPOTS):
        b["hut"] = list(spot)
    p.write_text(json.dumps(d, ensure_ascii=False, indent=2))


async def shoot(root: Path, bid: str, mode: str, out: Path, prep=None, rows: int | None = None) -> tuple[str, int]:
    _freeze_clock()
    app = OrkcraftApp(repo_root=root, auto_commit=False, layout_file=root / ".orkcraft.json", demo=True)
    async with app.run_test(size=(W, H)) as pilot:
        await settle(pilot, 8)
        app.desktop.set_mode(mode)
        app.set_focus_state("neutral"); app.desktop.set_active(None)
        await settle(pilot, 10)
        w = app.desktop.get_window(bid)
        if prep:
            found = w.query(TypedView)
            r = prep(app, found.first() if found else w)
            if asyncio.iscoroutine(r):
                await r
        app.refresh_roster(); app.desktop.refresh_huts()
        await settle(pilot, 16)
        hut = app.desktop.huts[bid]
        r = hut.region
        lines = shotlib.screen_lines(app)
        # the hut and nothing else: its name, roof, body and buttons
        crop = shotlib.crop(lines, r.x, r.y, r.right, r.bottom)
        n = r.height
        text = shotlib.text_of(crop)
        shotlib.save(crop, out)
        return f"{r}\n{text}", n


def run(root: Path, outdir: Path, cls: str, plan: dict, only=None, modes=("camp", "office")):
    for name, (bid, prep) in plan.items():
        if only and name not in only:
            continue
        rows = None
        for mode in modes:
            out = outdir / cls / mode / f"{name}.png"
            out.parent.mkdir(parents=True, exist_ok=True)
            tmp = root.parent / f"{root.name}-hut"
            shutil.rmtree(tmp, ignore_errors=True)
            shutil.copytree(root, tmp, symlinks=True)
            layout(tmp, bid)
            text, rows = asyncio.run(shoot(tmp, bid, mode, out, prep, rows))
            print(f"== {cls}/{mode}/{name}\n{text}")
