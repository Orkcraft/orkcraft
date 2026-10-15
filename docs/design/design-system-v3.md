# Design — the design system, v3: the brighter Camp

Status: built 2026-10-14 (V3, [decisions-2026-10.md](decisions-2026-10.md) §13). It turns the frame the owner approved,
**F1** ([img/references/v3/f1-town.jpg](img/references/v3/f1-town.jpg), and `-grey`), and the night's decisions
([v3-prompts.md](v3-prompts.md) §1, §5, §6) into tokens, a scale, layout rules and type, on v2's grid and sprite
pipeline ([design-system-v2.md](design-system-v2.md)). What is settled here is in `design-system/tokens.json` (→
`tokens.css`), `design-system/fonts/`, `tools/camp_sheets_v3.json` and `tests/test_design.py`. Preview:
`design-system/previews/CampKitV3.html`. F1b's colours drifted (v3-prompts §6): **no colour here is taken from F1b.**

I1 (the keeper, the scroll, quick actions, the terminal) and I2 (the Task board's inside) are built on these tokens;
nothing of their UI is built here.

**Held to throughout:** a look changes the drawing, never a word (CLAUDE.md). Buildings are named by what they do
(External listeners, Task board, Agent pool, Review gate, Publisher, Inspector), orks by their orkish names.

## 0. Where v3 stands (the end of the night of 14 October)

**Done** and on `main`: the tokens (§2), the scale and the layers (§3), the layout (§4), the signals (§5), the type
(§6), the preview (§7) and the cutter with its manifest (§8): `python tools/camp_sheet.py --v3` cuts every picked sheet
into `design-system/sprites/v3/` and rewrites the preview. Cut so far: the buildings (B1–B5, the lookout, the catapult,
the Task board as the dispatcher's booth, the Review gate with its barrier down and up, Research as a mine); the capped
ork (body, fifteen roles and the **Prospector**, states, inside poses, stepping out of a door); the carts; the track
(c2 and its curves); the ground, the decor, the palisade with its right wall; the UI pieces for I1; the person's
**eleven classes** (`people/<role id>.png`); the **growth marks** (`growth/footing-1..3`, `banner-1..3`,
`annex-thrift`, `annex-quality`).

**For I1 and I2, the stable names:** sprite paths are `design-system/sprites/v3/<kind>/<name>.png` as listed in its
`manifest.json` (each row: `size`, `frame`, `frames`, `pitch`, `show`, `anchor`, `slots`); a building keeps its type's
file name (`buildings/fields.png` is the Task board, `loot_vault.png` the Review gate, `mine.png` Research), whatever
sheet drew it last. Token names are `design-system/tokens.json`'s; none was renamed in v3, only added.

**The scale, per layer** (CSS px per art px; × the sprite's own `show`, ×1 for every sheet cut so far):

| layer | what | density 2: overview · **default** · close | density 1: overview · **default** |
|---|---|---|---|
| buildings `L.b` | buildings, stations, growth marks, carts, ground, decor, palisade | ×1 · **×1.5** · ×3 | ×1 · **×2** |
| orks and track `L.s` | orks and the Prospector, track tiles | ×1 · **×1** · ×2 | ×1 · **×1** |
| UI | signals, chips, names, the HUD | CSS px at every zoom (28-px badges, 24-px chips) | the same |

The layout's unit is 2 CSS px at `L.b = 1` (buildings are half their art px in units at every zoom); the track's tile
is `64 × L.s / (2 × L.b)` units, so rows, gaps and stations are computed from the sprites at each step (`grid()`).

**The layout** (§4 in full): one line per row, joined in a loop — the way in down through the lookout in the back
wall, the split on the left, the merge on the right, line 2 on to the buffer stop and the catapult against the right
wall. A building joins its line by a dirt path; **a station has its own track** (§4.11): the dispatcher's booth stands
over a siding off line 1 (a north T, a curve, room for three carts, a buffer) with the waiting carts on it and a `+N`
chip for more; the Review gate's weighbridge track and the mine's shaft track run into their line through a north T;
the gate's barrier is down while a cart waits on the weighbridge, up otherwise (the preview's *Gate clear* toggle).
**The person's home stands beside the Review gate** (where the person approves), east of it on line 1's row, over
the line's turn (the right column runs only below line 1, so the loop does not widen): `homes/<kin>.png`, one per kin
of `realm/intents.py` `ROLES` (k2-homes #1); the preview's *Home* button cycles the seven, the ork's first.

**Still a stand-in** (after GEN's round 10, k2-homes and c2-fix, run once the credits were topped up):

- **the split's junction** (north–east–south): c2's north T turned a quarter. c2-more's `t-e` is cut but its straight
  sits off the tile's column (round 8, below). **c2-fix #2** does not join either: its straight's rails are 150 image px
  apart and its branch's 223 (1.49×), so at the set's gauge (32 art px) the branch comes out about 48 at any one
  scale, and the turnout spans about 4 × 3 tiles; its other piece is a south-east curve two tiles wide, a turn the
  loop does not have. Neither is cut. `track/corner-nw` (c2-more) is cut and unused. A junction drawn on one tile,
  both legs 32 apart, is still wanted.
- **the Prospector's** walking, digging and sack frames: only standing is cut (o7 at `merge: 2.25`, 54 px tall).
- **the door patch on a building** (§4.7): `orks/body/door.png` (o6-door #2, four frames) is cut for I1; the preview
  does not open doors.
- the palisade has no front or left side (the camp is open there by design); its other corners are cut and unused.

## 1. What changes from v2

| | v2 | v3 |
|---|---|---|
| the world's palette | a dusk camp: muted grass `#5e8a4c`, grey-brown earth, maroon cloth | F1's sunny camp: meadow `#7cbd40`, sand paths `#e4b469`, honey wood, lilac stone, **teal and plum** cloth, turquoise water (§2) |
| the ground's value band | luminance 0.12–0.30 | **0.15–0.55**, the main grass and paths at least 7:1 from an outline and a chip (§2.3) |
| signals | 20 px badges on a dark plate | **28 px** (32 on the phone), plate, outline and a light keyline; nothing in the art as light as the question's yellow (§5) |
| the scale | art at ×1 at the overview, ×2 close, ½ for the map from half-size copies | the generated art **at its own pixel, ×1**, never resampled; ×2 close; ½ the map (§3) |
| the ork | a 32 × 48 frame | about **64** screen px tall, as the sheet draws it |
| the cart | 48 × 40 bin and a 48 × 32 load | about **64 × 48** with its load, as the sheet draws it |
| a building | a cover kit that lifts (nine-slice roofs and walls, facade, crest) | **one sprite with a door**; the keeper steps out of it (§13.1); the cover kit is superseded |
| spurs | a rail spur to each building | **one main line**; dirt paths join the buildings to it; carts stop opposite a path (§4) |
| the camp's edge | a palisade of sharpened 48-px stakes | a **low palisade of rounded logs**, 64 px tall, along the back and the right edge; the lookout tower in it, the catapult (in side view) against it (§4) |
| type | Titillium Web labels, chips in the UI face, today's sizes | **Nunito** labels, **Pixelify Sans** titles and chips, JetBrains Mono; every size a step larger (§6) |

## 2. The palette

### 2.1 How it was measured

On F1 (1312 × 816) each surface's colour is the **median of a patch of its own pixels** (a JPEG's noise is
averaged out; edges and outlines kept out of the patch), checked against a 28-colour k-means of the whole frame: the
open grass at two places (`#7cbd3f`, `#7dbd40`), the paths (`#e6b76a`, `#e2b268`), the grass's shade by the
buildings (`#3e8248`), the pond (`#38bbad`), the long house's planks (`#c88444`), the workshop's lower wall and the
tower's legs (`#935e3f`), the palisade (`#7c503d`), the canvas (`#389683`), the banner (`#8f3761`), the book tower's
stone (`#a9b9a9`), the gate's (`#b5c2b1`), the horn (`#ede0af`), the top bar's parchment (`#ebdebb`), walnut
(`#3d2a23`) and teal (`#216564`), the frame's darkest tone (`#160e05`).

v3-prompts §6 gave F1's grass as `#70ae43` and its paths as `#8f6144`. The grass there is the **mean** of every green
pixel, bushes and shadows included (measured again: `#6ba73f`); the open meadow is `#7cbd40`. The `#8f6144` "paths"
are the brown of the paths' rims and the track's ties: the paths themselves are **sand**, `#e0b36a` by the median of
every sand-coloured pixel (9 % of the frame). F1b's sand measures `#cda477` and covers under 1 % of its frame: it drew
most of its paths over in grass, which is part of why it looks duller.

### 2.2 The tokens, before and after (Camp)

**World and art** (the sprites' palette and the ground; never under text):

| token | v2 | **v3** | luminance | what for, where it comes from |
|---|---|---|---|---|
| `world-grass` | `#5e8a4c` | **`#7cbd40`** | 0.41 | most of the ground: F1's open meadow |
| `world-grass-light` | `#6f9a56` | **`#8fcc52`** | 0.50 | tufts, the light tone (yellow-green, hue 90°, never yellow) |
| `world-grass-dark` | `#4e7840` | **`#3e8248`** | 0.17 | the rim round paths, a building's shadow side, bushes: F1 |
| `world-earth` | `#8f7250` | **`#e4b469`** | 0.50 | the dirt paths, trodden earth, the track's bed: F1's sand |
| `world-earth-dark` | `#735b4c` | **`#c08548`** | 0.28 | a path's edge, ruts |
| `world-water` | `#2f5a55` | **`#38bbad`** | 0.39 | the Inspector's pond: F1 |
| `world-water-dark` | — | **`#2a8a80`** | 0.20 | new: the pond's deep and rim |
| `art-wood` | `#7c5f48` | **`#c88444`** | 0.29 | honey planks and posts: F1 |
| `art-wood-light` | `#ba9468` | **`#e2a865`** | 0.45 | lit wood, a beam's top |
| `art-wood-dark` | `#4f3935` | **`#935e3f`** | 0.15 | caramel shade, the ties, the map's track line: F1 |
| `art-wood-deep` | — | **`#664337`** | 0.07 | new: walnut, the palisade's shade, a cart's bin, a doorway: F1 |
| `art-stone` | `#7d7a74` | **`#a7a6b8`** | 0.39 | cool light stone with lilac; **a step darker than F1's** `#b5c2b1` (0.52) |
| `art-stone-dark` | `#4d4848` | **`#6f6e84`** | 0.16 | stone's shade |
| `art-iron` | `#4a4b52` | **`#63696b`** | 0.14 | rails, bands, the portcullis: F1 |
| `art-bone` | `#dccaa0` | **`#dcc798`** | 0.58 | tusks, the horn, scrolls, pages; **a step darker than F1's** `#ede0af` (0.74) |
| `art-cloth` | `#6b2a2c` | **`#389683`** | 0.24 | teal: the Agent pool's canvas, aprons, banners: F1. Maroon is gone |
| `art-cloth-plum` | — | **`#8f3761`** | 0.09 | new: the Town Hall's banners, the second cloth: F1 |
| `art-skin` | `#769544` | `#769544` | 0.26 | the ork's olive-moss skin, unchanged (v3-prompts §1.2) |
| `art-outline` | `#1c1410` | `#1c1410` | 0.01 | every outline (F1's darkest is `#160e05`; v2's kept, a breath warmer) |

**Signals and chips** — unchanged on purpose: `signal-ask` `#facc15` (a question), `signal-fire` `#e8411c` (an
error, 🔥), `signal-held` `#8fa3b8` (⏳), `chip` `#1c1712`, `chip-ink` `#e8e0c8`.

**The UI's parchment** (new; F1's top bar and the panels of v3-prompts §3e, for I1 and I2): `parchment` `#ebdebb`,
`parchment-ink` `#3d2a23` (10.1:1), `walnut` `#3d2a23` (the frames, the HUD bar), `accent-teal` `#216564` (studs, an
active tab's edge, a primary button; `ink` on it 5.1:1). Office maps them to its own panel, ink, frame and selection.
The chrome of today's windows (`panel`, `wood`, `bone`, `cloth`, …) is unchanged here: I1 moves the windows it
touches onto parchment.

The other Camp biomes (ice, void) and Office keep their `world-*` / `art-*` values; the new tokens take their
nearest sibling's there. Forest is the only biome offered (v2 §12, answer 7).

### 2.3 The rules the tests hold, and what changed

`tests/test_design.py`:

- **The ground band rose** from luminance 0.12–0.30 to **0.15–0.55**. v2's band was set for a dusk camp; the owner
  approved F1's sunny one, whose meadow is 0.41 and whose paths are 0.50. What the band protects is unchanged: a dark
  outline and a dark chip are seen on every ground tone (still at least 3:1), and on the two that cover most of the
  screen, the grass and the paths, now **at least 7:1** (they measure 7.8–9.5). The lower end rose a little so a
  ground tone never sinks to the outline's darkness.
- **New: a signal wins by value.** No `world-*` / `art-*` tone is as light as `signal-ask` (luminance 0.64; the
  lightest art, bone, is 0.58). F1 failed exactly this in grey (v3-prompts §5.2): the gate's stone, the horn and the
  book were the brightest things, so the stone and the bone are a step darker than F1 drew them.
- **New: badges are larger:** `badge` 28 (was 20), `badge-touch` 32, `chip-h` 24 (was 20).
- **New: the scale fits ten buildings** (§3): a core building 200–260 screen px wide, an ork 56–64 tall, a cart about
  64 wide, every size on the grid of 8.
- **New: parchment reads:** `parchment-ink` on `parchment` at least 7:1 in Camp and Office; `ink` on `accent-teal` at
  least 4.5:1.
- Kept: `chip-ink` on `chip` at least 7:1; each signal on `chip` at least 3:1; **no world or art tone is a saturated
  yellow (45–65°) or red** — the sand (37°) and the honey wood (29°) sit below yellow, the plum (331°) away from red.

## 3. The scale

**The art is shown at its own pixel, ×1** (`--art-scale: 1`), **never resampled.** Revised after round 3
([v3-prompts.md](v3-prompts.md) §7): the first draft of v3 asked for sprites drawn at half and shown at ×2, so the cutter
read the generated sheets at a coarser cell to fit 128-px slots, and snapped their colours to the tokens; the Agent
pool lost its barrels and crates and its roof's shade turned stone-grey
([before and after](img/v3-preview/agent-pool-before-after.png)). The sheets come at about 4.2 image px per art px, and
a core building is drawn about 190 art px wide — already the 200–260 screen px asked. So the art's pixel is the
screen's pixel, and **a slot is what the sheet draws**, rounded up to the grid of 8; the sizes below are the plan the
prompts ask for and the layout reserves. Ground and track tiles and the layout cell follow the same rule (the cell
16, a tile 32 art px as drawn).

**The zoom** (the owner, v3-prompts §10): **×1.5 by default on a screen of density 2 or more** (one art pixel = 3 × 3
device pixels, sharp), so the town fills the window as F1 does; **×1 by default at density 1** (×1.5 cannot be sharp
there). **The wheel zooms ×1 · ×1.5 · ×2**, snapping, each step whole in device pixels (at density 1: ×1 · ×2). The map
is ½ from the pipeline's half-size copies (`map` on a group, made when the map zoom is built).

**Each sheet at its own pixel, shown at a whole multiple.** The sheets come at different pixel sizes, so a sprite is
cut at its sheet's own pitch and shown at the whole multiple (`show`: ×1, ×2) that brings it nearest its target size;
on screen it is `show × zoom` CSS px per art px. Pixels of two sizes side by side are accepted. The manifest records
each sprite's `pitch` and `show`; the preview reads them.

| sheet | pitch (image px per art px) | drawn (art px) | target at ×1 | `show` | on screen at ×1 · ×1.5 |
|---|---|---|---|---|---|
| B1–B3 buildings | 4.17 | 72–192 wide | core about 190 | ×1 | 192 · 288 (Agent pool) |
| o1, o2 orks | 5.00, 5.15 | frames about 32–54 × 46–57 | 48–64 tall | ×1 | about 54 · 81 |
| c1 carts | 8.33 | about 36 × 31–43 | about an ork's height, as in F1 | ×1 | 36 · 54 wide |
| c2 track | 6.24 | tile 64 (4 tie spacings of 15 → 60, ×1.07) | 48–64 | ×1 | 64 · 96 |
| g1 ground | 7.19 | tiles 45; earth fill 32, rims 40 × 17–18 | — | ×1 | 32 · 48 (fill) |
| g2 decor | 6.31 | 18–47 | — | ×1 | trees about 45 · 68 |
| u1 bubble and scroll (I1) | 8.39 | bubble pieces 22–24, scroll sheets 29–42, banner 236 × 38 | about 40 | ×2 | for I1 |

**The proportion rule** (round 7): every later sheet and layout is checked against F1, with **the Agent pool's canvas
roof as the unit** (F1: 278 px at 1312 wide; the cut sprite: 156 art px of its 192, the rest is ropes). Measured on F1
by eye on a 10-px grid at ×3–×4, on the preview from the sprites' own pixels:

| | F1 | ratio | preview (×1) | ratio | action |
|---|---|---|---|---|---|
| an ork's height | 50–57 px | 0.19 | 44 | 0.28 | **orks are 1.45× too large beside the buildings**: the next ork or building sheets (GEN) draw the ork at about 0.19 of the work hall's roof, or the buildings larger |
| a cart, wide × tall with its load | 64 × 71 | 0.23 × 0.26 | 36 × 43 (c1 at ×1) | 0.23 × 0.28 | matches (since round 6's ×1) |
| the track's band (ties end to end) | 45 | 0.16 | 32 (c2) | 0.21 | 1.27×; acceptable, or c2's ties drawn shorter |
| a path's width | 55–60 | 0.21 | 32 | 0.21 | matches; kept at 32 (stop areas the same) |
| the gap between buildings | 45–60 | about 0.18 | was 64 (upper row), 16 (lower) | 0.41, 0.10 | **set to 32** (one path's width, the nearest step of 8): the loop widened by 32 units to hold the lower row |

**Layers at their own multiple** (round 7, the PM's proposal, no sheet redrawn): at the default zoom **buildings,
carts, the ground and the decor are shown at ×1.5, orks and the track at ×1** (on density 2: 3 and 2 device px per art
px, both whole). The layout's grid (paths, gaps, the loop) scales with the buildings. The measured ratios then, with
the same unit (the canvas roof, 156 × 1.5 = 234 px):

| | F1 | preview, layers ×1.5 / ×1 |
|---|---|---|
| ork height | 0.19 | 44 / 234 = **0.19** |
| cart, wide × tall | 0.23 × 0.26 | 54 × 64.5 / 234 = **0.23 × 0.28** |
| track band | 0.16 | 32 / 234 = **0.14** |
| path width | 0.21 | 48 / 234 = **0.21** |
| gap between buildings | about 0.18 | 48 / 234 = **0.21** |

**The buildings against F1** (round 8, the owner's picks; same unit; F1 by eye on a 10-px grid):

| building | F1, wide × tall | ratio | preview (cut) | ratio | note |
|---|---|---|---|---|---|
| Agent pool | roof 278 | 1.00 | roof 156 | 1.00 | the unit |
| Review gate | 225 wide | 0.81 | 160 | 1.03 | a little large |
| Task board | 128 × 105 | 0.46 × 0.38 | 152 × 112 (b1-taskboard at `merge: 2.6`) | 0.79 of the pool's full 192 | the owner: about 0.8 of the Agent pool's width (≈154 px), shrunk by the cutter to the nearest clean size (the 8-px grid: merge 2.5 gave 160, 2.75 gave 144) |
| External listeners | 120 × 290 | 0.43 × 1.04 | 130 × 186, its piece of wall included | 0.83 × 1.19 | built into the wall, as decided |
| Publisher | about 120 wide | 0.43 | 146 × 94 (side view, its own track) | 0.94 | side view, as decided |

**Orks from other sheets at o1's size:** o3 (the states) is drawn at about twice o1's art pixel and is read at `merge: 2`
(2 × 2 → 1, the median): its orks come out 47–50 px against o1's 44. o5 (inside a building) is drawn at the same
pixel as o1 but its ork is drawn 1.6× larger (about 70 art px tall); read at `merge: 1.5` (the median over 1.5-px
cells, the nearest clean rule) it comes out 44–47 px. The asking ork in the preview wears o3's pose.

**Round 8, the rest:** the lookout and the Task board drew wood more orange than F1's honey (saturation ≥ 0.75,
value ≥ 0.7, where a signal's orange is). The check is not loosened; on building and decor sheets (`wood_pull`) those
pixels are pulled back into the wood family — each keeps its value and takes the hue and saturation of the nearest
`art-wood*` token — and the cutter reports how many: the lookout 1 348 px, the Task board 1 378. **c2-curves** (a
south-east curve and a larger one, a south-west, a north-east, a switch, a crossing) is fitted to c2's set with
`tile_from` (its rails 41 art px apart against the set's 32 → ×0.78, the 64-px tile) and its three curves replace c2's;
they join the straights. It has **no north-west curve and no junction north–east–south**, so the loop's split stays the
stand-in (c2's north T turned a quarter). **g3** drew no corners or side pieces (front-on, a wall going away is not
seen): the back wall is its straight run with end posts.

**Round 8, the sides:** **g3-sides #1** gives the right wall: the back run ends in `palisade-corner-ne` (one log dropping
where the wall turns), `palisade-v` (a column of log tops, 40 × 120) runs down the right edge, stacked 110 art px apart
so its 7 empty rows above and 3-row tail below tuck under the next copy, and `palisade-post` stands at its foot. The
other corners (nw, sw, se) are cut for a wall that closes the camp; the preview's camp is open at the front and on
the left. **c2-more #1** gives `track/corner-nw` and `track/t-e`, fitted with `tile_from` at ×0.727 (rails 44 art px
apart against 32); neither is placed yet. t-e's straight sits off the tile's middle column and its branch stops short
of the east edge, so at the split it breaks the line and the turned north T stays. corner-nw is clipped at the top,
and the loop has no north-west turn to use it. Both need a redraw at the set's gauge (v3-prompts §11).

**The ork is the capped ork of 0.3** (v3-prompts §12; o1/o2's bald ork is `retired`, its sprites gone with it, the
door frames and the prospector among them). Cut the v3 way from the 0.3 sheets: walking down, up and to the side (6
frames each), idle 4, work 6, sit 2 (`ork-body-a`, `-b`); fifteen roles by their props — warchief, grunt, mason,
mechanic, seer, quartermaster, pathfinder from the 0.3 sheet (`ork-roles-a`), taskmaster, lookout, loader, farseer,
warder, artisan, treasurer, alchemist from `roles-2` (`ork-roles-b`, drawn 1.4× and read at `merge: 1.5`) —
[side by side](img/v3-preview/ork-roles.png); its states from the owner's `o3-states-r1` (×1) and its inside poses from
`o5-inside-r1` (`merge: 1.5`; piece 18 of the pinning row, two frames touching, left out). Heights at ×1: body 46–51,
roles 46–53, states 38–40, inside 40 — **0.16–0.22 of the unit, about F1's 0.19**; the sheets differ by 1.2–1.4×,
which no whole merge closes, so each is read at the nearest. **Awaited for this ork:** stepping out of a door (one
sheet, with `roles-2.jpg` attached); there is no prospector among its roles.

**The zoom steps keep whole device pixels** (buildings / orks and track): on density 2, **×1.5 / ×1** (default),
×3 / ×2 (close), and ×1 / ×1 (an overview: whole, the orks a little large); on density 1, **×2 / ×1** (default) and
×1 / ×1. The wheel steps through them (or `#zoom=0` · `1` · `2` in the page's address), **drag pans**; the default view is centred on the work (the back wall to line 2),
the lookout and the catapult at the ends reached by dragging or by the overview. **The loop is compact:** line 2 sits as
close under line 1 as the lower row allows, a whole number of track tiles below it (computed from the tile at each
step).

**Carts against orks** (round 6; since then shown at ×1, the PM's decision: the 64-px target was wrong — a cart about
an ork's height, as in F1). The numbers at ×2 that led to it: an ork is drawn 44 px tall (o1's idle; the roles 40–43); a cart is
36 art px wide, so 72 px at ×2. The empty cart stands 62 px, the loaded ones 70 (letter) to 86 (scroll, crate): the
load rises to about twice the ork's height (×1.5: 93–129 against 66). At ×1 a cart would be 36 × 31–43, as tall as an
ork, but under the 64-px target.

**The window: 1440 × 900.** A 36 px HUD, then the world, 1440 × 864. With a line per row the loop must hold the lower
row (five buildings, about 408 units of 2 px), so the camp is 696 × 308 units: about 1390 × 620 px at ×1, which fits,
and about 2090 × 920 px at ×1.5, which does not — at the default ×1.5 the window shows the camp's middle (both lines
and all eight inner buildings) and the lookout and the catapult at its two ends are just outside; the wheel's ×1 shows
the whole camp. Either the camera pans (drag, I1), or the lower row is drawn narrower.

| piece | as drawn on B1–B3 (art px = screen px) | the plan (token) |
|---|---|---|
| Agent pool, Town Hall | 192 × 128, 184 × 128 | `footprint-xl` 192 |
| Review gate, Test bench, output | 160 × 112, 152 × 104, 144 × 120 | `footprint-l` 160 |
| Publisher, Inspector, Wiki, Branches & PRs, UX bench, Review board | 128 × 104–120 (Review board 136) | `footprint-m` 128 |
| Script, Drop file here, Transformer | 104–112 × 104–120 | `footprint-s` 104 |
| External listeners' tower, Router, **the Task board** | 80 × 128, 72 × 112, **88 × 72** | `footprint-xs` 80 |
| Research | 96 × 128 | — |
| the ork | (o1 not yet drawn) | `ork-frame-w/-h` 64 (56–64 tall) |
| a mine cart with its load | (c1 not yet drawn) | `minecart-w/-h` 64 × 48 |
| a dirt path's width | — | `path-w` 32 |
| the palisade's height | — | `palisade-h` 64 |
| a chip (UI, at every zoom) | — | `chip-h` 24 (28 on the phone) |
| a badge ❓ ! ⏳ (UI) | — | `badge` 28 (`badge-touch` 32) |

**The sizes drift between sheets** (the Task board drawn at 88 px beside a 192-px Agent pool): the next sheets ask each
building at its planned width, and the Task board is redrawn as a core building (about 160–192 wide).

**Ten buildings on the window, at F1's density:** the preview packs the ten of §4 as F1 does — two rows close to the
line (the upper row's doors a 32-px path above the track, the lower row's roofs just under it, its lane under its
doors), about one path's width (32 px) between buildings, sand strips no wider than a path. At ×1 the camp inside its
walls is about 990 × 580 px and stands in the middle of the 1440 × 864 world, wilderness round it; the buildings cover
about 12 % of the window and 26 % of the camp. **F1 draws its buildings about 1.6–1.7× larger** (its work hall is
about 330 px wide at 1440 against the cut Agent pool's 192), so at ×1 the camp cannot fill the window as F1 does without
a larger scale, which v3 does not use. To get F1's fill, the sheets must draw the buildings larger — fewer to a sheet
(three or four instead of six), so the model gives each more pixels — or the camp stays compact in its wilderness.

**What this supersedes in v2:** §2.3's ladder, §2.4's footprints as cards, §4f's 32 × 48 ork (the owner's answer 4),
§4e's 48 × 32 cart, the sizes by S/M/L (answer 8: sizes follow what each sheet draws).

## 4. Layout rules (decided the night of 14 October)

1. **A line of track per row of buildings, joined in a loop** (the owner, v3-prompts §11). The way in comes down from
   outside the wall at the lookout's foot and **splits on the left** into line 1, under the upper row's doors, and
   line 2, under the lower row's; the two **merge on the right**, and line 2 runs on to the catapult's buffer stop.
   **No rail spurs:** each building is joined to its own line by a short **dirt path** (earth with grass rims, 32 px
   wide) from its door to its stop. **Carts run on the lines only, orks on the paths.** An eleventh building starts
   another row with its own line, joined into the loop the same way (a station is the exception, rule 11). (This replaces round 4's lane per row.) c2 has no
   junction with exits north, east and south yet: in the preview its north T turned a quarter clockwise stands in (a
   flat track seen from above reads the same turned); the merge on the right is c2's own north T, the turns its
   north-east and south-west curves, so the loop needs no north-west curve.
2. **Carts stop opposite a path.** The stop is where a building's path meets its line; the line's last cell is the buffer stop at
   the catapult.
3. **The keeper waits at the stop.** A building that takes work from the line (Task board, Agent pool, Review gate,
   Inspector) has its keeper at the end of its path; where the keeper stands says its state (v3-prompts §5): at the
   stop looking down the line = waiting for work; lifting the load off a stopped cart and carrying it in = work
   arrived; inside, its bubble over the roof = working; at its door with ❓ = asking the person.
4. **Orks never push or ride carts.** The keeper lifts the load off and carries it in, and puts the result back on a
   cart at the stop.
5. **The two buildings that face the world stand in the wall.** External listeners' lookout tower is **built into the
   palisade**; the track comes in from outside through a gap at **the tower's foot**. The Publisher's catapult stands
   **against the palisade at the line's end**, drawn **in side view** (the owner: it reads better; the one exception
   to the single projection), facing right, the track coming into its side from the left, and throws up and to the
   right over the wall. *Whatever crosses the camp's border stands on the
   wall* — the way in on one side, the way out on the other (for now only these two).
6. **The palisade is low, of rounded logs** (64 px tall, never sharpened), along the back and **down the right edge**,
   which the catapult stands against and throws over; nowhere round a building. Work comes in through the tower in the
   wall at the left and leaves over the wall at the right.
7. **A building is one sprite with a door** (§13.1): no lifting cover, no nine-slice roof, no facade or crest slot.
   The door is in the lower middle of its front; its three states (closed; open, warm light; the keeper half out) are
   a 32 × 40 patch drawn over it. The cover kit (v2 §4a–4c) stays only until I1 takes it out.
8. **Dense, as F1:** two rows hugging the line, about one path's width between buildings, sand no wider than a path;
   the camp is as large as its buildings at ×1 and the wilderness round it takes the rest of the window.
9. **Few orks:** an ork is a session; a camp shows four to eight. Edges are quiet (few crates and bushes) so the eye
   stays on the line.
10. The town's name is the person's (the project's name, "My camp" in the previews), never a character's.
11. **Stations on the line** (round 9, v3-prompts §13.1): a building whose work is the track's own has its own track
    and no path. **The Task board is the dispatcher's booth** over a **siding** off line 1: a north T on the line, the
    south-east curve up, three tiles where waiting carts stand, a buffer stop; more than three waiting is a `+N` chip by
    the buffer. **The Review gate** stands on a **weighbridge** whose track runs south into line 1 through a north T;
    its **barrier is down while a cart waits on the weighbridge** (that cart wears the yellow flag and its chip), **up**
    otherwise (`buildings/loot_vault-up.png`). **Research is a mine** whose shaft track runs south into line 2 the same
    way; **the Prospector** keeps it, standing by the shaft. (st-mine is drawn 184 × 240; read at `merge: 2` it is
    96 × 120, as tall as the lower row with its paths, so line 2 stays up and the default ×1.5 shows both lines.) A station's track stands on a track tile's middle column so
    it meets the line square. The rows are as tall as their tallest piece: a station's track reaches its line, a
    building's door is a path (16 units) above it, the booth's foot is on its siding.
12. **Growth shows on the building** (v3-prompts §13.4): its level I–III as a stone footing by the door and a banner on
    the roof (`growth/footing-N`, `banner-N`); a goal's annex (Thrift, Quality) stands against its east wall. The
    preview shows the Agent pool at III, the Test bench at II with the Quality annex, the Town Hall at I with the
    Thrift annex.
13. **The person's home stands beside the Review gate**, east of it on the upper row, its door a path above line 1
    like a building's, its name *Home* on it (no stop: carts do not stop there): the person is the one who approves
    at the gate. One home per kin (k2).
    **Built (INV):** `layout.js` `lay(…, home)` puts `homes/<kin>.png` east of the gate on the gate's row (with no
    gate, at the first row's end), the row as tall as it needs; `js/camp/town.js` `Home` draws it, and a click opens
    the town's menu with *Since your last look* (`look.show`: the digest since the last look ended, on demand),
    *You: profile and deeds* (the portrait's menu) and *Town settings…*.

### 4b. A real town on these rules (I1, built)

The preview places ten buildings by hand; the GUI lays out whatever the town has
(`orkcraft/gui/static/js/camp/layout.js`, pure, tested in Node by `tests/test_camp_layout.py`; drawn by
`js/camp/town.js`). A town's roads are a graph between buildings, so:

1. **The work's order.** Each building's depth is the longest chain of roads that reaches it (a source is 0; a loop of
   roads stops at the number of buildings); buildings sort by depth, then as the town lists them; a building no road
   touches stands after all the work.
2. **The wall's two.** The first External listeners stands in the back wall at the way in; the last Publisher stands
   at the buffer stop against the right wall. A second one of either stands in the rows like any other building.
3. **Rows.** The rest fill rows of at most five, balanced (nine are 5 + 4, six are 3 + 3), the first row under the
   back wall. **A building placed in Office takes its row from its Office position** (decisions §14, the PM's call
   overnight, to confirm): its y picks the band (the top band the top row), its x its place in the row, so moving a
   card in Office moves the building in Camp; a full row passes the next one down. A building never placed fills the
   room left, top row first, in the work's order. Nothing is dragged in Camp itself. Each row stands on its own line: a building's feet are a short path
   (24 art px) above its line, its stop where its path meets the line. The Review gate and Research draw their own
   spur down to the line (the weighbridge, the headframe's track), so they stand on it with no dirt path.
4. **The loop.** The way in comes down the left column from outside the wall; at each line but the last a junction
   (c2's north T turned a quarter) sends the track east and on south; the last line turns east (`corner-ne`). With two
   rows or more, the right column joins the lines (`corner-sw` at line 1, the T turned back at the lines between, the
   north T as the merge at the last) and the last line runs on to the buffer stop and the catapult. One row has no
   right column: its line runs straight to the buffer. Lines are whole track tiles apart, so the columns tile.
5. **A road's carts** go from the source's stop to the building's stop by the shortest way along the track (a search
   over the tiles by their exits): along a line, down or up a column, along another line. A cart from External
   listeners comes in from outside the wall. Carts never leave the lines; a stopped cart stands at its building's stop
   (on the Review gate's weighbridge, the barrier down while it waits for the person), more than three are a pile.
6. **The Task board** is the dispatcher's booth with a siding of three tiles beside it: its to-do lane's tasks wait on
   it as carts, five at most and a `+N` chip for the rest.
7. **The view.** The zoom steps of §3 (`zoomLevel` a · b · c: the overview, the default, close; ⌘± and the wheel), a drag
   pans, and the default view is centred on the work (the back wall to the last line, between the columns) in the
   part of the window the panel leaves.

Office draws the same town as its cards where the person put them (`js/town.js`): one town, two drawings, the same
words. Each building's steward is called by its orkish name (`ork_name` in the snapshot, `orc.<type>` in the
glossary).

**Layers** (v2 §3, revised): ground · paths and track · buildings · carts · orks · **doors** (the patch over a
building, sorted with it) · signals · chips · UI. The covers' layer is gone. Shadows stay the product's.

### 4c. Loops, services and the person's places (the owner, 15 October; not built)

The line shows **the flow**: work that changes hands. An agent's own loop (think, read, edit, test, again) is one
session and is drawn **inside it**: the ork's bubble (its phase as 📖 ✏️ 🧪) and the building's inside, never on the
track. Between buildings, three kinds of link, three drawings:

| link | examples | drawn as |
|---|---|---|
| **flow**: the work changes hands | Task board → Agent pool → Review gate → catapult | carts on the line (§4) |
| **return**: the answer goes back to who asked (`returns: true`, a send-back) | the Calendar → Agent pool → the brief back; the Review gate's send-back to the pool | the same cart (one id) goes **round again**: on along its line, back along the **return line**, in again at the left column to the building that asked (rules 5–7). Never backwards on a line. A frequent loop gets a siding of its own, as 1b's proving siding |
| **service**: consulted, never passed through | the Wiki read by an Agent pool (`notes`); later the Town Hall | **no track and no stop.** It stands in a row beside its busiest reader; an ork walks the short path to it with a scroll before the run and back with the excerpt: one walk per run, never one per `wiki_search`. Other readers show 📖 in their ork's bubble |

**Rules:**

1. **A service beside its reader** (the owner, 15 October; the back row along the palisade was built and is taken
   out: one building did not earn a row of its own and long paths). A service stands in a row like any building,
   next to its busiest reader, with no stop on the line; one short footpath (16 art px, narrower than a building's)
   joins its door to its reader's path. Readers further away get no path: their ork's bubble shows 📖 while it reads.
   A service the person placed in Office keeps its place and gets no path. Paths never run along the track; a level
   crossing (planks, square to the line) stays for any path that must cross one.
2. **Neighbours.** Two buildings joined by a return road stand in the same row, at most one place apart, so the round
   trip is short. A service stands beside its busiest reader (rule 1).
3. **The person's places win.** A building the person placed in Office keeps its row and place; neighbours place only
   buildings never placed. A far placement costs a longer trip, shown as it is (and only shown:
   rule 9). Later, perhaps: the Workchief says once, as a 💡 improvement, never forced, "The brief rides across the
   whole camp. Put the Calendar next to the Agent pool?"
4. **The track is the product's, the places are the person's.** The person chooses a building's row and its order,
   never its coordinates, so the track comes out right whatever they do:
   - the topology is fixed: a line per row, the two columns, the split, the merge, the buffer stop; placing only
     changes which stop is where. No crossings of track, no spurs, no diagonals;
   - every line runs the camp's full width (the loop stays a rectangle); a short row's buildings stand from the left,
     and the grass left over is where the person places items (v3-prompts §14);
   - rows hold at most five; a sixth placed in a full row passes to the next, as today;
   - stations keep their track (§4.11) wherever their row is.

5. **One way round.** Every cart runs one way: east along the lines, down the right column, **west along the return
   line** under the lowest row, up the left column. No cart ever runs backwards, so two carts never meet head-on. The
   return line is the loop's own bottom edge: the camp grows one track tile (64 units) taller; whether both lines and
   the return line fit the default ×1.5 at 1440 × 900 is checked in the preview first (else the return line shows at
   the overview and its edge at the default).
6. **Switches say where a cart goes.** Every point where a cart can take one of two ways (into a line from the left
   column, out to the return line or on to the buffer stop on the right, into a pocket) has a small **switch stand**
   beside the track: a lever and a target arm, read by position, never by colour. It throws as a cart comes near and
   the cart takes the way it shows, so a return reads from across the camp: the switch at the right throws to the
   return line and the cart goes round again. Switches still for a cart going on.
7. **Carts keep their distance and wait off the line.** On one line carts follow one another a cart apart and never
   overtake; one that catches up waits behind, and the reason stands in front of it. **A cart never waits on the main
   line:** it stands just off the line at the end of its building's path while the ork works (a pile of more than
   three stands there as the pile). **Decided 15 October (PM, from the screenshots `img/loop/pocket-none.png` and
   `pocket-flat.png`): no pocket track** — the calmer of the two; a pocket track (arched or flat) doubled the rails.
   Stations keep their own (the Task board's siding, the Review gate's weighbridge, the mine's shaft). This amends
   §4.1's "no rail spurs" for pockets only: one tile, parallel, never a branch to a building.

8. **A round has its price.** A cart going round again wears its round and what that round cost on its chip, on the
   return line and back in: `round 2 · 🪵 18k` (and `$` on an API key), from the recorded tokens only, as the flying
   cart's cost (the-score.md). A second round reads as the price of rework, not as distance.
9. **Placement is tidiness, never throughput.** A cart's trip is drawn only: the work reaches its building at once
   (`cart_travel_s` 0), so a far placement costs nothing real, and nothing pretends it does. No layout-efficiency
   measure, no trip time in the score; the optimising game is the score (fewer rounds, cheaper roles, the Wiki read
   first). The Workchief's 💡 line about a long round trip (rule 3) moves to **Later**: the person may notice it alone.
   To check on the owner's own play: do they move buildings for shorter trips, and does that pull last a week? If it
   does, something real behind placement is worth a thought then.

**Priority:** one way round with the return line, the switches, the pockets, the queue and a round's price are **P0, built with Mission
1b** (its rework and the gate's send-back need them), after the owner has played Mission 1: about 2–3 days. The back
row, the neighbours, the ork's walk to the Wiki and the 💡 line are **P1**. **No:** a cart backing along a line; each
tool call or MCP read of an agent drawn as a cart or a flash.

**Art wanted:** the switch stand (a lever and a target arm, two positions, about 16 × 24 art px); the pocket's
switches on c2's gauge, with the north–east–south junction still owed (§0).

**Built (LOOP, 15 October).** Rules 1–3 and 5–8, the 💡 line not.
- **Track and traffic.** `js/camp/track.js` gives each tile the ways a cart may leave it (`go`), so routes run one way
  round and a cart for a building behind it goes round the return line, one tile under the lowest line.
  `js/camp/traffic.js` keeps carts a cart apart, never overtaking, one that catches up waiting behind.
- **Switches and pockets.** A switch stand (c3's `track/switch-0|1`, drawn at twice the track's zoom so its arm
  reads) stands at every fork and throws while a cart that turns there is near. The split on the left is c3's `t-e`.
  A building's waiting carts stand on the end of its path just off the line, with no pocket track (the owner chose
  this over a flat pocket in code; the arch of c2's curves and the flat stand-in are both gone).
  Stations keep their own track.
- **Send-backs.** A rework handed straight back is kept by the road engine (`sent_back`) and wears
  `round N · 🪵 …` (`gui/state.py`).
- **Services and neighbours.** `js/camp/services.js` (the back row was built, then taken out by the owner) stands a
  Wiki the person never placed in its busiest reader's row beside it, with no stop and no path to the line. One
  footpath (16 art px) joins its door to that reader: along the row's front, or straight down to the line by the
  depot's gateway. Other readers get no path; their 📖 is not built, since no reading phase reaches the camp yet. A
  Wiki the person placed keeps its place and gets no path. Return pairs among unplaced buildings become neighbours, a
  building already settled beside its partner staying. Level crossings (c3's `track/crossing`) stay for a path that
  must cross a line; none does now.
- **The fit.** Both lines and the return line do not fit the default ×1.5 at 1440 × 900: the return line shows at its
  edge there and whole at the overview. Shots: [img/loop/](img/loop/).

**Built (LOOP, 15 October): the Prospector's moves** (o7-moves, `orks/prospector/walk|dig|carry`, six frames each;
`js/camp/orks.js` `Prospector`). The mine's keeper stands just east of the headframe, in front of it. It paces its
ground there while it waits, digs while Research runs (its building busy), and carries a sack to the stop as a
result leaves. Shots: `img/loop/prospector-moves.png` (walk, dig, carry), `prospector-dig.png`. A dropped-class slip in
`Ork` that kept every steward's lift animation from showing is fixed with it.

### 4d. The Agent pool as the depot (the owner, 15 October; not built)

The Agent pool is the camp's heart: the orks build the person's project there. So it becomes **a station, the
depot**, drawn as an engine shed over the track; carts roll **into** it. Its words do not change (Agent pool; its
orks are Grunts and their steward); this is its look, as the booth, the weighbridge and the mine are (§4.11).

1. **On the line itself** (the owner, said twice): the depot is a shed over its line, the line running through it
   west to east, doors at both ends (`buildings/depot.png`, st-depot #4). Carts roll in at the west doors and out at
   the east. A cart for another building rolls straight through without stopping; a cart for the pool stops inside.
2. **A bay per ork.** The shed's front has three open bays along the track (`max_orcs`, 3 by default, drawn at most
   3; more is a `+N` chip): a cart stopped in a bay is a Grunt at work on it, its bubble over that bay; an empty bay
   is free room, its shutters closed (`depot/doors.png`). **Busy or free reads from across the camp without a badge.**
   A cart waiting for a free bay waits on the line before the west doors (the queue of §4c rule 7); a cart passing
   through waits behind it too, honestly.
3. **Out the east doors.** Done, the cart rolls out and back onto the line at the second switch, towards the Review
   gate. With Mission 1b's check on, the **proving siding** (first-mission.md §10.1) is the depot's exit track: the
   semaphore arm at its mouth; a failed check sends the cart back into its bay from the exit side (shunting on the
   depot's own track, never on the main line), `round 2 · tests failed` on its chip.
4. **No pocket and no path** (§4c rule 7 does not apply to stations): the bays are where its carts wait.
5. **Size.** About two buildings wide (it is the largest building, and should be); a row counts it as two of its five
   places. In Office its card is unchanged.
6. **Its steward** stands by the west doors, where carts come in (§4.3).

**Art:** done, st-depot #4 (d88f5a6): the shed on the line with the track through it, three bays along its front,
shutters, and the semaphore in two positions (`depot/semaphore-0|1`).

**Priority: P0**, the next work of the LOOP session after its fixes and before its step 4 (they share `layout.js` and
`track.js`); about 2 days. The pool's old building sprite stays for Office's card if wanted.

**Built (LOOP, 15 October).**
- **On its line.** The Agent pool draws `buildings/depot.png` in Camp, its own rails laid over its line's
  (`layout.js` `DEPOT`, `DEPOT_BAYS`), with no path and no pocket. It takes two of a row's five places. Its steward
  stands by the west gateway.
- **Bays.** A cart for the pool rolls in at the west gateway to its first free bay and stops on the through track; a
  cart behind it waits. With every bay busy it stops on the line before the gateway. A cart for a building beyond
  rolls through.
- **Busy or free.** Busy bays (its Grunts at work) show the cart in hand, free ones their shutters
  (`depot/doors.png`), more than three a `+N` chip.
- **The exit.** `depot/semaphore-0` stands at the east gateway where the exit track begins. Raising it, the verdict
  and the shunt back into a bay are Mission 1b's.
- Shots: `img/loop/depot.png`, `depot-busy.png` (its bays and queue injected by the shot script).

### 4e. Ground: a track bed under every rail, narrower paths, varied tiles (the owner, 15 October; not built)

1. **A track bed under all track.** Every track tile (lines, columns, the return line, sidings, pockets, the depot's
   tracks, the stations' spurs) stands on **earth**, not grass: a band of path earth one track tile wide with the
   path's grass rims along both sides, following the track round its curves and junctions. The camp reads as worn
   ground where carts run; grass is where nothing does. Items never stand on it (v3-prompts §14 rule 1, already).
2. **Narrower building paths.** `PATH_W` goes from 32 to **24** art px (about an ork and a half wide at the default):
   the paths are the orks' footways, the track bed is the wide earth. The gap between buildings stays 32 (§4.8).
3. **Varied tiles, never one stamp.** Grass and earth each get several tiles chosen by a fixed hash of the cell (the
   same camp always draws the same), so no pattern repeats in rows:
   - grass: 4 plain variants, 2 with a few tufts, 1 with small flowers (the decor stays sparse, §4.9);
   - earth: 3 plain variants, 1 with small stones, 1 with old cart ruts (track bed only);
   - rims and corners: all four outer and **all four inner** corners (only `inner-ne` exists), for earth on grass,
     so a path meeting the track bed joins cleanly.
4. Calm values: the earth stays the paths' warm sand (about #e4b469), a step darker under the rails so the sleepers
   read; nothing as light as `signal-ask` (§5).

**Art (GEN):** `g5-ground`: the tiles of rule 3 at 64 × 64 (grass, earth) and the rims and corners at the path's
gauge; the track bed's curve and junction pieces to match c2's curves and c3's junction. **Code (LOOP):** the bed,
`PATH_W` 24 and the hashed variants, with today's `earth.png` and rims standing in until g5 lands. **Priority: P0**
(the look comes first, decisions §13.1–2), after the depot.

**Built (LOOP, 15 October).** `js/camp/ground.js` and `town.js` `Bed`:
- **The bed.** A square of path earth lies under every track tile (lines, columns, the return line, sidings, pockets,
  under the depot), a step darker, with the grass's rims on its open sides. All rims are drawn first and the earth
  over them, so the bed joins itself and a path with no seam.
- **Paths.** `PATH_W` is 24.
- **Variants.** Grass and earth take g5's variants by a fixed hash of the cell (`ground/grass-1…4`,
  `grass-tufts-1|2`, `grass-flowers`, `earth-1…3`, `earth-stones`, `earth-ruts`, ruts on the bed only); each is
  drawn once cut into the manifest. Until then today's earth stands in, shifted by the hash, and today's tufts and
  flowers sit on a few of the cells the hash gives them.
- **Not yet.** The bed's curves and junctions are squares until g5 draws them.
- Shot: `img/loop/depot-and-bed.png`.

## 5. Signals win by value

The grey test of F1 (v3-prompts §5.2) showed the yellow flag turning into a white flag and the ❓ smaller than the
light stone. So signals are **UI drawn by the product** (layer 8), never in the art, and win by value, not hue alone:

- ❓, `!`, ⏳ are **28 px** (32 on the phone, a 44 tap area), the glyph in its `signal-*` on a **`chip` plate** with a
  1 px `art-outline` border and a 1 px `chip-ink` keyline inside it, so the plate reads on the bright grass and on the
  dark shade alike; a short tail points at the head or door it marks. ⏳ is drawn, not the emoji (an emoji wears its own
  yellow).
- **A cart's flag** is outlined in `art-outline` (2 px) with a darker lower band, and a waiting cart always shows
  its chip (`#42 · Fix login bug`) under it.
- Nothing in the art is as light as `signal-ask` (§2.3).
- Order of loudness unchanged (v2 §5.5): ❓ → `!` and 🔥 → a waiting cart's chip → the track → buildings → orks and
  carts at work → the ground. Check it in the preview's **Grey test**.

## 6. Type

**The faces** (all SIL OFL 1.1, shipped in `design-system/fonts/` with their licences, no network):

| role | face | why | Cyrillic |
|---|---|---|---|
| display: titles, the map's chips | **Pixelify Sans** (500) | a true pixel face that stays readable at 14 px; already the War Map's and Camp's titles' (v2 §12, answer 3) | yes (kept) |
| labels and running text | **Nunito** (400, 600, 700, 800) | rounded, friendly, very legible at small sizes; fits a cosy camp better than Titillium Web's technical narrowness | **yes, new** (Titillium had none) |
| the terminal, code | **JetBrains Mono** (400, 700) | unchanged: built for code, clear at 13–14 px | Latin shipped, as today |
| the wordmark | Almendra SC | unchanged, the product's name only | — |

Titillium Web stays shipped as Nunito's fallback (`--font-camp: "Nunito", "Titillium Web", …`), so nothing breaks
while a machine still has the old page cached.

**The type scale, one step larger** — Camp, the monospace, and Office too (the owner, v3-prompts §8): Office's title
20 → 22/28, heading 11 → 12/16, label and body 13 → 14/20, caption 12 → 13/18, chip 12 → 13/16. Camp's:

| style | face | v2 | **v3** |
|---|---|---|---|
| `camp-title` | Pixelify Sans | 28/32, 700 | **32/40, 500** |
| `camp-heading` | Pixelify Sans | 18/24, 700 | **20/24, 500** |
| `camp-chip` | ~~the UI face~~ **Pixelify Sans** | 12/16, 600 | **14/16, 500** |
| `camp-label` | Nunito | 13/16, 700 | **14/20, 700** |
| `camp-body` | Nunito | 15/22, 400 | **16/24, 400** |
| `camp-caption` | Nunito | 12/16, 600 | **13/18, 600** |
| `camp-number` | Nunito | 13/16, 700 | **14/20, 700** |
| `code` | JetBrains Mono | 13/20 | **14/20** |
| `code-small` | JetBrains Mono | 12/18 | **13/18** |

The pixel face is set at its shipped weight (500): a browser's synthetic bold smears a pixel face. Every style is now
also a CSS variable, `--type-<style>` (`font: var(--type-camp-body)`), written by `python -m orkcraft.design.tokens`;
new components (I1, I2) name the variable, never a size. The building windows' role classes (`.ok-font-*`) follow the
new scale already; the older hand-sized rules in `components.css` and the GUI's sheets move to the variables as I1 and
I2 redraw them.

## 7. The preview

`design-system/previews/CampKitV3.html` (open it from the folder; no server needed): the 1440 × 900 frame — the HUD
(the camp's name on parchment, 🔥 ❓ 🥩 counters, Stop all in teal), the ten buildings of §4 on the grid, the loop with
its way in at the tower's foot and its buffer stop at the catapult, the stations (the booth's siding with three carts
and `+2`, the gate's weighbridge, the mine's shaft), paths, the low palisade with its right wall, carts (three rolling,
three waiting on the siding, one at the Test bench, one held on the weighbridge with its flag and chip), orks (keepers
at the stops, one lifting the load at the gate, one asking with ❓, the Prospector at the mine), growth on three
buildings. Below it: **the person's eleven classes**, the palette before and after, the signals, the type, and **every
v3 sprite awaited or arrived**.

Each piece is drawn from **the v3 sprite** in `design-system/sprites/v3/` once its sheet is cut, else **v2's
placeholder** (darker, and drawn at ×1 where its art pixel is finer than v3's), else **a block in v3's tokens**.
Toggles: *Grey test*, *Show v3 slots* (each sprite's slot, dashed, with its size), *Building names*, *Blocks only*,
*Gate clear* (the barrier up, no cart on the weighbridge).

Screenshots at 1440 × 900 on a density-2 screen (re-shot at the end of round 9: ×1.5, the overview, the classes):
[the overview](img/v3-preview/v3-town-overview.png), [the classes](img/v3-preview/v3-classes.png),
[the gate clear](img/v3-preview/v3-town-gate-clear.png), [the town](img/v3-preview/v3-town.png),
[in grey](img/v3-preview/v3-town-grey.png), [with the slots](img/v3-preview/v3-town-slots.png); at density 1 (×1):
[the town](img/v3-preview/v3-town-dpr1.png); the labels sit just under each building's foot, the top row's on its facade so they clear the track (round 6); before the first sheet: [round 1](img/v3-preview/v3-town-round1.png).
The preview is written by `tools/campkit_v3.py` from `tools/campkit_v3.html` (`--v3` runs it after cutting).

## 8. The sheets: names, sizes, one command

The owner saves each sheet of v3-prompts §3 into `docs/design/img/references/v3/` under **exactly** its name below,
then runs:

```
python tools/camp_sheet.py --v3            # cut every sheet that is there; list the rest as awaited
python tools/camp_sheet.py --v3 --expect   # only list the sheets, their sprites and sizes, and which have arrived
python tools/camp_sheet.py --list docs/design/img/references/v3/b1-core.png   # a sheet's pieces in reading order
```

The sprites go to `design-system/sprites/v3/` with their `manifest.json` (beside v2's `camp/`, so nothing in the GUI
moves until I1 switches). The sheets are asked "in a neat grid with even spacing", so a piece is named by its
**order** (reading order: rows top to bottom, each left to right, from 0), not by a point; if the model drew one out
of order, the numbers in `tools/camp_sheets_v3.json` change, never the names.

**Cut as drawn** (the spec's `native` and `keep_colours`, after round 3): each sprite is read at the sheet's own art
pixel and never re-read coarser; its slot is what the sheet draws, rounded up to 8 (the sizes below are the plan the
prompts ask, not a crop); **the art keeps its own colours and shading** — no snap to the tokens. The tokens stay the
palette the product draws with (ground, paths, chips, its own shapes) and the reference the prompts ask the model to
keep. The cutter only **reports** pixels in a signal's yellow, orange or red (saturation ≥ 0.75, value ≥ 0.7, hue
340°–65°; the honey wood and the sand sit well below), and such a sprite is redrawn; only the signals' sheet may have
them. Round 3's report: the UX bench's banner (1.4 % of its pixels) and a few px of the Review board's fire.

**Tiles must tile, so they are not "whatever the sheet draws"** (`kind: track`, c2): the tile's length is a whole
number of the straight piece's tie spacings (`ties`, 4), rounded to the grid of 8 — the one place v3 resamples, along
the rails by a few per cent; a straight tile is one tie spacing repeated, so it joins itself exactly as it joins inside;
every other piece is placed so its rails cross each of its `exits` at the tile's middle, and a rail that stops short of
an edge is carried on to it. On c2: ties every 15.0 art px, four of them 60 → **a 64 × 64 tile** (×1.067), shown ×1;
across a seam the step equals the step at the same place inside (16 and 16 on the straight, 4 and 4 on the vertical).
[Crop at ×1.5](img/v3-preview/track-c2.png).

**c1 and c2, mapped by their geometry** (round 5): c1 by point, since the code cart and the flag cart below it touch —
row 1 `empty`, `code`, `asset` (the crate), `message`, `doc`, `bundle`; row 2 `flag-none`, `flag-flag`, `flag-held`
(the hourglass), and `pile` (four at the buffer stop); the rolling row is three-quarter and not cut. c2 by order: 0
straight-h, 1 straight-v, 3 corner-se, 4 corner-sw, 6 corner-ne, 8 t-n, 9 t-s, 10 switch-e (two tiles long), 11 the
merge and the crossing drawn touching (cut by halves: merge-e two tiles long, cross), 12 stop-e; not used: 2 (a vertical
switch) and 5, 7 (smaller south-east curves). **There is no north-west curve yet**: the next c2 asks for it.

**g1, g2, u1** (round 6). **g1, the ground:** plain grass is the token `world-grass` itself; the sheet's grass
(`#507937`) and earth (`#664633`) are moved onto the tokens' (`world-grass`, and `world-earth`, F1's sand) so an edge
meets the plain grass with no step and the paths keep F1's sand; outlines stay. Cut with `kind: ground`: the tufts and
the flowers as **decals** (their plain grass transparent), the **earth fill** from inside its drawn border (32 × 32,
repeating), and **rims** from the edge tiles (`rim-n`, `rim-s`, `rim-w`, `rim-e`: the grass side to just inside the
earth, laid along a path's open sides, its earth side flush with the path); the corners `corner-ne`, `corner-nw` and
an inner corner kept whole (no south corners on the sheet). In the preview the paths and the lane are earth with grass
rims, the rims left open where paths join. **g2, the decor:** seventeen pieces plus a dry brush and a mossy log drawn
touching (cut by halves), scattered sparsely in the wilderness round the camp only. **u1, for I1:** the bubble's nine
pieces (`ui/bubble/nw…se`) and its two tail dots, three scroll columns (`ui/scroll/a|b|c-top|sheet|bottom`), the long
`banner`, three rings (`ui/ring-s|m|l`, the small one dashed); nine-slice pieces keep their exact size (`exact`), so
some are off the grid of 8 — I1 uses them as drawn. No UI is built from them here. g3 (the palisade) is not cut.

**o1 and o2** (round 5, the owner's ork): o1 by order, rows idle 4, walk-down 6, walk-up 6, walk-side 6, work 6, door 4;
o2 row 1 in the prompt's order without the pathfinder (warchief … warder, prospector, loader), the pathfinder from row 2
(19). Both with `degrid`. The signal check does not flag the warder's key or the prospector's lamp (their yellow is
below its saturation and value); the taskmaster keeps a pink smudge by its quill. o3 and o5 are not cut (another ork;
regenerated on o1). The 0.3 stand-ins of round 4 are gone: c1, c2 and o1 replace them.

**A drawn grid** (round 4: the model drew a box round every cell of the ork sheets, which joined the sprites): a sheet
with `degrid` (set on o1–o5) has the grid dropped before the pieces are found — long (≥ 120 px), thin (≤ 14 px) dark
straight runs with the background on both sides, the key's own darkened violet, and a cut along any line drawn across
most of the sheet, so a smudge across a line cannot join two cells. Tried with `--degrid --list` on the round-4
references: o1 reads 32 pieces in rows of 4/6/6/6/6/4 (45 without), o2 two rows of 11 (11 blobs without). It stays off
for the building sheets, where it would eat a building's own straight outlines (B1's catapult was lost in the test).

**Re-pixelised** (the sheets are soft: the model renders at about 4.17 image px per art px and smooths it, and the
JPEG blurs again — inside one art pixel the colour varies by about 25 of 255): each art pixel is the **median of its
cell's inner pixels** (the cell's edges skipped); the **magenta cast** near the key is removed (an opaque pixel within
3 px of the background whose red and blue both stand well above green, blue at least ¾ of red — the plum cloth is
redder — takes the median of its clean neighbours); then the sprite is reduced to **its own 24 colours** (a median cut on
its own pixels, not the tokens) with a hard alpha. The signal check runs before that reduction, so a banner's orange
cannot be averaged away. The Agent pool went from 6 530 colours to 24, its floor's purple cast gone:
[img/v3-preview/agent-pool-repixelised.png](img/v3-preview/agent-pool-repixelised.png).

| file | v3-prompts | sprites (planned art px) |
|---|---|---|
| `b1-core.png` | §3a B1 | `buildings/` watchtower 96×128, fields 128×96, barracks 128×112, loot_vault 128×112, lake 112×96, catapult 128×112 |
| `b2-town.png` | §3a B2 | town_hall 128×128, council 112×96, mine 96×128, scrolls 96×96, lab 96×96, ux_lab 96×96 |
| `b3-plumbing.png` | §3a B3 | signpost 64×80, mill 96×96, workshop 80×80, pit 64×64, loot 96×80, forge 96×96 |
| `b4-others.png` | §3a B4 | crag 64×80, war_drum 80×80, forest 96×96, gramophone 80×80, horn 64×80, custom 80×80 |
| `b5-doors.png` | §3a doors | `doors/<type>.png`, 32×40 × 3 states, for the core six (one row each, B1's order) |
| `o1-body.png` | §3b.1 | `orks/body/` idle ×4, walk-down ×6, walk-up ×6, walk-side ×6, work ×6, door ×4; 32×32 |
| `o2-roles.png` | §3b.2 | `orks/roles/` the twelve roles, 32×32 |
| `o3-states.png` | §3b.3 | `orks/states/` working, asks, stuck, held, doze; 32×32 |
| `o4-faces.png` | §3b.4 | `orks/faces/` twelve at 16×16, then twelve at 24×24 |
| `o5-inside.png` | §3b.5 | `orks/inside/` carry ×6, lens ×4, quill ×4, pin ×4 (for I2) |
| `c1-carts.png` | §3c.1 | `carts/` empty, code, asset, message, doc, bundle 32×24; flag-none, flag-flag, flag-held 32×40; pile 128×40; rolling ×4 |
| `c2-track.png` | §3c.2 | `track/` 12 tiles, 32×32 |
| `g1-ground.png` | §3d.1 | `ground/` grass-0..2, earth-0..1, edges n e s w, corners ne nw se sw; 32×32 |
| `g2-decor.png` | §3d.2 | `decor/` tree-0..1 32×48, bush-0 32, bush-1 16, rock, stump, reeds, mushrooms 16, logs 32 |
| `g3-palisade.png` | §3d.3 | `edge/` palisade-h, corner-nw, corner-ne, end-w, end-e, gap; 32 wide |
| `u3-icons.png` | §3e.3 | `icons/` the eighteen action icons, 24×24 |
| `u4-signals.png` | §3e.4 | `signals/` ask, fire, held at 16 and 24; flame, flag-ask, flag-fire 16 |
| `u1-bubble.png`, `u5-hud.png` | §3e.1, .5 | nine-slices and the HUD: listed, cut by I1 |
| `u2-panels.png` | §3e.2 | `ui/panel/` parchment, terminal (its tabs cropped off); `ui/tab/` active, inactive; `ui/button/` normal, hover, pressed — cut (round 11), not yet drawn by the GUI |
| `u6-inside.png`, `u6-cards.png` | §3e.6 | `inside/` booth (the backdrop), board (one board's frame), sheet, slab, pin, flag-down, flag-half, flag-up, lever — drawn by the Task board's inside (round 11) |

PNG is best (a JPEG's noise blurs the key and the colours); a sheet saved as `.jpg` or `.jpeg` under the same name is
found as well.

**One-building sheets** (`over`): `b1-catapult.png` (v3-prompts §8, the catapult alone in side view against a low log
wall, four frames; frame 0 is the building), `b1-lookout.png` (the tower built into a low log wall, §7.3) and
`b1-taskboard.png` (the Task board at core size, 160–192 wide, §9) are their own sheets in `tools/camp_sheets_v3.json`,
listed after B1 with `"over": "b1-core"`: once one is there, its sprite replaces B1's of the same name
(`buildings/catapult.png`, `watchtower.png`, `fields.png`); until then B1's stays. The preview lists each sprite once.

**Generated, then picked** (`tools/gen_sheets.py`, internal, never shipped): the sheets come from the Gemini API's
image model with the key in `GEMINI_API_KEY`, never the `agy` CLI or a Google login (decisions-2026-10.md §5). Each
prompt is v3-prompts §3's head, the sheet's prompt and the reviews' lines (front-on, no frames, no smoke or glow, no
ground, F1's colours, no signal hues; the same orc on an ork sheet); F1 is always attached, with b1-core for buildings,
o1 and o2 for orks, c2 for the track. Candidates go to `img/references/v3/candidates/<sheet>/<n>.jpg` (the model sends
JPEG, whatever the prompt asks; the API has no PNG option) with a report of the cutter's own checks — pieces found
against expected, the art pixel, the pieces' size in art px against the taken sheets', signal-hue pixels, the magenta
cast — and [candidates/index.html](img/references/v3/candidates/index.html) shows them side by side. Only
`python tools/gen_sheets.py --pick <sheet> <n>` writes a cut sheet's name, then runs `camp_sheet.py --v3`.
`c2-curves` (the four curves, the merge and the crossing apart) is generated but not yet in the cut spec: once picked,
its pieces are mapped into c2's track set.

**Round 7, picked from gen_sheets** (the owner, through the PM session): b1-lookout #3, b1-catapult #3, b1-taskboard #1,
b2-town #1, b3-plumbing #1, b4-others #3, o3-states #3, o5-inside #1, g3-palisade #1, c2-curves #1, saved under their
cut names and cut. Mapped by order: the lookout is piece 1 (0 is a smoke puff), the catapult frame 0 is piece 1 (the
log stack beside it, the scrolls and the other frames are not cut); B2 with `close` 4 so the fire ring's stones are one
piece, its second Town Hall (3) not used; B3's second chute (4) not used; B4's sundial (2), sign board (4) and second
horn (7) not used; g3 drew no corners (a corner is not seen front-on): `palisade-h` 0, `gap` 1, `end-w` 2, `end-e` 3,
the corners wait. Left to fix: the Task board is drawn 400 × 296 (about twice the Agent pool) and, with the lookout,
has orange wood (the signal check); o3 and o5 are drawn at about twice o1's art pixel; c2-curves is not mapped yet.
A single-frame sprite whose feet are off its middle (the forge's anvil) is centred on its box when centring on its
feet would cut a side off.

## 9. What the owner generates next

In this order, each with **F1 attached** and the line of v3-prompts §6, with the measured values: "keep exactly the
colours of the attached frame F1: the grass as saturated and bright as in it (about #7cbd40), the paths warm sand
(about #e4b469)":

1. **B1, the core six** (v3-prompts §3a), with these changes to its prompt: the lookout tower **with its legs in a low
   log wall** and a gap at its foot; the catapult **against a low log wall** at a buffer stop; the Review gate rough
   timber and stone with bone tusks, **no crenellations**; the gate's stone and the book a step darker.
2. **The doors** of the core six (b5).
3. **o1 and o2**, the ork's body and the roles, at **32 × 32**.
4. **c1 and c2**, the carts and the track; **g1 and g3**, the ground and the low palisade.
5. **u4**, the signals (the only sheet with yellow and red), then B2–B4, o3–o5, g2, u3.
6. I1 asks for u1, u2, u5; I2 for u6.

After each sheet: `python tools/camp_sheet.py --v3`, then open the preview; the piece takes its slot.

## 10. The owner's answers (v3-prompts §8)

1. **Nunito** for labels: yes.
2. **The catapult in side view**, against the right wall; the palisade runs down the right edge (§4.5–4.6).
3. **A lane per row** of buildings, joined to the main line by short paths; carts on the line only (§4.1).
4. **Office** a step larger too (§6).
