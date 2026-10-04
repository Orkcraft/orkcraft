"""The dashboard set of the showcase (T1105 stage 9, camp buildings of T1107): three orkspaces.

    orkcraft --demo --demo-set dashboard

F1 My Day — Task Fields, War Drum, Scroll Dump, File Forest, The Pit and a Watchtower (it shows
how to connect a mailbox; the sandbox has none), with a Daily Brief mill that gets the War Drum's
digest, task moves and what is dropped in the Pit.
F2 Agent Yard — The Forge, a Barracks whose foreman has already hired, a Clan Fire that sent
a plan back once and then let it go, a Loot Vault with changes to review and a Tally Crag over a day of runs.
F4 Library — three LLM wikis the librarian orcs keep (the code, the team, the design), seeded
with pages: tasks from Task Fields pass through the Code Wiki on their way to a Barracks, so each
arrives with the wiki's map; the Clan Fire spot-checks what the librarian wrote and its verdict
lands in reviews.md. One code change is not taken in yet (● on the source).
F3 Gates — The Pit feeds a Totem whose rules send a patch or a link to the Lake of Insight and a
release note out through the Catapult (checked against a schema; the sandbox only dry-runs); a
Workshop built from scratch counts the words of every paste with its approved script; the Horn
sounds a chime for every paste and a horn for every route the Totem takes.
The Town Hall shows the T1108 pipeline seeded: the Council's reviews, 👍 / 👎 with an incident,
a self-improvement proposal and a weekly report.

The sandbox is a real git repository (so the Forge, the Forest and the Loot show real things);
agents never run in it — the Barracks and the Clan Fire answer with simulated text.
"""
from __future__ import annotations

import datetime as dt
import subprocess
from pathlib import Path

SEL = "on_selection_change"
TODAY = dt.date.today()
_T = lambda d=0: (TODAY + dt.timedelta(days=d)).strftime("%Y%m%d")
BRIEF = ("python3 -c \"import sys; t = sys.stdin.read().strip(); "
         "print('### Daily brief' + chr(10) + chr(10) + (t or 'nothing new'))\"")


def typed(bid: str, kind: str, title: str, icon: str, orc: str, role: str, roof: str | None = None, **config) -> dict:
    spec = {"id": bid, "type": kind, "title": title, "icon": icon, "summary": role,
            "orc": {"name": orc, "role": role}}
    if config:
        spec["config"] = config
    if roof:
        spec["roof"] = roof
    return spec


CALENDAR = "\r\n".join(["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//orkcraft//demo//EN"] + [
    line for start, end, title in (
        (f"{_T()}T053000", f"{_T()}T060000", "Morning review (orkcraft)"),
        (f"{_T()}T110000", f"{_T()}T113000", "Standup"),
        (f"{_T()}T150000", f"{_T()}T160000", "Design sync: Town Hall"),
        (f"{_T(1)}T100000", f"{_T(1)}T110000", "Release v0.2"),
        (f"{_T(3)}T090000", f"{_T(3)}T093000", "Dentist"),
    ) for line in ("BEGIN:VEVENT", f"UID:{start}@demo", f"DTSTART:{start}", f"DTEND:{end}", f"SUMMARY:{title}",
                   "END:VEVENT")] + ["END:VCALENDAR"]) + "\r\n"

MY_DAY = {
    "id": "my_day", "name": "My Day", "icon": "🏡", "biome": "forest", "git": {"enabled": False},
    "segment": "Everyone", "story": "A personal dashboard: the day, the tasks, the notes, the mail",
    "nodes": [],
    "files": {
        "TASKS.md": "# My tasks\n\n## To Do\n- [ ] Plan the v0.2 release\n- [ ] Answer Ann about the offsite\n"
                    "- [ ] Renew the domain\n\n## In Progress\n- [ ] Write the Barracks docs\n\n## Done\n"
                    "- [x] Town Hall audit\n- [x] Git building\n",
        "demo/calendar.ics": CALENDAR,
        "docs/handbook/onboarding.md": "# Onboarding\n\n## Your first day\nRead the town map.\n\n## Tools\n- orkcraft\n- git\n",
        "docs/handbook/releases.md": "# Releases\n\n## Versioning\nSemVer.\n\n## Checklist\n- tag\n- changelog\n- announce\n",
        "docs/notes/ideas.md": "# Ideas\n\n## A calendar roof\n## Mail digests at 05:00\n",
        "src/app.py": "def main():\n    print('hello from the demo')\n",
        "src/billing.py": "PRICE = 9\n",
    },
    "buildings": [
        typed("todo", "fields", "Task Fields", "🌾", "Taskmaster", "keeps my three columns", "tiles", path="TASKS.md"),
        typed("days", "war_drum", "War Drum", "🥁", "Drummer", "today and this week", "flag",
              ics="demo/calendar.ics", day_starts="05:00"),
        typed("notes", "scrolls", "Scroll Dump", "🗑️", "Scroll Scrapper", "my handbook and notes", "dome",
              paths=["docs/handbook", "docs/notes"]),
        typed("tree", "forest", "File Forest", "🌲", "Woodcutter", "the source folder", "gable", path="src"),
        typed("drop", "pit", "The Pit", "🕳️", "Scavenger", "drop a file to brief it"),
        typed("post", "watchtower", "Watchtower", "🗼", "Lookout", "my inbox", "chimney",
              host="imap.example.com", user_env="DEMO_MAIL_USER", password_env="DEMO_MAIL_PASSWORD"),
        typed("brief", "mill", "Daily Brief", "⚙️", "Miller", "turns what arrives into a brief", "thatch",
              steps=[f"script: {BRIEF}"]),
    ],
    "layout": [(0.0, 0.0, 0.32, 0.46), (0.34, 0.0, 0.32, 0.46), (0.68, 0.0, 0.32, 0.46),
               (0.0, 0.54, 0.24, 0.46), (0.26, 0.54, 0.16, 0.46), (0.44, 0.54, 0.26, 0.46), (0.72, 0.54, 0.28, 0.46)],
    "roads": [
        ("brief", "days", "calendar.day_schedule", "on_digest", None, None),
        ("brief", "todo", "tasks.status_changed", "on_task_moved", None, None),
        ("brief", "drop", "drop.file", "on_drop", None, None),
    ],
    "payloads": {
        ("days", "calendar.day_schedule"): ("text", f"**{TODAY:%A %d %B}** — 3 events\n\n- 05:30 Morning review\n"
                                                    "- 11:00 Standup\n- 15:00 Design sync", "today"),
        ("todo", "tasks.status_changed"): ("node", "write-the-barracks-docs", "Write the Barracks docs · To Do → In Progress"),
        ("drop", "drop.file"): ("file", "docs/notes/ideas.md", "ideas.md"),
    },
}

AGENT_YARD = {
    "id": "agent_yard", "name": "Agent Yard", "icon": "⚔", "biome": "void", "git": {"enabled": False},
    "segment": "Developers", "story": "Branches, parallel orks, a team that agrees, files to review",
    "nodes": [],
    "files": {},
    "buildings": [
        typed("branches", "forge", "The Forge", "⚒️", "Smith", "branches, PRs, changes", "castle"),
        typed("camp", "barracks", "Barracks", "🏕️", "Grunts", "runs tasks in parallel", "tent",
              max_orcs=3, providers=["claude", "agy"], budget_usd=5.0),
        typed("council", "council", "Clan Fire", "🪔", "Chieftains", "reviews what the Barracks writes", "pagoda",
              steward_prompt="Let a plan go when nobody blocks it; ask me before a release date moves.",
              members=["Product manager:claude", "Architect:agy", "Security:claude"], veto=["Security"],
              max_cycles=3, budget_usd=2.0),
        typed("outputs", "loot", "Loot Vault", "📦", "Quartermaster", "files agents wrote, to review", "snow"),
        typed("crag", "crag", "Tally Crag", "🪨", "Crag Carver", "spend and load", "castle", source="spend",
              warn=2.0, crit=5.0),
    ],
    "layout": [(0.0, 0.0, 0.44, 0.46), (0.56, 0.0, 0.44, 0.46), (0.0, 0.54, 0.3, 0.46), (0.35, 0.54, 0.3, 0.46),
               (0.7, 0.54, 0.3, 0.46)],
    "roads": [
        ("camp", "branches", "git.pr_opened", "on_pr_opened", None, None),
        ("council", "camp", "pool.done", "on_task_done", None, None),
        ("crag", "outputs", "generator.accepted", "on_accepted", None, None),
    ],
    "payloads": {
        ("branches", "git.pr_opened"): ("text", "feature/login: #12 Login form", "feature/login"),
        ("camp", "pool.done"): ("text", "**Login form** — Grub (claude)\n\nform, validation, tests", "Login form"),
        ("outputs", "generator.accepted"): ("file", "docs/release-notes.md", "release-notes.md"),
    },
}

RELEASE_SCHEMA = '{"type": "object", "required": ["notes"], "properties": {"notes": {"type": "string"}}}\n'

GATES = {
    "id": "gates", "name": "Gates", "icon": "🗿", "biome": "ice", "git": {"enabled": False},
    "segment": "Everyone", "story": "What comes in is sorted by rules: a look in the Lake, or out through the Catapult",
    "nodes": [],
    "files": {"demo/release.schema.json": RELEASE_SCHEMA},
    "buildings": [
        typed("gate_pit", "pit", "The Pit", "🕳️", "Scavenger", "drop or paste anything"),
        typed("crossroads", "totem", "Totem", "🗿", "Spirit Guide", "routes by rules", "pagoda",
              rules=["view: matches (?i)diff --git|http", "send: contains release", "view: else"]),
        typed("insight", "lake", "Lake of Insight", "🌊", "Seer", "shows what it is given", "dome"),
        typed("launcher", "catapult", "The Catapult", "🎯", "Loader", "sends releases out", "flag",
              url="https://example.com/hooks/release", schema="demo/release.schema.json", method="POST"),
        typed("counter", "workshop", "Word Count", "🔢", "Tinker", "counts the words of every paste",
              runtime="python", layout="card", inputs=["gate_pit:pit.text"]),
        typed("gate_horn", "horn", "The Horn", "📯", "Hornblower", "sounds what comes in",
              sounds=["pit.text: chime", "crossroads/totem.routed: horn", "*: ding"], quiet="23:00-07:00"),
    ],
    "layout": [(0.0, 0.0, 0.3, 0.46), (0.35, 0.0, 0.3, 0.46), (0.7, 0.0, 0.3, 0.46), (0.0, 0.54, 0.3, 0.46),
               (0.35, 0.54, 0.3, 0.46), (0.7, 0.54, 0.3, 0.46)],
    "roads": [
        ("crossroads", "gate_pit", "pit.text", "on_drop", None, None),
        ("counter", "gate_pit", "pit.text", "on_paste", None, None),
        ("insight", "crossroads", "totem.routed", "view", None, {"route": ["view"]}),
        ("launcher", "crossroads", "totem.routed", "send", None, {"route": ["send"]}),
        ("gate_horn", "gate_pit", "pit.text", "on_paste", None, None),
        ("gate_horn", "crossroads", "totem.routed", "routed", None, None),
    ],
    "payloads": {
        ("gate_pit", "pit.text"): ("text", "diff --git a/src/app.py b/src/app.py\n--- a/src/app.py\n+++ b/src/app.py\n"
                                           "@@ -1 +1 @@\n-print('hello')\n+print('hello, camp')\n", "patch"),
        ("crossroads", "totem.routed"): ("text", "diff --git a/src/app.py b/src/app.py\n--- a/src/app.py\n"
                                                 "+++ b/src/app.py\n@@ -1 +1 @@\n-print('hello')\n+print('hello, camp')\n",
                                         "view"),
    },
}

LIBRARY = {
    "id": "library", "name": "Library", "icon": "📜", "biome": "forest", "git": {"enabled": False},
    "segment": "Developers, managers, designers",
    "story": "Three LLM wikis the orks keep — the code, the team, the design — and tasks that pass through them",
    "nodes": [],
    "files": {
        "LIBRARY_TASKS.md": "# Tasks\n\n## To Do\n- [ ] Show the price tag in the new accent colour\n"
                            "- [ ] Add yearly billing\n\n## In Progress\n\n## Done\n",
        "design/components.md": "# Components (exported from the design file)\n\n## PriceTag\nAmount and currency; "
                                "variants: default, discounted (old price struck through), large.\n\n## CheckoutButton\n"
                                "Primary action; disabled while the payment is pending.\n",
        "design/tokens.md": "# Tokens\n\n- color.accent = #E4572E (was #3A7CA5)\n- color.text = #1B1B1B\n"
                            "- space.m = 12px\n- radius.card = 8px\n",
        "design/decisions.md": "# Decisions\n\n## Accent colour for prices (2026-09-28)\nPrices use color.accent: "
                               "tested better than blue in the checkout study (n=12).\n",
    },
    "buildings": [
        typed("lib_tasks", "fields", "Task Fields", "🌾", "Taskmaster", "what the team asks for", "tiles",
              path="LIBRARY_TASKS.md"),
        typed("code_wiki", "scrolls", "Code Wiki", "📜", "Scroll Scrapper", "the code: modules, flows, decisions",
              "dome", topic="codebase", sources=["code:src", "docs"], council="lib_council"),
        typed("team_wiki", "scrolls", "Team Wiki", "📜", "Scroll Scrapper", "people, process, product", "dome",
              topic="team", sources=["docs/handbook", "docs/notes"]),
        typed("design_wiki", "scrolls", "Design Wiki", "📜", "Scroll Scrapper", "components, screens, decisions, tokens",
              "dome", topic="design", sources=["design"]),
        typed("lib_camp", "barracks", "Barracks", "🏕️", "Grunts", "does the tasks, wiki in hand", "tent",
              max_orcs=2, providers=["claude"], budget_usd=3.0),
        typed("lib_council", "council", "Wiki Clan Fire", "🪔", "Chieftains", "spot-checks fresh wiki pages", "pagoda",
              steward_prompt="Let pages go when they match their sources; send back what is wrong.",
              members=["Reviewer:claude", "Critic:agy"], max_cycles=2, budget_usd=1.0),
    ],
    "layout": [(0.0, 0.0, 0.24, 0.46), (0.27, 0.0, 0.3, 0.46), (0.6, 0.0, 0.4, 0.46),
               (0.0, 0.54, 0.3, 0.46), (0.33, 0.54, 0.3, 0.46), (0.66, 0.54, 0.34, 0.46)],
    "roads": [
        ("code_wiki", "lib_tasks", "tasks.created", "on_task", None, None),
        ("lib_camp", "code_wiki", "knowledge.chunks", "with_the_map", None, None),
    ],
    "payloads": {
        ("lib_tasks", "tasks.created"): ("node", "add-yearly-billing", "Add yearly billing"),
        ("code_wiki", "knowledge.chunks"): ("text", "**Project wiki:** `llm-wiki/codebase/`\n\n**Task:** Add yearly "
                                                    "billing\n\n- [Modules](pages/modules/index.md)", "Add yearly billing"),
    },
}

DASHBOARD_SCENARIOS = [MY_DAY, AGENT_YARD, GATES, LIBRARY]


# -- the repository and the seeded state ----------------------------------------------------------------

def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, text=True)


def prepare(root: Path) -> None:
    """Make the sandbox a git repository with two feature branches, then leave a few files changed
    for the File Generator to review; seed the Barracks and the Council."""
    (root / ".gitignore").write_text(".orkcraft/\n.orkcraft.json\n.orkcraft-demo\n", encoding="utf-8")
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.email", "demo@orkcraft.local")
    _git(root, "config", "user.name", "Orkcraft Demo")
    _seed_wikis(root)
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "demo: the town is founded")
    for branch, path, lines, msg in (("feature/login", "src/login.py", 42, "login form with validation"),
                                     ("fix/parser", "src/parser.py", 7, "parser handles empty lines")):
        _git(root, "checkout", "-q", "-b", branch)
        (root / path).write_text("".join(f"line_{i} = {i}\n" for i in range(lines)), encoding="utf-8")
        _git(root, "add", path)
        _git(root, "commit", "-q", "-m", msg)
        _git(root, "checkout", "-q", "main")
    # what the agents "generated": the File Generator and the File Tree see them
    (root / "docs" / "release-notes.md").write_text("# v0.2\n\n- Town Hall\n- typed buildings\n- roofs\n", encoding="utf-8")
    (root / "src" / "billing.py").write_text("PRICE = 12  # raised by the pricing agent\n", encoding="utf-8")
    _seed_barracks(root)
    _seed_council(root)
    _seed_ledger(root)
    _seed_pipeline(root)


WIKI_PAGES = {
    "codebase": {
        "index.md": "# Index — codebase\n\nThe map of this wiki: read it first, then a section's index, then the pages.\n\n"
                    "- [Architecture](pages/architecture/index.md) — the app in one picture\n"
                    "- [Modules](pages/modules/index.md) — app, billing\n"
                    "- [Flows](pages/flows/index.md) — checkout\n"
                    "- [Decisions](pages/decisions/index.md) — why prices live in billing\n"
                    "- [How-to](pages/how-to/index.md) — release\n",
        "pages/modules/index.md": "# Modules\n\n- [app](app.md) — the entry point\n- [billing](billing.md) — prices and plans\n",
        "pages/modules/app.md": "---\nkind: modules\naliases: [main, entry point]\nsources: [../../src/app.py]\n"
                                "updated: 2026-10-01\nowner: orc\n---\n# app\n\nThe entry point: `main()` prints the "
                                "greeting. Everything else is imported from here.\n",
        "pages/modules/billing.md": "---\nkind: modules\naliases: [pricing, PRICE, plans]\nsources: [../../src/billing.py]\n"
                                    "updated: 2026-10-01\nowner: orc\n---\n# billing\n\nOne monthly plan; `PRICE` is the "
                                    "amount in euros (9). See [the decision](../decisions/prices-in-billing.md).\n",
        "pages/flows/index.md": "# Flows\n\n- [checkout](checkout.md) — from the price tag to a paid plan\n",
        "pages/flows/checkout.md": "---\nkind: flows\naliases: [payment, buy]\nsources: [../../src/billing.py]\n"
                                   "updated: 2026-10-01\nowner: orc\n---\n# Checkout\n\n1. The PriceTag shows "
                                   "[billing](../modules/billing.md)'s `PRICE`.\n2. The CheckoutButton starts the payment.\n",
        "pages/decisions/index.md": "# Decisions\n\n- [prices in billing](prices-in-billing.md) — one place for every price\n",
        "pages/decisions/prices-in-billing.md": "---\nkind: decisions\naliases: [ADR-1]\nsources: [../../docs/handbook/releases.md]\n"
                                                "updated: 2026-10-01\nowner: human\n---\n# Prices live in billing\n\n"
                                                "Every price is read from `billing.py`; nothing else hard-codes an amount.\n",
        "pages/how-to/index.md": "# How-to\n\n- [release](release.md) — tag, changelog, announce\n",
        "pages/how-to/release.md": "---\nkind: how-to\naliases: [ship, publish]\nsources: [../../docs/handbook/releases.md]\n"
                                   "updated: 2026-10-01\nowner: orc\n---\n# Release\n\nSemVer; tag, write the "
                                   "changelog, announce.\n",
        "log.md": "# Log\n\nNewest first.\n\n## 2026-10-01\nTook in src/app.py, src/billing.py, docs/handbook/*: "
                  "added modules/app, modules/billing, flows/checkout, how-to/release.\n",
        "reviews.md": "# Reviews\n\nThe Council's spot-checks, newest first.\n\n## 2026-10-01 — spot-check\n\n"
                      "billing.md: OK. checkout.md: name the PriceTag variant the checkout uses.\n",
        "lint.md": "# Lint 2026-10-01\n\n- pages/modules/app.md: no page links to it — link it from architecture\n",
    },
    "team": {
        "index.md": "# Index — team\n\n- [Process](pages/process/index.md) — how we release\n"
                    "- [Onboarding](pages/onboarding/index.md) — your first day\n- [Product](pages/product/index.md) — ideas\n",
        "pages/process/index.md": "# Process\n\n- [releases](releases.md) — versioning and the checklist\n",
        "pages/process/releases.md": "---\nkind: process\naliases: [shipping]\nsources: [../../docs/handbook/releases.md]\n"
                                     "updated: 2026-10-01\nowner: orc\n---\n# Releases\n\nSemVer. Checklist: tag, "
                                     "changelog, announce.\n",
        "pages/onboarding/index.md": "# Onboarding\n\n- [first day](first-day.md) — read the town map\n",
        "pages/onboarding/first-day.md": "---\nkind: onboarding\nsources: [../../docs/handbook/onboarding.md]\n"
                                         "updated: 2026-10-01\nowner: human\n---\n# Your first day\n\nRead the town "
                                         "map, then pair with someone on a real task. (Written by people: the ork only "
                                         "suggests changes here.)\n",
        "pages/product/index.md": "# Product\n\n- [ideas](ideas.md) — a calendar roof, mail digests\n",
        "pages/product/ideas.md": "---\nkind: product\nsources: [../../docs/notes/ideas.md]\nupdated: 2026-10-01\n"
                                  "owner: orc\n---\n# Ideas\n\nA calendar roof; mail digests at 05:00.\n",
        "proposals.md": "# Proposals\n\n- pages/onboarding/first-day.md: mention the tools list (orkcraft, git) "
                        "from docs/handbook/onboarding.md\n",
    },
    "design": {
        "index.md": "# Index — design\n\n- [Components](pages/components/index.md) — PriceTag, CheckoutButton\n"
                    "- [Screens](pages/screens/index.md) — checkout\n- [Decisions](pages/decisions/index.md) — accent "
                    "for prices\n- [Tokens](pages/tokens/index.md) — colours, spacing\n",
        "pages/components/index.md": "# Components\n\n- [PriceTag](price-tag.md) — amount + currency\n"
                                     "- [CheckoutButton](checkout-button.md) — the primary action\n",
        "pages/components/price-tag.md": "---\nkind: components\naliases: [PriceTag, price, formatPrice]\n"
                                         "sources: [../../design/components.md]\nupdated: 2026-10-01\nowner: orc\n---\n"
                                         "# PriceTag\n\nAmount and currency in `color.accent`. Variants: default, "
                                         "discounted, large. Used on [checkout](../screens/checkout.md).\n",
        "pages/components/checkout-button.md": "---\nkind: components\naliases: [CheckoutButton, pay button]\n"
                                               "sources: [../../design/components.md]\nupdated: 2026-10-01\nowner: orc\n"
                                               "---\n# CheckoutButton\n\nPrimary; disabled while the payment is pending.\n",
        "pages/screens/index.md": "# Screens\n\n- [checkout](checkout.md) — PriceTag + CheckoutButton\n",
        "pages/screens/checkout.md": "---\nkind: screens\naliases: [payment screen]\nsources: [../../design/components.md]\n"
                                     "updated: 2026-10-01\nowner: orc\n---\n# Checkout\n\nThe plan, its "
                                     "[PriceTag](../components/price-tag.md) and the [CheckoutButton](../components/checkout-button.md).\n",
        "pages/decisions/index.md": "# Decisions\n\n- [accent for prices](accent-for-prices.md) — orange beat blue\n",
        "pages/decisions/accent-for-prices.md": "---\nkind: decisions\nsources: [../../design/decisions.md]\n"
                                                "updated: 2026-10-01\nowner: orc\n---\n# Accent colour for prices\n\n"
                                                "Prices use `color.accent` (#E4572E): it tested better than blue (n=12).\n",
        "pages/tokens/index.md": "# Tokens\n\n- [colours](colors.md) — accent, text\n- [spacing](spacing.md) — m, radius\n",
        "pages/tokens/colors.md": "---\nkind: tokens\naliases: [color.accent, color.text, palette]\n"
                                  "sources: [../../design/tokens.md]\nupdated: 2026-10-01\nowner: orc\n---\n# Colours\n\n"
                                  "| token | value | role |\n|---|---|---|\n| color.accent | #E4572E | prices, highlights |\n"
                                  "| color.text | #1B1B1B | body text |\n",
        "pages/tokens/spacing.md": "---\nkind: tokens\naliases: [space.m, radius.card]\nsources: [../../design/tokens.md]\n"
                                   "updated: 2026-10-01\nowner: orc\n---\n# Spacing\n\nspace.m = 12px; radius.card = 8px.\n",
    },
}


def _seed_wikis(root: Path) -> None:
    """The three wikis of the Library, as their librarians would have left them: pages, maps, a log,
    reviews and proposals, and a manifest of what each has taken in (before the demo's last changes)."""
    from orkcraft.realm import wiki
    from orkcraft.sources import lore
    for spec in LIBRARY["buildings"]:
        if spec["type"] != "scrolls":
            continue
        cfg = spec["config"]
        topic = cfg["topic"]
        wroot = wiki.root_of(root, None, topic)
        wiki.scaffold(wroot, topic)
        for rel, text in WIKI_PAGES[topic].items():
            (wroot / rel).parent.mkdir(parents=True, exist_ok=True)
            (wroot / rel).write_text(text, encoding="utf-8")
        lib = lore.Library(lore.from_config(cfg, root))
        lib.scan()
        prints = wiki.Fingerprints(root)
        wiki.save_manifest(wroot, {n.path: prints.of(n) for n in lib.notes()})


WORD_COUNT = """import json, sys

cart = json.load(sys.stdin)
words = cart.get("value", "").split()
if not words:
    sys.exit(3)                       # nothing to count: the steward would say what it is
print(json.dumps({"words": len(words), "lines": cart.get("value", "").count(chr(10)) + 1, "first": words[0][:20]}))
sys.exit(4 if len(words) > 400 else 0)
"""


def _seed_pipeline(root: Path) -> None:
    """T1108: the Workshop's approved script and blueprint, the Council's reviews, 👍 / 👎 with an
    incident, a waiting self-improvement proposal and a weekly report — what the Town Hall shows."""
    import json

    from orkcraft.realm import fastpath, feedback, optimize, weekly, workshop
    now = dt.datetime.now().replace(microsecond=0)
    mocks = [workshop.cart("pit.text", "gate_pit", "release notes for v0.2"), workshop.cart("pit.text", "gate_pit", "")]
    workshop.save_script(root, "counter", "python", WORD_COUNT)
    workshop.save_blueprint(root, "counter", {"id": "counter", "title": "Word Count", "runtime": "python",
                                              "layout": "card", "inputs": ["gate_pit:pit.text"], "mocks": mocks,
                                              "purpose": "count the words of what I paste into the pit"})
    for kind, bid, decision, notes in (
            ("building", "counter", "approved", []),
            ("road", "gate_pit->crossroads", "approved", []),
            ("building", "fetcher", "rejected", [{"role": "warder", "severity": "block",
                                                   "text": "mill step pipes the network into a shell: curl x | sh"}]),
            ("agent", "Summariser", "overridden", [{"role": "chief", "severity": "object",
                                                     "text": "a chain could keep only the failed checks"}])):
        path = root / fastpath.COUNCIL_DIR / "reviews.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": now.isoformat(), "kind": kind, "id": bid, "decision": decision, "model": "haiku",
                                "cost_usd": 0.001, "error": "", "notes": notes}) + "\n")
    feedback.record_output(root, "counter", "workshop.done", '{"words": 5, "lines": 1, "first": "release"}')
    feedback.like(root, "counter")
    feedback.record_output(root, "brief", "mill.done", "### Daily brief\n\nnothing new")
    scroll = type("S", (), {"buildings": [type("B", (), {"id": "brief", "roads": [type("R", (), {"source": "days"})()]})()]})()
    feedback.dislike(root, scroll, "brief", "inputs", "the War Drum sent yesterday's schedule")
    optimize.save(root, optimize.Proposal("demo1", now.isoformat(), "camp", "shrink", "orders",
                                          "Work through every task carefully, explain each change in detail, …",
                                          "Do the task; list changed files; one-line summary.",
                                          "the same job in a third of the words", "~60 % input tokens", 41000))
    weekly.save(root, weekly.Report(now.isoformat(), "The Barracks spends most of the week; the Tally Crag "
                                    "warns too early.", [
        weekly.Item(1, "Shorter Barracks orders", "same job, fewer words", "shrink", "camp", {"target": "orders"}),
        weekly.Item(2, "Warn at $3", "$2 fires every day", "set_config", "crag", {"key": "warn", "value": 3.0}),
        weekly.Item(3, "Try a Totem before the Lake", "advice", "note")], "opus", 1.4))


def _seed_ledger(root: Path) -> None:
    """A day of runs, so the Tally Crag has something to carve."""
    from orkcraft.realm import metrics
    now = dt.datetime.now().replace(second=0, microsecond=0)
    for i, (h, b, cost, out) in enumerate(((22, "camp", 0.4, "done"), (19, "council", 0.24, "done"),
                                            (15, "camp", 0.9, "done"), (12, "camp", 0.3, "error"),
                                            (8, "brief", 0.0, "done"), (5, "camp", 1.1, "done"),
                                            (2, "council", 0.5, "done"), (1, "camp", 0.6, "done"))):
        metrics.record_run(root, b, out, cost, int(cost * 40000), now=now - dt.timedelta(hours=h, minutes=i))


def _seed_barracks(root: Path) -> None:
    from orkcraft.realm import barracks as bk
    st = bk.Barracks(root / ".orkcraft" / "barracks" / "camp")
    st.orcs = [bk.PoolOrc("Grub", "claude", keys=["T1042"], done=3, last="2026-10-02T05:20:00", hired="2026-10-02T05:00:00"),
               bk.PoolOrc("Mogka", "agy", bk.AGY_CODE, done=1, failed=1, last="2026-10-02T05:25:00",
                          hired="2026-10-02T05:05:00")]
    st.queue = [bk.PoolTask("q1", "Docs for the API", "Write the API docs", "", "2026-10-02T05:30:00")]
    st.tasks = [bk.PoolTask("t1", "T1042 login form", "x", "T1042", status="done", orc="Grub", result="form + tests"),
                bk.PoolTask("t2", "Fix the parser", "x", status="failed", orc="Mogka", error="tests failed")]
    st.stats = {"claude": {"runs": 3, "ok": 3, "cost": 0.9}, f"agy:{bk.AGY_CODE}": {"runs": 2, "ok": 1, "cost": 0.1}}
    st.save()
    for d in (bk.Decision("2026-10-02T05:00:00", "t1", "hire", "Grub", "0/3 orks busy → hire; claude: no record yet; fits a code task"),
              bk.Decision("2026-10-02T05:05:00", "t2", "hire", "Mogka", "1/3 orks busy → hire; agy: no record yet"),
              bk.Decision("2026-10-02T05:21:00", "t3", "follow-up", "Grub", "T1042 was Grub's"),
              bk.Decision("2026-10-02T05:30:00", "q1", "queue", "", "paused for the night")):
        st.log(d)


def _seed_council(root: Path) -> None:
    from orkcraft.realm import team as tm
    plan = ("# v0.2 release plan\n\n1. Freeze features on Monday\n2. Run the secret scan on the wheel\n"
            "3. Tag and sign `v0.2.0`\n4. Publish to PyPI\n5. Roll back: yank and re-tag if the smoke test fails\n"
            "6. The operator announces")
    first = tm.new("v0.2 release plan", "# v0.2 release plan\n\n1. Freeze\n2. Tag\n3. Publish\n4. Announce")
    first.started, first.ended, first.outcome, first.spent = "2026-10-02T05:10:00", "2026-10-02T05:13:00", "rework", 0.14
    first.decision = "1. Sign the release and scan the wheel (Security's veto).\n2. Add a rollback step.\n3. Name who announces."
    first.turns = [tm.Turn("Product manager", "review", "1. Who announces?", "changes"),
                   tm.Turn("Architect", "review", "1. No rollback step.", "changes"),
                   tm.Turn("Security", "review", "An unsigned, unscanned wheel must not ship.", "veto"),
                   tm.Turn("Steward", "decide", first.decision, "rework")]
    second = tm.new("v0.2 release plan", plan, cycle=2)
    second.started, second.ended, second.outcome, second.spent = "2026-10-02T05:40:00", "2026-10-02T05:42:00", "approved", 0.1
    second.decision = "Every point of the first review is answered; Security approves."
    second.turns = [tm.Turn("Product manager", "review", "", "approve"), tm.Turn("Architect", "review", "", "approve"),
                    tm.Turn("Security", "review", "Signed and scanned — fine.", "approve"),
                    tm.Turn("Steward", "decide", second.decision, "approve")]
    folder = root / ".orkcraft" / "council" / "council"
    tm.save(folder, first)
    tm.save(folder, second)


def payload_of(sc: dict, source: str, event: str):
    from orkcraft.realm.pipes import Payload
    kind, value, title = sc["payloads"][(source, event)]
    return Payload(kind, value, source, event, title)

