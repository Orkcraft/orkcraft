// Camp's back row and neighbours (design-system-v3.md §4c rules 1–3, P1). A service (the Wiki) is consulted, never
// passed through: it stands in the back row along the palisade, with no line and no stop, above its busiest reader, and
// a dirt path runs from it down to each building that reads it, through the gaps between the rows' buildings, crossing
// a line at a level crossing (planks between the rails, square to the line); never along the track. Two buildings
// joined by a road back (`returns`) stand in one row, at most one place apart. Only buildings the person never placed
// in Office move: the person's places win.
//
// Pure: no page (tests/test_camp_layout.py runs it in Node). Numbers are CSS px in the world's frame.

export const SERVICES = new Set(["scrolls"]);       // the Wiki; later the Town Hall
const placed = (b) => Array.isArray(b.hut);

/** The buildings that stand in the back row: services the person never placed. */
export const backOf = (list) => list.filter((b) => SERVICES.has(b.type) && !placed(b));

/** Its readers, busiest first: the buildings a road joins it to, by how many roads (then as listed). */
export function readersOf(id, roads, here) {
  const n = new Map();
  for (const r of roads) {
    const other = r.from === id ? r.to : r.to === id ? r.from : null;
    if (other && other !== id && here.has(other)) n.set(other, (n.get(other) || 0) + 1);
  }
  return [...n].sort((a, c) => c[1] - a[1]).map(([k]) => k);
}

/** Rows with each road back's two ends as neighbours: an unplaced end (the less busy one; never one an earlier pair
 *  settled) moves into its partner's row, just after it (a full row: it trades places with the one after the
 *  partner, if that one was never placed either). In place. */
export function neighbours(rows, roads, max) {
  const where = (id) => {
    for (let r = 0; r < rows.length; r++) { const i = rows[r].findIndex((b) => b.id === id); if (i >= 0) return [r, i]; }
    return null;
  };
  const links = new Map(), settled = new Set();
  for (const r of roads) for (const id of [r.from, r.to]) links.set(id, (links.get(id) || 0) + 1);
  for (const road of roads.filter((x) => x.returns && x.from !== x.to)) {
    const a = where(road.from), z = where(road.to);
    if (!a || !z) continue;
    const [ra, ia] = a, [rz, iz] = z;
    if (ra === rz && Math.abs(ia - iz) <= 2) continue;               // at most one place apart already
    // the end that moves: one never placed and not settled by a pair before, the less busy one (the hub stays)
    const can = (pos) => !placed(rows[pos[0]][pos[1]]) && !settled.has(rows[pos[0]][pos[1]].id);
    const busy = (pos) => links.get(rows[pos[0]][pos[1]].id) || 0;
    const [mover, stay] = can(z) && (!can(a) || busy(z) <= busy(a)) ? [z, a] : can(a) ? [a, z] : [null, null];
    settled.add(road.from).add(road.to);
    if (!mover) continue;                                            // both placed or settled: shown as it is
    const [rm, im] = mover, [rs, is] = stay, m = rows[rm][im], partner = rows[rs][is];
    if (rm === rs || rows[rs].length < max) {
      rows[rm].splice(im, 1);
      rows[rs].splice(rows[rs].indexOf(partner) + 1, 0, m);
    } else {
      const j = is + 1 < rows[rs].length ? is + 1 : is - 1;
      if (j >= 0 && !placed(rows[rs][j])) [rows[rs][j], rows[rm][im]] = [rows[rm][im], rows[rs][j]];
    }
  }
  return rows;
}

/** The back row's x: each service centred over its busiest reader, then pushed right so none overlaps, never left of
 *  `from` (clear of the way in and the lookout). `items`: [{ id, w, over (a reader's cx, or null) }]. */
export function spread(items, from, gap) {
  let x = from;
  const out = {};
  const sorted = [...items].sort((a, c) => (a.over ?? Infinity) - (c.over ?? Infinity));
  for (const it of sorted) {
    const want = it.over === null || it.over === undefined ? x : Math.round(it.over - it.w / 2);
    const at = Math.max(x, want);
    out[it.id] = at;
    x = at + it.w + gap;
  }
  return out;
}

/** The free spans of [lo, hi) once `taken` ([a, b] spans) are cut out. */
function freeOf(lo, hi, taken) {
  let spans = [[lo, hi]];
  for (const [a, b] of taken) {
    spans = spans.flatMap(([x, y]) => (b <= x || a >= y ? [[x, y]] : [[x, Math.min(a, y)], [Math.max(b, x), y]]))
      .filter(([x, y]) => y > x);
  }
  return spans;
}

/** A service's path to one reader, as boxes of earth, and the level crossings it makes. `s` the service, `p` the
 *  reader (laid out); `L` the town so far (its buildings, lines, tiles, home); `w` a path's width. The path leaves the
 *  service's door, runs along under the back row to a gap in the rows above the reader's, down it (crossing each line
 *  on a plain straight, never a switch, a curve or a pocket), across the open grass under the line above the reader's
 *  row to a gap in its row when the first runs on into a building, down that, and along the reader's front to its door
 *  (a station's near side: its track reaches the line). Never through a building, never along the track. Null when no
 *  way is free. */
export function pathTo(s, p, L, w) {
  const T = L.T, r = Math.max(0, p.row), half = w / 2, foot = Math.round(w * 0.75);
  const all = Object.values(L.buildings).filter((q) => !q.back && !q.wall);
  const meets = (a, b) => a.x < b.x + b.w && b.x < a.x + a.w && a.y < b.y + b.h && b.y < a.y + a.h;
  const home = L.home ? [L.home] : [];
  const lo = L.cols.left + T, hi = L.cols.right ?? L.buffer.x;
  // the columns free down through rows `from`..`to` (their buildings, the home) and across lines `from`..`lines` - 1
  const columns = (from, to, lines = to) => {
    const taken = [];
    for (const q of [...all, ...home]) if (q.row >= from && q.row <= to) taken.push([q.x, q.x + q.w]);
    for (let k = from; k < lines; k++) {
      for (const t of L.tiles) {
        const onLine = t.y === L.lines[k], inPocket = t.y === L.lines[k] - T && t.pocket !== undefined;
        if ((onLine && t.name !== "straight-h") || inPocket) taken.push([t.x, t.x + T]);
      }
    }
    for (const t of L.tiles) if (t.siding) taken.push([t.x, t.x + T]);
    return freeOf(lo, hi, taken).filter(([a, b]) => b - a >= w);          // a gap is one path wide (§4.8)
  };
  const strip = Math.min(p.feet, L.lines[r] - T - foot);                // the reader's row's front strip
  const front = [...all.filter((q) => q.id !== p.id && q.row === r).map((q) => ({ x: q.x, y: q.y, w: q.w, h: q.feet - q.y })),
                 ...home.filter((h) => h.row === r)];
  const end = (gx) => (!p.spur && !p.depot ? p.door.x : gx < p.cx ? p.x + 8 : p.x + p.w - 8);
  const inside = (g, x) => Math.min(Math.max(x, g[0] + half), g[1] - half);
  const stubOf = (gx) => ({ x: Math.min(gx, end(gx)) - half, y: strip, w: Math.abs(end(gx) - gx) + w, h: foot });
  const near = (gs, x) => gs.map((g) => inside(g, x)).sort((m, n) => Math.abs(m - x) - Math.abs(n - x));
  // the gap in the reader's row whose way along the front meets nothing, nearest its door
  const g2 = near(columns(r, r), end(p.cx)).find((gx) => !front.some((q) => meets(stubOf(gx), q)));
  if (g2 === undefined) return null;
  let g1 = g2, jog = null;
  if (r > 0) {
    const through = columns(0, r);                                        // one gap all the way down, if there is one
    const straight = through.some(([a, b]) => g2 - half >= a && g2 + half <= b);
    if (!straight) {
      const yj = L.lines[r - 1] + T + 4, rowTop = Math.min(...[...all, ...home].filter((q) => q.row === r).map((q) => q.y));
      if (rowTop - yj < w + 4) return null;                               // no grass to cross under the line
      g1 = near(columns(0, r - 1, r), g2)[0];
      if (g1 === undefined) return null;
      jog = { x: Math.min(g1, g2) - half, y: yj, w: Math.abs(g2 - g1) + w, h: w };
    }
  }
  const top = s.feet, mid = jog ? jog.y : strip;
  const boxes = [
    { x: Math.min(s.cx, g1) - half, y: top - 6, w: Math.abs(g1 - s.cx) + w, h: w + 6 },     // along under the back row
    { x: g1 - half, y: top, w, h: mid - top + (jog ? w : foot) },                          // down the first gap
    ...(jog ? [jog, { x: g2 - half, y: jog.y, w, h: strip - jog.y + foot }] : []),          // across, down the second
    stubOf(g2),                                                                             // along the reader's front
  ].map((b) => ({ ...b, x: Math.round(b.x), y: Math.round(b.y), service: s.id, reader: p.id }));
  const crossings = Array.from({ length: r }, (_, k) => ({ x: Math.round(g1 - T / 2), y: L.lines[k], w: T, h: T, service: s.id }));
  return { boxes, crossings, x: g1 };
}
