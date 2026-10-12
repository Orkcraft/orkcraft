# Design — the zoom: the map, the overview, close up

Status: design notes, written 2026-10-12; stages 1 and 2 are implemented (`js/zoom.js`, `js/hut.js`, `js/town.js`,
`yards.css`, `layout.css`). Builds on the folded cards ([folded-cards.md](folded-cards.md)), the yards and the bare
buildings ([yards.md](yards.md) §3, §7), the card sizes of the UX bench ([improve-buildings.md](improve-buildings.md)
§6.3) and the calm town ([calm-town.md](calm-town.md)). Wording: ork, orkestration (CLAUDE.md).

| stage | what | state |
|---|---|---|
| 1 | the map view: every building as its house, its plinth and its name; a peek on trouble and on a drag; `M`, a pinch, the bare town's menu | done |
| 2 | three levels — the map, the overview, close up — by a pinch and ⌘+ / ⌘−; a building as wide at every level, only its height and its place down the town change; the huts glide | done |
| 3 | the mark floats up over a house when it changes, and settles; at most three in the air; a `mark(b)` for the types with none yet (Task board, Calendar, Wiki, File tree) | |
| 4 | a button for the zoom in the HUD; `/zoom` in the Warchief's line; the phone keeps its own | |

## 1. Why

A person who runs orks mostly watches (calm-town.md). A town of twelve cards reads as a dashboard with houses drawn on
it; most of them say the same thing all day. The zoom is the strategy game's camera: pulled back, the town is its
houses, its roads, its carts and its fire, and only what needs the person is said; brought close, the cards say what
each building is doing. It is also the picture that says what Orkcraft is in half a second.

## 2. Three levels of the whole town, not a state of each card

| level | a building with a card | a bare building (Router, Transformer…) | over a house |
|---|---|---|---|
| **a — the map** | its house, its plinth, its name; no fence | the same | only a question (its ork's `!`, the plinth's glow) and what broke (the fire, an `error` mark) |
| **b — the overview** (default) | its card in its yard, no taller than a small card (120 px) | its house and its mark, as yards.md §7 | its mark |
| **c — close up** | its card in its yard, no taller than a medium card (170 px), or the size the person stretched it to | its card in a small yard of its own | everything |

- **One handle, not twelve.** A level is the whole town's; it changes no building. Each building's fold, size, spot and
  pin stay in the Town Scroll as the person left them.
- **The person's choices hold.** A folded card stays its title bar at every level ("always small"). A card the person
  stretched shows that size close up only; at the overview it is a small card like the rest. Cards are stretched close
  up only (the grip shows there).
- **A card is as tall as what it says, up to its level's height.** A quiet card is shorter; a long one is cut at the
  level's height, so what a small card shows first is its type's to say — the Alchemist lays a card out at each size
  (improve-buildings.md §6.3).
- **The Town Hall** stands as it is in its corner at every level.
- **Office** draws no house (portrait.md §3): on the map every card is folded to its title bar; the overview and close
  up draw the cards at their heights.

## 3. Only down the town: widths never change

- **A building is as wide at the overview as close up**: its medium width (300 px, whole pickets in Camp), or wider as
  the person stretched it. Zooming between them, a card grows or shrinks down, never across, and the roads keep their
  runs across the town. On the map a house stands where its card's left side stood.
- **Down the town, a spot is deeper the closer the zoom** (js/town.js `DEPTH`: the map ½, the overview 1, close up
  1.4 of the room's height). Across, a spot is the same at every level. On the map the town is short and wide: long
  roads across it. Close up it is taller than the window and scrolls. A card that grew onto the one under it pushes it
  down (js/town.js `settle`), as it always did.
- **The huts glide** to their new places in a quarter of a second and the roads come in again; under
  `prefers-reduced-motion` they jump.

## 4. How the person zooms

- **A pinch** on the town (a trackpad sends it as Ctrl with the wheel): out a level, in a level; one level a gesture,
  so a long pinch never runs through all three. The plain wheel scrolls the town, as before.
- **⌘+ / ⌘−** (Ctrl on other systems) a level in or out, the page itself never zoomed; **⌘0** back to the overview.
- **`M`** the map and back to the level before it.
- **The bare town's right click** has *Zoom in*, *Zoom out* and *Map view*.
- The level is the person's on this machine (this browser's storage, `orkcraft.zoom`; the map view of before,
  `orkcraft.map`, is read once as the map). A storage that cannot be read starts at the overview.
- **Coming close to one building is choosing it**, never the zoom: a press selects it, a second opens it, and the
  camera brings it and the buildings on its roads into view (js/town.js `useCamera`).

## 5. What stays the same

- **Where buildings stand across**, their roads' runs, a press, a right click, a drag (its ghost the size of what is
  drawn), a road pulled from a plinth or a fence.
- **The peek.** On the map a building whose ork asks, whose worker failed or that is paused opens its card under its
  plinth, over its neighbours, never pushing them (folded-cards.md §2); so does a file or a link held over it, so Drop
  file here takes a drop on the map.
- **Growth of cards** into the room around them (yards.md §7) happens close up only.

## 6. Later: the mark in the air (stage 3)

The mark says what changed, so it moves only when it changes:

- **A new mark floats up** from the roof and settles beside it in about a second, as an RTS's "+5" does.
- **Priority:** fire, then a question, then an error mark, then any other. At most three float at once.
- **Under `prefers-reduced-motion`, in quiet hours or with Do not disturb** nothing floats.

## As built

- **Stage 1.** The map view, `M`, a pinch and the menu; a building on the map is bare in Camp (`is-bare is-far`) and
  folded in Office, and peeks.
- **Stage 2.** `js/zoom.js` keeps the level (`zoomLevel`: a, b, c) and its keys. `js/hut.js` draws a building at its
  level: on the map as before, its marks only an error's (`Mark` `quiet`); its card as wide as a medium one
  (`LEVEL_M.w`) and no taller than the level's height (`max-height`), the person's size close up only, the grip close
  up only; a bare building in a small yard close up (`roomy`). `js/town.js` makes a spot deeper or shallower by the
  level (`DEPTH` in `free()`), takes a pinch a level a gesture, gives the bare town's menu Zoom in and Zoom out, and
  marks the town `is-zoom-<level>` and, for a moment, `is-zooming` (layout.css: the huts glide).
