// Camp's services and neighbours (design-system-v3.md §4c rules 1–3). A service (the Wiki) is consulted, never passed
// through: it stands in a row beside its busiest reader with no stop on the line, and one short footpath joins its
// door to its reader's path; readers further away get no path (their ork's bubble says it reads). Two buildings joined
// by a road back (`returns`) stand in one row, at most one place apart. Only buildings the person never placed in
// Office move, and a service they placed gets no path: the person's places win. (The back row along the palisade was
// built and taken out, the owner, 15 October: one building did not earn a row of its own and long paths.)
//
// Pure: no page (tests/test_camp_layout.py runs it in Node). Numbers are CSS px in the world's frame.

export const SERVICES = new Set(["scrolls"]);       // the Wiki; later the Town Hall
export const FOOTPATH = 16;                          // a service's footpath, art px wide: narrower than a building's
const placed = (b) => Array.isArray(b.hut);

/** Its readers, busiest first: the buildings a road joins it to, by how many roads (then as listed). */
export function readersOf(id, roads, here) {
  const n = new Map();
  for (const r of roads) {
    const other = r.from === id ? r.to : r.to === id ? r.from : null;
    if (other && other !== id && here.has(other)) n.set(other, (n.get(other) || 0) + 1);
  }
  return [...n].sort((a, c) => c[1] - a[1]).map(([k]) => k);
}

/** The pairs that stand together: each road back's two ends, and each service the person never placed with its
 *  busiest reader. */
export function pairsOf(list, roads) {
  const here = new Set(list.map((b) => b.id));
  const pairs = roads.filter((x) => x.returns && x.from !== x.to).map((r) => [r.from, r.to]);
  for (const b of list) {
    if (!SERVICES.has(b.type) || placed(b)) continue;
    const r = readersOf(b.id, roads, here)[0];
    if (r) pairs.unshift([r, b.id]);                                // a service moves to its reader, first
  }
  return pairs;
}

/** Rows with each pair's two ends as neighbours (`pairsOf`): an unplaced end (the less busy one; never one an earlier
 *  pair settled; a service before its reader) moves into its partner's row, just after it (a full row: it trades
 *  places with the one after the partner, if that one was never placed either). In place. */
export function neighbours(rows, roads, max, weight = () => 1) {
  const where = (id) => {
    for (let r = 0; r < rows.length; r++) { const i = rows[r].findIndex((b) => b.id === id); if (i >= 0) return [r, i]; }
    return null;
  };
  const load = (r) => rows[r].reduce((k, b) => k + weight(b), 0);
  const links = new Map(), settled = new Set();
  for (const r of roads) for (const id of [r.from, r.to]) links.set(id, (links.get(id) || 0) + 1);
  for (const [from, to] of pairsOf(rows.flat(), roads)) {
    const a = where(from), z = where(to);
    if (!a || !z) continue;
    const [ra, ia] = a, [rz, iz] = z;
    const item = (pos) => rows[pos[0]][pos[1]];
    if (ra === rz && Math.abs(ia - iz) <= (SERVICES.has(item(z).type) ? 1 : 2)) { settled.add(from).add(to); continue; }
    // the end that moves: one never placed and not settled by a pair before, a service, else the less busy one
    const can = (pos) => !placed(item(pos)) && !settled.has(item(pos).id);
    const busy = (pos) => (SERVICES.has(item(pos).type) ? -1 : links.get(item(pos).id) || 0);
    const [mover, stay] = can(z) && (!can(a) || busy(z) <= busy(a)) ? [z, a] : can(a) ? [a, z] : [null, null];
    settled.add(from).add(to);
    if (!mover) continue;                                            // both placed or settled: shown as it is
    const [rm, im] = mover, [rs, is] = stay, m = rows[rm][im], partner = rows[rs][is];
    if (rm === rs || load(rs) + weight(m) <= max) {
      rows[rm].splice(im, 1);
      rows[rs].splice(rows[rs].indexOf(partner) + 1, 0, m);
    } else {
      const j = is + 1 < rows[rs].length ? is + 1 : is - 1;
      if (j >= 0 && !placed(rows[rs][j]) && !settled.has(rows[rs][j].id) && weight(rows[rs][j]) === weight(m)) {
        [rows[rs][j], rows[rm][im]] = [rows[rm][im], rows[rs][j]];
      }
    }
  }
  return rows;
}

/** A service's one footpath to its reader beside it, or null: along the row's front from the service's door to the
 *  reader's path (its door) or a station's near side; to the depot, which stands on its line, straight down from the
 *  service's door to the line by the depot's gateway. `w` its width. */
export function footpath(s, p, w) {
  if (!p || p.row !== s.row) return null;
  if (p.depot) {                                     // the depot stands on its line: down to it, by its gateway
    return { x: Math.round(s.door.x - w / 2), y: Math.round(s.feet - 2), w: Math.round(w), h: Math.round(p.door.y - s.feet + 2),
             service: s.id, reader: p.id, foot: true };
  }
  const to = p.spur || p.depot || p.wall ? (p.cx < s.cx ? p.x + p.w - 8 : p.x + 8) : p.door.x;
  const y = Math.round(s.feet - 2);
  return { x: Math.round(Math.min(s.door.x, to) - w / 2), y, w: Math.round(Math.abs(to - s.door.x) + w), h: Math.round(w),
           service: s.id, reader: p.id, foot: true };
}
