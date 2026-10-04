import asyncio, os, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from shootlib import run, Payload

ROOT, OUT = Path(sys.argv[1]), Path(sys.argv[2])
os.environ["PATH"] = f"{ROOT / '.orkcraft' / 'bin'}:{os.environ['PATH']}"


def loot(app, view):
    view.accept("hero-b.md")
    view.refresh_data()
    lst = view.query_one("#gen-files")
    ids = [lst.get_option_at_index(i).id for i in range(lst.option_count)]
    if "hero-b.md" in ids:
        lst.highlighted = ids.index("hero-b.md")


def lake(app, view):
    view.show_value("branch", "copy/error-v2", "copy/error-v2")


def council(app, view):
    view.query_one("#team-turns").highlighted = 2


async def mill(app, view):
    view.receive(Payload("file", "design/tokens.json", "e_tasks", "drop.file", "tokens.json"), "tokens.json", "")
    await asyncio.sleep(0.5)
    view.query_one(".typed-detail").scroll_end(animate=False)


def pit(app, view):
    root = view._get_repo_root()
    for item in (str(root / "refs/hero-old.png"), str(root / "refs/rival-hero.png"),
                 "https://moodboard.example/onboarding", "Client: make the CTA warmer"):
        view.drop(item)


async def scrolls(app, view):
    await asyncio.sleep(0.3)
    view.find("errors")


def forge(app, view):
    lst = view.query_one("#git-branches")
    ids = [lst.get_option_at_index(i).id for i in range(lst.option_count)]
    if "chore/tokens-v2" in ids:
        lst.highlighted = ids.index("chore/tokens-v2")


PLAN = {
    "loot-vault": ("e_loot", loot),
    "lake-of-insight": ("e_lake", lake),
    "orc-council": ("e_council", council),
    "token-mill": ("e_mill", mill),
    "the-pit": ("e_pit", pit),
    "task-fields": ("e_tasks", None),
    "scroll-dump": ("e_scrolls", scrolls),
    "forge": ("e_forge", forge),
}
run(ROOT, OUT, "elf", PLAN, only=sys.argv[3:] or None, modes=("camp",) if os.environ.get("CAMP_ONLY") else ("camp", "office"))
