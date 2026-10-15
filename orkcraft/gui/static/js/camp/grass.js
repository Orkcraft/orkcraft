// Where an item may stand on Camp's grass (docs/design/v3-prompts.md §14, realm/items.py): on a grid of 16 art px from
// the camp's corner (the back wall's left end), never on the track, a path or a stop, never against a building or the
// home, never in the palisade, never on another item. Pure: tests/test_camp_layout.py runs it in Node.

export const CELL = 16;           // art px, at the buildings' layer (step.b)

/** The grid's origin and its cell, CSS px in the world at this zoom step. */
export function grid(L) {
  return { x: L.camp.x, y: L.wall.y, c: CELL * L.step.b };
}

/** An item's box when its feet stand in cell (gx, gy): centred on the cell, its feet on the cell's foot. */
export function boxAt(L, size, gx, gy) {
  const g = grid(L), B = L.step.b, w = size[0] * B, h = size[1] * B;
  const cx = g.x + gx * g.c + g.c / 2, feet = g.y + (gy + 1) * g.c;
  return { x: Math.round(cx - w / 2), y: Math.round(feet - h), w, h };
}

/** The cell whose box would hold a point (world CSS px) at an item's feet. */
export function cellAt(L, x, y) {
  const g = grid(L);
  return { gx: Math.floor((x - g.x) / g.c), gy: Math.floor((y - g.y) / g.c) };
}

const grow = (r, k) => ({ x: r.x - k, y: r.y - k, w: r.w + 2 * k, h: r.h + 2 * k });
const meets = (a, b) => a.x < b.x + b.w && b.x < a.x + a.w && a.y < b.y + b.h && b.y < a.y + a.h;

/** What no item may touch, as boxes: the buildings and the home with a cell round them (never against one), a goal's
 *  annex, the paths, every track tile (the lines, the columns, the sidings, the stops), the decor already standing
 *  round the camp, the back palisade. */
export function blockers(L) {
  const B = L.step.b, c = CELL * B, out = [];
  for (const p of Object.values(L.buildings)) {
    out.push({ ...grow({ x: p.x, y: p.y, w: p.w, h: Math.max(p.h, p.feet - p.y) }, c), id: p.id });
    if (p.growth && p.growth.annex) out.push({ ...grow({ x: p.x + p.w, y: p.feet - 64 * B, w: 66 * B, h: 64 * B }, c / 2), id: p.id });
  }
  if (L.home) out.push(grow(L.home, c));
  for (const p of L.paths) out.push(grow(p, c / 4));
  for (const t of L.tiles) out.push({ x: t.x, y: t.y, w: L.T, h: L.T });
  for (const d of L.decor) out.push({ x: d.x - 20 * B, y: d.y - 40 * B, w: 40 * B, h: 40 * B });   // the wilderness's own
  const w = L.wall;
  out.push({ x: w.left - c, y: w.y - 56 * B, w: w.x - w.left + 2 * c, h: 56 * B + c / 2 });     // the back wall
  return out;
}

/** True when an item's box stands on grass: inside the world, clear of every blocker and of the other items' boxes. */
export function fits(L, box, walls, others = []) {
  if (box.x < 0 || box.y < 0 || box.x + box.w > L.w || box.y + box.h > L.h) return false;
  return !walls.some((r) => meets(box, r)) && !others.some((r) => meets(box, r));
}

/** What a placed item's box meets now that the camp changed: the building that took its cell (its id), "" for
 *  anything else (a path, the track, the home), null when it still stands on grass. A pixel of slack, so the zoom's
 *  rounding never moves an item. */
export function takenBy(L, box, walls) {
  const inner = grow(box, -1);
  if (inner.x < 0 || inner.y < 0 || inner.x + inner.w > L.w || inner.y + inner.h > L.h) return "";
  const hit = walls.find((r) => meets(inner, r));
  return hit ? hit.id || "" : null;
}
