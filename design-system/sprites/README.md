# Sprites in this folder

Camp's finished pixel-art sprites, the ones the GUI shows. Every sprite is shown with
`image-rendering: pixelated` at 1× or a whole multiple, each with an `@2x`.

- `buildings/<type>/header.png`: the header of each of the 19 catalog buildings, the flat set
  (docs/design/building-sprites.md) on the ork mark's five colours, cut from generated sheets by
  `tools/sheet.py` (`js/icons.js` `headerSprite`).
  - Sheet 1 (`--cell 11 --scale 2`): town_hall, war_drum, watchtower, forge, scrolls, barracks, lake, loot.
  - Sheet 2 (`--cell 16.6 --scale 2`, the sheet's labels painted over first): mill (52×44), horn (50×46),
    signpost (46×48), pit (42×48), catapult (50×36), workshop (50×46), fields (50×52), council (46×46).
  - Sheet 3 (`--cell 16.6 --scale 2`): forest, crag, custom.
- `fence/row.png`, `fence/side.png`, `fence/post.png` (21×21, 15×27, 15×36): a yard's picket fence — a picket
  and its rails, a side picket and its gap, a gate post — in muted bronze wood, drawn by `tools/fence_sprites.py`
  at 3 px a pixel (`gui/static/yards.css`, docs/design/yards.md).
- `orks/ork-stand.png`, `orks/ork-walk-a.png`, `orks/ork-walk-b.png` (24×18): the ork's head out of its building on
  the plinth, facing you, and two steps of its walk facing left (mirrored as it walks back in); `icons/thumb-up.png`,
  `icons/thumb-down.png` (20×20): its bubble's green 👍 and 👎; `icons/bubble.png`, `icons/bubble-tail.png`: the
  bubble, a nine-slice, and its tail. Drawn by `tools/visit_sprites.py` (`js/visit.js`, docs/design/yards.md §4).
- `icons/road-handle.png`, `icons/road-target.png` (22×22, 18×18): the small gate a road is pulled out of a hut by, and the
  four corner brackets round the hut it would land on, drawn by `tools/road_sprites.py` (`js/hut.js`; the
  brackets are a nine-slice, layout.css `.gui-hut.is-target`).
- `orks/ork.png` (24×16): the ork, the ork mark's flat head (`../logo/`); `ork-idle.png`, `ork-busy.png`,
  `ork-waiting.png`, `ork-frozen.png`, `ork-draft.png` (40×16): its states, the head with a glyph beside it,
  drawn by `tools/logo.py` (`js/icons.js` `OrkHead`): eyes shut and a pale-blue Zz; a gold gear; a flame on
  the crown and an orange `!`; a snowflake; a page.
- `intents/<intent>.png` (16×16, `@2x` 32×32): what a building is for, the Build row's icons — incoming, agents (in
  parallel), discuss, calendar, transform (process data), research, check (validate), drop, tasks, wiki, and behind ⋯
  code, send, route, chart, sound, listen; drawn by `tools/intent_sprites.py` (`js/build.js` `INTENTS`, docs/design/warchief-line-and-cards.md §2).
- `orks/steward-<role>.png` (24×20) and `orks/hat-<role>.png` (24×4): a steward's head under its building's hat
  (scribe, lookout, smith, clerk, captain, miner), on the Warchief's line when its building is selected, and the hat
  alone on the ork out of its building; drawn by `tools/hat_sprites.py` (`js/icons.js` `HATS`,
  docs/design/select-a-building.md §2).
- `orks/warchief*.png` (24×20, its states 40×20): the Warchief, the ork's head under a gold crown, and its
  states with the ork's glyphs beside it (the crown's points burn while it waits), drawn by `tools/logo.py` (`js/icons.js` `WarchiefHead`; docs/design/growth.md §8).
- `buildings/<type>/header-<biome>.png`: each header redrawn by `tools/growth_sprites.py` for ice (snow), dust
  (dry olive, sand), void (ashen violet) and lava (basalt, embers); dirt and forest wear `header.png`
  (`js/icons.js` `headerSprite`; docs/design/war-map.md §3).
- `flags/level-<n>.png`: the flag on a hut's roof at renown I–III, gold at III (its anchor per type in
  `js/icons.js` `FLAG_AT`); `flags/footing-<n>.png`: a tile of the stones under the hut, a course more at
  each level; `flags/annex-thrift.png` (a lean-to over logs) and `flags/annex-quality.png` (a crystal on a
  whetstone): beside the hut by its goal, none for balance (`js/icons.js` `HutSprite`; docs/design/growth.md §5).
- `mascots/<role>-<stage>.png` (24×22): the operator's mascot, eleven roles in four stages, on the landing's class grid
  (`js/icons.js` `MascotHead`; docs/design/growth.md §7).
- `icons/res-quota.png`, `res-gold.png`, `res-lumber.png`, `res-meat.png` (16×16): the HUD resources, an
  hourglass, a stack of coins, two crossed logs and meat on the bone (`js/chrome.js`; the gold also rides
  on carts, `js/town.js`).
- `icons/harness-claude.png`, `harness-agy.png`, `harness-codex.png`, `harness-hermes.png`, `harness-pi.png`,
  `harness-cursor.png` (16×16): each AI tool's mark, a simple sign of its own in the tool's colours (no one's
  logo) with the house's dark outline: an orange starburst (Claude), an arch in Google's four colours
  (Antigravity), a green tile with `>_` (Codex), a purple winged staff (Hermes), a rose tile with π (pi), a
  grey cube (Cursor). Drawn by `tools/icon_sprites.py` (`js/icons.js` `ToolMark`: schemes, toasts, Town
  settings, the onboarding, the Mine; Office draws the same signs as small SVGs).
  `harness-pipeline.png` (16×16) and `harness-arrow.png` (10×16): a scheme's P and the grey arrow between
  steps (`js/icons.js` `Scheme`; Office keeps them as text).
- `icons/notify-on.png`, `notify-off.png` (16×16): Do not disturb's toggle beside the portrait, a bone speaking
  horn with a gold rim, struck through while it holds (`tools/icon_sprites.py`, `js/portrait.js` `Horn`).
- `icons/chain.png` (16×16): a wooden signpost with a gold stud, the chain-or-script marker in place of an
  ork (`js/icons.js`).

Component previews (`../previews/`) embed their sprites as `data:` URIs, because an upload's `/_blob/`
URL does not load inside a preview frame, so they keep drawings no longer in this folder (carts, road
tiles, doodads, fire, tier marks). The app itself loads the files.
