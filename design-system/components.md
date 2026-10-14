# Components

Every component shows the same markup in Camp and Office. Open `previews/<Name>.html` in a browser to see it; each preview loads `../tokens.css` and `../components.css`.

## Badge
A garrison badge: who lives in a building, which harnesses run it and what it is doing. It sits on the right of a window title and on roster rows.

**Markup**
- `.ok-badge` holds, in order:
  - The kind: the 24×16 ork head (the ork mark), in its state: `orks/ork.png` at rest, `ork-idle` asleep with its eyes shut (was 💤), `ork-busy` with a drop of sweat (was ⚙), `ork-waiting` with a flame on its head (was 🔥). The base ork head (`orks/ork.png`, `<img class="ok-sprite" data-kind="ork">`) for an agent, the 16×16 signpost (`icons/chain.png`, `data-kind="chain"`, was 🪧) for a chain or script, and both for a hybrid. It sits inside the plate. Office hides the sprite and shows the name alone.
  - The name.
  - The harness scheme: `ok-h-claude` ✻, `ok-h-agy` ✦, `ok-h-codex` ⌬ or `ok-h-pipe` P, with steps joined by `ok-arrow` →. A scheme longer than three steps is written `first→last·N`. Camp draws each mark as its 16×16 pixel sprite (`icons/harness-*.png`, `<img data-kind="harness">`) and the arrow as `icons/harness-arrow.png` (js/icons.js `Scheme`, `ToolMark`); Office shows each AI tool as its small SVG in the tool's colours, the P and the arrow as text.
- States: `is-alert`. Tiers are coloured with `tier-*` and carry their 16×16 icon (`icons/tier-elder.png` an orb, `tier-warrior` crossed swords, `tier-laborer` a pickaxe; `data-kind="tier"`), which Office hides.

**Camp.** A sunken square plate.

**Office.** A pill with a hairline.

**Both.** The harness marks are never emoji: pixel sprites in Camp, small coloured SVGs (a tool) and text (P, →) in Office. On a hut card the lead's head and its scheme stand bare after the name, no plate (js/hut.js `Keeper`).

## Button
A command. Use `ok-btn` for buttons in dialogs and panels, with one `primary` per dialog. Use `ok-act` for the actions a building offers.

**Markup**
- `<button class="ok-btn">`, with the modifiers `primary`, `danger`, `is-pressed`, `is-focus` and `disabled`.
- A key hint goes in a trailing `<span class="ok-kbd">`.
- A pictograph goes in `<i class="ok-ico">`, so Office drops it.
- Building actions: `<button class="ok-act" title="Run">`, holding `<img>` (the 32px command icon sprite) or `<i class="ok-ico">` until the sprite exists, followed by `<span class="ok-act__label">Run</span>`.

**Camp (1990s real-time strategy × Factorio)**
- `ok-btn` is a square stone face (`panel-raised`) with `bevel-raised` and an uppercase `camp-label` in `ink-gold` (light wood). Pressing swaps it to `bevel-sunken`. `primary` uses the Factorio confirm green (`action`).
- `ok-act` is a 40px square command button carrying an `icon-command` sprite, like a 1990s real-time strategy command card. Its label is only the tooltip.

**Office (VS Code)**
- `ok-btn` is flat with `radius-sm`, regular weight and a hover wash. `primary` uses `action` green. `danger` is outlined.
- `ok-act` becomes a text link in `info`, like a view-toolbar action. The icon is hidden and the label shows.

**Do.** Write labels as a verb and an object ("Draft the blueprint", "Halt All"), and write ork, never orc.

**Don't.**
- Don't put two `primary` buttons side by side.
- Don't make an icon-only `ok-btn`.
- Every `ok-act` needs its label, because that label is all Office shows.

## Checkbox
Multi-choice marks (the carts a building takes, the events it sends) and single-choice chips (the onboarding levels).

**Markup**
- `label.ok-check` › `<i>` holding ✓ or nothing, then the label.
- `.ok-chip`, with `is-on` on the chosen one.
- The onboarding levels are 🐣 New to it · 🪓 Some · 🤘 **Punk ork**.

**Camp.** A sunken square with a green ✓. The chosen chip is raised, its label in `ink-gold` (light wood).

**Office.** A VS Code checkbox: checked is filled `frame-focus`. Chips are pills.

## DayBar
Your day from 00:00 to 24:00, one cell per half hour.

**Colours**
- `day` amber: waking hours.
- `day-quiet` purple: 🌙 quiet hours.
- `day-office` grey: office hours (Shift only).
- Half purple, half grey where quiet and office hours overlap.

**Markup**
- `.ok-day` › `.ok-day__cells`, holding 48 spans: none, `q`, `o` or `qo`. Add `now` to the current cell.
- Then `.ok-day__ticks`.

**Camp.** Separate bevelled cells.

**Office.** One smooth rounded bar, with a 2px marker for now.

## Dialog
A modal: the Builder chat, Orders, Confirm, F10 settings. It is the only place a primary action lives.

**Markup**
- `.ok-dialog` holds, in order:
  - `.ok-dialog__head`, with an optional `.ok-dialog__portrait` and `.ok-dialog__title`.
  - `.ok-dialog__text`.
  - `.ok-dialog__section` labels and any controls.
  - `.ok-dialog__hint`.
  - `.ok-dialog__actions`.
- Variants: the default (`frame-focus`), `is-warn` (proposals, Confirm), `is-error` (build failed).

**Camp**
- A 1990s real-time strategy panel: a square 4px warm wood frame (`frame`) with a hard drop; the active window's frame turns bone (`frame-focus`) and its title bar is maroon cloth (`banner`).
- The speaker's 46×38 portrait sits beside a `camp-title` heading. The Builder has his (`portraits/builder.png`: an old ork in a dented helmet with a candle stub, round spectacles, a grey beard and a blueprint behind one ear); the asking ork uses `orks/ork-portrait.png`.
- Actions are left-aligned, with the primary last.

**Office**
- A VS Code dialog: a hairline frame, `radius-lg`, a soft shadow and a 16px semibold title.
- No portrait.
- Actions are right-aligned, with the primary last.

**Rule.** Agents never open dialogs; a question from an ork sets its building on fire.

## Forge
The Forge opened: every branch with its pull request and changes, the selected branch in detail, and the merge (see `screens/typed/git_view.py`, `realm/forge.py`).

**Markup**
- `.ok-forge` holds `ul.ok-branches` on the left and `.ok-detail` on the right.
- Each branch is `li.ok-branch`, holding:
  - `.ok-branch__cur` (● on the checked-out branch);
  - `.ok-branch__name`;
  - an optional `.ok-pr` with `data-state` set to `open`, `draft`, `merged` or `closed`;
  - `.ok-branch__stat`, holding `.ok-add` +N, `.ok-del` −N and `.ok-ab` ↑ahead ↓behind.
- Add `is-selected` to the selected branch.
- `.ok-detail` holds, in order:
  - `.ok-detail__head` (⎇ name and the PR pill);
  - `.ok-detail__pr` (the title and the Open PR link);
  - `.ok-detail__meta` (ahead/behind the base, files, +/−);
  - `ul.ok-commits` › `.ok-commit` (a `code` hash, the message, `.when`);
  - `ul.ok-files` › `.ok-file` (the path, +/− counts, a `.ok-file__bar` with `.a` and `.d` parts scaled to the branch's largest change);
  - a `Meter` with `is-busy` while a merge runs its tests;
  - `.ok-detail__actions`;
  - `.ok-detail__result` for the last merge (✓ merged, ✗ conflicts or red tests).
- PR colours: open is `success`, merged is `pr-merged`, closed is `danger`, draft is `ink-muted`. The state is always written in the pill too.

**Behaviour.** ⚒ Merge tests the branch with `test_cmd` in a throw-away worktree and squash-merges it into the base without asking. `C` turns a confirmation on first. Success sends `forge.merged`, and conflicts or red tests send `forge.conflict`.

**Camp (1990s real-time strategy × Factorio)**
- The Forge sprite stands on the window, glowing while the window is active.
- Branches sit in a sunken ledger, and PR pills are small bevelled plates.
- The detail is a raised plate with an Almendra heading, hashes in `code`, a sunken gold/green/red diff bar and the striped test belt.

**Office (VS Code)**
- The Source Control view: a sidebar list with 22px rows, outlined pill badges and a `frame-focus` outline on the selected branch.
- The detail is a plain panel with smooth rounded diff bars and the sweeping progress strip.

## Camp kit (v2)
The new Camp's world: the card as a building, rails and mine carts, the orks, signals and chips. Settled in
docs/design/design-system-v2.md; built with the backlog's C2–C5, beside today's Hut, Road and Sprite until each is
replaced. Preview: `previews/CampKit.html` (the 0.3 reference sprites cut to the system; references, not shipped art).
Sizes are in art pixels; the town draws them at ½ (map), 1 (overview) or 2 (close) CSS pixels per art pixel, never
in between. Words and badges are UI at their own size at every zoom.

**Cover** — a building as it stands. Three kinds: **hall** (a roof over the walls kit: Agent pool, Research),
**open ground** (the scene is the cover: the Inspector's pond, the Review board's fire), **tower or gate** (the
structure from the front over its yard walls: External listeners, the Review gate).
- Slots: `footprint` (XS 96×64, S 120×80, M 144×96, L 168×112: the card's area; the walls stand outside it) ·
  `material` · `facade` · `crest` · `signal` · `count` · `state`.
- States: `covered` (map, overview) · `peek` (hover or select: the cover at 50 %) · `lifted` (close: the cover gone,
  the walls are the card's frame, the crest is the card's header mark) · `burning` · `asking` · `idle` (never
  dimmed below 92 %).
- Office: the same box with its name, `hut-frame`; `peek` turns the frame `frame-focus`.

**Nine-slice (roofs and walls).** Corners 24×24 (back corners 24×32) with a border on their two outer sides only;
edges 24 deep (the back 32), a border on their outer side only, repeating every 8 px with up to three variants;
the centre a 32×32 tile with no border. Repeat, never stretch. Roofs: canvas (maroon), thatch, hide. Walls: stone
and log, palisade logs.

**Facade** — a building's own front at the door, 96×48 (XS 64×48), standing on the front wall's centre, the bottom
cut straight, no ground under it. Where orks go in and the track spur meets the building.

**Crest** — one object over the cover, 32×48, bottom centre on the ridge; one per building, never repeated in a camp.
At the close zoom it is the card's header mark, drawn at 1×.

**Track** — roads drawn as rails. 32×32 autotiles, the gauge 20 centred, ties every 8 px and low in contrast: straight
(H, V), corners (4), T-junctions (4), a crossing, switches and merges per direction, buffer stops (4), the way in and
the way out through the palisade. Picked by a 4-bit neighbour mask; never rotated. At the map zoom a 4 px line in
`art-wood-dark`. Office: today's Road lines.

**Mine cart** — side view 48×32, front view 32×40, anchored at the wheels' bottom centre. `load` slot 32×24 over the
bin (`code` a `</>` scroll, `asset` a crate, `message` a sealed letter, `doc` a book, `bundle` three sacks; a `×3`
chip for several). `flag` slot 16×12 on a pole at the back left: none (moving), `ask` (`signal-ask`), `held` (⏳),
`fire` (`signal-fire`, flickering). Rolling: 4 frames. A queue is a pile at a buffer stop with a `×4` chip. Orks never
move or ride carts. Office: a 10 px square in the state's colour, the load as a word.

**Ork** — one body, frame 32×48, anchored at the feet. Directions down, up, side (mirrored). Frames: idle 4, walk 6
per direction, work 6, sit 2, at 8 fps. `role` slot: headgear and tool over the body (its name is `orc.<type>` in
`TERMS`: the Warchief, a Grunt, the Lookout, the Seer, …). `state` slot, a pose: working (the tool swings, no badge),
asks (a hand raised, ❓), stuck (slumped, `!`), held (arms crossed, ⏳), idle (dozing, no badge). Office: the state as
a word.

**Signal** — ❓ `!` ⏳ on a dark plate (`chip`, 1 px `art-outline`), 20×20 (24×24 and a 44×44 tap area on the phone),
2 px over the head or roof it marks. Yellow (`signal-ask`) and red (`signal-fire`) appear nowhere else. Only for
exceptions: normal work is motion.

**Chip** — every word on the map: `chip` plate, `chip-ink` text in `camp-chip` / `office-chip`, 20 high (24 on the
phone, text never under 11), 6 px padding. A cart's chip `#42 · Login form` (a title cut at about 20 characters) is
always shown for a cart that waits for the person; a building's count chip (`🥩 2 · ❓ 1`) at its door. The same chip
in both looks.

**Spotlight** — hover or select an ork, a cart or a 🥩 row: the pair is lifted (full saturation, a 1 px `chip-ink`
keyline), a dashed rope in `chip-ink` joins them, the rest dims to 70 % saturation and 85 % lightness. Office: the
row and its cart highlighted, the rest at 40 %.

**Layers**, bottom to top: ground · track · floors · buildings · carts · orks · covers · signals · chips · UI.

**Do.** Draw every word on a chip. Keep the yellow and the red for signals. Scale by whole numbers.
**Don't.** No pixel text, no baked shadows, no fence round a card, no isometric piece, no decorative fire.

## Ground
The Camp map behind the buildings. It is one flat colour per biome with a handful of small decorations, so the cards, the fire and the text keep the eye.

**Markup**
- Set `.ok-ground` on the map container. It paints a plain, single-colour `canvas` in every biome: no patches and no texture.
- Decorations are `div.ok-doodad`, absolutely placed, each holding an `ok-sprite` (`tree`, `bush` or `mount`).

**Rules**
- 5–7 decorations per screen in all, scattered by the app with a deterministic seed per orkspace, the way the TUI's terrain is.
- A decoration never sits under a card or within 24px of one. It is not interactive, and Office hides it.
- Forest has trees and bushes, ice has icy mountains and frozen trees, and void has rocks.
- Decorations are dark silhouettes at about 1.5:1 against `canvas`. They are shapes in the dark, not objects to look at.

In this preview, `.only-forest`, `.only-ice` and `.only-void` pick each biome's decorations. The generation brief is in the Sprites section.

## Hud
The resource strip along the top of the town: the brand, the menu, the halt state, waiting orders and the four resources.

**Markup**
- `.ok-hud` holds `.ok-hud__brand`, `.ok-hud__ready` or `.ok-hud__halt`, `.ok-hud__fire`, a `.ok-hud__spacer`, then one `.ok-res` per resource.
- Each resource carries its Camp icon and its Office word (`ok-word`), following `modes.RESOURCES`: Quota (`icons/res-quota.png`, an hourglass, was ⏳), Spend (`res-gold`, a stack of coins, was 🪙), Context (`res-lumber`, crossed logs, was 🪵) and Agents (`res-meat`, meat on the bone, was 🥩). Each is a 16×16 `icon-resource` sprite `<img class="ok-sprite" data-kind="res">`; Office hides it and keeps the word.
- States: `is-warn` at 80% or more, `is-over` at 100% or more, and `quiet` for the quiet-hours segment.

**Camp.** A real-time strategy resource bar: a bevelled `panel-raised` strip, the brand in Almendra, and an icon then a number for each resource.

**Office.** A VS Code title bar: flat `panel-inset` with a bottom hairline, the UI face, each word before its value, and no icons.

## Hut
A building as it stands on the town map, collapsed. In Camp it is a card with the building's header sprite on top. In Office it is an explorer card with the same sprite at two thirds of the size, standing at its left. Clicking it opens the building as a Window, which carries the wide banner version of the same art.

**Markup**
- `.ok-hut` holds, in order:
  - `.ok-head`, holding the header `ok-sprite` and an optional `.ok-head__fx` with flames.
  - `.ok-hut__label`, holding `.no`, the name and `.ok-hut__dot`.
  - `ul.ok-hut__lines`, with 1 to 3 live lines.
  - An optional `.ok-hut__acts` row of `ok-act` buttons.
- States:
  - `is-selected`.
  - `is-busy`: an ork is working.
  - `is-alert`: a question waits.
  - `is-alert is-hot`: it has waited 30 s or more.
- Size classes `xs`, `s`, `m`, `l` on `.ok-hut` set the width (`header-xs` … `header-l`). The header slot is as wide as the card.
- The structure is `.ok-hut` › `.ok-head` (unframed) + `.ok-hut__card`. The frame, selection and fire belong to the card only.

**Camp (1990s real-time strategy)**
- A bevelled `panel` card with a 2px `frame` border.
- The header is a small, compact building (2:1) in the frame's own muted colours. It stands centred on the card's top edge like a finial, outside the frame, and the frame's edge stays visible on both sides.
- The card opens with a bevelled title bar, as a window's: the number, the name in `camp-heading` and the garrison's Badge (the ork's head in its state). Under it go status lines in `camp-caption` and 40px command buttons.
- The selected building glows softly from behind in `frame-focus`, the colour of its frame. A burning one glows in `alert` / `alert-hot`.
- Selection turns the frame bone (`frame-focus`) and adds corner brackets, as a 1990s strategy game marks a unit.
- Fire follows the stages in `modes.py`:
  - **0 s:** an `alert` frame with the `glow-fire` halo, the card's panel turns `fire-ground`, and the building glows `alert` from behind.
  - **30 s:** `alert-hot`, `fire-ground-hot` and an `alert-hot` glow.
  - **60 s:** flame sprites appear over the header one by one, until it is covered at 5 min. Each flame is `span.ok-flame.is-sprite` with `fx/fire.png` as its background: a 64×16 strip of 4 frames that CSS steps through every 0.6 s.
  - No flicker under `prefers-reduced-motion` or in 🌙 quiet hours, where a ❓ follows the name instead.

**Office (VS Code)**
- A 240px card on `panel-raised` with a 1px `hut-frame` and `radius-md`, so it keeps its box on the map. No header: the name heads the card over a `frame` hairline, so a block is one box and its roads meet that box.
- The hut's number and pin show on hover, focus or selection only.
- A status dot on the right: grey when idle, `alert-hot` when waiting.
- Busy is a 2px `meter` strip sweeping along the card's foot (still under `prefers-reduced-motion`), never `frame-focus`: that colour is selection only.
- Text actions.
- A waiting card turns its outline (2px) and name the question's yellow (`alert`) and adds `?`.
- With a building selected, every hut that is neither it nor at the other end of one of its roads dims to 40%. A waiting hut never dims.

## Input
A single-line text field: answers to an ork, building names, the Builder chat.

**Markup.** `<input class="ok-input">`, with `is-focus` to force the focus look.

**Font.** Both looks use the UI face. Switch to `code` only for a field that holds code or a shell command.

**Camp.** A sunken well. Focus adds a 2px `frame-focus` ring.

**Office.** A VS Code input: a 1px `frame-strong` border that turns `frame-focus` on focus.

## KeyFooter
The bottom strip of key hints.

**Markup**
- `.ok-keys` holds one span per binding, with the key in `ok-kbd`.
- Where Office words a binding differently (`modes.FOOTER_WORDS`), put the Camp label in `ok-ico` and the Office label in `ok-word`. For example, Spawn Ork becomes Add agent, and Orders becomes Answers.

**Camp.** A bevelled strip with keys in `ink-gold` (light wood).

**Office.** The VS Code status bar: a solid 22px `frame-focus` strip with `on-action` text, where each item gets a hover wash.

## Meter
A labelled progress bar for quotas, budgets, telemetry and long jobs.

**Markup**
- `.ok-meter` holds a label, `.ok-meter__track` › `.ok-meter__fill` (set its `width`), then `.ok-meter__val`.
- States: `is-warn` (`warning`), `is-over` (`danger`) and `is-busy` (indeterminate).
- The value always prints as text too.

**Camp.** A 12px sunken trough holding a warm wood `meter` bar with a lit top edge and a dark bottom edge, like a Factorio progress bar. While busy, the trough shows a striped belt.

**Office.** A smooth 6px track with `radius-full` ends.
- The fill eases to new widths over 0.3 s.
- While busy, a short `frame-focus` bar sweeps across, like VS Code's progress strip.
- The sweep stops under `prefers-reduced-motion`.

## Road
A subscription between two buildings, with carts (events) travelling from the exit gate to the entry gate.

**Markup**
- `.ok-road` holds `.ok-road__gate`, then `.ok-road__path` › `i.ok-cart`, then `.ok-road__gate`.
- Cart states: `held`, `error`, `filtered`.
- Road states: none (faint), `is-bright`, and `is-selected` with an `.ok-road__label`.

**Camp**
- In the final art, roads are 16×16 top-down dirt tiles (`road-tile`): a straight, a corner, a crossing, a dead end and two gates. The app rotates them and cuts the tees from the crossing.
- Carts are 20×18 iron mine carts with a gold rim and a heap of amber ore. On a horizontal road the side profile (`carts/minecart.png`) serves both directions, since it is symmetric; the bottom of the wheels sits 2px above the bottom edge of the track, so the cart rides on the road, not in it. On a vertical road (`.ok-road.is-vertical`) carts are centred on the track: `is-down` uses the front view (`carts/cart-down.png`) and `is-up` the back view (`carts/cart-up.png`, a plain iron back with a gold coupling ring). The iron and gold stand out against the brown road.
- The tile set above shows each slot until the sprites exist.
- The UI draws the state: faint roads at 60% opacity, the selected road with a `road-selected` glow, held or failed carts with a `cart-held` or `cart-error` outline, filtered carts at 50%. The full brief is in Sprites.
- The straight tile (`roads/straight.png`, rotated by the app for vertical roads), the dead end (`roads/end.png`), the crossing (`roads/cross.png`; the app cuts tees from it), the exit gate (`roads/gate-out.png`: the road's rounded start with a gold arrow post pointing along it), the entry gate (`roads/gate-in.png`: the rounded end with a gold ring post) and the mine cart's side and front views exist; the tile set above shows the tiles at 2×. A road that leads nowhere (its target building was removed) ends in the dead-end tile instead of an entry gate. Only the corner is still to come.

**Office**
- The town reads as a block diagram: 2px lines, an exit dot and a filled 10px arrowhead at the entry, both on the card's frame.
- A plain road (no handler) is dashed in `road`. A road a handler works on is solid in `road-live` (moss green).
- Every road carries its label, in `ink-muted` on a `canvas` halo, at the middle of its longest straight run.
- Bends turn on `radius-md` (4px). Where roads cross, the later one's `canvas` halo breaks the one below.
- Roads that would share a path take lanes of their own, one cell (8px) apart.
- With a building selected, its roads out turn `road-selected` (light wood), its roads in keep their colour, and every other road dims to 40%.
- Carts are small stacks of gold (`icons/res-gold.png`, the Spend icon, at 8px) glowing gold, red while held, grey when turned back, with a pill label.
- A road runs straight out of its gate and into the other for up to 48px before it turns, so it never bends right at a building.

**Motion.** Carts move at about 8 fps. More than six on one road collapse into a counter (×N).

## Sprite
The slots that Camp pixel art fills: each building's header and banner, map decorations, command icons, resource icons and ork portraits. Office shows no sprites.

**Markup**
- A finished sprite: `<img class="ok-sprite m" src="…">`.
- Until a sprite exists: `<div class="ok-sprite is-empty m">fields</div>`. It shows the exact slot, so you can lay screens out now.

**Sizes**

| Slot | Class | Size | Token | For |
|---|---|---|---|---|
| Hut header | `xs` | 64×32 on a 192 card | `header-xs` | Pit, Mill, Horn |
| Hut header | `s` | 80×40 on a 240 card | `header-s` | Signpost, Scroll Dump, Loot Vault, Catapult, Workshop, Custom |
| Hut header | `m` | 96×48 on a 288 card | `header-m` | Watchtower, Task Fields, Barracks, Clan Fire, Forge, Tally Crag |
| Hut header | `l` | 112×56 on a 336 card | `header-l` | War Drum, File Forest, Town Hall, Lake |
| Window building | `banner` | 128×64 | `banner-w`, `banner-h` | every building |
| Decoration | `tree`, `bush`, `mount` | 16×24, 16×12, 32×24 at most | `doodad-s`, `doodad-l` | the map ground, 5–7 per screen |
| Command icon | `icon` | 32×32 | `icon-command` | building actions |
| Resource icon | `res` | 16×16 | `icon-resource` | HUD resources and carts |
| Ork | `data-kind="ork"` | 24×16 | `ork-w`, `ork-h` | badges, the roster, the War Map: everywhere 🧌 stood |
| Portrait | `portrait` | 46×38 | `portrait-w`, `portrait-h` | the selected ork (`orks/ork-portrait.png`, 26×24 centred) and the Builder |

**Headers**
- A header is a small, compact building (2:1), centred on its card's top edge. The frame's top edge stays visible on both sides, so the building reads as a finial on the frame, not as a picture.
- It is a flat 2D front view in the frame's own muted colours, with very little detail.
- It has no ground strip and a transparent background. Its base is the bottom row and stands on the card's top edge.

**Rendering**
- Always `image-rendering: pixelated`.
- Show sprites at 1× or a whole multiple only.

The generation brief is in the Sprites section.

## Tabs
Switches between views inside one window, as in the Town Hall (Hall · Sessions · Limits).

**Markup.** `.ok-tabs` › `.ok-tab`, with `is-active` on one.

**Camp.** Sunken stone tabs. The active tab is raised, with its label in `ink-gold` (light wood).

**Office.** VS Code editor tabs, 35px tall and separated by hairlines. The active tab sits on `panel` with a 1px `frame-focus` top line.

## TaskFields
The Task Fields building opened: one board that holds both tasks and sticky notes (see `docs/design/fields-board.md`).

**Markup**
- `.ok-board` (set `--lanes` to the number of lanes) › `section.ok-lane` › `header.ok-lane__head` (the name and `.ok-lane__count`), then the cards, then `.ok-lane__add`.
- Add `is-notes` to a lane of notes (Ideas, Questions, For the sync). Lanes that are not notes are status lanes: To Do, Doing, Done.
- A card is `.ok-card` with `data-color` set to `yellow`, `green`, `blue`, `red` or `purple` (or none), holding:
  - `.ok-card__title`, which contains `i.ok-card__sw`, an optional `.ok-card__check` and the title;
  - an optional `.ok-card__text`, clamped to 2 lines;
  - an optional `.ok-card__meta` (✎ when a task has text, `sent → Barracks` after `s`).
- States: `is-selected`, `is-dragging`, `is-done` (struck through, with ✓), and `is-alert` (an ork asks about this card).
- A card's kind follows its lane. Moving a note into To Do makes it a task, so a task and a note look the same.

**Camp (1990s real-time strategy × Factorio)**
- Lanes are sunken fields with Almendra headers: `ink-gold` (light wood) for status lanes, `warning` for lanes of notes.
- Cards are bevelled plaques tinted with their `sticky-*` colour, like Factorio's coloured slots.
- Selected: a 2px `frame-focus` (bone) outline. Dragging: the card tilts and lifts.

**Office (VS Code)**
- Lanes are bare columns with an 11px uppercase header and a pill counter.
- Cards are hairline cards on `panel` with `radius-md`. The colour is a 10px `mark-*` square before the title, the same square the board file writes (🟨 🟩 🟦 🟥 🟪).
- Selected: a 1px `frame-focus` outline.

**Keys** (KeyFooter): `n` new, `<` `>` move, `e` open, `c` colour, `t` note ⇄ task, `s` send.

## Toast
A short, passive notice in the corner. It never asks a question; questions are fire.

**Markup**
- `.ok-toast` takes `is-ok`, `is-warn` or `is-error`.
- Inside go `.ok-toast__mark` (✓, ⚠ or ✗) and one sentence.

**Camp.** A bevelled stone plate.

**Office.** A VS Code notification: `panel`, a hairline and `radius-md`.

## Town
A piece of the map: real building sprites on their cards, on the Camp ground, beside the same cards in Office. This preview shows how the parts look together. It is not a component of its own.

**What it shows**
- Town Hall (L) **selected**: a bone frame, corner brackets and a glow behind the hall.
- War Drum (L) **busy**.
- Tally Crag (M).
- Lake of Insight (L) **waiting for an answer**: a yellow frame and halo (`alert`), a yellow glow behind the pier, and a flame on its roof.
- File Forest (L).
- The Forge, Task Fields and Barracks **busy**, Clan Fire and Watchtower (all M).
- The Catapult, Loot Vault, Workshop, Scroll Dump, Custom and Signpost (all S).
- The Pit, The Mill (busy) and The Horn (all XS). With these, all 19 catalog buildings have their header.
- A few pines around them.

**Markup.** `.ok-town` is a wrapping flex row of `Hut` cards; the app places huts freely on the canvas instead. Each sprite is a `.ok-sprite` `<img>` in the card's `.ok-head`, standing on the card's top edge and centred.

**Sprites.** These are the first five building headers, drawn to the brief in Sprites and reduced to their slots: 112×56 for L and 96×48 for M, keeping the outline on the edges and the gold where it shows. A full-width ground band or plank under Lake and Tally Crag was cut off.

## WarMap
The list of orkspaces (F1–F8) with their biome and a marker for waiting questions. The same `ok-list` also builds the Clan Roster, the Command Card and the F10 menu.

**Markup**
- `.ok-list` contains `.ok-list__head`, then `ul.ok-list__items` of `li.ok-item`, then an optional `.ok-list__foot`.
- Each `li.ok-item` holds an `ok-kbd` key, the name and a `.meta` on the right.
- States: `is-selected`, `is-alert`, `is-disabled`.

**Camp**
- A `frame-focus` (bone) rule on top, an Almendra header in `ink-gold` and items in a sunken well.
- The selected row sits on `selection`. An alert row is `alert` yellow (the question's) and ends with the waiting ork (`orks/ork-waiting.png`).

**Office**
- A VS Code sidebar section: an 11px uppercase header and 24px rows with a hover wash.
- The key moves to the right, as a keybinding hint.
- The selected row gets a `frame-focus` outline. An alert row is `danger` and ends with `?`.
- Biomes show as words.

## Window
An opened building. In Camp it is a wide banner sprite over a title bar and a panel of live content. In Office it is an editor group.

**Markup**
- `.ok-win` holds, in order:
  - `.ok-head.is-banner`, holding the banner `ok-sprite` and an optional `.ok-head__fx` with flames.
  - `.ok-win__bar`, holding `.ok-win__no`, `.ok-ico`, `.ok-win__title` and a `Badge`.
  - `.ok-win__body`.
  - An optional `.ok-win__grip`.
- States:
  - `is-active`: the window has focus.
  - `is-alert`: a question waits.
  - `is-alert is-hot`: it has waited 30 s or more.

**Camp (1990s real-time strategy)**
- The window is `.ok-win` › `.ok-head.is-banner` (unframed) + `.ok-win__frame` (border, bar, body). The frame, focus and fire belong to `.ok-win__frame`.
- The window's building sprite is 128×64 (`banner-w` × `banner-h`): the same building a size up, in the frame's muted colours, centred on the frame's top edge. The building stands on the frame's top edge, and its roof rises over the map ground, not inside the frame. A narrower window crops the banner from the centre.
- The active window's building glows softly from behind in `frame-focus`; a burning one glows in `alert` / `alert-hot`. The UI draws the glow with `drop-shadow`.
- Under the banner sit a bevelled title bar in `camp-heading` and a 4px wood frame that turns bone on focus, under a maroon title bar.
- A waiting window burns: an `alert` frame with the `glow-fire` halo, the building glows `alert-hot` from behind, and flame sprites spread over its roof.

**Office (VS Code)**
- The banner is hidden.
- The window is a 1px frame with `radius-lg`, a 35px tab bar, focus as a 1px `frame-focus` outline, and a yellow frame and title (`alert`) while waiting.

**Behaviour.** A window has no close button: closing is Demolish (`X`). Double-clicking the bar maximizes the window.
