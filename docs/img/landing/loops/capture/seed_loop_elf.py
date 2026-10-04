"""Elf's variants loop: brief → three variants → critique rounds → you look → accept or send back."""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from classes import *
from orkcraft.realm import barracks as bk

ROOT = Path(sys.argv[1])
TOKENS = '[{"name": "color-primary", "value": "#E8743B"}, {"name": "radius-md", "value": "6px"}]\n'
B = [
    typed("pit", "pit", "The Pit", "🕳️", "Scavenger", "briefs and references"),
    typed("grunts", "barracks", "Barracks", "🏕️", "Grunts", "three variants at once", "tent", max_orcs=3,
          providers=["claude"], budget_usd=3.0),
    typed("review", "council", "Orc Council", "🔥", "Chieftains", "critique", "pagoda", goal="Critique the variants",
          members=["Critic:claude", "Accessibility:claude", "Copy:agy"], max_rounds=3, budget_usd=1.0),
    typed("lake", "lake", "Lake of Insight", "🌊", "Seer", "you look here", "dome"),
    typed("vault", "loot", "Loot Vault", "📦", "Quartermaster", "accept or send back", "snow"),
    typed("mill", "mill", "Token Mill", "⚙️", "Miller", "tokens JSON → CSS", "chimney",
          steps=["json", "template: --{name}: {value};", "join"]),
]
ROADS = [
    ("grunts", "pit", "pit.text", "brief", None, None),
    ("review", "grunts", "pool.done", "critique", None, None),
    ("lake", "review", "team.artifact_ready", "look", None, None),
    ("grunts", "vault", "generator.rejected", "send-back", None, None),
    ("mill", "vault", "generator.accepted", "tokens", None, None),
]
sc = scenario("loop_elf", "Variants", "🧝", B, {"design/tokens.json": TOKENS}, ROADS)
sc["biome"] = "ice"
sc["layout"] = [(0.0, 0.0, 0.2, 0.4)] * len(B)
root = build(ROOT, sc)
barracks(root, "grunts", [bk.PoolOrc("Weaver", "claude", done=3), bk.PoolOrc("Artisan", "claude", done=2),
                          bk.PoolOrc("Wordsmith", "claude", done=1)], [], [], [])
write(root, "hero-a.md", "# Hero A\n[ Get started ]\n")
write(root, "hero-b.md", "# Hero B\n[ Start free ]\n")
write(root, "hero-c.md", "# Hero C\n[ Try it now ]\n")
p = root / ".orkcraft.json"; d = json.loads(p.read_text())
POS = {"pit": [0.0, 0.0], "grunts": [0.27, 0.0], "review": [0.55, 0.0], "lake": [1.0, 0.0],
       "vault": [0.27, 1.0], "mill": [0.0, 1.0]}
for b in d["buildings"]:
    if b["id"] in POS:
        b["hut"] = POS[b["id"]]
p.write_text(json.dumps(d, ensure_ascii=False, indent=2))
print(root)
