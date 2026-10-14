// The town's ground on the phone, as on the desktop (gui/static/js/terrain.js, icons.js BIOMES): in Camp the page
// stands on the chosen orkspace's biome, its colour and a sparse scatter of its glyphs; Office has no ground.
// The colours and glyphs are the desktop's (tests/test_pwa.py keeps them so).

export const BIOMES = {
  dirt: "#141210", forest: "#1b170e", ice: "#070d14", dust: "#1a1712", void: "#0e0c14", lava: "#170f0d", meadow: "#0d1a16",
};

const GLYPHS = {
  dirt: { glyphs: ["·", ".", "`", "°"], ink: "#2a251c" },
  forest: { glyphs: ["·", ",", '"', "↟"], ink: "#2d2e1c" },
  ice: { glyphs: ["·", "'", "*", "⁕"], ink: "#162736" },
  dust: { glyphs: ["·", "~", "∴", "˜"], ink: "#3a2d1b" },
  void: { glyphs: [], ink: "" },
  lava: { glyphs: ["·", "^", "∴", "⁘"], ink: "#2a201e" },
  meadow: { glyphs: ["·", ",", "ʷ", "✿"], ink: "#1c3a30" },
};

const CELL_W = 10, CELL_H = 18, COLS = 48, ROWS = 24, DENSITY = 0.09;   // as terrain.js

function hash(x, y, stream) {
  let h = (Math.imul(x, 0x9e3779b1) ^ Math.imul(y, 0x85ebca77) ^ Math.imul(stream + 1, 0xc2b2ae3d)) >>> 0;
  h ^= h >>> 16; h = Math.imul(h, 0x7feb352d) >>> 0;
  h ^= h >>> 15; h = Math.imul(h, 0x846ca68b) >>> 0;
  return (h ^ (h >>> 16)) >>> 0;
}

const made = {};
function tile(biome) {
  if (biome in made) return made[biome];
  const g = GLYPHS[biome] || GLYPHS.dirt;
  let url = "";
  try {
    if (g.glyphs.length) {
      const scale = Math.min(Math.ceil(window.devicePixelRatio || 1), 3);
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
  } catch { url = ""; }                         // no canvas: the flat ground
  made[biome] = url;
  return url;
}

/** The page stands on `biome` in Camp, on the look's own canvas in Office. Returns the ground's colour ("" in
 *  Office), for the bar the system draws over the app. */
export function wearGround(biome, camp) {
  const root = document.documentElement.style;
  if (!camp) {
    root.removeProperty("--canvas");
    root.removeProperty("--terrain-image");
    return "";
  }
  const b = BIOMES[biome] ? biome : "dirt";
  root.setProperty("--canvas", BIOMES[b]);
  const url = tile(b);
  root.setProperty("--terrain-image", url ? `url("${url}")` : "none");
  return BIOMES[b];
}
