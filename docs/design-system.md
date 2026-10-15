# The design system

How Orkline looks, written down as data so that people, the GUI (the one face) and the orks that rebuild
buildings all follow the same rules. Background: [docs/design/gui-migration.md](design/gui-migration.md).
**Version 2** (2026-10-14) adds the new Camp's world: the card as a building, rails and mine carts, the orks, signals
and chips (§6–§9). **Version 3** (2026-10-14) makes it the brighter camp the owner approved: F1's palette as the
world tokens, the generated art shown at its own pixel (×1, never resampled), one track line with dirt paths, Nunito and a larger type scale
(§10). The full proposal, its audit and its open questions: [docs/design/design-system-v2.md](design/design-system-v2.md).

| What | Where |
|---|---|
| Tokens: font roles, colour roles, space | `orkcraft/design/tokens.json` (read by `design/tokens.py`) |
| A building's UI document, its schema | `orkcraft/schemas/building-ui.v1.json` |
| What each type's window has (its contract) | `orkcraft/design/buildings/<type>.json` |
| Checking a document, the rules a model gets | `orkcraft/design/ui.py` (`validate`, `RULES`) |
| The GUI's tokens, components, sprites, previews | `design-system/` (`tokens.json` → `tokens.css` by `python -m orkcraft.design.tokens`) |
| The new Camp's kits and sprite pipeline (v2) | `design-system/components.md` (Camp kit), `design-system/sprites/README.md` |
| The brighter Camp (v3): palette, scale, layout, type, the sheets awaited | [docs/design/design-system-v3.md](design/design-system-v3.md), `design-system/previews/CampKitV3.html`, `tools/camp_sheets_v3.json` |

## 1. Tokens: roles, not values

A document never says "18 px Almendra SC in #ff8c1a". It says `"font": "title", "tone": "fire"`, and each
face looks the role up.

**Font roles**

| role | for | GUI type style (camp / office) | (the old terminal's) |
|---|---|---|---|
| `title` | a building's name, a dialog's heading | `camp-heading` / `office-title` | bold |
| `heading` | a pane's or a section's heading | `camp-label` / `office-heading` | bold |
| `body` | running text: notes, Markdown | `camp-body` / `office-body` | as is |
| `mono` | code, diffs, paths, terminals, the editor | `code` / `code` | as is |
| `status` | the short live lines | `camp-caption` / `office-caption` | the view's muted colour |
| `label` | a field's or a column's name, a key | `camp-label` / `office-label` | bold, dim |
| `number` | counters, money, tokens, percentages | `camp-number` / `office-label` | bold |

The GUI's type styles, faces and colours are the GUI design system's
([design/gui-design-system.md](design/gui-design-system.md), `design-system/tokens.json`), the source
of truth: Camp sets headings in Pixelify Sans (Almendra SC is the wordmark's alone) and the rest in Titillium Web, Office uses the system UI
face, and both use JetBrains Mono for code; the War Map's title and lands are in Pixelify Sans, a pixel
face with Cyrillic for the names people give. The fonts ship with it (`design-system/fonts/`, OFL).
`orkcraft/design/tokens.json` maps each role onto it (`gui`), and the GUI wears them as the classes
`tokens.roles_css()` writes (`.ok-font-status`, `.ok-tone-fire`).

**Colour roles** (`tone`): `text`, `muted`, `accent`, `ok`, `wait`, `fire`, `error`; and the frame
and ground roles `canvas`, `surface`, `frame`, `frame_focus`, `road`, `road_selected`; and one per
harness (`harness.claude`, `harness.agy`, `harness.codex`, `harness.pipeline`). Camp and Office give
each role their own value: in the GUI the design system's colour token the role maps to (`fire` →
`alert`, `ok` → `success`, `surface` → `panel`, …), in `orkcraft/design/tokens.json` a hex kept from the removed terminal face. **`fire` means one thing only: something waits for the person.**

**Space**: steps 0–6, which are pixels (0, 4, 8, 12, 16, 24, 32).

## 2. A building's UI document

Every building has one. A building with no document of its own (nobody changed it) wears its type's
default. The document is kept in the building's entry of the Town Scroll (`ui`), so it is part of
every checkpoint, and `Z` takes a change back.

```json
{
  "version": 1, "type": "scrolls", "split": "column",
  "panes": [
    {"id": "head", "component": "status", "size": "auto", "font": "status"},
    {"split": "row", "size": 1, "panes": [
      {"id": "tree", "component": "tree", "size": 2, "font": "body"},
      {"id": "page", "component": "markdown", "size": 3, "font": "body"}
    ]}
  ],
  "note": "the page reads wider than the tree"
}
```

- **A pane** has an `id` from its type's contract and a `component`. It may also set `size`
  (`auto`, or 1–12 as a share of the room left), `font`, `tone`, `title` and `hidden`.
- **A group** has a `split` (`column`: one under another; `row`: side by side), panes, and
  optionally a `size`. Groups nest at most two deep.
- **The contract** of a type lists its panes, the components each may wear, and which panes are
  `required` (always there, never hidden) or `dynamic` (they show and hide themselves, like the
  Lake's editor). A type with no contract file is one pane, `main`: its own view.
- **Components** form a closed list: `status`, `text`, `markdown`, `diff`, `editor`, `list`,
  `table`, `tree`, `board`, `counter`, `chart`, `log`, `form`, `terminal`, `view`.

Contracts so far: 🌊 Lake (`head`, `view`, `editor`), 🌾 Task Fields (`board`), 🗑️ Scroll Dump
(`head`, `tree`, `page`). Every other type is one `main` pane for now. A type gets a contract when
its view is split into named panes (`TypedView.UI_PANES`).

**How the GUI draws it**: the groups exactly as written, a font role as its type style and a tone as its colour token
(`.ok-font-<role>`, `.ok-tone-<role>`). (The terminal face that drew it before was removed, [calm-town.md](design/calm-town.md) §9.)

## 3. Who changes a building's window

- **You, through its steward**: select the building, press **`D` 🎨**, and say what should change
  ("the tree narrower, the page larger"). The steward rewrites the document in one model call.
  It is checked against the contract, and a wrong answer goes back to the model with the problems.
  You see the new layout in one line. `Enter` keeps it, as a checkpoint `ui(<id>)`, and `Z` takes it
  back. Typing `default` puts the type's own layout back without a model call.
- **Not at night**: a new layout always waits for your `Enter`. The orks' own changes in quiet
  hours never touch a window.

## 4. The rules (what a model is given, word for word in `design/ui.py` `RULES`)

1. Change only what was asked, and leave every other pane as it is.
2. Use only the contract's panes, and for each only the components it lists. A required pane stays
   and is never hidden. A dynamic pane shows and hides by itself.
3. Name roles, never values. No colours, font names, pixel sizes or code.
4. Pick fonts by meaning: `title` for a name, `heading` for a pane, `body` for text, `mono` for
   code, paths and diffs, `status` for live lines, `label` for field names, `number` for counters
   and money.
5. Tones mean something: `ok`, `wait` and `error` as they say, and `fire` only for what waits for
   the person. Most panes have no tone.
6. Sizes: `auto` for a pane as tall as its content. Otherwise a share, and the pane people read
   most gets the largest one.
7. Put panes side by side only where both halves stay readable, such as a list beside its detail.
8. The town stays simple: a layout never adds roads, ports or settings to the map. A building's
   settings live in its window.
9. Give a pane a title only when its content does not say what it is.
10. Write the `note`: one sentence on what changed and why.

## 5. The town stays simple

These hold for any face, Office and Camp alike:

- There is one kind of edge, the road. A building has no ports or parameters on the canvas.
- On the map a building shows its name and up to three status lines. Its settings and its work
  live inside its window.
- Where a building stands is the person's choice, never an automatic layout.

## 6. Camp's world (v2): the grid, the projection, the layers

- **The art pixel is the unit; the grid is 8.** Every sprite is drawn at its final size, a multiple of 8 art pixels.
  Ground and track tiles are 32 × 32; the layout cell is 16.
- **Whole numbers only:** the zoom snaps to a ladder of **map ½** (the pipeline's half-size copies), **overview 1**
  and **close 2** CSS pixels per art pixel; on a fractional screen the camera picks the nearest whole device scale.
- **The card is the building's inside:** footprints XS 96 · S 120 · M 144 · L 168 art pixels wide (`footprint-*`),
  so at the close zoom the card keeps its width (192 · 240 · 288 · 336).
- **One projection, three-quarter top-down, never isometric;** light from the top left.
- **Layers, bottom to top:** ground · track · floors · buildings · carts · orks · covers · signals · chips · UI.
  Signals and chips never sort with the art. The product draws the shadows; the art carries none.

## 7. Colour: three families that never mix

| family | tokens | rule |
|---|---|---|
| **UI chrome** | `panel*`, `ink*`, `wood`, `bone`, `cloth`, `ink-wood`, … | text and frames; contrast as before (4.5:1 text, 3:1 frames) |
| **world** | `world-*` (grass, earth, water), `art-*` (wood, stone, iron, bone, cloth, skin, outline) | the sprites' palette and the map's ground; **no text is ever drawn on them** |
| **signals and chips** | `signal-ask` (yellow: a question), `signal-fire` (red: an error, 🔥), `signal-held` (⏳), `chip`, `chip-ink` | yellow and red appear nowhere else |

Today's dark Camp ground (`canvas`, the biomes' grounds) stays behind windows and today's cards; the new camp's grass
is the world layer. **Old names are aliases:** `frame` = `wood`, `frame-focus` = `bone`, `banner` = `cloth`,
`ink-gold` = `ink-wood` (same values in every theme; `tests/test_design.py` holds it). Road tokens keep `road-*`:
a road is a road, whatever Camp draws it as.

## 8. Signals and chips

1. **Badges only for exceptions:** ❓ (a question), `!` (stuck, an error), ⏳ (held). Normal work is motion.
2. **Words on chips, in the UI font** (`camp-chip` / `office-chip`), never pixel text on the ground. A waiting cart's
   chip is always shown.
3. **Sizes in CSS pixels at every zoom:** chip 20 high (24 on the phone, text never under 11); badge 20 (24 on the
   phone) with a 44 tap area.

## 9. Camp and Office

One layout, two drawings: every component of the Camp kit (`design-system/components.md`) has an Office drawing in the
same place with the same word (the table in [design-system-v2.md](design/design-system-v2.md) §9). Office has no world
art: its `world-*` and `art-*` fall back to its plain greys.

## 10. Version 3: the brighter Camp

[docs/design/design-system-v3.md](design/design-system-v3.md) in full; in short:

- **Palette:** the world tokens are F1's (meadow `world-grass` `#7cbd40`, sand paths `world-earth` `#e4b469`, honey
  wood, lilac stone, teal `art-cloth` and plum `art-cloth-plum`, turquoise water). The ground's band is luminance
  0.15–0.55; no art is as light as `signal-ask`; yellow and red stay the signals'. New UI tokens `parchment`,
  `parchment-ink`, `walnut`, `accent-teal` for the keeper's scroll and the panels.
- **Scale:** the generated art at its own pixel, ×1 (`art-scale`), never resampled; a slot is what the sheet draws: a
  core building about 190 px, an ork about 54 tall, a cart about 76 wide; each sheet at its own pixel, shown at a whole
  multiple (`show`, in the manifest); at most ten buildings on 1440 × 900. The zoom: ×1.5 by default on density 2
  (one art px = 3 × 3 device px), ×1 on density 1; the wheel ×1 · ×1.5 · ×2; map ½. The cutter keeps the art's colours and only reports the signals' hues.
- **Layout:** one main line; buildings joined to it by dirt paths; carts stop opposite a path, the keeper waits there
  and lifts the load off; the lookout tower in the low palisade with the way in at its foot, the catapult against it
  at the line's end; a building is one sprite with a door.
- **Signals:** 28 px on a dark plate with an outline and a keyline; a cart's flag outlined; they win by value.
- **Type:** Pixelify Sans for titles and chips, Nunito for labels (Cyrillic included), JetBrains Mono for the
  terminal; every Camp size a step larger; each style also a `--type-<style>` variable.

## 11. Version 4: Camp's chrome in wood, teal and parchment

[docs/design/design-system-v4.md](design/design-system-v4.md) in full; in short:

- **Only Camp's chrome changes** (the top bar, the command bar, the building panel, the scroll, the consoles, Items,
  the toasts, the inside's right panel); the camp's drawing, Office and every word stay as they were.
- **The kit:** thick wooden frames with a teal inner border and teal caps, parchment panels, bevelled wood and teal
  buttons, teal plates for headers, a column of icon tabs at a panel's side, framed counter chips, inventory slots;
  drawn in code by `tools/ui_kit.py` (nine-slices at 2 CSS px an art pixel), worn through `design-system/kit.css`
  (the `.kit-*` classes, Camp only) and `orkcraft/gui/static/kit.css` (today's components). Preview:
  `design-system/previews/UIKitV4.html`.
- **Tokens added:** `kit-*` colours (wood, teal, sunk parchment, `kit-ink`), sizes (`kit-frame`, `kit-hud-h`, …) and
  type styles. Yellow and red stay the signals'.
- **Type:** Jersey 15, a pixel face, for headings, numbers and buttons only (`--font-kit`); every sentence stays Nunito,
  code JetBrains Mono, the wordmark New Rocker.
