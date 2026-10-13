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
together in a pile. Row 3, the cart pulled by the worker orc, 6 frames walking right."

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
