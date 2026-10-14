# Design — v3: prompts for the reference frames and every asset to replace (2026-10-14)

Status: for the owner's image model, tonight. Built on [decisions-2026-10.md](decisions-2026-10.md) §13 (the keeper
instead of the cover, the inside of a building, a brighter Camp, art generated for now) and on what the rounds of
[asset-prompts.md](asset-prompts.md) taught. **Order:** the frames of §2 first; the owner picks one look; only then the
sheets of §3, each with the chosen frame attached as the style reference.

## 1. What changes from v2, in one place

1. **Brighter and more saturated than Camp on `main`.** A sunny late-afternoon camp, not a dusk war camp. Away from
   the strategy game's colours: **no maroon banners, no gold, no blood red, no spikes on everything**.
2. **The proposed palette** (the owner corrects it on the frames):
   - grass: lively meadow greens, from fresh yellow-green to emerald, still a **middle value** (sprites and chips stand
     off it);
   - wood: warm honey and caramel; stone: cool light grey with a hint of lilac;
   - cloth (banners, roofs, aprons): **teal and plum**, with sky blue as a third;
   - water: clear turquoise; bone: cream;
   - the ork: our own olive-moss skin, unchanged;
   - **reserved for signals only, nowhere else:** bright yellow (a question), bright red (an error), cool grey-blue
     (held).
3. **Scale: at most ten buildings on a 1440 × 900 laptop window.** A core building about 200–260 screen px wide, an ork
   about 56–64 px tall, a mine cart about 64 px wide. Sprites are drawn at **half** that (art pixels shown at ×2):
   a core building 96–128 art px wide, an ork 32 × 32, a cart 32 × 24.
4. **A cart is found from far away:** an oversized, high-contrast load (a big scroll with `</>`, a crate) and a tall
   flag; carts are the only things that move along the track.
5. **A building is one picture now.** The cover no longer lifts (§13.1), so no nine-slice roofs: each building is a
   whole sprite with **a door** where its keeper steps out. Much cheaper to generate, and to keep in one style.
6. **Type:** a pixel display font for titles and chips, a plain readable sans for labels, a monospace for the
   terminal; every size a step larger than today. Fonts are chosen from free (OFL) families by the V3 session, not
   generated; the frames only show the feel.

## 2. The reference frames (generate these first)

**The shared head for every frame** (paste first):

> "A finished screenshot of a cosy pixel-art strategy-management game for programmers, 16:10, 1440 × 900. Crisp hard
> pixels on a strict grid, every sprite with a dark 1-pixel outline, no blur, no gradients on the art. One
> three-quarter top-down projection for everything, never isometric, every road and wall along the screen's axes.
> Bright, saturated, sunny late afternoon: lively meadow greens, warm honey wood, light cool stone, teal and plum cloth,
> turquoise water, cream bone. Small round friendly orcs with olive-moss skin, big heads, short bodies, cloth caps,
> leather aprons, tool belts, small tusks. No maroon, no gold, no spikes. Bright yellow and bright red appear ONLY on
> the question mark and error markers described below. The interface is clean and modern pixel-UI: cream parchment
> panels in dark walnut frames with teal accents, short readable English labels."

**F1. The town.**
> "[head] The whole camp on one screen, seen from above. Nine buildings, no more, in two rows, joined by one wooden
> mine-cart track that runs left to right with a short spur to each building's door. In the order of the work, left
> to right on the top row: a wooden lookout tower with a bone horn (incoming messages); a notice board under a small
> roof with big scrolls pinned on it (the task board); a large work hall with a teal canvas roof (the agent pool);
> a stone gatehouse with a portcullis and a small wooden plate reading "PR" (the review gate); at the far right a
> wooden catapult with a scroll in its bucket. Bottom row, smaller: a turquoise pond with a glass lens on a stand (an
> inspector), a stone tower with a big open book (research), a workshop with a little anvil (test bench), the town
> hall, a long house with a plum banner. Five small mine carts on the track, rolling by themselves, each with a big
> clear load: two with a scroll marked "</>", one with a crate, one with a sealed letter; one cart stopped at the gate
> with a tall bright yellow flag. Orks at work at their buildings' doors; one ork by the work hall with a bright yellow
> "?" over its head, the loudest thing on screen. A low palisade only along the top edge, with a gap where the track
> comes in. A thin top bar: the town's name on the left, three small counters (a flame "0", a "?" "1", a meat
> icon "3"), and a "Stop all" button on the right."

**F2. A building clicked** (the Task board).
> "[head] The same camp as the attached frame, the same zoom. The task board is selected: a soft light ring on the
> ground round it, the rest of the town slightly dimmed. Its keeper, an orc with a quill behind the ear, has stepped
> out of the door; over its head a white thought bubble with a tiny scroll icon and the words "Fix login". Over the
> building floats a large unrolled parchment scroll with four short lines: "Task board", "To do 4 · Doing 2 · Done
> 11", "Next: Fix login bug", "2 waiting for you". At the bottom centre of the screen a row of five square pixel
> buttons in walnut frames, each with an icon and a short label under it: "New task", "Pause", "Run next", "Open",
> "Settings"."

**F3. An ork clicked.**
> "[head] The same camp, the same zoom. One orc in front of the work hall is selected (a light ring under it, a thin
> rope of light to the cart it works on). Its thought bubble shows a tiny gear and "Add tests". At the bottom, across
> the full width, a dark terminal panel about a third of the screen high, in a walnut frame: on its top edge the orc's
> small face, its name "Grunt 2", and tabs "Now", "History", "Tokens", "Task"; inside, monospace lines of a coding
> agent's work in light green and white on near-black, the last line a blinking cursor; on the right of the panel a
> small block "Tokens 41k · 6 % of window"."

**F4. Inside the Task board.**
> "[head] A full screen inside one building. The left 60 %: the inside of a big wooden hall seen from above, warm
> light, a plank floor, timber beams, three tall wooden boards standing side by side with carved headings "To do",
> "Doing", "Done". On the boards, large cards as sheets of parchment and slabs of light stone, pinned with bone pins,
> each with a two-word title in hand lettering; instead of a checkbox each card has a small cloth flag, lowered on
> "To do", raised on "Done". Three orcs inside: the keeper with a quill reading a card; one carrying a stone slab
> between boards; one holding a big magnifying glass to a card; each with a small thought bubble over its head with a
> two-word task. The right 40 %: a tall panel like a merchant's window in an action role-playing game, cream parchment
> in a walnut frame: the title "Task board" at the top with a small notice-board icon, then plain settings as rows with
> pixel toggles and small value boxes ("Takes tasks from: GitHub issues", "Up to 3 at once", "Ask before starting:
> on"), a "Save" button at the bottom. A clear "Exit" button with an arrow in the top-right corner of the screen."

**F5. A cart clicked: the task's history.**
> "[head] The same camp, the same zoom. One mine cart with a "</>" scroll is selected (a light ring). Beside it a
> parchment card, like a shipping waybill, with a wax seal at the top and the cart's id "#42 Fix login bug"; under it a
> vertical route of five small stops with icons and times: "Task board 10:02", "Agent pool 10:05 — asked 1 question",
> "Agent pool 10:31 — tests added", "Review gate 10:40 — waiting for you", and a dotted last stop "Publisher"; at the
> bottom a line "Tokens 58k · 9 % of window · 38 min"."

**F6. The phone (optional).**
> "[head] A phone screen, 9:19.5, portrait. The same camp at a smaller zoom fills the top half, orcs and carts moving,
> one "?" over an orc. Over the bottom half a sheet slides up: "Since your last look (40 min)": "2 carts at the gate",
> "1 question", each with one big button ("Answer", "Pass", "Send back")."

**How a frame is judged** (before any sheet): it feels like a game you want to open in the evening, not a dashboard;
the "?" and the yellow flag are the first things the eye finds (the grey test); the carts and the track read at once;
nothing in it calls the big strategy game to mind; nine buildings fit without crowding.

## 3. The sheets: every old asset, replaced

**The shared head for every sheet** (paste first, with the chosen frame attached):

> "No shadows. Pixel-art sprite sheet in exactly the style and palette of the attached image. Crisp hard pixels on a
> strict grid, no anti-aliasing, no blur, no gradients, each sprite with a dark 1-pixel outline, drawn at its final
> size with no finer detail than that size can hold. One three-quarter top-down projection, never isometric. Sprites
> in a neat grid with even spacing on a flat solid #FF00FF magenta background, nothing touching, no ground under
> them, no text unless asked. Bright yellow and bright red appear nowhere."

### 3a. The buildings (one picture each, with a door)

Each building 96–128 px wide for the core and 64–96 px for the rest, its door in the lower middle of its front.
Generate in four sheets of about six; each building's line is what it does, drawn as a camp object.

**Sheet B1, the core and the line's ends:**
1. **External listeners:** a wooden lookout tower with a bone horn on a stand and a little ladder, 96 × 128.
2. **Task board:** a notice board under a small shingle roof with big scrolls and stone slabs pinned to it, 128 × 96.
3. **Agent pool:** a long work hall with a teal canvas roof on log poles, open side, benches visible, 128 × 112.
4. **Review gate:** a light stone gatehouse with a portcullis, a small wooden "PR" plate and plum banners, 128 × 112.
5. **Inspector:** a turquoise pond with reeds and a round glass lens on a wooden stand, 112 × 96.
6. **Publisher:** a wooden catapult at a track's buffer stop, a bone skull on its front, a scroll in its bucket, drawn
   in the same three-quarter view with the track coming in straight from the left, 128 × 112.

**Sheet B2, the town and its work:** 7. **Town Hall:** a big long house with a carved totem and a plum banner, 128 ×
128. 8. **Review board:** an open ring of stones round one calm campfire, logs to sit on, 112 × 96. 9. **Research:** a
stone tower with a big open book on a lectern at its top, 96 × 128. 10. **Wiki:** a hut stacked with scrolls and
shelves, 96 × 96. 11. **Test bench:** a workshop with a small anvil and gears on a bench, 96 × 96. 12. **UX bench:** a
painter's hut with an easel and colour pots, 96 × 96.

**Sheet B3, the plumbing:** 13. **Router:** a wooden signpost with three arms on a small plinth, 64 × 80.
14. **Transformer:** a small water mill with a turning wheel, 96 × 96. 15. **Script:** a tinker's workbench with
cogs and a crank, 80 × 80. 16. **Drop file here:** a wooden chute into an open crate, 64 × 64. 17. **output:** a
covered storehouse with crates at the door, 96 × 80. 18. **Branches & PRs:** a smithy with a forge glowing teal, not
red, 96 × 96.

**Sheet B4, the others:** 19. **Metrics:** a carved stone with a chart scratched on it, 64 × 80. 20. **Calendar:** a
big drum on a frame with a sundial beside it, 80 × 80. 21. **File tree:** a small grove of three trees with labelled
stakes, 96 × 96. 22. **Audio briefing:** a small stage with a horn speaker made of bone, 80 × 80. 23. **Sound
alerts:** a horn on a post, 64 × 80. 24. **A building of one's own:** a plain empty hut with a blank sign, 80 × 80.

**Then, per building, the door states** (one sheet for the core six): the door closed; the door open with warm light
inside; the door open with the keeper half out (the keeper of §3b).

### 3b. The orks

1. **The body, in the new palette:** "The same small round orc as the attached frame, 32 × 32, facing the viewer.
   Row 1: idle, 4 frames. Row 2: walking down, 6 frames. Row 3: walking up, 6 frames. Row 4: walking right, 6 frames
   (left is mirrored). Row 5: working at a table, 6 frames. Row 6: stepping out of a door and turning to the viewer,
   4 frames. Arms and legs clearly swing in every walk."
2. **The roles:** "The same body, twelve times, only headgear, clothes and tool change, 32 × 32 each, one row:
   1. the Warchief: a horned helmet and a loosened necktie over a leather vest; 2. a Grunt: a bone-white hard hat and a
   muted brown work vest; 3. the Taskmaster (task board keeper): a quill behind the ear and a scroll; 4. the Seer
   (inspector): a hood and a staff with a glass charm; 5. the Lookout: a fur hat and a simple headset; 6. the Mechanic:
   a welder's cap and a wrench; 7. the Alchemist: a pointed cloth hat and a muted green flask; 8. the Treasurer: a
   wooden clipboard and a coin pouch; 9. the Warder: a round shield and a brass key; 10. the Pathfinder: a map and a
   lantern; 11. the Prospector (research): a miner's lamp and a pick; 12. the Loader (publisher): thick gloves and a
   rope coil. Each told apart by its silhouette at 32 px; the Treasurer and the Mechanic, the Loader and the
   Pathfinder must not look alike."
3. **The states:** "The worker orc, 32 × 32, five poses: working with a calm face; waiting with one hand raised and a
   curious face; slumped with a frown and a small grey smoke puff; sitting with arms crossed; dozing."
4. **The faces:** "The twelve roles' heads only, 16 × 16 and 24 × 24, facing the viewer, friendly, each with its
   headgear; for small icons in lists and tabs."
5. **Inside the building:** "The worker orc, 32 × 32, carrying a stone slab (6 frames walking right), holding a big
   magnifying glass up (4 frames), writing with a quill at a lectern (4 frames), pinning a parchment to a board
   (4 frames)."

### 3c. Carts and track

1. **Mine carts:** "Small wooden mine carts with iron bands, 32 × 24, three-quarter view. Row 1, the loads, oversized
   and high-contrast so they read from far away: empty; a big scroll with a large clear "</>"; a crate; a sealed
   letter with a teal seal; a thick book; three bundles. Row 2, a tall pole flag on the cart: none; a flag (to be
   recoloured by the product); an hourglass; four carts lined up at a buffer stop. Row 3: rolling right, 4 frames."
2. **The track:** "A wooden mine-cart track on few, light ties, 32 × 32 autotile set: straight both ways, four
   corners, T-junctions from above and below, a switch, a merge, a crossing, a buffer stop. It reads as a clear line
   on bright grass, not as a texture."
   **So that the tiles join** (V3, design-system-v3.md §8), add: "Every tile exactly the same square size, drawn on
   the same pixel grid; each tile shown alone with magenta round it, no border or frame. The rails and the earth bed
   cross the tile's edge at exactly the same place on every tile and stop flush with the edge. The ties are evenly
   spaced and the spacing divides the tile's width exactly: the first tie starts half a spacing in from the left edge
   and the last ends half a spacing before the right edge, so two tiles side by side continue the same rhythm. The
   rails sit in the middle of the tile, the same distance apart on every piece."

### 3d. Ground, edge and the biomes

1. **Ground (the forest biome, first):** "Seamless ground tiles, 32 × 32, tileable on every side, with no border:
   three tones of lively meadow grass (plain, tufts, a few small flowers in teal and white, never yellow or red);
   trodden earth in two tones; grass-to-earth edges and corners. Bright but in a middle value, low contrast inside the
   set."
2. **Decorations:** "Small decorations, 16 × 16 and 32 × 32: bushes, two kinds of trees, rocks, a stump, reeds, a log
   pile, mushrooms in teal and white. Bright, calm, nothing yellow or red."
3. **The edge:** "A low wooden palisade of rounded logs (not sharpened), 32-px pieces: straight, corners, and a gap
   where a track runs through."
4. **The other biomes** (later, one sheet each, the same three prompts with these words instead of "meadow grass"):
   ice — "packed snow and pale blue ice"; dirt — "warm sandy earth with dry grass"; dust — "pale desert sand and
   cracked clay"; meadow — "flower meadow, softer and lighter than the forest"; void — "deep indigo stone with faint
   teal glowing moss"; lava — "dark basalt with **teal** crystal veins" (**never** glowing red or orange: red is the
   error's colour).

### 3e. The interface

1. **The keeper's bubble and the scroll:** "Pixel UI pieces on magenta, crisp, 1-px dark outline: a white thought
   bubble as a nine-slice (four corners, four edges, a centre, a three-dot tail), 8-px grid; a small parchment scroll
   rolled at both ends as a nine-slice that stretches sideways and down; the same scroll larger, unrolled; a soft round
   selection ring on the ground, 3 sizes."
2. **Panels:** "Pixel UI panels as nine-slice pieces, 8-px grid: a cream parchment panel in a dark walnut frame with
   small teal corner studs; a dark terminal panel in the same walnut frame; tabs (active and inactive) to sit on a
   panel's top edge; a square action button 48 × 48 in a walnut frame in three states (normal, hover, pressed); a wide
   button; a toggle on and off; a small value box; an "Exit" button with an arrow."
3. **Icons for actions** (24 × 24, the same style, on magenta): new task, pause, run, run next, stop, stop all, open,
   settings, history, tokens, pass, send back, answer, add source, save, exit, search, filter.
4. **The signals** (the only sheet with yellow and red): "Pixel markers, 16 × 16 and 24 × 24, crisp, dark outline: a
   bright yellow speech bubble with "?"; a bright red badge with "!"; a cool grey-blue hourglass; a small bright red
   flame; a yellow cart flag; a red cart flag."
5. **The HUD bar:** "A thin top bar for a pixel game, 1440 × 40, walnut wood with a cream inlay, room for a title on the
   left and three small counters and a button on the right."
6. **The Task board's inside:** "The inside of a wooden hall from above, plank floor, beams, 480 × 360, empty; three
   tall wooden boards with carved blank headers, 96 × 200; parchment cards and light stone slabs as nine-slices that
   grow downward; a small cloth flag on a pin, lowered and raised; bone pins."

## 4. What comes back, and what happens to it

- The owner sends each result to the PM session (or drops it into `docs/design/img/references/v3/`); each round is
  reviewed in this doc as in [asset-prompts.md](asset-prompts.md).
- **The frame chosen** becomes design system v3's reference (§13, V3): its palette is measured into tokens, the
  scale into the grid, and only then I1 (the keeper, the scroll, quick actions, the terminal, the waybill) and I2
  (the Task board's inside) are built.
- The sheets are keyed and cut by the existing sprite pipeline ([design-system-v2.md](design-system-v2.md) §11).

## 5. Round 1: F1, the town — taken as v3's direction (2026-10-14)

[img/references/v3/f1-town.jpg](img/references/v3/f1-town.jpg) (and `-grey`). **The owner: "this is what it has to
be"**; the placing of the interface is still to be worked on.

**Holds:** bright, saturated and still a middle value; a game to open in the evening, not a dashboard; nine
buildings fit at the 1440-wide window; the track is the clearest line and the carts read from far away with their
loads (`</>`, crate, letter); the teal canvas and the plum banners carry the camp away from the strategy game's
colours; our round orks; the "PR" plate and `</>` as the developer's tells; one way in through the palisade on the
left; the HUD bar thin and plain.

**To fix in the next frames and sheets:**

1. **"Grom's camp" must never be used:** Grom is a named character of the big strategy game (Q18). The town's name
   in every frame is neutral ("My camp", the project's name).
2. **In grey the signals do not lead:** the yellow flag turns into a white flag and the ❓ is small, while the light
   stone gate, the tusk on the tower and the open book are the brightest things. Signals must win by **value**, not
   by hue alone: the product draws ❓, `!` and ⏳ as UI (layer 8) larger, on a dark plate with an outline; the cart's
   flag gets a dark outline and a chip. The gate's stone and the book a step darker.
3. **Spurs are dirt paths, not track:** the carts stay on one main line and stop opposite a door. **Proposed:** keep
   it — simpler to read and to build than a switch per building; the cart stops at the path, the keeper walks to it.
   (Owner to confirm.)
4. **The gate reads as a human castle** (crenellations): rougher, timber-and-stone, tusks or a bone arch, the
   portcullis kept.
5. **The palisade is sharpened and tall:** lower, rounded logs, as asked.
6. **Too many orks idle** (about twenty): in the product an ork is a session; a frame shows four to eight.
7. **The edges are busy** (crates, bushes in every corner): fewer, so the eye stays on the line.
8. The interface's placing: the owner's notes go into F2–F5.

**The owner, after the frame: the two buildings that face the world stand in the wall.** The lookout tower
(External listeners) is **built into the palisade**, the track's way in passing through a gate at its foot; the
catapult (Publisher) stands **against the palisade** at the line's end and throws over it. The camp's story
([camp-story.md](camp-story.md)) becomes the layout itself: work comes in at the tower, goes along the line, and
leaves over the wall. *Proposed rule:* whatever crosses the camp's border stands on the wall — the way in on one
side, the way out on the other; for now only these two. **F1b**, the frame redrawn with this, is the prompt below.

> "[head of §2] The same camp as the attached frame, the same style, palette and zoom, with these changes: the
> palisade runs along the top and is lower, of rounded logs. At its left end the wooden lookout tower with the bone
> horn is **part of the palisade**, its legs in the wall, and the mine-cart track comes in from outside through a
> wooden gate at the tower's foot. The track runs left to right through the camp. At its right end the catapult
> stands **against the palisade**, at a buffer stop, its arm pointing up and over the wall, a scroll flying away
> over the logs. Between them, along the track: the task board, the work hall with the teal canvas roof, the review
> gate (rougher, timber and stone with bone tusks, no crenellations, the portcullis and the "PR" plate kept). The
> lower row as before (pond with lens, book tower, workshop, long house). Six orks in all, one with a "?" over it.
> Fewer crates and bushes at the edges. The top bar says "My camp"."

**The owner: the spurs stay paths, and an ork waits for the cart at the stop.** Carts run on one main line and stop
opposite a building's path; **the building's keeper stands at the end of its path**, waiting for the cart, and can be
clicked on its own (its terminal, §13.1). Where the keeper stands says its state at a glance, with no badge:

| where the keeper is | what it means |
|---|---|
| at the stop, looking down the line | waiting for work (nothing for it yet) |
| taking the load off a stopped cart and carrying it inside | work arrived |
| inside (not seen on the town), its bubble over the roof | working |
| at its door with ❓ | asking the person |

**Orks still never push or ride carts:** the keeper only lifts the load off and carries it in, and puts the result
back on a cart at the stop. On the town, keepers wait only at buildings that take work from the line (Task board,
Agent pool, Review gate, Inspector); the lookout and the catapult work the wall. In F1b's prompt: "at the end of the
paths of the task board, the work hall and the gate, an orc stands by the track waiting, one of them lifting a
scroll off a stopped cart".

## 6. Round 2: F1b (2026-10-14)

[img/references/v3/f1b-town.jpg](img/references/v3/f1b-town.jpg). **The owner: the grass and the paths look duller
than F1.** Measured on the two images (the mean of the grass and of the paths' pixels):

| | F1 | F1b |
|---|---|---|
| grass | `#70ae43`, saturation 0.62, value 0.68 | `#679a54`, saturation 0.46, value 0.60 |
| paths | `#8f6144`, saturation 0.52 | `#926d50`, saturation 0.45 |

The image model drifted; the prompt did not ask for it. **F1's colours are v3's**: the palette becomes tokens
measured from F1, so the product's grass is ours, whatever a later frame drifts to. Every later prompt adds: "keep
exactly the colours of the attached frame F1: the grass as saturated and bright as in it (about #7cbd40), the paths
warm sand (about #e4b469)". (Corrected by V3, [design-system-v3.md](design-system-v3.md) §2.1: `#70ae43` was the mean
of every green pixel, bushes and shade included, and `#8f6144` the paths' rims and the track's ties; the open meadow
measures `#7cbd40` and the paths' sand `#e4b469`.)

## 7. Where the sheets go (V3)

Each sheet of §3 is saved into `docs/design/img/references/v3/` under its name in
[design-system-v3.md](design-system-v3.md) §8 (`b1-core.png`, `o1-body.png`, `c1-carts.png`, …), then
`python tools/camp_sheet.py --v3` cuts it. The art is shown at its own pixel (×1) and cut as drawn
(design-system-v3.md §3, §8): an ork about 64 px tall, a cart about 64 wide, a door state a patch about 64 × 80. The order of the next sheets is in §9 there.

**Holds in F1b:** the keeper at the stop works as a picture (an ork lifting the scroll off the cart at the gate);
the ❓ ork at the hall's door; nine orks instead of twenty; fewer crates.

**Not taken by the model:** the tower is not in the palisade, the catapult not against it, the gate still a castle,
the title still copied. **An image model redraws a picture, it does not move buildings in it** (as round 1 of
asset-prompts already found). So the layout is not iterated in whole frames any more: the sheets are generated one
building at a time, and the frame is put together from them on the grid — by hand, or by the V3 session's preview.

## 7. Round 3: sheets B1–B3, cut into the v3 preview (2026-10-14)

`img/references/v3/b1-core.jpg`, `b2-town.jpg`, `b3-plumbing.jpg`; cut by `tools/camp_sheet.py --v3` (18 sprites;
B2 and B3 each drew one extra piece — a stray stone, a second workbench — so their orders were moved, not the names).
The preview with them: [img/v3-preview/v3-town-round1.png](img/v3-preview/v3-town-round1.png).

**Taken:** the Task board, the Agent pool's teal hall, the **Review gate** (rough stone, bone tusks, plum banners,
the "PR" plate, no crenellations — the castle is gone), the Inspector's pond and lens, the Review board's fire ring,
the lookout's hide roof and horn. The art pixel is regular (about 4.2 image px), so the cut is clean.

**To redo:**

1. **The projection is mixed.** B1 is drawn front-on (the front wall parallel to the screen's bottom edge), as F1;
   **B2 and B3 are isometric** (buildings turned 45°): Town Hall, Research, Wiki, Test bench, UX bench, Router, Mill,
   Script, Drop file here, output, Branches & PRs. Side by side in the preview it is the first thing seen. Add to the
   head of every sheet: **"Every building faces the viewer: its front wall parallel to the bottom edge of the image,
   the door in the middle of the front, seen slightly from above, exactly like the task board in the attached
   sheet. Never turned at an angle, never isometric."** and attach `b1-core.jpg` beside F1.
2. **The catapult** is diagonal with its own diagonal rails: redrawn front-on, the track coming in straight from the
   left, against a low log wall.
3. **The lookout** is not yet in the wall: its legs in a low log wall with a gap at its foot.
4. **Research** is a crenellated tower again (a castle cue): a round timber-and-stone tower, no crenellations.
5. **The UX bench** has a yellow-orange banner: no yellow or orange, ever (signals).
6. **The ground is one flat colour** until g1 (grass tiles) comes; and the palisade is v2's until g3.
7. Sheets as **PNG** when the tool allows (a JPEG's noise blurs the key).

**The owner: "the images get strangely worse."** True, and it is the cutter, not the sheets:
[img/v3-preview/cut-loss-barracks.png](img/v3-preview/cut-loss-barracks.png) (left: the Agent pool as drawn, at its
own art pixel; right: the cut sprite). Three causes, in `tools/camp_sheet.py --v3`:

1. **Downscaled 1.5×:** the hall is drawn 193 art px wide and its slot is 128, so it is re-read at a coarser cell;
   barrels and crates turn to mush. **The generated art already comes at the screen's size** (193 art px ≈ the
   200–260 px a core building should take), so v3 shows it at **×1 per art pixel**, cut at its own pixel, never
   resampled; slots follow the art, not the other way round.
2. **Colours snapped to the tokens:** the teal roof's shaded half was mapped to the stone's grey, and the shading
   flattened. Building art keeps its own colours; the cutter only refuses yellow, orange and red (the signals).
3. **JPEG:** its noise blurs the key; PNG when the tool allows.

**And the sheet itself is soft** (the owner: "even the left one is smoothed"). True: the image model renders its
pixel art at a fractional scale (one art pixel ≈ 4.17 image px) and smooths it up, and the JPEG blurs again; inside
one art pixel the colour still varies (a median deviation of ~25 of 255). So the cutter **re-pixelises**: each art
pixel takes the median of its cell's inner pixels, then the sprite is reduced to its **own** 24 or so colours (not
the tokens), hard alpha, magenta fringe removed. A first try on the Agent pool:
[img/v3-preview/cut-clean-barracks.png](img/v3-preview/cut-clean-barracks.png) (left: the sheet as it is; right:
re-pixelised, crisp, every barrel and crate kept). Left to fix: the purple cast where the model blended magenta into
the floor's shade.

**Fixed (V3, after round 3):** the cutter no longer resamples or snaps colours: `tools/camp_sheets_v3.json` sets
`native` and `keep_colours`, the art is shown at ×1 (`art-scale` 1), slots follow what each sheet draws; it only reports
the signals' hues (round 3: the UX bench's banner). B1–B3 re-cut; before and after:
[img/v3-preview/agent-pool-before-after.png](img/v3-preview/agent-pool-before-after.png). The re-cut takes each art
pixel's median over its cell's inner pixels with a hard alpha (the re-pixelising above); reducing a sprite to its own
few colours and removing the magenta cast are not done yet.

## 8. The owner's answers to design-system-v3 §10 (2026-10-14)

1. **Nunito** for labels: yes.
2. **The catapult in side view** (the owner: it reads better). Taken: in profile its arm, bucket and throw are seen;
   the track comes in from the left into its side; one machine at the line's end, the one allowed exception to the
   single projection. So **the palisade runs down the right edge too**: the catapult stands against it and throws
   over it, up and to the right — work comes in through the tower in the left wall and leaves over the right one.
3. **A lane for each row of buildings.** Buildings face the viewer, so a row's doors open downwards: the top row's
   lane is the track's verge (short paths); each lower row has its own lane under its doors, joined to the main line
   by short paths between buildings, each joint a stop where the keeper meets the cart. **Carts run on the main line
   only;** lanes are for orks. More than ten buildings: another row, the same way.
4. **Office** goes a step larger as well.

The catapult's prompt, for B1's redo: "No shadows. A crude orc wooden catapult **in side view**, facing right, at a
log buffer stop where a mine-cart track ends coming in from the left, a cow skull on its frame, bone tusks on the
base, its arm and bucket with a scroll; four frames: resting; pulled back; mid-throw; the scroll flying up and to the
right. The same style and colours as the attached sheet, front wall of the frame parallel to the image's bottom
edge."

## 9. Round 4: o1 body, o2 roles, o3 states, B4 (2026-10-14)

Saved as references, **not cut** (named `-r1` so `camp_sheet.py --v3` does not pick them up):
`o1-body-r1.jpg`, `o2-roles-r1.jpg`, `o3-states-r1.jpg`, `b4-others-r1.jpg`.

**Taken:**

- **The ork of v3:** round, big head, olive skin, a leather apron, small tusks, a friendly resting face — the same
  character in o1 and o2, and our own.
- **The twelve roles read by silhouette** (o2): the Warchief's horned helmet and tie, the Grunt's hard hat, the
  Taskmaster's quill and scroll, the Seer's hood and staff, the Lookout's fur hat, the Mechanic's cap and wrench, the
  Alchemist's pointed hat and flask, the Treasurer's clipboard, the Warder's shield, the Pathfinder's map and lantern
  (row 2), the Prospector's miner's lamp and pick, the Loader's rope and gloves.
- **The door frames** (o1, last row): the ork stepping out of a door reads at once — the keeper of §13.1.
- **The states' poses and faces** (o3): working, asking with a hand up, stuck with a grey puff, arms crossed (held),
  dozing with "z z" — exactly the five states.

**To fix:**

1. **Frames round every cell** (o1, o2, o3): the model drew a box round each sprite; the boxes join the sprites, so
   the cutter cannot separate them (o2 read as 11 blobs). Add to the head of every ork sheet: **"No frames, no boxes,
   no grid lines, no borders between sprites; each sprite floats alone on the magenta."** (And the cutter learns to
   drop a drawn grid, if the model keeps drawing one.)
2. **o3 is drawn at twice the pixel size** (one art pixel ≈ 8.3 image px against o1's 5): a different, blockier
   character beside o1. Regenerate with **o1 attached**: "the same orc, the same pixel size and proportions as the
   attached sheet", keeping these five poses.
3. **o1's cap comes and goes:** bare-headed from the front, a cap from the back, the side and at work. One choice:
   **bare-headed** (the roles add the headgear). Walking down barely moves its legs, and its last two frames turn to
   three-quarter; walking up barely moves. Ask for "legs and arms clearly swinging, the same facing in every frame
   of a row".
4. **Signal colours in props:** the Warder's key is gold, the Prospector's lamp glows yellow, a pink smudge sits by
   the Taskmaster's quill: brass key, a teal-white lamp, no smudge.
5. **The Lookout and the Mechanic** both wear a cap: the Lookout keeps the fur hat and gets the headset that was
   asked; the Mechanic a welder's cap with goggles up.
6. **B4 is isometric again** (the drum, the grove on its own square of grass, the stage, the huts), with purple smoke
   blurred into two pieces, and the Script bench repeated from B3. Redo with the front-on line of §7 and
   `b1-core.jpg` attached; "no ground under the building, no smoke, no glow".

**The Task board must be asked at core size.** B1 drew it 88 × 72 beside a 192-px Agent pool; it is a core building
on the line. In B1's redo: "the task board as large as the work hall beside it, about 160–192 px wide: a broad notice
board under a shingle roof on two posts, big scrolls and stone slabs pinned to it, a door-sized gap below for its keeper".

**Done (V3, after round 3):** the cutter re-pixelises (median per art pixel, the magenta cast removed, each sprite in its own
24 colours; [img/v3-preview/agent-pool-repixelised.png](img/v3-preview/agent-pool-repixelised.png)); §8's answers are in
design-system-v3.md §4, §6, §10 and the preview (the catapult against the right wall, a lane per row, Office larger).


## 10. Round 5: c1 carts, c2 track, o5 inside (2026-10-14)

`c1-carts.jpg` and `c2-track.jpg` saved under their cut names; `o5-inside-r1.jpg` as a reference. (o1 came again,
the same image as `o1-body-r1.jpg`.)

**c1, the carts — taken.** Front-on, the loads oversized and readable from far away (`</>`, crate, a letter with a
teal seal, a book, bundles), the flag in teal and plum (the product recolours it for a signal), the hourglass, four
carts at a log buffer stop. The rolling row turns to three-quarter: the first frame is enough until the track
needs a rolling cart.

**c2, the track — taken.** Flat from above, dark iron rails on honey-wood ties, the ties evenly spaced, clean pixels:
straights, curves, both T-junctions, a switch, a merge, a crossing, a buffer stop. One extra piece (a vertical switch).

**o5, inside the building — not taken as drawn:** it is **another ork** — taller, in a cap, shirt and trousers,
brighter green — the ork of o3, not of o1/o2. The poses are right (carrying a slab, the magnifying glass, writing at
a lectern, pinning a sheet); the lens has a magenta cast; one frame of the pinning row stands idle.

**Two things learned:**

1. **Each sheet comes at its own pixel size:** an art pixel is 4.2 image px on the buildings, 5 on the orks, 6.2 on
   the track, 8.3 on the carts. Cut at its own pixel and shown at ×1, a cart would be ~36 px beside a 192-px hall.
   So each sheet is cut at its own pixel and shown at the **whole multiple** (×1, ×2) that brings it nearest its
   target size (cart ~64 px, ork ~48–64, track tile ~48–64); pixels of two sizes side by side are accepted.
2. **Two orks exist now:** the bald, round one of o1/o2 (the roles are drawn on it) and the capped, taller one of
   o3/o5. One must be chosen; the other sheets are regenerated with it attached.

**The owner's choices (2026-10-14):**

1. **The ork is o1/o2's:** bald, round, the leather apron; the roles add the headgear. o1 and o2 are renamed to their
   cut names and cut as they are (o1's walks and its cap that comes and goes are fixed by a later sheet). o3's five
   poses and o5's four actions are **regenerated on this ork**, with `o1-body.jpg` and `o2-roles.jpg` attached.
2. **The scale: ×1.5 by default on a screen of density 2 or more** (one art pixel = 3 × 3 device pixels, sharp), so
   the town fills the window as F1 does; **the mouse wheel zooms ×1 · ×1.5 · ×2**, each step whole in device pixels;
   on a screen of density 1 the default is ×1 (×1.5 cannot be sharp there).

**V3, round 5 cut:** c1, c2, o1 and o2 are cut (with `degrid`) and in the preview at the owner's ×1.5; each sheet's
pitch and whole multiple are in design-system-v3.md §3. **For c2's next round:** the set has **no north-west curve** (it
drew three south-east ones); ask "four curves, one for each pair of sides: north–east, east–south, south–west,
west–north", and the merge and the crossing apart, not touching.

