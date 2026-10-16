# Spec 27 — Mission 1 in four quests: no Office quest, no "Two at once"

Branch `spec/27-mission-four-quests` · design: decisions §35.4, first-mission.md §3 · **Builds:** Claude ·
**Review:** light · before 17b (17b builds on it)

## What
Mission 1 becomes **board → pool → gate → listen**. Quest 3½ (`office`: switch to Office and back) and quest 5
(`two`: two cards at once) leave Mission 1. Nothing else of the mission changes: its lines, presses, costs, the
finale after quest 3, *Lift the barrier*, Mission 1 done after `listen`.

1. `orkcraft/realm/mission.py`: remove the `office` and `two` quests from `QUESTS` (so from `IDS`). Remove
   `TWO_BUDGET_USD`, `TWO_COST` and the comments about quest 5 if nothing else uses them.
2. `orkcraft/core/mission.py`: remove what only those two quests use (`LABELS["office"]`, `LABELS["two"]`, the
   `office_seen` check, quest 5's press, its budget, `two_cost`, its hooks question for `two`). Keep the hooks question
   for `listen` as it is.
3. **Old state keeps loading.** A saved mission state whose current quest is `office` moves on to `listen`; one at
   `two`, or with a `two` key, counts Mission 1 as done (it already is after `listen`). No error, no lost deed or item
   already earned. The deed *Two faces*, if earned, stays; it is no longer earned by the mission.
4. The GUI (`js/mission.js` and anything reading the quest list or the labels `3½` and `5`): the quest log shows four
   quests numbered 1–4; no dead code paths for `office`/`two`. The building plots' labels follow.
5. Docs a person reads that list the quests (README, `docs/` guides for people, not design docs): four quests.

## Not in this spec
The Office look itself stays (the key, the setting, Office drawing). Running two cards in parallel stays a feature
of the product; only the quest goes. No new hint or line in its place.

## Tests
Update `tests/test_mission.py` and `tests/test_gui_mission_browser.py` to four quests; add: an old state at
`office` loads and moves to `listen`; an old state with `two` loads as Mission 1 done. Run the critical tests
(CLAUDE.md) plus the test files of every module touched.
