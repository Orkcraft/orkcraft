"""buildings.json from the approved selection, for the classes shot so far."""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent)); sys.path.insert(0, str(Path(__file__).parent))
from selection import SEL
from alts import ALT
MODE_WORD = {"camp": "Camp mode", "office": "Office mode"}
out = {}
for cls in ("peon", "knight", "elf", "lich"):
    if cls not in ALT:
        continue
    out[cls] = []
    for bid, _btype, title, rts, lines, dogma, _why, _plan in SEL[cls]:
        text = "\n".join(lines)
        assert len(text) <= 170, (cls, bid, len(text))
        alt = ALT[cls][bid]
        out[cls].append({"id": bid, "title": title, "rtsAnalog": rts, "text": text, "dogma": dogma,
                         "media": {m: f"buildings/{cls}/{m}/{bid}.png" for m in ("camp", "office")},
                         "alt": {m: f"{alt} ({MODE_WORD[m]})" for m in ("camp", "office")}})
Path(sys.argv[1]).write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print({k: len(v) for k, v in out.items()})
