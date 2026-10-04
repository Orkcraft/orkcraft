import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from looplib import run

EMITS = [
    ("drum", "calendar.day_schedule", "10:00 Standup · 14:00 Sprint 14 review", "today"),
    ("board", "tasks.status_changed", "Checkout 500 → In Progress", "moves"),
    ("watch", "watch.cron", "09:00 digest", "09:00"),
    ("digest", "catapult.sent", "Sprint 14 status digest · 6 events · 2 blockers", "digest"),
    ("watch", "watch.github", "#41 review waiting 2 d", "github"),
    ("totem", "totem.routed", "#41 review waiting 2 d", "stuck"),
    ("tally", "charts.threshold", "In Progress 7 ≥ 6 (critical)", "overload"),
]
async def prep(app):
    import asyncio
    from orkcraft.screens.typed.crag_view import CragView
    await asyncio.sleep(0.5)
    for v in app.query(CragView):
        v.refresh_data()


run(Path(sys.argv[1]), Path(sys.argv[2]), "lich-daily-status", EMITS, size=(170, 56), prep=prep)
