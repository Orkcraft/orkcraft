# Design — a colour pass: keep the style, make what matters stand out

Status: proposal 2026-10-12, the owner's question ("is it too pale? brighter colours? is it all one style?"); nothing
changed. Priority **P0 for the token pass** (§3, the demo GIF is judged on it), **No** for redrawing the sprites' shapes (a new
palette is §8).
Builds on [gui-design-system.md](gui-design-system.md), `design-system/tokens.json`, [sprites.md](sprites.md),
[portrait.md](portrait.md) (the looks). Looked at: `docs/img/town.png` (2026-10-11) and the buildings' `header@2x.png`
side by side.

## 1. What is seen

**The sprites are one style, and a good one.** Two inks and an accent: moss greens for the body, bone and cream for
horns, scrolls and paper, a little gold for fire and light. The silhouettes differ well (the horned hall, the forge's
chimney, the drum, the scroll heap, the tower, the board, the gate, the mill). Nothing to redraw.

**Why it reads pale** is not the palette but three things together:

1. **Figure and ground are the same colour.** Green buildings stand on a green ground (`canvas` `#172a0a` in Camp ·
   forest). With little contrast between them, the eye has nothing to catch.
2. **Idle buildings are dimmed on purpose:** `brightness(.78) saturate(.8)` on every hut not busy, alerting or selected
   (`layout.css`, `.gui-hut__roof`). In a calm town, which is most of the time and the whole of today's screenshot,
   everything is dimmed at once.
3. **The warm accent does two jobs.** Gold is the forge's fire, the drum's sun, the HUD's sun and also "look here"
   (Answers, a yellow dot, the error badge's orange is near it). A signal that shares its colour with decoration does
   not stand out.

**Where the style is not one:**

- **Four type families:** Almendra SC (a gothic display: the wordmark, "Town Hall"), Pixelify Sans (the War Map), Titillium
  Web (the text), JetBrains Mono (code). Two display faces for one role.
- **The War Map's rows** in purple, blue and green bars: colours from nowhere else in the palette.
- **The roads**, "the point" of the README, are thin grey dashes, the faintest thing on the screen.
- Some sprite edges look soft rather than crisp at 2×: to check at 1× (a generator's resample left in).

## 2. The rule

> **A strategy game's rule: a quiet ground, clear units, loud signals.** The ground stays dark and calm; buildings
> stand off it; the warmest, brightest colours are kept for what needs the person (🔥, ❓, an error) and nothing else.

Brighter everywhere is not the answer: it would make the signals of [ork-console.md](ork-console.md) §5 harder to see,
not easier.

## 3. The pass (tokens and CSS only, P0)

1. **Ground away from the buildings' hue:** Camp · forest's `canvas` and `terrain` toward a dark neutral earth (brown or
   grey), so the green buildings stand off it. Ice and void are checked the same way.
2. **Idle dimming softened:** from `.78 / .8` to about `.92 / .95`, so a calm town is calm but not faded; busy and
   selected stay bright.
3. **Warm colours for signals only:** 🔥 and errors a clear red-orange, ❓ a clear yellow, both kept out of decoration
   and chrome; the HUD's sun stays, it is the clock.
4. **Roads seen:** a warm path colour, wider, the selected building's roads brighter as today; carts visible on them.
5. **One display face:** Pixelify Sans (it matches the sprites) for titles and the wordmark, or Almendra SC; not both.
   Titillium for text and JetBrains Mono for code stay.
6. **The War Map's rows** in the palette's own tones.

**How it is decided, not by taste:** the same demo town in three variants of these tokens, each screenshot put through
three checks: in grey (do buildings and roads still stand off the ground?), squinted or blurred (what is seen first?),
and five seconds with a tester ("what needs you here?"). The variant where the answer is the 🔥 and the ❓ wins.

## 4. Not now

- **Redrawing the sprites, or a new palette for them:** No. They are the product's strongest look.
- **A light theme:** Later, if testers ask.
- **Office:** untouched by this pass; it is calm and monochrome by design.

## 5. Decided with the owner (2026-10-12)

1. **The biomes are a task of their own, P1.** Each building has a header per biome (`header-meadow`, `-dust`, `-ice`,
   `-lava`, `-void`); each is compared with its biome's ground, in grey and squinted, as in §3. The P0 pass touches
   only Camp · forest, the biome of the demo and the GIF.
2. **Almendra SC stays for the product's name only:** the wordmark "Orkcraft" is a picture of a name, not the
   interface's face. Every other display text is Pixelify Sans; text Titillium Web; code JetBrains Mono.

## 6. The yard's frame: ground, not a fence (P1)

Asked 2026-10-12: does the picket fence round a building's card fit the idea, should the whole window be a big
building, should the window be apart from the map, should the town go isometric?

**What the fence gets right:** a building has its plot, and its card is its yard
([yards.md](yards.md)); with Work gone, the data lives on the card on the town ([lighter-buildings.md](lighter-buildings.md) §2).

**What it gets wrong:** the fence is the densest repeated pattern on the screen; the building is tiny beside its
fenced card, so the town reads as "windows with fences" more than as a town; and its thick posts outweigh the roads'
thin lines, while the roads are meant to be the lines that matter.

| option | verdict | why |
|---|---|---|
| the whole window drawn as a big building | **No** | data inside drawn art scales badly and reads badly; art per type × three sizes × five biomes |
| the window's interface apart from the map | **No** | it is the Work panel the owner decided to drop the same day |
| **the yard as a patch of ground**: the card on trodden earth a little lighter than the ground, no fence line; posts only where a road enters, as a gate | **Yes, P1** | the yard stands off the ground by tone, not by pattern; **the roads become the only lines on the map**; at the map zoom there are no cards at all, only buildings and roads, where the strategy-game feel is strongest |
| isometric | **No** (at most Later, for the map zoom with no cards; likely never) | every sprite in every biome redrawn; rectangular cards of text do not sit in isometry; roads, clicks and layout rewritten; the 1990s style it follows was top-down anyway |

Checked as §3 is: in grey and squinted, the yard must stand off the ground and the roads must be seen first.

**A fence stays, as decoration, in the way of Stardew Valley** (the owner, 2026-10-12: that look is liked). The yard
is still the patch of ground; the fence is a light touch on it, never its frame:

- **light, warm wood**, lower in contrast than the roads, never the dark posts of today;
- **not a closed box:** short runs and corners, the back of the yard more than its sides, as a field's fence in that
  game;
- **open at its gates:** wherever a road enters, a gap with two posts;
- **smaller** than today's posts, and only at the overview and close zooms; the map zoom shows none;
- **none in Office** (calm and monochrome by design).

The test does not change: in grey and squinted, the roads are seen before the fence.

## 7. Pixel art stays; a painted style like Kingdom Rush is No

Asked 2026-10-12: move the look toward Kingdom Rush, or keep the pixels?

**Keep the pixels.**

1. **Cost:** a painted cartoon style (outlines, gradients, rich detail, animation frames) means redrawing twenty types
   × five biomes × their motions; and the whole pipeline is made for pixels (Scale2x, `tools/hat_sprites.py`, mascots
   drawn as grids by a text model, the painter's edit within a marked region). A painted style is far harder to make
   consistent with an image model.
2. **Small sizes:** buildings are drawn at 16 to 80 px; pixel art stays crisp there, painted detail turns to mush.
3. **Beside text:** pixels and a clean text face sit well together; a painted cartoon beside dense text reads as a
   mobile game's advert, and "it is a toy" gets louder.
4. **The audience:** to developers pixels say an indie craft they grew up with; the painted style says casual mobile.
5. **Another brand:** looking like one particular game is the risk of [open-questions.md](open-questions.md) Q18 again.

**What to take from it without changing the drawing:**

- **Juice:** a short motion and a flash when a cart arrives, an ork finishes, a ❓ appears or is answered. That, more
  than its drawing, is why it feels good. With [building-motion.md](building-motion.md); P1.
- **Warm, saturated accents on a dark ground:** the rule of §2 already.
- **Big, friendly silhouettes:** the buildings have them.

## 8. Camp commits to being a game (decided 2026-10-13)

The owner: today Camp is not colourful enough for a game and too much of a game for a working tool. The middle is the
worst place: it neither delights as a game nor convinces as a tool.

The decisions of 12–13 October give the way out: **Office is the working tool** (by day, on the laptop), **Camp is the
game** (after work, on the phone too) ([work-and-play.md](work-and-play.md)), and the people it is for find
optimising a pleasure ([audience.md](audience.md)). So Camp no longer has to look serious; Office does that job.
**Camp goes all the way to the game.**

1. **Brighter and warmer, with a hierarchy.** A cosy farming game is bright and still reads well: the ground bright
   but even, buildings standing off it by a dark outline and by lightness, and the loudest thing what moves. §2's rule
   holds with "quiet ground" meaning *even*, no longer *dark and grey*; the grey and squint checks of §3 stay.
2. **The sprites' palette changes, not their shapes.** The paleness comes first from every building being one green.
   A palette swap keeps every silhouette and gives materials their colours: wood brown, stone grey, roofs red, blue or
   thatch, each type its own. This refines §4: **no redraw of shapes; a new palette, yes.**
3. **Light by the time of day (Later):** a light town by day, a warm dusk in the evening, the moon at night, tied to the
   clock's sun and moon ([town-time.md](town-time.md) §5).
4. **One reference frame first, then the sprites:** the frame the GIF will be (Camp, the map zoom, the five core
   buildings, carts and orks, the evening), in two or three palettes, chosen by a test: five seconds with a tester,
   "what needs you here?" and "would you like to play this?".

**Priorities:** **P0 before the launch:** the reference frame and the palette swap of the five core buildings in the
forest biome (it is the GIF). **P1:** the other buildings and biomes ([color-pass.md](color-pass.md) §5, the biomes'
task). **Later:** light by the time of day.

**Not started yet** (the owner, 2026-10-13): the decision is recorded; no sprite or palette work, not even sketches,
until the owner starts it, and then with the reference frame first.

§3's token pass (P0 now) is not wasted: its ground, signals and roads are the base the brighter palette sits on.
