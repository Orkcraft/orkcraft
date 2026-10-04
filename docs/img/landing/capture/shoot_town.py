import asyncio, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import shotlib
from orkcraft.app import OrkcraftApp
from orkcraft.demo.scenarios import SCENARIOS
from orkcraft.demo.screens import _payload

ROOT = Path(sys.argv[1]); OUT = Path(sys.argv[2]); W, H = int(sys.argv[3]), int(sys.argv[4]); TICKS = int(sys.argv[5])

async def main():
    app = OrkcraftApp(repo_root=ROOT, auto_commit=False, layout_file=ROOT / ".orkcraft.json", demo=True)
    async with app.run_test(size=(W, H)) as pilot:
        for _ in range(5): await pilot.pause()
        app.desktop.traffic_changed = lambda: None
        await pilot.press("f1")
        for _ in range(4): await pilot.pause()
        app.desktop.traffic.clear()
        if app.desktop._traffic_timer is not None:
            app.desktop._traffic_timer.pause()
        app.desktop.set_active(None); app.set_focus_state("neutral")
        sc = SCENARIOS[0]
        for target, source, event, *_ in sc["roads"]:
            app.roads.emit(_payload(sc, source, target, event, 0))
        for _ in range(TICKS):
            app.desktop.traffic.tick()
        app.refresh_roster(); app.desktop.refresh_huts()
        for _ in range(6): await pilot.pause()
        lines = shotlib.screen_lines(app)
        for i, l in enumerate(shotlib.text_of(lines).split("\n")):
            print(f"{i:2d} {l}")
        shotlib.save(lines, OUT / f"town-{W}x{H}-{TICKS}.png")
        if len(sys.argv) > 6:
            x0, y0, x1, y1 = map(int, sys.argv[6:10])
            shotlib.save(shotlib.crop(lines, x0, y0, x1, y1), OUT / "prev-war-map.png")
asyncio.run(main())
