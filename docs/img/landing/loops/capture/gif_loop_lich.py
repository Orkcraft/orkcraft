import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import giflib
from giflib import run, emit, open_building

giflib.SIM["draft"] = "Unblock #41: Mira reviews today, Smith pairs at 15:00"


async def crag_refresh(app):
    from orkcraft.screens.typed.crag_view import CragView
    for v in app.query(CragView):
        v.refresh_data()


TIMELINE = [
    (0.0, crag_refresh),
    (0.3, emit("drum", "calendar.day_schedule", "10:00 Standup · 14:00 Sprint 14 review", "today")),
    (0.6, emit("board", "tasks.status_changed", "Checkout 500 → In Progress", "moves")),
    (0.9, emit("watch", "watch.cron", "09:00 digest", "09:00")),
    (1.4, emit("watch", "watch.github", "#41 review waiting 2 d", "github")),
    (1.8, emit("tally", "charts.threshold", "In Progress 7 ≥ 6 (critical)", "overload")),
    (4.0, open_building("review")),
]
for mode, texts in run(Path(sys.argv[1]), Path(sys.argv[2]), "lich-daily-status", TIMELINE, seconds=5.0, size=(170, 56)):
    print(f"--- {mode} last\n" + "\n".join(texts[-1].splitlines()[:16]))
