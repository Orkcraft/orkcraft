import asyncio, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import shotlib
from orkcraft.app import OrkcraftApp
from orkcraft import scroll as ts
from orkcraft.screens.console import WarMap, ClanRoster, CommandCard

ROOT = Path(sys.argv[1]); OUT = Path(sys.argv[2]); WHAT = sys.argv[3:]

async def settle(pilot, n=8):
    for _ in range(n): await pilot.pause(0.05)

def rows_of(app, widget, first=0, last=None):
    lines = shotlib.screen_lines(app)
    r = widget.region
    rows = shotlib.crop(lines, r.x, r.y, r.right, r.bottom)
    return rows[first:last]

async def run():
    app = OrkcraftApp(repo_root=ROOT, auto_commit=False, layout_file=ROOT / ".orkcraft.json", demo=True)
    async with app.run_test(size=(120, 44)) as pilot:
        await settle(pilot)
        await pilot.press("f1"); await settle(pilot)
        if "warmap" in WHAT:
            app._console.set_height_pct(60)
            app.desktop.focus_window(app.desktop.get_window("oauth_spire"))
            app.set_focus_state("building", building_id="oauth_spire"); app.refresh_roster(); await settle(pilot)
            app.desktop.set_active(None)
            rows = rows_of(app, app.query_one(WarMap))
            print(shotlib.text_of(rows))
            rows = shotlib.trim_right(rows[:9])
            shotlib.save(rows, OUT / "prev-war-map.png")
        if "overseer" in WHAT:
            b = app.scroll.building("oauth_spire")
            for name, role, status in (("Test Runner", "runs the failing tests", "alert"),
                                       ("Linter", "style and types", "busy"),
                                       ("Scout", "finds related code", "idle")):
                o = ts.add_handler(app.scroll, "oauth_spire", name, role=role)
                o.status = status
            for o in b.garrison.members:
                if o.name == "Shaman": o.status = "busy"
                if o.name == "Reviewer": o.status = "busy"
            app.refresh_roster()
            app.desktop.focus_window(app.desktop.get_window("oauth_spire"))
            app.set_focus_state("building", building_id="oauth_spire"); app.refresh_roster(); await settle(pilot)
            rows = [list(__import__("rich.segment").segment.Segment.divide(r, [1, 999]))[1] for r in rows_of(app, app.query_one(ClanRoster))]
            print(shotlib.text_of(rows))
            from rich.segment import Segment
            # the garrison is 21 columns: one blank column on the right (in each row's own colour) keeps it ≥ 1200 px
            rows = [r + [Segment("  ", r[-1].style)] for r in shotlib.trim_right(rows[:6], keep=1)]
            shotlib.save(rows, OUT / "prev-overseers.png")
        if "command" in WHAT:
            app.set_focus_state("neutral"); app.desktop.set_active(None)
            app.action_toggle_view(); await settle(pilot)
            app._console.set_height_pct(40); app.refresh_roster(); await settle(pilot)
            rows = [list(__import__("rich.segment").segment.Segment.divide(r, [1, 999]))[1] for r in rows_of(app, app.query_one(CommandCard))]
            print(shotlib.text_of(rows))
            shotlib.save(shotlib.trim_right(rows[:8]), OUT / "prev-command-card.png")

asyncio.run(run())
