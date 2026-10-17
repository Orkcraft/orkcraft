# Spec 32 — the words goal and target

Branch `spec/32-goal-and-target` · design: decisions §44 · **Builds:** agy (flash) · **Review:** light · track 1, P1

## What (wording only)
1. `orkcraft/realm/lexicon.py` `TERMS`: the entry `track` shows **goal / goals** (`was`: "track", "tracks"). Its key,
   the code, the files, `pages/tracks/` and `kind: track` stay as they are.
2. The building setting shown as **Goal** (`orkcraft/gui/static/js/steward.js` `Goal`, and wherever its label is
   written) shows **Target** (`was`: "Goal"). Its values (thrift · balance · quality) and its config key stay.
3. Every visible string that says track(s) for §43's tracks, or Goal for the setting, follows: the board
   (`js/board/*.js`, `pwa/board.js`), `gui/ideas.py`, the phone, the Workchief's lines. Through `say()` for data;
   at the source for a template's own text (CLAUDE.md "Wording").
4. Docs a person reads (README, `docs/` guides) follow; design docs keep their words.

Change nothing else: no key, no file name, no behaviour.

## Tests
Update the tests that check these strings (CLAUDE.md: tests use the same wording); `tests/test_gui_wording.py` passes.
Run the critical tests and the test files of the modules touched, plus the board's browser tests.
