// The town's ground as the TUI drew it (orkcraft/theme.py): a sparse scatter of terminal glyphs, one
// colour a step off the ground, about one cell in eleven. Drawn once per biome on a canvas tile and laid
// under the town as a repeating background (docs/design/war-map.md §3.5): quiet enough that cards, gold
// and fire stay the only things that read. Void has none, as in the TUI.
import { BIOMES } from "./icons.js";

const CELL_W = 10, CELL_H = 18;            // a monospace cell at 13 px
const COLS = 48, ROWS = 24;                // the tile: 480 × 432 px
const DENSITY = 0.09;                      // theme.TERRAIN_DENSITY

// glyphs and their colour per biome: forest and ice are the TUI's own
export const GLYPHS = {
  dirt: { glyphs: ["·", ".", "`", "°"], ink: "#2a251c" },
  forest: { glyphs: ["·", ",", '"', "↟"], ink: "#1f3823" },
  ice: { glyphs: ["·", "'", "*", "⁕"], ink: "#162736" },
  dust: { glyphs: ["·", "~", "∴", "˜"], ink: "#3a2d1b" },
  void: { glyphs: [], ink: "" },
  lava: { glyphs: ["·", "^", "∴", "⁘"], ink: "#2a201e" },
  meadow: { glyphs: ["·", ",", "ʷ", "✿"], ink: "#1c3a30" },
};

function hash(x, y, stream) {               // a small deterministic mixer: the same ground every time
  let h = (Math.imul(x, 0x9e3779b1) ^ Math.imul(y, 0x85ebca77) ^ Math.imul(stream + 1, 0xc2b2ae3d)) >>> 0;
  h ^= h >>> 16; h = Math.imul(h, 0x7feb352d) >>> 0;
  h ^= h >>> 15; h = Math.imul(h, 0x846ca68b) >>> 0;
  return (h ^ (h >>> 16)) >>> 0;
}

const made = {};

/** The biome's ground tile as a data URL; "" for a biome with no glyphs (void) or no canvas. `scale` 2 draws
 *  it for a retina screen (the landing page's backgrounds take it so). */
export function terrainUrl(biome, scale = 1) {
  const key = `${biome}@${scale}`;
  if (key in made) return made[key];
  const g = GLYPHS[biome] || GLYPHS.dirt;
  let url = "";
  try {
    if (g.glyphs.length) {
      const c = document.createElement("canvas");
      c.width = COLS * CELL_W * scale; c.height = ROWS * CELL_H * scale;
      const ctx = c.getContext("2d");
      ctx.scale(scale, scale);
      ctx.fillStyle = g.ink;
      ctx.font = "13px ui-monospace, 'DejaVu Sans Mono', Menlo, monospace";
      ctx.textBaseline = "top";
      for (let y = 0; y < ROWS; y++) {
        for (let x = 0; x < COLS; x++) {
          if (hash(x, y, 0) / 4294967296 >= DENSITY) continue;
          ctx.fillText(g.glyphs[hash(x, y, 1) % g.glyphs.length], x * CELL_W + 1, y * CELL_H + 2);
        }
      }
      url = c.toDataURL("image/png");
    }
  } catch (e) {
    url = "";                                // no canvas (a test page): the flat ground
  }
  made[key] = url;
  return url;
}

/** Lay the open orkspace's ground on the page: its colour and its glyphs. */
export function wearGround(biome) {
  const root = document.documentElement.style;
  root.setProperty("--canvas", (BIOMES[biome] || BIOMES.dirt).ground);
  const url = terrainUrl(biome);
  root.setProperty("--terrain-image", url ? `url("${url}")` : "none");
}
