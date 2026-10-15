# Spec 10 — the phone's new UX (v4): one building in view, the orks' asks in a swiped sheet

Model **pro** for 10a, **flash** for 10b–10d · design: docs/design/mobile.md §13 (read it first) · after spec 01
(the fast first load), so the new screen doesn't load slowly.

Four parts, each its own branch and review, in order. All in `orkcraft/gui/static/pwa/` (the phone app: `app.js`
the app, `town.js` today's home screen of tiles, `camp.js` the Camp v3 drawing, `dock.js` the bottom bar, `slots.js`
the 🥩 sheet, `look.js`, `util.js` with `h()` and `sheet()`, `app.css`), plus `orkcraft/gui/mobile.py` (the compact
snapshot) only where a part says so. Nothing on the desktop changes. What a phone may do stays `mobile.allowed`.

## The screen (portrait), top to bottom

```
┌──────────────────────────┐
│ HUD (one slim row, v4)   │  🔥 n · ❓ n · 🥩 n · [Stop all] · [⛶ Full view]
├──────────────────────────┤
│ THE BUILDING IN VIEW     │  30–40 % of the height: Camp centred on the current card's
│ (camp.js, not pannable)  │  building; pans smoothly when the card's building changes
├──────────────────────────┤
│ ═ the sheet (parchment) ═│  one card: who asks, the question or proposal, its options;
│ ‹  2 / 5  ›   • • ● • •  │  swipe left/right or ‹ › to the next card
│ [Option A] [Option B]    │
│ [Reply…]                 │
└──────────────────────────┘
```

## 10a — the structure and the cards (branch `spec/10a-phone-cards`, model pro)

1. **The cards list**, a pure function `cards(snapshot)` in a new `pwa/cards.js`, built from what the compact
   snapshot already carries (today's tiles in `town.js` read the same data: find there what a question, a problem
   and a building's state look like). Order:
   1. **Since your last look**, one card, only if the snapshot has its digest (wins first: results at the gate,
      carts moved, the score's change; then counts of the rest);
   2. **questions** an ork waits on, oldest first (building, ork's name, the question, its options);
   3. **problems** (🔥 / stuck), oldest first;
   4. **proposals** (an ork's plan waiting for approval, an improvement), if the snapshot has them.
   Each card: `{id, kind, buildingId, title, body, options: [{label, cmd, args}], canReply}`.
   If a field the cards need is missing from the compact snapshot, add it in `orkcraft/gui/mobile.py` `compact`
   (small, read-only fields only) with a test in `tests/test_mobile.py`.
2. **The layout:** a new `pwa/home.js` replaces `town.js` as the home screen (keep `town.js` for one release behind a
   setting "Classic phone view" in the Look card, default off). Three regions as drawn above: HUD, building view
   (CSS height `clamp(30vh, 36vh, 40vh)`), sheet (the rest).
3. **The building view:** reuse `camp.js` to draw the camp; centre it on the current card's building at the default
   step; no pan or pinch in this view; a tap opens that building's sheet as today.
4. **The sheet:** one card; its options as buttons (`cmd` sent with the existing `deliver`/outbox, so answers given
   without signal are kept); "Reply…" when `canReply`; `2 / 5` and dots. An answered card shows "Sent ✓" for 600 ms and
   the next card comes in.
5. **Empty:** no cards → the building with the most work in view, the sheet says "All quiet" with **Drop an idea**
   (today's Drop sheet from `dock.js`).

## 10b — swipe, the camera, typing (branch `spec/10b-phone-motion`, model flash)

1. Horizontal **swipe** on the sheet (touch: ≥ 40 px horizontal, more horizontal than vertical) and ‹ › buttons
   change the card; the dots follow.
2. When the next card's building differs, the building view **pans** to it over 300 ms, moving on whole pixels
   (`steps()` or rounding as `js/camp/sprites.js` `dev()` does on the desktop), never a fractional transform.
3. **Typing:** "Reply…" opens a text field; the sheet **slides up over the building view** until the field sits above
   the keyboard (use `visualViewport` resize); the camp under it is not resized or redrawn. Closing the keyboard
   slides the sheet back.

## 10c — Full view and landscape (branch `spec/10c-phone-full-view`, model flash)

1. **Landscape** (`orientation: landscape`) shows the whole camp at the overview step, pannable and pinchable as the
   camp is today, the HUD on top, no sheet; a small "‹ Back" returns to portrait's cards when the phone turns back.
2. The HUD's **⛶ Full view** button does the same in portrait (for a phone with rotation locked); the same button
   returns.

## 10d — the v4 look (branch `spec/10d-phone-v4-look`, model flash)

1. Bring the v4 kit's look into `app.css` for Camp (`[data-look="camp"]`): wooden frame on the HUD, parchment sheet,
   teal plates, kit buttons, Jersey 15 for the HUD's numbers and card titles (the font files are under the desktop's
   fonts; serve them as `pwa.files()` serves the other fonts), the text face for card bodies. Copy the needed rules,
   don't load the desktop's `kit.css`.
2. Office look on the phone stays plain (as today).

## Tests (every part)
Critical tests, plus `tests/test_pwa.py tests/test_pwa_browser.py tests/test_pwa_console_browser.py`, and per part:
- 10a: `cards()` order and content from a fixture snapshot (new `tests/test_pwa_cards.py`, run in Node as
  `tests/test_camp_layout.py` runs layout.js); a browser test at 390 × 844: the three regions, a question's option
  sends its command, "All quiet" when empty.
- 10b: swipe changes the card and the view pans to its building; typing keeps the field above a simulated keyboard.
- 10c: landscape shows the whole camp; Full view in portrait and back.
- 10d: computed styles on the HUD and sheet in Camp; Office unchanged.

## Prompt
Use the prompt in docs/specs/README.md with `<NN-name>` = `10a-phone-cards` (then 10b, 10c, 10d), adding:
"The spec is docs/specs/10-phone-v4.md; do only part 10a" (or 10b, 10c, 10d).
