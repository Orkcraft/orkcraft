"""The HUD's resource counters (🪙 gold = spend, 🪵 lumber = context tokens, 🥩 supply = running orcs)."""
import asyncio, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import shotlib
from rich.cells import cell_len
from orkcraft.app import OrkcraftApp
from orkcraft.widgets.hud import Resources

ROOT = Path(sys.argv[1]); OUT = Path(sys.argv[2])

async def main():
    app = OrkcraftApp(repo_root=ROOT, auto_commit=False, layout_file=ROOT / ".orkcraft.json", demo=True)
    async with app.run_test(size=(120, 30)) as pilot:
        for _ in range(6): await pilot.pause()
        app.refresh_hud = lambda: None                  # keep the demo values on screen
        app._hud.set_resources(Resources(budget=app.scroll.budget, supply=3, supply_max=5, alerts=0, commit=False,
                                         gold="$4.12 / $5.00", gold_level="warn",
                                         lumber="91k / 128k", lumber_level="ok"))
        for _ in range(6): await pilot.pause()
        lines = shotlib.screen_lines(app)
        row = "".join(s.text for s in lines[0])
        start = cell_len(row[:row.index("[🪙")])
        strip = shotlib.trim_right(shotlib.crop(lines, start, 0, app.size.width, 1), keep=0)
        print(shotlib.text_of(strip))
        shotlib.save(strip, OUT / "prev-token-budget.png")
asyncio.run(main())
