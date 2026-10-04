"""Knight's night watch: production → bug → fix → release, and support mail → a drafted reply."""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from classes import *

ROOT = Path(sys.argv[1])
B = [
    typed("watch", "watchtower", "Watchtower", "🗼", "Lookout", "prod, mail, schedule", "flag", cron="every 15m"),
    typed("totem", "totem", "Totem", "🗿", "Spirit Guide", "sorts by rules", "pagoda",
          rules=["bug: matches (?i)sentry|500", "help: matches (?i)refund|invoice", "board: else"]),
    typed("grunts", "barracks", "Barracks", "🏕️", "Grunts", "fixes in worktrees", "tent", max_orcs=2,
          providers=["claude"], budget_usd=5.0),
    typed("smithy", "forge", "The Forge", "⚒️", "Smith", "tests, then merge", "castle", test_cmd="pytest -q"),
    typed("launcher", "catapult", "The Catapult", "🎯", "Loader", "fires the release", "flag",
          url="https://example.com/hooks/deploy", method="POST"),
    typed("replies", "mill", "Reply Mill", "⚙️", "Miller", "drafts support replies", "chimney",
          steps=["lines", "template: Re: {line} — refunded, sorry for the trouble.", "join"]),
    typed("vault", "loot", "Loot Vault", "📦", "Quartermaster", "replies to send", "snow"),
    typed("tally", "crag", "Tally Crag", "🪨", "Crag Carver", "your spend", "castle", source="spend",
          orientation="horizontal", window="24h", warn=1.5, crit=3.0),
    typed("horn", "horn", "The Horn", "📯", "Hornblower", "sounds the alarm", "flag",
          sounds=["charts.threshold: alarm", "*: ding"]),
]
ROADS = [
    ("totem", "watch", "mail.received", "alerts", None, None),
    ("grunts", "totem", "totem.routed", "bug", None, {"route": ["bug"]}),
    ("replies", "totem", "totem.routed", "help", None, {"route": ["help"]}),
    ("smithy", "grunts", "pool.done", "ship", None, None),
    ("launcher", "smithy", "forge.merged", "release", None, None),
    ("vault", "replies", "mill.done", "reply-draft", None, None),
    ("horn", "tally", "charts.threshold", "alarm", None, None),
]
sc = scenario("loop_knight", "Night-Watch", "🗡", B, {}, ROADS)
sc["biome"] = "ice"
sc["layout"] = [(0.0, 0.0, 0.2, 0.4)] * len(B)
root = build(ROOT, sc)
branch(root, "fix/checkout", {"api/checkout.py": "def checkout(cart):\n    return charge(cart)\n"}, "checkout 500", 1)
fake_gh(root / ".orkcraft" / "bin", [{"number": 13, "state": "OPEN", "headRefName": "fix/checkout", "url": "",
                                      "title": "Fix checkout 500", "isDraft": False}])
barracks(root, "grunts", [bk_orc for bk_orc in []], [], [], [])
from orkcraft.realm import barracks as bk
barracks(root, "grunts", [bk.PoolOrc("Smith", "claude", done=4), bk.PoolOrc("Scout", "claude", done=2)], [], [], [])
signals(root, "watch", [
    {"at": (NOW - dt.timedelta(minutes=m)).isoformat(), "source": s, "title": t, "body": ""}
    for m, s, t in ((40, "cron", "Deploy v1.8.0 watch"), (22, "mail", "Refund request · Pro plan"),
                    (6, "mail", "Sentry: 500 /api/checkout"))])
ledger(root, [("grunts", 0.9, 0), ("grunts", 0.8, 0), ("smithy", 0.5, 0), ("replies", 0.0, 0), ("grunts", 0.9, 0)])
p = root / ".orkcraft.json"; d = json.loads(p.read_text())
POS = {"watch": [0.0, 0.0], "totem": [0.25, 0.0], "grunts": [0.5, 0.0], "smithy": [0.75, 0.0], "launcher": [1.0, 0.0],
       "replies": [0.25, 1.0], "vault": [0.5, 1.0], "tally": [0.75, 1.0], "horn": [0.0, 1.0]}
for b in d["buildings"]:
    if b["id"] in POS:
        b["hut"] = POS[b["id"]]
p.write_text(json.dumps(d, ensure_ascii=False, indent=2))
print(root)
