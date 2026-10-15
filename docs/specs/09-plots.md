# Spec 09 — plots: empty places that invite a building

Branch `spec/09-plots` · model **flash** · design: decisions §20 ("Plots…", "Plots come after Mission 1") · after 07
**Builds:** agy · **Review:** light (docs/specs/README.md "Who builds")

## Art (the owner, Gemini app or agy): one small sheet
Attach `docs/design/img/references/v3/f1-town.jpg`. Prompt: "Pixel-art, same style as the attached frame: on flat
magenta, three separate pieces: a building plot staked out with four short wooden stakes and a rope between them
(seen from the front, flat on the grass, 128×64 px); a blank wooden sign on a post; a rolled blueprint pinned to a
post. Crisp dark outline, no text, no yellow, no red." Save 3 candidates in
`docs/design/img/references/v3/candidates/p1-plots/`; the PM session cuts them.

## Do (agy)
1. Plots exist only once Mission 1 is done (`mission_done`).
2. At most two at once, in the free places of band 1 (for a main-line type not built) or the quarter (others).
3. Which: a small rule table in a new pure module `orkcraft/realm/plots.py`: the campaign's next mission's building;
   a pain seen in the town (failed checks → Test bench `lab`; ≥ 3 meetings this week → Calendar `war_drum`); the
   charter's goal keywords (game → `ux_lab`; library → `lab`, `forge`). Returns building types with a one-line why.
4. Drawn: the stakes and rope; a tap/hover shows the building's v3 sprite as a dark silhouette (CSS filter
   brightness(0) opacity .35) and a kit notice with the why line, the price in plain words, **Build…** (opens the
   build flow on that type) and **Not now** (hidden 14 days, saved in `.orkcraft/plots.json`).
5. Calm: no badge, no count, no animation; Office draws none.

## Tests
Critical tests, plus new `tests/test_plots.py` (the rules, the 14 days, none before Mission 1),
`tests/test_camp_layout.py`, a browser test (a plot shows its silhouette and Build opens the flow).

## Prompt
Use the prompt in docs/specs/README.md with `<NN-name>` = `09-plots`.
