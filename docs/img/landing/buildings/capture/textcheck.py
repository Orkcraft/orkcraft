"""Print the text drawn in each SVG (one row per line) and flag anything that looks personal."""
import re, sys, html
from pathlib import Path
BAD = re.compile(r"/tmp|claude-0|(?<!@)@(?!@)|vadim|sidoryk|/home/|https?://|token=|sk-|ghp_", re.I)
hits = 0
for f in sorted(Path(sys.argv[1]).glob("**/*.svg")):
    t = f.read_text()
    rows = {}
    for x, y, ch in re.findall(r'<text x="([\d.]+)" y="([\d.]+)"[^>]*>([^<]*)</text>', t):
        rows.setdefault(float(y), []).append((float(x), html.unescape(ch)))
    text = "\n".join("".join(c for _, c in sorted(r)) for _, r in sorted(rows.items()))
    for m in BAD.finditer(text):
        hits += 1; print("FLAG", f, repr(text[max(0, m.start()-20):m.end()+20]))
print("flags:", hits)
