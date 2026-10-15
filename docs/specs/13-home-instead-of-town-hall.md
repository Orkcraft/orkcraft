# Spec 13 — no Town Hall in the camp; the home's menu takes its door and the Items

Branch `spec/13-home-menu` · model **flash** · design: decisions-2026-10.md §20 ("No Town Hall in the camp…")

## Do
1. **Camp:** `js/camp/layout.js` and `js/camp/town.js` no longer place or draw the `town_hall` building (its orks
   and its config stay; nothing is deleted from the town file). Office (`js/town.js`) is unchanged.
2. **The home's menu** (`js/camp/town.js`, today: Since your last look · You: profile and deeds · Town settings…)
   becomes, in this order:
   - Since your last look
   - You: profile and deeds
   - **Items** — opens the Items panel (`js/camp/items.js`)
   - **The Workchief's council** — opens the Town Hall building's panel (the same view a click on the hall opened)
   - **The charter** — only when a charter is set (spec 03)
   - Town settings…
   Words for new labels go through `orkcraft/realm/lexicon.py` if they name a concept (CLAUDE.md "Words").
3. **The Items button** under the portrait is removed in Camp; dragging an item from the panel onto the grass works
   as today.
4. Anything that opened the Town Hall by clicking its building in Camp (the Workchief's line at the camp's foot, a
   notice, a quest) now opens the home's menu's council entry instead. Grep for the Town Hall's id/type in
   `js/camp/` and `js/warchief.js`.

## Tests
Critical tests, plus `tests/test_camp_layout.py` (no town_hall placed in Camp), `tests/test_items.py`,
`tests/test_gui_camp_browser.py` (the home's menu has the six entries; Items opens the panel and an item still drags
onto the grass; the council entry opens the hall's panel), `tests/test_gui_browser.py` (Office still shows the hall).

## Prompt
Use the prompt in docs/specs/README.md with `<NN-name>` = `13-home-menu`.
