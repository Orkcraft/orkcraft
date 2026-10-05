# Orkcraft GUI design system

The files live in [`design-system/`](../../design-system/): `tokens.json` (and the generated `tokens.css`), `components.css`, the sprites and a browser preview of every component. The component notes are in [`design-system/components.md`](../../design-system/components.md); the sprite brief is in [sprites.md](sprites.md) and the building prompts in [building-prompts.md](building-prompts.md).

Orkcraft runs many coding agents in one project as a real-time strategy game. The GUI shows the same town in two looks, built on **one set of semantic tokens**.

- Switch looks by setting `data-theme` on a root element. The markup never changes.
- This mirrors `realm/modes.py`: the data is identical in both looks, and only the presentation differs.

| Look | Theme ids | References | Feel |
|---|---|---|---|
| **Camp** (immersion) | `camp` (forest, the default), `camp-ice`, `camp-void` | Warcraft 2 × Factorio | Pixel-art header sprites on every building, square bevelled stone and oak panels, gold labels, hard shadows, fire |
| **Office** (hidden) | `office` | VS Code layout in Camp's colours | Editor chrome: flat panels, hairlines, rounded controls, smooth progress bars, a status bar, no emoji and no sprites. Its palette is Camp's, calmer: warm dark browns, gold accents, moss green, so switching modes feels like one product |

**Shift** is not a third look. It is Office during office hours on office days and Camp at other times, so the app swaps `data-theme` at runtime.

There is no terminal styling in the GUI. ASCII silhouettes, box drawing and `[bracket]` buttons belong to the TUI only. The mono face (`code`) is used only for code, diffs, logs and terminals.

## Content fundamentals

- **Wording.**
  - In everything a person reads, write **ork / orks / Ork** and **orkestration / orkestrate**, never "orc" or "orchestration".
  - The top onboarding level is **Punk ork**.
  - Code identifiers (`orc_id`, `realm/orcs.py`, CSS ids) keep their old spelling.
- **Voice.**
  - Short and plain, in sentence case.
  - Actions lead with a verb: "Draft the blueprint", "Halt All", "Open in browser".
  - Status lines are terse fragments, such as `Branch main · 2 merged today` or `All quiet · $0.00 / $5`.
- **Game nouns are the product nouns.** Building, hut, ork, garrison, road, cart, orkspace, War Map, Town Hall, orders.
  - Camp shows them with sprites. Until the sprites exist, it uses the TUI's pictographs (none left: every Camp pictograph now has a sprite); the ork and its states, the fire, the resources, the chain marker and the tiers already have their sprites.
  - Office says them in words: Agents, Spend, Context, `?`, `busy`.
- **Questions are fire, not dialogs.** An ork never opens a dialog. When it needs you, its building burns (Camp) or turns red (Office), and you answer in Orders (`!`). Toasts only inform.
- **Separators.** Use `·` between facts, `→` for flow (`pit → lake`, `✻→✦`), and `—` before an explanation.

## Visual foundations

### Colour

Every colour is a token with one value per theme. Use the token, never the hex.

- **Grounds.**
  - `canvas`: the town ground.
  - `panel`: window, card, dialog and menu interiors.
  - `panel-inset`: wells (inputs, lists) and Office's tab and title bars.
  - `panel-raised`: Camp faces (buttons, title bars, HUD) and Office button fills.
  - `selection`: the selected row.
- **Text.**
  - `ink` is the default on every ground.
  - `ink-muted` is for status lines and hints on `panel`, `panel-inset` and `canvas`.
  - `ink-gold` is Camp's voice: button labels, window titles, HUD numbers.
  - `ink-comment` is only for disabled text. It is below 4.5:1 by design.
- **Frames.**
  - `frame` is the inactive border. It is decorative and never the only cue. In forest it is muted bronze gold, so every card and window reads as a gilded frame; ice and void keep their biome borders.
  - `frame-strong` is for control borders and is at least 3:1.
  - `frame-focus` marks focus everywhere and is at least 3:1 on every ground. It is bright gold in forest (a clear step above the bronze `frame`), gold in void, blue in ice, and the same gold in Office.
- **Signals.** Put signal text only on `panel`, `panel-inset` or `canvas`.
  - Always pair the colour with a mark: `success` with ✓, `danger` with ✗, `warning` with ⚠. `info` is for links and Office text actions.
  - `alert` means a question is waiting. `alert-hot` means it has waited 30 s or more; use it only for fills, frames and icons.
  - The fire set (`fire-glow`, `fire-ember`, `fire-ground`, `fire-ground-hot`) is the burning building in Camp.
- **Domain colours.**
  - Harness marks: `harness-claude` ✻, `harness-agy` ✦, `harness-codex` ⌬, `harness-pipeline` P.
  - Tiers: `tier-elder`, `tier-warrior`, `tier-laborer`.
  - Day bar: `day`, `day-quiet`, `day-office`, with `quiet-ink` for its text.
  - Roads: `road`, `road-bright`, `road-selected`.
  - Carts: `cart-held`, `cart-error`, `cart-filtered`.
  - Meters: `meter`. It is tan gold in every look, kept apart from the brighter `warning` yellow.
  - Pull requests: `pr-merged` (open is `success`, closed `danger`, draft `ink-muted`).
  - Task cards: `sticky-*` tints fill a card in Camp. `mark-*` are the colour squares Office puts before a card title.

### Type

| Look | Headings | UI, body and numbers | Code |
|---|---|---|---|
| Camp | `display`: Almendra SC, a calligraphic small-caps serif that echoes the gold wordmark (`camp-title`, `camp-heading`) | `camp`: Titillium Web, the Factorio UI face (`camp-label` in uppercase, `camp-body`, `camp-caption`, `camp-number` with tabular figures) | `mono` (`code`) |
| Office | `office`: the system UI stack, as VS Code uses (`office-title`, and `office-heading` at 11px uppercase) | `office` (`office-label`, `office-body`, `office-caption`) | `mono` (`code`, `code-small`) |

- Keys are written as words (`Ctrl+S`, `F10`).
  - In Camp they are engraved gold `ok-kbd`.
  - In Office they are VS Code keycaps.
- Camp labels and buttons are uppercase with 0.06em tracking.
- Office uses sentence case, except for its 11px section headers.

### Shape, depth and spacing

- **Radii.**
  - Camp is square everywhere (`radius-0`).
  - Office uses `radius-sm` for buttons and inputs, `radius-md` for cards, menus and toasts, `radius-lg` for windows and dialogs, and `radius-full` for meters, the day bar, chips and pills.
- **Strokes.**
  - Camp uses the 2px `border-bevel` for bevels, cards and focus, and the 4px `border-frame` for windows and dialogs.
  - Office uses the 1px `border-hair` everywhere.
- **Depth.**
  - Camp has no blur. `bevel-raised` has a lit top/left edge and a dark bottom/right edge, like Warcraft 2 and Factorio buttons. `bevel-sunken` is its reverse, used for wells and presses. `shadow-window` is a keyline plus a hard 4px drop.
  - Office is flat. `shadow-window` is a soft widget shadow.
- **Spacing.**
  - The scale runs from `space-1` to `space-8` (4 to 32px).
  - Camp pads controls with `space-3` and panels with `space-4`.
  - Office pads with `space-2` and `space-3`.
- **Heights.**
  - Controls: `control-camp` (32px), `control-office` (26px).
  - HUD: `bar-hud`.
  - Office tab bar: 35px. Office status bar: 22px.

### Progress

- **Camp:** a 12px sunken trough with a gold bar that has a lit and a dark edge, like Factorio. A busy bar shows a striped belt.
- **Office:** a smooth 6px rounded track.
  - The fill eases to new values over 0.3 s.
  - An indeterminate bar is a short gold bar that sweeps across, like VS Code's progress strip.
  - The motion stops under `prefers-reduced-motion`.

### Focus

Focus is always a solid `frame-focus` ring, never colour alone:

- **Camp:** a 2px outline, offset by 2px.
- **Office:** a 1px border.

It is at least 3:1 against every ground in all four themes.

### States and motion

**Fire** (the stages come from `modes.py`). In Camp:

- **0 s:** the card or window gets an `alert` frame with the `glow-fire` halo, its panel turns `fire-ground`, and the building glows `alert` from behind.
- **30 s:** the frame and glow turn `alert-hot`, and the panel `fire-ground-hot`.
- **60 s:** flame sprites start appearing over the header, until it is covered at 5 min. The flames flicker every 0.4 s.

In Office, only the outline and name turn red-orange (`alert-hot`), and `?` follows the name.

**When fire stops.** Nothing flickers in 🌙 quiet hours (a ❓ follows the name instead) or under `prefers-reduced-motion`.

### Ground

- **Camp:** one flat colour per biome (`canvas`), with no patches and no texture. On it go 5–7 small decorations per screen — trees, icy mountains, rocks — that are quiet silhouettes and never touch a card. See Ground and Sprites.
- **Office:** a plain `canvas`.

## Iconography and sprites

- **Camp: pixel art in the style of Warcraft 2.** Headers and banners are **flat 2D front views** with a transparent background and no ground strip. The building stands on the top edge of its card or window, its roof rising over the map ground. Frames, selection and fire light only the card, and the selected building glows softly from behind in its frame's colour. Only ground and road tiles are top-down. Each building carries two header sprites:
  - a small, compact building (2:1) centred on its hut card's top edge, from 64×32 to 112×56 by catalog size;
  - a 128×64 version of the same building on its opened window (`banner-w` × `banner-h`).
  - Both are drawn with very little detail in the frame's own muted colours, so they read as part of the frame, not as pictures.
- **Other Camp art:**
  - command buttons (`icon-command`, 32px);
  - HUD resources and carts (`icon-resource`, 16px);
  - the ork (`ork-w` × `ork-h`, 16×15) wherever 🧌 stood, and ork portraits (`portrait-w` × `portrait-h`, 46×38);
  - fire overlays.
- **Rendering:** always `image-rendering: pixelated`, at 1× or a whole multiple. The full brief is in the Sprites section.
- **Until sprites exist:** Camp uses the TUI's pictographs, wrapped in `<i class="ok-ico">` so Office can drop them.
  - Resources now have sprites: an hourglass (quota), coins (spend), logs (context) and meat (agents), in `icons/res-*.png`.
  - Orks: the chain or script has its signpost sprite (`icons/chain.png`). The agent ork already has its sprite (`orks/ork.png`, 16×15) and no longer uses 🧌.
  - Status is the ork's face: `orks/ork-idle.png` asleep, `ork-busy` sweating, `ork-waiting` with a flame on its head.
- **Office: no emoji and no sprites** (`modes.strip_emoji`).
  - Words in `<span class="ok-word">` replace pictographs: Quota, Spend, Context, Agents, `busy`, `?`.
  - Icon buttons become text actions.
  - Status is a coloured dot next to a word.
  - The text glyphs ✓ ✗ ⚠ · → stay, as do the harness marks ✻ ✦ ⌬.
- **Sprites group.** Finished sprites live here, starting with The Forge: a 137×114 header, trimmed to the building with no ground strip, and its @2x copy.
- **Brand** (Brand group).
  - The gold wordmark is for the splash screen and onboarding.
  - The ork mascot is for Camp onboarding and empty states.
  - Office sets the name in plain type.

## Components

Every component card shows the same markup in Camp and Office side by side.

- Load `components/bundle.css` after `tokens.css`.
- Its knobs (`--ok-font`, `--ok-radius`, `--ok-control`…) follow `data-theme`.

| Group | Components |
|---|---|
| Town | Town (real sprites together), Window (banner + bar), Hut (card + header), Ground (map, decorations), Sprite (every slot size), Badge, Road |
| Buildings | Forge (branches, pull requests, the merge), TaskFields (the board of tasks and notes, with ticket cards) |
| Chrome | Hud, WarMap (and every list: roster, Command Card, F10 menu), KeyFooter |
| Controls | Button (and the building action `ok-act`), Tabs, Input, Checkbox |
| Overlays | Dialog, Toast |
| Data | Meter, DayBar |
