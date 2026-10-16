# Spec 11 — Mission 1b, Proof before the gate (three parts, three branches)

model **pro** · design: first-mission.md §10 (all of it; its table §10.5 is the plan) · after the testers' feedback
**Builds:** Claude · **Review:** full (docs/specs/README.md "Who builds")

Run the parts in order, each its own branch and its own review:

- **11a `spec/11a-missions-as-data`:** Mission 1's quests moved out of `orkcraft/realm/mission.py` into
  `missions/1.json` (and its loader), `mission.json` keyed by mission (Mission 1's old file still read); a test that
  every mission file is valid and its buildings exist. **No behaviour change**: all of `tests/test_mission.py` and
  `tests/test_gui_mission_browser.py` pass unchanged.
- **11b `spec/11b-proof-rounds`:** the check's rounds (§10.1): the test command found and run once on main (§10.2
  quest 1, `realm/mission_work.py`), `pool.checked` on the bus (round, verdict, the failure's tail), the depot's exit
  track as the proving siding with the semaphore (`depot/semaphore-0|1`, already cut), the waybill's rows per round
  and its foot; the drill's scripted check (`"check": [false, true]`).
- **11c `spec/11c-mission-1b`:** `missions/1b.json` with the three quests, the trigger and the one-time offer
  (§10.3), the deeds and the proving stone item (`design-system/sprites/v3/items/proving-stone.png` exists), the
  finale's chip.

## Tests
Each part: critical tests, `tests/test_mission.py`, `tests/test_gui_mission_browser.py`, and the new tests its part
of §10.5 names.

## Prompt
Use the prompt in docs/specs/README.md with `<NN-name>` = `11a-missions-as-data` (then 11b, 11c), adding:
"The spec is docs/specs/11-mission-1b.md; do only part 11a" (or 11b, 11c).
