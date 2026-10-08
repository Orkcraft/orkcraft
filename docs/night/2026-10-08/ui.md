# GUI audit — queue (D1, 2026-10-08)

Written by **Night D1: GUI audit + quick fixes**. Taken by D2, D3 (rules in `plan.md` → Queues).
Screenshots: `ui/<look>-<place>.png`, taken on the demo sandbox (`orkcraft gui --demo --browser`), 1440×900
desktop and 390×844 phone, both looks. The Camp look, the orks and the gamification stay; these items are
about drawing them clearly.

Order: value / risk, best first. First version — refined below as the audit goes on.

## Queue

- [ ] U01 Phone: the HUD overflows sideways — "Answers" is cut at the right edge, Spend / Context / Orks are
  off-screen, the page scrolls sideways — `ui/camp-phone-town.png`, `ui/office-phone-town.png` —
  `gui/static/layout.css` / `mobile` styles of the HUD — S — the phone is a place people answer from; the
  answers button is the one thing the phone must show.
- [ ] U02 A road's label is drawn over a card's footer: Calendar's "3 meetings left today" reads
  "t3 meetings left today" under `on_task_moved` (Camp); in Office `on_digest` is cut by the Daily brief card
  — `ui/camp-town.png`, `ui/camp-win-todo.png`, `ui/office-town.png` — `gui/static/js/roads*.js` / `town.css`
  — M — overlapping text is the first thing a new person sees as broken; a label must sit on a free stretch of
  its road, or on a plate above the cards.
- [ ] U03 Town settings: "Accounts" is a heading with nothing under it (no accounts in the demo) — an empty
  state with no line saying what goes there or how to add one — `ui/camp-settings.png` —
  `gui/static/js/settings.js`, `accounts.js` — S — an empty heading reads as a bug.
- [ ] U04 War Map's list is cut at the bottom of the window: the fifth land ("Front Desk") shows only its top
  pixels, no scroll cue — `ui/camp-town.png`, `ui/office-town.png` — `gui/static/js/warmap.js` + its css — S —
  a cut row looks like a rendering error; either fit the list or fade + scroll.
- [ ] U05 HUD: "Spend $— / $5.00" and "Context — / 128k" — a dash in a money figure reads as broken; say
  "$0.00" or "none yet" — `ui/camp-town.png` — HUD in `gui/static/js/` — S — money says plainly what happens
  (CLAUDE.md, voice).
- [ ] U06 Phone: "Asks you 0" and "At work 0" look disabled (grey on brown, below contrast) while they are the
  two main buttons — `ui/camp-phone-town.png` — `gui/static/js/mobile*.js` / css — S — a zero is a state, not
  a disabled control; keep the label at `ink-gold`, dim only the count.
- [ ] U07 With a building's panel open the Warchief's line squeezes: the placeholder is cut ("Ask the
  Warchief… or /") and the question beside it is cut to "Quartermaster: 3 cart…" —
  `ui/camp-win-todo.png` — `gui/static/js/warchief*.js` / `layout.css` — S/M — when space is short, drop the
  waiting question to an icon + count rather than cut both.
- [ ] U08 Office: the orange ✻ (busy Claude mark) floats in the middle of a card's title row, far from the
  title — `ui/office-town.png` — `office.css` hut title — S — the mark belongs to the card's title, at its
  right edge or right after the name.
