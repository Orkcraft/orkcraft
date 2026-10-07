# The biomes' grounds, for the landing page

The seven grounds an orkspace stands on in the app (docs/design/war-map.md §3), exported from the GUI's
own code (`gui/static/js/terrain.js`, `js/icons.js` `BIOMES`), so the page and the app look the same.

| file | what |
|---|---|
| `<biome>.png`, `<biome>@2x.png` | the ground's glyphs on a **transparent** 480 × 432 tile (960 × 864 at 2x): lay it over the ground colour and repeat it |
| `biomes.json` | per biome: `ground` (the town's colour), `land` (its land on the War Map), `glyphs` and `ink` (their colour), `tile` |

Void has no glyphs (as in the TUI): the colour alone.

```css
.biome-ice {
  background: #070d14 url("ice@2x.png") repeat;
  background-size: 480px 432px;          /* the @2x tile at its 1x size: sharp on retina */
}
```

| biome | ground | land | the kin it is home to |
|---|---|---|---|
| dirt | `#1a1813` | `#3a3326` | orks |
| forest | `#101a0b` | `#22341a` | elves |
| ice | `#070d14` | `#1c2c3c` | the undead |
| dust | `#2a2014` | `#5a462a` | goblins |
| void | `#0e0c14` | `#2c263c` | skeletons |
| lava | `#161212` | `#342c2a` | gnomes |
| meadow | `#0d1a16` | `#24443a` | knights |

The huts of each biome are `design-system/sprites/buildings/<type>/header-<biome>.png` (dirt and forest:
`header.png`); the mascots are `design-system/sprites/mascots/<role>-<stage>.png`. To export again after a
change: open the GUI and save `terrainUrl(biome, 1)` and `terrainUrl(biome, 2)` from `js/terrain.js`.
