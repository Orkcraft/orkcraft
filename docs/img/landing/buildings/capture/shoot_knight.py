import asyncio, os, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from shootlib import run, Payload

ROOT, OUT = Path(sys.argv[1]), Path(sys.argv[2])
os.environ["PATH"] = f"{ROOT / '.orkcraft' / 'bin'}:{os.environ['PATH']}"


async def barracks(app, view):
    for t in ("Stripe webhooks", "Fix checkout 500", "Usage emails"):
        view.receive(Payload("text", t, "board", "tasks.status_changed", t), t, t)
    await asyncio.sleep(0.4)


def watch(app, view):
    view.read(view.signals[0])


def crag(app, view):
    view.refresh_data()


def catapult(app, view):
    for src, value, title in (("smithy", "v1.8.0 merged", "build"), ("vault", "launch.md accepted", "notes"),
                              ("board", "Launch post done", "tasks")):
        view.receive(Payload("text", value, src, "x", title), title, value)


PLAN = {
    "launch-board": ("board", None),
    "barracks": ("k_barracks", barracks),
    "tally-crag": ("k_crag", crag),
    "watchtower": ("k_watch", watch),
    "forge": ("smithy", None),
    "loot-vault": ("vault", None),
    "town-hall": ("town_hall", None),
    "catapult": ("k_catapult", catapult),
}
run(ROOT, OUT, "knight", PLAN, only=sys.argv[3:] or None, modes=("camp",) if os.environ.get("CAMP_ONLY") else ("camp", "office"))
