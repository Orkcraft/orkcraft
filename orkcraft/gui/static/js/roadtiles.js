// Camp's roads drawn with the road tiles (docs/design/sprites.md "Road tiles"): 16×16 tiles, the track 8px
// wide through the middle. Straights run along each leg of a road (turned for a vertical one); a corner is cut
// from the crossing — only the arms it needs show — since the corner tile is not drawn yet; a gate-out tile
// where a road leaves its card, a gate-in where it enters (turned to the card's side). The UI draws the
// state, never the tile: faint (60%) for roads of buildings not selected, as drawn for the selected
// building's, a road-selected glow for the picked road; a return road is every other tile, fainter.
// Office keeps its lines (js/town.js).
import { html, cls } from "./html.js";
import { opened } from "./windows.js";
import { pickedRoad } from "./build.js";

const T = 16, H = T / 2;
const SPRITE = (name) => `/ds/sprites/roads/${name}@2x.png`;
const DIR = { right: [1, 0], left: [-1, 0], bottom: [0, 1], top: [0, -1] };
const OUT_TURN = { right: 0, bottom: 90, left: 180, top: 270 };    // gate-out is drawn leaving to the right
const IN_TURN = { left: 0, top: 90, right: 180, bottom: 270 };     // gate-in is drawn entering from the left

/** The crossing cut down to the arms a corner or a tee needs (up, right, down, left), as a clip polygon. */
function arms(set) {
  const pts = [[4, 4]];
  if (set.has("up")) pts.push([4, 0], [12, 0]);
  pts.push([12, 4]);
  if (set.has("right")) pts.push([16, 4], [16, 12]);
  pts.push([12, 12]);
  if (set.has("down")) pts.push([12, 16], [4, 16]);
  pts.push([4, 12]);
  if (set.has("left")) pts.push([0, 12], [0, 4]);
  return `polygon(${pts.map(([x, y]) => `${x / 16 * 100}% ${y / 16 * 100}%`).join(", ")})`;
}

const heading = ([ax, ay], [bx, by]) => (bx > ax ? "right" : bx < ax ? "left" : by > ay ? "down" : "up");
const BACK = { right: "left", left: "right", up: "down", down: "up" };

/** The tiles of one road: [{x, y (centre), sprite, turn, clip}]. */
export function tilesOf(p) {
  const pts = p.points;
  if (pts.length < 2) return [];
  const out = [];
  const [ex, ey] = DIR[p.side] || [1, 0];
  out.push({ x: pts[0][0] + ex * H, y: pts[0][1] + ey * H, sprite: "gate-out", turn: OUT_TURN[p.side] || 0 });
  const side = p.entrySide || "left";
  const [nx, ny] = DIR[side];
  const last = pts[pts.length - 1];
  out.push({ x: last[0] + nx * H, y: last[1] + ny * H, sprite: "gate-in", turn: IN_TURN[side] || 0 });
  for (let i = 0; i + 1 < pts.length; i++) {
    const a = pts[i], b = pts[i + 1], dir = heading(a, b);
    const len = Math.hypot(b[0] - a[0], b[1] - a[1]);
    const s = i === 0 ? T : H, e = len - (i + 2 === pts.length ? T : H);     // the gates' and corners' room
    if (e - s > 2) {
      const n = Math.max(1, Math.ceil((e - s) / T));
      for (let k = 0; k < n; k++) {
        const d = s + ((e - s) * (k + 0.5)) / n;
        const fx = (b[0] - a[0]) / len, fy = (b[1] - a[1]) / len;
        out.push({ x: a[0] + fx * d, y: a[1] + fy * d, sprite: "straight", turn: dir === "up" || dir === "down" ? 90 : 0,
                   straight: true });
      }
    }
    if (i + 2 < pts.length) {                         // a corner at b: the arm back along this leg, and the next
      const next = heading(b, pts[i + 2]);
      out.push({ x: b[0], y: b[1], sprite: "cross", turn: 0, clip: arms(new Set([BACK[dir], next])) });
    }
  }
  return out;
}

export function RoadTiles({ paths, roads }) {
  const byId = Object.fromEntries(roads.map((x) => [x.id, x]));
  const active = opened.value.active;
  return html`<div class="gui-tiles" aria-hidden="true">
    ${paths.map((p) => {
      const road = byId[p.id];
      if (!road) return null;
      const bright = active === road.from || active === road.to;
      let straight = 0;
      return html`<div key=${p.id} class=${cls("gui-tiles__road", { "is-bright": bright, "is-picked": pickedRoad.value === p.id,
          "is-return": road.returns })}>
        ${tilesOf(p).map((t, i) => {
          if (t.straight && road.returns && straight++ % 2) return null;      // a return road: every other tile
          return html`<i key=${i} class="gui-tile" style=${`left:${t.x - H}px;top:${t.y - H}px;`
            + `background-image:url(${SPRITE(t.sprite)});${t.turn ? `transform:rotate(${t.turn}deg);` : ""}`
            + `${t.clip ? `clip-path:${t.clip};` : ""}`}></i>`;
        })}
      </div>`;
    })}
  </div>`;
}
