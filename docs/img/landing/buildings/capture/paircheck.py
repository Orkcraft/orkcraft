"""Camp and Office of one building must differ only by the mode: compare every row but the frame's title row."""
import re, sys, html
from pathlib import Path


def rows(f):
    t = f.read_text()
    out = {}
    for x, y, ch in re.findall(r'<text x="([\d.]+)" y="([\d.]+)"[^>]*>([^<]*)</text>', t):
        out.setdefault(round(float(y)), []).append((float(x), html.unescape(ch)))
    return ["".join(c for _, c in sorted(r)) for _, r in sorted(out.items())]


bad = 0
for camp in sorted(Path(sys.argv[1]).glob("*/camp/*.svg")):
    office = camp.parent.parent / "office" / camp.name
    a, b = rows(camp)[1:], rows(office)[1:]
    if a != b:
        bad += 1
        diff = [(x, y) for x, y in zip(a, b) if x != y][:2]
        print("DIFF", camp.parent.parent.name, camp.stem, diff)
print("pairs differing beyond the title row:", bad)
