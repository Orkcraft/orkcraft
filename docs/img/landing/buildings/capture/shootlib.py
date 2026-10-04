"""Shoot a class's buildings: each one maximized in a 56×15 terminal, in Camp and in Office,
cropped to the building's window (56×12 cells), padded to 2.3:1."""
from __future__ import annotations
import asyncio, shutil, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
import shotlib
from PIL import Image
from orkcraft.app import OrkcraftApp
from orkcraft.screens.typed.base import TypedView
from orkcraft.realm.pipes import Payload

W, H = 56, 15


def _slow_work(harness, prompt, workdir, cancel, model, env, resume):
    """The sandbox's simulated orc, kept at work until the picture is taken."""
    if cancel.wait(60):
        raise InterruptedError("stopped")
    return "_(demo — simulated)_", None, None, ""


from orkcraft.screens.typed.pool_view import PoolView
PoolView.work_runner = staticmethod(_slow_work)
RATIO = 2.3


async def settle(pilot, n=8, t=0.05):
    for _ in range(n):
        await pilot.pause(t)


def pad_to_ratio(path: Path) -> None:
    im = Image.open(path).convert("RGB")
    w, h = im.size
    bg = im.getpixel((3, 3))
    if w / h > RATIO:                       # too wide: more room above and below
        nh = round(w / RATIO)
        out = Image.new("RGB", (w, nh), bg); out.paste(im, (0, (nh - h) // 2))
    else:                                   # too tall: more room left and right
        nw = round(h * RATIO)
        out = Image.new("RGB", (nw, h), bg); out.paste(im, ((nw - w) // 2, 0))
    out.save(path)


async def shoot(root: Path, bid: str, mode: str, out: Path | None, prep=None, rows=None) -> str:
    app = OrkcraftApp(repo_root=root, auto_commit=False, layout_file=root / ".orkcraft.json", demo=True)
    async with app.run_test(size=(W, H)) as pilot:
        await settle(pilot, 6)
        app.desktop.set_mode(mode)
        w = app.desktop.get_window(bid)
        app.desktop.focus_window(w); app.set_focus_state("building", building_id=bid)
        await settle(pilot, 4)
        app.desktop.toggle_maximize(w)
        await settle(pilot, 4)
        app.set_focus_state("neutral")
        await settle(pilot, 10)
        found = w.query(TypedView)
        view = found.first() if found else w
        if prep:
            r = prep(app, view)
            if asyncio.iscoroutine(r):
                await r
            await settle(pilot, 12)
        for wd in app.query("*"):                       # no scrollbars in the pictures
            wd.styles.scrollbar_size_vertical = 0
            wd.styles.scrollbar_size_horizontal = 0
        await settle(pilot, 6)
        lines = shotlib.screen_lines(app)
        r = w.region
        crop = shotlib.crop(lines, r.x, r.y, r.right, r.bottom)
        if rows:
            crop = crop[rows[0]:rows[1]]
        text = shotlib.text_of(crop)
        if out is not None:
            shotlib.save(crop, out)
            pad_to_ratio(out)
        return text


def run(root: Path, outdir: Path, cls: str, plan: dict, only=None, modes=("camp", "office")):
    for name, (bid, prep) in plan.items():
        if only and name not in only:
            continue
        for mode in modes:
            out = outdir / cls / mode / f"{name}.png"
            out.parent.mkdir(parents=True, exist_ok=True)
            tmp = root.parent / f"{root.name}-shot"
            shutil.rmtree(tmp, ignore_errors=True)
            shutil.copytree(root, tmp, symlinks=True)          # every shot starts from the same data
            text = asyncio.run(shoot(tmp, bid, mode, out, prep))
            print(f"== {cls}/{mode}/{name}\n{text}")
