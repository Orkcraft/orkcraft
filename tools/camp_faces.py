"""Cut each ork's face from its role body (docs/design/ork-icons.md §6): the interface's small faces.

    python tools/camp_faces.py              cut every face in the spec (tools/camp_sheets.json `faces`)
    python tools/camp_faces.py --sheet DIR  also write the check sheet (every face at 16 px, in colour and in grey)

`tools/camp_sheet.py` runs it after cutting the sheets, so a recut body recuts its face. For each role the spec
lists (`faces.roles`):

1. its body is `camp/orks/roles/<role>.png` (48 × 56, feet at the bottom centre); the face is the window of
   `faces.rows` over it, 32 wide, centred on the skin of the head (the olive pixels under the headgear);
2. the role's `clear` boxes (in the body's pixels) are emptied first: a held thing that touches the head
   (the Workchief's banner); what is not joined to the head (a staff, a flask) falls away by itself;
3. it is written as `camp/orks/faces/<role>.png`, 32 × 24, and halved into `<role>-16.png`, 16 × 16 (the head's
   16 × 12 at the foot of the frame), the one for list rows. Both at 1×: the interface scales by whole numbers
   (design-system-v2.md §2, §11).

A role with no body yet gets the **plain head** (the `plain` role's head, its headgear taken off: an olive dome
drawn over the brow), never a borrowed role's face (ork-icons.md §6.3). When its body lands in `orks/roles/`,
rerunning this tool gives it its own face; the interface already asks for `faces/<role>.png`
(`js/icons.js` `FACES`). Every face is a placeholder, as its body is (camp/README.md).
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from camp_sheet import AUTHOR, LICENCE, OUT, SPEC, half, label, save  # noqa: E402

W, H = 32, 24                    # the face's frame; the small one is its half, padded to 16 × 16


def skin(img: np.ndarray) -> np.ndarray:
    """The olive of an ork's skin: green clearly over red and blue."""
    r, g, b = (img[..., i].astype(int) for i in range(3))
    return (img[..., 3] > 0) & (g > r + 12) & (g > b + 20)


def face(body: np.ndarray, rows: tuple[int, int], clear: list) -> np.ndarray:
    img = body.copy()
    for x0, y0, x1, y1 in clear:
        img[y0:y1, x0:x1] = 0
    y0, y1 = rows
    win = img[y0:y1]
    ys, xs = np.nonzero(skin(win))
    cx = int(round(np.median(xs)))
    x0 = min(max(cx - W // 2, 0), img.shape[1] - W)
    win = win[:, x0:x0 + W].copy()
    lab, _ = label(win[..., 3] > 0)            # keep what is joined to the head
    keep = set(np.unique(lab[skin(win)])) - {0}
    win[~np.isin(lab, list(keep))] = 0
    xs = np.nonzero(win[..., 3].any(0))[0]                       # the head in the middle of its frame
    shift = (W - 1 - xs.max() - xs.min()) // 2
    return np.roll(win, shift, axis=1)


def bare(head: np.ndarray) -> np.ndarray:
    """The plain head: the headgear above the brow turned to the skin it covered, its outline kept, so the
    head keeps the cap's round shape with nothing on it."""
    out = head.copy()
    sk = skin(out)
    brow = next(y for y in range(H) if sk[y].sum() >= 8)
    tones = out[sk][:, :3]
    lum = tones.astype(int).sum(1)
    mid = np.median(tones[(lum >= np.percentile(lum, 40)) & (lum <= np.percentile(lum, 60))], 0).astype(np.uint8)
    light = tones[lum >= np.percentile(lum, 92)].mean(0).astype(np.uint8)
    outline = tuple(out[out[..., 3] > 0][:, :3][out[out[..., 3] > 0][:, :3].astype(int).sum(1).argmin()])
    opaque = out[..., 3] > 0
    top = int(np.nonzero(opaque.any(1))[0][0])
    for y in range(top, brow + 3):
        for x in range(W):
            if not opaque[y, x] or sk[y, x]:
                continue
            edge = any(not (0 <= y + dy < H and 0 <= x + dx < W and opaque[y + dy, x + dx])
                       for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1)))
            out[y, x, :3] = outline if edge else mid
    for y in range(top + 1, top + 3):                              # a light on the crown, up and to the left
        xs = np.nonzero(opaque[y])[0]
        if len(xs):
            for x in range(xs.min() + 3, xs.min() + 3 + (6 if y == top + 1 else 3)):
                out[y, x, :3] = light
    return out


def small(img: np.ndarray) -> np.ndarray:
    h = half(img)                                                  # 16 × 12
    out = np.zeros((16, 16, 4), np.uint8)
    out[16 - h.shape[0]:] = h
    return out


def cut(spec: dict | None = None) -> list[dict]:
    """Write every face in the spec; return their manifest rows."""
    spec = spec or json.loads(SPEC.read_text(encoding="utf-8"))
    f = spec["faces"]
    rows_ = tuple(f["rows"])
    bodies = {}
    for role in f["roles"]:
        p = OUT / "orks" / "roles" / f"{role}.png"
        if p.exists():
            bodies[role] = np.asarray(Image.open(p).convert("RGBA"))
    clear = f.get("clear", {})
    plain = bare(face(bodies[f["plain"]], rows_, clear.get(f["plain"], [])))
    out = []
    for role in f["roles"]:
        own = role in bodies
        img = face(bodies[role], rows_, clear.get(role, [])) if own else plain
        out += write(role, img, role if own else f["plain"], not own)
    return out + write("plain", plain, f["plain"], True)


def write(name: str, img: np.ndarray, body: str, plain: bool) -> list[dict]:
    """The face and its 16 px half, and their manifest rows."""
    rows = []
    for rel, pic in ((f"orks/faces/{name}.png", img), (f"orks/faces/{name}-16.png", small(img))):
        save(pic, rel)
        rows.append({"file": rel, "size": list(pic.shape[1::-1]), "frame": list(pic.shape[1::-1]), "frames": 1,
                     "anchor": "bottom-centre", "placeholder": True, "source": f"orks/roles/{body}.png",
                     "plain": plain, "licence": LICENCE,
                     "author": AUTHOR.replace("tools/camp_sheet.py", "tools/camp_faces.py")})
    return rows


def check_sheet(roles: list[str], into: pathlib.Path) -> None:
    """Rule 3: every face at 16 px, in colour and in grey, side by side at 4× (and the 32 × 24 above them)."""
    into.mkdir(parents=True, exist_ok=True)
    pad = 4
    big = Image.new("RGBA", (len(roles) * (W + pad) + pad, H + 2 * 16 + 4 * pad), (58, 52, 44, 255))
    for i, role in enumerate(roles):
        x = pad + i * (W + pad)
        a = Image.open(OUT / "orks" / "faces" / f"{role}.png")
        s = Image.open(OUT / "orks" / "faces" / f"{role}-16.png")
        big.paste(a, (x, pad), a)
        big.paste(s, (x + 8, H + 2 * pad), s)
        g = s.convert("LA").convert("RGBA")
        big.paste(g, (x + 8, H + 16 + 3 * pad), g)
    big.resize((big.width * 4, big.height * 4), Image.NEAREST).save(into / "faces-check.png")


def write_manifest(rows: list[dict]) -> None:
    manifest = OUT / "manifest.json"
    m = json.loads(manifest.read_text(encoding="utf-8"))
    m["sprites"] = sorted([r for r in m["sprites"] if not r["file"].startswith("orks/faces/")] + rows,
                          key=lambda r: r["file"])
    manifest.write_text(json.dumps(m, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--sheet", type=pathlib.Path)
    args = ap.parse_args()
    spec = json.loads(SPEC.read_text(encoding="utf-8"))
    rows = cut(spec)
    write_manifest(rows)
    print(f"{len(rows)} faces in {(OUT / 'orks' / 'faces').relative_to(OUT.parent.parent.parent)}")
    if args.sheet:
        bodied = [r for r in spec["faces"]["roles"] if (OUT / "orks" / "roles" / f"{r}.png").exists()]
        check_sheet(bodied + ["plain"], args.sheet)


if __name__ == "__main__":
    main()
