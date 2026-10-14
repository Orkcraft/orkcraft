# camp/: the new Camp's sprites — placeholders

**Every sprite in this folder is a placeholder:** generated art, cut from the 0.3 reference sheets
(`docs/design/img/references/0.3/`) by `tools/camp_sheet.py`, to be replaced one by one by the commissioned
artist's hand-made sprites before the public launch (docs/design/color-pass.md §10–10b,
docs/design/artist-brief.md). Never shown as Orkline's art in the README, the landing page or a post; every row of
`manifest.json` says `"placeholder": true`.

The layout, names, anchors and sizes are design-system v2's (docs/design/design-system-v2.md §2–4, §11), so the
artist's PNG drops into the same path and the town does not change. Drawn at 1× in art pixels, every size a multiple
of 8; the renderer scales by whole numbers (no `@2x`); `map/` holds the half-size copies of the covers for the map
zoom.

**Recut:** `python tools/camp_sheet.py` (all sheets, then the faces), `--only <name>` (one sheet), `--check DIR` (each nine-slice kit
tiled 3 × 3 and 5 × 4, at 4×, to look for seams). A new sheet is a new entry in `tools/camp_sheets.json`;
`--list SHEET` prints the pieces it finds and where.

## What is here

| folder | sprites | frame | anchor |
|---|---|---|---|
| `orks/body/` | `idle` (4), `walk-down`, `walk-up`, `walk-side` (6 each; mirrored for the other side), `work` (6, the hammer), `sit` (2, on a log) | 32 × 48; `work`, `sit` 48 × 48 | the feet, bottom centre |
| `orks/roles/` | `warchief`, `grunt`, `mason`, `mechanic`, `seer`, `quartermaster`, `pathfinder` (orks-round3); `taskmaster`, `lookout`, `loader`, `farseer`, `warder`, `artisan`, `treasurer`, `alchemist` (roles-2) | 48 × 56; roles-2 72 × 56 (what they hold reaches wide) | bottom centre |
| `orks/faces/` | `<role>` and `<role>-16` for every role of `faces.roles` in `tools/camp_sheets.json`; `plain` | 32 × 24; `-16` 16 × 16 (the head's half, 16 × 12, at the foot) | bottom centre |
| `carts/` | `side`, `rolling-side` (4), `front`; `loads/<code\|asset\|message\|doc\|bundle>` and `-front`; `flags/<ask\|held\|fire>` | 48 × 40 (front 48 × 48); loads 48 × 32; flags 40 × 32 | bottom centre (flags: the pole's foot, bottom left) |
| `track/` | `straight-h`, `straight-v`, `corner-nw` (and `-1`), `corner-ne`, `corner-se`, `cross`, `switch-e`, `merge-e`, `stop-e`, `stop-n` | 32 × 32 | top left |
| `covers/hall/` | `roof-canvas/`, `roof-thatch/`, `roof-hide/`, `walls-stone/`, `walls-palisade/`: `nw n ne w c e sw s se`, edges with variants `-1 -2` | corners 24 × 24, back 24 × 32; edges 8 long, 24 deep (back 32); `c` 32 × 32 | top left |
| `covers/open/` | `fire-calm`, `fire-warm`, `fire-alarm` (🔥: a signal sprite), `pond` | 128 × 80 | bottom centre |
| `covers/tower/`, `covers/gate/` | `lookout`, `gatehouse` | 64 × 128, 128 × 96 | bottom centre |
| `facades/` | `fields`, `barracks`, `loot_vault`, `lake`, `watchtower` | 96 × 48 | bottom centre |
| `crests/` | `horn`, `banner`, `totem`, `lens`, `chimney`, `skull`, `lantern`, `axes`, `scrolls`, `raven` | 32 × 48 | bottom centre |
| `edge/` | `palisade-h`, `palisade-v` (repeat units), `palisade-corner-<nw\|ne\|sw\|se>`, `palisade-gate-<w\|e>` | 32 × 48; corners 64 × 80–88; gate 48 × 72 | bottom centre |

The track tiles have their sheet's grass keyed out (`key_grass`): only the earth bed, the ties and the rails stay, on
the ground layer's own grass. A load is what the loaded cart has that the empty one has not, so a load drawn over
`side.png` (feet together) gives the loaded cart back. Colours are snapped to the `art-*` / `world-*` tokens plus the
few tones each group lists in the manifest (`tones`); yellow and red only in `carts/flags/` and `fire-alarm`.

## The faces (`orks/faces/`, docs/design/ork-icons.md §6)

The interface's small faces (the 🥩 list, the console, Info's ork card, the Warchief's line, the UX bench's gallery):
each role's head and headgear cut from its body by `tools/camp_faces.py` (`--sheet DIR` writes the 16 px check, in
colour and in grey). `js/icons.js` `FACES` says which ork wears which role's face; a role with no body yet has the
**plain head** (the Grunt's head, its cap turned to skin) in its own file, so its body lands by rerunning the tool,
with no code changed. On the plain head now (no body yet): Scavenger, Grot Pointa, Miller, Hornblower, Chieftain,
Drummer, Woodcutter, Scroll Scrapper, Bard, Prospector, Smith, Crag Carver, Tinker, Peon.

**Rule 3 at 16 px and in grey (2026-10-14, with the second roles sheet):** told apart: the Warchief (horns), the
Seer (dark hood), the Mason (bandana), the Alchemist (now its pointed hat, apart from the Mechanic), the Artisan
(straw hat), the Farseer (a narrow dark hood with its charm, apart from the Alchemist's wide brown brim, if only just),
the Taskmaster (a dark flat cap against the Grunt's light one). **Not told apart:** the **Warder and the
Quartermaster** (the same iron helmet: one grey blob; ork-icons.md §6 proposes a ledger and stamp for the
Quartermaster); the **Treasurer and the Mechanic** (now both a cap over round lenses); the **Loader and the
Pathfinder** (both a cap with ear flaps); the Lookout's hood leans on its spyglass to part from the Seer's. At
32 × 24 in colour all fifteen are told apart.

## Where the placeholders fall short of v2 (the artist fixes them)

- **Sizes off v2's slots where the sheet's drawing does not fit:** `work` and `sit` (48 × 48), the role figures
  (whole figures 48 × 56, not headgear and tool over the body), the carts (48 × 40, not 48 × 32), the flags (40 × 32,
  not 16 × 12 on the pole), the open grounds (128 × 80). Several are read at a coarser cell than the sheet's own
  pixel (`scale` in the manifest), so they are softer than hand-drawn art.
- **Missing from the 0.3 sheets:** the ork's state poses (asks, stuck, held, doze), the Warchief in a tie, the
  T-junctions, `corner-sw`, `stop-w` and `stop-s` (the town mirrors the ones it has for now), switches and merges
  other than left to right, the ways in and out through the palisade, grass and earth tiles, hall furniture, the
  catapult. They were drawn in the owner's second batch, which is not in the repository (only the concept frame
  `docs/design/img/orkline-camp-concept-v2.png` is).
- **The sheets' own flaws, kept:** the facades and the gatehouse stand on a bit of their island of ground; the
  lookout is isometric and the watchtower's facade has the metal megaphone; the roofs' centres are cut from pieces
  that were not seamless (the hide roof shows its repeat).
