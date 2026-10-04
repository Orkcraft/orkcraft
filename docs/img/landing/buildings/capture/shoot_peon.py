import asyncio, os, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from shootlib import run, Payload

ROOT, OUT = Path(sys.argv[1]), Path(sys.argv[2])
os.environ["PATH"] = f"{ROOT / '.orkcraft' / 'bin'}:{os.environ['PATH']}"


async def barracks(app, view):
    for t in ("T2101 PKCE flow", "T2104 Token TTL", "T2105 Reuse check", "T2103 Rotate keys"):
        view.receive(Payload("text", t, "p_tasks", "tasks.created", t), t, t)
    await asyncio.sleep(0.4)


def lake(app, view):
    view.show_value("branch", "feat/oauth", "feat/oauth")


def council(app, view):
    view.query_one("#team-turns").highlighted = 6


def watch(app, view):
    view.read(view.signals[0])


def crag(app, view):
    view.refresh_data()


PLAN = {
    "task-fields": ("p_tasks", None),
    "barracks": ("p_barracks", barracks),
    "forge": ("p_forge", None),
    "lake-of-insight": ("p_lake", lake),
    "orc-council": ("p_council", council),
    "watchtower": ("p_watch", watch),
    "loot-vault": ("p_loot", None),
    "tally-crag": ("p_crag", crag),
}
run(ROOT, OUT, "peon", PLAN, only=sys.argv[3:] or None)
