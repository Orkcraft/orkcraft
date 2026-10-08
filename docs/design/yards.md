# Design — yards and huts: an ork lives only where it thinks

Status: built on the branch `claude/great-cray-5i993w` 2026-10-08, not merged: real screenshots go to a design,
product and marketing review first. Builds on [script-first.md](script-first.md) (the rule of which buildings
call a model), [folded-cards.md](folded-cards.md) (a card folded to its title bar) and the Camp look of
[gui-design-system.md](gui-design-system.md). GUI only: the TUI is deprecated
([calm-town.md](calm-town.md) §9).

| stage | what | state |
|---|---|---|
| 1 | a script-first building shows no ork on its card; the ork comes to it while it is woken or asked (§2) | built |
| 2 | the yard's card: a picket fence round its inside, the title bar a fence the building stands on, the name over it (§3) | built |
| 2′ | every building's orks seen from outside: Zz or a wheel over its roof, the asking ork out by the door (§4) | built |
| 3 | the ork that comes walks to the door and back (§3d) | |

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

- In Camp it stands **by the building's door** (§3b, §4): its head while it works, the asking ork with its `!` while it
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
- **Muted bronze wood** (palette B on the design canvas): outline `#120d08`, shade `#2b2116`, wood `#3f3120`,
  lit edge `#54422a`, highlight `#665233` — a step above the ground and a step below the card, never orange:
  five fences on a map must stay quieter than one fire, and gold and fire stay the brightest things on it. Ice and void get their own wood tints, as their stone panels do.
- **It tiles**: a card that is stretched (`hut_size`, building-views.md §1a) repeats its pickets at any
  level. The lower half of the picket row stands over the ground, not the panel, so it reads as a fence.
- **States ride on the fence.** Selected: the pickets lit `frame-focus`. Fire: the fence takes the
  `alert` frame and the halo, as a card does, and the flames stand on the roof.

### 3b. The top fence, the building on it, the name over it

- **The title bar is the top fence**, its height (`--titlebar`, 28 px) and nothing more: pickets from edge to
  edge. No gate and no posts: **the building is the gate.** Its sprite is a fifth bigger than a hut's (zoom 0.8
  against 2/3) and stands on the pickets.
- **The ork that came stands by the door**, as on a hut (§4): its head while it works for a wake or a job, the
  asking ork with its `!` while it asks — a press on that one opens its question.
- **The name goes over the building**: number, type icon, name, on the ground with no plate — muted caps
  with a pixel outline, gold while selected, the fire's colour while it asks, cut short at 260 px. A press on
  the building or the fence opens it as the title bar did. Office keeps the name in the title bar.
- Pin and fold stay at the right end of the bar, on a small plate, shown on hover; the bar keeps 26 px
  clear at its right for the road handle, so neither is ever under it.
- The road handle on every card is a small gate (`tools/road_sprites.py`): two posts, a door of upright
  planks, a gold latch.
- Code: `js/hut.js` `YardName`, `Caller`, `Visitor`; `yards.css`; the sprites by `tools/fence_sprites.py` into
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

The portrait's menu has **Card background**: *Panel* (the card's own, as always) or *Ground* — the cards drawn
with no background, the town's biome showing through; yards keep their fence, huts their frame, every title bar
its plate, a card that asks the fire's ground. It is this browser's alone (`localStorage`, `js/portrait.js`):
a look to try before it is decided, not a setting of the town.

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
- **The ork that asks comes out**: by the door, at the sprite's right, its head and its `!` (`ork-waiting.png`),
  pacing a step to and fro; a yard's stands there too. **A press on it opens its question**
  (`js/orders.js` `openOrders(id)`); the building stays shut. The hit area is wider than the sprite and it stops
  under the mouse. Answers in the HUD stays the way to every question; this is the short way to one.
- Fire stays on the roof as before; the card burns as before.
- Under `prefers-reduced-motion`, nothing paces or floats. Office draws none of it: it keeps its words
  (`busy`, `?`, `visiting`) in the title bar.
- What the head told — its name, its AI tool — is in Info and in the caller's tooltip.
- Code: `js/hut.js` `Doing`, `Caller`, `Visitor`; `yards.css`; `office.css` hides them.
- Later: a running cycle for the caller, a building's own "at work" (smoke, sparks) instead of the wheel.

## 5. What we measure

- **The screenshot.** The README's town (`docs/img/town.png`) before and after: can a person who never
  ran Orkcraft point at the buildings that spend money? Asked of five people.
- **Noise.** A town of 15 buildings: the eye goes to the cards that want it (fire, a peek) first.
  If the fences make it go elsewhere, stage 2 waits on a quieter fence, never on more decoration.
- **Spend.** No change: stage 1 is a picture of a rule that already holds.

## 6. Not doing

- Taking the steward out of a yard. It writes the yard's rules (building-views.md §2: no rule editors),
  and script-first.md made it cost nothing while it sleeps.
- A fence on a hut, or a texture inside a card.
- A word that differs between the looks: the Office says `visiting` and `yard` too.
