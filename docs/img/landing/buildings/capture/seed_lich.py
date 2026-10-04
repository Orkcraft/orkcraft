import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from classes import *
from orkcraft.realm import barracks as bk

ROOT = Path(sys.argv[1])
TASKS = "# Sprint 14\n\n## To Do\n" + "".join(f"- [ ] {t}\n" for t in (
    "OAuth rollout", "Pricing page", "Usage emails", "Audit log", "Billing export", "Invite flow", "SSO spike",
    "Error budget", "Docs refresh")) + "\n## In Progress\n" + "".join(f"- [ ] {t}\n" for t in (
    "Security review OAuth", "Checkout 500", "Tokens v2", "Onboarding copy")) + "\n## Done\n" + "".join(
    f"- [x] {t}\n" for t in ("Stripe webhooks", "Login form", "Hero section", "Session cookie", "Rate limits",
                             "Status page"))
D = dt.date.today()
T = lambda d=0: (D + dt.timedelta(days=d)).strftime("%Y%m%d")
CAL = "\r\n".join(["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//orkcraft//landing//EN"] + [
    line for start, end, title in (
        (f"{T()}T100000", f"{T()}T101500", "Standup"),
        (f"{T()}T113000", f"{T()}T120000", "1:1 · Mira"),
        (f"{T()}T140000", f"{T()}T150000", "Sprint 14 review"),
        (f"{T()}T160000", f"{T()}T170000", "Sprint 15 planning"),
        (f"{T(1)}T100000", f"{T(1)}T101500", "Standup"),
        (f"{T(2)}T150000", f"{T(2)}T160000", "Release v0.9"),
    ) for line in ("BEGIN:VEVENT", f"UID:{start}{title[:3]}@landing", f"DTSTART:{start}", f"DTEND:{end}",
                   f"SUMMARY:{title}", "END:VEVENT")] + ["END:VCALENDAR"]) + "\r\n"

sc = scenario("lich", "Delivery", "💀", [
    typed("l_board", "fields", "Sprint Board", "🌾", "Farmer", "Sprint 14", "tent", path="TASKS.md"),
    typed("vault", "loot", "Loot Vault", "📦", "Quartermaster", "digests and reports", "snow", path="reports"),
    typed("l_crag", "crag", "Tally Crag", "🪨", "Crag Carver", "sprint in bars", "castle", source="tasks",
          orientation="horizontal", window="24h"),
    typed("tower", "watchtower", "Watchtower", "🗼", "Lookout", "escalations", "flag",
          github="delivery-orcs/camp", cron="daily 09:00"),
    typed("l_drum", "war_drum", "War Drum", "🥁", "Drummer", "the day's rhythm", "tent", ics="calendar.ics",
          day_starts="08:00"),
    typed("l_council", "council", "Orc Council", "🔥", "Chieftains", "agrees on plans", "pagoda",
          goal="Sprint 15 plan", members=["Planner:claude", "Critic:agy", "Security:claude"], max_rounds=3,
          budget_usd=2.0),
    typed("l_barracks", "barracks", "Barracks", "🏕️", "Grunts", "agents at work", "tent", max_orcs=2,
          providers=["claude"], budget_usd=5.0),
    typed("l_scrolls", "scrolls", "Scroll Dump", "🗑️", "Scroll Scrapper", "decisions and notes", "gable",
          paths=["notes"]),
], {"TASKS.md": TASKS, "calendar.ics": CAL, "reports/.keep": "",
    "notes/ADR-014 Payments.md": "# ADR-014 Payments\n\n## Decision\nPayments talk to the Ledger only by events.\n",
    "notes/Retro Sprint 13.md": "# Retro · Sprint 13\n\n## Keep\nSmall PRs.\n\n## Change\nReview within a day.\n",
    "notes/1on1 Mira.md": "---\nsubtype: personal\n---\n# 1:1 · Mira\n\nGrowth plan.\n"})
root = build(ROOT, sc)

barracks(root, "l_barracks", [bk.PoolOrc("Smith", "claude", done=5), bk.PoolOrc("Scout", "claude", done=3)], [],
         [bk.PoolTask("t1", "Stripe webhooks", "x", status="done", orc="Smith", result="done")], [])

council(root, "l_council", "Sprint 15 plan", [
    (1, "Planner", "draft", "plan v1 · 11 stories"),
    (1, "Critic", "review", "OBJECT: 11 stories, velocity is 8", False),
    (1, "Security", "review", "OBJECT: no slot for the OAuth audit", False),
    (1, "Moderator", "revise", "plan v2 · 8 stories + audit"),
    (2, "Critic", "review", "AGREE", True),
    (2, "Security", "review", "AGREE", True)], 2, 0.38, outcome="agreed",
    draft="# Sprint 15\n\n1. OAuth audit\n2. Pricing page\n3. Usage emails")

signals(root, "tower", [
    {"at": (NOW - dt.timedelta(minutes=m)).isoformat(), "source": s, "title": t, "body": b}
    for m, s, t, b in ((180, "cron", "09:00 digest", ""), (120, "mail", "Client: launch date?", ""),
                       (64, "github", "Check failed on main", ""),
                       (15, "github", "#41 review waiting 2 d", "Security review OAuth\nno reviewer since Monday"))])
fake_gh(root / ".orkcraft" / "bin", [])
print(root)
