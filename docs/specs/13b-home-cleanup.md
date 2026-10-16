# Spec 13b — the home's menu: a small cleanup after spec 13

Branch `spec/13b-home-cleanup` · model **flash** · design: spec 13 (merged in `541f2ef`)
**Builds:** agy · **Review:** light (docs/specs/README.md "Who builds")

## Do
Change only `tests/test_pwa_browser.py`, `orkcraft/gui/static/js/camp/town.js`, `orkcraft/gui/static/js/camp/notices.js`.
Change nothing outside these files. Check 3 of "Before you commit" has one exception here: item 1 removes that one
assertion, because it never tested anything; touch no other assertion.
1. In `tests/test_pwa_browser.py`, drop the `notice_reaches_home` assertion: it compares a lambda defined in the test,
   so it proves nothing (the phone's Camp, `pwa/camp.js`, does not load `notices.js`). Keep the no-hall and
   draws-without-error checks.
2. `town.js` (~247): the charter entry calls `command("charter.open")`, which does not exist until spec 03; remove it
   until then.
3. `notices.js`: one `isHall(id)` helper on `HALL` instead of `id === "town_hall" || id === HALL` twice.

## Tests
Critical tests, plus `tests/test_camp_layout.py tests/test_gui_camp_browser.py tests/test_pwa_browser.py`.
