"""The sprites of growth and of the biomes, drawn from code so they never drift (docs/design/growth.md,
docs/design/war-map.md):

    python tools/growth_sprites.py

- `design-system/sprites/mascots/<role>-<stage>.png` (and `@2x`): the operator's mascot, a head on the
  landing's 12 × 11 class grid per onboarding role, each of its four stages adding its own headgear or
  prop (a red bandana, then a horned helm; a keyword tag, then rating stars…), never a crown: the crown
  is the Warchief's.
- `design-system/sprites/flags/`: a building's renown and goal, drawn at the header sprites' scale (2 px
  a pixel). `level-<n>.png`, the flag on its roof at I–III (ivory, taller at II, gold at III; the pole's
  foot at the bottom left, `js/icons.js` `FLAG_AT` says where on each roof it stands); `footing-<n>.png`,
  a tile of the stones under it, a course more at each level; `annex-thrift.png` (a lean-to over a stack
  of logs) and `annex-quality.png` (a crystal on a whetstone), beside it by its goal. Balance has none.
- `design-system/sprites/buildings/<type>/header-<biome>.png` (and `@2x`): each flat header redrawn
  for ice (snow on the edges facing the sky), dust (sun-bleached sandstone, sand at the foot), void (ashen violet)
  lava (ash-grey basalt, embers at the foot) and meadow (spring green, daisies at the foot). Dirt and forest keep
  `header.png`.

Needs Pillow.
"""
from __future__ import annotations

import pathlib

from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parent.parent
SPRITES = ROOT / "design-system" / "sprites"

# -- the palette: the ork mark's flat colours (building-sprites.md) and the kins' skins --------------------
GREEN, DARK_GREEN, IVORY, GOLD, NIGHT = "#86c062", "#628a4c", "#ece4cf", "#e8b94a", "#1a1813"


def rgb(hex_: str) -> tuple[int, int, int, int]:
    return tuple(int(hex_[i:i + 2], 16) for i in (1, 3, 5)) + (255,)


def grid_image(grid: list[str], colours: dict[str, str], k: int) -> Image.Image:
    img = Image.new("RGBA", (len(grid[0]) * k, len(grid) * k), (0, 0, 0, 0))
    for y, row in enumerate(grid):
        for x, c in enumerate(row):
            if c not in ". ":
                img.paste(rgb(colours[c]), (x * k, y * k, (x + 1) * k, (y + 1) * k))
    return img


def save_pair(img1x: Image.Image, path: pathlib.Path) -> None:
    """`img1x` at the sprite's own scale, and its @2x by nearest neighbour."""
    path.parent.mkdir(parents=True, exist_ok=True)
    img1x.save(path)
    img1x.resize((img1x.width * 2, img1x.height * 2), Image.NEAREST).save(path.with_name(path.stem + "@2x.png"))


# -- the mascots ---------------------------------------------------------------------------------------
# The operator's mascot by role (realm/intents.py `ROLES`) and stage: a head on the 12 × 11 grid of the
# landing's class sprites, each stage adding its own headgear or prop. A grid is a base head and an
# overlay: '.' keeps the base, '_' clears it. Never a crown: the crown is the Warchief's.

PALETTE = {
    "K": "#1a1813",                                   # eyes, mouths, outlines
    "I": "#ece4cf",                                   # ivory: tusks, teeth, beards, bone
    "G": "#e8b94a", "Y": "#facc15", "W": "#a8781e",   # gold, bright gold, gold shade
    "R": "#e8411c", "r": "#8a1f10", "O": "#ff8c1a",   # red, dark red, orange
    "L": "#3fb950", "l": "#2a7a3a",                   # leaf green, its shade
    "B": "#3b6fd8", "b": "#82aaff", "c": "#cfe9ff",   # blue, light blue, glass
    "P": "#c084fc", "p": "#6b5a7e", "q": "#3e3352",   # purple, plum, deep plum
    "M": "#9aa0a8", "m": "#5e646c", "H": "#d7dbe0",   # metal, dark metal, highlight
    "t": "#8a5a32", "T": "#4e3420",                   # leather, dark leather
    "k": "#f29ac0",                                   # pink plume
    "o": "#86c062", "d": "#5d8a40",                   # ork skin, its brows
    "g": "#a8c040",                                   # goblin
    "n": "#e3b58c", "N": "#c99a74",                   # gnome skin, nose
    "e": "#eadcc2",                                   # elf skin
    "h": "#e8c76a", "j": "#b08a3a",                   # blonde hair, its shade
    "a": "#a8552e", "A": "#6e3418",                   # auburn hair, its shade
    "v": "#8e88a8",                                   # lich
    "w": "#c4ced8", "x": "#5f6f80",                   # wraith face, its hood
    "s": "#fffbe6",                                   # lamp light
    "z": "#3b8f8f",                                   # visor green
}

BASES = {
    "orc": ["............",
            "............",
            "............",
            "...oooooo...",
            "o.oooooooo.o",
            "oooddooddooo",
            ".ooKKooKKoo.",
            "..oooooooo..",
            "..oIooooIo..",
            "..oIooooIo..",
            "...oooooo..."],
    "goblin": ["............",
               "............",
               "............",
               "...gggggg...",
               "gg.gggggg.gg",
               ".gggggggggg.",
               "..gKKggKKg..",
               "..gggggggg..",
               "..gKIKIKIg..",
               "...gggggg...",
               "............"],
    "gnome": ["............",
              "............",
              "............",
              "..nnnnnnnn..",
              ".nnnnnnnnnn.",
              ".nnKKnnKKnn.",
              ".nnnnNNnnnn.",
              ".InnnNNnnnI.",
              ".IIInnnnIII.",
              "..IIIIIIII..",
              "...IIIIII..."],
    "elf": ["............",
            "............",
            "....eeee....",
            "...eeeeee...",
            "..eeeeeeee..",
            "eeeeeeeeeeee",
            ".eeKKeeKKee.",
            "..eeeeeeee..",
            "..eeeeeeee..",
            "...eeKKee...",
            "....eeee...."],
    "lich": ["............",
             "...vvvvvv...",
             "..vvvvvvvv..",
             ".vvvvvvvvvv.",
             ".vKKKvvKKKv.",
             ".vvvvvvvvvv.",
             "..vvvKKvvv..",
             "..vIvIvIvv..",
             "...vvvvvv...",
             "............",
             "............"],
    "wraith": ["............",
               "....xxxx....",
               "..xxxxxxxx..",
               ".xxwwwwwwxx.",
               ".xwwwwwwwwx.",
               ".xwKKwwKKwx.",
               ".xwwwwwwwwx.",
               ".xwwwKKwwwx.",
               "..xwwwwwwx..",
               "..xwxwwxwx..",
               "...x.ww.x..."],
    "knight": ["............",
               "............",
               "............",
               "...MMMMMM...",
               "..MMMMMMMM..",
               ".MMMMMMMMMM.",
               ".MMKKKKKKMM.",
               ".MMMMMMMMMM.",
               ".MMKMKMKMMM.",
               "..MMMMMMMM..",
               "...MMMMMM..."],
    "skeleton": ["............",
                 "............",
                 "............",
                 "...IIIIII...",
                 "..IIIIIIII..",
                 ".IIIIIIIIII.",
                 ".IKKIIIIKKI.",
                 ".IKKIIIIKKI.",
                 "..IIIKKIII..",
                 "...IKIKIK...",
                 "...IIIIII..."],
}

E = ["............"] * 11                             # an empty overlay


def ov(**rows: str) -> list[str]:
    """An overlay from its non-empty rows: ov(r3="...RRRR.....")."""
    out = list(E)
    for k, v in rows.items():
        assert len(v) == 12, (k, v)
        out[int(k[1:])] = v
    return out


# Hair the elves share; the designer's is blonde, the lore elf's auburn (h/j → a/A).
ELF_HAIR = ov(r1="....jhhj....", r2="..jhhhhhhj..", r3=".jhhh..hhhj.", r4=".h........h.",
              r6="j..........j", r7=".j........j.", r8=".j........j.")
ELF_LONG = ov(r1="....jhhj....", r2="..jhhhhhhj..", r3=".jhhh..hhhj.", r4=".h........h.",
              r6="h..........h", r7="hj........jh", r8="hj........jh", r9="hh........hh", r10=".h........h.")


def auburn(o: list[str]) -> list[str]:
    return [r.replace("h", "a").replace("j", "A") for r in o]


RAINBOW = ov(r9="........RObL", r10=".......OYLbP")

# role → (base, [overlay stage 1, 2, 3, 4]); an overlay may be a list of overlays, laid in order.
ROLES = {
    # Engineer — Burnout Peon: a plain grunt, then the sweat and the bags, a red bandana and war paint,
    # a warlord's horned iron helm with gold eyes.
    "engineer": ("orc", [
        E,
        ov(r2="..........c.", r3="..........b.", r7="..oppooppo.."),
        ov(r1="..........R.", r2=".........RR.", r3="...RRRRRRR..", r4="o.RRRRRRRR.o", r5="ooodKoodKooo",
           r7="..oRooooRo.."),
        ov(r0="I..........I", r1="I..........I", r2=".ImmmmmmmmI.", r3=".mMMMGGMMMm.", r4="omMMMMMMMMmo",
           r5="ooommoommooo", r6=".ooYYooYYoo."),
    ]),
    # QA — Bug Ork: a beetle on the head, then a magnifier on the eye, goggles up and the beetle caught,
    # a golden beetle-shell helm.
    "qa": ("orc", [
        ov(r1=".....K.K....", r2="....KPPPK...", r3="...opPpPpo.."),
        ov(r1=".....K.K....", r2="....KPPPK...", r3="...opPpPpo..", r5="ooodd.MMMMoo", r6=".ooKKoMKKMo.",
           r7="..ooooMMMMo.", r8="..oIooooIot.", r9="..oIooooIoot"),
        ov(r0="........K.K.", r1=".......KPPPK", r2="..mmmmmmmPpP", r3="..mccmmccm..", r4="o.mccmmccm.o"),
        ov(r0="...K....K...", r1="....K..K....", r2="..GGGGKGGGG.", r3=".GYGGGKGGGYG", r4="oGGGGGKGGGGo",
           r5="ooodWooWdooo", r6=".ooYYooYYoo."),
    ]),
    # Engineering manager — The Jira Lich: a sticky note on the brow, then the bow tie, a headset for the
    # calls, a release-night collar and a gold tie with gold eyes.
    "eng_manager": ("lich", [
        ov(r2="......YY....", r3="......YG...."),
        ov(r9="...RRrrRR...", r10="...RR..RR..."),
        ov(r0="..mmmmmmmm..", r1=".m........m.", r2=".m........m.", r3="mM........Mm", r4="mM........Mm",
           r5=".m........m.", r6="..m.........", r7="..m.........", r8="...mK.......", r9="...RRrrRR...",
           r10="...RR..RR..."),
        ov(r1="q..........q", r2="qq........qq", r3="qq........qq", r4="qvYYYvvYYYvq", r5="qq........qq",
           r6="qqq......qqq", r7="qqq......qqq", r8="qqqP....Pqqq", r9="qqqGGWWGGqqq", r10="...GG..GG..."),
    ]),
    # Product manager — Roadmap Wraith: a pale wraith in its hood, then a rolled roadmap, a map pin over
    # the hood, a gold-hemmed hood and the roadmap unrolled with its milestones.
    "product_manager": ("wraith", [
        E,
        ov(r8="..xwwwwwwxtI", r9="..xwxwwxwIRI", r10="...x.ww.IIt."),
        ov(r0="....RRR.....", r1="....RsRx....", r2="..xxxRxxxx..", r8="..xwwwwwwxtI",
           r9="..xwxwwxwIRI", r10="...x.ww.IIt."),
        ov(r0="....GGGG....", r1="...GxxxxG...", r2="..GxxxxxxG..", r5=".xwccwwccwx.", r8="IIIIIIIIIIII",
           r9="IRIIYIIRIIYI", r10="tIIIIIIIIIIt"),
    ]),
    # Product designer — Gradient-Sick Elf: a sprout of a designer, then the hair and the rainbow, a
    # ranger's green hood with a pencil, long hair, gold pins and gold eyes, swatches at the ears.
    "designer": ("elf", [
        [ov(r0=".....lL.....", r1="....lL......"), ELF_HAIR, ov(r0=".....lL.....", r1="....lLhj....")],
        [ELF_HAIR, RAINBOW],
        [ov(r0="....llll....", r1="...lLLLLl...", r2="..lLLLLLLl..", r3=".lLLe..eLLl.", r4=".l........l.",
            r6="l..........l", r7=".l........l.", r8=".l........l."),
         ov(r2=".........Yk.", r3="........YW..")],
        [ELF_LONG, ov(r2="..Y......Y..", r6="RjeYYeeYYejB", r5="OeeeeeeeeeeL")],
    ]),
    # Game designer — Lore Elf: auburn hair, then a quill in it, a bard's plum beret with the quill, and
    # long hair, gold eyes and a d20.
    "game_designer": ("elf", [
        auburn(ELF_HAIR),
        [auburn(ELF_HAIR), ov(r0=".........II.", r1="........II..", r2=".......AI...")],
        [auburn(ELF_HAIR), ov(r0="...pppppp.I.", r1="..pPPPPPPpI.", r2=".pPPPPPPPPI.", r3="..pppppppp..")],
        [auburn(ELF_LONG), ov(r0="..........P.", r1=".........PIP", r2="..........P.", r6=".eeYYeeYYee.")],
    ]),
    # ASO manager — Keyword Gnome: a red cap, then a keyword tag on it, brass goggles on the brim, a
    # gold-banded cap under five rating stars.
    "aso_manager": ("gnome", [
        ov(r0="......R.....", r1="....RORR....", r2="..RRRRRRRR.."),
        ov(r0="......R...I.", r1="....RORR.IKI", r2="..RRRRRRRRI."),
        ov(r0="......R...I.", r1="....RORR.IKI", r2="..RRRRRRRRI.", r3="..GccGGccG..", r4=".nGccGGccGn."),
        ov(r0="Y.Y...Y...Y.", r1="....RORR..Y.", r2="..GGGGGGGG..", r5=".nnYYnnYYnn."),
    ]),
    # Marketing — Growth-Hack Gnome: a blue cap, then its gold star, a megaphone, a gold-banded cap with
    # the green arrow of growth.
    "marketing": ("gnome", [
        ov(r0="......B.....", r1="....BbBB....", r2="..BBBBBBBB.."),
        ov(r0="......B...Y.", r1="....BbBB.YYY", r2="..BBBBBBBBY."),
        ov(r0="......B...Y.", r1="....BbBB.YYY", r2="..BBBBBBBBY.", r6="RRnnnNNnnnn.", r7="RIRnnNNnnnI.",
           r8="RRIInnnnIII."),
        ov(r0="......B...L.", r1="....BbBB.LLL", r2="..GGGGGGGGL.", r3="..nnnnnnnnL.", r5=".nnYYnnYYnn."),
    ]),
    # Data analyst — Data-Mining Goblin: an accountant's green visor, then the miner's lamp, a pickaxe
    # over the shoulder, a tycoon's top hat, a monocle and a gold tooth.
    "data_analyst": ("goblin", [
        ov(r2="...zzzzzz...", r3="..zzzzzzzz.."),
        ov(r0=".........ss.", r1=".......ss...", r2="....GsWG....", r3="...GGGGGG..."),
        ov(r0="MM.......ss.", r1=".MMt...ss...", r2="...tGsWG....", r3="...GGGGGG..."),
        ov(r0="...qqqqqq...", r1="...qpqqqq...", r2="...GGGGGG...", r3="..qqqqqqqq..", r6="..gKKgGKKG..",
           r7="..ggggggggG.", r8="..gKIKYKIg.."),
    ]),
    # Founder — Indie Knight: a squire's leather coif, then the steel helm and its pink plume, a seed of a
    # sprout and a gold trim, a paladin's white-and-gold helm with a gold plume and a glowing visor.
    "founder": ("knight", [
        [ov(r3="...tttttt...", r4="..tttttttt..", r5=".tttttttttt.", r6=".ttnnnnnntt.", r7=".ttnnnnnntt.", r8=".ttnnKKnntt.", r9="..tttttttt..", r10="...tttttt..."),
         ov(r6=".ttnKnnKntt.")],
        ov(r0="......I.....", r1="......k.....", r2=".....kI....."),
        ov(r0=".....lL.....", r1="......l.....", r2=".....kI.....", r5=".MGGGGGGGGM.", r7=".MMMMMMMMMM."),
        ov(r0="......Y.....", r1=".....YG.....", r2=".....GY.....", r3="...HHHHHH...", r4="..HHHHHHHH..",
           r5=".HGGGGGGGGH.", r6=".HHYYYYYYHH.", r7=".HHHHHHHHHH.", r8=".HHGHGHGHHH.", r9="..HHHHHHHH..",
           r10="...HHHHHH..."),
    ]),
    # Someone else — Wandering Skeleton: a bare skull, then a wanderer's straw hat, a pirate captain's
    # hat and an eye patch, and a crest of a thousand open tabs with gold eyes.
    "other": ("skeleton", [
        E,
        ov(r1="....htth....", r2="...hhhhhh...", r3="jhhhhhhhhhhj"),
        ov(r0="....qqqq....", r1="..qqqIqqqq..", r2="GqqqqqqqqqqG", r6=".IKKIIKKKKI.", r7=".IKKIIIKKKI."),
        ov(r0="BB.RR.LL.PP.", r1="BBBRRRLLLPPP", r2="ccccccccccc.", r6=".IYYIIIIYYI."),
    ]),
}


def mascot_grid(role: str, stage: int) -> list[str]:
    base, stages = ROLES[role]
    grid = [list(r) for r in BASES[base]]
    layers = stages[stage - 1]
    if not isinstance(layers[0], list):              # one overlay, not a list of them
        layers = [layers]
    for layer in layers:
        for y, row in enumerate(layer):
            for x, ch in enumerate(row):
                if ch == ".":
                    continue
                grid[y][x] = "." if ch == "_" else ch
    return ["".join(r) for r in grid]

STAGES = (1, 2, 3, 4)


def mascots() -> None:
    for old in (SPRITES / "mascots").glob("*.png"):        # the kin heads they replace, and any role gone
        old.unlink()
    for role in ROLES:
        for stage in STAGES:
            save_pair(grid_image(mascot_grid(role, stage), PALETTE, 2), SPRITES / "mascots" / f"{role}-{stage}.png")


# -- a building's renown and goal (docs/design/growth.md §5) ---------------------------------------------
# The renown is told twice, by a flag on the roof and by the stones under the hut; the goal by an annex
# beside it. ⚖️ balance, the default, has none, so a goal chosen stands out.
#
# The flag: | the pole (dark green), X the cloth. The pole's foot is the bottom left pixel. None at level 0;
# ivory at I, the pole taller at II, the cloth gold at III.
FLAG = ["|XXX", "|XXX"]
POLE = {1: 1, 2: 3, 3: 3}                         # the bare pole under the cloth, by level
CLOTH = {1: IVORY, 2: IVORY, 3: GOLD}
FLAGS = {level: FLAG + ["|"] * POLE[level] for level in POLE}

# The stones: a tile the width of four pixels, repeated under the whole hut (`js/icons.js` `HutSprite`),
# a course of stones (S) and mortar (m) for each level, the top edge in ivory (c) from II.
STONE, MORTAR = "#8f8166", "#4a4235"
FOOTINGS = {1: ["SSSm", "mmmm"],
            2: ["cccc", "SSSm", "SmSS", "mmmm"],
            3: ["cccc", "SSSm", "SmSS", "SSSm", "SmSS", "mmmm"]}

# The annex, standing on the ground at the hut's right: G green, W dark green, I ivory, D the dark.
ANNEXES = {
    "thrift": ["......WW........",          # a lean-to over a stack of logs: kept, counted, reused
               "....WWGGGG......",
               "..WWGGGGGGGG....",
               "WWGGGGGGGGGGGGW.",
               "GGGGGGGGGGGGGGGW",
               ".W............W.",
               ".W.II.II.II...W.",
               ".W.ID.ID.ID...W.",
               ".W..II.II.II..W.",
               ".W..ID.ID.ID..W.",
               ".W.II.II.II.II.W",
               ".W.ID.ID.ID.ID.W",
               "WWWWWWWWWWWWWWWW"],
    "quality": [".....I......",               # a crystal on a whetstone: cut, polished, checked
                "....III.....",
                "...IIWII....",
                "..IIIWIII...",
                "..IIWIIII...",
                ".IIIWIIIII..",
                ".IIWIIIIWI..",
                ".IIWIIIWII..",
                "..IIIIWII...",
                "..IIIWIII...",
                "...IIWII....",
                "....III.....",
                "..WWWWWWW...",
                ".WGGGGGGGW..",
                "WWWWWWWWWWW."],
}


def renown_and_goals() -> None:
    folder = SPRITES / "flags"
    for old in folder.glob("*.png"):          # the old goal flags, <goal>-<level>.png
        old.unlink()
    for level, rows in FLAGS.items():
        w = max(len(r) for r in rows)
        grid = [r.ljust(w).replace(" ", ".") for r in rows]
        save_pair(grid_image(grid, {"|": DARK_GREEN, "X": CLOTH[level]}, 2), folder / f"level-{level}.png")
        save_pair(grid_image(FOOTINGS[level], {"S": STONE, "m": MORTAR, "c": IVORY}, 2),
                  folder / f"footing-{level}.png")
    for goal, grid in ANNEXES.items():
        save_pair(grid_image(grid, {"G": GREEN, "W": DARK_GREEN, "I": IVORY, "D": NIGHT}, 2),
                  folder / f"annex-{goal}.png")


# -- the huts of each biome -------------------------------------------------------------------------------

def _near(c: tuple, ref: str) -> bool:
    r = rgb(ref)
    return sum(abs(a - b) for a, b in zip(c[:3], r[:3])) < 40


def biome_sprite(native: Image.Image, biome: str) -> Image.Image:
    """A flat header at its own pixel (1 px a pixel) for `biome`: only colours swapped and pixels added."""
    im = native.copy()
    px, (w, h) = im.load(), im.size
    if biome == "ice":                         # snow on the edges that face the sky, two pixels deep
        for x in range(w):
            for y in range(h):
                if not px[x, y][3]:
                    continue
                if _near(px[x, y], GREEN) or _near(px[x, y], DARK_GREEN):
                    px[x, y] = rgb(IVORY)
                    if y + 1 < h and _near(px[x, y + 1], GREEN):
                        px[x, y + 1] = rgb(IVORY)
                break
    # dust: sun-bleached sandstone, lighter than the fence's wood (olive sank into the wood and the ground);
    # lava: ash-grey basalt, light enough to stand off the dark (dark grey on black read as one smear). Each at about
    # the contrast dirt's green has to its ground (light ~9:1 / ~7:1, dark ~4:1 / ~3:1).
    swaps = {"dust": ("#d4b77a", "#9c7a46"), "void": ("#8e88a8", "#5e587a"), "lava": ("#a49a96", "#6a605c"),
             "meadow": ("#7fbf9a", "#4f8a6c")}
    if biome in swaps:
        light, dark = swaps[biome]
        for x in range(w):
            for y in range(h):
                c = px[x, y]
                if c[3] and _near(c, GREEN):
                    px[x, y] = rgb(light)
                elif c[3] and _near(c, DARK_GREEN):
                    px[x, y] = rgb(dark)
        foot = {"dust": ("#c9a46a", 5, 3), "lava": ("#8a2a10", 6, 2), "meadow": ("#ece4cf", 5, 1)}.get(biome)
        if foot:
            colour, every, of = foot
            for x in range(w):
                if px[x, h - 1][3] and x % every < of:
                    px[x, h - 1] = rgb(colour)
    return im


BIOME_VARIANTS = ("ice", "dust", "void", "lava", "meadow")


def biome_huts() -> None:
    for folder in sorted((SPRITES / "buildings").iterdir()):
        header = folder / "header.png"
        if not header.is_file():
            continue
        img = Image.open(header).convert("RGBA")
        if len(img.getcolors(maxcolors=4096) or range(4097)) > 64:
            continue                           # painted (tools/painted.py): its biomes are that tool's, shading kept
        native = img.resize((img.width // 2, img.height // 2), Image.NEAREST)
        for biome in BIOME_VARIANTS:
            out = biome_sprite(native, biome)
            save_pair(out.resize((out.width * 2, out.height * 2), Image.NEAREST), folder / f"header-{biome}.png")


def main() -> None:
    mascots()
    renown_and_goals()
    biome_huts()
    print("wrote the mascots, the flags, footings and annexes, and the huts of each biome")


if __name__ == "__main__":
    main()
