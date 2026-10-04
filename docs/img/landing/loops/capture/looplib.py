"""Shoot a loop camp: the town map with its huts, roads and carts caught mid-road, Camp and Office."""
from __future__ import annotations
import asyncio, os, shutil, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent)); sys.path.insert(0, str(Path(__file__).parent.parent.parent))
import shotlib
import shootlib
from shootlib import settle, _freeze_clock
from orkcraft.app import OrkcraftApp
from orkcraft.realm.pipes import Payload

shotlib.SCALE = 4
shotlib.MARGIN = 4      # ×4 → 16 px


async def shoot(root: Path, mode: str, out: Path, emits, size=(150, 42), ticks=3, prep=None, box=None):
    _freeze_clock()
    os.environ["PATH"] = f"{root / '.orkcraft' / 'bin'}:{os.environ['PATH']}"
    app = OrkcraftApp(repo_root=root, auto_commit=False, layout_file=root / ".orkcraft.json", demo=True)
    async with app.run_test(size=size) as pilot:
        await settle(pilot, 8)
        app.desktop.set_mode(mode)
        app.set_focus_state("neutral"); app.desktop.set_active(None)
        app.desktop.traffic_changed = lambda: None          # carts move only when we tick them
        await settle(pilot, 8)
        app.desktop.traffic.clear()
        if app.desktop._traffic_timer is not None:
            app.desktop._traffic_timer.pause()
        if prep:
            r = prep(app)
            if asyncio.iscoroutine(r):
                await r
        for source, event, value, title in emits:
            app.roads.emit(Payload("text", value, source, event, title))
        for _ in range(ticks):
            app.desktop.traffic.tick()
        app.refresh_roster(); app.desktop.refresh_huts()
        app._console.display = False                      # the War Map strip is not part of the picture
        await settle(pilot, 12)
        if box is None:                                   # Camp sets the frame, Office reuses it
            huts = [h.region for b, h in app.desktop.huts.items() if h.region.width]
            box = (max(0, min(r.x for r in huts) - 2), max(1, min(r.y for r in huts) - 1),
                   min(size[0], max(r.right for r in huts) + 2), max(r.bottom for r in huts) + 1)
        x0, y0, x1, y1 = box
        lines = shotlib.screen_lines(app)
        crop = shotlib.crop(lines, x0, y0, x1, y1)
        shotlib.save(crop, out)
        return shotlib.text_of(crop), box


def run(root: Path, out_dir: Path, name: str, emits, **kw):
    box = None
    for mode in ("camp", "office"):
        tmp = root.parent / f"{root.name}-shot"
        shutil.rmtree(tmp, ignore_errors=True)
        shutil.copytree(root, tmp, symlinks=True)
        out = out_dir / mode / f"{name}.png"
        out.parent.mkdir(parents=True, exist_ok=True)
        text, box = asyncio.run(shoot(tmp, mode, out, emits, box=box, **kw))
        print(f"== {mode}/{name}\n{text}")
