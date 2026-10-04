import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from classes import *

ROOT = Path(sys.argv[1])
TASKS = """# Onboarding

## To Do
- [ ] Step 2 · error state
- [ ] Step 3 · empty state

## In Progress
- [ ] Step 2 · loading
- [ ] Hero, 3 variants

## Done
- [x] Step 1 · all 4 states
- [x] Icon set v2
"""
TOKENS = [{"name": "color-primary", "value": "#E8743B"}, {"name": "color-ink", "value": "#1D1A16"},
          {"name": "radius-md", "value": "6px"}, {"name": "space-3", "value": "12px"},
          {"name": "font-body", "value": "Inter 16/24"}]
COPY_OLD = "# Connect bank · error\n\nSomething went wrong.\nPlease try again later.\n\n[ Try again ]\n"
COPY_NEW = "# Connect bank · error\n\nWe couldn't reach your bank.\nTry again, or pick another bank.\n\n[ Try again ]\n"


def hero(letter: str, cta: str) -> str:
    return (f"# Hero · variant {letter.upper()}\n\n"
            "┌────────────────────────┐\n"
            "│  Invoices in one click │\n"
            f"│  [ {cta:<12}]       │\n"
            "└────────────────────────┘\n")


sc = scenario("elf", "Design-Review", "🧝", [
    typed("e_loot", "loot", "Loot Vault", "📦", "Quartermaster", "variants to approve", "snow"),
    typed("e_lake", "lake", "Lake of Insight", "🌊", "Seer", "look and compare", "dome"),
    typed("e_council", "council", "Orc Council", "🔥", "Chieftains", "critique the flow", "pagoda",
          goal="Critique the onboarding flow", members=["Critic:claude", "Accessibility:claude", "Copy:agy"],
          max_rounds=3, budget_usd=1.0),
    typed("e_mill", "mill", "Token Mill", "⚙️", "Miller", "tokens JSON → CSS", "chimney",
          steps=["json", "template: --{name}: {value};", "join"]),
    typed("e_pit", "pit", "The Pit", "🕳️", "Scavenger", "drop references"),
    typed("e_tasks", "fields", "Task Fields", "🌾", "Farmer", "screens and states", "tent", path="TASKS.md"),
    typed("e_scrolls", "scrolls", "Scroll Dump", "🗑️", "Scroll Scrapper", "design guidelines", "gable", paths=["design"]),
    typed("e_forge", "forge", "The Forge", "⚒️", "Smith", "hand off to engineering", "castle", test_cmd="npm test"),
], {"TASKS.md": TASKS, "design/tokens.json": json.dumps(TOKENS, indent=1) + "\n",
    "onboarding/copy.md": COPY_OLD,
    "design/Buttons.md": "# Buttons\n\n## Primary\nOne per screen. Verb first: 'Start free'.\n\n## Secondary\nOutline, never red.\n",
    "design/Spacing.md": "# Spacing\n\n## Scale\n4, 8, 12, 16, 24.\n",
    "design/Voice and tone.md": "# Voice and tone\n\n## Errors\nSay what happened, then what to do.\n",
    "refs/hero-old.png": "png\n", "refs/rival-hero.png": "png\n"})
root = build(ROOT, sc)

branch(root, "copy/error-v2", {"onboarding/copy.md": COPY_NEW}, "error copy v2", 2)
branch(root, "chore/tokens-v2", {"design/tokens.json": json.dumps(TOKENS + [
    {"name": f"color-step-{i}", "value": f"#{i:02d}{i:02d}{i:02d}"} for i in range(10)], indent=1) + "\n"},
       "tokens v2: 64 tokens", 3)
fake_gh(root / ".orkcraft" / "bin", [
    {"number": 7, "state": "OPEN", "headRefName": "chore/tokens-v2", "url": "", "title": "Tokens v2", "isDraft": False},
    {"number": 8, "state": "DRAFT", "headRefName": "copy/error-v2", "url": "", "title": "Error copy v2", "isDraft": True}])

council(root, "e_council", "Critique the onboarding flow", [
    (1, "Critic", "draft", "flow v1 · 4 steps"),
    (1, "Accessibility", "review", "OBJECT: focus jumps to the footer after Try again", False),
    (1, "Copy", "review", "OBJECT: the error text blames the user", False),
    (1, "Moderator", "revise", "sent back → v2"),
    (2, "Accessibility", "review", "AGREE", True),
    (2, "Copy", "review", "AGREE", True)], 2, 0.31, outcome="agreed", draft="flow v2 · focus order fixed, error copy v2")

write(root, "hero-a.md", hero("a", "Get started"))
write(root, "hero-b.md", hero("b", "Start free"))
write(root, "hero-c.md", hero("c", "Try it now"))
print(root)
