# Design — yards and huts: an ork lives only where it thinks

Status: built 2026-10-08 (stages 1, 2, 2′; merged into `main` with PR #131; stage 3 not yet). Real screenshots go to a design,
product and marketing review first. Builds on [script-first.md](script-first.md) (the rule of which buildings
call a model), [folded-cards.md](folded-cards.md) (a card folded to its title bar) and the Camp look of
[gui-design-system.md](gui-design-system.md). GUI only: the TUI is deprecated
([calm-town.md](calm-town.md) §9).

| stage | what | state |
|---|---|---|
| 1 | a script-first building shows no ork on its card; the ork comes to it while it is woken or asked (§2) | built |
| 2 | the yard's card: a picket fence round its inside, the title bar a fence the building stands on, the name over it (§3) | built |
| 2′ | every building's orks seen from outside: Zz or a wheel over its roof, the ork out on its plinth under the mouse or to ask, its bubble's 👍, 👎 and AI tool (§4) | built |
| 3 | the ork that comes walks to the door and back (§3d) | |
| 4 | the fence on every card with a view, no card on a building with none, no ork room at a yard, the ork out on selection (§7) | built |

## 1. Why

Every card carries an ork's head in its title bar (`js/hut.js` `Keeper`). On a Router, a Sound alerts,
a File tree the head says nothing: [script-first.md](script-first.md) §3 already promises that such a
building never calls a model on its own. The head is on all 21 types, so it cannot answer the question
a person who runs agents asks first: **where does a model think, and what does it cost?**

The people Orkcraft is for (developers, indie studios, game designers) ask that of every agent tool.
An ork drawn only where a model works answers it at a glance, and says plainly what spends money
(CLAUDE.md, Wording: anything about money says plainly what happens).

The rule: **an ork lives in a building whose work is a model's. A building whose work is code is a
yard: no ork lives in it, one comes when it is woken or asked, and leaves when its job is done.**

## 2. Stage 1 — who lives where

### 2a. Huts and yards

- **A hut** is every building that is not script-first (`realm/script_first.py`
  `is_script_first(spec, b)` is false): Agent pool, Clan Fire, Wiki, Publisher, a script-first type with a
  thinking handler, a Transformer with an `agent:` step, External listeners, Task board, Town Hall.
  Its card is as today: the garrison's lead in the title bar.
- **A yard** is a building that is script-first now. Drop file here, Sound alerts, Router, File tree,
  Metrics, Calendar, Review gate, Branches & PRs, and a Transformer or a Script whose parts are code.
- The rule is `script_first`'s, never a list of its own: a Transformer that gains an `agent:` step
  becomes a hut on the next snapshot, and the person sees why (its steward's line, script-first.md §5).

### 2b. The ork that comes

A yard shows **no ork head** in its title bar while nothing calls its model. Its steward comes, and its
head stands in the title bar, while one of these holds:

| why | until |
|---|---|
| a wake is open: an error or a 👎 (script-first.md §4) | the proposal is applied or closed |
| the person asked it: keeper in plain words, Redesign, Watch, Ork setup | its job ends |
| it asks the person (`alert`) | the question is answered |

- In Camp it stands **on the building's plinth** (§3b, §4) while it works, the asking ork with its `!` while it
  asks. In Office its head's place in the title bar says **visiting** after the name (`Keeper` gets `visiting`).
- The rest of the time, where the head stood, nothing: the name gets the room.
- Info (the right panel) still shows the steward and its line (`js/steward.js`): who comes and what
  wakes it. Nothing about the steward is removed; only its head on the card.

### 2c. What does not change

- **Data.** The steward stays in the roster, the scroll and the snapshot; `orc` in the catalog and
  `garrison` in `gui/state.py` keep their names. A town scroll written before loads as it is.
- **Asking.** The right click's *Ask the Warchief about it*, the keeper on a selection in Lake, `@name`
  in the Warchief's line all work on a yard as on a hut: asking is what brings the ork.
- **Fire.** A yard whose ork asks burns as a hut does (gui-design-system.md: questions are fire).
- **Office.** The Office look draws no heads; it shows the same rule in words: `visiting` after the
  name while the ork is there.

### 2d. Code

- `gui/state.py`: each building says `yard: bool` (`script_first.is_script_first`) and `visit: str`
  (`"wake"`, `"asked"`, `"alert"` or `""`). The wake log (`script_first.wakes`) and the keeper's jobs
  (`gui/keeper.py`) already know both.
- `js/hut.js` `Keeper`: on a yard, nothing unless `b.visit`. Class `is-yard` on the hut.
- `realm/lexicon.py` `TERMS`: `yard` → "yard", `visiting` → "visiting".
- Tests: `tests/test_script_first.py` (yard and visit per type, a Transformer with an `agent:` step is no
  yard), `tests/test_gui_script_first_browser.py`: a Router's card has no `.gui-hut__keeper` until a wake.

## 3. Stage 2 — the yard's card: a fence and the building on it

Both keep their building's header sprite on the card's top edge. A yard is a fenced plot: **its card's
frame is a fence, its title bar is the top fence its building stands on, its name stands over the building
on the ground.** Camp only: a look changes how things are drawn, never a word ([portrait.md](portrait.md) §3).
Office draws a yard as any card: nothing of this stage is drawn there (`yards.css` is Camp's alone).

```
 4 ⑂ ROUTER                                ← its name over the building, on the ground, no plate
  [ sprite ] ork!                          ← the building, a fifth bigger; the ork that came by its door
 ▲═▲═▲═▲═▲═▲═▲═▲═▲═▲═▲═▲═▲═▲═▲═▲═▲═▲═▲   ← the top fence it stands on: pickets edge to edge
 ▴│ 12 sent · 0 dropped               │▴   ← the inside: the card's plain `panel`, never wood
 ▴│ last: release-notes → mill        │▴   ← each side: full pickets, tips up, a narrow rail down the middle
 ▲═▲═▲═▲═▲═▲═▲═▲═▲═▲═▲═▲═▲═▲═▲═▲═▲═▲═▲   ← pickets along the bottom
```

### 3a. The fence

- **Only the edges are wood.** A row of pickets along the bottom: dense and low (pointed, two thin rails
  between them, a 7×7 sprite tile, no ground line), each side a column of pickets as tall as the bottom
  ones, tips up, with a 2 px gap under each where the rail shows: one
  rail down the middle behind them, a quarter narrower than a picket's face (a 5×9 tile; the rail 7 CSS px); the inside is the plain `panel` it is today.
  Text never sits on wood (contrast stays 4.5:1).
- **Chunky pixels, few of them.** Sprite pixels are 3 CSS px (`image-rendering: pixelated`); a picket
  has an outline, a lit edge, a face and a shade, and nothing more. Detail is what makes a frame shout.
- **Dark, low-chroma wood** (darkened 2026-10-09, §7): outline `#0b0907`, shade `#1c1814`, wood `#262019`,
  lit edge `#302820`, highlight `#3a3026` — a step or two above the ground, never orange:
  five fences on a map must stay quieter than one fire, and gold and fire stay the brightest things on it. Ice and void get their own wood tints, as their stone panels do.
- **It tiles**: a card that is stretched (`hut_size`, building-views.md §1a) repeats its pickets at any
  level. The lower half of the picket row stands over the ground, not the panel, so it reads as a fence.
- **States ride on the fence.** Selected: the pickets lit `frame-focus`. Fire: the fence takes the
  `alert` frame and the halo, as a card does, and the flames stand on the roof.

### 3b. The top fence, the building on it, the name over it

- **The title bar is the top fence**, its height (`--titlebar`, 28 px) and nothing more: pickets from edge to
  edge. No gate and no posts: **the building is the gate.** Its sprite is a fifth bigger than a hut's (zoom 0.8
  against 2/3) and stands on the pickets.
- **The ork that came stands on the plinth**, left of the house, as on a hut (§4): while it works for a wake or a
  job, and with its `!` while it asks — a press on that one opens its question.
- **The name goes over the building**: number, type icon, name, on the ground with no plate — muted caps
  with a pixel outline, gold while selected, the fire's colour while it asks, cut short at 260 px. A press on
  the building or the fence opens it as the title bar did. Office keeps the name in the title bar.
- Pin and fold stay at the right end of the bar, on a small plate, shown on hover; the bar keeps 26 px
  clear at its right for the road handle, so neither is ever under it.
- The road handle on every card is a small gate (`tools/road_sprites.py`): two posts, a door of upright
  planks, a gold latch.
- Code: `js/hut.js` `YardName`, `js/visit.js` `Outside`; `yards.css`; the sprites by `tools/fence_sprites.py` into
  `design-system/sprites/fence/` (`post.png` is drawn but unused since the posts went).

### 3b′. A yard is sized by its pickets

- **A yard's card is stretched in whole pickets**: its width in steps of one bottom picket and its gap
  (21 px), its height in steps of one side picket and its gap (27 px). No picket is ever cut at a corner.
  The grips (`js/hut.js` `Grips`) round to the step while dragging.
- `hut_size` stays in pixels in the Town Scroll, a multiple of the step. A size saved before is rounded
  when drawn and never rewritten, so a town opens as it was.
- A card with no size of its own is rounded in width (its type's size class); its height follows its
  content, and the side pickets repeat with even gaps (`background-repeat: space`) so no seam shows.
- A hut is not stepped: its stone frame has no pattern to cut.

### 3c. Fold is the top fence alone

A folded card ([folded-cards.md](folded-cards.md)) is **its name, its building and the top fence alone**:
the rest gone. A peek (a question, an error, a drag) brings the fence back with the inside, over the
neighbours as a peek does now. Drop file here and Router are yards and are built folded; a Transformer
is built folded and is a yard while its steps are code.

### 3e. A look to try: the cards on the ground

The portrait's menu has **Card background**: *Panel* (the card's own, as always), *Shade* — a light dark veil
(black at 25 %) under the words, the biome showing through it while roads and decorations under a card dim — or
*Ground* — the cards drawn with no background, the town's biome bare; yards keep their fence, huts their frame, every title bar
its plate, a card that asks the fire's ground. It is this browser's alone (`localStorage`, `js/portrait.js`):
a look to try before it is decided, not a setting of the town.

Two rules make the cards' words safe on the ground itself:

- **Every biome is dark.** Its ground is darker than a card, and a card's words read on it: `ink` at 7:1 and
  `ink-muted` at 4.5:1 at least (`tests/test_biome_grounds.py`, against `js/icons.js` `BIOMES`). Tried on a light
  test ground (sand, `#cdbf97`): Panel reads, Shade loses the muted lines and the gold, Ground loses the words. A
  light biome may not be added.
- **No road runs under a card.** Today a road only avoids one: a step under a hut costs more (`js/roads.js`
  `WINDOW_COST`), so in a crowded town a road may still pass under a card. Before Ground is a choice for everyone,
  the router keeps out from under cards (a road with no way round waits for the person to move a building).

### 3f. The plinth, and where roads meet a building

- **Every building stands on a plinth** in Camp: a paved slab in the road's tan (`#8f8166`), a little wider than its
  sprite (`design-system/sprites/fence/plinth.png`, `tools/fence_sprites.py`). It is not the renown's footing: the
  footing's courses still tell the level on top of it (growth.md §5), the flag still flies.
- **Roads meet a hut at its plinth** (`js/hut.js` measure, `js/town.js` ports): the entrance is at the building, so
  roads keep over and beside the cards instead of running at them. **Roads meet a yard at its fence**: the fence is
  its boundary, the house is part of it. Office draws no plinth; its roads meet the card as before.
- **A yard's house stands at its card's left edge**, its plinth set into the line of the top fence; the top fence's
  pickets start where the house ends (`--house-w`, measured), and the sides start under the top fence, so nothing
  stands beside the house.
- **Card background defaults to Shade** (§3e): the biome under a light veil, the safe way for the words.

### 3g. A road out of the edge, a size from the corner

- **The road handle comes to the mouse.** Near a card's edge (12 px) — a yard's fence, a hut's frame — the small gate
  stands under the pointer, and a road is pulled out of it there (`js/hut.js` `edgeAt`); it never comes over a control
  (pin, fold, a button of the card), nor on the title bar, which moves the card (a yard's is its top fence). Where the road then runs is still the router's: the gate is only where it is
  grabbed. A built road leaves no gate: it keeps its arrow.
- **Only the corner resizes** (the bottom-right grip, its arrows): the edges are the roads'. The ghost of the new size
  turns red over another hut, as a drag's does, and a yard's size steps in whole pickets.
- **On a touch screen** there is no hover: the gate stands at the right edge of the selected card, as before.

### 3d. Stage 3 — motion

- The ork that comes walks in from the yard's edge to the door (its 16×15 sprite, 300 ms), and out when it
  leaves.
- None of it under `prefers-reduced-motion`; nothing of it in Office.

## 4. Stage 2′ — its orks, seen from outside

The ork's head in the title bar said little: it was on every card and nearly always said *idle*. In Camp it
leaves the title bar on every card, hut and yard; the building says what its orks do, as an RTS does.

- **Over its roof**, a hut that has orks says what they do: **Zz** while they sleep, a **wheel** while they work
  (the right half of the ork's state sprites, `orks/ork-idle.png`, `ork-busy.png`). A yard shows nothing: no ork
  lives in it.
- **Its ork comes out onto the plinth.** The plinth runs on 28 px left of the house (the house stands that much
  further right); that end is the ork's place, so it never stands on a fence or a card. The ork is its head alone, a third
  of its building's height. Under the mouse the ork
  walks out of the door (two steps facing left, `orks/ork-walk-a.png`, `ork-walk-b.png`), turns to you
  (`ork-stand.png`) and speaks in a pixel comic bubble (`icons/bubble.png`, a nine-slice, and its tail):
  - **👍 and 👎**, green pixel thumbs (`icons/thumb-up.png`, `thumb-down.png`). A hut's rate its lead ork's work
    (`ork.like`, `ork.dislike` with a note); a yard's rate the building (`building.like`, `building.dislike`: its
    steward wakes on a 👎);
  - **its AI tool** (a hut's, its harness scheme): pressed, the bubble lists the AI tools this machine runs and a
    press changes it from its next run (`ork.model`); a pipeline, or one tool and no other, opens the model dialog.
  The mouse gone, it waits 0.4 s and walks back in facing right. Touch is not drawn here: it gets its own interface.
- **The ork that asks comes out by itself** and waits on the same spot, pacing a step, a `!` in its bubble;
  **a press on it opens its question** (`js/orders.js` `openOrders(id)`); the building stays shut. An ork come to
  a yard for a wake stands there too while it is.
- Coins, not orks, go between buildings: the roads carry the work (§3f), an ork stays at its own door.
- Fire stays on the roof as before; the card burns as before.
- Under `prefers-reduced-motion`, nothing paces or floats. Office draws none of it: it keeps its words
  (`busy`, `?`, `visiting`) in the title bar.
- What the head told — its name, its AI tool — is in Info and in the caller's tooltip.
- Code: `js/hut.js` `Doing`, `js/visit.js` `Outside` and `VisitDialogs`; `yards.css`; `office.css` hides them;
  the sprites `tools/visit_sprites.py`.
- Later: a building's own "at work" (smoke, sparks) instead of the wheel.

## 5. What we measure

- **The screenshot.** The README's town (`docs/img/town.png`) before and after: can a person who never
  ran Orkcraft point at the buildings that spend money? Asked of five people.
- **Noise.** A town of 15 buildings: the eye goes to the cards that want it (fire, a peek) first.
  If the fences make it go elsewhere, stage 2 waits on a quieter fence, never on more decoration.
- **Spend.** No change: stage 1 is a picture of a rule that already holds.

## 6. Not doing

- Taking the steward out of a yard. It writes the yard's rules (building-views.md §2: no rule editors),
  and script-first.md made it cost nothing while it sleeps.
- A texture inside a card. (A fence on a hut is built since §7: the owner asked for it on every card with a view.)
- A word that differs between the looks: the Office says `visiting` and `yard` too.

## 7. Stage 4 — the fence on every card with a view; no card where there is none

Asked by the owner on 2026-10-09 after looking at a town: the fence is the frame of every card that **shows
something** (the Task board, the Calendar, the Wiki…), hut or yard alike, and a building that shows nothing of its
own needs no card at all.

- **A card with a view is fenced** (`js/hut.js` `fenced`, class `is-fenced`): §3a to §3c hold for it, hut or yard.
  Its name stands over the building; the title bar is the top fence. `is-yard` keeps its meaning (no ork lives
  there) and its width in pickets; the Town Hall keeps its frame.
- **A bare building has no card** (`js/hut.js` `bareOf`): its type's module says `export const bare = true`.
  Bare today: Signpost (Router), Mill (Transformer), Workshop (Script), Horn (Sound alerts), Watchtower
  (External listeners), Catapult, Pit (Drop file here). It stands as its house on its plinth, its name over it;
  a clear layer over both takes a press (open, move) as a title bar does, and roads meet the plinth. Its card is
  still drawn, hidden, so what it wires stays (the Pit's drop zone takes a file dropped on the building). Office
  draws its card as before.
- **A yard keeps no room for an ork**: the plinth is its house's alone (no 28 px run on the left). An ork that
  comes for a wake or to ask stands just left of it.
- **The ork comes out when its building is selected**, not under the mouse (§4 said hover): the mouse over a
  building brings out nothing, nor its quick actions (they are in its Info once it is open). The bubble's AI tool
  picker closes on a press anywhere else or on Escape, and the bubble goes when the building is no longer selected.
- **The bubble is rounder**: its corners step over four pixels (`tools/visit_sprites.py`), so its sides read round
  and stay pixel.
- **Cards on the ground by default** (§3e): Card background is *Ground* (the default) or *Panel*; *Shade* is gone, and
  a browser that kept it draws Ground.
- **A card takes the free room around it** — *off by default since 2026-10-09: it twice drew the town in a loop, and a
  layout that changes with the window costs the person where things are; a browser tries it with localStorage
  `orkcraft.grow` = `1`* (`js/town.js` `grow`): a card with a view and no size of its own grows right
  and down into free room, a road's gap from every other card and the town's edges, up to 560 × 440. Its height steps
  to a level of building-views.md §1a (240, 400) so the room it takes shows more; else it only widens. Cards are
  placed by their natural size, so growing never moves a neighbour; a size the person gives wins.
- **A bare building's plate**: what it says first (`js/hut.js` `Mark`: new mail, a failing source, a run that
  failed) stands on a small plate by its house, so a building with no card is still read at a glance.
- **Buildings drawn at 0.9 of their sprite** (a fenced or bare one; the Town Hall at 0.75).
