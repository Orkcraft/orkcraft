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

/** A grass cell's tile: four plain, two with tufts, one with flowers. */
export const grassOf = (gx, gy) => GRASS[hash(gx, gy, 1) % GRASS.length];

/** An earth cell's tile: three plain, one with stones; the track bed may also wear old ruts. */
export const earthOf = (gx, gy, bed = false) => EARTH[hash(gx, gy, 2) % (bed ? EARTH.length : RUTS)];

/** Where today's earth is shifted for a cell standing in for its variant, art px (a whole step, so pixels stay whole). */
export const shiftOf = (gx, gy) => [(hash(gx, gy, 3) % 4) * 8, (hash(gx, gy, 4) % 4) * 8];

/** The track bed: a square of earth under each track tile (`T` its side) and the sides where grass meets it, as
 *  { x, y, cell: [gx, gy], open: "nesw" } — a side is open where no other tile of the bed lies beside it. */
export function bedOf(tiles, T) {
  const at = new Map(), out = [];
  for (const t of tiles) {
    const k = `${t.x},${t.y}`;
    if (!at.has(k)) at.set(k, { x: t.x, y: t.y });
  }
  for (const b of at.values()) {
    const open = [["n", 0, -T], ["e", T, 0], ["s", 0, T], ["w", -T, 0]]
      .filter(([, dx, dy]) => !at.has(`${b.x + dx},${b.y + dy}`)).map(([d]) => d).join("");
    out.push({ ...b, cell: [Math.round(b.x / T), Math.round(b.y / T)], open });
  }
  return out;
}
