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

**A fence stays, as decoration, in the way of a cosy farming game** (the owner, 2026-10-12: that look is liked). The yard
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

**The style's three sources** (the owner, 2026-10-13), named by kind, not by title (the care of
[open-questions.md](open-questions.md) Q18), each giving one thing, so the mix does not turn to mush:

| source | what is taken |
|---|---|
| **a 1990s real-time strategy game** (the base) | big readable silhouettes; materials (wood, stone, bone); the orks' camp; the top-down, slightly tilted view; the HUD's command-panel frames |
| **a cosy farming game** (the warmth) | daylight, saturation, a little life around, friendly characters, fences and paths, the juice of feedback |
| **a factory-building game** (the flow) | **the flow read at a glance:** carts with their load seen on the roads, a building's motion saying working or standing, the pleasure of optimising |

**From the factory game, later:** hold a key and Office's numbers appear over the Camp world, let go and the world is
clean again: a look at the numbers without switching looks ([work-and-play.md](work-and-play.md)). **Later.**

**Priorities:** **P0 before the launch:** the reference frame and the palette swap of the five core buildings in the
forest biome (it is the GIF). **P1:** the other buildings and biomes ([color-pass.md](color-pass.md) §5, the biomes'
task). **Later:** light by the time of day.

**Not started yet** (the owner, 2026-10-13): the decision is recorded; no sprite or palette work, not even sketches,
until the owner starts it, and then with the reference frame first.

§3's token pass (P0 now) is not wasted: its ground, signals and roads are the base the brighter palette sits on.

## 9. Prompts for the owner's experiments (2026-10-13)

Given to the owner to try by hand with an image tool. Rules: **no game titles** in a prompt (Q18; and a title makes a
model copy); crisp pixels; sprites on a solid `#ff00ff`; each result judged in grey, squinted, and by "what needs you
here?" in five seconds; results kept out of the repository until the sprite work starts (§8).

**1. The reference frame** (the GIF's), run three times with the last line's palette changed:

```
Pixel art screenshot of a cosy top-down management game, 16:9, crisp chunky pixels, no anti-aliasing, flat 2D front-facing buildings seen from slightly above, no isometric perspective.
An orc camp at early evening, warm low sunlight, long soft shadows. Even, bright grass ground with a few darker tufts; sandy dirt paths connect the buildings.
Five buildings, each with its own materials and a dark 1px outline so it stands off the ground:
1) a wooden notice board on two posts with cream paper notes pinned on it and a small bone skull on top;
2) a timber barracks with a red-brown tiled roof, small banners, a training yard;
3) a stone gate with two short towers, an iron portcullis and blue pennants;
4) a small stone reading lodge with one big round glass lens window;
5) a tall wooden lookout tower with a thatched roof and a horn hanging from it.
Small green-skinned orcs with tusks walk the paths; wooden carts carry crates and papers between buildings.
One orc stands at the barracks with a bright yellow speech bubble containing "?". One small red-orange flame burns on the gate's tower roof. These two are the brightest, most saturated things in the image; everything else is calmer.
A light warm-wood picket fence runs along the back of each yard only, open where a path enters.
No text, no UI, no logos.
Palette: [A] warm greens, browns, terracotta, cream / [B] cooler: sage, slate stone, blue roofs, cream / [C] autumn: ochre grass, rust roofs, dark timber
```

**2. A new palette for one building** (the existing sprite attached, e.g. `design-system/sprites/buildings/barracks/header@2x.png`):

```
Recolour the attached pixel-art building. Keep its silhouette, every pixel's position, its size and its outline exactly; change only the colours.
Give it materials instead of one green: timber walls in warm browns, a red-brown tiled roof, bone-white horns and trim, iron-grey metal parts, a 1px dark outline round the whole shape.
Crisp pixels, no anti-aliasing, no new details, no shading style change. Solid flat magenta #ff00ff background.
```

The materials line per building: Task board `oak board and posts in warm browns, cream papers with tiny dark marks, a
bone skull`; Review gate `grey stone towers, an iron portcullis, blue pennants, a brass padlock`; External listeners `a
timber tower, a straw-yellow thatched roof, a brass horn`.

**3. The same town in Office** (beside Camp in the README):

```
The same five-building camp as the attached image, redrawn as a calm monochrome office dashboard: a dark warm-grey background, each building a simple flat outline icon in one muted tone, paths as thin lines, carts as small rectangles, short labels and numbers beside each building ("To Do 3", "2 at work", "34 % of the window"). One yellow "?" marker and one small red marker are the only colours. 16:9, crisp, no pixel-art texture, no logos.
```

**4. The camp on a phone in the evening:**

```
Pixel art, portrait 9:19 phone screen, a cosy orc camp seen from above at dusk: warm lamplight in windows, a moon low in the sky, the same five buildings (notice board, timber barracks with red roof, stone gate with blue pennants, stone lodge with a round lens window, wooden lookout with thatch), sandy paths, a few orcs walking home, one cart arriving at the gate. One yellow "?" bubble above an orc is the brightest thing. Crisp pixels, no text, no UI.
```

**5. A yard with a light fence** (one building, close):

```
Pixel art close-up, top-down, of one building's yard in a cosy orc camp: a patch of trodden earth slightly lighter than the grass around it; on it a wooden notice board with cream papers and a bone skull; a light warm-wood picket fence only along the back of the yard and two short runs at the front corners, open at the front where a sandy path enters with two gate posts. A small wooden cart with crates on the path. Crisp pixels, no anti-aliasing, no text.
```

### 9a. Round 1 (2026-10-13): what held, what changes

The reference frame (prompt 1), first try. **Held:** the ❓ and the flame are the loudest things; each building has its
own materials and reads by its silhouette; carts and orks on the paths give the flow. **Changes asked by the owner:**
more saturated grass; narrower paths; more **orkish** buildings (tusks, axes and the like). **Seen besides:** the
buildings read as a human medieval village (a half-timbered cottage, a knight's castle), the main thing to fix; the
fence ran as a long closed row across the frame, against §6; the paths outweighed the buildings.

**Round 2's prompt** keeps prompt 1 and changes: lush, saturated, even grass; paths one cart wide; every building crude
and orkish (rough lashed logs, hide roofs, palisade spikes, tusks and horns, skulls, crossed axes, red war banners with a
white tusk mark); the fence only as short runs at a yard's back corners. If it turns grim, the line "Friendly and cosy,
not menacing: rounded shapes, warm light, a little humour." is added: a cosy orc camp, not a dark fortress.

### 9b. Does the frame speak to the first audience? (2026-10-13)

Half. **It catches:** developers who like pixel strategy and cosy games stop on it; the ❓ reads; carts on paths hint at
a flow. **It does not explain:** nothing in it says *code*, so the first audience ([audience.md](audience.md)), people
building their own projects with agents, may take it for one more cosy farming game and scroll on; the carts read as
decoration, not as a flow of work, and the factory's pleasure is what holds this audience; and a generated look
(drifting scale, generic detail) is something developers are quick to see.

**Developer tells in the frame, two or three, no more** (the cosiness stays): a scroll marked `</>` or a git branch on a
cart; a small "tests ✓" bubble over a second ork; a "PR #42" plate at the gate; "⏳ 34 %" in the HUD's corner. **The
factory:** two or three carts in one chain along one route (board → barracks → gate), so a line of work is seen.

**Checked, not argued:** the frame shown to five developers, "what is this product?". Three or more saying "something
with agents or code": it lands. "A farming game": the tells are too weak.

**The GIF carries the bridge a single frame cannot:** in ten seconds, the camp → a click on the ❓ → the console with an
agent's real question about code → the answer → the cart rolls to the gate with its pull request. The bridge between the
game and the work is the positioning itself.

### 9c. Round 2: the direction is taken (2026-10-13)

The owner prefers round 2's palette and style to round 1. **Kept as the reference frame's direction:**

- **Orkish, not a human village:** logs, hides, tusks, skulls, spikes, red banners with a tusk mark; the five
  buildings stay apart by material (hide and timber barracks, dark stone gate, grey stone lodge with its lens, a
  thatched lookout with its horn, a board with a skull).
- **Signals stay loudest:** the yellow ❓ (about `#fefe08`) and the flame on the gate are the only warm saturated spots
  besides the banners' red (about `#a32926`).
- **The palette, sampled:** grass about `#2f9f2f`, the path about `#eba756`. Warm brown wood on a green field reads
  well in grey.

**To fix in the next frame:**

1. **The grass one step quieter, in two or three tones**, with tufts and small patches of flowers: today it is one flat,
   very saturated green over large empty areas, louder than the "quiet ground" rule (§1) and behind the GUI's cards it
   would tire the eye. Same hue, less saturation; the yellow-green corner gradient dropped.
2. **The fence:** the owner likes it; it may run along the camp's back edge as a border, never between buildings or
   across a road.
3. **The developer tells and the chain of carts** of §9b are still missing.
4. **One projection:** the buildings mix top-down and three-quarter; the sprites keep one angle.

Not started: no sprites until the owner says (§8).


### 9d. The next batch of reference images (2026-10-13)

Made by the owner in an image model while the review waits, each with the round-2 frame attached and opened with "Same
pixel-art style, palette and three-quarter top-down projection as the attached image". References, not sprites: the
model keeps no pixel grid, and the text in images is not trusted (in the product every word is on a UI chip,
[town-readability.md](town-readability.md) §2). In order:

1. **Round 3 of the frame:** §9c's fixes, banners maroon, outlines and shadows, the developer tells of §9b, a chain of
   three carts, one ❓ and one flame as the only bright yellow.
2. **The readability stress test:** 8 orks and 10 carts; most working with no badge; one ❓, one red `!`, one ⏳; a pile
   of four carts; one chip "#42 · Login form". Checked by [town-readability.md](town-readability.md) §6.
3. **The orks by role:** Warchief, Grunt, Mason, Alchemist, Mechanic, Treasurer, Farseer, Warder, Pathfinder, one
   size and angle, readable at 32 px ([ork-icons.md](ork-icons.md)).
4. **One ork's states:** working, asking, error, held for a limit, idle.
5. **The carts:** loads (code, asset, message, document, ×3) and state flags (none, yellow, ⏳, red, a pile ×4).
6. **The same town in Office:** flat grey shapes, plain labels, rows of ids, one yellow dot
   ([work-and-play.md](work-and-play.md)).
7. **The GIF's storyboard, four frames:** the camp with a ❓ → the console with a question about code → the answer →
   the cart reaches the gate with its pull request.

If time is left: the camp at night (for the clock and Camp after work), and a phone frame (the camp above, the console
below; [audience.md](audience.md) §2a).

## 10. The art that ships is made by people, not generated (2026-10-13)

**What was seen:** Pixel Agents, the category's leader ([similar-products.md](similar-products.md)), draws with a free
asset pack, not with generated images. It bears out [open-questions.md](open-questions.md) Q11's worry: this community
reads generated art as slop, and a developer is quick to see it.

**Today:** Orkcraft's sprites were made with an image generator, then reduced to the pixel grid by hand
([sprites.md](sprites.md), "how the done sprites were made").

**Decided:**

1. **Generated images stay references:** the palette, the silhouettes, the rules (§9). They are never shipped, nor
   shown in the README, the landing page or a post as Orkcraft's art.
2. **What ships is made by people:**
   - **a free pack as the base** (ground, paths, trees, fences, props), **CC0 first** (no conditions), CC-BY with its
     credit in `NOTICE`; **no share-alike or GPL art**, so the art's terms never mix with Apache 2.0;
   - **a pixel artist commissioned for what is Orkcraft's own:** the five core buildings, the orks by role
     ([ork-icons.md](ork-icons.md)), the carts and their loads ([town-readability.md](town-readability.md)). The
     generated references of §9d are the artist's brief. The artist credited in the README and on the landing page.
3. **Said plainly:** "hand-made pixel art by ‹artist›" on the landing page: in this category it is a difference.
4. **Priority:** **P0 before the launch** for what the GIF, the README and the landing show (the camp at the overview
   zoom, the five core buildings, a Grunt, a cart); the rest of the sprites follow. Until then the generated sprites
   stay in the product, and no new art is generated for it.

**For the owner:** a budget and a person for the commission. *Default:* one pixel artist from the indie community, a
fixed brief (five buildings, nine orks, carts and loads, one palette), the pack chosen together with them so the two
match.
