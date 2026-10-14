"""Write design-system/previews/CampKitV3.html from its template (tools/campkit_v3.html): the v3 sprites awaited
(tools/camp_sheets_v3.json) and the whole multiple each cut one is shown at (design-system/sprites/v3/manifest.json),
so the preview needs no server. `python tools/camp_sheet.py --v3` runs it after cutting; or `python tools/campkit_v3.py`.
"""
from __future__ import annotations

import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "tools" / "campkit_v3.html"
SPEC = ROOT / "tools" / "camp_sheets_v3.json"
MANIFEST = ROOT / "design-system" / "sprites" / "v3" / "manifest.json"
OUT = ROOT / "design-system" / "previews" / "CampKitV3.html"


def build() -> pathlib.Path:
    spec = json.loads(SPEC.read_text(encoding="utf-8"))
    expected = []
    for sh in spec["sheets"]:
        for g in sh.get("groups", []):
            for item in g["items"]:
                w, h = item.get("size", g["size"])
                expected.append([sh["file"], item["file"], w, h, len(item.get("frames", [item]))])
    rows = json.loads(MANIFEST.read_text(encoding="utf-8"))["sprites"] if MANIFEST.exists() else []
    show = {r["file"]: r.get("show", 1) for r in rows}
    page = TEMPLATE.read_text(encoding="utf-8")
    page = page.replace("%%EXPECTED%%", "[\n" + ",\n".join(json.dumps(e) for e in expected) + "\n]")
    page = page.replace("%%SHOW%%", json.dumps(show, sort_keys=True))
    OUT.write_text(page, encoding="utf-8")
    return OUT


if __name__ == "__main__":
    print(build().relative_to(ROOT))
