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
| the scale | art at ×1 at the overview, ×2 close, ½ for the map from half-size copies | art **drawn at half, shown at ×2** in the town; ×1 the map, ×3 close; no derived copies (§3) |
| the ork | a 32 × 48 frame | **32 × 32** (64 screen px) |
| the cart | 48 × 40 bin and a 48 × 32 load | **32 × 24** with its load (64 screen px wide) |
| a building | a cover kit that lifts (nine-slice roofs and walls, facade, crest) | **one sprite with a door**; the keeper steps out of it (§13.1); the cover kit is superseded |
| spurs | a rail spur to each building | **one main line**; dirt paths join the buildings to it; carts stop opposite a path (§4) |
| the camp's edge | a palisade of sharpened 48-px stakes | a **low palisade of rounded logs**, 32 tall; the lookout tower in it, the catapult against it (§4) |
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

**Sprites are drawn at half and shown at ×2** (`--art-scale: 2`). The grid stays v2's: every sprite a multiple of 8
art px; ground and track tiles 32 × 32; the layout cell 16.

**The ladder** (whole numbers only, as in v2 §2.3): **map ×1** (the whole camp, art at its own size — no half-size
copies any more), **town ×2** (the default, the frame's), **close ×3**. On a fractional `devicePixelRatio` the camera
picks the nearest whole device scale, as before. The inside of a building is its own screen (I2), drawn at ×2.

**The window: 1440 × 900.** A 36 px HUD, then the world of **720 × 432 art px** at ×2 (1440 × 864).

| piece | art px (drawn) | screen px at ×2 | token |
|---|---|---|---|
| a core building on the line (Task board, Agent pool, Review gate, Publisher), the Town Hall | 128 wide, 96–128 tall | 256 | `footprint-xl` |
| Inspector, Review board | 112 × 96 | 224 | `footprint-l` |
| External listeners' tower, Research | 96 × 128 | 192 × 256 | `footprint-m` |
| Wiki, Test bench, UX bench, Transformer, Branches & PRs, output | 96 × 80–96 | 192 | `footprint-m` |
| Script, Calendar, Audio briefing, a building of one's own | 80 × 80 | 160 | `footprint-s` |
| Router, Drop file here, Metrics, Sound alerts | 64 × 64–80 | 128 | `footprint-xs` |
| a door state (a patch over the building at its door) | 32 × 40 | 64 × 80 | — |
| the ork, one frame | **32 × 32** | **64** | `ork-frame-w/-h` |
| a mine cart with its load | **32 × 24** (the flag's pole 24 more) | **64** × 48 | `minecart-w/-h` |
| a ground or track tile | 32 × 32 | 64 | `ground-tile`, `track-tile` |
| a dirt path's width | 16 | 32 | `path-w` |
| the palisade's height | 32 | 64 | `palisade-h` |
| a chip (UI, at every zoom) | — | 24 (28 on the phone) | `chip-h` |
| a badge ❓ ! ⏳ (UI) | — | 28 (32 on the phone) | `badge`, `badge-touch` |

**Ten buildings on the window** (the preview's town, art px):

| row | buildings, left to right | widths + gaps |
|---|---|---|
| the wall and the line's ends | External listeners in the palisade (top left); the Publisher against it at the line's end (right) | 96 · 128 |
| above the line (taking work from it) | Task board · Agent pool · Review gate | 3 × 128 + 2 × 16, from x 152 |
| below the line | Inspector · Research · Test bench · Town Hall · UX bench | 112 + 3 × 96 + 128 + gaps of 32 = 664 of 720 |

Heights: the palisade 32, the upper row's feet at 192, paths to the line at 224–256, the lower row's tops from 288,
its feet and the lane in front of it at 416–432. It fits with no building overlapping another; an eleventh does not
fit without crowding, as asked.

**What this supersedes in v2:** §2.3's ladder, §2.4's footprints as cards, §4f's 32 × 48 ork (the owner's answer 4),
§4e's 48 × 32 cart, the half-size map copies (answer 5), the sizes by S/M/L (answer 8: the core buildings are now one
size, XL).

## 4. Layout rules (decided the night of 14 October)

1. **One main track line** runs left to right in the work's order. **No rail spurs:** each building is joined to the
   line by a **dirt path** (`world-earth`, 16 wide, a `world-grass-dark` rim) from its door.
2. **Carts stop opposite a path.** The stop is where a path meets the line; the line's last cell is the buffer stop at
   the catapult.
3. **The keeper waits at the stop.** A building that takes work from the line (Task board, Agent pool, Review gate,
   Inspector) has its keeper at the end of its path; where the keeper stands says its state (v3-prompts §5): at the
   stop looking down the line = waiting for work; lifting the load off a stopped cart and carrying it in = work
   arrived; inside, its bubble over the roof = working; at its door with ❓ = asking the person.
4. **Orks never push or ride carts.** The keeper lifts the load off and carries it in, and puts the result back on a
   cart at the stop.
5. **The two buildings that face the world stand in the wall.** External listeners' lookout tower is **built into the
   palisade**; the track comes in from outside through a gap at **the tower's foot**. The Publisher's catapult stands
   **against the palisade at the line's end** and throws over it. *Whatever crosses the camp's border stands on the
   wall* — the way in on one side, the way out on the other (for now only these two).
6. **The palisade is low, of rounded logs** (32 tall, never sharpened), along the back and down the side the catapult
   throws over; nowhere round a building.
7. **A building is one sprite with a door** (§13.1): no lifting cover, no nine-slice roof, no facade or crest slot.
   The door is in the lower middle of its front; its three states (closed; open, warm light; the keeper half out) are
   a 32 × 40 patch drawn over it. The cover kit (v2 §4a–4c) stays only until I1 takes it out.
8. **Few orks:** an ork is a session; a camp shows four to eight. Edges are quiet (few crates and bushes) so the eye
   stays on the line.
9. The town's name is the person's (the project's name, "My camp" in the previews), never a character's.

**Layers** (v2 §3, revised): ground · paths and track · buildings · carts · orks · **doors** (the patch over a
building, sorted with it) · signals · chips · UI. The covers' layer is gone. Shadows stay the product's.

## 5. Signals win by value

The grey test of F1 (v3-prompts §5.2) showed the yellow flag turning into a white flag and the ❓ smaller than the
light stone. So signals are **UI drawn by the product** (layer 8), never in the art, and win by value, not hue alone:

- ❓, `!`, ⏳ are **28 px** (32 on the phone, a 44 tap area), the glyph in its `signal-*` on a **`chip` plate** with a
  1 px `art-outline` border and a 1 px `chip-ink` keyline inside it, so the plate reads on the bright grass and on the
  dark shade alike; a short tail points at the head or door it marks. ⏳ is drawn, not the emoji (an emoji wears its own
  yellow).
- **A cart's flag** is outlined in `art-outline` (2 px at ×2) with a darker lower band, and a waiting cart always shows
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

**The type scale, one step larger** (Camp and the monospace; Office keeps its editor's scale):

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

Screenshots of the preview on 14 October, before any v3 sheet: [the town](img/v3-preview/v3-town.png) (v2's
stand-ins where they exist), [in grey](img/v3-preview/v3-town-grey.png), [blocks only, with the
slots](img/v3-preview/v3-town-blocks-slots.png).

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
of order, the numbers in `tools/camp_sheets_v3.json` change, never the names. A group is read at one scale so that its
largest piece fits its slot; colours are snapped to the v3 tokens; only the signals' sheet may keep yellow and red.

| file | v3-prompts | sprites (art px) |
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

## 10. Open questions for the owner

1. **Nunito for labels** instead of Titillium Web: friendlier and with Cyrillic, but rounder; the alternative is to
   keep Titillium (no Cyrillic) at the larger sizes.
2. **The palisade down the right side:** the catapult stands against a wall, so the preview runs the palisade down
   the right edge as well as the back. Keep, or only along the back with the catapult at its corner?
3. **The lane in front of the lower row:** the lower buildings face the viewer, so their doors open onto a lane at the
   bottom, joined to the line by three short paths (each a stop). Keep, or a path per building?
4. **Office** keeps its type scale; should it also go a step larger?
