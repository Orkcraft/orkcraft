# Design — prompts for reference sprite sheets (2026-10-13)

For the owner's image model, with the round-2 frame attached ([color-pass.md](color-pass.md) §9c). **References,
never shipped** (§10): they become the commissioned artist's brief and a check of the decisions in
[town-readability.md](town-readability.md) and [color-pass.md](color-pass.md) §6a–6c.

## The shared head and tail (put on every prompt)

**Head:** "Pixel-art sprite sheet in the same style and palette as the attached image: three-quarter top-down view, a
cosy orc war camp, crisp hard pixels on a strict pixel grid, no anti-aliasing, no blur, no gradients. Every sprite has a
dark 1-pixel outline and a small soft dark shadow under it. Sprites laid out in a neat grid with even spacing on a
flat solid #FF00FF magenta background, each sprite separate, nothing touching. No text, no labels, no UI."

**Tail:** "Palette: lush but calm greens, warm brown wood, grey stone, bone-white tusks and skulls, dark maroon cloth.
Bright yellow and bright red appear nowhere except where asked."

## 1. The ork: one body, nine roles

**1a. The body's animations.** "One orc worker, the same character in every frame, 32 by 32 pixels, facing down-right.
Row 1: idle, 4 frames (breathing). Row 2: walking, 6 frames. Row 3: working with a hammer, 6 frames (swing and hit).
Row 4: carrying a small crate, 6 frames walking. Row 5: sitting on a log, 2 frames (resting). Same proportions,
same colours in every frame."

**1b. The roles as heads and tools on the same body.** "The same orc body nine times, only the headgear and the held
tool change, 32 by 32 pixels each, in one row: 1. a chieftain with a horned helmet and a small banner on his back;
2. a worker with a plain leather cap and an axe; 3. a builder with a stone hammer and a block; 4. an alchemist with
goggles and a glass flask; 5. a mechanic with a wrench and a gear on the belt; 6. a treasurer with a coin pouch and a
ledger; 7. a seer with a staff and a glowing eye charm; 8. a warden with a round shield and a big key; 9. a
pathfinder with a rolled map and a lantern. Readable at 32 pixels: each told apart by its silhouette."

**1c. The states** (UI badges are drawn by the product; here only poses). "The worker orc in five poses, 32 by 32: working
(mid-swing), waiting with a hand raised, slumped and frustrated with a small smoke puff over the head, sitting with
arms crossed (held), sitting and dozing (idle)."

## 2. Carts

"Small wooden hand carts, 32 by 24 pixels each, three-quarter view. Row 1, the loads: empty; a rolled scroll tied with
string; a closed wooden crate; a sealed letter with a wax seal; a thick book; three bundles stacked. Row 2, the same
cart with a small pole flag: no flag; a yellow flag; an hourglass hung on the pole; a red flag; four carts parked close
together in a pile." (Orks never move carts: see the rails section below.)

## 3. Ground and roads

**3a. Ground tiles.** "Seamless ground tiles, 32 by 32 pixels each, tileable on every side: three tones of calm grass
(plain, with tufts, with a few small flowers); trodden earth, two tones (a building's floor round its walls); the
transition from grass to earth on each edge and corner. Quiet ground: low contrast, small marks, nothing that draws the
eye."

**3b. The road set.** "A dirt road one cart wide, as a 32-pixel autotile set with grass on its sides: straight
horizontal, straight vertical, the four corners, the four T-junctions, a crossing, the four dead ends. A few small
stones at the edges. The road must be seen before the grass, but stay calm."

**3c. The camp's edge.** "A wooden palisade of sharpened logs with tusks on some posts, 32-pixel pieces: straight
horizontal, straight vertical, the four corners, a gate opening. For the outer edge of the camp only."

## 4. The buildings as kits (color-pass §6a–6b)

**4a. The hall.** "A building kit drawn as nine-slice pieces, three-quarter top-down: a canvas roof stretched on
wooden poles with rope ties, in dark maroon, in nine pieces (four corners, four edges, a centre) that stretch to any
size; a second roof of thatch; a third of stitched hides. Below, stone and log walls as nine-slice pieces, seen from
inside from above (a frame with a floor of trodden earth). Each piece separate."

**4b. Open ground.** "An open-air gathering place seen from above, 128 by 128 pixels: a ring of stones round a campfire,
logs to sit on, three orcs sitting round it. The same scene twice more: the fire calm and warm; the fire flaring red
with dark smoke (an alarm). Also a small pond with a reed shore and a round glass lens on a wooden stand over the water,
128 by 128."

**4c. The tower and the gate.** "A wooden lookout tower with a horn at the top, three-quarter view, 64 by 128 pixels;
seen from above its yard walls as nine-slice pieces. A stone gatehouse with tusks either side, a portcullis and a
banner on top, 128 by 96 pixels."

**4d. The five facades, at the door.** "Five building fronts, the lower part with the door only, 96 by 48 pixels each,
same style: 1. two posts with scrolls and notes pinned on a board, a skull on top (a task board); 2. a weapon rack and
a training dummy beside a log door (a worker pool); 3. a stone arch with tusks and a portcullis (a review gate); 4. a
reed shore with a small jetty (an inspector's lake); 5. a ladder and a signal horn at the foot of a tower (a lookout
for messages)."

**4e. The crests, above the roof.** "Ten small objects to stand on top of a roof, 32 by 32 pixels each: a curved horn, a
maroon banner with a tusk mark, a carved totem, a round glass lens, a chimney with grey smoke, a skull on a pole, a
lantern, a pair of crossed axes, a bundle of scrolls on a spike, a raven on a perch."

## 5. The camp put together (to check, not to cut)

"The same camp as the attached image, built from these pieces: five buildings as roofs at a distance, one roof
half-transparent showing a card-like room inside with orcs at work, the open fire place, the gatehouse and the lookout;
roads one cart wide between them; three carts in a line from the notice board to the gate, one with a scroll; one orc
with its hand raised; the palisade only on the camp's outer edge."

## How the sheets are judged

The grey test, squinting, five seconds ([town-readability.md](town-readability.md) §6); one projection and one scale
across all sheets; the ork's silhouettes told apart at 32 px; the roof's nine pieces really tile. What passes becomes
the artist's brief; nothing is cut out and shipped.

## Round 1 of the sheets, reviewed (2026-10-13)

The owner made five sheets: the roof and wall kits, the ork's animations, the tower and the gate, the palisade, the
five facades. **The palette holds** (maroon cloth, warm wood, grey stone, bone tusks, dark outlines) and the camp's
voice is right. Kept as the brief's direction: **the wall kit** (a true nine-slice: corners, edges, an earth floor),
**the gatehouse** (tusks, skull, maroon banners, portcullis), **the palisade** with tusks and its gate, the **Task
board** facade (posts, pinned scrolls, a skull) and the **Agent pool** facade (weapon rack, dummy).

**To fix:**

1. **The ork looks like the big strategy game's grunt:** bulky, muscled, green, a loincloth, tusks under the lip. It
   is the most recognisable silhouette that game owns, and the riskiest thing on any sheet for the name question
   ([open-questions.md](open-questions.md) Q18). **Our ork is our own:** smaller and rounder, a big head on a short
   body (reads at 32 px, cosier), a working camp's clothes (apron, cap, tool belt), a skin hue of its own (olive or
   moss, not saturated green). The commissioned artist gets this as the first line of the brief.
2. **The roofs are not nine-slice:** each canvas and hide piece has its own frame on all four sides, so they would
   show seams. A corner has a border on its two outer sides only, an edge on one, the centre none. Thatch is closer.
3. **One projection:** the tower is drawn isometric (a diamond footprint), the rest three-quarter top-down. The facades
   sit on baked-in islands of grass and earth; a facade is an overlay at the foot of the walls, with no ground.
4. **The shadows are blended into the magenta** and will leave a purple fringe when keyed out. The product draws
   shadows itself ([town-readability.md](town-readability.md) §2): sheets carry **no shadows**.
5. **Too fine for the size:** the ork is drawn at about 64 px of detail; at 32 px it will blur. Drawn at the size it
   is shown.
6. **The lookout's horn became a metal megaphone,** a modern object in the camp; a bone horn on a stand. The lake's
   facade has a jetty to no water and no lens.
7. **The walk turns mid-row** to a profile; one direction per row.
8. **Not made yet:** the roles, the poses, carts, ground and roads, open ground, crests.

**The changes to the shared head:** "No shadows. Every sprite drawn at its final size, no finer detail than that size
can hold. One three-quarter top-down projection for everything, never isometric."

## Round 2: the ork of our own, taken (2026-10-13)

The new ork is **taken as the character's direction for the brief:** a small round worker, a big head on a short
body, a cloth cap, a leather apron and a tool belt, small tusks, olive skin. Nothing in it is the big strategy game's
grunt; it reads at a glance and is cosy, as the camp is. Notes for the next sheets and the artist:

- **Directions:** every walking row faces the viewer; carts and orks move along roads in four directions, so walking
  is drawn down, up and to the side (the side mirrored for the other way).
- **The shadows are still purple-blended:** "no shadows" has to be said at the top of the prompt, not only in the
  head.
- **The hammer's swing** changes hands and shows two tools in some frames; the artist animates it, the reference only
  shows the pose.
- **Pointed ears and a cap** may read as a goblin; the tusks keep it an ork. Checked with testers at the GIF's zoom.
- **The face** frowns in most frames; a friendlier resting face for idle and walking suits the camp's voice; the
  frown kept for a stuck ork.

## Round 3: directions and roles (2026-10-13)

**Taken:** the back view, the side walk, the ork pushing a hand cart (the cart reads at once), and the nine roles,
each told by its silhouette: the chieftain's horned helmet and banner, the worker's axe, the builder's headband and
block, the seer's hood and staff (the strongest), the warden's helmet and shield, the pathfinder's fur hat, map and
lantern. The shadows are gone where "no shadows" led the prompt.

**To fix:**

1. **Signal colours in the props:** the warden's bright gold key and the alchemist's red flask use the yellow and red
   kept for ❓ and errors ([town-readability.md](town-readability.md) §2): brass and muted green or blue instead.
2. **The alchemist and the mechanic** both wear goggles; one changes (the alchemist a pointed cloth hat, or the
   mechanic a welder's cap).
3. **The treasurer** is weak: a ledger only. A coin pouch on the belt and a small abacus or scales.
4. **Walking towards the viewer** barely moves between frames; the legs and arms must swing as in the side walk.

## The camp put together, round 1 (2026-10-13)

**What it proves:** the roof lifted on one building, with orks working at tables inside its walls, reads at once:
color-pass §6a works as a picture. The open ground (a ring of stones, logs, the fire) and the tusked gate fit the kit.

**Why it is not yet our town:**

1. **A village, not a factory:** nine houses round a square, paths as loose patches of mud. The town is five buildings
   joined by roads one cart wide, the work going one way along them (board → pool → gate); nothing here shows a flow.
2. **Isometric** (houses at 45°), against the one three-quarter top-down projection; isometry is a "No"
   ([decisions-2026-10.md](decisions-2026-10.md) §3).
3. **Fire everywhere** (both gate towers, two fires, torches): fire is the 🔥 signal; decorative fire empties it. One
   fire only, the Review board's, calm.
4. **A skull on every roof:** the crest is each building's own mark (§6b); repeated, it marks nothing.
5. **Every building drawn as its own picture,** not the roof and wall kit: the brief's cheapness and the community's
   buildings rest on the kit.
6. **Missing:** the ❓, the developer's tells, a chain of carts; the orks are the old generic ones, not ours.

**What follows:** an image model composes a village of its own; it does not lay out our town. **The frame is put
together by hand** from the sheets on a grid (any editor, about half an hour): it also checks the scale, the projection
and whether the nine-slice pieces join. A tighter prompt is kept as the fallback.

## The camp put together, round 2: the first frame that is our town (2026-10-13)

**Holds:** five structures in one row, one projection, the palisade only behind; the Agent pool's hall open with our
orks at tables inside; one calm fire (the Review board); the ❓ on an ork by the hall is the loudest thing in the frame;
a chain of three carts on a road one cart wide; a different crest on most roofs (lantern, totem, banner, horn); quiet
ground. **It is good enough for the first five-second test** with developers, as it is.

**For the next round:**

1. **The flow:** each building's door joined to the road by a short path, and the carts moving board → hall → gate,
   rolling by themselves (orks never move carts), so the line of work is seen, not only a road in front of the camp.
2. **Two horns** (the gate and the lookout): the gate's crest becomes a skull-and-banner or a portcullis wheel.
3. **The ground went too dull:** the grass one step back towards round 2's lushness, still in two or three calm tones.
4. **The developer's tell:** the `</>` on the scroll is not legible; drawn larger, and a small wooden plate at the gate
   ("PR") as the second tell (§9b).
5. **Sizes:** the hall dwarfs the board; the core buildings closer in size (the card's three sizes are a choice, not a
   given).

## Rails and mine carts (color-pass §6d)

**The track set.** "No shadows. A crude orc-built mine-cart track as a 32-pixel autotile set, three-quarter top-down:
two wooden rails on log ties, a few bone ties; straight horizontal, straight vertical, the four corners, a switch
splitting into two, a merge of two into one, a crossing, a buffer stop of logs at a dead end. Low contrast: the track
reads as a line, not a texture."

**The mine carts.** "No shadows. Small wooden mine carts with iron-banded sides for that track, 32 by 24 pixels, in
side view and in front view. Row 1, the loads: empty; a rolled scroll with a large clear "</>" mark; a crate; a sealed
letter; a book; three bundles. Row 2: the cart with a small pole flag: none, yellow, an hourglass, red; four carts
lined up at a buffer stop. Row 3: one cart rolling to the right by itself, 4 frames (wheels turning)." **Orks never
move carts** (the owner, 2026-10-13): the town routes them; an ork works on a cart at its table inside a building.


## The camp put together, round 3: rails (2026-10-13)

**The reference frame is reached.** One track with a spur to each building; mine carts on it; the `</>` scroll
legible and a "PR" plate at the gate (the developer's tells, §9b of color-pass); the ❓ the loudest thing; the open
hall with orks at work and a cart at its door; a different crest on most buildings; lush, calm grass. **It goes to the
five-second test with developers as it is**, and into the artist's brief.

**For the brief, not for another round:**

1. **The flow in the layout's order:** left to right as the work goes: External listeners (the lookout) → Task board →
   Agent pool → Review gate. Today the lookout stands at the far right, after the gate.
2. **The core five are board, pool, gate, Inspector and listeners** ([catalog-shelves.md](catalog-shelves.md)): the
   fire ring is the Review board, not core; the Inspector's lake takes its place in the GIF's camp. (The prompt asked
   for the fire ring; the prompt was wrong.)
3. **The track is too loud:** heavy ties across the whole width make it the strongest pattern; fewer, lower-contrast
   ties (color-pass §6d).
4. **The palisade is too tall** for a back edge: half its height.
5. **An ork rides in the third cart:** orks never ride or move carts.
6. **The hall has no crest.**

## The twist: a Warchief in a tie, workers in work clothes (the owner, 2026-10-13)

**Taken, as the characters' signature.** It is the first audience's own joke ([audience.md](audience.md) §2a): a day
of other people's merge requests and calls with managers, then the evening's camp. The orks are a small company of
their own, and it sets them further apart from the big strategy game (Q18).

- **The Warchief:** the horned helmet, and **a tie, loosened**, over the leather: the boss just back from a meeting.
  (The person is the Warchief's boss; the joke is on meetings, never on the person.)
- **The workers:** a hard hat made of half a skull or a bone-white helmet, the apron and tool belt they already have;
  the Grunts on the line in **work vests in a muted orange-brown**, never bright orange or yellow (kept for signals,
  [town-readability.md](town-readability.md) §2).
- **The rule for the joke:** **modern things only as deliberate jokes on the characters,** one per role at most (a
  tie, a hard hat, a clipboard for the Treasurer, a headset for the Lookout); **never in buildings or signals**, where
  the camp stays a camp (the megaphone stays out).
- **The voice matches:** the Warchief's lines may joke about meetings and stand-ups; labels and anything about money
  or safety stay plain (CLAUDE.md, Wording).

**Prompt** (with the round-3 roles sheet attached): "No shadows. The same nine orc roles as the attached sheet, same
body and style, with small modern work clothes as a joke: the chieftain keeps the horned helmet and wears a loosened
necktie over his leather vest; the worker wears a bone-white hard hat and a muted brown work vest; the builder a hard
hat; the treasurer holds a wooden clipboard; the lookout wears a simple headset over the cap; the others unchanged.
No bright yellow, no bright red, no bright orange. 32 by 32 each, one row."

## The concept frame from the owner's sprites (2026-10-14)

Put together by hand from the sheets in `design-system/sprites/orkcraft 0.3/` (magenta keyed out, nothing redrawn):
[img/orkline-camp-concept.png](img/orkline-camp-concept.png) and its grey version
[img/orkline-camp-concept-grey.png](img/orkline-camp-concept-grey.png). A concept, not the product's drawing.

**What it shows:** the work going left to right (External listeners → Task board → Agent pool → Review gate → out
to the Publisher), a spur of track from each door, mine carts rolling by themselves with their loads (a letter, the
`</>` scroll, a crate), the Agent pool with its cover lifted and orks at work inside (one cart at an ork's place), the
Inspector's lake on its own spur below the line, one ork asking (❓, the loudest thing), a cart waiting at the gate for
the person (a yellow flag and its chip), the Warchief by the gate, words only on dark chips.

**What it teaches:**

- **In grey the ❓ and the chips still lead;** the buildings stand off the grass by their dark outlines.
- **The track is the strongest line,** as color-pass §6d wants, and a little loud: its ties could be fewer.
- **The Task board's facade sits on its own island of earth;** the facades are to lose their baked-in ground.
- **The lifted cover reads at once,** with the walls kit as the frame: color-pass §6a is right.
- **Missing from the sheets:** the Publisher's catapult, the ways in through the palisade, a table inside the hall.

## What the 0.3 sheets cover, and what is missing (2026-10-14)

**Replacing the sprites is not a swap.** Today's sprites are building headers on cards (`design-system/sprites/buildings/<type>/header*.png`,
per biome); the 0.3 sheets are a different drawing: a three-quarter camp of covers, walls, rails and mine carts. They
come into the product with the backlog's C3 (the card as a building), C4 (rails and mine carts) and C2 (badges on
orks), not before. **What can be done now without code:** cutting the sheets into single transparent sprites, named,
at their target sizes (1× and 2×), into a new folder beside today's, ready for C3 and C4.

| need | covered by 0.3 | missing |
|---|---|---|
| the ork | idle, walk (4 ways), hammer, carry, sit; nine roles | **the state poses** (asking, stuck, held, dozing); the Warchief in a tie and the work clothes |
| carts | loads, flags, a pile, rolling | — |
| track | straight, corners, switch, merge, crossing, buffer stops | **a T-junction** (a spur joining from above), **quieter ties** |
| buildings | tower, gate, walls kit, three roof kits, fire ring (three states), lake, five facades | **the Publisher's catapult** and its launch; **facades without their island of earth**; **tables and workbenches** inside a hall |
| the camp's edge | palisade pieces, its gate | **a gap where the track comes in and goes out** |
| ground | — | **seamless grass in three tones and trodden earth** |
| crests | ten | — |

**Prompts for what is missing** (the shared head first, with "No shadows" as its first line; attach the 0.3 sheet of
the same kind as the style reference):

1. **The catapult.** "No shadows. A crude orc wooden catapult that is the end of a mine-cart track, three-quarter
   top-down, 160 by 160 pixels: a throwing arm with a bucket, log frame, rope, tusks on the base. Four frames: resting;
   the arm pulled back with a scroll in the bucket; mid-throw; the scroll flying away over a palisade. No fire."
2. **The ways in and out.** "No shadows. The same sharpened-log palisade with a gap in it where a mine-cart track passes
   through, as 32-pixel pieces: the gap with the track running in from outside, the gap with the track running out, and
   both with small tusked posts either side."
3. **Facades without ground.** "No shadows. The same five building fronts as the attached sheet, the lower part with the
   door, but with no ground, grass or earth under them: only the building, cut straight at the bottom edge, on flat
   magenta. The lookout tower's front with a bone horn on a stand instead of the metal megaphone."
4. **Inside a hall.** "No shadows. Furniture seen from three-quarter top-down for the inside of an orc work hall, 64 by
   48 pixels each: a rough wooden table with scrolls, a workbench with tools, a table with a small anvil, a desk with an
   open book and a candle, a crate stack, a barrel, a bench."
5. **The T-junction and quieter track.** "No shadows. The same mine-cart track as the attached sheet, as 32-pixel
   tiles, with fewer and lower-contrast ties: straight horizontal, straight vertical, a T-junction where a branch joins
   the horizontal track from above, the same from below, and a crossing."
6. **Ground.** "No shadows. Seamless ground tiles, 32 by 32 pixels, tileable on every side, in the same palette: three
   tones of calm grass (plain, with tufts, with a few small flowers); trodden earth in two tones; grass to earth edges
   and corners. Low contrast, nothing that draws the eye."
7. **The ork's states.** "No shadows. The same orc worker as the attached sheet, 32 by 32, five poses: working with a
   calm face; waiting with one hand raised and a curious face; slumped with a frown and a small grey smoke puff over
   the head; sitting with arms crossed; sitting and dozing."
8. **The Warchief and work clothes.** The prompt of "The twist" above.

## The concept frame, v2, with the missing pieces (2026-10-14)

[img/orkline-camp-concept-v2.png](img/orkline-camp-concept-v2.png) (and `-grey`): the owner's second batch put in:
seamless grass tiles, the quieter track with T-junctions from above and below, furniture inside the Agent pool, the
new lookout and gatehouse, a covered building (Research, below the line, to show the cover beside the lifted one),
and **the Publisher's catapult at the line's end with a scroll flying over the wall**: the camp's story from the way
in to the launch, in one frame.

**Notes on the batch:** the ground tiles carry a thin dark border each (cut inside it to tile); the catapult is drawn
in side view, a step off the three-quarter projection (acceptable for one machine, the artist evens it); the palisade
gaps join the track with a curve, good for a way in on the back edge; the hall furniture reads well at a quarter size.

**A second catapult** (2026-10-14): richer (a skull on the front, tusks, its own buffer stop, a clear launch in four
frames), but **isometric, its track running diagonally**: it cannot join the camp's orthogonal track and breaks the one
projection. Kept as the design to keep (skull, tusks, buffer stop), redrawn in the camp's view with the track coming
in straight from the left; until then the side-view catapult is the one in the concept frame.
