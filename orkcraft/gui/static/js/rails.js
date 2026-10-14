// Camp draws a road as a rail track (docs/design/color-pass.md §6d, design-system-v2.md §4d): the road's cells
// (js/roads.js plan) laid with an autotile set chosen by each cell's neighbours along the roads that run on it.
// A cell's links (n e s w) pick its tile: straight, corner, a T-junction, a crossing; where one road's carts come
// in and leave two ways it is a switch, where two come in and leave one way a merge; the last cell before a
// building is a buffer stop, where carts that wait stand. Tiles never rotate: each direction is its own name, as
// the sprites are (design-system/sprites/camp/track/; js/track.js lays them). The words stay: a road is a road.

const OPPOSITE = { n: "s", s: "n", e: "w", w: "e" };
const ORDER = "nesw";

/** The side of cell `a` that cell `b` lies on, when they touch; else "". */
function sideOf(a, b) {
  const dx = b[0] - a[0], dy = b[1] - a[1];
  if (Math.abs(dx) + Math.abs(dy) !== 1) return "";
  return dx === 1 ? "e" : dx === -1 ? "w" : dy === 1 ? "s" : "n";
}

const sorted = (dirs) => [...dirs].sort((p, q) => ORDER.indexOf(p) - ORDER.indexOf(q)).join("");

/** The piece of track that joins two sides of a cell, as its tile names it: `h`, `v` or a corner `ne`, `se`, … */
export function move(a, b) {
  if (!a && !b) return "h";
  if (!a || !b) return "ns".includes(a || b) ? "v" : "h";
  if (OPPOSITE[a] === b) return "ns".includes(a) ? "v" : "h";
  return ("ns".includes(a) ? a : b) + ("ew".includes(a) ? a : b);
}

/** The tile of a cell from the sides it links to and which of them carts come in by and leave by. */
export function tileOf(links, ins, outs) {
  const all = sorted(links);
  if (all.length >= 4) return "cross";
  if (all.length === 3) {
    if (ins.size === 1 && outs.size === 2) return `switch-${OPPOSITE[[...ins][0]]}`;   // the way the line runs on
    if (ins.size === 2 && outs.size === 1) return `merge-${[...outs][0]}`;
    return `t-${OPPOSITE[[...ORDER].find((d) => !links.has(d))]}`;   // named by its spur: t-n a spur from above
  }
  const m = move(...all);
  return m === "h" ? "straight-h" : m === "v" ? "straight-v" : `corner-${m}`;
}

/** The track of every road: each road's pieces (`pieces[road id]`: {x, y, move, stop?}), every cell's tile ({x, y,
 *  tile}, and `at`: "x,y" → tile),
 *  the switches and merges, the crossings, and the buffer stops ({x, y, dir, road}: the last cell before the road's
 *  building, `dir` the way the cart rolls into it). `paths` as js/roads.js plans them (each with `cells`). */
export function lay(paths) {
  const cells = new Map();
  const at = (x, y) => {
    const k = `${x},${y}`;
    if (!cells.has(k)) cells.set(k, { x, y, links: new Set(), ins: new Set(), outs: new Set() });
    return cells.get(k);
  };
  const pieces = {}, stops = new Map();
  for (const p of paths) {
    const cs = p.cells || [];
    pieces[p.id] = [];
    cs.forEach((c, i) => {
      const from = i > 0 ? sideOf(c, cs[i - 1]) : "", to = i < cs.length - 1 ? sideOf(c, cs[i + 1]) : "";
      const cell = at(c[0], c[1]);
      if (from) { cell.links.add(from); cell.ins.add(from); }
      if (to) { cell.links.add(to); cell.outs.add(to); }
      pieces[p.id].push({ x: c[0], y: c[1], move: move(from, to) });
    });
    if (cs.length >= 2) {
      const [x, y] = cs[cs.length - 2], dir = sideOf(cs[cs.length - 2], cs[cs.length - 1]);
      if (dir) pieces[p.id][cs.length - 2].stop = dir;
      if (dir && !stops.has(`${x},${y}`)) stops.set(`${x},${y}`, { x, y, dir, road: p.id });
    }
  }
  const tiles = [...cells.values()].map((c) => ({ x: c.x, y: c.y, tile: tileOf(c.links, c.ins, c.outs) }));
  return {
    pieces,
    tiles,
    at: new Map(tiles.map((t) => [`${t.x},${t.y}`, t.tile])),
    junctions: tiles.filter((t) => /^(switch|merge|cross)/.test(t.tile)),
    stops: [...stops.values()],
  };
}
