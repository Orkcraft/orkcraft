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
- `icons/road-handle.png`, `icons/road-target.png` (22×22, 18×18): the `+` a road is pulled out of a hut by, and the
  four corner brackets round the hut it would land on, drawn by `tools/road_sprites.py` (`js/hut.js`; the
  brackets are a nine-slice, layout.css `.gui-hut.is-target`).
- `orks/ork.png` (24×16): the ork, the ork mark's flat head (`../logo/`); `ork-idle.png`, `ork-busy.png`,
  `ork-waiting.png`, `ork-frozen.png`, `ork-draft.png` (40×16): its states, the head with a glyph beside it,
  drawn by `tools/logo.py` (`js/icons.js` `OrkHead`): eyes shut and a pale-blue Zz; a gold gear; a flame on
  the crown and an orange `!`; a snowflake; a page.
- `orks/warchief*.png` (24×20, its states 40×20): the Warchief, the ork's head under a gold crown, and its
  states with the ork's glyphs beside it (the crown's points burn while it waits), drawn by `tools/logo.py` (`js/icons.js` `WarchiefHead`; docs/design/growth.md §8).
- `buildings/<type>/header-<biome>.png`: each header redrawn by `tools/growth_sprites.py` for ice (snow), dust
  (dry olive, sand), void (ashen violet) and lava (basalt, embers); dirt and forest wear `header.png`
  (`js/icons.js` `headerSprite`; docs/design/war-map.md §3).
- `flags/level-<n>.png`: the flag on a hut's roof at renown I–III, gold at III (its anchor per type in
  `js/icons.js` `FLAG_AT`); `flags/footing-<n>.png`: a tile of the stones under the hut, a course more at
  each level; `flags/annex-thrift.png` (a lean-to over logs) and `flags/annex-quality.png` (a crystal on a
  whetstone): beside the hut by its goal, none for balance (`js/icons.js` `HutSprite`; docs/design/growth.md §5).
- `mascots/<kin>-<stage>.png` (24×22): the operator's mascot, seven kins in four stages, on the ork mark's grid
  (`js/icons.js` `MascotHead`; docs/design/growth.md §7).
- `icons/res-quota.png`, `res-gold.png`, `res-lumber.png`, `res-meat.png` (16×16): the HUD resources, an
  hourglass, a stack of coins, two crossed logs and meat on the bone (`js/chrome.js`; the gold also rides
  on carts, `js/town.js`).
- `icons/chain.png` (16×16): a wooden signpost with a gold stud, the chain-or-script marker in place of an
  ork (`js/icons.js`).

Component previews (`../previews/`) embed their sprites as `data:` URIs, because an upload's `/_blob/`
URL does not load inside a preview frame, so they keep drawings no longer in this folder (carts, road
tiles, doodads, fire, tier marks). The app itself loads the files.
