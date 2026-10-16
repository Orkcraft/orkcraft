# Audit of screens in Camp look at 1440 × 900 (v4 kit)

Date: 15 October 2026.
Spec: `docs/specs/12-v4-remaining-screens.md`.
Scope: Camp look only (`[data-look="camp"]`). Office stays unchanged. Wording stays unchanged.
Tonight's limits: Skip portrait's / home's menu and Items panel (spec 13 changes them). Changes only in CSS and HTML templates.

---

## 1. Summary

| Screen | Status before this spec | Uses `.kit-*` in code? | Needs move? | Notes |
|---|---|---|---|---|
| **Onboarding** (tools, class cards, town, setup) | Old dark panel look | No | **Yes** | Moved via CSS onto wood frame, parchment, Jersey 15 headings, wood bevel class cards |
| **Mission 1 quest log & finale toast** | On kit | Yes (`.kit-frame-thin`, `.kit-paper`) | **No** (already on kit) | Quest log uses thin frame & parchment; toasts use thin frame & pixel marks |
| **Settings** (Town settings, Phones) | Old dark dialog look | No | **Yes** | Moved via `.ok-dialog` kit rules; `.gui-steps` moved to wood/teal controls |
| **You** (in portrait menu) | Old look | No | **Skipped** | Tonight's limits: skip portrait's / home's menu (spec 13 changes them) |
| **Build menu & steps** | Frame on kit, inner text old | Partially (frame only) | **Yes** | Inner group headers moved to Jersey 15 sentence case; rules engraved in parchment |
| **Improve** | Frame on kit; dialog uses `ok-dialog` | Partially | **Yes** | Moves onto kit when `.ok-dialog` moves; days list on parchment |
| **Workchief's chat** (Town Hall & thread) | Town Hall omitted from `PAPER` | Thread yes; Town Hall Work no | **Needs JS** | Town Hall panel is omitted from `PAPER` in `windows.js`, so it stays dark; requires a JS change to add to `PAPER`, left for a later round |
| **"Since your last look"** | Old dark dialog | No | **Yes** | Uses `.ok-dialog`; moves onto kit (wood frame, parchment, Jersey 15 sections) |
| **Portrait's menu and deeds** | Old look | No | **Skipped** | Tonight's limits: skip portrait's / home's menu (spec 13) |
| **Items panel** | On kit in `kit.css` | Yes (`.kit-frame`, slots) | **Skipped** | Tonight's limits: skip Items panel (spec 13) |
| **Inside of Task board** | On kit | Yes (`.gui-inside__shop-frame`) | **No** (already on kit) | Right panel uses thick frame with teal caps, teal plate, well inputs |
| **Every modal or confirm dialog** | Old dark panel look | No | **Yes** | Moved via `.ok-dialog` to thick wood frame, parchment, teal plate title |
| **Error and empty states** | Toasts on kit; dialogs/lists old | Partially | **Yes** | Error toasts already on kit; error dialogs and list empty states move with containers |
| **Search / command palette** | On kit | Yes (`.kit-frame-thin`, `.kit-paper`) | **No** (already on kit) | Over bar wears thin frame & parchment; commands in mono on parchment |
| **Settings (Phones)** (screenshot 10) | Old dark dialog | No | **Yes** | Scrolled view of Phones in Town settings (`10-settings-phones.png`), moved via `.ok-dialog` kit rules |
| **Meat slots dropdown** (`.gui-slots__list`) | Old dark panel | No | **Yes** | Moved to thin wood frame on parchment under the HUD |
| **Road bar** (`.gui-roadbar`) | Old toast look | No | **Yes** | Moved to thin wood frame on parchment |

---

## 2. Details per screen

### 2.1 Onboarding
- **Before:** `.gui-onb__card` had dark slate background (`var(--panel)`), old border, gold heading (`var(--ok-head)`). Class cards (`.gui-onb__kin`) used dark panel tiles with gold headers. Floating setup card (`.gui-onb__setup`) used dark panel.
- **Move:** Scoped under `[data-look="camp"]`:
  - `.gui-onb__card`: thick wooden frame (`sprites/v4/ui/frame.png`), parchment ground (`sprites/v4/ui/parchment.png`), text in `var(--parchment-ink)`.
  - `.gui-onb__title`: Jersey 15 (`var(--type-kit-title)`).
  - Class cards (`.gui-onb__kin`): wooden bevels (`sprites/v4/ui/btn-wood.png`), text in `var(--kit-ink)`, name in `var(--type-kit-heading)`, active state (`.is-on`) pressed teal (`sprites/v4/ui/btn-teal-down.png`).
  - Tables & inputs (`.gui-onb__table`, `.gui-onb__warder`): sunken parchment wells (`sprites/v4/ui/well.png` / `#f6efdc`).
  - Floating setup card (`.gui-onb__setup`): thin wooden frame (`sprites/v4/ui/frame-thin.png`) on parchment.
  - Buttons (`.ok-btn`): already wear kit buttons (`btn-wood` / `btn-teal`).

### 2.2 Mission 1's quest log & finale toast
- **Before:** Already wore `.kit-frame-thin` and `.kit-paper` in `warchief.js` line 645. Toasts in `chrome.js` already wore `.kit-frame-thin.kit-paper` with pixel marks in signal colors.
- **Move:** Already conformant.

### 2.3 Settings (Town settings, Phones) & Modals (`.ok-dialog`)
- **Before:** `.ok-dialog` used dark slate background (`var(--panel)`), border `var(--frame-focus)`, rounded corners `var(--ok-radius-lg)`, gold heading. Warning dialogs had full yellow borders.
- **Move:** Scoped under `[data-look="camp"]`:
  - `.ok-dialog`: thick wooden frame (`border-image: frame.png 14 / var(--kit-frame) round`), parchment background (`sprites/v4/ui/parchment.png`), dark ink on parchment.
  - `.ok-dialog__title`: teal plate (`sprites/v4/ui/plate.png`), Jersey 15 heading (`var(--type-kit-heading)`), text in `var(--kit-ink)`.
  - `.ok-dialog__section`: Jersey 15 heading with engraved rule in parchment (`var(--kit-parchment-rule)`).
  - `.ok-dialog.is-warn`, `.ok-dialog.is-error`: keeps wooden frame; signal colors are restricted to icons/marks, never the frame.
  - `.gui-steps` / `.gui-steps__one`: wooden segmented control (`btn-wood.png` / `btn-teal-down.png` when active), Jersey 15 font.
  - Inputs & selects (`.ok-input`): sunken well (`sprites/v4/ui/well.png` / `#f6efdc`).

### 2.4 Build menu and its steps
- **Before:** Outer container in `warchief.js` line 634 was already `.kit-frame-thin.kit-paper`. Inner group words (`.gui-build__group-word`) were uppercase Nunito with dark rule lines.
- **Move:** Scoped under `[data-look="camp"]`:
  - `.gui-build__group-word`: Jersey 15 (`var(--type-kit-small)`), sentence case, rule line engraved in parchment (`var(--kit-parchment-rule)`).
  - Intent tiles (`.gui-build__tile`): wooden slot / bevel hover (`sprites/v4/ui/slot.png` / `slot-hover.png`), active/yours with teal/gold accent.

### 2.5 Improve
- **Before:** Bar panel in `warchief.js` was already `.kit-frame-thin.kit-paper`. Fixes dialog used `.ok-dialog`.
- **Move:** Moves onto kit automatically via `.ok-dialog` kit rules; day buttons wear kit buttons.

### 2.6 Workchief's chat
- **Status:** **Needs JS**. Town Hall Work view is omitted from the `PAPER` set in `windows.js`, so its panel does not receive `.kit-paper` styling. A CSS `:has()` workaround was tested in round 1 but removed in round 2 in accordance with tonight's limits (do not touch `.js` or `.py` files; screens needing JS changes are marked "needs JS" and left for a later round).

### 2.7 "Since your last look"
- **Before:** Rendered via `.ok-dialog` inside `.gui-lastlook` with dark slate background and old fonts. Quiet bar used dark panel.
- **Move:** Main dialog moves onto kit via `.ok-dialog` (thick wooden frame, parchment ground, teal plate heading, Jersey 15 sections). Quiet bar (`.gui-lastlook.is-quiet`) wears thin wooden frame on parchment.

### 2.8 Inside of the Task board
- **Before:** `.gui-inside__shop-frame` in `kit.css` already used thick wooden frame with teal caps, teal title plate, parchment ground, and Jersey 15 Exit button. Left booth uses pixel face for plaques and custom pixel art.
- **Move:** Already conformant. Added kit styling to `.gui-steps` inside the shop frame for Goal and Autonomy controls.

### 2.9 Search / command palette
- **Before:** Over bar in `warchief.js` already wore `.kit-frame-thin.kit-paper`. Commands list rendered with JetBrains Mono on parchment with teal selection.
- **Move:** Already conformant.

### 2.10 Meat slots dropdown (`.gui-slots__list`) & Road bar (`.gui-roadbar`)
- **Before:** Meat dropdown under HUD had dark slate panel with 2px stroke. Road bar had basic dark toast styling.
- **Move:** Meat dropdown moved to thin wooden frame (`frame-thin.png`) on parchment (`sprites/v4/ui/parchment.png`). Road bar moved to thin wooden frame on parchment.

### 2.11 Screenshot index 10: Settings (Phones)
- In round 1, screenshot 10 was skipped in the numbering sequence between 09 (Task board inside) and 11 (Meat slots dropdown). In round 2, `10-settings-phones.png` captures the Phones pairing section within Town settings, showing the kit's parchment and buttons.
