# Spec 13 — no Town Hall in the camp; the home's menu takes its door and the Items

Branch `spec/13-home-menu` · model **flash** · design: decisions-2026-10.md §20 ("No Town Hall in the camp…")
**Builds:** agy (round 2) · **Review:** light (docs/specs/README.md "Who builds")

## Merged (16 October); a small cleanup left for a later run
Rounds 1 and 2 are in `main` (`541f2ef`). Left, on a new branch `spec/13b-home-cleanup` from `main`, changing only
`tests/test_pwa_browser.py`, `js/camp/town.js`, `js/camp/notices.js`:
1. In `tests/test_pwa_browser.py`, drop the `notice_reaches_home` assertion: it compares a lambda defined in the test,
   so it proves nothing (the phone's Camp, `pwa/camp.js`, does not load `notices.js`). Keep the no-hall and
   draws-without-error checks.
2. `town.js` (~247): the charter entry calls `command("charter.open")`, which does not exist until spec 03; remove it
   until then.
3. `notices.js`: one `isHall(id)` helper on `HALL` instead of `id === "town_hall" || id === HALL` twice.

## Round 2 (15 October): fix the first round, nothing else
The branch is `spec/13-home-instead-of-town-hall` (not the name above); it already holds round 1 (`330857f`). Work on
it, on top of that commit. Change only `orkcraft/gui/static/js/camp/layout.js`, `town.js`, `notices.js`,
`console.js`, `items.js`, `orkcraft/realm/lexicon.py` and the tests below. Change nothing outside these files.
1. **Point 4 below was not done.** In Camp, a notice from the `town_hall` (notices.js filters by `L.buildings[id]`, so
   today it vanishes) shows on the person's home instead and opens the council (`openCouncil`). The External
   listeners' road dialog (`console.js`, ListenDialog) no longer offers the Town Hall as a road source in Camp.
2. **Lexicon:** drop the made-up old spellings (`was="The Warchief's council"` and the new `_PHRASES` entries): these
   words never existed, so there is nothing to translate. Move the new terms (`charter`, `item`) into the section
   where their kind lives, each with a one-line comment like its neighbours.
3. **One filter:** the `town_hall` exclusion lives once, in `layout.js` (`lay`/`order`); remove the copies elsewhere
   (`layout.js` and `town.js`).
4. **The phone:** the phone app also loads `camp/layout.js`, so its Camp loses the hall too. Add a test that the
   phone's Camp still draws without error and has no Town Hall, and that the hall's notices reach the home there too.

Tests: critical tests, plus `tests/test_camp_layout.py tests/test_items.py tests/test_lexicon.py
tests/test_gui_wording.py tests/test_gui_camp_browser.py tests/test_pwa_browser.py`.

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
