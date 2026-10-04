import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from classes import *
from orkcraft.realm import barracks as bk

ROOT = Path(sys.argv[1])
TASKS = """# Launch week

## To Do
- [ ] Launch post and pricing page
- [ ] Product Hunt draft

## In Progress
- [ ] Stripe webhooks
- [ ] Fix checkout 500

## Done
- [x] Landing hero
- [x] Waitlist email
"""
SCHEMA = '{"type": "object", "required": ["smithy", "vault", "board"]}\n'
BILLING_OLD = "".join(f"plan_{i} = 'free'\n" for i in range(40))
sc = scenario("knight", "Solo-SaaS", "🗡", [
    typed("board", "fields", "Launch Board", "🌾", "Farmer", "code, copy and launch", "tent", path="TASKS.md"),
    typed("k_barracks", "barracks", "Barracks", "🏕️", "Grunts", "orcs code while you write", "tent", max_orcs=2,
          providers=["claude"], budget_usd=5.0),
    typed("k_crag", "crag", "Tally Crag", "🪨", "Crag Carver", "your spend", "castle", source="spend",
          orientation="horizontal", window="24h", warn=1.5, crit=3.0),
    typed("k_watch", "watchtower", "Watchtower", "🗼", "Lookout", "after the deploy", "flag",
          github="solo-orcs/saas-camp", cron="every 15m"),
    typed("smithy", "forge", "The Forge", "⚒️", "Smith", "ship to main", "castle", test_cmd="pytest -q"),
    typed("vault", "loot", "Loot Vault", "📦", "Quartermaster", "launch copy to accept", "snow"),
    typed("k_catapult", "catapult", "The Catapult", "🎯", "Loader", "fires the release", "flag",
          url="https://example.com/hooks/release", schema="release.schema.json", method="POST",
          wait_for=["smithy", "vault", "board"]),
], {"TASKS.md": TASKS, "release.schema.json": SCHEMA, "billing/plans.py": BILLING_OLD})
root = build(ROOT, sc)

branch(root, "feat/stripe", {"billing/stripe.py": "".join(f"step_{i} = {i}\n" for i in range(412)),
                             "billing/plans.py": BILLING_OLD.split("plan_37")[0] + "plan_37 = 'pro'\n"},
       "Stripe billing", 2)
branch(root, "fix/checkout", {"api/checkout.py": "def checkout(cart):\n    return charge(cart)\n"}, "checkout 500", 4)
fake_gh(root / ".orkcraft" / "bin", [
    {"number": 12, "state": "OPEN", "headRefName": "feat/stripe", "url": "", "title": "Stripe billing", "isDraft": False},
    {"number": 13, "state": "OPEN", "headRefName": "fix/checkout", "url": "", "title": "Fix checkout 500", "isDraft": False}])

barracks(root, "k_barracks",
         [bk.PoolOrc("Smith", "claude", done=4), bk.PoolOrc("Scout", "claude", done=2)], [],
         [bk.PoolTask("t1", "Landing hero", "x", status="done", orc="Smith", result="hero + tests")], [])

signals(root, "k_watch", [
    {"at": (NOW - dt.timedelta(minutes=m)).isoformat(), "source": s, "title": t, "body": b}
    for m, s, t, b in ((70, "cron", "Deploy v1.8.0 watch", ""), (44, "mail", "Refund request · Pro", ""),
                       (25, "github", "Check 'e2e' failed", ""),
                       (9, "mail", "Sentry: 500 /api/checkout", "StripeInvalidRequest\n14 events in 10 min"))])

ledger(root, [("barracks", 0.9, 0), ("barracks", 0.8, 0), ("forge", 0.5, 0), ("loot", 0.25, 0), ("barracks", 0.5, 0),
              ("forge", 0.4, 0), ("loot", 0.15, 0), ("watchtower", 0.05, 0), ("council", 0.12, 0)])

write(root, "launch.md", "# We launched\n\nInvoices in one click.\nStripe billing, live today.\n")
write(root, "hn.md", "Show HN: invoices in one click\n")
write(root, "ph.md", "# Product Hunt\n\nTagline: invoices in one click.\n")
write(root, "pricing.md", "# Pricing\n\n- Free: 1 project\n- Pro: $12 / month\n")
write(root, ".orkcraft/town/order.json", json.dumps({"prompt": "post every merged PR to the changelog", "domain": "",
                                                     "seen": True, "ts": NOW.isoformat()}))
print(root)
