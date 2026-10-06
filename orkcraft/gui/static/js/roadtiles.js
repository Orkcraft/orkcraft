// Camp's roads drawn with the road tiles (docs/design/sprites.md "Road tiles"): a forest footpath, 32×32 tiles
// with the track a third of the tile through the middle. Straights run along each leg of a road (turned for a
// vertical one), the corner tile turns where a road does, a gate-out tile where a road leaves its card and a
// gate-in where it enters (both drawn with the path coming in from the left to a post: turned so the post
// stands at the card). The UI draws the
// state, never the tile: faint (85%) for roads of buildings not selected, as drawn for the selected
// building's, a road-selected glow for the picked road; a return road is every other tile, fainter.
// Office keeps its lines (js/town.js).
import { html, cls } from "./html.js";
import { opened } from "./windows.js";
import { pickedRoad } from "./build.js";

const T = 32, H = T / 2;
const SPRITE = (name) => `/ds/sprites/roads/${name}@2x.png`;
const DIR = { right: [1, 0], left: [-1, 0], bottom: [0, 1], top: [0, -1] };
// A gate's path runs off to the left of its post: turned so it runs away from the card, on the card's side.
const GATE_TURN = { left: 0, top: 90, right: 180, bottom: 270 };
// The corner tile has its arms right and down; each quarter turn clockwise moves both arms on.
const CORNER_TURN = { "down right": 0, "down left": 90, "left up": 180, "right up": 270 };

const heading = ([ax, ay], [bx, by]) => (bx > ax ? "right" : bx < ax ? "left" : by > ay ? "down" : "up");
const BACK = { right: "left", left: "right", up: "down", down: "up" };

/** The tiles of one road: [{x, y (centre), sprite, turn, clip}]. */
export function tilesOf(p) {
  const pts = p.points;
  if (pts.length < 2) return [];
  const out = [];
  const [ex, ey] = DIR[p.side] || [1, 0];
  out.push({ x: pts[0][0] + ex * H, y: pts[0][1] + ey * H, sprite: "gate-out", turn: GATE_TURN[p.side || "right"] });
  const side = p.entrySide || "left";
  const [nx, ny] = DIR[side];
  const last = pts[pts.length - 1];
  out.push({ x: last[0] + nx * H, y: last[1] + ny * H, sprite: "gate-in", turn: GATE_TURN[side] });
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
      out.push({ x: b[0], y: b[1], sprite: "corner", turn: CORNER_TURN[[BACK[dir], next].sort().join(" ")] || 0 });
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
            + `background-image:url(${SPRITE(t.sprite)});${t.turn ? `transform:rotate(${t.turn}deg);` : ""}`}></i>`;
        })}
      </div>`;
    })}
  </div>`;
}
