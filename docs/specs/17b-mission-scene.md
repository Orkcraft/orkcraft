# Spec 17b — Mission 1 as a scene: the Workchief on the map, a walk through each building

Branch `spec/17b-mission-scene` · design: first-mission.md §12 (read it first), §3 · after 17a
**Builds:** Claude · **Review:** full (docs/specs/README.md "Who builds")

## Why
Today the quest log sits in the Workchief's line at the camp's foot (`js/mission.js` `QuestLog`); new people don't
see it, and a raised building is never shown. The owner, 16 October: put the window away, zoom on the stage, let the
Workchief speak on the map, and walk the person through each building.

## Do
1. **Focus mode** (`mission.focus` in the snapshot while quests 1–3 run): the chrome fades out (command bar, HUD,
   the camp's foot line, open panels), the map dims except the stage (the mission's plots and the Workchief's place),
   and the camera zooms so the stage fills the view (`js/zoom.js`, whole device pixels, no fractional transforms).
   Leaving focus restores the person's zoom and the chrome as they were.
2. **The Workchief on the map:** his camp sprite walks in to his place (no motion under `prefers-reduced-motion`);
   a speech bubble anchored above him in the v4 kit (parchment, his face on a teal plate) shows the quest's lines one
   at a time: *Next*, Space or a click; the quest's press on its last line; *Skip the mission* in the corner. The
   lines live in `realm/mission.py` with the quests (more than one line per quest now), through `say()`.
3. **The walk:** after a quest raises its building, the building's room opens (spec 21's screen; the Agent pool's and the
   Review gate's rooms from specs 22 and 23 once merged, else the plain room) and two or three steps highlight
   one part each (the rest of the view dimmed), the Workchief's line beside it; *Next*, *Got it* (ends the walk),
   *Back to the camp*. Task board: the drill card, how cards arrive. Agent pool: the bays and the orks, where ❓ shows.
   Review gate: the barrier, pass or send back, the waybill. Each step names its target by a stable selector in the
   view, so a view change breaks a test, not the walk silently.
4. **The chrome returns** after quest 3 (the finale), with one line naming the command bar (quest 3½ is gone: spec 27); from quest 4 the quest log works as today,
   the bubble on the map only for each quest's first line.
5. **Office:** the same steps without sprites: the bubble a plain card beside the plot; the dim kept.
6. Events for the dogfood log (`dogfood-logs.md`): a walk started, ended by *Got it* or finished, per building; the
   mission skipped at which line. So the testers' sessions show where people stop.

## Not in this spec
New art (the Workchief's existing camp sprite is used), sound, the charter (spec 03), the rewards.

## Tests
Critical tests, plus `tests/test_mission.py tests/test_gui_mission_browser.py tests/test_gui_camp_browser.py`:
focus hides the chrome and dims the map; the bubble sits on the map near the Workchief, not at the foot; *Next*
walks the lines; the press raises the building and opens its walk; *Got it* ends it; *Skip the mission* restores the
chrome and the zoom; reduced motion has no walk-in; Office shows the card, no sprites; the chrome is back after quest 3.
Every new test shown to fail without its code (README "Before you commit").
