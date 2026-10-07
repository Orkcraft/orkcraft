// Tidy up (the bare town's right click): the huts laid out along their roads, left to right — a building
// stands one column right of the furthest building that sends it anything, so most roads run one way and
// short. In a column the huts keep the order of what feeds them (the mean row of their sources), so roads
// cross as little as they can; a building no road touches stands in a column of its own at the right.
// Pinned huts and the Hall keep their places. The spots are fractions of the room, as `hut.move` keeps them:
// columns and rows close together from the top left (roads stay short), never down into the room's bottom
// part, where the War Map stands at the left and the Hall at the right.
const COLUMN = 0.42;                       // the most room a column takes across: a road's label fits between
const ROW = 0.3;                           // the most room a row takes down
const LOW = 0.6;                           // no hut is put lower than this

/** id → [fx, fy] for every hut `buildings` may move, from `roads` ({from, to}) between them. */
export function tidySpots(buildings, roads, fixed = () => false) {
  const ids = buildings.map((b) => b.id);
  const here = new Set(ids);
  const links = roads.filter((r) => here.has(r.from) && here.has(r.to) && r.from !== r.to);
  const touched = new Set(links.flatMap((r) => [r.from, r.to]));
  const col = Object.fromEntries(ids.map((id) => [id, 0]));
  // the longest way in from a building nothing feeds; a loop stops growing after as many rounds as huts
  for (let round = 0; round < ids.length; round++) {
    let grew = false;
    for (const r of links) {
      if (col[r.to] < col[r.from] + 1 && col[r.from] + 1 < ids.length) { col[r.to] = col[r.from] + 1; grew = true; }
    }
    if (!grew) break;
  }
  const flowing = ids.filter((id) => touched.has(id));
  const last = flowing.length ? Math.max(...flowing.map((id) => col[id])) : -1;
  for (const id of ids) if (!touched.has(id)) col[id] = last + 1;
  const columns = Math.max(...ids.map((id) => col[id]), 0) + 1;

  const row = {};
  const out = {};
  for (let c = 0; c < columns; c++) {
    const inCol = ids.filter((id) => col[id] === c);
    const fed = (id) => {
      const from = links.filter((r) => r.to === id && row[r.from] !== undefined).map((r) => row[r.from]);
      return from.length ? from.reduce((a, b) => a + b, 0) / from.length : 0;
    };
    inCol.sort((a, b) => fed(a) - fed(b));
    const step = inCol.length > 1 ? Math.min(ROW, LOW / (inCol.length - 1)) : 0;
    const across = columns > 1 ? Math.min(COLUMN, 1 / (columns - 1)) : 0;
    inCol.forEach((id, j) => {
      row[id] = j * step;
      if (!fixed(id)) out[id] = [Math.round(c * across * 1000) / 1000, Math.round(row[id] * 1000) / 1000];
    });
  }
  return out;
}
