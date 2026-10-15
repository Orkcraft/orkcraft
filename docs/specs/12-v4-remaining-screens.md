# Spec 12 — the v4 kit on the screens it has not reached yet

Branch `spec/12-v4-remaining-screens` · model **flash** · design: design-system-v4.md (the kit), decisions §17.1

## Tonight's limits (15 October: runs beside 01 and 13)
Specs 13 and 01 run on other branches the same night. So in this spec: **skip the portrait's / home's menu and the
Items panel** (13 changes them; they move to the kit in a later round), and change **only CSS files and HTML
templates** of the desktop GUI (`orkcraft/gui/static/**/*.css`, `orkcraft/gui/**/*.html`) plus
`docs/design/img/v4/`. Do not touch any `.js` or `.py` file, nor anything under `orkcraft/gui/static/pwa/`. If a
screen can't move without a JS change, list it in the audit as "needs JS" and leave it.

## Why
The v4 kit (wood frames, teal plates, parchment, Jersey 15 for headings and numbers) is on Camp's chrome and all 19
building views (V4 session, 15 October). Screens a tester meets that may still wear the old look must be checked and
moved to it, Camp only (Office stays as it is).

## Do
1. **Audit first:** open each screen below in Camp at 1440 × 900 and list in `docs/design/img/v4/audit.md` which
   already use the kit's classes (`.kit-*` from `design-system/kit.css`) and which do not:
   the onboarding (every step, the class cards), Mission 1's quest log and its finale toast, Settings (Town settings,
   Phones, You), the Build menu and its steps, Improve, the Workchief's chat, "Since your last look", the portrait's
   menu and deeds, the Items panel, the inside of the Task board, every modal or confirm dialog, the error and empty
   states, the search/command palette if any.
2. **Move each one not on the kit** onto it: frames, plates for titles, parchment for content, kit buttons
   (`btn-wood` / `btn-teal`), Jersey 15 only for headings, numbers and buttons; long text stays the text face. Scope
   every rule under `[data-look="camp"]`.
3. Nothing changes in Office; no word changes anywhere.

## Tests
Critical tests, plus `tests/test_design.py tests/test_gui_wording.py tests/test_gui_browser.py
tests/test_gui_camp_browser.py`. Take one screenshot per moved screen into `docs/design/img/v4/remaining/`.

## Prompt
Use the prompt in docs/specs/README.md with `<NN-name>` = `12-v4-remaining-screens`.
