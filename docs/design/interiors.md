# Design — entering a building: the room on the whole screen, its things are its data

Status: decided with the owner, 16 October 2026 (decisions §31–§33). Builds on decisions §13.2 (the inside of a building,
the Task board first), js/inside.js, first-mission.md §12 (the walk through each building).
An improvement of an existing mechanic (decisions §27).
Specs 21 (screen foundation, black stage) and 24 (doors: open-air buildings) merged to `main`.
Art frame s1 approved (`docs/design/img/references/v3/s1-steampunk.png`); all sheets follow docs/specs/art-steampunk-all.md.

## 1. The screen

- **Enter:** a click on a building (as today's second click, js/windows.js `openBuilding`) in Camp. The camp goes
  away entirely: **a black screen**, and on it the building **in the middle, roof off, as large as the screen
  allows**, whole device pixels, lit like a stage (a soft light on its floor, black round it). No camp behind it, so
  nothing distracts (the owner, 16 October). No permanent settings panel (today's right-hand "shop" goes; spec 21).
- **The view is top-down, as in the old JRPGs' interiors** (the owner, same day): the floor seen from above, the back
  (north) wall shown as a band with its face, the side and front walls as thin rims, furniture and props seen from
  above with a little of their front. Not a side view, not the camp's front-top angle. Every room, now and later.
- **Rooms are built, not drawn whole** (the owner, same day): the code lays a room from a shared kit (floor tiles,
  the back wall band, rims and corners, floor markers) and the building's own furniture pieces, all top-down; a
  generated whole room comes out too small and in side view. The kit and the pieces: docs/specs/art-steampunk-all.md.
- **Settings behind a gear** in the room's top-right corner: a panel slides in (today's Info, js/console.js
  `InfoTab`, as it is), and out again. Money and safety stay in plain words, never drawn into the room (§13.2).
- **Exit** always in view, and Esc, back to the camp where it was (restoring previous pan and zoom).
- **Office** keeps its card: Office draws no rooms (a look changes drawing, never words).
- A building whose furniture is not drawn yet gets a plain room: its floor and walls in the kit, its things as cards (spec 21).

## 2. The rule: a building's data are things in its room

**Big things, not papers on a table** (the owner, same day). A room is large and what it holds must read at a glance,
so the work is drawn as **few, large props on the floor**, never small items on furniture:
- **Size:** a work item is at least about a sixth of the room's width; its title readable at the default size (the
  kit's label size or larger). At most six to eight items show; more stand as a pile with `+N`.
- **Shape by meaning:**
  - A task is a **stone slab** or a **long plank** on the floor with its title carved or painted on it.
  - A result to judge is a **large crate** as tall as an ork with a **speech bubble** over it holding its title and state.
  - A source or listener is a **tall brass horn** or a **letterbox** as tall as an ork.
  - A code branch or PR is an **iron ingot or glowing blade** resting on a heavy anvil.
  - A metric or chart is a **large blackboard or brass dial board** set upright on a floor lot.
  - A document or guide is a **giant open tome** on a heavy wooden lectern.
  - An audio note or briefing is a **wax cylinder** sitting in a brass cradle.
  The prop says *what* it is, the bubble or the carving says *which*.
- **Lots, not tables:** the floor has marked places (chalk squares, pallets, rail stops, painted circles) where the
  props stand; the furniture is scenery round the edge.
- **Detail on a click:** the prop shows its title and its one state (❓, 🔥, done); everything else opens on a click
  (the card, the waybill, the ork's console, the markdown viewer).
- Orks are drawn at the room's scale, as large as the props.

What the building holds is drawn as objects in the room, and what the person can do is done on those objects. One
click on a thing opens what it is (a card, an ork's console, a waybill); no second list beside the room.

### All 23 buildings: rooms, things, and actions

| building (type) | door / open | floor & wall (kit) | floor lots & scenery | the things in its room | what the person does on them |
|---|---|---|---|---|---|
| **Task board** (`fields`) | open | wooden planks, wood wall | yard before board; 6 slab lots | cards as large slabs or planks; to-do checkbox as a flag | open, move, send a card |
| **Agent pool** (`barracks`, drawn as depot) | door | wooden planks, stone wall | 6 rail stops with workbenches; bench by back wall | ork with cart in each busy bay; bubble over cart; idle orks on bench; empty bay with sign | click opens ork's console; ❓ over asking ork; empty bay's sign is *Add ork* |
| **Review gate** (`loot_vault`) | door | stone flags, stone wall | 3 crate pallets; barrier arm at far door; stamp on post | results waiting on lots (crates + bubbles); last passed stacked by exit | click opens waybill: **Pass**, **Needs another round**, **Not this**; rolls out through far door |
| **External listeners** (`watchtower`) | open | wooden planks, low rail rim | platform rim; 4 horn/letterbox lots; telescope | sources as tall horns and letterboxes; incoming letters/slabs on floor | click on letter/horn opens what came in or the generated card on Task board |
| **Review board** (`council`) | door | stone flags, wood wall | round floor; ring of seats; open centre | debating orks on seats; subject of debate displayed on stone in centre | click opens debate transcript, vote, or ork consensus |
| **Research** (`mine`) | door | packed earth, stone wall | cart tracks from mine shaft; 4 cart lots | carts of findings, scrolls, reference docs from the deep shaft | click opens finding note or assigns a new research dig |
| **Transformer** (`mill`) | door | wooden planks, stone wall | steam wheel at back; input lot (left), output lot (right) | input crate/text on left lot; transformed output on right lot; machine status | click inspects before/after transformation or reconfigures recipe |
| **Test bench** (`lab`) | door | metal grate, stone wall | test stands; big lever & gauge panel | test suites as test stands with pass/fail gauges; broken test sparks 🔥 | click opens test report, logs, or triggers test run |
| **UX bench** (`ux_lab`) | door | wooden planks, wood wall | studio window; 4 easel lots | visual drafts and screenshots mounted on easels side by side | click opens full screenshot, before/after diff, approves look |
| **Branches & PRs** (`forge`) | door | stone flags, stone wall | roaring forge at back; 4 anvil lots | active branches / PRs as glowing metal ingots on anvils | click opens git diff, merges PR, or rebases branch |
| **Publisher** (`catapult`) | open | packed earth, stone wall | catapult cradle; 3 crate lots on loading ground | releases and packaged builds on crates waiting to be flung | click triggers launch/publish, opens release notes |
| **Metrics** (`crag`) | open | stone flags, rock wall | wall of brass dials; 4 chart board lots | token spend, speed, acceptance rate on large chalkboard slates | click drills into period stats, tokens, charts |
| **Inspector** (`lake`) | open | stone flags, rim railing | crane over deep inspection pit; 4 lots round rim | cart suspended over pit; payload broken down on stone slabs | click inspects raw payload, trace events, JSON viewer |
| **Wiki** (`scrolls`) | open | wooden planks, wood wall | scroll racks round rim; 4 lectern lots | knowledge base topics as giant open tomes on heavy wooden lecterns | click opens markdown document reader / editor |
| **Router** (`signpost`) | open | packed earth, low rim | track junction; switch levers; 4 track lots | task queue at each rail branch; switch state indicator | click re-routes task flow or configures route filter |
| **Calendar** (`war_drum`) | open | packed earth, stone wall | drum frame; clockwork ground dial; 4 calendar lots | scheduled cron automations, quiet hours, milestones on dial lots | click sets schedule, toggles quiet hours, adds event |
| **Drop file here** (`pit`) | open | metal grate, stone wall | chute over pit; lots round hopper rim | recently ingested files / payloads waiting to be dispatched | click inspects file content or routes it to a building |
| **Script** (`workshop`) | open | wooden planks, wood wall | clockwork machine; workbench; 3 lots before machine | deterministic recipes / scripts as punch-cards or gear sets | click edits script code or runs job manually |
| **File tree** (`forest`) | open | packed earth, grove rim | brass labels on trees; 4 clearing lots | file directory clusters shown as clearings between labelled trees | click browses files in folder, views file code |
| **Output** (`loot`) | open | wooden planks, low rim | dock crane; loading dock; 4 pallet lots | finished deliverables, exported assets, packages on pallets | click downloads or opens final product deliverable |
| **Audio briefing** (`gramophone`) | open | wooden planks, wood wall | giant brass horn on stand; 3 cylinder lots | audio summaries and podcasts as wax cylinders in brass holders | click plays audio playback or shows text transcript |
| **Sound alerts** (`horn`) | open | packed earth, post rim | brass horn on tall post; slate lot at base | alert sounds and notification rules carved on slate | click previews chime sounds, configures notification thresholds |
| **Custom building** (`custom`) | door | wooden planks, wood wall | sturdy open room; 4 general lots; tool rack | user-defined agent or integration props | click opens custom extension config or agent console |

## 3. Doors: who walks in, who works outside

Of the 26 building sprites, 13 have a doorway marked (manifest `doorway`, tools/doorways.py), 13 have none (the Task
board's booth, the catapult, the lookout, the horn and others). An ork stepping out of a building with no door looks
wrong. So:

- **A building with a doorway is entered:** its ork walks to the doorway, passes behind the jamb, and comes out the
  same way (js/camp/steward.js `OutOfDoor`, as today for those).
- **A building with none is open-air:** its ork works beside it on its stop's side (at the board, at the catapult)
  and never walks in or out. Spec 24 (merged).
- **New art keeps the rule** (the owner, 16 October): a building that orks enter has a **visible doorway an ork fits
  through**, not always in the same place (front, side, a ramp, a hatch), but **always marked at the cut**: its
  rectangle in the manifest's `doorway` (tools/doorways.py), so the ork walks to it, passes behind its jamb and comes
  out of it, wherever it is. A sheet whose doorway can't be marked is not cut. When a building is redrawn, its outside
  and its inside (furniture pieces) are made **on one sheet**, so the two match; cut once from the source (CLAUDE.md "Art").

## 4. The room construction kit: code & art

Rooms are assembled dynamically in code (`InsideStage`, `RoomLayout`) rather than baked into static single-image rooms.
This ensures crisp pixel-art, scale flexibility across screen sizes, and room for big props.

### The shared kit (`a-room-kit`)
From `docs/specs/art-steampunk-all.md`, drawn top-down in s1's cute orkish steampunk style:
1. **Floors (seamless square tiles):**
   - Wooden planks (warm timber, nails, slight grain).
   - Stone flags (weathered grey stone blocks).
   - Packed earth (trodden dirt with small pebbles).
   - Metal grate (industrial iron/copper mesh over dark ground).
2. **Back wall band (north wall face):**
   - Wooden horizontal planks, stone brickwork, and variants with brass pipe runs and pressure gauges.
   - West and east end caps.
3. **Wall rims & corners:**
   - Thin 1–2 pixel dark wooden/stone borders for west, east, and south edges to define the room bounds against the black screen.
4. **Floor markers (lots):**
   - Chalk square (for slabs, tomes, easels).
   - Wooden pallet (for crates, barrels, heavy machinery).
   - Rail stop with short rail segment (for orks with carts).
   - Painted circle (for debate spots, dials, horns).
5. **Lighting & props (scenery):**
   - Lantern on a post, hanging brass wall lamp.
   - Small boiler puffing steam, copper pipes with valves.
   - Stacked crates, wooden barrels, tool racks.

### Dynamic layout & data binding
1. **Stage viewport:** The room is sized to fit the available viewport (maintaining whole device pixels, `dpr`).
   A soft radial vignette illuminates the floor while the surround remains jet black (#000000).
2. **Perimeter furniture:** Placed along the north wall band and corners from the building's own sprite sheet.
3. **Data lots grid:** The floor space is divided into marked lots (at least 1/6th of room width each). Up to 6–8
   active items are rendered directly on their markers. If more items exist, the last lot renders a `+N` stack.
4. **Interactive props:** Each item renders its custom SVG/sprite prop (slab, crate, anvil, easel) with readable text
   and state indicator (❓, 🔥, ✓). A click invokes the corresponding handler (open waybill, open console, edit card).

## 5. The look of the new art: cute orkish steampunk

Every sheet made keeps the camp's cartoon, cute orkish style (the same pixel size, outlines and warm
woods) and adds **steampunk**: brass and copper fittings, pipes and gauges, cogs, rivets, little boilers and
chimneys puffing steam, valves and levers, patched leather.

- **Orkish first, steampunk as trimming:** crude, bolted on, cheerful, never a cold Victorian engine.
- **Signals reserved:** pure yellow and pure red remain strictly reserved for signals (❓, 🔥, !). Brass leans to warm ochre, never signal yellow.
- **Approved style frame:** `docs/design/img/references/v3/s1-steampunk.png` (s1 candidate 1, approved 16 October). Every sheet attaches it.

## 6. Implementation roadmap & specs

1. **Screen foundation (Spec 21) — MERGED:**
   Full-screen black stage, centred room, gear slides settings panel in/out, Esc/Exit returns to camp with view preserved, plain room fallback.
2. **Doors & open-air stewards (Spec 24) — MERGED:**
   Buildings with doorways step out; open-air buildings show their steward beside the building at its foot without exit door.
3. **Art generation (`art-steampunk-all.md`) — IN PROGRESS:**
   Owner runs agy pro on `a-room-kit` and the five buildings of decisions §35 (3 candidates each); the other sheets Later. PM session cuts chosen candidates and records doorways.
4. **Room layout engine (Spec 25):**
   The Preact component that tiles the `a-room-kit` floor and wall band, places perimeter furniture, and provides the lot grid for props.
5. **Mission 1 core rooms:**
   - **Agent pool room (Spec 22):** 6 bays with rail stops, busy orks with carts, idle bench, *Add ork* sign.
   - **Review gate room (Spec 23):** 3 crate lots, barrier arm at exit, waybill overlay (Pass, Needs another round, Not this).
   - **Task board room:** finished; cards scaled to large slabs on chalk lots.
6. **Remaining rooms:** rolled out in order of player progression (External listeners, Forge/PRs, Wiki, Metrics).
