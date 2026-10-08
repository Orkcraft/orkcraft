# GUI audit — queue (D1, 2026-10-08)

Written by **Night D1: GUI audit + quick fixes**. Taken by D2, D3 (rules in `plan.md` → Queues).
Screenshots: `ui/<look>-<place>.png`, taken on the demo sandbox (`orkcraft gui --demo --browser`), 1440×900
desktop and 390×844 phone, both looks. The Camp look, the orks and the gamification stay; these items are
about drawing them clearly.

Order: value / risk, best first. First version — refined below as the audit goes on.

## Queue

- [x] U01 Phone: the HUD overflows sideways — "Answers" is cut at the right edge, Spend / Context / Orks are
  off-screen, the page scrolls sideways — `ui/camp-phone-town.png`, `ui/office-phone-town.png` —
  `gui/static/layout.css` / `mobile` styles of the HUD — S — the phone is a place people answer from; the
  answers button is the one thing the phone must show. — done by D1: the HUD wraps to a second row, the portrait stands for the brand (`ui/after-U01-camp-phone.png`, `ui/after-U01-office-phone.png`)
- [ ] U02 A road's label is drawn over a card's footer: Calendar's "3 meetings left today" reads
  "t3 meetings left today" under `on_task_moved` (Camp); in Office `on_digest` is cut by the Daily brief card
  — `ui/camp-town.png`, `ui/camp-win-todo.png`, `ui/office-town.png` — `gui/static/js/roads*.js` / `town.css`
  — M — overlapping text is the first thing a new person sees as broken; a label must sit on a free stretch of
  its road, or on a plate above the cards.
- [ ] U03 A scrolling box gives no cue that it scrolls where scrollbars are overlay (macOS, phones, headless):
  Town settings stops at the "Accounts" heading and looks empty (its Google part and Phones are below the
  fold, `.gui-settings` is 848 px in 506), the War Map's fifth land is cut in half — `ui/camp-settings.png`,
  `ui/camp-town.png` — `layout.css` (`.gui-settings`, `.gui-map__view`), maybe one shared `.gui-scrolls` class
  — S/M — a fade at the edge that has more (the `background-attachment: local` shadows trick works on a flat
  `panel`) says "more below" in both looks.
- [-] U04 War Map's list cut at the bottom — merged into U03 (it is a scrolling list, 204 px in 144).
- [-] U05 HUD "Spend $— / $5.00" — left: the dash is deliberate (`core/treasury.py`: "—" until a session
  reports, so the HUD never claims a $0.00 it has not measured) and the TUI's tests hold it. A question for the
  morning in `report.md` (a tooltip "no agent has reported yet" would be the small step).
- [ ] U06 Phone: the HUD says "Answers (3)" while the chip under it says "❓ Asks you 0" (disabled) — the
  Quartermaster's three carts wait for review but no *building* is alerted, and the chips count only buildings
  — `ui/after-U01-camp-phone.png` — `gui/static/js/pocket.js` (`asks`) — S/M — two numbers for "what waits for
  me" that disagree; the chip should count what Answers counts (or open Answers when the town waits on a
  non-building).
- [ ] U07 With a building's panel open the Warchief's line squeezes: the placeholder is cut ("Ask the
  Warchief… or /") and the question beside it is cut to "Quartermaster: 3 cart…" —
  `ui/camp-win-todo.png` — `gui/static/js/warchief*.js` / `layout.css` — S/M — when space is short, drop the
  waiting question to an icon + count rather than cut both.
- [ ] U08 Office: the orange ✻ (busy Claude mark) floats in the middle of a card's title row, far from the
  title — `ui/office-town.png` — `office.css` hut title — S — the mark belongs to the card's title, at its
  right edge or right after the name.
- [x] U09 Office, phone: the building rows were 240 px wide on a 390 px screen (the Office theme's fixed
  `.ok-hut[class]` width won over the pocket's `width: auto`) — `ui/office-phone-town.png` → `ui/after-U01-office-phone.png` —
  `layout.css` — S — done by D1.
- [ ] U10 Office: a building's card, opened, grows in place and covers its neighbours and the portrait's two
  quick buttons (Calendar over Wiki's left half and over 🔕/look at the top-left); the War Map covers the
  External listeners card — `ui/office-win-days.png` — `layout.css` / `office.css` (z-order, the open card's
  room) — M — the town under an open panel should stay readable; the open card at least must not cover the
  HUD corner's controls.
- [ ] U11 An open card repeats its window's actions ("New event", "Prepare doc" under the Calendar card, while
  the panel's top row has the same two) — `ui/office-win-days.png`, `ui/camp-win-todo.png` ("New task",
  "New note") — `gui/static/js/hut.js` — S — with the panel open, one place for the actions is enough; hide the
  card's quick row while its panel is open.

