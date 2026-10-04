"""Peon's red-green loop as a camp: the roads are a DAG (orkcraft refuses a loop of roads); the
loop closes inside the Council (rounds) and through git: a red Forge sends the task back to the
orc who wrote it."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from classes import *

ROOT = Path(sys.argv[1])
TASKS = "# Sprint\n\n## To Do\n- [ ] T2104 Token TTL\n\n## In Progress\n- [ ] T2101 PKCE flow\n\n## Done\n- [x] T2100 OAuth client\n"
B = [
    typed("tasks", "fields", "Task Fields", "🌾", "Farmer", "the sprint's queue", "thatch", path="TASKS.md"),
    typed("grunts", "barracks", "Barracks", "🏕️", "Grunts", "orcs in worktrees", "tent", max_orcs=3,
          providers=["claude"], budget_usd=5.0),
    typed("review", "council", "Orc Council", "🔥", "Chieftains", "reviews every patch", "pagoda",
          goal="Review the patch", members=["Diff Inspector:claude", "Test Runner:agy"], max_rounds=4, budget_usd=2.0),
    typed("vault", "loot", "Loot Vault", "📦", "Quartermaster", "verdicts and changelogs", "snow"),
    typed("smithy", "forge", "The Forge", "⚒️", "Smith", "tests, then merge", "castle", test_cmd="pytest -q"),
    typed("tally", "crag", "Tally Crag", "🪨", "Crag Carver", "tokens per building", "castle", source="tokens",
          orientation="horizontal", window="24h", warn=100000, crit=150000),
    typed("horn", "horn", "The Horn", "📯", "Hornblower", "sounds the alarm", "flag",
          sounds=["charts.threshold: alarm", "*: ding"]),
]
ROADS = [
    ("grunts", "tasks", "tasks.status_changed", "in-progress", None, None),
    ("review", "grunts", "pool.done", "review", None, None),
    ("vault", "review", "team.artifact_ready", "verdict", None, None),
    ("grunts", "smithy", "forge.conflict", "red:back-to-orc", None, None),
    ("vault", "smithy", "forge.merged", "changelog", None, None),
    ("horn", "tally", "charts.threshold", "alarm", None, None),
]
sc = scenario("loop_peon", "Red-Green", "⛺", B, {"TASKS.md": TASKS}, ROADS)
sc["biome"] = "ice"
sc["layout"] = [(0.0, 0.0, 0.2, 0.4)] * len(B)
root = build(ROOT, sc)
branch(root, "feat/oauth", {"auth/token.py": "def exchange_code(req):\n    return mint(req)\n"}, "PKCE flow", 2)
fake_gh(root / ".orkcraft" / "bin", [{"number": 41, "state": "OPEN", "headRefName": "feat/oauth", "url": "",
                                      "title": "PKCE flow", "isDraft": False}])
ledger(root, [("smithy", 0.9, 61000), ("smithy", 1.1, 94000), ("review", 0.4, 28000), ("grunts", 0.5, 33000)])
# where the huts stand on the map: a ring that reads left to right, then back
import json
p = root / ".orkcraft.json"; d = json.loads(p.read_text())
POS = {"tasks": [0.0, 0.0], "grunts": [0.34, 0.0], "review": [0.68, 0.0], "vault": [1.0, 0.0],
       "smithy": [0.34, 1.0], "tally": [0.68, 1.0], "horn": [0.0, 1.0]}
for b in d["buildings"]:
    if b["id"] in POS:
        b["hut"] = POS[b["id"]]
p.write_text(json.dumps(d, ensure_ascii=False, indent=2))
print(root)
