# Spec 10 — the phone's v4 screen

Branch `spec/10-phone-v4` · model **pro** · design: mobile.md §13 (all of it) · after spec 01

## Do (in `orkcraft/gui/static/pwa/`)
1. **HUD:** one slim row in the v4 kit (copy the needed kit classes' look into `app.css`; the PWA does not load the
   desktop's kit.css): 🔥 · ❓ · 🥩 counts, Stop all (teal), Full view.
2. **The building in view:** the top 30–40 % shows the camp (today's Camp v3 drawing in `camp.js`) centred on the
   current card's building, not pannable in this mode; it pans smoothly (300 ms, whole pixels) when the card's
   building changes; a tap opens that building's sheet as today.
3. **The bottom sheet:** parchment, one card at a time, swiped horizontally (touch) or with ‹ › buttons; `2 / 5` and
   dots. Order: since your last look (one card) → questions (oldest first) → 🔥 problems → proposals. A question's
   options are buttons; "Reply…" opens a text field: the sheet **slides up over the building** to sit above the
   keyboard and slides back when it closes (never squeezes the camp). Answered: a short confirmation, next card.
   Nothing waiting: "All quiet" and **Drop an idea**.
4. **Full view:** landscape shows the whole town at the overview step; the button does the same in portrait.
5. Same commands as today (`mobile.allowed`); words from the snapshot as today.

## Tests
Critical tests, plus `tests/test_pwa.py tests/test_pwa_browser.py tests/test_pwa_console_browser.py`; new browser
cases at 390 × 844: swipe changes the card and pans to its building; typing slides the sheet; Full view in landscape.

## Prompt
Use the prompt in docs/specs/README.md with `<NN-name>` = `10-phone-v4`.
