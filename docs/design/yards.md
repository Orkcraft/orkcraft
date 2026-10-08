# Design — yards and huts: an ork lives only where it thinks

Status: proposed 2026-10-08. Builds on [script-first.md](script-first.md) (the rule of which buildings
call a model), [folded-cards.md](folded-cards.md) (a card folded to its title bar) and the Camp look of
[gui-design-system.md](gui-design-system.md). GUI only: the TUI is deprecated
([calm-town.md](calm-town.md) §9).

| stage | what | state |
|---|---|---|
| 1 | a script-first building shows no ork on its card; the ork comes to it while it is woken or asked (§2) | |
| 2 | the yard's card: a picket fence round its inside, a gate round its title bar, the gate alone when folded (§3) | |
| 3 | the gate opens and shuts with a short move; the ork walks in through it (§3d) | |

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

- Its head is drawn as on a hut (`OrkHead`, the scheme, the flash when it asks), with the word
  **visiting** in its title (`Keeper` gets `visiting`), so the tooltip reads *Grot Pointa · visiting ·
  at work*.
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

## 3. Stage 2 — the yard's card: a fence and a gate

Both keep their building's header sprite on the card's top edge. A yard is a fenced plot: **its card's
frame is a fence, its title bar is the gate.** Camp only: a look changes how things are drawn, never a
word ([portrait.md](portrait.md) §3). Office draws a yard as any card: nothing of this stage is drawn there.

A first prototype (a stylesheet over the dashboard demo's real cards) is on the design canvas *Yards
and Huts*: the pickets and side beams as background tiles of the card, the gate's posts as the title bar's
pseudo-elements, its beam as a tile under the plate.

```
 ▲                                   ▲
 █┌─────────────────────────────────┐█   ← two posts, their tops above the bar
 █│ 3 ⑂ Router              📌  ▾   │█   ← the title bar: its dark plate, as on a hut
 █╞═════════════════════════════════╡█   ← the beam under it
 ▌│ 12 sent · 0 dropped             │▐   ← the inside: the card's plain `panel`, never wood
 ▌│ last: release-notes → mill      │▐   ← a beam down each side
 ▲═▲═▲═▲═▲═▲═▲═▲═▲═▲═▲═▲═▲═▲═▲═▲═▲═▲   ← pickets along the bottom
```

### 3a. The fence

- **Only the edges are wood.** A row of pickets along the bottom: dense and low (pointed, one rail between
  them, a 7×7 sprite tile, no ground line), a beam down each side (4 px wide); the inside is the plain `panel` it is today.
  Text never sits on wood (contrast stays 4.5:1).
- **Chunky pixels, few of them.** Sprite pixels are 3 CSS px (`image-rendering: pixelated`); a picket
  has an outline, a lit edge, a face and a shade, and nothing more. Detail is what makes a frame shout.
- **Muted wood**, near the frame's bronze, never orange: five fences on a map must stay quieter than
  one fire. Ice and void get their own wood tints, as their stone panels do.
- **It tiles**: a card that is stretched (`hut_size`, building-views.md §1a) repeats its pickets at any
  level. The lower half of the picket row stands over the ground, not the panel, so it reads as a fence.
- **States ride on the fence.** Selected: the pickets lit `frame-focus`. Fire: the fence takes the
  `alert` frame and the halo, as a card does, and the flames stand on the gate.

### 3b. The gate

- **The title bar keeps its dark plate** (`panel-raised`, as on a hut), and all its content on it:
  number, icon, name, the visiting ork, `?`, mark, pin, fold. The gate is drawn round it, never under it.
- **Two posts** stand at its ends, taller than the bar, their pointed tops above it: that is what makes
  it a gate. **A beam** runs under the bar (5 sprite px) and the side beams start from it.
- The road handle stays where it is, on the right post.
- The type's header sprite stays where it stands on a hut: on the top edge, between the posts. A yard
  is told by its fence and gate, never by losing its building.

### 3c. Fold is the gate alone

A folded card ([folded-cards.md](folded-cards.md)) is **the gate alone**: posts, plate and beam, the
fence gone. A peek (a question, an error, a drag) brings the fence back with the inside, over the
neighbours as a peek does now. Drop file here and Router are yards and are built folded; a Transformer
is built folded and is a yard while its steps are code.

### 3d. Stage 3 — motion

- The gate opens and shuts in 120 ms (two frames of the sprite) on unfold and on a peek.
- The visiting ork walks in through the gate (its 16×15 sprite, 300 ms) when it comes, and out when it
  leaves.
- None of it under `prefers-reduced-motion`; nothing of it in Office.

## 4. What we measure

- **The screenshot.** The README's town (`docs/img/town.png`) before and after: can a person who never
  ran Orkcraft point at the buildings that spend money? Asked of five people.
- **Noise.** A town of 15 buildings: the eye goes to the cards that want it (fire, a peek) first.
  If the fences make it go elsewhere, stage 2 waits on a quieter fence, never on more decoration.
- **Spend.** No change: stage 1 is a picture of a rule that already holds.

## 5. Not doing

- Taking the steward out of a yard. It writes the yard's rules (building-views.md §2: no rule editors),
  and script-first.md made it cost nothing while it sleeps.
- A fence on a hut, or a texture inside a card.
- A word that differs between the looks: the Office says `visiting` and `yard` too.
