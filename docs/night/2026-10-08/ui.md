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
- [x] U02 A road's label is drawn over a card's footer: Calendar's "3 meetings left today" reads
  "t3 meetings left today" under `on_task_moved` (Camp); in Office `on_digest` is cut by the Daily brief card,
  and in Office dark (main set) `on_patch` runs under card 1 and reads "tch"
  — `ui/camp-town.png`, `ui/camp-win-todo.png`, `ui/office-town.png`, `ui/office-dark-town-main.png` — `gui/static/js/roads*.js` / `town.css`
  — M — overlapping text is the first thing a new person sees as broken; a label must sit on a free stretch of
  its road, or on a plate above the cards. — done by D2 (7338c3d): a label goes on the first free stretch of its road that clears every card and label (`js/town.js` `labelSpot`) — `ui/after-U02-camp-town.png`, `ui/after-U02-office-town.png`, `ui/after-U02-office-dark-main.png`
- [x] U03 A scrolling box gives no cue that it scrolls where scrollbars are overlay (macOS, phones, headless):
  Town settings stops at the "Accounts" heading and looks empty (its Google part and Phones are below the
  fold, `.gui-settings` is 848 px in 506), the War Map's fifth land is cut in half — `ui/camp-settings.png`,
  `ui/camp-town.png` — `layout.css` (`.gui-settings`, `.gui-map__view`), maybe one shared `.gui-scrolls` class
  — S/M — a fade at the edge that has more (the `background-attachment: local` shadows trick works on a flat
  `panel`) says "more below" in both looks. — done by D2 (7338c3d): one shared cue, `.gui-scrolls` + `js/scrollcue.js` — the edge that has more fades (a mask, so it works over the War Map's opaque lands too), on Town settings and the War Map — `ui/after-U03-camp-settings.png`, `ui/after-U03-office-settings.png`, `ui/after-U03-camp-map.png`
- [-] U04 War Map's list cut at the bottom — merged into U03 (it is a scrolling list, 204 px in 144).
- [-] U05 HUD "Spend $— / $5.00" — left: the dash is deliberate (`core/treasury.py`: "—" until a session
  reports, so the HUD never claims a $0.00 it has not measured) and the TUI's tests hold it. A question for the
  morning in `report.md` (a tooltip "no agent has reported yet" would be the small step).
- [x] U06 Phone: the HUD says "Answers (3)" while the chip under it says "❓ Asks you 0" (disabled) — the
  Quartermaster's three carts wait for review but no *building* is alerted, and the chips count only buildings
  — `ui/after-U01-camp-phone.png` — `gui/static/js/pocket.js` (`asks`) — S/M — two numbers for "what waits for
  me" that disagree; the chip should count what Answers counts (or open Answers when the town waits on a
  non-building). — done by D1: the chip counts what Answers counts and opens Answers when no building asks (`ui/after-U06-camp-phone.png`).
- [ ] U07 With a building's panel open the Warchief's line squeezes: the placeholder is cut ("Ask the
  Warchief… or /") and the question beside it is cut to "Quartermaster: 3 cart…" —
  `ui/camp-win-todo.png` — `gui/static/js/warchief*.js` / `layout.css` — S/M — when space is short, drop the
  waiting question to an icon + count rather than cut both.
- [x] U08 Office: the orange ✻ (busy Claude mark) floats in the middle of a card's title row, far from the
  title — `ui/office-town.png` — `office.css` hut title — S — the mark belongs to the card's title, at its
  right edge or right after the name. — done by D2 (33d906b): Office's name takes only its width (`office.css`), the ✻ follows it, the pin keeps the right edge — `ui/after-U08-office-town.png`
- [x] U09 Office, phone: the building rows were 240 px wide on a 390 px screen (the Office theme's fixed
  `.ok-hut[class]` width won over the pocket's `width: auto`) — `ui/office-phone-town.png` → `ui/after-U01-office-phone.png` —
  `layout.css` — S — done by D1.
- [ ] U10 Office: a building's card, opened, grows in place and covers its neighbours and the portrait's two
  quick buttons (Calendar over Wiki's left half and over 🔕/look at the top-left); the War Map covers the
  External listeners card — `ui/office-win-days.png` — `layout.css` / `office.css` (z-order, the open card's
  room) — M — the town under an open panel should stay readable; the open card at least must not cover the
  HUD corner's controls.
- [x] U11 An open card repeats its window's actions ("New event", "Prepare doc" under the Calendar card, while
  the panel's top row has the same two) — `ui/office-win-days.png`, `ui/camp-win-todo.png` ("New task",
  "New note") — `gui/static/js/hut.js` — S — with the panel open, one place for the actions is enough; hide the
  card's quick row while its panel is open. — done by D2 (33d906b): a selected (open) building's card keeps its quick row in (`layout.css`); the panel's Info has the actions — `ui/after-U11-camp-open.png`
- [x] U12 Answers: the list cut each question at 40 characters with no ellipsis ("price id missing i") —
  `ui/camp-answers.png` → `ui/after-U12-camp-answers.png` — `js/orders.js`, `layout.css` — S — done by D1:
  the whole question, cut by CSS with "…" when it does not fit, the full text in its tooltip.
- [x] U13 Camp: a building's text actions (Info tab: History, Open in OS, Deploy, Watch, Report, Redesign) were
  sentence case at 14 px beside uppercase tabs and buttons — `ui/camp-win-tree-info.png` →
  `ui/after-U13-camp-info.png` — `layout.css` — S — done by D1: `--ok-case` and `--ok-track`, as `ok-btn`.
- [x] U14 Answers: the answer options and "Later" are the same look, stacked in one column ("1 Acknowledge",
  then "Later" under it), so "Later" reads as one more answer — `ui/after-U12-camp-answers.png` — `js/orders.js`,
  `.gui-orders__options` — S — options in a row (they wrap), "Later" right-aligned in the actions row as every
  dialog's dismiss. — done by D2 (33d906b): the answers in a wrapping row, "Later" at the right of the actions row (`.gui-orders__later`) — `ui/after-U14-camp-answers.png`
- [-] U15 Answers is called three things: "Answers (4)" in the HUD, "Awaiting an answer (4)" as the dialog's
  title, "Asks you" on the phone — `ui/camp-answers.png` — left: "Awaiting an answer" is its own lexicon term
  (`realm/lexicon.py` `awaiting_orders`), so this is a wording decision for the owner (question in `report.md`).
- [x] U16 External listeners (Camp): two green primary buttons ("+ Add source", "Open new") and "Open new"
  wraps alone onto a second toolbar row — `ui/camp-win-post.png` — `gui/static/js/buildings/` (post) — S — one
  primary per view (design-system/components.md); "Open new" is a plain button in the row. — done by D2 (3b034e8): "Open new" was already a plain button (the green was the screenshot's scaling); its wrap was the cause — when it looked is now a line of its own under the actions, the five actions fit one row — `ui/after-U16-camp-post.png`
- [x] U17 A building's window showed another number than its card ("34 External listeners" over card "5"): the
  panel counted the whole town's buildings, the card only the open orkspace's — `ui/camp-watchtower-number.png`
  → `ui/after-U17-camp-watchtower.png` — `js/windows.js` — S — done by D1: the window counts as the town does.
- [x] U18 A raw git error was the whole message: "fatal: not a git repository (or any of the parent
  directories): .git", twice in Branches & PRs, in Review gate's bar, on both cards and in a warning toast —
  `ui/camp-forge.png`, `ui/camp-loot.png` → `ui/after-U18-camp-forge.png`, `ui/after-U18-camp-loot.png` — done
  by D1: `realm/gitinfo.py` `plain_error` says git's known messages (no repository, no commits yet, dubious
  ownership) in plain words with what to do, at the source (Branches & PRs, Review gate, File tree); an unknown
  message stays git's; Branches & PRs' body no longer repeats its bar.
- [x] U19 Agent pool's empty window: "No open tasks" at the top and "No orks yet…" 400 px lower, in the middle of
  nothing — `ui/camp-barracks.png` — `gui/static/js/buildings/barracks.js` — S — one empty state under the task
  field; the orks' line only when there is a task. — done by D2 (3b034e8): with no task and no ork the orks' pane says nothing; the pool's one empty line stays under the task field — `ui/after-U19-camp-barracks.png`
- [x] U20 Publisher: the card says "Fire · Dry run", its window "Dry run · Fire" — `ui/camp-catapult.png` —
  `buildings/catapult.js` — S — the same order in both, the safe one first (and "Fire" the primary only where
  an address is set: with none it can only dry-run). — done by D2 (3b034e8): Dry run first in the catalog (`realm/catalog.py`), so the card and the window agree; Fire is the primary only with an address (or MCP / browser mode) — `ui/after-U20-camp-catapult.png`
- [x] U21 Metrics writes money "0 $", the HUD "$0.00" — `ui/camp-crag.png` — `buildings/crag.js` — S — one
  format for money, the HUD's. — done by D2 (3b034e8): `core/workers/crag.py` `with_unit` writes money $0.00 ($— for none) in the window, the card and the threshold toast; the TUI's own Crag view keeps its format (TUI: fixes only) — `ui/after-U21-camp-crag.png`
- [ ] U22 The ork's 👍/👎 bubble over a yard (script-first building) covers the yard's number and the first letters
  of its name ("OUTER", "OUND ALERTS") while the mouse is over it — `ui/camp-signpost.png`, `ui/camp-horn.png`
  — `js/hut.js` / `yards.css` (the bubble from 9b87d76) — S — the bubble stands left of or above the title
  plate, never on it.
- [ ] U23 A folded yard (Transformer, Router) shows an empty plate with a lone "Run" or nothing — no state line
  ("No steps yet") as the other cards have — `ui/camp-mill.png`, `ui/camp-signpost.png` — `js/hut.js` — S/M —
  a card always says its state in one line.
- [x] U24 A building's ork waking on an error says nothing: the toast reads "Branches & PRs — its ork woke on an
  error: it says ERROR" — `ui/after-U18-camp-forge.png` — `gui/keeper.py` (`wake.detail`) and where the detail
  is made in `realm/` — S — say the building's own error line (as the card shows it), not its status word. — done by D2 (7338c3d): `core/wakes.py` `_detail` reads the error the worker keeps (a snapshot's, `last_error`, `errors`) or its card's ⚠ line; with none, "its card shows a failure with no reason given — open it to see". A unit test; no wake fired in the demo sandboxes (their folders are git repositories), so no screenshot

