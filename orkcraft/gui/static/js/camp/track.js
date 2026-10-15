// Camp's track, one way round (design-system-v3.md §4c rules 5–7): east along the lines, down the right column, west
// along the return line under the lowest row, up the left column. Each tile says which ways a cart may leave it
// (`go`), so a route never runs backwards: a cart for a building behind it goes on, round the return line and in
// again. A fork (into a line from the left column, on to the buffer stop or down to the return line) has a switch
// stand beside it. A cart waiting at a building stands off the line on its path's end: no pocket track (§4c rule 7).
//
// Pure: no page (tests/test_camp_layout.py runs it in Node). Every number is CSS px in the world's frame.

// A tile's ways out (n e s w), turned a quarter clockwise `rot` / 90 times. `t-e` is c3's north–east–south junction
// (the split on the left), `t-n` c2's north T (turned: the right column's T and the switch to the return line).
const EXITS = { "straight-h": "ew", "straight-v": "ns", "corner-ne": "ne", "corner-sw": "sw", "corner-se": "se",
                "corner-nw": "nw", "t-n": "new", "t-e": "nes", "stop-e": "w" };
const CW = { n: "e", e: "s", s: "w", w: "n" };
export function exitsOf(name, rot = 0) {
  let out = [...(EXITS[name] || "")];
  for (let k = 0; k < ((rot / 90) % 4 + 4) % 4; k++) out = out.map((d) => CW[d]);
  return new Set(out);
}

export const STEP = { n: [0, -1], e: [1, 0], s: [0, 1], w: [-1, 0] };
export const BACK = { n: "s", e: "w", s: "n", w: "e" };

/** The loop's tiles, `go` on each, and its switches. `lines`: each line's top y; `colL` the left column's x; `colR`
 *  the right column's x with two rows or more (`multi`), else where the one line ends. Returns { tiles, switches,
 *  buffer, ret } (`ret`: the return line's top y). */
export function loop(T, lines, colL, colR, multi) {
  const tiles = [], switches = [];
  const tile = (name, x, y, rot, go, extra = {}) => { const t = { name, x, y, rot, go, ...extra }; tiles.push(t); return t; };
  const last = lines.length - 1, endY = lines[last];
  // the way in: down the left column from outside the wall to line 1
  for (let y = lines[0] - T; y > -T; y -= T) tile("straight-v", colL, y, 0, "s");
  lines.forEach((ly, r) => {
    // the split on the left: in from the way in (line 1) or up from the return line; east into the line, or on up
    const sw = tile("t-e", colL, ly, 0, r === 0 ? "e" : "en");
    if (r > 0) switches.push({ x: colL, y: ly, on: "n", turn: "e", side: "w", tile: sw });
    for (let x = colL + T; x < colR; x += T) tile("straight-h", x, ly, 0, "e");
    if (multi) {                                                       // the right column: down to the last line
      if (r === 0) tile("corner-sw", colR, ly, 0, "s");
      else if (r < last) tile("t-n", colR, ly, -90, "s");
      else tile("t-n", colR, ly, 0, "e");
      if (r < last) for (let y = ly + T; y < lines[r + 1]; y += T) tile("straight-v", colR, y, 0, "s");
    }
    // up the left column from the line below (the way back from the return line)
    const below = r < last ? lines[r + 1] : endY + T;
    for (let y = ly + T; y < below; y += T) tile("straight-v", colL, y, 0, "n");
  });
  // on the right: the switch, on to the buffer stop or down to the return line; west along it; up the left column
  const xs = multi ? colR + T : colR;
  const out = tile("t-n", xs, endY, 180, "es");
  switches.push({ x: xs, y: endY, on: "e", turn: "s", side: "n", tile: out, ret: true });
  tile("stop-e", xs + T, endY, 0, "");
  const ret = endY + T;
  tile("corner-nw", xs, ret, 0, "w");
  for (let x = xs - T; x > colL; x -= T) tile("straight-h", x, ret, 0, "w", { ret: true });
  tile("corner-ne", colL, ret, 0, "n");
  for (const t of tiles) t.exits = exitsOf(t.name, t.rot);
  return { tiles, switches, buffer: { x: xs + T + T / 2, y: endY + T / 2 }, ret, xs };
}

/** The tiles by "x,y". */
export function cellsOf(tiles) {
  return new Map(tiles.filter((t) => !t.siding).map((t) => [`${t.x},${t.y}`, t]));
}

/** The way from one point to another along the track, one way round: the tiles a cart passes, first to last; null
 *  when there is none. A tile is left only by its `go` and entered only where it has an exit. */
export function path(cells, T, from, to) {
  const cellOf = (p) => cells.get(`${Math.floor(p.x / T) * T},${Math.floor(p.y / T) * T}`)
    || [...cells.values()].find((t) => p.x >= t.x && p.x < t.x + T && p.y >= t.y && p.y < t.y + T) || null;
  const start = cellOf(from), end = cellOf(to);
  if (!start || !end) return null;
  const key = (t) => `${t.x},${t.y}`;
  const prev = new Map([[key(start), null]]), queue = [start];
  while (queue.length) {
    const t = queue.shift();
    if (t === end) break;
    for (const d of t.go) {
      const n = cells.get(`${t.x + STEP[d][0] * T},${t.y + STEP[d][1] * T}`);
      if (!n || !n.exits.has(BACK[d]) || prev.has(key(n))) continue;
      prev.set(key(n), t);
      queue.push(n);
    }
  }
  if (!prev.has(key(end))) return null;
  const chain = [];
  for (let t = end; t; t = prev.get(key(t))) chain.unshift(t);
  return chain;
}

/** The switches a chain of tiles passes and the way each is set for it: [{ i (the switch's index), way: on|turn,
 *  at (its distance along the route's points) }]. */
export function throwsOn(switches, chain, pts, T) {
  const out = [];
  for (let k = 0; k < chain.length - 1; k++) {
    const i = switches.findIndex((s) => s.tile === chain[k]);
    if (i < 0) continue;
    const s = switches[i], n = chain[k + 1];
    const d = n.x > s.x ? "e" : n.x < s.x ? "w" : n.y > s.y ? "s" : "n";
    out.push({ i, way: d === s.turn ? "turn" : "on", at: along(pts, s.x + T / 2, s.y + T / 2) });
  }
  return out;
}

/** How far along a polyline its point nearest (cx, cy) lies. */
export function along(pts, cx, cy) {
  let best = Infinity, at = 0, run = 0;
  for (let i = 1; i < pts.length; i++) {
    const [ax, ay] = pts[i - 1], [bx, by] = pts[i];
    const L = Math.hypot(bx - ax, by - ay) || 1;
    const u = Math.max(0, Math.min(1, ((cx - ax) * (bx - ax) + (cy - ay) * (by - ay)) / (L * L)));
    const px = ax + u * (bx - ax), py = ay + u * (by - ay), dd = Math.hypot(px - cx, py - cy);
    if (dd < best) { best = dd; at = run + u * L; }
    run += L;
  }
  return at;
}

/** Points with the ones in the middle of a straight run left out. */
export function simplify(pts) {
  const out = [];
  for (const p of pts) {
    if (out.length && out[out.length - 1][0] === p[0] && out[out.length - 1][1] === p[1]) continue;
    if (out.length >= 2) {
      const [a, b] = [out[out.length - 2], out[out.length - 1]];
      if ((a[0] === b[0] && b[0] === p[0]) || (a[1] === b[1] && b[1] === p[1])) out.pop();
    }
    out.push(p);
  }
  return out;
}

/** The length of a polyline, px. */
export function lengthOf(pts) {
  let n = 0;
  for (let i = 1; i < pts.length; i++) n += Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]);
  return n;
}
