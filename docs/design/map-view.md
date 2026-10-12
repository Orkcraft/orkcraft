# Design — the map view: the town from above, buildings without their cards

Status: design notes, written 2026-10-12; stage 1 is implemented (`js/zoom.js`, `js/hut.js`, `js/town.js`,
`yards.css`). Builds on the folded cards ([folded-cards.md](folded-cards.md)), the yards and the bare buildings
([yards.md](yards.md) §3, §7) and the calm town ([calm-town.md](calm-town.md)). Wording: ork, orkestration (CLAUDE.md).

| stage | what | state |
|---|---|---|
| 1 | the map view: every building as its house, its plinth, its name and its mark; a peek on trouble and on a drag; `M`, a pinch, the bare town's menu | done |
| 2 | the mark floats up over the house when it changes, and settles; at most three in the air; a `mark(b)` for the types with none yet (Task board, Calendar, Wiki, File tree) | |
| 3 | a button for it in the HUD; `/map` in the Warchief's line; the phone keeps its own | |

## 1. Why

A person who runs orks mostly watches (calm-town.md). Folding (folded-cards.md) gave a quiet hut back its room, one
hut at a time, but a folded hut is still a strip of interface: a number, an icon, a name, a pin. A town of twelve
huts, half of them folded, still reads as a dashboard with houses drawn on it.

The map view is the town seen from above, as a strategy game's camera pulled back: the houses on their plinths, the
roads, the carts on them, the fire — and over a house only what changed. Nothing else asks to be read. It is also the
picture that says what Orkcraft is in half a second: the frame for a GIF, a screenshot, a first look.

## 2. A view of the town, not a state of each card

The person asked first for a third state of a card — open, folded, hidden to its sprite. It is a view of the whole
town instead:

- **One handle, not twelve.** A third state per card is a choice to make for every building and to remember after:
  which ones were hidden, and why that one is open. One view is one press, and the same press brings everything back
  as it was.
- **Nothing to keep.** The view changes no building: its fold, its size, its spot, its pin stay in the Town Scroll as
  the person left them. Leaving the map view shows each card exactly as before.
- **Fewer states to carry.** The peek, the drop target, the quick actions, the parts already have two states to
  serve (open, folded). A view draws every building in one way the town already knows — the bare building (yards.md
  §7) — and adds no third.

Two views, then: **Cards** (as now: each card open or folded, as the person set it) and **Map view**. Folding stays;
a per-card "sprite only" is not added.

## 3. What a building shows in the map view

```
          ┌──────┐
          │ house│      2/4 at work         ← its mark, in the air right of the house
      ▐▌  │      │  ▐▌                       ← a picket of its fence at each end, for a building that has a yard
      ═══════════════                        ← its plinth: roads meet it
       3 ⚒ Branches & PRs                    ← its number, icon and name over it (yards.md §3)
```

- **Its house, its plinth, its name, its mark** — as a bare building stands in Camp (yards.md §7), whatever its type.
  The Signpost and the Mill look the same in both views.
- **A picket at each end of its plinth** for a building that has a fenced yard in Cards: it says "this one has a
  view inside" without the fence around it.
- **Its mark** is what a folded card says first (folded-cards.md §1): `error`, `paused`, else its type's `mark(b)` —
  `2/4 at work`, `3 failing`, `N PRs`. It stands in the air right of the house. A building with nothing to say shows
  nothing.
- **The ork and the fire stay.** An ork that asks comes out with its `!` and the plinth glows; a building that broke
  burns (yards.md §8). Questions and breakage are what the map view is for.
- **The Town Hall stays as it is** in its corner: it is the way to the Warchief.
- **Office** draws no house (portrait.md §3). In the map view every Office card is folded to its title bar, with its
  mark; leaving the view brings back each one's own fold.

## 4. What stays the same

- **Where buildings stand.** A spot is a fraction of the room, never of a card's size (js/town.js `place`): the houses
  stand where their cards stood, the roads are planned again to their plinths. A town gets airier, never reshuffled —
  only a building that a taller card above it pushed down (js/town.js `settle`) stands at its own spot again.
- **A press selects, a second opens; a right click has the building's menu; a drag moves it** (its ghost the size of
  what is drawn); a road is pulled from its plinth.
- **The peek.** A building whose ork asks, whose worker failed or that is paused opens its card under its plinth, over
  its neighbours, never pushing them (folded-cards.md §2). So does a file or a link held over it: Drop file here takes
  a drop in the map view as in Cards.
- **Sizes and growth.** A card's size the person stretched is kept and not drawn; the town's growth of cards (yards.md
  §7) waits for Cards.

## 5. How the person gets there

- **`M`** toggles it, from anywhere but a field, a terminal or a dialog.
- **A pinch** on the town (Ctrl or ⌘ with the wheel, which a trackpad's pinch sends): out is the map view, in is Cards
  — the strategy game's camera.
- **The bare town's right click** has *Map view* (or *Leave the map view*), with `M` as its hint.
- The view is the person's on this machine (this browser's storage, as `orkcraft.grow`): the Town Scroll does not keep
  it and another person's town is not changed by it. A storage that cannot be read starts in Cards.

## 6. Later: the mark in the air (stage 2)

The mark says what changed, so it moves only when it changes:

- **A new mark floats up** from the roof and settles beside it in about a second, as an RTS's "+5" does. The same mark
  again draws nothing.
- **Priority:** fire, then a question, then an error mark, then any other. At most three float at once; the rest settle
  without floating.
- **Under `prefers-reduced-motion`, in quiet hours or with Do not disturb** nothing floats: the marks stand.

## 7. Later: a button and a command (stage 3)

- A button in the HUD, next to **Stop all**: *Map view* / *Cards*, so it is found without its key.
- `/map` and `/cards` in the Warchief's line.
- The phone app keeps its own layout (mobile.md): the map view is the desktop's.

## As built

- **Stage 1.** `js/zoom.js` keeps the view (`mapView`, `orkcraft.map` in localStorage) and its key `M`. `js/hut.js`
  draws a building in the map view as bare in Camp (`is-bare is-far`, plus `is-yard-far` for a type that has a
  fenced yard) and folded in Office; a peek opens its card under the plinth while it wants the person or a drag is
  held over it. `js/town.js` gives the bare town's menu its item, takes a pinch, and holds the cards' growth while the
  view is on. The word is `map_view` in `realm/lexicon.py`.
