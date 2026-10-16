# Art run — every building in cute orkish steampunk: its outside, and its room's furniture (3 candidates each)

Branch `art/steampunk-all` · agy (pro) generates; the owner picks; the PM session cuts the picks once
(CLAUDE.md "Art") and marks each doorway · design: decisions §32–§33, interiors.md §1–§3, §5

## For every sheet below (the same rules)

**Attach:** `docs/design/img/references/v3/s1-steampunk.png` (the approved style), `docs/design/img/references/v3/f1-town.jpg`
(the camp), and the building's sprite today, `design-system/sprites/v3/buildings/<sprite>.png` (what it is, its
footprint and proportions).

**One sheet, two parts, on flat magenta (#ff00ff), each part fully inside its half, nothing touching the edges:**
- **Left: the outside**, in the camp's front-top view and pixel size, the same footprint and proportions as today's
  sprite (width and height within ±10 %). Cute, chunky orkish, with crude bolted-on steampunk: brass and copper
  pipes, a little boiler or chimney with steam, gauges, cogs, rivets, levers, patched leather; warm woods, brass,
  teal accents. **door:** a clear doorway an ork could walk through, visible from the front (anywhere: front, side, an
  arch, a ramp), dark inside. **open:** no doorway; the work happens in the open (a board, a yard, a machine).
- **Right: the room's furniture, as separate pieces** (not a whole room: rooms are built by the code from these
  pieces and the shared kit, sheet `a-room-kit`). 4–8 pieces for what that building's room holds (the last column),
  each **seen top-down as in an old JRPG's interior** (from above, a little of its front showing), each standing
  alone with clear magenta round it, sized to an ork (a bench seats two orks, a workbench is an ork's width).
  **No characters, no papers, no small items on tables.**
- Crisp dark 1-pixel outline, no text, no letters, no shadows outside the objects. **No bright yellow, no red**
  (brass is warm ochre). No characters anywhere.

**Output:** `docs/design/img/references/v3/candidates/<id>/1.png`, `2.png`, `3.png`, three different takes
(different shapes and steampunk pieces, the same style). Do not resize, crop, re-pixelate or recolour what you
generate.

## The sheets

**First, once: `a-room-kit`** (the shared pieces every room is built from; no "outside" part, the whole sheet is the
kit), all top-down as an old JRPG's interior, in s1's style:
- **floors**, each a seamless square tile: wooden planks, stone flags, packed earth, a metal grate;
- **the back wall** as a band, a tiling segment and its two ends: wooden, stone, and each with a brass pipe run and a
  gauge variant; **side and front rims** as thin tiling strips and corners;
- **floor markers** for where large things stand: a chalk square, a wooden pallet, a rail stop with a short rail,
  a painted circle;
- **lights and odds**: a lantern on a post, a wall lamp, a pipe with a valve, a small boiler, a crate stack, a barrel.


| id | building (what it does) | sprite today | door / open | the outside | the room's furniture (separate pieces; "lots" and "bays" mean their floor markers) |
|---|---|---|---|---|---|
| a-depot | Agent pool (orks run the work) | depot | door | a long engine shed with bays along its front | six large bays, each a rail stop and a workbench; a bench by the back wall |
| a-gate | Review gate (the person passes or sends back) | loot_vault | door | a gatehouse with a barrier arm across its arch; **draw it twice on the left, arm down and arm up** | three large lots for crates; the barrier at the far door; a big stamp on a post |
| a-taskboard | Task board (work waits as cards) | fields | open | a big notice board under a little roof, a siding beside it | the yard before the board: room for six large stone slabs |
| a-review-board | Review board (orks debate a result) | council | door | a round council hut with a chimney | a round floor, a ring of seats, the middle open |
| a-research | Research (orks read and dig) | mine | door | a mine entrance with a winch and a cart track | lots for carts of findings; a shaft at the back |
| a-transformer | Transformer (changes a thing's form) | mill | door | a mill with a steam-driven wheel | a big machine at the back; lots in and out |
| a-test-bench | Test bench (checks the work) | lab | door | a small lab shack with flasks and a gauge panel | test stands as large lots; a big lever panel |
| a-ux-bench | UX bench (checks how it looks) | ux_lab | door | a small studio shack with a big window and lenses | easels as large lots |
| a-branches | Branches & PRs (manual git) | forge | door | a forge with an anvil and bellows | anvils as lots; the forge at the back |
| a-external | External listeners (what comes in) | watchtower | open | a tall lookout tower with horns and a brass telescope | the tower's platform from above: large horns and letterboxes round its rim, the middle open |
| a-publisher | Publisher (sends results out) | catapult | open | a catapult with a boiler and a loading cradle | the loading ground: lots for crates waiting to be thrown |
| a-metrics | Metrics (the camp's figures) | crag | open | a rock with big brass gauges and dials on it | a yard before a wall of dials; lots for chart boards |
| a-inspector | Inspector (looks into a cart) | lake | open | an inspection pit or pool with a crane | the pit from above; lots round it |
| a-wiki | Wiki (the camp's knowledge) | scrolls | open | a reading stand with scroll racks under a canopy | shelves round the rim; lots for big books |
| a-router | Router (sends work down its way) | signpost | open | a signpost with switch levers and pipes | the junction from above: rails splitting, lots at each branch |
| a-calendar | Calendar (meetings and dates) | war_drum | open | a drum on a frame with a clockwork dial | a yard with a big dial set into the ground |
| a-drop | Drop file here (files come in) | pit | open | a chute or hopper over a pit | the pit from above; lots round its edge |
| a-script | Script (a fixed job, no model) | workshop | open | an open workshop with a clockwork machine | lots before the machine |
| a-file-tree | File tree (the project's files) | forest | open | a small grove with brass labels on the trees | clearings as lots between the trees |
| a-output | Output (a result lands) | loot | open | a loading dock with crates and a crane | the dock from above; lots for crates |
| a-audio | Audio briefing (listen to a summary) | gramophone | open | a big gramophone horn on a stand | a listening yard; lots round the horn |
| a-alerts | Sound alerts | horn | open | a single brass horn on a post | the post's ground; one lot |
| a-custom | a building of one's own | custom | door | a plain sturdy hut ready for any job, a few pipes | an empty floor with lots |

Not in this run: the Town Hall (no longer drawn in Camp), the old `barracks` sprite (the Agent pool is drawn as the
depot), orks, carts, ground and items.

## Order and commits

Work down the table in order. After **each** sheet: save its three files and commit (`art: <id>, 3 candidates`).
Push the branch after every five sheets and at the end (`git push -u origin art/steampunk-all`). If one sheet fails
twice, skip it, note it, and go on. At the end print a list: id → three paths, one line per candidate on how it
differs; and the sheets skipped.
