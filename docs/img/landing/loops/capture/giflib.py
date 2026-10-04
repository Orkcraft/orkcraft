"""A 3–5 s animation of a loop camp: the real app runs, carts roll along the roads, the buildings
take the carts and change their status, and one building opens at the end. Frames are taken every
FRAME_S of real time, rendered like the stills, and joined by ffmpeg into a GIF and an MP4."""
from __future__ import annotations
import asyncio, os, shutil, subprocess, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent)); sys.path.insert(0, str(Path(__file__).parent.parent.parent))
import shotlib
import shootlib
from shootlib import settle, _freeze_clock
from orkcraft.app import OrkcraftApp
from orkcraft.realm.pipes import Payload
from orkcraft.screens.typed.pool_view import PoolView

SIM = {"work": "done", "draft": "the patch, revised", "review": "AGREE"}


def _sim_work(harness, prompt, workdir, cancel, model, env, resume):
    """The sandbox's simulated orc: 1.6 s of work, then it reports (SIM["work"])."""
    if cancel.wait(1.6):
        raise InterruptedError("stopped")
    return SIM["work"], None, None, ""


def _sim_council(harness, prompt, model):
    """The sandbox's simulated Council member: the draft, then everyone agrees."""
    return (SIM["review"], None) if "Review it from your role" in prompt else (SIM["draft"], None)


from orkcraft.screens.typed.team_view import TeamView
PoolView.work_runner = staticmethod(_sim_work)
TeamView.runner = staticmethod(_sim_council)
FRAME_S = 0.1


async def record(root: Path, mode: str, size, timeline, seconds: float, box=None):
    _freeze_clock()
    os.environ["PATH"] = f"{root / '.orkcraft' / 'bin'}:{os.environ['PATH']}"
    app = OrkcraftApp(repo_root=root, auto_commit=False, layout_file=root / ".orkcraft.json", demo=True)
    frames = []
    async with app.run_test(size=size) as pilot:
        await settle(pilot, 8)
        app.desktop.set_mode(mode)
        app.set_focus_state("neutral"); app.desktop.set_active(None)
        await settle(pilot, 10)
        app._console.display = False
        await settle(pilot, 4)
        if box is None:
            huts = [h.region for b, h in app.desktop.huts.items() if h.region.width]
            box = (max(0, min(r.x for r in huts) - 2), max(1, min(r.y for r in huts) - 1),
                   min(size[0], max(r.right for r in huts) + 2), max(r.bottom for r in huts) + 1)
        x0, y0, x1, y1 = box
        start = time.monotonic()
        pending = sorted(timeline, key=lambda a: a[0])
        n = round(seconds / FRAME_S)
        for i in range(n):
            t = i * FRAME_S
            while pending and pending[0][0] <= t:
                _, action = pending.pop(0)
                r = action(app)
                if asyncio.iscoroutine(r):
                    await r
            # keep real time: one frame every FRAME_S
            wait = start + (i + 1) * FRAME_S - time.monotonic()
            await pilot.pause(max(0.01, wait))
            app.desktop.refresh_huts()                     # repaint the huts every frame, not every 2 s
            await pilot.pause(0.01)
            frames.append(shotlib.crop(shotlib.screen_lines(app), x0, y0, x1, y1))
    return frames, box


def emit(source, event, value, title):
    return lambda app: app.roads.emit(Payload("text", value, source, event, title))


def open_building(bid):
    def act(app):
        w = app.desktop.get_window(bid)
        app.desktop.focus_window(w)
        app.set_focus_state("building", building_id=bid)
        app._console.display = False
    return act


import re
BAD = re.compile(r"/tmp|/home/|/root|claude-0|6edfe919|scratchpad|vadim|sidoryk|(?<!@)@(?![@~])|add_repo|this session")


def check(frames, name):
    """No frame may show a path of this machine, a session id or an address."""
    for i, f in enumerate(frames):
        m = BAD.search(shotlib.text_of(f))
        if m:
            raise SystemExit(f"{name}: frame {i} shows {m.group(0)!r} — not rendered")


def render(frames, out_base: Path, scale: float = 2.0, hold_last: int = 8):
    tmp = out_base.parent / f".{out_base.name}-frames"
    shutil.rmtree(tmp, ignore_errors=True); tmp.mkdir(parents=True)
    shotlib.SCALE, shotlib.MARGIN = scale, 8
    for i, f in enumerate(frames):
        shotlib.save(f, tmp / f"f{i:03d}.png")
    last = len(frames) - 1
    for k in range(hold_last):                             # hold the last frame a little
        shutil.copy(tmp / f"f{last:03d}.png", tmp / f"f{last + 1 + k:03d}.png")
    fps = round(1 / FRAME_S)
    out_base.parent.mkdir(parents=True, exist_ok=True)
    pal = tmp / "palette.png"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(fps), "-i", str(tmp / "f%03d.png"),
                    "-vf", "scale=iw/2:-1:flags=lanczos,palettegen=max_colors=256:stats_mode=full", str(pal)], check=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(fps), "-i", str(tmp / "f%03d.png"),
                    "-i", str(pal), "-lavfi", "[0:v]scale=iw/2:-1:flags=lanczos[x];[x][1:v]paletteuse=dither=none", "-loop", "0", str(out_base.with_suffix(".gif"))],
                   check=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(fps), "-i", str(tmp / "f%03d.png"),
                    "-vf", "pad=ceil(iw/2)*2:ceil(ih/2)*2", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20",
                    "-movflags", "+faststart", str(out_base.with_suffix(".mp4"))], check=True)
    texts = [shotlib.text_of(f) for f in frames]
    shutil.copy(tmp / "f000.png", out_base.parent / f"{out_base.name}-first.png")
    shutil.copy(tmp / f"f{last:03d}.png", out_base.parent / f"{out_base.name}-last.png")
    shutil.rmtree(tmp)
    return texts


def run(root: Path, out_dir: Path, name: str, timeline, seconds=4.5, size=(150, 42), scale=2.0):
    box = None
    for mode in ("camp", "office"):
        tmp = Path("/srv/camp")                 # a neutral place: a hut may show the paths it was given
        shutil.rmtree(tmp, ignore_errors=True)
        shutil.copytree(root, tmp, symlinks=True)
        frames, box = asyncio.run(record(tmp, mode, size, timeline, seconds, box))
        check(frames, f"{mode}/{name}")
        texts = render(frames, out_dir / mode / name, scale)
        print(f"== {mode}/{name}: {len(frames)} frames")
        for i, t in enumerate(texts):
            keys = [ln.strip() for ln in t.splitlines() if any(k in ln for k in ("active:", "round", "stored:", "status:"))]
            print(f"{mode} t={i * FRAME_S:.1f}", " | ".join(k[:60] for k in keys[:6]))
        yield mode, texts
