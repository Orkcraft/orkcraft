// Camp's roads as rail track (docs/design/design-system-v2.md §4d), drawn in the town's roads SVG (js/town.js Roads):
// each road's pieces under it, then the switches, merges and buffer stops over every road. A tile here is a
// placeholder drawn of plain shapes in the world's tokens (an earth bed, ties of wood, one in four of bone, two
// wooden rails), named as the sprite that replaces it (design-system/sprites/camp/track/). Office draws no track,
// and at the map zoom Camp's road is a plain line again (town.css).
import { html } from "./html.js";
import { CELL } from "./roads.js";

const C = CELL, MID = CELL / 2;
const RAIL = 2, BED = 6;                     // a rail's distance from the middle, the bed's width (px)

/** A straight piece, along x (`h`) or y (`v`); `bone` its tie of bone. */
function straight(id, vertical, bone) {
  const r = (x, y, w, h, c) => vertical ? html`<rect x=${y} y=${x} width=${h} height=${w} class=${c} />`
    : html`<rect x=${x} y=${y} width=${w} height=${h} class=${c} />`;
  return html`<symbol id=${id} viewBox=${`0 0 ${C} ${C}`} width=${C} height=${C}>
    ${r(0, MID - BED / 2, C, BED, "gui-rail__bed")}
    ${r(MID - 1, 0.5, 2, C - 1, bone ? "gui-rail__tie is-bone" : "gui-rail__tie")}
    ${r(0, MID - RAIL - 0.5, C, 1, "gui-rail__rail")}${r(0, MID + RAIL - 0.5, C, 1, "gui-rail__rail")}
  </symbol>`;
}

/** A corner joining two sides: arcs round the cell's corner between them, clipped by the cell. */
function corner(m) {
  const cx = m.includes("e") ? C : 0, cy = m.includes("s") ? C : 0;
  const arc = (r, c) => html`<circle cx=${cx} cy=${cy} r=${r} class=${c} />`;
  return html`<symbol id=${`gui-rail-${m}`} viewBox=${`0 0 ${C} ${C}`} width=${C} height=${C}>
    ${arc(MID, "gui-rail__bed is-curve")}${arc(MID - RAIL, "gui-rail__rail is-curve")}${arc(MID + RAIL, "gui-rail__rail is-curve")}
  </symbol>`;
}

/** A buffer stop of logs across the track at the side the carts roll to. */
function stop(dir) {
  const along = dir === "e" || dir === "w";
  const at = dir === "e" || dir === "s" ? C - 3 : 0;
  return html`<symbol id=${`gui-rail-stop-${dir}`} viewBox=${`0 0 ${C} ${C}`} width=${C} height=${C}>
    ${along ? html`<rect x=${at} y="0" width="3" height=${C} rx="1" class="gui-rail__log" />`
      : html`<rect x="0" y=${at} width=${C} height="3" rx="1" class="gui-rail__log" />`}
  </symbol>`;
}

/** The pieces' shapes, once per roads SVG. */
export function RailDefs() {
  return html`${straight("gui-rail-h", false, false)}${straight("gui-rail-h-bone", false, true)}
    ${straight("gui-rail-v", true, false)}${straight("gui-rail-v-bone", true, true)}
    ${["ne", "nw", "se", "sw"].map(corner)}${["n", "e", "s", "w"].map(stop)}
    <symbol id="gui-rail-lever" viewBox=${`0 0 ${C} ${C}`} width=${C} height=${C}>
      <rect x=${MID - 0.5} y="1" width="1" height=${MID} class="gui-rail__tie" /><circle cx=${MID} cy="1.5" r="1.5" class="gui-rail__knob" />
    </symbol>`;
}

/** One road's track: its pieces, cell by cell (js/rails.js lay). */
export function Rails({ pieces }) {
  return html`<g class="gui-rails">${pieces.map((p) => {
    const bone = (p.move === "h" || p.move === "v") && (p.x + p.y) % 4 === 0;
    return html`<use key=${`${p.x},${p.y},${p.move}`} href=${`#gui-rail-${p.move}${bone ? "-bone" : ""}`}
      x=${p.x * C} y=${p.y * C} width=${C} height=${C} />`;
  })}</g>`;
}

/** Over every road: a lever where a road's exits split (a switch) or roads join (a merge), and the buffer stops. */
export function RailMarks({ track }) {
  return html`<g class="gui-rail-marks">
    ${track.junctions.filter((j) => j.tile !== "cross").map((j) => html`<use key=${`j${j.x},${j.y}`} data-tile=${j.tile}
      href="#gui-rail-lever" x=${j.x * C + (j.tile.endsWith("-e") || j.tile.endsWith("-w") ? 0 : MID)}
      y=${j.y * C - MID} width=${C} height=${C} />`)}
    ${track.stops.map((s) => html`<use key=${`s${s.x},${s.y}`} data-tile=${`stop-${s.dir}`} href=${`#gui-rail-stop-${s.dir}`}
      x=${s.x * C} y=${s.y * C} width=${C} height=${C} />`)}
  </g>`;
}
