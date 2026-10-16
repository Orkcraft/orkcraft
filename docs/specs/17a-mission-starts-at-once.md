# Spec 17a — the onboarding's one fork: the tutorial, or a ready town

Branch `spec/17a-mission-starts-at-once` · model **flash** · design: first-mission.md §12.1, gui-onboarding.md §5
**Builds:** agy · **Review:** light (docs/specs/README.md "Who builds")

## Do
Change only `orkcraft/gui/onboarding.py`, `orkcraft/gui/static/js/onboarding.js`, `orkcraft/gui/static/onboarding.css`,
`tests/test_gui_onboarding.py` and a new `tests/test_gui_onboarding_browser.py` (modelled on
`tests/test_gui_mission_browser.py`). Change nothing outside these files.

In a first session (not *Set up again*), after the AI tools and the class, the town step becomes **one fork of two
cards**, side by side, nothing else on the screen:
1. **"I'm new: show me around"**, one line under it ("Build your camp one building at a time with the Workchief.
   About 5 minutes, free, no model."), its one button **Start the tutorial** → Mission 1, as *Set up the camp myself*
   does today (`onboarding.town` with `mission: true`).
2. **"Punk ork: I know orkestration"**, one line under it ("Start with a ready town, or describe the one you want."),
   its one button **Get a ready town** → a second screen with only two choices:
   - **the class's ready towns** (today's tabs and preview, *Use this town*);
   - **Describe your town** → today's 4b (the planner), closed with a line when no AI tool that can plan is on.
   A *Back* returns to the fork.
3. **Gone from the first session:** *Empty town, I'll build it myself* (a punk ork who wants it empty builds from
   Build). *Set up again* is unchanged.
4. Words: only the new labels above; nothing else changes.

## Tests
Critical tests, plus `tests/test_gui_onboarding.py tests/test_gui_onboarding_browser.py`: a first session's town
step shows exactly the two cards; *Start the tutorial* starts Mission 1 when the town opens; *Get a ready town* shows
the ready towns and *Describe your town*, and *Back* returns; no *Empty town* in a first session; *Set up again* as
before.
