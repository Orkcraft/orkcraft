# Design — the design system, v2: one system for the new Camp

Status: proposal 2026-10-14. It turns the art direction of 12–14 October into one system that engineering can build
the new Camp on (backlog C2–C6). What is settled here is written into [../design-system.md](../design-system.md),
`design-system/components.md`, `design-system/sprites/README.md` and the tokens. The owner's calls are in §12.
Builds on [color-pass.md](color-pass.md) §6a–6d and §9c–10c, [town-readability.md](town-readability.md),
[camp-story.md](camp-story.md), [work-and-play.md](work-and-play.md), [asset-prompts.md](asset-prompts.md),
[portrait.md](portrait.md) §3. The art it is measured against: `docs/design/img/references/0.3/` (ten reference
sheets) and the concept frame [img/orkline-camp-concept-v2.png](img/orkline-camp-concept-v2.png) (and `-grey`).
Preview: `design-system/previews/CampKit.html`. The artist's brief made from it: [artist-brief.md](artist-brief.md).

**Held to throughout:** a look changes the drawing, never a word (CLAUDE.md). The town says road, cart, Task board,
Agent pool, Review gate, Inspector, External listeners, Publisher, whatever Camp draws them as.

## 1. The audit: today's system against the new art

Today's system ([../design-system.md](../design-system.md), `design-system/`) was made for **cards with a small
building on top**: a 2:1 header sprite as a finial on a bevelled card, roads as 16 px dirt tiles, a 20 px cart, a
24×16 ork head. The new art is **a three-quarter camp in which the card is the building**. Measured on the 0.3 sheets
(each snapped to its own grid: one art pixel is about 6 screen pixels on every sheet but the track's):

| piece | 0.3 sheet, in art pixels | asked by the prompts | today's slot |
|---|---|---|---|
| the ork (one frame) | ≈ 28–32 × 44–48 | 32 × 32 | 24 × 16 (a head) |
| a mine cart, side view | ≈ 58 × 44 (load included) | 32 × 24 | 20 × 18 |
| a crest | ≈ 45–55 × 70–100 | 32 × 32 | — |
| a facade | ≈ 140–195 × 105–115, on an island of grass | 96 × 48 | — |
| the gatehouse | ≈ 172 × 120 | 128 × 96 | 96 × 48 header |
| the lookout tower | ≈ 116 × 233, isometric | 64 × 128 | 96 × 48 header |
| a wall kit piece | ≈ 45 × 40 | nine-slice | — |
| a roof kit piece | corners ≈ 42 × 40, edges ≈ 81 × 42 | nine-slice | — |
| a track tile | ≈ 72–96, its own pixel size | 32 | 16 |

### 1a. What holds

1. **Roles, not values.** Building UI documents name a font role and a tone; the GUI maps them to tokens
   (`orkcraft/design/tokens.json` → `design-system/tokens.json`). Nothing in the new Camp needs a document to say a colour.
2. **Camp's chrome after the colour pass:** warm wood, bone focus, maroon cloth, yellow and red kept for signals
   (`test_camps_chrome_is_wood_and_maroon_and_reads`). It is already the new art's palette.
3. **Whole-number scaling and `image-rendering: pixelated`** (components.md, Sprite). The new art keeps it.
4. **Square Camp, rounded Office** (`radius-0` against `radius-sm…lg`), the type faces, the space steps.
5. **The town stays simple** (design-system.md §5): one kind of edge, the road; settings in the window, not on the map.
6. **Office** is untouched by the art; it keeps its layout and gets the same components drawn plainly (§9).

### 1b. What breaks

1. **The hut as a card with a header** (components.md Hut, Window, Sprite → Headers) is replaced by the **cover kit**:
   the card is the building, its cover lifts close up ([color-pass.md](color-pass.md) §6a). The header and banner slots
   (`header-*`, `banner-w/h`) stay only until C3 lands, and only for the buildings not yet moved.
2. **The fence round a card** (`fence/`, yards.css) leaves the cards; the walls are the frame and the palisade is only
   the camp's edge (§6a).
3. **Sizes.** Every sheet drifts from what was asked; the ork is drawn at about 32 × 48 and halving it turns it to
   mush (checked: a 16 × 24 reduction loses face, cap and tusks). The scale ladder must follow the art's own detail
   (§2), not the old 16 px road grid.
4. **One projection.** The tower and the second catapult are isometric; the side-view catapult is a step off. The
   facades sit on baked-in islands of earth.
5. **Shadows baked into the magenta** leave a purple fringe; the outlines come out of the JPEGs tinted purple-black.
   Sheets carry no shadows, and the outline is one defined colour (§7).
6. **The roof kits are not nine-slice:** every canvas and hide piece has its frame on all four sides.
7. **The ground.** Today's Camp ground is a dark earth (`canvas`, and `BIOMES` in `js/icons.js`, held dark by
   `tests/test_biome_grounds.py` so a card's words read on the ground). The new camp stands on **lush, calm grass in a
   middle value**. Both are right for what they carry: the dark ground stays behind windows and the old cards; the
   grass is the **world layer** and carries no word at all (words are on chips, §4). Two token families, never mixed.
8. **The signal colours disagree.** Today `alert` (orange `#ff8c1a`) means "a question waits" and `warning` (yellow)
   means a held cart. The new rule ([town-readability.md](town-readability.md) §2–4) is **yellow = a question,
   red = an error or 🔥, ⏳ = held**. v2 adds the signal tokens for the new components; re-pointing today's `alert`
   changes today's Camp and is the owner's call (§12, Q2). *Done (answer 2):* `alert` is `signal-ask`'s yellow in
   every theme.
9. **Display type.** color-pass §5 decided Pixelify Sans for every display text and Almendra SC for the wordmark only;
   the tokens still set `camp-title` and `camp-heading` in Almendra (§12, Q3).
10. **Stale text:** design-system.md still speaks of the terminal face (removed, calm-town.md §9).
11. **References ship.** The wheel carries `design/system/**/*`, so the 0.3 sheets (≈ 22 MB of generated JPEGs) go to
    every machine that installs Orkline, against color-pass §10 ("never shipped") (§12, Q1).

### 1c. What is missing

The grid and scale ladder; the layer order; the cover kits as components with slots; the track autotile set; the
cart's load and flag slots; the ork's role and state slots; the chip and the badge as components with phone sizes;
the zoom levels; the spotlight; the world palette as tokens; a chip type style; motion values; a sprite pipeline for
sheets of this kind (`tools/sheet.py` cuts flat headers on a dark ground into the ork mark's five colours, not keyed
three-quarter art); the artist's deliverables as a list.

## 2. The pixel grid and the scales

1. **The art pixel is the unit.** Every sprite is drawn at its final size, no finer than it can hold.
2. **The grid is 8 art pixels.** Every sprite's width and height is a multiple of 8; anchors sit on the grid.
   **The ground tile and the track tile are 32 × 32** (four grid units), the camp's layout cell (where a building
   stands, where a track runs) is **16 × 16** (half a tile), as today's roads already run on cells
   (`gui/static/js/roads.js`).
3. **The scale ladder: whole numbers of device pixels per art pixel, always.**

   | zoom | CSS px per art px | what it is for |
   |---|---|---|
   | **map** | ½, from a half-size copy made by the pipeline (§11), never resampled live | the whole camp: covers, the track as a line, signals |
   | **overview** (the GIF's) | **1** | covers, carts, orks, chips on exceptions |
   | **close** | **2** | the cover lifted, the card inside the walls |

   On a screen whose `devicePixelRatio` is whole (1, 2, 3) every step is whole in device pixels. On a fractional one
   (1.25, 1.5) the camera picks the CSS scale whose device scale is the nearest whole number (`k / dpr`), so the art
   stays sharp and the camp is a little larger or smaller than asked. **Zoom snaps to the ladder;** between steps it
   eases (§10) but never rests.
4. **The card is the building's inside, at close zoom.** A building's **footprint** (its inside, the card's area) is
   set in art pixels so that at close zoom (×2) the card keeps today's widths:

   | size | footprint (inside) | card at close | overview | for |
   |---|---|---|---|---|
   | XS | 96 × 64 | 192 | 96 | small plumbing |
   | S | 120 × 80 | 240 | 120 | Publisher, Review gate's yard |
   | M | 144 × 96 | 288 | 144 | Task board, Inspector, External listeners' yard |
   | L | 168 × 112 | 336 | 168 | Agent pool |

   Heights are the minimum; a card taller than its footprint grows it in 8 px steps (the walls stretch, §3c). The
   walls stand **outside** the footprint (§3c), so a card never loses room to its frame.
5. **The phone** uses the same ladder (overview 1, a tapped building as a sheet, [color-pass.md](color-pass.md) §6c);
   on a phone `dpr` is 2–3, so the art is 2–3 device pixels to the art pixel, sharp.
6. **What scales and what does not.** The art scales with the zoom. **The UI on the map does not:** chips, badges,
   the spotlight's rope and the cursor are drawn in CSS pixels at their own size at every zoom (§4).

## 3. Projection and layers

**One projection: three-quarter top-down,** the camera tilted so a wall shows its top and its front face, a roof its
slope, an ork its face. Ground, track and floors are seen from straight above; everything that stands (walls, posts,
orks, carts, crests) shows its front. **Never isometric:** every edge runs along the grid's axes; light comes from the
top left; nothing is drawn at 45°.

**The layer order** (bottom to top; the town draws them in this order, each its own layer):

| # | layer | what | sorted by |
|---|---|---|---|
| 1 | **ground** | grass tiles, trodden earth round the walls, the camp's edge (palisade) | — |
| 2 | **track** | rails, switches, buffer stops; the ways in and out through the palisade | — |
| 3 | **floors** | a building's inside: the earth floor, the card at close zoom | — |
| 4 | **buildings** | walls, facades, open-ground scenes, towers and gates, crests | the foot's y |
| 5 | **carts** | mine carts with their load and flag | y |
| 6 | **orks** | orks walking and working (an ork inside a hall is drawn above its floor and below the front wall) | y |
| 7 | **covers** | roofs (lifted or not); at the map zoom the whole building is its cover | the foot's y |
| 8 | **signals** | ❓, `!`, ⏳, 🔥 on covers and orks, the spotlight's rope and dimming | — |
| 9 | **chips** | words and counts on the map | — |
| 10 | **UI** | the HUD, the 🥩 list, the console, sheets, menus, toasts | — |

Layers 4–7 share one depth sort inside a building's box: the front wall is drawn after what stands inside it. Layers
8–10 never sort with the art: a signal is never hidden behind a roof.

**Shadows are the product's, not the art's:** one soft ellipse under every ork, cart and building foot, in
`art-shadow` at the layer below the sprite.

## 4. The kits as components

Every kit is a set of pieces with **slots**: places the product fills (a facade, a crest, a load, a flag, a role, a
state). The names below are the components' names in `components.md`; their CSS classes come with C3–C5.

### 4a. Cover (the building) — three kinds, one behaviour

| kind | the cover at far zoom | the frame close up | crest slot | for (core first) |
|---|---|---|---|---|
| **hall** | a roof (canvas, thatch, hide), nine-slice | the walls kit, nine-slice | on the ridge | **Agent pool**, Research, most buildings |
| **open ground** | the scene itself (the fire ring with orks round it; the pond's surface) | a ring of stones and logs; the shore | the centrepiece (the fire; the lens on its stand) | **Inspector** (the lake), Review board (the fire) |
| **tower or gate** | the structure seen from the front | its yard walls (the walls kit) | the top (the horn on its stand; the gatehouse's banner) | **External listeners**, **Review gate** |

**Slots of every Cover:** `footprint` (XS–L, §2.4) · `material` (the roof or wall kit) · `facade` (below, at the
door) · `crest` (above) · `signal` (over the cover) · `count` (a chip at the door) · `state`.

**States:** `covered` (map and overview) · `peek` (hover or select at any zoom: the cover at 50 % opacity, the inside
seen) · `lifted` (close zoom: the cover gone, the walls stay as the card's frame, **the crest moves into the card's
header** as its mark) · `burning` (🔥: a hall's roof smoulders, an open ground's fire flares red with dark smoke, a
tower's top carries the flame) · `asking` (❓ over the cover) · `idle` (no motion; never dimmed below 92 %).

**The Task board** is a hall whose facade is the board on its posts; the Publisher is a **machine on open ground**
(the catapult at the track's end, §4e).

### 4b. The nine-slice rules (roofs and walls)

1. **Nine pieces:** four corners, four edges, a centre. **A corner has a border on its two outer sides only, an edge
   on its one outer side only, the centre none.** No piece carries a frame of its own on an inner side (the 0.3 roofs
   do; they would show seams).
2. **Sizes:** corners **24 × 24**, the back corners **24 × 32** (the back wall's front face shows); edges **24 deep**
   (the back edge 32), repeating every **8 px** along their length (so any footprint of §2.4 tiles without a cut
   piece); the centre a 32 × 32 tile (the earth floor; the roof's field).
3. **Repeat, never stretch:** an edge piece is drawn as a 24 × 8 (or 8 × 24) repeat unit with up to three variants the
   pipeline shuffles by a seed, so a long wall is not a pattern.
4. **The walls stand outside the footprint:** the inside is exactly the card; the outer box is
   footprint + 24 left, right and front, + 32 at the back.
5. **The roof covers the outer box;** its front edge overhangs the front wall by 8 px (three-quarter).
6. **Materials:** roofs **canvas** (maroon cloth on poles), **thatch**, **hide**; walls **stone and log** (the 0.3
   walls kit), **palisade logs** (the tower's and the gate's yards).

### 4c. Facade and crest

- **Facade:** each core building's own front, at the door, standing on the front wall's centre. Slot **96 × 48**
  (XS: 64 × 48), the bottom cut straight on the wall's foot, **no ground under it**. The five: the Task board's posts
  and pinned scrolls with a skull; the Agent pool's weapon rack and dummy; the Review gate's arch, tusks and
  portcullis (the gatehouse is its whole front); the Inspector's reed shore and jetty to the water; External
  listeners' ladder and a bone horn on a stand. The facade carries the **door**: where orks go in, and where the
  building's track spur meets it.
- **Crest:** one object over the cover, **32 × 48**, anchored bottom-centre on the ridge. One per building, never
  repeated in a camp (the skull is the Task board's alone). The ten of the 0.3 sheet are the starting set: horn,
  banner, totem, lens, chimney with smoke, skull on a pole, lantern, crossed axes, scrolls on a spike, raven.
  **At close zoom it becomes the card's header mark**, drawn at 1× in the card's title bar, so the building is known
  from inside.

### 4d. The track autotile set (roads drawn as rails)

- **Tile 32 × 32;** the gauge (outer rail to outer rail) **20 px**, centred; ties every **8 px**, low contrast
  (`art-wood-dark` on `art-earth`, one in four a bone tie); a 2 px earth bed under the ties, no grass edge baked in.
- **The set (16 tiles):** straight (H, V); corners (4); T-junctions (4: a spur from above, below, left, right); a
  crossing; a switch (one in, two out) and a merge (two in, one out) for each direction the line runs (the 0.3 sheet
  has them for left-to-right); buffer stops (4, logs); the way in and the way out through the palisade (a gap in the
  logs with the track passing, §6).
- **Autotiling:** a 4-bit mask of the cell's neighbours (N E S W) picks the tile; a switch or a merge is chosen where a
  road leaves or joins another (`roads.js` already knows which). Tiles never rotate (light comes from the top left);
  each direction is its own tile.
- **At the map zoom** the track is a 4 px line in `art-wood-dark`, not tiles.
- **Office:** the same paths as today's 2 px lines (components.md Road).

### 4e. The mine cart

- **Body 48 × 32 (side view, rolling left or right) and 32 × 40 (front view, rolling up or down)**, iron-banded wood,
  anchored at the wheels' bottom centre on the gauge.
- **Load slot:** a 32 × 24 box over the bin, the load's foot hidden by the bin's front rim. Loads: `code` (a scroll
  with a large `</>`), `asset` (a crate), `message` (a sealed letter), `doc` (a book), `bundle` (three sacks); a
  number chip `×3` beside it for several items (a chip, §5).
- **Flag slot:** a pole at the bin's back left, the flag 16 × 12: none (moving), **yellow** (waits for the person),
  **⏳** hung on the pole (held for a limit's reset), **red, flickering** (stuck). The gate's own colour at the Review
  gate.
- **Rolling:** 4 frames of the wheels turning. A queue is a **pile** (carts lined up at a buffer stop) and a `×4`
  chip, never a line of moving sprites.
- **Orks never move or ride carts;** the town routes them.
- **The catapult** (the Publisher) is the line's last piece: 160 × 160, the track coming in straight from the left
  into its own buffer stop; 4 frames of the launch (resting, drawn back with the load in the bucket, mid-throw, the
  load flying over the palisade). The design to keep: the skull on the front, tusks, its buffer stop.

### 4f. The ork

- **One body, frame 32 × 48,** anchored at the feet's bottom centre; the body about 28 × 44 inside it, a big head on a
  short body, olive skin, cap, apron, tool belt, small tusks; a friendly resting face, the frown kept for a stuck ork.
- **Directions:** down (toward the viewer), up, side (mirrored for the other side).
- **Animations** (frames): idle 4 · walk 6 per direction · work 6 (the tool's swing) · sit 2 · and the state poses
  below. 8 fps.
- **Role slot** (headgear and held tool on the same body, `orc.<type>` in `TERMS` says the name): Warchief (horned
  helmet, a loosened tie), Grunt (bone-white hard hat, a muted brown work vest), Taskmaster, Lookout (a headset over
  the cap), Seer (hood and staff), Quartermaster (helmet, shield, a brass key), Loader, Mechanic (welder's cap,
  wrench), Alchemist (pointed cloth hat, a muted green flask), Treasurer (clipboard, coin pouch), Pathfinder (fur hat,
  map, lantern). One modern joke per role at most; none in buildings or signals.
- **State slot** (the ork's pose; the badge is UI, §5):

  | state | pose | badge |
  |---|---|---|
  | working | the tool swings | none |
  | asks | one hand raised, a curious face | ❓ (yellow), the loudest thing in the camp |
  | stuck or error | slumped, a frown, a grey puff | `!` (red, flickering) |
  | held for a limit | sitting, arms crossed | ⏳ |
  | idle | sitting by its building, dozing | none (the pose says it) |

## 5. Signals and chips

1. **Yellow and red are reserved.** `signal-ask` (yellow) is a question and nothing else; `signal-fire` (red) is an
   error or 🔥 and nothing else. **Neither appears in the ground, the buildings, the props, the orks' clothes or the
   chrome.** Banners are maroon (`art-cloth`), flasks and keys brass or muted green. ⏳ is `signal-held` (a cool
   blue-grey), so it never reads as a question.
2. **Badges only for exceptions.** Normal work is motion: a swinging tool, a rolling cart, a turning wheel. A badge
   appears only for what needs the person (❓) or explains a stop (`!`, ⏳).
3. **Words live on chips, in the UI font,** never as pixel text on the ground and never inside the art: a dark chip
   (`chip`), its text `chip-ink` in the `chip` type style (the look's UI face), a 1 px `art-outline` border. The same
   chip in Camp and Office (Office's chip drawn over Camp, [town-readability.md](town-readability.md) §2).
   - a cart's chip: `#42 · Login form` (the short ref and the title cut at about 20 characters); **always shown for a
     cart that waits for the person;** otherwise on hover, select or the close zoom;
   - a building's count chip at its door: `🥩 2 · ❓ 1`;
   - a building's name chip under its door at the overview zoom; at the close zoom the name is in the card's title.
4. **Sizes (CSS px, at every zoom):**

   | | desktop | phone |
   |---|---|---|
   | chip height | 20 (text 12/16) | 24 (text 13/16, never under 11) |
   | badge (❓ `!` ⏳) | 20 × 20 on its dark plate | 24 × 24, a 44 × 44 tap area |
   | gap badge → the head or roof it marks | 2 | 4 |
   | chip's horizontal padding | 6 | 8 |

5. **Order of loudness** (each step reads before the next in grey and squinted): ❓ → `!` and 🔥 → a waiting cart's
   chip → the track → buildings → orks and carts at work → the ground.

## 6. The camp's edge and the story

The palisade is **only the camp's outer edge** (never round a card), half the height the 0.3 frame drew it: pieces
32 × 48 (straight, corners, the gate) along the back edge, lower posts on the sides. **The ways in** (External
listeners, the Task board, the clock) are gaps where the track enters from outside the wall; **the way out** is the
catapult at the palisade, the track's end ([camp-story.md](camp-story.md)). The work runs **left to right** in the
layout's order: External listeners → Task board → Agent pool → Review gate → Publisher; the Inspector and Research on
spurs below the line.

## 7. Colour roles for the new palette (tokens)

Three families, never mixed:

- **world** (`world-*`, `art-*`): the Camp map's art. **No text is ever drawn on them** (they fail text contrast by
  design); they are for the sprites' palette, the ground layer and the product's own shadows and outlines.
- **signals** (`signal-*`): the reserved colours of §5.
- **chips** (`chip`, `chip-ink`): words on the map.

| token | Camp | what for |
|---|---|---|
| `world-grass` | `#5e8a4c` | the grass, the middle tone (most of the ground) |
| `world-grass-light` | `#6f9a56` | tufts and the light tone |
| `world-grass-dark` | `#4e7840` | the dark tone, small patches |
| `world-earth` | `#8f7250` | trodden earth round the walls, the track's bed, a hall's floor |
| `world-earth-dark` | `#735b4c` | the earth's shade |
| `world-water` | `#2f5a55` | the Inspector's pond |
| `art-wood` | `#7c5f48` | logs, planks, posts, the carts' bins |
| `art-wood-light` | `#ba9468` | lit wood, thatch's light |
| `art-wood-dark` | `#4f3935` | wood's shade, the track's ties and the map's track line |
| `art-stone` | `#7d7a74` | stone walls, the gatehouse |
| `art-stone-dark` | `#4d4848` | stone's shade |
| `art-iron` | `#4a4b52` | cart bands, the portcullis |
| `art-bone` | `#dccaa0` | tusks, skulls, bone ties, scrolls |
| `art-cloth` | `#6b2a2c` | banners, the canvas roof (maroon) |
| `art-skin` | `#769544` | the ork's olive skin |
| `art-outline` | `#1c1410` | every sprite's 1 px outline, the chips' border |
| `art-shadow` | `#1c1410` at 35 % | the product's shadows under feet and walls (the alpha is the renderer's) |
| `signal-ask` | `#facc15` | ❓, a cart's yellow flag: a question for the person |
| `signal-fire` | `#e8411c` | 🔥, `!`, a red flag: an error or a stop |
| `signal-held` | `#8fa3b8` | ⏳: held for a limit's reset |
| `chip` | `#1c1712` | the chips' and badges' plate |
| `chip-ink` | `#e8e0c8` | words on a chip |

**Rules the tests hold** (`tests/test_design.py`):

- **the ground tones** (`world-grass`, `-light`, `-dark`, `world-earth`: what a sprite stands on) stay in a **middle
  value band** (relative luminance 0.12–0.30) and **at least 3:1** from `art-outline` and from `chip`, so an
  outline and a chip are always seen against the ground (the grey test); the shade tones (`*-dark`, `art-iron`,
  `art-cloth`) are inside sprites, never under them;
- `chip-ink` on `chip` **at least 7:1**; `signal-ask` and `signal-fire` on `chip` **at least 3:1**;
- the world tokens hold no saturated yellow or red (yellow and red are only `signal-*`).

**The UI chrome's names say what they are now** (the old names stay as aliases, with the same values in every theme,
so nothing in the GUI changes): `wood` (was `frame`, `hut-frame`), `bone` (was `frame-focus`), `cloth` (was
`banner`), `ink-wood` (was `ink-gold`; the gold left with the colour pass). `road-*` keep their names: a road is a
road, whatever Camp draws it as.

**Office** has no world: its `world-*` and `art-*` values are its own `canvas`, `panel` and frame greys, so a
component drawn in Office with Camp's tokens falls back to plain shapes. Its `signal-*` are its own signal colours;
`chip` and `chip-ink` are its `panel-raised` and `ink`.

**The biomes** (forest only now): a biome is a swap of the `world-*` and `art-*` values, never of shapes; each is held
to the same rules. P1, with [color-pass.md](color-pass.md) §5.

## 8. Zoom levels, hover and select

| | map (½) | overview (1) | close (2) |
|---|---|---|---|
| ground | flat `world-grass`, no tufts | the tiles | the tiles |
| track | a 4 px line | the autotiles | the autotiles |
| buildings | the covers only | covers, facades, crests | walls, facades; the cover lifted; the card inside; the crest in its header |
| carts | a 6 px dot in its state's colour (`signal-*` or `art-wood`) | the sprite, its load, its flag | the same; inside a hall, at its ork's place |
| orks | none | walking and working; inside a hall only on `peek` | at their places inside the card |
| signals | ❓ and 🔥 over the cover | ❓ `!` ⏳ over orks and covers | the same, and inside the card |
| chips | none, except a cart that waits | a building's name and its count chip; a waiting cart's chip | every cart's chip |

**Hover and select: the spotlight** ([town-readability.md](town-readability.md) §5). Pointing at an ork, a cart or a
🥩 row: the two (the ork and its cart) are lifted (drawn at full saturation, a 1 px `chip-ink` keyline), a short
dashed rope in `chip-ink` joins them, and everything else is dimmed to 70 % saturation and 85 % lightness. A building
on hover turns to `peek` (§4a). Select keeps the spotlight until Esc or a click on the ground. On the phone a tap
does what a hover does; a second tap opens.

## 9. Camp and Office: two drawings of the same components

Same component, same place, same word; only the drawing changes ([work-and-play.md](work-and-play.md) §2).

| component | Camp | Office |
|---|---|---|
| ground | grass tiles, tufts | `canvas`, flat |
| the camp's edge | palisade along the back | none |
| road | the track autotiles; switches, merges, buffer stops | 2 px lines (dashed plain, solid with a handler), arrowheads |
| a building, far | its Cover (roof, scene, tower or gate) with facade and crest | a box with the name, its frame `hut-frame` |
| a building, close | the cover lifted, walls as the card's frame, the crest in the header | the card, 1 px frame, `radius-md` |
| `peek` | the cover at 50 % | the card's frame turns `frame-focus` |
| a cart | a mine cart with its load and flag | a 10 px square in its state's colour, its load as a word (`code`, `doc`) |
| a queue | a pile at a buffer stop, `×4` chip | `×4` chip |
| an ork at work | the tool swinging | a word: Running pytest |
| an ork that asks | the raised hand and ❓ | ❓ and the word Asks |
| stuck | slumped, `!` | `!` and the reason |
| held | sitting, arms crossed, ⏳ | ⏳ and until when |
| 🔥 | the roof smoulders, the fire flares | the card's frame `alert-hot`, 🔥 |
| a chip | dark plate, UI font | the same chip |
| the launch | the catapult swings, the load flies over the wall, a line | a row: "PR #42 opened" |
| the spotlight | lift, rope, dim | the row and its cart highlighted, the rest at 40 % |

## 10. Type and motion

**Type roles** (the families are in `design-system/tokens.json`):

| role | face | where |
|---|---|---|
| wordmark | Almendra SC | the product's name only |
| display | Pixelify Sans | titles in Camp, the War Map (decided in color-pass §5; applying it is Q3) |
| UI | Titillium Web (Camp), the system face (Office) | everything else, **the chips included** |
| mono | JetBrains Mono | code, diffs, paths, terminals |

The new type style `camp-chip` / `office-chip` (12/16, 600) is the chips' face. No pixel text in the art.

**Motion** (values for C2–C5; tokens when the generator learns a motion group, §12 Q6):

| motion | how |
|---|---|
| **work as motion** | sprite frames at 8 fps (ork, cart wheels, the catapult); a building at work shows its motion (smoke, a turning part), idle shows none |
| **the cover lifting** | 250 ms ease-out opacity to 0 as the zoom crosses into close; the walls and crest never fade; `peek` 150 ms to 50 % |
| **zoom** | eases 200 ms between ladder steps and rests only on a step |
| **a cart on the track** | 48 px a second at overview, stepped to whole art pixels; it waits at a switch, never overtakes |
| **the launch** | the catapult's 4 frames over 600 ms, the load's arc 800 ms over the wall, one chip line ("PR #42 opened") for 3 s; no sound, no confetti; never during quiet hours |
| **❓ appearing** | a 2-frame bob, then still; `!` flickers at 2 Hz; 🔥 flickers with `fire-glow` / `fire-ember` |
| **reduced motion and hidden windows** | under `prefers-reduced-motion` the frames stop on their first, the cover lift is instant, the launch is the line only; every animation pauses while the window is hidden ([work-and-play.md](work-and-play.md) §4a) |
| **the phone** | at most 12 fps, stopped when the page is hidden |

## 11. The sprite pipeline

**Folders** (`design-system/sprites/camp/`, beside today's, so nothing in the GUI moves until C3–C6):

```
camp/
  manifest.json              every sprite: file, size, anchor, frames, fps, slots, licence, author
  ground/   grass-0..2.png  grass-tuft-0..2.png  earth-0..1.png  earth-edge-<n|ne|e|…>.png
  track/    straight-h.png straight-v.png corner-ne.png … t-n.png … cross.png
            switch-e.png merge-e.png … stop-e.png … way-in.png way-out.png
  edge/     palisade-h.png palisade-corner-nw.png … palisade-gate.png
  covers/   hall/roof-canvas/<piece>.png  hall/roof-thatch/…  hall/roof-hide/…  hall/walls-stone/…
            open/fire-<calm|warm|alarm>.png  open/pond.png
            tower/lookout.png  gate/gatehouse.png
  facades/  fields.png barracks.png loot_vault.png lake.png watchtower.png
  crests/   horn.png banner.png totem.png lens.png chimney.png skull.png lantern.png axes.png scrolls.png raven.png
  carts/    side.png front.png rolling-side.png (4 frames)  loads/<code|asset|message|doc|bundle>.png
            flags/<ask|held|fire>.png
  orks/     body/<idle|walk-down|walk-up|walk-side|work|sit|ask|stuck|held|doze>.png
            roles/<role>.png  (headgear and tool, drawn over the body's frames)
  props/    table.png bench.png anvil.png desk.png crates.png barrel.png
  machines/ catapult.png (4 frames)
  map/      the half-size copies the pipeline writes for the map zoom
```

- **Names:** lowercase, words joined by `-`; a building's piece named by its **type id** (`fields`, `barracks`,
  `loot_vault`, `lake`, `watchtower`, `catapult`: code names stay, CLAUDE.md); nine-slice pieces `nw n ne w c e sw s
  se` (edges with a variant suffix `n-1`, `n-2`); directions `n e s w`.
- **Animations** are horizontal strips, frames of equal size left to right; the frame count and fps are in the
  manifest, never guessed from the width.
- **`@2x` files are not made:** the art is drawn at 1× and the renderer scales by whole numbers. The map's half-size
  copies are the one derived set.
- **Anchors:** standing things at their feet's bottom centre; tiles and nine-slice pieces at the top left; a crest at
  its bottom centre.

**How a sheet becomes sprites** (`tools/camp_sheet.py`, its sheets listed in `tools/camp_sheets.json`; the 0.3 sheets
are cut into `camp/` as **placeholders**, `camp/README.md` says which and where they fall short):

1. **Key** the background: flat `#FF00FF` within a tolerance, and the purple fringe a blended shadow left (red and
   blue both well above green) as background too. A sheet drawn to the brief has neither (no shadows, a clean key).
2. **Find each sprite** as a connected shape on the keyed mask (small gaps closed, so a ring of stones is one piece).
3. **Snap to its own grid:** read the sheet's pixel size (about 6 screen px for the 0.3 sheets), then take each cell's
   median colour, so the sprite is a true pixel grid again; a cell less than half covered is transparent.
4. **Trim** to the opaque box, then **pad** to the slot's size (a multiple of 8) at its anchor.
5. **The border of tiles:** a tile drawn with a dark border (the 0.3 ground and track tiles) is **cut inside its
   border** (the border's width taken off every side) before the snap, then checked to tile: its left column against
   its right, its top row against its bottom.
6. **Snap the colours to the palette:** each pixel to the nearest `art-*` / `world-*` tone or a tone the manifest lists
   for the sprite; the outline to `art-outline`.
7. **Write** the PNG (8-bit with alpha, no smoothing, metadata stripped) and its manifest row; write the map copy.
8. **Check:** no pixel of `signal-ask` or `signal-fire` hue outside the signal sprites; nine-slice pieces join (the
   tool renders a 3 × 3 and a 5 × 4 of each kit); every size a multiple of 8.

**Reference sheets** (generated) are kept as references, not in what ships (§12, Q1).

**What the commissioned artist delivers:** [artist-brief.md](artist-brief.md): the PNGs in this layout at 1×, each
sheet also as its source file (Aseprite or the artist's own layered file), the palette as a `.gpl` / `.hex`, and the
manifest's rows (sizes, anchors, frames); under CC-BY 4.0.

## 12. Open questions for the owner

1. **The reference sheets in the wheel.** `pyproject.toml` ships `design/system/**/*`, so `design-system/sprites/
   orkcraft 0.3/` (≈ 22 MB of generated JPEGs) is in every install, against color-pass §10. *Proposed:* move them to
   `docs/design/img/references/0.3/` (the docs do not ship) and update the paths in asset-prompts.md. Not moved here:
   it is your upload and other sessions name the path.
2. **The question's colour in today's Camp.** Today a waiting question is `alert` orange and a held cart is `warning`
   yellow; v2 says yellow = a question, red = an error or 🔥, ⏳ = held. *Proposed:* the new components use `signal-*`
   from the start; today's cards keep `alert` until C3 replaces them, so the town does not wear two meanings at once
   during the move. Or: re-point `alert` to yellow now (today's Camp changes at once).
3. **Pixelify Sans for Camp's titles.** Decided in color-pass §5, not applied: `camp-title` and `camp-heading` are
   still Almendra SC. Apply now (today's windows change) or with C3?
4. **The ork's size.** v2 takes the art's own 32 × 48 (one frame); the prompts asked 32 × 32 and the old slot is
   24 × 16. 32 × 48 is what the sheets draw well and what the five-second test was passed with; it makes the ork a
   third of an M building's height at the overview zoom. A smaller ork (16 × 24) was tried and loses the face.
5. **The map zoom from half-size copies.** The one step off whole numbers. The alternative is the artist drawing a
   small cover per core building for the map (five more pieces, ≈ $50–150).
6. **Motion tokens.** `orkcraft/design/tokens.py` writes only the colour, shadow, space, radius, border and size groups;
   a `motion` group means a small change there (C2), not done here.
7. **Biomes.** v2 sets forest's world palette only; ice, dust, void, lava and meadow follow as palette swaps (P1).
   Keep all six, or fewer for the launch?
8. **Footprints by size.** The core five are proposed L (Agent pool), M (Task board, Inspector, External listeners)
   and S (Review gate, Publisher); round 2 of the frame asked the core buildings to be closer in size. Same, or all M?

### Answers (the owner, 2026-10-14)

1. **Yes:** the 0.3 reference sheets move to `docs/design/img/references/0.3/` (not shipped); paths updated.
2. **Re-point now:** a question is yellow everywhere at once (`alert` re-pointed to the question's yellow; red only
   for an error or 🔥; ⏳ for held). One meaning of the main signal, even during the move.
3. **Pixelify Sans for Camp's titles with C3,** so the look changes once.
4. **The ork 32 × 48.**
5. **Half-size copies for the map zoom for now;** the artist's small covers only if the five-second test asks.
6. **Motion tokens in C2.**
7. **Forest only for the launch;** the other five biomes stay in the code, not offered (P1).
8. **Agent pool L; Task board, Review gate, Inspector, External listeners M; Publisher S.**
