// Where roads run on the town: gates on the huts and orthogonal paths between them, as the TUI
// lays them (wm/roadmap.py, ported: the page plans them itself, so a road follows a hut while it is
// dragged). Gates sit on the side of a hut that faces the other end, several on one side spread
// evenly; paths are A* on a grid of CELL px where a step under a hut costs WINDOW_COST, a turn
// TURN_COST and a step on a cell an earlier road took LANE_COST, so roads keep to the gaps, turn as
// little as they can and run side by side in lanes of their own instead of on top of each other.
// A road leaves its gate and comes into one straight for STUB cells, so it never bends right at a hut.

const CELL = 8;
const WINDOW_COST = 40;
const TURN_COST = 3;
const LANE_COST = 6;
const STUB = 6;                            // cells a road runs straight out of a gate before it may turn
const STEP = { left: [-1, 0], right: [1, 0], top: [0, -1], bottom: [0, 1] };
const DIRS = [[1, 0], [-1, 0], [0, 1], [0, -1]];

function toCells(r) {
  const x = Math.floor(r.x / CELL), y = Math.floor(r.y / CELL);
  return { x, y, w: Math.max(Math.ceil((r.x + r.w) / CELL) - x, 1), h: Math.max(Math.ceil((r.y + r.h) / CELL) - y, 1) };
}

/** The side of `a` that faces `b` (cells are square here: no aspect to make up for). */
export function facingSide(a, b) {
  const horizontal = b.x >= a.x + a.w ? "right" : b.x + b.w <= a.x ? "left" : "";
  const vertical = b.y >= a.y + a.h ? "bottom" : b.y + b.h <= a.y ? "top" : "";
  if (horizontal && vertical) {
    const gapX = horizontal === "right" ? b.x - (a.x + a.w) : a.x - (b.x + b.w);
    const gapY = vertical === "bottom" ? b.y - (a.y + a.h) : a.y - (b.y + b.h);
    return gapX >= gapY ? horizontal : vertical;
  }
  if (horizontal || vertical) return horizontal || vertical;
  const dx = b.x + b.w / 2 - (a.x + a.w / 2), dy = b.y + b.h / 2 - (a.y + a.h / 2);
  if (Math.abs(dx) >= Math.abs(dy)) return dx >= 0 ? "right" : "left";
  return dy >= 0 ? "bottom" : "top";
}

function gateCell(g, side, i, k) {
  if (side === "left" || side === "right") {
    const span = Math.max(g.h - 2, 1);
    const y = g.y + 1 + Math.floor((span * (i + 1)) / (k + 1));
    return [side === "left" ? g.x : g.x + g.w - 1, Math.min(y, g.h > 2 ? g.y + g.h - 2 : g.y)];
  }
  const span = Math.max(g.w - 2, 1);
  const x = g.x + 1 + Math.floor((span * (i + 1)) / (k + 1));
  return [Math.min(x, g.w > 2 ? g.x + g.w - 2 : g.x), side === "top" ? g.y : g.y + g.h - 1];
}

function gates(geoms, roads, sideways = false) {
  const slots = new Map();
  for (const r of roads) {
    const a = geoms[r.from], b = geoms[r.to];
    if (!a || !b) continue;
    for (const [bid, role, me, other] of [[r.from, "exit", a, b], [r.to, "entry", b, a]]) {
      // Camp: roads meet a card on its left or right edge (its name and sprite stand above it)
      const side = sideways ? (other.x + other.w / 2 >= me.x + me.w / 2 ? "right" : "left") : facingSide(me, other);
      // along the side by where the other end lies, so roads do not cross at the hut
      const key = side === "left" || side === "right" ? other.y + other.h / 2 : other.x + other.w / 2;
      const slot = `${bid}\u0000${side}`;
      if (!slots.has(slot)) slots.set(slot, { bid, side, items: [] });
      slots.get(slot).items.push({ id: r.id, role, key });
    }
  }
  const out = {};
  for (const { bid, side, items } of slots.values()) {
    items.sort((p, q) => p.key - q.key || (p.id < q.id ? -1 : p.id > q.id ? 1 : 0) || (p.role < q.role ? -1 : 1));
    items.forEach((it, i) => {
      const [x, y] = gateCell(geoms[bid], side, i, items.length);
      (out[it.id] ||= {})[it.role] = { x, y, side };
    });
  }
  return out;
}

// A small binary heap of [priority, ...] arrays.
function push(heap, item) {
  heap.push(item);
  let i = heap.length - 1;
  while (i > 0) {
    const p = (i - 1) >> 1;
    if (heap[p][0] <= heap[i][0]) break;
    [heap[p], heap[i]] = [heap[i], heap[p]];
    i = p;
  }
}

function pop(heap) {
  const top = heap[0], last = heap.pop();
  if (heap.length) {
    heap[0] = last;
    let i = 0;
    for (;;) {
      const l = 2 * i + 1, r = l + 1;
      let m = i;
      if (l < heap.length && heap[l][0] < heap[m][0]) m = l;
      if (r < heap.length && heap[r][0] < heap[m][0]) m = r;
      if (m === i) break;
      [heap[m], heap[i]] = [heap[i], heap[m]];
      i = m;
    }
  }
  return top;
}

/** The cheapest orthogonal path of cells from `start` to `end`, both included. `taken` (optional): the
 * cells earlier roads run on, which cost LANE_COST more to step on. */
export function route(start, end, under, width, height, taken = null) {
  const [sx, sy] = start, [ex, ey] = end;
  if (sx === ex && sy === ey) return [start];
  const key = (x, y, d) => (y * width + x) * 4 + d;
  const best = new Map(), came = new Map(), heap = [];
  for (let d = 0; d < 4; d++) {
    best.set(key(sx, sy, d), 0);
    came.set(key(sx, sy, d), -1);
    push(heap, [Math.abs(ex - sx) + Math.abs(ey - sy), 0, sx, sy, d]);
  }
  while (heap.length) {
    const [, cost, x, y, d] = pop(heap);
    if (cost > (best.get(key(x, y, d)) ?? Infinity)) continue;
    if (x === ex && y === ey) {
      const path = [];
      for (let k = key(x, y, d); k !== -1; k = came.get(k)) {
        const cell = Math.floor(k / 4);
        path.push([cell % width, Math.floor(cell / width)]);
      }
      path.reverse();
      return path.filter((c, i) => i === 0 || c[0] !== path[i - 1][0] || c[1] !== path[i - 1][1]);
    }
    for (let nd = 0; nd < 4; nd++) {
      const nx = x + DIRS[nd][0], ny = y + DIRS[nd][1];
      if (nx < 0 || ny < 0 || nx >= width || ny >= height) continue;
      const nc = cost + (under[ny * width + nx] ? WINDOW_COST : 1) + (nd !== d ? TURN_COST : 0)
        + (taken && taken[ny * width + nx] ? LANE_COST : 0);
      const k = key(nx, ny, nd);
      if (nc < (best.get(k) ?? Infinity)) {
        best.set(k, nc);
        came.set(k, key(x, y, d));
        push(heap, [nc + Math.abs(ex - nx) + Math.abs(ey - ny), nc, nx, ny, nd]);
      }
    }
  }
  return [start, end];
}

const centre = ([x, y]) => [x * CELL + CELL / 2, y * CELL + CELL / 2];

/** Where a gate meets its hut, in px: the middle of the hut's edge cell, on the edge itself. */
function edgePoint(g, rect) {
  const [cx, cy] = centre([g.x, g.y]);
  if (g.side === "left") return [rect.x, cy];
  if (g.side === "right") return [rect.x + rect.w, cy];
  if (g.side === "top") return [cx, rect.y];
  return [cx, rect.y + rect.h];
}

/** Only the corners of an orthogonal polyline. */
function corners(points) {
  const out = [];
  for (const p of points) {
    if (out.length && out[out.length - 1][0] === p[0] && out[out.length - 1][1] === p[1]) continue;
    if (out.length >= 2) {
      const [a, b] = [out[out.length - 2], out[out.length - 1]];
      if ((a[0] === b[0] && b[0] === p[0]) || (a[1] === b[1] && b[1] === p[1])) out.pop();
    }
    out.push(p);
  }
  return out;
}

/** Every road with both ends on the town: {id, points (px, its corners), exit, entry}. `ports` (default the
 *  huts themselves) are where gates sit — Camp's huts carry a sprite over their card, and roads meet the card;
 *  the huts whole stay what the roads go round. */
export function plan(rects, roads, roomW, roomH, ports = rects, sideways = false) {
  const width = Math.max(Math.ceil(roomW / CELL), 1), height = Math.max(Math.ceil(roomH / CELL), 1);
  const geoms = {};
  for (const [id, r] of Object.entries(ports)) geoms[id] = toCells(r);
  const under = new Uint8Array(width * height);
  for (const g of Object.values(rects).map(toCells)) {
    for (let y = Math.max(g.y, 0); y < Math.min(g.y + g.h, height); y++) {
      under.fill(1, y * width + Math.max(g.x, 0), y * width + Math.min(g.x + g.w, width));
    }
  }
  const clamp = ([x, y]) => [Math.min(Math.max(x, 0), width - 1), Math.min(Math.max(y, 0), height - 1)];
  const all = gates(geoms, roads, sideways);
  const taken = new Uint8Array(width * height);
  const out = [];
  for (const r of roads) {
    const g = all[r.id];
    if (!g || !g.exit || !g.entry) continue;
    // Straight out of each gate for up to STUB cells: never into another hut, and where the two gates
    // face each other, each to half the gap, so a short jog between them bends in the middle.
    const reach = (gate, most) => {
      const [dx, dy] = STEP[gate.side];
      let n = 1;
      while (n < most) {
        const [x, y] = [gate.x + dx * (n + 1), gate.y + dy * (n + 1)];
        if (x < 0 || y < 0 || x >= width || y >= height || under[y * width + x]) break;
        n++;
      }
      return n;
    };
    let most = STUB;
    if (STEP[g.exit.side][0] === -STEP[g.entry.side][0] && STEP[g.exit.side][1] === -STEP[g.entry.side][1]) {
      const [dx, dy] = STEP[g.exit.side];
      const gap = (g.entry.x - g.exit.x) * dx + (g.entry.y - g.exit.y) * dy - 1;   // free cells between, facing
      if (gap > 0) most = Math.max(Math.min(STUB, Math.ceil(gap / 2)), 1);
    }
    const stub = (gate) => {
      const n = reach(gate, most), [dx, dy] = STEP[gate.side];
      return Array.from({ length: n }, (_, i) => clamp([gate.x + dx * (i + 1), gate.y + dy * (i + 1)]));
    };
    const away = stub(g.exit), back = stub(g.entry);
    const cells = route(away[away.length - 1], back[back.length - 1], under, width, height, taken);
    for (const [x, y] of [...away, ...cells, ...back]) taken[y * width + x] = 1;
    const exit = edgePoint(g.exit, ports[r.from]), entry = edgePoint(g.entry, ports[r.to]);
    // From the edge straight out along the gate's side, then cell by cell, then straight in.
    const first = centre(cells[0]), last = centre(cells[cells.length - 1]);
    const lead = g.exit.side === "left" || g.exit.side === "right" ? [first[0], exit[1]] : [exit[0], first[1]];
    const tail = g.entry.side === "left" || g.entry.side === "right" ? [last[0], entry[1]] : [entry[0], last[1]];
    out.push({ id: r.id, exit, entry, side: g.exit.side, entrySide: g.entry.side,
               points: corners([exit, lead, ...cells.map(centre), tail, entry]) });
  }
  return out;
}
