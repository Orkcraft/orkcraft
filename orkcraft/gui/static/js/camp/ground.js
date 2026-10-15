// Camp's ground (design-system-v3.md §4e): never one stamp. Grass and earth each draw one of several tiles, chosen by a
// fixed hash of the cell, so the same camp always draws the same and no pattern repeats in rows. Under every rail lies a
// track bed of path earth with the grass's rims along its open sides, so the track reads as worn ground.
//
// The variants are g5-ground's names (GEN's sheet, awaited): each is drawn once it is cut into the manifest. Until then
// today's earth stands in for every earth variant, shifted by the hash so it does not repeat, and the grass is the
// token itself with today's tufts and flowers on a few cells. Pure: tests/test_camp_layout.py runs it in Node.

export const GRASS = ["ground/grass-1.png", "ground/grass-2.png", "ground/grass-3.png", "ground/grass-4.png",
                      "ground/grass-tufts-1.png", "ground/grass-tufts-2.png", "ground/grass-flowers.png"];
export const EARTH = ["ground/earth-1.png", "ground/earth-2.png", "ground/earth-3.png", "ground/earth-stones.png",
                      "ground/earth-ruts.png"];
const RUTS = EARTH.length - 1;                  // old cart ruts: the track bed only
export const STAND_IN = { earth: "ground/earth.png", tufts: "ground/tufts.png", flowers: "ground/flowers.png" };

/** A fixed hash of a cell (and a salt): the same cell, the same number, 0 … 2³² − 1. */
export function hash(gx, gy, salt = 0) {
  let h = (Math.imul(gx | 0, 374761393) + Math.imul(gy | 0, 668265263) + Math.imul(salt | 0, 2246822519)) | 0;
  h = Math.imul(h ^ (h >>> 13), 1274126177);
  return (h ^ (h >>> 16)) >>> 0;
}

/** A grass cell's tile: plain grass the most (one of four), tufts about one cell in eight (one of two), flowers about
 *  one in twenty, so the decor stays quiet (§4.9). */
export function grassOf(gx, gy) {
  const k = hash(gx, gy, 1) % 40, v = hash(gx, gy, 8);
  if (k < 5) return GRASS[4 + (v % 2)];                // 5 in 40: tufts
  if (k < 7) return GRASS[6];                          // 2 in 40: flowers
  return GRASS[v % 4];                                 // the rest: plain
}

/** An earth cell's tile: three plain, one with stones; the track bed may also wear old ruts. */
export const earthOf = (gx, gy, bed = false) => EARTH[hash(gx, gy, 2) % (bed ? EARTH.length : RUTS)];

/** Where today's earth is shifted for a cell standing in for its variant, art px (a whole step, so pixels stay whole). */
export const shiftOf = (gx, gy) => [(hash(gx, gy, 3) % 4) * 8, (hash(gx, gy, 4) % 4) * 8];

/** The track bed (§4e rule 1, amended): a narrow band of earth just wider than the sleepers (`BED` of a tile, about
 *  1.25× their length) under every rail, following each tile's ways out: a straight's band end to end, a curve's or a
 *  junction's from its middle out to each exit. As { x, y, w, h, along: "h" | "v", cell }. */
export const BED = 0.625;
const WAYS = { "straight-h": "ew", "straight-v": "ns", "corner-ne": "ne", "corner-nw": "nw", "corner-se": "se",
               "corner-sw": "sw", "t-n": "new", "t-e": "nes", "stop-e": "w", crossing: "ew" };
const TURN = { n: "e", e: "s", s: "w", w: "n" };
export function bedOf(tiles, T) {
  const W = Math.round(T * BED), m = (T - W) / 2, out = [], seen = new Set();
  for (const t of tiles) {
    const k = `${t.x},${t.y}`;
    if (seen.has(k)) continue;
    seen.add(k);
    let ways = t.exits ? [...t.exits] : [...(WAYS[t.name] || "ew")];
    if (!t.exits && t.rot) for (let q = 0; q < ((t.rot / 90) % 4 + 4) % 4; q++) ways = ways.map((d) => TURN[d]);
    const cell = [Math.round(t.x / T), Math.round(t.y / T)];
    const has = (d) => ways.includes(d);
    if (has("e") || has("w")) {
      const x0 = has("w") ? 0 : m, x1 = has("e") ? T : T - m;
      out.push({ x: t.x + x0, y: t.y + m, w: x1 - x0, h: W, along: "h", cell });
    }
    if (has("n") || has("s")) {
      const y0 = has("n") ? 0 : m, y1 = has("s") ? T : T - m;
      out.push({ x: t.x + m, y: t.y + y0, w: W, h: y1 - y0, along: "v", cell });
    }
  }
  return out;
}
