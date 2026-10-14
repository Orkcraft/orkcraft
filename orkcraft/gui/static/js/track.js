// Camp's roads as rail track (docs/design/design-system-v2.md §4d), drawn in the town's roads SVG (js/town.js Roads):
// each road's pieces under it, one v2 track tile (32 × 32, design-system/sprites/camp/track/) a cell of the track's grid
// (js/roads.js TRACK_CELL). A piece is the tile its move names (straight, corner); where the cell is a switch or a
// merge its straight is that tile and the branch its corner; a crossing is the crossing tile; the road's last cell before
// its building the buffer stop. The set has a direction or two of some tiles yet: until the artist's land, a missing
// one is its mirror (corner-sw of corner-se, stop-w of stop-e, stop-s of stop-n). Office draws no track, and at the
// map zoom Camp's road is a plain line again (town.css).
import { html } from "./html.js";

const TILES = "/ds/sprites/camp/track";
const HAVE = new Set(["straight-h", "straight-v", "corner-ne", "corner-nw", "corner-se", "cross", "switch-e", "merge-e",
  "stop-e", "stop-n"]);
const MIRROR = { "corner-sw": ["corner-se", "x"], "stop-w": ["stop-e", "x"], "stop-s": ["stop-n", "y"] };

/** The tile a road draws on one of its cells: by its move, the cell's own tile (a switch, a merge, a crossing) and
 *  whether it is the road's stop. */
export function pieceTile(p, cellTile) {
  if (p.stop) return `stop-${p.stop}`;
  if (cellTile === "cross") return "cross";
  if (p.move === "h" && (cellTile === "switch-e" || cellTile === "merge-e")) return cellTile;
  return p.move === "h" ? "straight-h" : p.move === "v" ? "straight-v" : `corner-${p.move}`;
}

function Tile({ name, x, y, size }) {
  const [file, flip] = HAVE.has(name) ? [name, ""] : MIRROR[name] || [name.startsWith("corner") ? "corner-se" : "straight-h", ""];
  const t = flip === "x" ? `translate(${x + size} ${y}) scale(-1 1)` : flip === "y" ? `translate(${x} ${y + size}) scale(1 -1)` : null;
  return html`<image href=${`${TILES}/${file}.png`} data-tile=${name} x=${t ? 0 : x} y=${t ? 0 : y} width=${size} height=${size}
    transform=${t} preserveAspectRatio="none" />`;
}

/** One road's track: its pieces, cell by cell (js/rails.js lay); `tiles` every cell's own tile ("x,y" → name). */
export function Rails({ pieces, tiles, cell }) {
  return html`<g class="gui-rails">${pieces.map((p) => html`<${Tile} key=${`${p.x},${p.y},${p.move}`}
    name=${pieceTile(p, tiles.get(`${p.x},${p.y}`))} x=${p.x * cell} y=${p.y * cell} size=${cell} />`)}</g>`;
}
