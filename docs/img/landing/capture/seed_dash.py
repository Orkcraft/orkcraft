"""On-brand demo data for the dashboard sandbox copy: a token ledger and a code-review council."""
import datetime as dt, json, sys
from pathlib import Path
from orkcraft.realm import metrics, team as tm

root = Path(sys.argv[1])
# -- Tally Crag: a day of runs, tokens per building ---------------------------------------------
(root / ".orkcraft/ledger.jsonl").unlink(missing_ok=True)
now = dt.datetime.now().replace(second=0, microsecond=0)
runs = [("oauth_forge", 0.9, 61000), ("oauth_forge", 1.1, 74000), ("oauth_spire", 0.4, 28000),
        ("oauth_lab", 0.3, 22000), ("oauth_forge", 0.6, 39000), ("oauth_spire", 0.5, 31000),
        ("oauth_lab", 0.2, 14000), ("oauth_vault", 0.1, 9000), ("oauth_spire", 0.3, 18000),
        ("oauth_vault", 0.1, 6000), ("qa_ground", 0.5, 33000), ("qa_spire", 0.3, 21000),
        ("qa_burrow", 0.2, 12000), ("qa_vault", 0.1, 4000), ("arch_hall", 0.1, 7000)]
for i, (b, cost, tok) in enumerate(runs):
    metrics.record_run(root, b, "done", cost, tok, now=now - dt.timedelta(hours=22 - 1.5 * i, minutes=i))
crag = root / ".orkcraft/buildings/crag.json"
spec = json.loads(crag.read_text()); spec["config"] = {"source": "tokens", "orientation": "horizontal",
                                                       "window": "24h", "warn": 100000, "crit": 150000}
crag.write_text(json.dumps(spec, ensure_ascii=False, indent=2))
# -- Orc Council: a patch reviewed, sent back, reviewed again ----------------------------------
council = root / ".orkcraft/buildings/council.json"
spec = json.loads(council.read_text())
spec["config"] = {"goal": "Review the patch for feat/oauth-flow",
                  "members": ["Smith:claude", "Diff Inspector:claude", "Test Runner:agy"],
                  "max_rounds": 4, "budget_usd": 2.0}
council.write_text(json.dumps(spec, ensure_ascii=False, indent=2))
ddir = root / ".orkcraft/council/council/discussions"
for p in ddir.glob("*.json"):
    p.unlink()
d = tm.new("Review the patch for feat/oauth-flow", "Review the patch for feat/oauth-flow")
d.started, d.outcome, d.round, d.spent = now.isoformat(), "running", 3, 0.62
d.draft = "patch v3 · persist new_family() before minting the refresh token"
d.turns = [
    tm.Turn(1, "Smith", "draft", "patch v1"),
    tm.Turn(1, "Diff Inspector", "review", "OBJECT: new_family() is not persisted", False),
    tm.Turn(1, "Test Runner", "review", "OBJECT: 1 failing: test_refresh_reuse_revokes_family", False),
    tm.Turn(1, "Moderator", "revise", "sent back → v2"),
    tm.Turn(2, "Diff Inspector", "review", "AGREE", True),
    tm.Turn(2, "Test Runner", "review", "OBJECT: still failing: expired code accepted", False),
    tm.Turn(2, "Moderator", "revise", "sent back → v3"),
    tm.Turn(3, "Diff Inspector", "review", "AGREE", True),
]
tm.save(root / ".orkcraft/council/council", d)
print("seeded")
