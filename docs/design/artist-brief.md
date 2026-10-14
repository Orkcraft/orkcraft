# Orkline — the brief for the pixel artist

Status: 2026-10-14, made from the design system v2 ([design-system-v2.md](design-system-v2.md)). It goes with the
first letter ([color-pass.md](color-pass.md) §10a–10b): the licence comes first, then the style. The reference
sheets (`docs/design/img/references/0.3/`) and the concept frame
([img/orkline-camp-concept-v2.png](img/orkline-camp-concept-v2.png)) are generated images: **references for the
silhouettes, the palette and the layout, never to be traced or shipped.** Everything here is to be drawn by hand.

## 1. What Orkline is, in two lines

A desktop control room for AI coding agents. In its game look, **Camp**, your project is an ork camp: work comes in at
the gaps in the palisade, rolls along a rail line in mine carts, is refined by small working orks in the buildings,
passes a gate, and is catapulted over the wall as a finished pull request. Cosy, a little funny, and a factory at a
glance.

## 2. Licence (first)

- **CC-BY 4.0** (or CC0) for everything delivered, credited to you in the README, the landing page and `NOTICE`
  ("hand-made pixel art by …"). The repository is public, the art ships in every install, and other people will make
  buildings that must match the kit.
- You keep the right to show the work in your portfolio and to sell it elsewhere (CC-BY allows that); the price
  reflects that the art is open (color-pass §10b).

## 3. The style in one paragraph

A cosy camp of **small round working orks** (a big head on a short body, olive skin, cloth cap, leather apron, tool
belt, small tusks, a friendly resting face), **warm wood, grey stone, bone tusks and skulls, dark maroon cloth**, lush
but calm grass; **crisp hard pixels, no anti-aliasing, no gradients, no dithering noise**; **a 1 px dark outline** on
everything that stands; **three-quarter top-down** (walls show their top and their front face; never isometric, no
45° edges); light from the top left. **Our ork is our own:** not the big bulky muscled green warrior of a well-known
strategy game, no gold-on-blue.

## 4. Rules for every file

1. **Drawn at 1×, at the final size.** One art pixel is one pixel of the file. No detail finer than the size holds.
2. **Every size is a multiple of 8.**
3. **No shadows** (the product draws them), **no text** in any sprite, **no ground** under standing things.
4. **Transparent PNG**, 8-bit with alpha; plus the source file (Aseprite or your own layered format).
5. **Yellow and red are reserved** for the signal sprites (§6.5). Nowhere else: no gold keys, no red flasks, no
   fire as decoration, no bright orange. Banners are maroon; brass and muted green are fine.
6. **The palette:** the tones below are the starting point; you may refine them and add ramps, and you deliver the
   final palette (`.gpl` or `.hex`, ≤ 48 colours for the whole set).

   | role | start | | role | start |
   |---|---|---|---|---|
   | grass (3 tones) | `#4e7840` `#5e8a4c` `#6f9a56` | | stone (2) | `#7d7a74` `#4d4848` |
   | trodden earth (2) | `#8f7250` `#735b4c` | | iron | `#4a4b52` |
   | wood (3) | `#ba9468` `#7c5f48` `#4f3935` | | bone | `#dccaa0` |
   | water | `#2f5a55` | | maroon cloth | `#6b2a2c` |
   | ork skin | `#769544` | | outline | `#1c1410` |
   | signal: a question | `#facc15` | | signal: an error | `#e8411c` |

   The grass and the earth stay in a middle value: a dark outline and a dark label must read on them in greyscale.
7. **Animations** as horizontal strips of equal frames, 8 fps unless said.
8. **Names and folders** as in [design-system-v2.md](design-system-v2.md) §11 (we can rename on delivery if easier).

## 5. Grid and sizes

The ground and track tile is **32 × 32**; the camp lays out on a 16 px cell. The product shows the art at 1×
(overview) and 2× (close), and a half-size copy at the farthest zoom: **a sprite must read at 1×** and stay pleasant
at 2×. Size checks: an ork is 32 × 48; a mine cart 48 × 32; a medium building 192 × 152 with its walls.

## 6. The kits

### 6.1 Ground, track, the camp's edge

| piece | size | count |
|---|---|---|
| grass, seamless, three tones; tufts and a few small flowers as variants | 32 × 32 | 6–8 |
| trodden earth, seamless, two tones; grass-to-earth edges and corners | 32 × 32 | ≈ 14 |
| **track autotiles:** two wooden rails on log ties, a 20 px gauge centred, **few, low-contrast ties** (one in four a bone tie), a thin earth bed: straight H, straight V, 4 corners, 4 T-junctions, a crossing, a switch and a merge for each of 4 directions, 4 buffer stops of logs | 32 × 32 | 19 |
| palisade of sharpened logs with tusks, **low** (a back edge, not a fortress): straight, corners, posts for the sides | 32 × 48 | 6 |
| the ways in and out: a gap in the palisade with the track passing through | 32 × 48 | 2 |

### 6.2 Building covers (three kits)

**Hall** — a roof over a ring of walls; stretches to four sizes by **nine-slice**:

- **walls kit** (stone footing, log walls, an earth floor), seen from above with their top and front face;
- **three roofs:** maroon canvas on poles with rope ties; thatch; stitched hides;
- nine pieces each: corners **24 × 24** (back corners **24 × 32**), edges **24 deep** (the back 32) as **8 px
  repeat units with 2–3 variants**, a **32 × 32** centre. **A corner has its border on its two outer sides only, an
  edge on its one outer side, the centre none** (the 0.3 roofs fail this: every piece has its own frame);
- they must tile to these insides: 96 × 64, 120 × 80, 144 × 96, 168 × 112 (walls outside).

**Open ground** — the scene is the building:

- the **Inspector's pond** with a reed shore and a round glass lens on a wooden stand, about 192 × 120;
- the **Review board's fire ring** (stones, tusks, logs to sit on), about 192 × 120, in three states: unlit, a calm
  warm fire, **the alarm** (flaring red, dark smoke: the only fire in the camp that may be red, as a signal, 4 frames).

**Tower or gate:**

- **External listeners:** a wooden lookout tower with a **bone horn on a stand** (no metal megaphone), 64 × 128,
  **three-quarter, not isometric**, over its yard (the walls kit in palisade logs);
- **Review gate:** a stone gatehouse with tusks, a portcullis, a skull and a maroon banner, about 168 × 120.

**The Publisher's catapult** (the line's end, at the palisade): about 160 × 160, three-quarter, the track coming in
straight from the left into its own buffer stop; a skull on its front, tusks on the base; **4 frames** of the launch
(resting, drawn back with the load in the bucket, mid-throw, the load flying over the wall).

### 6.3 Facades and crests (each building's two marks)

- **Five facades**, 96 × 48 (the door included), the bottom cut straight, **no ground under them**: Task board (posts,
  pinned scrolls, a skull), Agent pool (weapon rack, a training dummy, a log door), Review gate (the arch, tusks, the
  portcullis), Inspector (a reed shore and a jetty to the water), External listeners (a ladder and the bone horn).
- **Ten crests**, 32 × 48 each, one object to stand on a roof's ridge: a curved horn, a maroon banner with a tusk
  mark, a carved totem, a round glass lens, a chimney (with a 4-frame grey smoke), a skull on a pole, a lantern,
  crossed axes, scrolls on a spike, a raven on a perch. Each must read at 1× and at 16 px tall (it also sits in a
  card's title bar).

### 6.4 Inside a hall

Furniture seen from three-quarter top-down, 32–64 wide: a rough table with scrolls, a workbench with tools, a table
with a small anvil, a desk with an open book and a candle (the flame small and warm, not red), a crate stack, a
barrel, a bench. 6–8 pieces.

### 6.5 Mine carts, loads, flags

- **The cart:** wooden, iron-banded; **side view 48 × 32** and **front view 32 × 40**; **rolling, 4 frames** of the
  wheels for each view.
- **Five loads**, each 32 × 24, sitting in the bin: a scroll with a large clear `</>` (code), a crate (an asset), a
  sealed letter (a message), a thick book (a doc), three sacks (a bundle).
- **Three flags**, 16 × 12 on a pole: **yellow** (`#facc15`, waits for a person), **an hourglass** hung on the pole
  (held), **red** (`#e8411c`, stuck; 2 frames for a flicker).
- **A pile:** four carts close together at a buffer stop.

### 6.6 The ork (one body, roles as headgear and tools)

**The body, 32 × 48 a frame**, the feet at the bottom centre, the same character in every frame:

| animation | frames | directions |
|---|---|---|
| idle (breathing) | 4 | down |
| walk | 6 | down, up, side (we mirror the side) |
| work (a tool's swing and hit; one hand, one tool) | 6 | down |
| sit on a log | 2 | down |
| **asks** (one hand raised, a curious face) | 2 | down |
| **stuck** (slumped, a frown, a small grey puff) | 2 | down |
| **held** (sitting, arms crossed) | 2 | down |
| **doze** (sitting, eyes shut) | 2 | down |

**Eleven roles** as headgear and a held tool drawn over the body's frames (a layer per role), each told apart by its
silhouette at 1×; one modern joke per role at most, never in buildings or signals:

| role | headgear and tool |
|---|---|
| Warchief | horned helmet, **a loosened necktie** over the leather vest, a small banner on the back |
| Grunt | a bone-white hard hat, a muted brown work vest, an axe |
| Taskmaster | a cap with a pencil behind the ear, a scroll |
| Lookout | a cap with **a simple headset**, a spyglass |
| Seer | a hood, a staff with an eye charm (muted, not glowing yellow) |
| Quartermaster | a helmet, a round shield, a **brass** key |
| Loader | leather gloves, a coil of rope |
| Mechanic | a welder's cap, a wrench, a gear on the belt |
| Alchemist | a pointed cloth hat, a **muted green** flask (no goggles: those are the Mechanic's) |
| Treasurer | a wooden clipboard, a coin pouch, a small abacus |
| Pathfinder | a fur hat, a rolled map, a lantern |

## 7. What we judge on delivery

1. **Greyscale:** every ork and cart stands off the grass; the yellow and red signals are the brightest things.
2. **Five seconds** at 1× on a laptop: "which ork waits for you, which cart is stuck, which building is which?"
3. **The kits join:** each nine-slice renders at the four sizes and as 3 × 3 and 5 × 4 with no seam.
4. **One projection** across all sheets; sizes on the 8 px grid; no shadows, no text.

## 8. Stages and what comes first

| stage | pieces | for |
|---|---|---|
| **1. The launch's minimum** | the ork body (idle, walk, work, asks) and the Grunt; the cart (side, rolling) with the `</>` load and the yellow flag; the track set; grass; the walls kit and one roof; the five facades and five crests; the gatehouse; the catapult | the demo GIF, the README, the landing page |
| 2. The camp complete | the other roles and poses, loads and flags, the other roofs, the pond and the fire ring, the tower, the palisade and its gaps, the furniture, the remaining crests | the product at launch |
| 3. Later | biome palettes (ice, dust, lava, void, meadow) as palette swaps of the same files | P1 |

We send sketches back within two days of each delivery; the devlog may show your progress, credited.
