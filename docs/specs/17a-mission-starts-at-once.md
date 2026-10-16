# Spec 17a — Mission 1 starts at once; the other ways under one link

Branch `spec/17a-mission-starts-at-once` · model **flash** · design: first-mission.md §12.1, gui-onboarding.md §5
**Builds:** agy · **Review:** light (docs/specs/README.md "Who builds")

## Do
Change only `orkcraft/gui/onboarding.py`, `orkcraft/gui/static/js/onboarding.js`, `orkcraft/gui/static/onboarding.css`,
`tests/test_gui_onboarding.py` and the onboarding's browser test. Change nothing outside these files.
1. In a first session (not *Set up again*), after the AI tools and the class, the town step opens **Mission 1** as
   its only primary choice: the Mission 1 card with its one button (*Set up the camp myself*), full width.
2. The ready towns (tabs), *Doesn't fit: tell the planner* and *Empty town, I'll build it myself* move under one
   quiet link below it, **Other ways to start**, closed by default; opened, they look and work as today.
3. *Set up again* is unchanged (it never shows Mission 1).
4. No word changes except the new link's text, "Other ways to start".

## Tests
Critical tests, plus `tests/test_gui_onboarding.py` and the onboarding's browser test: a first session shows the
Mission 1 button and no town tabs until *Other ways to start* is pressed; pressing it shows the three ways; *Set up
again* is as before.
