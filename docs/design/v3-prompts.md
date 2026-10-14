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
