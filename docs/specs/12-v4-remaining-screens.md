# Spec 12 — the v4 kit on the screens it has not reached yet

Branch `spec/12-v4-remaining-screens` · model **flash** · design: design-system-v4.md (the kit), decisions §17.1
**Builds:** agy · **Review:** light (docs/specs/README.md "Who builds")

## Merged (16 October); left for a later round (12b, optional)
1. Town settings' section headings (shot 03) are still uppercase in the text face: Jersey 15, as the kit's headings.
2. Contrast on parchment (shot 13): the disabled *Cancel* and the tool warning line read too faintly.
3. `audit.md`: the Improve row says it moved, but it was already on the kit (06 before = after); say so.

## Round 2 (16 October): make the kit actually show, nothing else
The branch `spec/12-v4-remaining-screens` holds round 1 (`64082f8`). Work on it, on top of that commit. The limits
below still hold (only CSS and HTML templates of the desktop GUI, plus `docs/design/img/v4/`).
Round 1's CSS is scoped right, but the screenshots show the dialogs, Town settings and the Town Hall's Work panel
**still in the old look**: dark brown, no teal title plate, no parchment, old segmented controls.
1. **Find why the rules don't take effect** in Camp: `.ok-dialog`, `.gui-steps`, and the Town Hall
   `[data-type="town_hall"]` rules in `orkcraft/gui/static/kit.css`. `data-look="camp"` sits on `<html>` and
   `kit.css` loads last, so check what still wins (the dialog's own rules in `/ds/components.css` and `layout.css`,
   a more specific selector, an inline style or a CSS variable set later) with the browser's computed style, and fix
   it in CSS. Don't use `!important`.
2. **Retake every screenshot** after a fresh page load: each shot a different screen (01 and 05 are the same file
   today), the missing `10` added or its absence said in `audit.md`. Each moved screen visibly shows parchment, a
   wood frame, a teal title plate, and Jersey 15 only on headings, numbers and buttons. Put one **before** shot (from
   `main`) beside each after shot: `NN-name-before.png`.
3. In `audit.md`, list the Town Hall's Work chat as **"needs JS"** (its panel is missing from `PAPER` in
   `windows.js`) instead of a CSS `:has()` workaround; remove that workaround.
4. Remove the `.ok-dialog.is-warn, .ok-dialog.is-error` rule that only repeats the base frame, and scope the Camp
   `.gui-steps` rules to the dialogs and the shop frame the audit names.

Tests: as below. A browser test checks one moved dialog's computed style in Camp (a background that is the
parchment token, a title on the plate) and that the same dialog in Office is unchanged.

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
