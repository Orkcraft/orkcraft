import asyncio, os, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from shootlib import Payload
from hutlib import run

ROOT, OUT = Path(sys.argv[1]), Path(sys.argv[2])
os.environ["PATH"] = f"{ROOT / '.orkcraft' / 'bin'}:{os.environ['PATH']}"
DIGEST = ("# Sprint 14 status digest\n\n6 events · 2 blockers\n\n- Security review OAuth waits 2 d\n"
          "- Checkout 500 reopened\n\ncost $0.04")


def loot(app, view):
    view.receive(Payload("text", "week 40 · release notes v0.9", "tower", "x", "Release notes v0.9"), "Release notes v0.9", "")
    view.receive(Payload("text", DIGEST, "tower", "x", "Sprint 14 status digest"), "Sprint 14 status digest", DIGEST)


def watch(app, view):
    view.read(view.signals[0])


async def crag(app, view):
    await asyncio.sleep(0.3)
    view.refresh_data()


async def barracks(app, view):
    for t in ("Pricing page", "Usage emails", "Invite flow"):
        view.receive(Payload("text", t, "l_board", "tasks.status_changed", t), t, t)
    await asyncio.sleep(0.4)
    view.query_one(".typed-detail").scroll_end(animate=False)


def council(app, view):
    view.query_one("#team-turns").highlighted = 2


async def scrolls(app, view):
    await asyncio.sleep(0.3)
    view.find("decision")


PLAN = {
    "sprint-board": ("l_board", None),
    "loot-vault": ("vault", loot),
    "tally-crag": ("l_crag", crag),
    "watchtower": ("tower", watch),
    "war-drum": ("l_drum", None),
    "orc-council": ("l_council", council),
    "barracks": ("l_barracks", barracks),
    "scroll-dump": ("l_scrolls", scrolls),
}
run(ROOT, OUT, "lich", PLAN, only=sys.argv[3:] or None, modes=("camp",) if os.environ.get("CAMP_ONLY") else ("camp", "office"))
