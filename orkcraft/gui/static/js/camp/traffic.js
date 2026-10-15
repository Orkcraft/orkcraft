// The traffic on Camp's track (design-system-v3.md §4c rules 6–7): each rolling cart moves along its route at its own
// speed, but on one line carts keep a cart's distance and never overtake: one that catches up waits behind, the cart in
// front its reason. A switch throws while a cart that turns there is near, and stands still for one going on.
//
// Pure: no page (tests/test_camp_layout.py runs it in Node). A cart here is { id, pts, len, v (px a second), s (px
// along its route), rank (lower: earlier on the track, so it goes first when two stand on one spot), parks (its stop
// is a pocket, where it stays once there), throws }.

/** Where a cart stands `s` px along its route, and which way it faces: east (1) or west (−1) on a straight run, its
 *  last facing kept up and down a column (c1 draws carts from the side only). */
export function pointAt(pts, s) {
  let run = 0, face = 1;
  for (let i = 1; i < pts.length; i++) {
    const [ax, ay] = pts[i - 1], [bx, by] = pts[i];
    if (bx !== ax) face = bx < ax ? -1 : 1;
    const L = Math.hypot(bx - ax, by - ay);
    if (run + L >= s || i === pts.length - 1) {
      const u = L ? Math.max(0, Math.min(1, (s - run) / L)) : 1;
      return { x: ax + u * (bx - ax), y: ay + u * (by - ay), face };
    }
    run += L;
  }
  const p = pts[pts.length - 1] || [0, 0];
  return { x: p[0], y: p[1], face };
}

/** How far ahead of `from` along a route it first passes within `eps` of (x, y): Infinity when it never does. */
export function aheadOn(pts, from, x, y, eps) {
  let run = 0;
  for (let i = 1; i < pts.length; i++) {
    const [ax, ay] = pts[i - 1], [bx, by] = pts[i];
    const L = Math.hypot(bx - ax, by - ay);
    if (L && run + L >= from) {
      const u = Math.max(0, Math.min(1, ((x - ax) * (bx - ax) + (y - ay) * (by - ay)) / (L * L)));
      const at = run + u * L;
      if (at >= from && Math.hypot(ax + u * (bx - ax) - x, ay + u * (by - ay) - y) <= eps) return at - from;
    }
    run += L;
  }
  return Infinity;
}

/** One step of `dt` seconds: each cart on at its speed, but never nearer than `gap` to a cart in front of it on its
 *  way (one standing at its stop included); two on one spot: the earlier (lower rank) goes first. Returns the carts
 *  held back this step, by id → the id of the cart in front. Moves `s` in place. */
export function step(carts, dt, gap, eps) {
  const held = {};
  // the furthest along first, so each cart sees where the ones in front of it stand now (on one spot: the earlier)
  const order = carts.map((c, i) => i).sort((i, j) => carts[j].s - carts[i].s || carts[i].rank - carts[j].rank);
  const at = carts.map((c) => pointAt(c.pts, c.s));
  for (const i of order) {
    const a = carts[i], free = Math.min(a.len, a.s + a.v * dt);
    let want = free, by = null;
    carts.forEach((b, j) => {
      if (i === j || (b.s >= b.len && !b.parks)) return;      // one arrived at a station has left the line
      const d = aheadOn(a.pts, a.s, at[j].x, at[j].y, eps);
      if (d === Infinity || (d < 1 && b.rank > a.rank)) return;
      if (a.s + d - gap < want) { want = a.s + d - gap; by = b.id; }
    });
    a.s = Math.max(a.s, want);
    at[i] = pointAt(a.pts, a.s);
    if (by !== null && want < free) held[a.id] = by;
  }
  return held;
}

/** Which switches are thrown now: a switch is thrown while a cart that turns there is within `near` px before it (or
 *  on it); a cart going on leaves it still. `n` switches; each cart's `throws`: [{ i, way, at }]. */
export function thrown(n, carts, near, past) {
  const out = Array.from({ length: n }, () => false);
  for (const c of carts) {
    for (const t of c.throws || []) {
      if (t.way === "turn" && c.s >= t.at - near && c.s <= t.at + past) out[t.i] = true;
    }
  }
  return out;
}
