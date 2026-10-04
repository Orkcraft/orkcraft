"""Contact sheet: every building of a class, camp | office, at 390 px wide."""
import sys
from pathlib import Path
from PIL import Image, ImageDraw
root, cls, out = Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3])
names = sorted(p.stem for p in (root / cls / "camp").glob("*.png"))
W = 390; H = round(W / 2.3); G = 8
sheet = Image.new("RGB", (2 * W + 3 * G, len(names) * (H + G + 14) + G), (255, 255, 255))
d = ImageDraw.Draw(sheet)
for i, n in enumerate(names):
    y = G + i * (H + G + 14)
    d.text((G, y), n, fill=(0, 0, 0))
    for j, mode in enumerate(("camp", "office")):
        im = Image.open(root / cls / mode / f"{n}.png").convert("RGB").resize((W, H))
        sheet.paste(im, (G + j * (W + G), y + 12))
sheet.save(out)
