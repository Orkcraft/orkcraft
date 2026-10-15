# Spec 14 — the modular depot (an ork in every bay), the small campfire, the small barrier

Branch `spec/14-modular-depot` · model **flash** · design: process-lines.md §2–§5; design-system-v3.md §4d (the depot)

## Part A — art (the owner generates in the Gemini app or agy; no API)
Attach: `design-system/sprites/v3/buildings/depot.png` (the depot today), `docs/design/img/references/v3/f1-town.jpg`.
Three prompts, 3 candidates each, saved in `docs/design/img/references/v3/candidates/<sheet>/1.png … 3.png`:

**d2-depot-parts**
> Pixel-art sprite sheet, exactly the style, palette, pixel size and front view of the attached engine shed. On flat
> magenta (#ff00ff), separate pieces that tile side by side into a shed of any length: (1) the left end with its
> open west gateway and a pitched roof end; (2) one middle bay segment: a stretch of pitched roof with a vent, one
> open arched bay in the front wall, dark inside, the same width as one bay of the attached shed; (3) the same bay
> segment with its wooden shutters closed; (4) the right end with its open east gateway. The rails run along the
> floor through every piece at the same height so pieces join seamlessly. No ork, no cart, no text; crisp dark outline.

**d3-bay-ork** (an ork seen working inside a bay)
> Pixel-art, same style and ork as the attached camp: four small frames of a capped ork in a leather apron seen
> from the front through a dark arched opening, working at a mine cart: hammering, reading a scroll, typing at a
> small lectern, wiping its brow. Each frame fits inside one bay opening of the attached shed. Flat magenta
> background, no text.

**a2-small-pieces**
> Pixel-art, same style as the attached frame, on flat magenta, three separate small pieces: (1) a small campfire
> ring of four logs and stones with a low fire, unlit and lit versions (two pieces), about a third of a building's
> width; (2) a small boom barrier across one rail track, down and up versions (two pieces), the same style as a
> railway crossing barrier, wooden post with a striped boom in muted colours (no yellow, no red). Crisp outline, no text.

Push the candidates on the branch; the PM session picks and cuts them (`tools/camp_sheet.py`) into
`design-system/sprites/v3/depot/{end-w,bay,bay-shut,end-e}.png`, `depot/bay-ork-1..4.png`,
`annex/council-unlit|lit.png`, `track/barrier-down|up.png`.

## Part B — code (agy, after the PM session has cut the sprites)
1. **The depot is composed of parts** in `js/camp/layout.js` / `town.js`: west end + N bay segments + east end,
   N = the pool's `max_orcs` (1 to 8; the one-bay size is N = 1, process-lines.md §2). It counts as
   `ceil((N + 1) / 2)` places in its row. A line too short for N bays shows as many as fit and a `+N` chip.
2. **An ork in every busy bay:** a bay whose Grunt works shows `depot/bay-ork-<k>.png` (k cycles every few seconds,
   whole frames, no fractional motion) with that Grunt's bubble above the roof; a free bay shows `bay-shut`; a cart
   for that bay stands in its opening. Hover a bay: that ork's name and task; click: its console (as clicking an ork
   does today).
3. **The small campfire** (`annex/council-*`) and **the small barrier** (`track/barrier-*`) are drawn by the layout
   when a station has `debate: true` / `approve: true` in its config (spec 15 sets these); lit while a debate runs;
   the barrier down while a cart waits for the person, with the cart's yellow flag (the only yellow).
4. Office unchanged.

## Tests
Critical tests, plus `tests/test_camp_layout.py` (depot width by N; places counted; the `+N` chip), and
`tests/test_gui_camp_browser.py` (a busy bay shows an ork frame and opens its console; a station with
`debate: true` shows the annex; with `approve: true` a waiting cart stops at a lowered barrier).

## Prompt
Use the prompt in docs/specs/README.md with `<NN-name>` = `14-modular-depot`, adding: "Part A is done; do Part B."
