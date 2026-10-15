// Camp's town in v3 (docs/design/design-system-v3.md §3–§4): the buildings laid into rows by the work's order, a line of
// track under each row, the lines joined into a loop; the lookout in the back wall at the way in, the catapult at the
// right wall's buffer stop; each building joined by a short dirt path to its pocket, one tile above its line where its
// carts stop (§4c rule 7). Carts run on the track only, one way round (js/camp/track.js): a road's carts go from its
// source's stop to its building's stop (`route`), round the return line when the building is behind.
//
// Pure: no page, no Preact (tests/test_camp_layout.py runs it in Node). Every number out is CSS px in the world's frame
// at one zoom step: buildings, carts, the ground and the paths at `step.b` CSS px per art px, orks and the track at
// `step.s` (the layers at their own whole multiple, §3).

import { loop, cellsOf, path, throwsOn, simplify, lengthOf, exitsOf } from "./track.js";
import { backOf, neighbours, readersOf, spread, pathTo } from "./backrow.js";

export { exitsOf, simplify, lengthOf };
export const TILE = 64;          // a track tile, art px (c2's 64 × 64), shown at step.s
export const PATH_W = 32;        // a dirt path's width, art px at step.b
export const PATH_L = 24;        // from a building's door down to its line
export const GAP = 32;           // between two buildings in a row (one path's width, §3)
export const WALL_H = 48;        // the low palisade, its foot below the camp's top
export const ROW_MAX = 5;        // buildings to a row: a sixth starts the next row and its own line
export const SIDING_TILES = 3;   // the Task board's siding: the carts waiting to go (two straights and the buffer)
export const SIDING_SHOWN = 5;   // carts drawn on it; the rest a "+N" chip (design-system-v3.md §4, decisions §13.1)
export const FALLBACK = [128, 112];
// Where a building's carts wait off the line (§4c rule 7): "flat", a pocket track just above the line, joined to it by a
// short diagonal at each end (a stand-in drawn in code: c2's quarter curves read as arches); "none", no pocket track,
// the cart standing on the end of the building's path, the line clear. Which is calmer is the owner's call.
export const POCKET = { style: "none" };
const FLAT_LIFT = 0.6;           // the flat pocket's rails above the line's, in tiles
const STAND = 52;                // "none": the room a waiting cart takes at the path's end, art px   // a building with no v3 sprite: a block of this size

// The zoom steps, buildings / orks and track (§3): whole device pixels at every step. Density 2: ×1 / ×1 (an overview),
// ×1.5 / ×1 (the default), ×3 / ×2 (close). Density 1: ×1 / ×1, ×2 / ×1 (the default). Density 3 (a phone): ⅔ (two
// device px an art px, the overview), ×1 (three, the default) and ×2 / ×4⁄3 (close).
const HI = [{ b: 1, s: 1 }, { b: 1.5, s: 1 }, { b: 3, s: 2 }];
const LO = [{ b: 1, s: 1 }, { b: 2, s: 1 }];
const TRI = [{ b: 2 / 3, s: 2 / 3 }, { b: 1, s: 1 }, { b: 2, s: 4 / 3 }];
export const stepsFor = (dpr) => (dpr >= 3 ? TRI : dpr >= 2 ? HI : LO);
export const DEFAULT_STEP = 1;
/** A phone's default step: the art at its own pixel (×1), whatever the screen's density. */
export const phoneStep = (steps) => Math.max(0, steps.findIndex((s) => s.b === 1 && s.s === 1));

export const WAY_IN = "watchtower";          // stands in the back wall; the track comes in at its foot
export const WAY_OUT = "catapult";           // stands against the right wall at the line's buffer stop
export const SIDING = "fields";              // the Task board: the dispatcher's booth and its siding
const SPUR = new Set(["loot", "mine"]);
// growth (growth.md §5, v3-prompts §13.4): a goal other than balance builds its annex against the building's east wall
export const ANNEX = { thrift: "growth/annex-thrift.png", quality: "growth/annex-quality.png" };      // their sprite draws its own track down to the line (gate, headframe)

/** A building's v3 sprite (design-system/sprites/v3/): its type's, the Review gate's barrier up or down. */
export function spriteOf(b, waiting = false) {
  if (b.type === "loot") return waiting ? "buildings/loot_vault.png" : "buildings/loot_vault-up.png";
  return `buildings/${b.type}.png`;
}

/** The buildings in the work's order: by the longest chain of roads that reaches each (a source first), then as the
 *  town lists them; one no road touches after them all. A road back (`returns`) does not count. A loop of roads never
 *  runs away: a depth stops at the number of buildings. */
export function order(buildings, roads) {
  const at = new Map(buildings.map((b, i) => [b.id, i]));
  const depth = new Map(buildings.map((b) => [b.id, 0]));
  // a road back (`returns`: the answer to who asked, a send-back) is not the work's order: it goes round again (§4c)
  const edges = roads.filter((r) => at.has(r.from) && at.has(r.to) && r.from !== r.to && !r.returns);
  for (let k = 0; k < buildings.length; k++) {
    let changed = false;
    for (const r of edges) {
      const d = depth.get(r.from) + 1;
      if (d > depth.get(r.to) && d < buildings.length) { depth.set(r.to, d); changed = true; }
    }
    if (!changed) break;
  }
  const linked = new Set(edges.flatMap((r) => [r.from, r.to]));      // a building no road reaches stands after the work
  const rank = (b) => (linked.has(b.id) ? depth.get(b.id) : buildings.length);
  return [...buildings].sort((a, c) => rank(a) - rank(c) || at.get(a.id) - at.get(c.id));
}

/** The rows, top to bottom, from buildings in the work's order: at most five a row, balanced. A building the person
 *  placed in Office (`hut`: [x, y] as fractions of the room) takes its row by its y (the top band the top row) and
 *  its place in the row by its x, so moving a card in Office moves the building in Camp; one never placed fills the
 *  room left, top row first, in the work's order (decisions-2026-10.md §14). */
export function rowsOf(list) {
  // a second row as soon as one building was placed in the lower half (Build's "Bottom row" in Camp, a card in Office)
  const low = list.length >= 2 && list.some((b) => Array.isArray(b.hut) && b.hut[1] >= 0.5);
  const n = Math.max(low ? 2 : 1, Math.ceil(list.length / ROW_MAX));
  const per = Math.max(1, Math.ceil(list.length / n));
  const rows = Array.from({ length: n }, () => []);
  const placed = list.filter((b) => Array.isArray(b.hut));
  const band = (b) => Math.min(n - 1, Math.max(0, Math.floor(b.hut[1] * n)));
  for (const b of [...placed].sort((a, c) => a.hut[1] - c.hut[1] || a.hut[0] - c.hut[0])) {
    let r = band(b);
    while (r < n - 1 && rows[r].length >= per) r++;
    while (rows[r].length >= per && r > 0 && rows[r - 1].length < per) r--;
    rows[r].push(b);
  }
  for (const row of rows) row.sort((a, c) => a.hut[0] - c.hut[0]);
  for (const b of list.filter((x) => !Array.isArray(x.hut))) {
    const r = rows.findIndex((row) => row.length < per);
    rows[r < 0 ? n - 1 : r].push(b);
  }
  return rows;
}

/** The town laid out at one zoom step. `size(file)`: a v3 sprite's [w, h] in art px, or null when it is not cut.
 *  `waiting(b)`: a cart waits at it for the person (the Review gate's barrier is down). `home`: the person's home
 *  (`homes/<kin>.png`), east of the Review gate on its row, its door a path above the line like a building's
 *  (§4.13); with no gate, at the first row's end. */
export function lay(buildings, roads, step, size, waiting = () => false, home = "") {
  const B = step.b, S = step.s, T = TILE * S;
  const dims = (b) => {
    const file = spriteOf(b, waiting(b));
    const got = size(file);
    const [w, h] = got || FALLBACK;
    return { file: got ? file : "", w: w * B, h: h * B };
  };
  const sorted = order(buildings, roads);
  const tower = sorted.find((b) => b.type === WAY_IN) || null;
  const cata = [...sorted].reverse().find((b) => b.type === WAY_OUT) || null;
  const inRows = sorted.filter((b) => b !== tower && b !== cata);
  // the back row (§4c rule 1): services never placed stand along the palisade; return pairs as neighbours (rule 2)
  const backs = backOf(inRows);
  const rows = neighbours(rowsOf(inRows.filter((b) => !backs.includes(b))), roads, ROW_MAX);

  const td = tower ? dims(tower) : null, cd = cata ? dims(cata) : null;
  const M = Math.round(160 * B);                                        // the wilderness round the camp
  const top = M + Math.max(td ? td.h - WALL_H * B : 0, 0);              // room above the wall for the tower
  const campX = M, wallY = top + WALL_H * B;                            // the back wall's foot
  const colL = campX + Math.max(Math.round((td ? td.w / 2 : 48 * B) - T / 2), 24 * B);   // the way in, down to the lines
  const out = { step, T, buildings: {}, tiles: [], paths: [], sidings: [], decor: [], lines: [], home: null };
  const homeS = home ? size(home) : null;
  const homeRow = homeS ? Math.max(0, rows.findIndex((row) => row.some((b) => b.type === "loot"))) : -1;
  const putHome = (x, lineTop, r) => {
    const w = homeS[0] * B, h = homeS[1] * B, feet = lineTop - PATH_L * B, cx = Math.round(x + w / 2);
    out.home = { file: home, x: Math.round(x), y: Math.round(feet - h), w, h, feet, row: r, cx };
    out.paths.push({ x: Math.round(cx - PATH_W * B / 2), y: Math.round(feet - 6 * B), w: PATH_W * B,
                     h: Math.round(lineTop - feet + 6 * B + 2), home: true });
    return w + GAP * B;
  };

  // the rows, top to bottom: each row stands on its line, the next line whole tiles under the last (the columns tile).
  // An ordinary building stands over its pocket (§4c rule 7): one tile above the line, under its door, entered and left
  // by a T on the line, so a building's slot is centred on a tile and its pocket's three tiles (the curve in, the
  // pocket, the curve out) never meet the next one's. A station keeps its own track and has no pocket.
  const pockets = [];
  const backD = backs.map((b) => ({ b, d: dims(b) }));
  const backFeet = wallY - 24 * B + Math.max(0, ...backD.map(({ d }) => d.h));
  let lineTop = 0, right = colL + 3 * T;
  const style = POCKET.style;
  // how far above the line's top an ordinary building's path ends: at the pocket's top, or above a waiting cart
  const lift = style === "none" ? Math.round(STAND * B) : style === "flat" ? Math.round(T * FLAT_LIFT) : T;
  rows.forEach((row, r) => {
    const ds = row.map((b) => ({ b, d: dims(b), spur: SPUR.has(b.type), own: SPUR.has(b.type) || b.type === SIDING }));
    const band = Math.max(64 * B, ...ds.map(({ d, spur, own }) => (spur ? d.h - T / 4 : d.h + PATH_L * B + (own ? 0 : lift))),
                          r === homeRow ? homeS[1] * B + PATH_L * B : 0);
    if (r === 0) lineTop = Math.max((backs.length ? backFeet + PATH_W * B + 12 * B : wallY - 24 * B) + band, wallY + T);
    else {
      const prev = out.lines[r - 1];
      const cross = backs.length ? PATH_W * B + 8 * B : 0;                 // room under the line for a path across (§4c)
      lineTop = prev + Math.ceil((T + 8 * B + cross + band) / T) * T;
    }
    out.lines.push(lineTop);
    pockets.push([]);
    let x = colL + T + GAP * B, free = colL + T;                       // the next box's x; the pocket row free from
    for (const { b, d, spur, own } of ds) {
      const w = Math.max(d.w, PATH_W * B);
      let cx;
      const pocketed = !own && style !== "none";
      if (own || !pocketed) {
        x = Math.max(x, free);
        cx = Math.round(x + w / 2);
      } else {
        const k = Math.max(2, Math.ceil((free - colL) / T) + 1, Math.ceil((x + w / 2 - T / 2 - colL) / T));
        cx = colL + k * T + T / 2;
        x = cx - w / 2;
        free = colL + (k + 2) * T;
        pockets[r].push(colL + k * T);
      }
      const feet = spur ? lineTop + T / 4 : own ? lineTop - PATH_L * B : lineTop - lift - PATH_L * B;
      const pocketY = style === "flat" ? lineTop + T / 2 - lift : lineTop - T / 2;    // the pocket's rails' middle
      const annexS = ANNEX[b.goal] && size(ANNEX[b.goal]);
      out.buildings[b.id] = { id: b.id, type: b.type, file: d.file, x: Math.round(x + (w - d.w) / 2), y: Math.round(feet - d.h),
                              w: d.w, h: d.h, cx, feet, row: r, spur, door: { x: cx, y: feet }, pocket: pocketed,
                              stop: { x: cx, y: pocketed ? pocketY : lineTop + T / 2 }, waitAt: { x: cx, y: pocketed ? pocketY : lineTop },
                              growth: { level: Math.min(Math.max(b.level || 0, 0), 3), annex: annexS ? ANNEX[b.goal] : "" } };
      if (annexS) x += annexS[0] * B + 2 * B;
      if (!spur) out.paths.push({ x: Math.round(cx - PATH_W * B / 2), y: Math.round(feet - 6 * B), w: PATH_W * B,
                                  h: Math.round((pocketed ? lineTop - lift : lineTop) - feet + 6 * B + 2) });
      x += w + GAP * B;
      if (!pocketed) free = Math.max(free, x - GAP * B);
      if (b.type === SIDING) {                                           // the siding beside the booth, its buffer east
        const sx = Math.round(x - GAP * B / 2), sy = Math.round(feet - T * 0.75);
        out.sidings.push({ id: b.id, x: sx, y: sy, tiles: SIDING_TILES, stand: { x: sx + T * 0.6, y: sy + T * 0.8, dx: T * 0.62 } });
        x += SIDING_TILES * T + GAP * B / 2;
        free = Math.max(free, x);
      }
      if (b.type === "loot" && r === homeRow && !out.home) { x = Math.max(x, free); x += putHome(x, lineTop, r); free = x; }
    }
    if (r === homeRow && !out.home) { x = Math.max(x, free); x += putHome(x, lineTop, r); free = x; }
    right = Math.max(right, x - GAP * B, free);
  });
  // each service over its busiest reader, none over another, clear of the way in and the lookout
  const here = new Set(Object.keys(out.buildings));
  const xs = spread(backD.map(({ b, d }) => {
    const r = readersOf(b.id, roads, here)[0];
    return { id: b.id, w: d.w, over: r ? out.buildings[r].cx : null };
  }), colL + T + GAP * B, GAP * B);
  for (const { b, d } of backD) {
    const x = xs[b.id], cx = Math.round(x + d.w / 2);
    out.buildings[b.id] = { id: b.id, type: b.type, file: d.file, x, y: Math.round(backFeet - d.h), w: d.w, h: d.h, cx,
                            feet: backFeet, row: -1, back: true, spur: false, pocket: false, door: { x: cx, y: backFeet },
                            stop: { x: cx, y: backFeet }, growth: { level: Math.min(Math.max(b.level || 0, 0), 3), annex: "" } };
    right = Math.max(right, x + d.w);
  }
  const last = out.lines.length - 1, multi = out.lines.length > 1;
  const colR = colL + Math.ceil((right + GAP * B - colL) / T) * T;      // the right column (the merge), or the line's end

  // the track, one way round (js/camp/track.js): the way in, a line per row with its pockets, the right column, the
  // switch on to the buffer stop or down to the return line, the return line west, up the left column
  const track = loop(T, out.lines, colL, colR, multi, pockets);
  out.tiles = track.tiles;
  out.pocketStyle = style;
  if (style === "flat") {                                                // the flat pocket: its rails `lift` over the line's
    for (const t of out.tiles) if (t.pocket !== undefined) t.py = t.y + T + T / 2 - lift;
  }
  out.switches = track.switches;
  out.ret = track.ret;
  const endY = out.lines[last];
  const x = track.xs + T;                                               // the buffer stop's tile
  const buffer = track.buffer;
  for (const s of out.sidings) {
    for (let k = 0; k < s.tiles - 1; k++) out.tiles.push({ name: "straight-h", x: s.x + k * T, y: s.y, rot: 0, siding: s.id });
    out.tiles.push({ name: "stop-e", x: s.x + (s.tiles - 1) * T, y: s.y, rot: 0, siding: s.id });
  }

  // the two buildings in the wall
  const wallX = (cd ? x + T - 12 * B + cd.w : x + T + 24 * B) + 8 * B;
  if (tower) {
    const cx = colL + T / 2;
    out.buildings[tower.id] = { id: tower.id, type: tower.type, file: td.file, x: Math.round(cx - td.w / 2), y: Math.round(wallY + 8 * B - td.h),
                                w: td.w, h: td.h, cx, feet: wallY + 8 * B, row: -1, wall: "in", door: { x: cx, y: wallY },
                                stop: { x: cx, y: wallY + T / 2 } };
  }
  if (cata) {
    const left = x + T - 12 * B, feet = endY + T * 0.8;
    out.buildings[cata.id] = { id: cata.id, type: cata.type, file: cd.file, x: Math.round(left), y: Math.round(feet - cd.h),
                               w: cd.w, h: cd.h, cx: Math.round(left + cd.w / 2), feet, row: last, wall: "out",
                               door: { x: Math.round(left + cd.w / 3), y: feet }, stop: buffer };
  }
  out.buffer = buffer;
  const foot = out.ret + T;                                             // the return line's foot, the loop's bottom edge
  out.wall = { y: wallY, x: wallX, left: campX, bottom: foot + 64 * B,
               gap: tower ? [out.buildings[tower.id].x + 8 * B, out.buildings[tower.id].x + td.w - 8 * B] : [colL, colL + T] };
  out.cols = { left: colL, right: multi ? colR : null };
  out.camp = { x: campX, y: top, w: wallX + 24 * B - campX, h: foot + 48 * B - top };
  out.w = Math.round(wallX + 24 * B + M);
  out.h = Math.round(foot + 48 * B + M);
  // the work: from the back wall to the return line, between the columns (the default view is centred on it)
  // a path from each service to each building that reads it, crossing lines on planks (§4c rule 1)
  out.crossings = [];
  for (const { b } of backD) {
    for (const id of readersOf(b.id, roads, here)) {
      const way = out.buildings[id] && !out.buildings[id].back && pathTo(out.buildings[b.id], out.buildings[id], out, PATH_W * B);
      if (!way) continue;
      out.paths.push(...way.boxes);
      out.crossings.push(...way.crossings);
    }
  }
  out.work = { x: colL, y: wallY - 24 * B, w: track.xs + 2 * T - colL, h: foot - wallY + 24 * B };
  out.decor = decorAround(out, B);

  const cells = cellsOf(out.tiles);
  out.route = (fromId, toId) => route(out, cells, fromId, toId);
  out.routeOut = (fromId) => route(out, cells, fromId, { stop: buffer });   // to the line's buffer stop, where it leaves
  return out;
}

// g2's decor, a little, only in the wilderness round the camp (never in the work area, §4.9): fixed spots, so every
// shot of the same town is the same.
const DECOR = ["pine", "tree", "bush", "rock", "mushrooms-teal", "stump", "logpile", "reeds", "boulder", "pebbles",
               "log-mossy", "bush-small", "rocks", "mushrooms-white"];
function decorAround(out, B) {
  const c = out.camp, list = [];
  let k = 0;
  const put = (x, y) => list.push({ name: DECOR[k++ % DECOR.length], x: Math.round(x), y: Math.round(y) });
  for (let y = c.y + 80 * B; y < c.y + c.h; y += 120 * B) { put(c.x - 60 * B - (k % 2) * 40 * B, y); put(c.x + c.w + 50 * B + (k % 3) * 20 * B, y + 40 * B); }
  for (let x = c.x + 40 * B; x < c.x + c.w; x += 150 * B) { put(x + (k % 2) * 30 * B, c.y + c.h + 50 * B + (k % 3) * 18 * B); }
  return list;
}

/** A road's way for its carts: from its source's stop to its building's stop (or to `toId` a place: `{ stop }`) along
 *  the track, one way round, as points (the polyline through the tiles' middles, straight runs one segment); its
 *  `throws` the switches it passes and the way each is set for it (js/camp/track.js `throwsOn`). Null when either end
 *  is not on the town or no way leads there. */
function route(out, cells, fromId, toId) {
  const a = out.buildings[fromId], z = typeof toId === "string" ? out.buildings[toId] : toId;
  if (!a || !z) return null;
  const T = out.T;
  const chain = path(cells, T, a.stop, z.stop);
  if (!chain) return null;
  // a flat pocket (POCKET): its corners are short diagonals from the line's middle to the pocket's rails
  const mid = (t) => (t.py === undefined ? [t.x + T / 2, t.y + T / 2]
    : t.name === "corner-se" ? [t.x + T, t.py] : t.name === "corner-sw" ? [t.x, t.py] : [t.x + T / 2, t.py]);
  // a cart from the lookout comes in from outside the wall, down the way in
  const first = a.wall === "in" ? [a.stop.x, -T] : [a.stop.x, a.stop.y];
  const pts = simplify([first, ...chain.slice(1, -1).map(mid), [z.stop.x, z.stop.y]]);
  pts.throws = throwsOn(out.switches, chain, pts, T);
  return pts;
}
