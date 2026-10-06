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
- `orks/ork.png`, `ork-idle.png`, `ork-busy.png`, `ork-waiting.png` (24×16): the ork, the ork mark's flat
  head (`../logo/`), and its states, drawn by `tools/logo.py` (`js/icons.js` `OrkHead`): eyes shut and a
  sleep mark; a pale-blue drop of sweat; a flame on the crown.
- `icons/res-quota.png`, `res-gold.png`, `res-lumber.png`, `res-meat.png` (16×16): the HUD resources, an
  hourglass, a stack of coins, two crossed logs and meat on the bone (`js/chrome.js`; the gold also rides
  on carts, `js/town.js`).
- `icons/chain.png` (16×16): a wooden signpost with a gold stud, the chain-or-script marker in place of an
  ork (`js/icons.js`).

Component previews (`../previews/`) embed their sprites as `data:` URIs, because an upload's `/_blob/`
URL does not load inside a preview frame, so they keep drawings no longer in this folder (carts, road
tiles, doodads, fire, tier marks). The app itself loads the files.
