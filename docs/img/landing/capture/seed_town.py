"""Lay the Feat-OAuth huts out as a compact triangle: the Forge feeds the Scrying Spire and the Alchemy Lab."""
import json, sys
from pathlib import Path
p = Path(sys.argv[1]) / ".orkcraft.json"
d = json.loads(p.read_text())
pos = {"oauth_forge": [float(sys.argv[2]), 0.45], "oauth_spire": [float(sys.argv[3]), float(sys.argv[4])],
       "oauth_lab": [float(sys.argv[3]), float(sys.argv[5])], "oauth_vault": [0.9, 0.05]}
for b in d["buildings"]:
    if b["id"] in pos:
        b["hut"] = pos[b["id"]]
p.write_text(json.dumps(d, ensure_ascii=False, indent=2))
