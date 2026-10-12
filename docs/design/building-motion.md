# Design — buildings at work: the mill turns, the catapult throws

Status: design notes, written 2026-10-12; nothing is built yet. Builds on the painted headers (tools/painted.py,
building-sprites.md), the fire (yards.md §8) and the map view (map-view.md). Wording: ork, orkestration (CLAUDE.md).

| stage | what | state |
|---|---|---|
| 1 | four buildings move while their ork works: the mill's sails turn, the catapult throws, the forge sparks, the watchtower's lamp swings | |
| 2 | the catapult throws when a cart leaves it, not on a loop | |
| 3 | the rest of the catalog, one by one, as their sheets are painted | |

## 1. Why

A town where the mill turns and the catapult throws while the orks work is alive on its own: the picture that is
watched to the end and passed on. It also says, with no word, which buildings are at work right now.

## 2. Rules

- **Only what works moves.** A building moves while it is busy (js/fold.js `busy`) and stands still otherwise. In a
  quiet town nothing moves, so a motion means something, as fire does.
- **Short loops of four frames, in the headers' own painting**, stepped (`steps(4)`), never a smooth CSS tween of a
  sprite.
- **Never under `prefers-reduced-motion`, in quiet hours or with Do not disturb**, as the fire (js/hut.js `Flames`).
- **Office draws no sprite**: it keeps its spinner and its words.

## 3. Where the frames come from

Cutting the moving part out of a painted header by code was tried (the mill's sails, 2026-10-12): it works for the
mill alone, costs a tool per building and leaves seams. The frames are painted instead, as the headers were: an image
model paints a sheet of four frames of one building from its `header@2x.png`, and a tool cuts it into
`buildings/<type>/work.png` (and `@2x`, and each biome's), a strip of four frames of one size, the building standing
on the same spot in each. `js/icons.js` `HutSprite` plays the strip over its header while the building is busy.

The sheet's rules (the prompt asks them): four frames in one row, equal cells, a flat magenta ground (#FF00FF) that
the building never uses, the same building at the same size on the same ground line in every cell, only the moving
part changed; a part that moves past the header (a sail turned level) stays inside its cell.
