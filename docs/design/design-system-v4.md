# Design — the design system, v4: Camp's chrome in wood, teal and parchment

Status: step 1 of 3 (V4, [decisions-2026-10.md](decisions-2026-10.md) §17.1), 15 October. The target is the owner's
frame [img/references/v4/target-ui.jpg](img/references/v4/target-ui.jpg): thick wooden frames with a teal inner border,
parchment panels, square bevelled icon buttons, a column of icon tabs at a panel's side, counters in framed chips,
tab headers on teal plates, inventory slots. Today's Camp, for comparison: [img/loop/depot-busy.png](img/loop/depot-busy.png).

What v4 changes is **the interface's chrome in the Camp look only**. The camp's drawing (ground, track, buildings,
orks, carts) is LOOP's and the art session's, and stays as v3 has it. **Office is not changed** (calm, monochrome); a
look changes how a thing is drawn, never its word (CLAUDE.md). The target's words ("ORC LIST", "BEHAVIOR EDITOR") are
only a picture: v4 writes today's words, orks by their orkish names, buildings by what they do.

| | where |
|---|---|
| the pieces, drawn in code | `tools/ui_kit.py` → `design-system/sprites/v4/ui/` (`<piece>.png`, `@2x`, `kit.json`) |
| the tokens (added, none renamed) | `design-system/tokens.json` → `tokens.css`: `kit-*` colours, `kit-*` sizes, the `kit` family, the `kit-*` type styles |
| the pixel face | `design-system/fonts/jersey-15-latin-400-normal.woff2` (OFL, `OFL-Jersey-15.txt`), in `fonts.css` |
| the comparison of faces | [img/v4/pixel-faces.png](img/v4/pixel-faces.png) (density 2), [img/v4/pixel-faces-dpr1.png](img/v4/pixel-faces-dpr1.png) |
| the preview (step 2) | `design-system/previews/UIKitV4.html` |

## 1. Rules

1. **Wood, teal, parchment.** Frames are wood (`kit-wood*`, darker than the art's honey wood so a frame never reads as
   a building) round a teal inner border (`accent-teal`, `kit-teal-*`); panels are parchment (`parchment`, a step
   sunk: `kit-parchment-deep`). **Yellow and red stay the signals'** (❓, `!`, 🔥, design-system-v3 §5): no frame,
   button or plate wears them. Stop all is a teal button, as v3's HUD had it.
2. **One art pixel is 2 CSS px**, at every zoom (`kit-px`). Every piece is drawn on that grid and shown at a whole
   multiple: `<piece>.png` is 2 image px an art px (density 1), `<piece>@2x.png` 4 (density 2), both
   `image-rendering: pixelated`, chosen with `image-set()`.
3. **A piece is a nine-slice.** CSS takes it as `border-image`: the slice and the border width are the piece's inset
   ×2 (CSS px); the edges `repeat` (`round` for the frame, so its grain never stretches). The panel's own background
   (parchment, or the console's dark) shows inside.
4. **Pixel face for headings, numbers and buttons only** (the owner): `--font-kit`, Jersey 15. Settings, waybills,
   consoles, chat and every sentence keep Nunito (`camp-body`, `camp-label`, `camp-caption`) and JetBrains Mono. The
   wordmark stays New Rocker. Case is as written: no `text-transform` (the words are today's, and so is their case).
5. **States are pieces, not filters:** a button has `-hover`, `-down` (the bevel turned over) and `-off` (a flat
   parchment face); a tab `-hover` and `-on`; a slot `-hover` and `-on`. Focus is a 2-px `kit-ink` outline 2 px out,
   on every control.
6. **Only Camp wears the kit:** every kit rule is scoped `[data-look="camp"]`. In Office the same markup is drawn by
   its own rules, unchanged.

## 2. The pieces

Sizes and insets in art px (×2 for CSS px). Drawn by `tools/ui_kit.py`; nothing generated, nothing measured off the
target by a tool. `kit.json` beside the files carries the same numbers.

| piece | size | inset (slice) | what it draws | states |
|---|---|---|---|---|
| `frame` | 22 × 22 | **7** (14 CSS px, `kit-frame`) | outline · wood lit above, wood, wood shaded below (with grain) · walnut · teal lit · teal shade; **teal caps** 7 × 7 with a rivet at the four corners | — |
| `frame-thin` | 22 × 22 | 7 | the same rings without the caps | — |
| `bar` | 16 × 16 | **5** (10, `kit-bar`) | outline · wood lit, wood, wood shaded · walnut | — |
| `well` | 8 × 8 | **2** (4) | a rule line engraved in parchment, a shade along its top and left | — |
| `btn-wood` | 10 × 10 | **3** (6, `kit-bevel`) | outline · bevel lit top-left, shaded bottom-right · wood face (`fill`) | `-hover`, `-down`, `-off` |
| `btn-teal` | 10 × 10 | 3 | the same in teal: the primary, the active, Stop all | `-hover`, `-down`, `-off` |
| `plate` | 10 × 10 | 3 | a tab header's teal plate: lit top row, shaded bottom | — |
| `tab` | 12 × 12 | **4** (8) | an icon tab at a panel's left: outline on three sides, open on the right where it meets the frame | `-hover`, `-on` (teal) |
| `slot` | 10 × 10 | 3 | an inventory slot sunk into parchment: wood rim, shade top-left, light bottom-right | `-hover` (rim lit), `-on` (teal rim) |
| `band` | 6 × 6 | **2** (4) | a section's wooden strip across a panel (outline above and below) | — |
| `parchment` | 32 × 32 | — (a tile) | parchment with a few fibres, seamless | — |

**Sizes of the controls** (tokens, CSS px): the top bar `kit-hud-h` 56 (a 36-px row inside its 10-px frame); a
square icon button `kit-icon-btn` 36 (a 20–24 glyph inside); an icon tab `kit-tab` 44 (its icon 24); a slot
`kit-slot` 48 (its item 32, its count in the lower right in `kit-small`); a text button 36 high, 12 px of padding.

**Icons** on icon buttons and tabs are today's sprites (`design-system/sprites/icons/`, the harness marks, the ork
faces) or a glyph in `--font-kit`; a missing icon is drawn into `tools/ui_kit.py` from a pixel grid (as
`tools/logo.py` draws the mark), never generated.

**Textures.** Every piece above is flat pixel colour and needs no image model. If the owner wants a painted wood grain
or a parchment with stains later, that request goes to the art session through the PM session (§7), and its result
replaces `frame` / `parchment` under the same names and insets.

## 3. Tokens (added in `design-system/tokens.json`; none renamed)

Colours (Camp; Camp's other biomes the same; Office maps each to its own frame, hairline, panel and ink):

| token | Camp | for | reads |
|---|---|---|---|
| `kit-wood` | `#6b4631` | frames, a wooden button's face, a tab | `kit-ink` on it ≥ 4.5:1 |
| `kit-wood-light` | `#8e5f40` | the lit ring, a bevel's top | |
| `kit-wood-dark` | `#47301f` | the shaded ring, the grain, a slot's rim | |
| `kit-wood-hover` | `#7c5339` | a wooden button or tab under the pointer | `kit-ink` ≥ 4.5:1 |
| `kit-teal-light` | `#3a8a87` | the inner border's lit ring, a cap's bevel | |
| `kit-teal-dark` | `#133f3e` | the inner border's shade, a teal bevel's bottom | |
| `kit-teal-hover` | `#276f6d` | a teal button under the pointer | `kit-ink` ≥ 4.5:1 |
| `kit-parchment-deep` | `#dccb9f` | a slot's inside, a sunk field, the fibres | `parchment-ink` ≥ 7:1 |
| `kit-parchment-rule` | `#b39a6c` | a line engraved in parchment, a disabled face | |
| `kit-ink` | `#f3ead0` | words and glyphs on wood and teal | |

Kept from v3 and used as they are: `parchment`, `parchment-ink`, `walnut`, `accent-teal`, `art-outline` (every
outline), `chip`/`chip-ink` (the map's chips, unchanged). `tests/test_design.py` holds the contrasts above and that no
`kit-*` tone is a signal's yellow or red.

Sizes: `kit-px` 2, `kit-frame` 14, `kit-bar` 10, `kit-bevel` 6, `kit-hud-h` 56, `kit-icon-btn` 36, `kit-tab` 44,
`kit-slot` 48. Family: `--font-kit: "Jersey 15", "Pixelify Sans", "Nunito", sans-serif`.

## 4. Type: the pixel face

**Jersey 15** (Soft Type, SIL OFL 1.1), chosen from three candidates set on the same pieces at the HUD's sizes
([img/v4/pixel-faces.png](img/v4/pixel-faces.png); at density 1: [pixel-faces-dpr1.png](img/v4/pixel-faces-dpr1.png)):

| candidate | verdict |
|---|---|
| **Pixelify Sans** 500 (shipped since v3) | **out for numbers:** its 5 is drawn like its S (`$5.00` reads `$S.00`, `550` reads `SS0`), its 8 close to its B, and at density 1 the figures blur further. Wide, so the top bar's counters do not fit beside Stop all. Kept where it is today (the map's chips, the War Map, `camp-title`/`camp-heading`) and as the Cyrillic fallback. |
| **Jersey 15** 400 | **chosen.** Every figure unambiguous (0/O, 1/l/I, 5/S, 8/B, 2/Z, 6/G); heavy strokes that hold on teal, wood and parchment alike; condensed, so `Spend $0.42 / $5.00 · Context 92k / 128k · Orks 3/5` fits the bar; tabular-looking figures; the closest to the target's lettering. Its letters are smaller for their size, so it is set about a quarter larger (its capitals then match the others'). Latin only: a Cyrillic orkspace name falls back to Pixelify Sans's Cyrillic, already shipped. |
| **Tiny5** 400 | readable, with Cyrillic, but its 5 and S and its 8 and B are near twins, its `%` and `$` break up at 16, and its very wide letters cost a third more width than Jersey 15. |

Its pixel is 1/27 em (50 units of 1350): crisp at 27 CSS px, and at 13.5 on a density-2 screen; the sizes between are
smoothed by the browser and stay sharp enough on density 2 (the shots).

| style | size / line | for |
|---|---|---|
| `kit-title` | 27/32 | a panel's or a dialog's title |
| `kit-heading` | 22/24 | a tab plate's header, a section heading on parchment, a band's word |
| `kit-number` | 22/24 | the top bar's counters; any number read at a glance (tabular figures) |
| `kit-button` | 20/24 | the words on a button, a tab's badge |
| `kit-small` | 16/16 | a slot's count; never a sentence |

Everything else (`camp-body`, `camp-label`, `camp-caption`, `code`) is unchanged. A long name in a heading is cut with
an ellipsis, never wrapped in the pixel face.

## 5. Piece by piece onto today's components

The order is step 3's. Class names are today's (`orkcraft/gui/static/`, `design-system/components.css`); each keeps
its markup and its words, and gains the kit in Camp by `[data-look="camp"]` rules in one sheet,
`orkcraft/gui/static/kit.css`, loaded after the others.

| today | v4 in Camp |
|---|---|
| **The top bar** `.ok-hud.gui-hud` (js/chrome.js): the brand, Menu, the score, the hour, Spend, Context, Orks | the strip on `bar` with parchment inside, 56 high; the brand in New Rocker on the wood at the left; each counter group (`.ok-res`, `.gui-score…`, `.gui-slots…`) a `well` chip on the parchment with its sprite and its number in `kit-number`, its word in `camp-label`; Menu a `btn-wood` |
| Stop all `.gui-hud__stop` (js/slots.js) | a `btn-teal` at the bar's right end, `kit-button` |
| the hour `.gui-hour__dial` and its menu | a square `btn-wood` icon button (`kit-icon-btn`) holding today's sun/moon sprite; the menu on `frame-thin` with parchment |
| **The command bar** `.gui-warchief__bar` (js/warchief.js) | `bar` round it; the Workchief's face in a square `well`; Build, Answers (n), Improve, Open and the quick actions `.gui-warchief__act` as `btn-wood`; Build when open, Open and `.ok-btn.primary` as `btn-teal`; the input `.gui-warchief__input` a `well` on parchment in Nunito |
| the panels over it `.gui-warchief__over` (the Workchief's thread, Build, Improve, set-up) | `frame-thin` on parchment; their text stays Nunito |
| **The building panel** `.gui-panel` with `.ok-win` (js/windows.js), its tabs `.ok-tabs .ok-tab` (Work/Card, Info, documents) | the panel on `frame` (caps); its title on a `plate` across the top edge in `kit-heading`; **the tabs become a column of icon tabs** on the panel's left (`tab`, `-on` for the open one), each with its icon and its word as the tooltip and accessible name; close, whole town and more as square icon buttons in the plate's row |
| the scroll `.gui-camp__scroll` and its quick actions `.gui-camp__scroll-acts` (js/camp/steward.js) | the scroll's head stays its sprite; its body on `frame-thin` and the `parchment` tile; the title in `kit-heading`; actions `btn-wood`, the primary `btn-teal` |
| **The ork's console sheet** `.gui-orkconsole` (js/orkconsole.js) | on `frame`; its header (the ork's name, its role) on a `plate`; its sections under `band`s; the terminal and logs inside keep the console's dark ground and JetBrains Mono |
| **The Items panel** `.gui-items` and its toggle `.gui-items__toggle` (js/camp/items.js) | the toggle a `btn-wood`; the panel on `frame` with a `band` heading "Items"; each item `.gui-items__row`'s picture in a `slot` (`-hover` under the pointer, `-off` look when it stands in the camp); the Workchief's notes and the hint stay Nunito |
| **The quest log** (js/mission.js in `.gui-warchief__setup`) | `frame-thin` on parchment; its objective's heading in `kit-heading` on a `plate`; its one press a `btn-teal`; the jokes and lines Nunito |
| **The toasts** `.gui-toast.ok-toast`, `.gui-toolerr` (js/chrome.js) | `frame-thin` on parchment; the mark (✓ ⚠ ✗) in a small square `well`, ✗ keeps the signal's red as it is a signal; copy and close square icon buttons |
| **The Task board's inside, its right panel** (`js/buildings/fields_inside.css`) | `frame` with a `plate` header; the counts in `kit-number`; its rows on parchment; its buttons `btn-wood`/`btn-teal` |
| the map's chips, names and badges `.gui-camp__chip`, `.gui-camp__name`, `.gui-camp__badge` | **unchanged** (layers 8–9 are v3's, design-system-v3 §5) |

## 6. Steps and checks

1. This document, `tools/ui_kit.py` and its pieces, the tokens, the face. Checks: `tests/test_design.py`
   (the tokens, the kit's pieces are the drawer's output, the contrasts), `tests/test_architecture.py`.
2. `design-system/previews/UIKitV4.html`: every piece and state, the type, and a mock of the top bar and one side
   panel over a Camp screenshot. Shots at 1440 × 900, density 2, into `img/v4/`.
3. Camp's real chrome, in §5's order; the browser tests stay green; shots into `img/v4/`, beside the target.

## 7. For the owner and the other sessions

- **No texture needs an image model** for now (§2, Textures). If one is wanted, V4 writes the request for the art
  session and sends it to the PM session; V4 never calls a model itself.
- LOOP changes `js/camp/` at the same time: v4 stays in the UI layers (`kit.css`, the chrome's components), never in
  the camp's drawing.
