import asyncio, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import shotlib
from orkcraft.app import OrkcraftApp
from textual.widgets import OptionList

ROOT = Path(sys.argv[1]); OUT = Path(sys.argv[2])

async def open_max(app, pilot, bid):
    await pilot.press("f2")
    for _ in range(6): await pilot.pause()
    w = app.desktop.get_window(bid)
    app.desktop.focus_window(w); app.set_focus_state("building", building_id=bid)
    for _ in range(6): await pilot.pause(0.1)
    app.desktop.toggle_maximize(w)
    for _ in range(10): await pilot.pause(0.1)
    return w

def content_rows(lines, x0, y0, x1, y1):
    """Drop trailing blank rows of the region."""
    rows = shotlib.crop(lines, x0, y0, x1, y1)
    while rows and not "".join(s.text for s in rows[-1]).strip():
        rows.pop()
    return rows

async def crag():
    app = OrkcraftApp(repo_root=ROOT, auto_commit=False, layout_file=ROOT / ".orkcraft.json", demo=True)
    async with app.run_test(size=(44, 40)) as pilot:
        for _ in range(6): await pilot.pause()
        w = await open_max(app, pilot, "crag")
        from orkcraft.screens.typed.crag_view import CragView
        app.query_one(CragView).refresh_data()
        for _ in range(6): await pilot.pause(0.1)
        lines = shotlib.screen_lines(app)
        h, c = app.query_one("#crag-head").region, app.query_one("#crag-chart").region
        rows = shotlib.trim_right(content_rows(lines, h.x, h.y, h.right, c.bottom))
        print(shotlib.text_of(rows))
        shotlib.save(rows, OUT / "prev-token-budget.png")

async def council():
    app = OrkcraftApp(repo_root=ROOT, auto_commit=False, layout_file=ROOT / ".orkcraft.json", demo=True)
    async with app.run_test(size=(110, 36)) as pilot:
        for _ in range(6): await pilot.pause()
        w = await open_max(app, pilot, "council")
        lst = app.query_one("#team-turns", OptionList)
        lst.highlighted = 6
        for _ in range(6): await pilot.pause(0.1)
        lines = shotlib.screen_lines(app)
        r = lst.content_region
        rows = shotlib.trim_right(content_rows(lines, r.x, r.y, r.right, r.bottom)[1:9])
        print(shotlib.text_of(rows))
        shotlib.save(rows, OUT / "prev-review-sendback.png")

asyncio.run(crag()) if 'crag' in sys.argv[3:] else None; asyncio.run(council()) if 'council' in sys.argv[3:] else None
