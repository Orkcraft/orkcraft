# Spec 14 — the modular depot (an ork in every bay), the council fire of parts (an ork on every seat), the small barrier

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

**a2-council-parts** (the debate's campfire, built of parts like the depot: 1 to 6 orks)
> Pixel-art, same style, palette, pixel size and front view as the attached camp, on flat magenta (#ff00ff),
> separate pieces that compose a small council around a campfire: (1) the campfire centre: a ring of stones with
> logs, unlit; (2) the same, lit with a low fire; (3) one log seat (a short log lying sideways), empty, to stand left
> or right of the fire; (4)–(6) the same log seat with a capped ork in a leather apron sitting on it, seen from the
> front: talking with a raised hand, listening with arms crossed, pointing at a scroll. Seats and orks are drawn so
> they can be placed side by side in a row, one to three on each side of the fire. Muted colours, no yellow, no red,
> no text, crisp dark outline.

**a3-small-barrier**
> Pixel-art, same style as the attached frame, on flat magenta: a small boom barrier across one rail track, down and
> up versions (two pieces), wooden post with a striped boom in muted colours (no yellow, no red). Crisp outline, no text.

Push the candidates on the branch; the PM session picks and cuts them (`tools/camp_sheet.py`) into
`design-system/sprites/v3/depot/{end-w,bay,bay-shut,end-e}.png`, `depot/bay-ork-1..4.png`,
`annex/council-fire-unlit|lit.png`, `annex/council-seat.png`, `annex/council-ork-1..3.png`,
`track/barrier-down|up.png`.

## Part B — code (agy, after the PM session has cut the sprites)
1. **The depot is composed of parts** in `js/camp/layout.js` / `town.js`: west end + N bay segments + east end,
   N = the pool's `max_orcs` (1 to 8; the one-bay size is N = 1, process-lines.md §2). It counts as
   `ceil((N + 1) / 2)` places in its row. A line too short for N bays shows as many as fit and a `+N` chip.
2. **An ork in every busy bay:** a bay whose Grunt works shows `depot/bay-ork-<k>.png` (k cycles every few seconds,
   whole frames, no fractional motion) with that Grunt's bubble above the roof; a free bay shows `bay-shut`; a cart
   for that bay stands in its opening. Hover a bay: that ork's name and task; click: its console (as clicking an ork
   does today).
3. **The council, composed of parts** (process-lines.md §3): when a station has `debate: true`, its annex is the fire
   centre with **one seat per critic** (1 to 6, from the station's debate config), seats placed alternately left and
   right of the fire. An empty seat while no debate runs; during a debate each critic sits as an ork
   (`council-ork-<k>`, cycling whole frames), the fire lit, and the critic now speaking wears a small speech bubble
   with its role ("Skeptic", "User advocate"…). Hover an ork: its role and its verdict once given. The annex counts as
   one place in its row up to 2 seats, two places beyond.
   **The small barrier** (`track/barrier-*`) is drawn when a station has `approve: true`: down while a cart waits for
   the person, with the cart's yellow flag (the only yellow).
4. Office unchanged.

## Tests
Critical tests, plus `tests/test_camp_layout.py` (depot width by N; places counted; the `+N` chip), and
`tests/test_gui_camp_browser.py` (a busy bay shows an ork frame and opens its console; a station with
`debate: true` and 3 critics shows the fire with 3 seats, 3 orks while debating; with `approve: true` a waiting cart stops at a lowered barrier).

## Prompt
Use the prompt in docs/specs/README.md with `<NN-name>` = `14-modular-depot`, adding: "Part A is done; do Part B."
