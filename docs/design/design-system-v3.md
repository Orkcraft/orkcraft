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

**The zoom steps keep whole device pixels** (buildings / orks and track): on density 2, **×1.5 / ×1** (default),
×3 / ×2 (close), and ×1 / ×1 (an overview: whole, the orks a little large); on density 1, **×2 / ×1** (default) and
×1 / ×1. The wheel steps through them, **drag pans**; the default view is centred on the work (the back wall to line 2),
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
   another row with its own line, joined into the loop the same way. (This replaces round 4's lane per row.) c2 has no
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

**Layers** (v2 §3, revised): ground · paths and track · buildings · carts · orks · **doors** (the patch over a
building, sorted with it) · signals · chips · UI. The covers' layer is gone. Shadows stay the product's.

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
(the camp's name on parchment, 🔥 ❓ 🥩 counters, Stop all in teal), the ten buildings of §3 on the grid, the main line
with its way in at the tower's foot and its buffer stop at the catapult, paths and the lane, the low palisade, four
carts (two rolling, one stopped, one held at the Review gate with its flag and chip), six orks (keepers at the stops,
one lifting the load at the gate, one asking with ❓). Below it: the palette before and after, the signals, the type,
and **every v3 sprite awaited or arrived**.

Each piece is drawn from **the v3 sprite** in `design-system/sprites/v3/` once its sheet is cut, else **v2's
placeholder** (darker, and drawn at ×1 where its art pixel is finer than v3's), else **a block in v3's tokens**.
Toggles: *Grey test*, *Show v3 slots* (each sprite's slot, dashed, with its size), *Building names*, *Blocks only*.

Screenshots at 1440 × 900 on a density-2 screen (×1.5, round 5): [the town](img/v3-preview/v3-town.png),
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
| `u1-bubble.png`, `u2-panels.png`, `u5-hud.png` | §3e.1, .2, .5 | nine-slices and the HUD: listed, cut by I1 |
| `u6-inside.png` | §3e.6 | the Task board's inside: listed, cut by I2 |

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
