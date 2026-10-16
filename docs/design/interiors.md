# Design — entering a building: the room on the whole screen, its things are its data

Status: decided with the owner, 16 October 2026 (decisions §31). Builds on decisions §13.2 (the inside of a building,
the Task board first), js/inside.js (today's screen), first-mission.md §12 (the walk through each building).
An improvement of an existing mechanic (decisions §27).

## 1. The screen

- **Enter:** a click on a building (as today's second click, js/windows.js `openBuilding`) in Camp. The camp dims and
  the building appears **in the middle, roof off, as large as the screen allows**, whole device pixels, drawn on
  its own ground. Nothing else on the screen: no permanent settings panel (today's right-hand "shop" goes).
- **Settings behind a gear** in the room's top-right corner: a panel slides in (today's Info, js/console.js
  `InfoTab`, as it is), and out again. Money and safety stay in plain words, never drawn into the room (§13.2).
- **Exit** always in view, and Esc, back to the camp where it was.
- **Office** keeps its card: Office draws no rooms (a look changes drawing, never words).
- A building whose room is not drawn yet gets a plain room: its floor and walls in the kit, its things as cards.

## 2. The rule: a building's data are things in its room

What the building holds is drawn as objects in the room, and what the person can do is done on those objects. One
click on a thing opens what it is (a card, an ork's console, a waybill); no second list beside the room.

| building (type) | the things in its room | what the person does on them |
|---|---|---|
| **Task board** (`fields`) — built | the cards as sheets of parchment on the board, a to-do's checkbox as a flag | open, move, send a card |
| **Agent pool** (`barracks`, drawn as the depot) | a bay per run (🥩 n / 8): in each, its ork at a workbench with its cart, its task in a bubble; idle orks on a bench by the wall; an empty bay with a sign | a click on an ork opens its console; ❓ hangs over the ork who asks; the empty bay's sign is *Add ork* |
| **Review gate** (`loot_vault`) | the results waiting on a long table, each a crate or a scroll with its waybill tag; the barrier at the far door; the last passed on a shelf | a click on a result lays its waybill open: **Pass**, **Needs another round**, **Not this** (the words of decisions §24); passed, it rolls out through the far door |
| **External listeners** (`watchtower`) | the sources as horns and letterboxes on the wall; what came in as letters pinned up | a click on a letter opens what it became (a card on the Task board) |
| Wiki, Calendar, Metrics, the Publisher, the rest | a library's shelves, a wall calendar, a board of charts, crates by the catapult | after the testers |

## 3. Doors: who walks in, who works outside

Of the 26 building sprites, 13 have a doorway marked (manifest `doorway`, tools/doorways.py), 13 have none (the Task
board's booth, the catapult, the lookout, the horn and others). An ork stepping out of a building with no door looks
wrong. So:

- **A building with a doorway is entered:** its ork walks to the doorway, passes behind the jamb, and comes out the
  same way (js/camp/steward.js `OutOfDoor`, as today for those).
- **A building with none is open-air:** its ork works beside it on its stop's side (at the board, at the catapult)
  and never walks in or out. Spec 24.
- **New art keeps the rule** (the owner, same day): a building that orks enter has a **visible doorway an ork fits
  through**, not always in the same place (front, side, a ramp, a hatch), but **always marked at the cut**: its
  rectangle in the manifest's `doorway` (tools/doorways.py), so the ork walks to it, passes behind its jamb and comes
  out of it, wherever it is. A sheet whose doorway can't be marked is not cut. When a building is redrawn, its outside
  and its inside (roof off) are made **on one sheet**, so the two match; cut once from the source (CLAUDE.md "Art").

## 4. The order

Before the testers: the screen (spec 21); the Agent pool's and the Review gate's rooms (specs 22, 23; their art
first); doors (spec 24). If time allows, External listeners. The rest after the testers, in the order people reach
them. Mission 1's walk (spec 17b) opens these rooms.

## 5. The look of the new art: cute orkish steampunk (the owner, same day)

Every sheet made from now on keeps the camp's cartoon, cute orkish style (the same pixel size, outlines and warm
woods) and adds **steampunk**: brass and copper fittings, pipes and gauges, cogs, rivets, little boilers and
chimneys puffing steam, valves and levers, patched leather. Orkish first, steampunk as the trimming: crude, bolted on,
cheerful, never a clean Victorian machine. Yellow and red stay reserved for signals (brass leans to warm ochre, never
signal yellow). A **style frame** comes first (§6, card s1), approved by the owner; the rooms and every redrawn
building follow it.

## 6. Art cards (the owner generates; the PM session cuts)

**s1-steampunk (the style frame, first).** Attach `docs/design/img/references/v3/f1-town.jpg`,
`design-system/sprites/v3/buildings/depot.png`, `design-system/sprites/v3/buildings/loot_vault.png`.
> Pixel-art, the same cartoon style, pixel size, outlines and front-top view as the attached camp and buildings, made
> **orkish steampunk**: the same two buildings (the long engine shed and the gatehouse) redrawn with crude bolted-on
> brass and copper pipes, a small boiler with a chimney puffing steam, gauges, cogs, rivets, valves and levers,
> patched leather; still cute, chunky and cheerful, warm woods with brass and teal. Each building **with a clear
> doorway an ork could walk through** (the shed's on its front, the gatehouse's under its arch). Beside each, **the
> same building from inside with its roof removed** as a cutaway. On a flat magenta (#ff00ff) background, every piece
> fully inside its area, crisp dark 1-pixel outline, no text, no characters. No bright yellow, no red.

The two room cards below are made **after s1 is approved**, in its style.


If s1's insides are good enough they are cut directly; otherwise: Three candidates each, saved as `docs/design/img/references/v3/candidates/<sheet>/1.png … 3.png`.

**i-depot (the Agent pool, inside).** Attach `docs/design/img/references/v3/st-depot.jpg` and
`design-system/sprites/v3/buildings/depot.png`.
> Pixel-art, exactly the style (the approved steampunk frame s1), palette, pixel size and front-top view of the attached engine
> shed. The same shed
> seen **from inside with its roof removed**, as a cutaway: a long plank floor; along it six work bays, each with a
> workbench, a tool rack and a rail stop where a small cart stands; a long bench by the back wall; lanterns on posts;
> crates and barrels in the corners; brass pipes along the walls, a small boiler, gauges. **No characters.** One bay empty, with a small blank wooden sign on a post. On a
> flat magenta (#ff00ff) background, the room fully inside the frame, crisp dark 1-pixel outline, no text, no
> shadows outside the room. Warm woods and teal cloth; no bright yellow, no red.

**i-gate (the Review gate, inside).** Attach `docs/design/img/references/v3/st-gate.jpg` and
`design-system/sprites/v3/buildings/loot_vault.png`.
> Pixel-art, exactly the style (the approved steampunk frame s1), palette, pixel size and front-top view of the attached
> gatehouse. The same gatehouse
> seen **from inside with its roof removed**, as a cutaway: a stone floor; a long wooden inspection table across the
> room with three empty spots for crates; a wooden barrier arm at the far doorway, closed; a shelf on the side wall
> with a few small sealed crates; a stamp and an ink pot on the table; a lantern. **No characters, no crates on the
> table.** On a flat magenta (#ff00ff) background, the room fully inside the frame, crisp dark 1-pixel outline, no
> text, no shadows outside the room. Warm woods and grey stone with teal accents; no bright yellow, no red.

The crates, scrolls and orks on the table and in the bays are drawn by the code from today's sprites, so one room
serves any number of results and runs.
