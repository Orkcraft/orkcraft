# Design — buildings at work: the mill turns, the catapult throws

Status: design notes, written 2026-10-12; stage 0 is built. Builds on the painted headers (tools/painted.py,
building-sprites.md), the fire (yards.md §8) and the map view (map-view.md). Wording: ork, orkestration (CLAUDE.md).

| stage | what | state |
|---|---|---|
| 0 | the Alchemist paints a moving house's two layers (the house without its moving part, the part alone) from the house and a brief, and previews them moving | done |
| 1 | the town plays them while the building is busy: the mill's sails turn, the catapult's arm swings | |
| 2 | the catapult throws when a cart leaves it, a gold stone flying along the road; sparks over the forge and the watchtower's lamp, drawn in code | |
| 3 | the rest of the catalog, one by one, as their layers are painted; each biome's colours | |

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

## 3. The model paints, the code moves

Cutting the moving part out of a painted header by code was tried (the mill's sails, 2026-10-12): it works for the
mill alone and costs a tool per building. Asking an image model for four frames of a building was tried too (Gemini,
the mill and the catapult): the building changed between frames, frames repeated, the arm swung the wrong way. A model
paints well and moves badly; code moves exactly.

So a moving house is **two layers** the model paints from the house as it is, on its own canvas: the house without
the part that moves (`work-still.png`) and the part alone (`work-part.png`). The code turns or swings the part around
its pivot (realm/motion.py `MOTIONS`: the move, the pivot as shares of the house, the degrees, the steps), so the
house cannot jump between frames.

- **The Alchemist paints them** (the UX bench, docs/design/improve-buildings.md §6): its window has an *At work*
  section for a type that moves — the two layers, each opened in the paint dialog with its brief written in, and a
  preview of the two moving. A layer is a draft until Apply puts it in this machine's pictures; the town ships none yet.
- **The prompt** is `design/prompts/motion.md`: the house's style, and "what you keep at exactly the same scale and in
  exactly the same position". The brief (what to remove, what to keep) is the type's in `MOTIONS`, and the person may
  change it before painting.
- **A type moves** once it has a brief in `MOTIONS`: the mill (`turn`, 90° of symmetry, four steps) and the catapult
  (`swing`, 70° and back).

## As built

- **Stage 0.** `realm/motion.py` (the briefs, the moves, the layers' paths), `design/prompts/motion.md`,
  `realm/painter.py` (`kind_of` → `motion`), `core/workers/ux_lab.py` (a layer not painted yet is painted from the
  house), `gui/views/ux_lab.py` (`motion` in its detail), `js/buildings/ux_lab.js` (`Motion`), `layout.css`
  (`.gui-work`, the preview the town will use).
