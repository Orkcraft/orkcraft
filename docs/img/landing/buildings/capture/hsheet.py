"""Contact sheet of hut pictures: each pair Camp | Office at one height, aspect kept."""
import sys
from pathlib import Path
from PIL import Image, ImageDraw
root, cls, out = Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3])
names = sorted(p.stem for p in (root / cls / "camp").glob("*.png"))
HH, G = 260, 10
rows = []
for n in names:
    ims = [Image.open(root / cls / m / f"{n}.png").convert("RGB") for m in ("camp", "office")]
    ims = [im.resize((round(im.width * HH / im.height), HH)) for im in ims]
    rows.append((n, ims))
W = max(sum(i.width for i in ims) + 3 * G for _, ims in rows)
sheet = Image.new("RGB", (W, len(rows) * (HH + G + 14) + G), (255, 255, 255))
d = ImageDraw.Draw(sheet)
for k, (n, ims) in enumerate(rows):
    y = G + k * (HH + G + 14)
    d.text((G, y), n, fill=(0, 0, 0))
    x = G
    for im in ims:
        sheet.paste(im, (x, y + 12)); x += im.width + G
sheet.save(out)
