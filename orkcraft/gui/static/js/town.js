// The town: every building of the orkspace as a hut card where the person put it, and the roads
// between them. Office draws huts as explorer cards and roads as a block diagram: 2px lines with an
// exit dot and an arrowhead, dashed when plain, moss green when a handler works on them, labelled,
// rounded at the bends and broken where another road crosses over (design-system/components.md: Hut,
// Road). Positions are the person's: dragging a hut saves its spot as fractions of the room (`hut`
// in the Town Scroll, the same the TUI reads). As in an RTS, a drag or a stretch moves only a ghost outline;
// no other hut moves to make room: where the ghost would stand on one it turns red, and a drop there is no
// move at all (Footprint).
import { signal } from "@preact/signals";
import { useEffect, useLayoutEffect, useRef, useState } from "preact/hooks";
import { html, cls } from "./html.js";
import { command, say, town as snapshot } from "./link.js";
import { opened, openBuilding, closeBuilding, panelShown, panelWidth } from "./windows.js";
import { plan } from "./roads.js";
import { pickedRoad, building as buildOpen, placing, constructing, built, raised } from "./build.js";
import { openMenu } from "./menu.js";
import { settingsOpen } from "./settings.js";
import { Hut, sizes, dragging, resizing, pulling, pullRoad, CORNER, fenced, bareOf, YARD_STEP } from "./hut.js";
import { lost } from "./parts.js";
import { tidySpots } from "./tidy.js";
import { foldQuiet, unfoldAll, quiet } from "./fold.js";
import { Ghost, planned as onboardingPlan, risen } from "./onboarding.js";
import { activeBiome } from "./icons.js";

const room = signal({ w: 1, h: 1, strip: 0 });
let numbered = [];                         // the huts' ids in the order of the numbers on their names

// 1–9 open the building with that number on its name, from anywhere but a field, a terminal or a dialog.
window.addEventListener("keydown", (e) => {
  if (e.ctrlKey || e.metaKey || e.altKey || !/^[1-9]$/.test(e.key) || document.querySelector(".gui-modal, .gui-menu")) return;
  if (e.target.closest && e.target.closest("input, textarea, select, [contenteditable], .gui-term")) return;
  const id = numbered[Number(e.key) - 1];
  if (!id) return;
  e.preventDefault();
  openBuilding(id);
});
const dropped = signal({});                // building id → {x, y}: where a hut was dropped, till the town says so

// The room never gets smaller than four huts across and three down: a narrower town scrolls, so
// huts placed as fractions never pile up when a window opens beside it.
const MIN_ROOM = { w: 1080, h: 600 };
const COLS = 4, ROWS = 3;
const MARGIN = 24;                          // between the room's edge and the outermost huts
const STRIP = 64;                          // the town's foot (the orkspaces, the Warchief's line, layout.css .gui-foot): no hut under it
const DEFAULT_SIZE = { w: 240, h: 64 };     // a hut not drawn yet
const RAISING_SIZE = { w: 140, h: 60 };     // a building under scaffolding (js/build.js raised): its house, where it was placed

// A card that shows something and has no size of its own takes the free room right of it and under it
// (docs/design/yards.md §7): the more room, the more it shows (js/hut.js levelOf). It keeps a road's gap from every
// other card, the town's edges and its foot, and grows no bigger than a large card.
// Off until it is proven (docs/design/yards.md §7): this browser turns it on with localStorage "orkcraft.grow" = "1".
const GROW_ON = (() => { try { return localStorage.getItem("orkcraft.grow") === "1"; } catch { return false; } })();
const GROW_GAP = 32;
const GROW_MAX = { w: 560, h: 440 };
const natural = {};                         // building id → its size as drawn while it was not grown
let grownLast = new Set();                      // the cards grown at the last draw: the town places them by their natural size
const LEVEL_H = [400, 240];                 // the heights where a card shows more (js/hut.js levelOf: l, m), tallest first
const LEVEL_W = [520, 360];

// Growth is worked out once per layout (the room, the buildings, where each stands, their natural sizes, rounded) and
// kept while it holds, so a card's new size never feeds the next draw's answer. A layout that still will not settle
// (it changed more than 6 times in a second) keeps its last growth until the town itself changes.
let held = { key: "", auto: {}, changes: [], frozen: "" };
function steady(compute, key, town) {
  if (held.frozen && held.frozen === town) return held.auto;
  if (key === held.key) return held.auto;
  const now = Date.now();
  const changes = [...held.changes.filter((t) => now - t < 1000), now];
  held = { key, auto: compute(), changes, frozen: changes.length > 6 ? town : "" };
  return held.auto;
}

/** The [w, h] each growing card takes: cards taken top to bottom, each seeing the room the ones before took. */
function grow(buildings, spots, rects, held) {
  if (!GROW_ON) return {};
  const r = room.value;
  const camp = document.documentElement.dataset.look !== "office";
  const down = (v, by) => (camp ? Math.floor(v / by) * by : v);     // whole pickets, never past the room
  const taken = { ...rects };
  const out = {};
  const can = buildings.filter((b) => fenced(b) && !b.size && !b.folded && !held.has(b.id) && natural[b.id]);
  for (const b of can) taken[b.id] = { ...spots[b.id], w: natural[b.id].w, h: natural[b.id].h };
  can.sort((a, c) => spots[a.id].y - spots[c.id].y || spots[a.id].x - spots[c.id].x);
  for (const b of can) {
    const n = natural[b.id], at = spots[b.id], top = n.top || 0;
    const others = Object.entries(taken).filter(([id]) => id !== b.id).map(([, o]) => o);
    const right = Math.min(r.w - MARGIN, ...others.filter((o) => o.x > at.x && o.y < at.y + n.h && o.y + o.h > at.y).map((o) => o.x - GROW_GAP));
    const w = down(Math.min(Math.max(right - at.x, n.w), GROW_MAX.w), YARD_STEP.w);
    const bottom = Math.min(r.h - r.strip - MARGIN, ...others.filter((o) => o.y > at.y && o.x < at.x + w && o.x + o.w > at.x).map((o) => o.y - GROW_GAP));
    // Its height steps to the tallest level that fits (or stays as it comes): room past a level shows nothing more.
    const fits = Math.min(bottom - at.y - top, GROW_MAX.h);
    const up = (v) => (camp ? Math.ceil(v / YARD_STEP.h) * YARD_STEP.h : v);   // whole pickets, as js/hut.js draws it
    const lv = LEVEL_H.findIndex((lh, i) => up(lh) <= fits && w >= LEVEL_W[i]);
    const h = lv < 0 ? 0 : up(LEVEL_H[lv]);
    if (w <= n.w && h <= n.h - top) continue;              // no room to speak of: it stays as it comes
    out[b.id] = [Math.max(w, n.w), h > n.h - top ? h : null];     // null: its height as it comes, only wider
    taken[b.id] = { ...at, w: out[b.id][0], h: out[b.id][1] ? top + out[b.id][1] : n.h };
  }
  return out;
}

/** The room a hut's spot is a fraction of: the canvas less the hut, the margins and the foot. */
function free(size) {
  const r = room.value;
  return { w: Math.max(r.w - size.w - 2 * MARGIN, 1), h: Math.max(r.h - size.h - 2 * MARGIN - r.strip, 1) };
}

/** A hut without a spot of its own: a grid of four across, as fractions like a spot of its own. */
function defaultSpot(i) {
  return [(i % COLS) / (COLS - 1), Math.min(Math.floor(i / COLS) / (ROWS - 1), 1)];
}

function place(b, i, size) {
  const f = free(size);
  if (b.id === CORNER) {                       // Camp's Hall: the bottom-right corner, over the town's foot
    const r = room.value;
    return { x: Math.max(r.w - size.w - MARGIN, 0), y: Math.max(r.h - size.h - MARGIN - r.strip, 0) };
  }
  if (dropped.value[b.id]) return dropped.value[b.id];
  const [fx, fy] = b.hut || defaultSpot(i);
  return { x: MARGIN + fx * f.w, y: MARGIN + fy * f.h };
}

const SIDE_PX = 8;                          // a hut whose top is this close over another's bottom still stands under it

/** How far each hut is lifted: a hut with parts hidden (js/parts.js) lost some height, and every hut
 * under it — its sides overlapping, its top below the other's full bottom — moves up with it, as much
 * as the least lifted hut over it allows, so none rides onto another. `full`: id → {x, y, w, h, lost}. */
function lifts(full) {
  const ids = Object.keys(full).sort((a, b) => full[a].y - full[b].y);
  const up = {};
  for (const id of ids) {
    const b = full[id];
    if (id === CORNER) { up[id] = 0; continue; }   // the Hall keeps its corner
    const over = ids.filter((o) => o !== id && up[o] !== undefined && full[o].x < b.x + b.w && b.x < full[o].x + full[o].w
                                   && full[o].y + full[o].h <= b.y + SIDE_PX);
    up[id] = over.length ? Math.min(...over.map((o) => up[o] + full[o].lost)) : 0;
  }
  return up;
}

const GAP_PX = 12;                          // the least room between two huts once they settle
const CORNER_ROOM = { x: 0, y: 0, w: 88, h: 62 };   // the big portrait's corner (js/portrait.js): no hut stands under it

/** How far each hut is pushed down so none stands on another: a town of many buildings, a spot kept from a
 * smaller window, or a card that grew would otherwise lay one card over the next. Top to bottom, a hut that
 * meets one already settled moves to just under it; the spots kept stay as the person left them.
 * `rects`: id → {x, y, w, h}; `fixed`: ids that never move (the Hall in its corner, the hut being dragged). */
function settle(rects, fixed = new Set()) {
  const ids = Object.keys(rects).sort((a, b) => rects[a].y - rects[b].y || rects[a].x - rects[b].x);
  const down = {};
  const done = ids.filter((id) => fixed.has(id)).map((id) => rects[id]);
  for (const id of ids) {
    if (fixed.has(id)) { down[id] = 0; continue; }
    const r = { ...rects[id] };
    for (let guard = 0; guard <= done.length; guard++) {
      const hit = done.find((o) => o.x < r.x + r.w + GAP_PX && r.x < o.x + o.w + GAP_PX
                                   && o.y < r.y + r.h + GAP_PX && r.y < o.y + o.h + GAP_PX);
      if (!hit) break;
      r.y = hit.y + hit.h + GAP_PX;
    }
    down[id] = r.y - rects[id].y;
    done.push(r);
  }
  return down;
}

/** Where `a` would stand on `o`, kept GAP_PX apart as settle keeps them: the part of `a` it takes, or null. */
function overlap(a, o) {
  const x = Math.max(a.x, o.x - GAP_PX), y = Math.max(a.y, o.y - GAP_PX);
  const r = Math.min(a.x + a.w, o.x + o.w + GAP_PX), b = Math.min(a.y + a.h, o.y + o.h + GAP_PX);
  return r > x && b > y ? { x, y, w: r - x, h: b - y } : null;
}

/** A ghost at `r` for hut `id`: the parts of it that would stand on another hut or the portrait's corner. */
function footprint(id, r, rects) {
  const others = [...Object.entries(rects).filter(([o]) => o !== id).map(([, o]) => o), CORNER_ROOM];
  return { ...r, hits: others.map((o) => overlap(r, o)).filter(Boolean) };
}

/** The ghost outline of a hut being dragged or stretched; red where it would stand on another, each such part
 *  marked. Let go there and nothing moves. */
function Footprint({ g }) {
  const blocked = g.hits.length > 0;
  return html`<div class="gui-footprints" aria-hidden="true">
    <div class=${cls("gui-footprint", { "is-blocked": blocked })} style=${`left:${g.x}px;top:${g.y}px;width:${g.w}px;height:${g.h}px`}></div>
    ${g.hits.map((h, i) => html`<div key=${i} class="gui-footprint__hit" style=${`left:${h.x}px;top:${h.y}px;width:${h.w}px;height:${h.h}px`}></div>`)}
  </div>`;
}

// Planning every road is a few A* runs: keep the last plan while nothing it reads changed.
let planned = { key: "", paths: [] };

const pair = (x) => `${x.from}\u0000${x.to}`;

/** The roads from one building into the same other one, the first of them first: they run as one road
 *  (docs/design/road-sound.md §2). A road the other way is a road of its own: the two make a loop. */
function together(roads) {
  const out = new Map();
  for (const x of roads) {
    if (!out.has(pair(x))) out.set(pair(x), []);
    out.get(pair(x)).push(x);
  }
  return out;
}

function plannedPaths(rects, roads, ports = rects) {
  const r = room.value;
  const key = JSON.stringify([rects, ports, roads.map((x) => [x.id, x.from, x.to]), r.w, r.h]);
  if (key !== planned.key) {
    // Two roads between the same two buildings run as one, with both labels: the later ones take the
    // first one's path (their carts run on it), and only the first is drawn.
    const groups = [...together(roads).values()];
    const firsts = plan(rects, groups.map((g) => g[0]), r.w, r.h, ports);
    const byFirst = Object.fromEntries(firsts.map((p) => [p.id, p]));
    const paths = [...firsts];
    for (const g of groups) {
      const p = byFirst[g[0].id];
      if (p) for (const x of g.slice(1)) paths.push({ ...p, id: x.id, mate: g[0].id });
    }
    planned = { key, paths };
  }
  return planned.paths;
}

// A building's card may colour the start of its roads out (`card.tints`: road key → a design-system mark,
// `--mark-<name>`): the Signpost's counters wear the colours of their roads.
const MARKS = new Set(["blue", "green", "purple", "yellow", "red"]);
const TINT_PX = 28;

function start(points) {
  const out = [points[0]];
  let left = TINT_PX;
  for (let i = 1; i < points.length && left > 0; i++) {
    const [ax, ay] = points[i - 1], [bx, by] = points[i];
    const d = Math.hypot(bx - ax, by - ay);
    const k = d > left ? left / d : 1;
    out.push([ax + (bx - ax) * k, ay + (by - ay) * k]);
    left -= d;
  }
  return out.map((q) => q.join(",")).join(" ");
}

/** The point `frac` of the way along a polyline (by length), for a road's sign. */
function along(points, frac) {
  const lens = points.slice(1).map((q, i) => Math.hypot(q[0] - points[i][0], q[1] - points[i][1]));
  let left = lens.reduce((a, b) => a + b, 0) * frac;
  for (let i = 0; i < lens.length; i++) {
    if (left <= lens[i] && lens[i] > 0) {
      const k = left / lens[i], [ax, ay] = points[i], [bx, by] = points[i + 1];
      return [ax + (bx - ax) * k, ay + (by - ay) * k];
    }
    left -= lens[i];
  }
  return points[points.length - 1];
}

// Carts (docs/design/roads-and-orcs.md §4a): each one the town sent lately moves from its road's exit gate
// to its entry gate once, in the time the road takes (`travel`, else a short trip); a filtered one turns
// back at the source. A cart is drawn from where it is now: one that left a while ago starts on its way.
const started = new Map();               // cart id → its animation-delay, fixed when first seen
const SHORT_TRIP_S = 1.6;

function delayOf(c) {
  if (!started.has(c.id)) {
    started.set(c.id, `${-Math.min(c.age, 30)}s`);
    if (started.size > 400) started.delete(started.keys().next().value);
  }
  return started.get(c.id);
}

function Carts({ paths, carts, travel }) {
  const byRoad = Object.fromEntries(paths.map((p) => [p.id, p]));
  const trip = travel > 0 ? travel : SHORT_TRIP_S;
  return html`<div class="gui-carts" aria-hidden="true">
    ${carts.filter((c) => byRoad[c.road] && c.age < trip + 1).map((c) => {
      const p = byRoad[c.road];
      const d = "M" + p.points.map((q) => q.join(" ")).join(" L");
      const back = c.status === "filtered";
      return html`<div key=${c.id} class=${cls("gui-cart", { "is-back": back, "is-held": c.status === "held" || c.status === "error" })}
          style=${`offset-path: path("${d}"); animation-duration: ${back ? SHORT_TRIP_S : trip}s; animation-delay: ${delayOf(c)}`}>
        <img class="gui-cart__gold" src="/ds/sprites/icons/res-gold.png" srcset="/ds/sprites/icons/res-gold@2x.png 2x"
          width="8" height="8" alt="" />
        ${c.title && !back && html`<span class="gui-cart__label ok-font-status">${say(c.title)}</span>`}
      </div>`;
    })}
  </div>`;
}

/** Signs on the roads that wait for a route (a Signpost's, a Clan Fire's that routes) or are named in words: always shown. */
function Signs({ paths, roads }) {
  const byId = Object.fromEntries(roads.map((x) => [x.id, x]));
  const signed = paths.filter((p) => byId[p.id] && byId[p.id].sign);
  return html`<div class="gui-signs" aria-hidden="true">
    ${signed.map((p) => {
      // signs of roads that leave one gate for the same event stand apart along their roads
      const mates = signed.filter((q) => byId[q.id].from === byId[p.id].from && byId[q.id].event === byId[p.id].event);
      const i = mates.indexOf(p);
      const [x, y] = along(p.points, (i + 1) / (mates.length + 1));
      return html`<span key=${p.id} class="gui-sign ok-font-status" style=${`left:${x}px;top:${y}px`}>${say(byId[p.id].sign)}</span>`;
    })}
  </div>`;
}

/** A building's ways out with no road yet (a Review board's exits, a Signpost's routes): a short dashed stub off its
 *  right edge with its sign; pull a road from it to a building and the road is laid for it (review-board.md §2.1). */
function LooseEnds({ buildings, rects }) {
  return html`<div class="gui-loose-ends">${buildings.filter((b) => b.loose && b.loose.length && rects[b.id]).map((b) =>
    b.loose.map((x, i) => {
      const r = rects[b.id];
      return html`<button key=${`${b.id}:${x.route}`} class="gui-loose" style=${`left:${r.x + r.w}px;top:${r.y + r.h - 18 - i * 26}px`}
          title=${say(`${x.name}: no road goes this way yet — pull one to a building`)} aria-label=${say(`Connect ${x.name}`)}
          onPointerDown=${(e) => pullRoad(e, b.id, x.event)}>
        <span class="gui-loose__stub"></span><span class="gui-sign gui-loose__sign ok-font-status">${say(x.name)}</span>
      </button>`;
    }))}</div>`;
}

const BEND_PX = 4;                          // a road's bends are rounded (radius-md)

/** A road's corners as a path, each bend rounded by up to `r` px. */
function pathOf(points, r) {
  const at = (p) => `${p[0]} ${p[1]}`;
  let d = `M ${at(points[0])}`;
  for (let i = 1; i < points.length - 1; i++) {
    const [a, p, b] = [points[i - 1], points[i], points[i + 1]];
    const la = Math.hypot(p[0] - a[0], p[1] - a[1]), lb = Math.hypot(b[0] - p[0], b[1] - p[1]);
    const k = Math.min(r, la / 2, lb / 2);
    if (!k) { d += ` L ${at(p)}`; continue; }
    const p1 = [p[0] - ((p[0] - a[0]) / la) * k, p[1] - ((p[1] - a[1]) / la) * k];
    const p2 = [p[0] + ((b[0] - p[0]) / lb) * k, p[1] + ((b[1] - p[1]) / lb) * k];
    d += ` L ${at(p1)} Q ${at(p)} ${at(p2)}`;
  }
  return d + ` L ${at(points[points.length - 1])}`;
}

/** Where a road's label goes: on a free stretch of its road, never over a card or another label (ui.md U02).
 *  Its straight runs are tried longest first, each at its middle, then a quarter in from either end, above or
 *  below a level run and right or left of an upright one; the first spot whose box clears every card and every
 *  label already placed (`taken`, which it joins) wins. None clears: the middle of the longest run, as before. */
function labelSpot(points, label = "", cards = [], taken = []) {
  const runs = [];
  for (let i = 1; i < points.length; i++) {
    const [a, b] = [points[i - 1], points[i]];
    runs.push({ a, b, len: Math.abs(b[0] - a[0]) + Math.abs(b[1] - a[1]) });
  }
  runs.sort((p, q) => q.len - p.len);
  if (!runs.length) return { x: (points[0] || [0])[0], y: (points[0] || [0, 0])[1], anchor: "middle" };
  const w = label.length * 6.5 + 4, h = 14;
  const box = (s) => {
    const left = s.anchor === "middle" ? s.x - w / 2 : s.anchor === "end" ? s.x - w : s.x;
    return { x: left, y: s.y - 11, w, h };
  };
  const hits = (p, q) => p.x < q.x + q.w + 2 && q.x < p.x + p.w + 2 && p.y < q.y + q.h + 2 && q.y < p.y + p.h + 2;
  const spots = (run) => [0.5, 0.25, 0.75].flatMap((f) => {
    const x = run.a[0] + (run.b[0] - run.a[0]) * f, y = run.a[1] + (run.b[1] - run.a[1]) * f;
    return run.a[1] === run.b[1] ? [{ x, y: y - 6, anchor: "middle" }, { x, y: y + 14, anchor: "middle" }]
      : [{ x: x + 6, y: y + 4, anchor: "start" }, { x: x - 6, y: y + 4, anchor: "end" }];
  });
  const fits = (run) => run.len >= (run.a[1] === run.b[1] ? w : h + 8);
  for (const run of runs.filter(fits)) {
    for (const s of spots(run)) {
      const b = box(s);
      if (b.x < 0 || b.y < 0 || cards.some((c) => hits(b, c)) || taken.some((t) => hits(b, t))) continue;
      taken.push(b);
      return s;
    }
  }
  return spots(runs[0])[0];
}

// The arrowheads Office puts at a road's entry, one per colour a road can wear (layout.css picks one).
const HEADS = [["gui-road-head", "--road"], ["gui-road-head-live", "--road-live"], ["gui-road-head-selected", "--road-selected"]];

function Roads({ roads, rects, ports, tints = {} }) {
  const r = room.value;
  const byId = Object.fromEntries(roads.map((x) => [x.id, x]));
  const groups = together(roads);
  const active = opened.value.active;
  // A press on a road picks all of it: its card lists every road that runs as one (js/build.js RoadBar).
  const pick = (g) => { pickedRoad.value = g[0].id; };
  const cards = Object.values(rects), taken = [];
  return html`<svg class=${cls("gui-roads", { "has-focus": !!active && !!rects[active] })} width=${r.w} height=${r.h} aria-hidden="true">
    <defs>${HEADS.map(([id, token]) => html`<marker id=${id} viewBox="0 0 10 10" refX="10" refY="5" markerWidth="10"
      markerHeight="10" markerUnits="userSpaceOnUse" orient="auto"><path d="M 0 0 L 10 5 L 0 10 Z" style=${`fill: var(${token})`} /></marker>`)}</defs>
    ${plannedPaths(rects, roads, ports).filter((p) => !p.mate).map((p) => {
      const road = byId[p.id];
      const g = groups.get(pair(road)) || [road];
      const out = active === road.from, into = active === road.to;
      const d = pathOf(p.points, BEND_PX);
      const label = g.filter((x) => !x.sign).map((x) => x.label).join(" · ");
      const spot = labelSpot(p.points, label, cards, taken);
      return html`<g key=${p.id} class=${cls("gui-road", { "is-selected": out || into || g.some((x) => x.id === pickedRoad.value),
                                                         "is-out": out, "is-in": into && !out, "is-live": g.some((x) => !!x.handler),
                                                         "is-return": g.some((x) => x.returns) })}>
        <path d=${d} class="gui-road__halo" />
        <path d=${d} class="gui-road__line" />
        ${MARKS.has(tints[p.id]) && html`<polyline points=${start(p.points)} class="gui-road__tint" style=${`stroke: var(--mark-${tints[p.id]}); stroke-width: 4`} />`}
        <path d=${d} class="gui-road__hit" onClick=${() => pick(g)} />
        <circle cx=${p.exit[0]} cy=${p.exit[1]} r="3" class="gui-road__out" /><circle cx=${p.entry[0]} cy=${p.entry[1]} r="4" class="gui-road__in" />
        ${label && html`<text x=${spot.x} y=${spot.y} text-anchor=${spot.anchor} class="gui-road__label ok-font-status">${label}</text>`}
      </g>`;
    })}
    ${pulling.value && rects[pulling.value.from] && html`<line class="gui-road__pull"
      x1=${rects[pulling.value.from].x + rects[pulling.value.from].w} y1=${rects[pulling.value.from].y + rects[pulling.value.from].h / 2}
      x2=${pulling.value.x} y2=${pulling.value.y} />`}
    ${pulling.value && html`<rect class="gui-road__pull-end" x=${Math.round(pulling.value.x) - 3} y=${Math.round(pulling.value.y) - 3}
      width="6" height="6" />`}
  </svg>`;
}

/** A spot on the room as the fractions a hut keeps (`hut` in the Town Scroll): where Build here raises one. */
function spotAt(x, y) {
  const f = free(DEFAULT_SIZE);
  return [Math.min(Math.max((x - MARGIN) / f.w, 0), 1), Math.min(Math.max((y - MARGIN) / f.h, 0), 1)];
}

/** Tidy up: every hut that may move goes to its spot along the roads (js/tidy.js). */
function tidy(buildings, roads) {
  const spots = tidySpots(buildings.filter((b) => b.id !== CORNER), roads, (id) => !!buildings.find((b) => b.id === id)?.pinned);
  for (const [id, [x, y]] of Object.entries(spots)) command("hut.move", { id, x, y }).catch(() => {});
}

/** The right click on the bare town: Build here, Tidy up, fold or unfold the huts, the town's settings. */
function bareMenu(e, buildings, roads) {
  if (e.target.closest(".gui-hut, .gui-road")) return;
  const r = e.currentTarget.querySelector(".gui-town__room").getBoundingClientRect();
  const hut = spotAt(e.clientX - r.left, e.clientY - r.top);
  openMenu(e, [
    { label: "Build here…", hint: "/build", run: () => { buildOpen.value = { hut }; } },
    buildings.some((b) => b.id !== CORNER && !b.pinned) && { label: "Tidy up", hint: "along the roads", run: () => tidy(buildings, roads) },
    buildings.some(quiet) && { label: "Fold the quiet ones", hint: "/fold", run: () => foldQuiet(buildings) },
    buildings.some((b) => b.folded) && { label: "Unfold all", hint: "/unfold", run: () => unfoldAll(buildings) },
    { label: "Settings", run: () => { settingsOpen.value = true; } },
    { label: "Set up again…", hint: "AI tools · class · MCP", run: () => command("onboarding.start").catch(() => {}) },
  ]);
}

/** Where the part of the town seen begins for these buildings: past the town's left chrome (the portrait's
 *  corner, the War Map) that stands at their height, else the room's margin. */
function leftOf(el, boxes) {
  const er = el.getBoundingClientRect();
  let inset = MARGIN;
  for (const c of document.querySelectorAll(".gui-portrait-slot.is-corner, .gui-map")) {
    const r = c.getBoundingClientRect();
    const top = r.top - er.top + el.scrollTop, bottom = r.bottom - er.top + el.scrollTop;
    if (boxes.some((b) => b.y < bottom && b.y + b.h > top)) inset = Math.max(inset, r.right - er.left + MARGIN / 2);
  }
  return inset;
}

/** The panel covers the town's right part: the room grows by as much, so the open building and the
 *  buildings its roads reach can be scrolled into the part left, and they are. */
function useCamera(el, rects, here, panelW) {
  const active = opened.value.active;
  useEffect(() => {
    if (!el || !active || !rects[active] || !panelW) return;
    const near = here.flatMap((r) => (r.from === active ? [r.to] : r.to === active ? [r.from] : [])).filter((id) => rects[id]);
    const boxes = [active, ...near].map((id) => rects[id]);
    const span = (xs) => [Math.min(...xs.map((x) => x.x)), Math.max(...xs.map((x) => x.x + x.w))];
    const [left, right] = span(boxes);
    const seen = el.clientWidth - panelW;
    const a = rects[active];
    // all of them when they fit, else the building itself, in the middle of the part left — right of the
    // portrait's corner and the War Map where a building stands as high or as low as they do
    const all = right - left <= seen - MARGIN - leftOf(el, boxes);
    const [from, to] = all ? [left, right] : span([a]);
    const inset = leftOf(el, all ? boxes : [a]);
    if (from >= el.scrollLeft + inset && to <= el.scrollLeft + seen - MARGIN) return;
    el.scrollTo({ left: Math.max((from + to) / 2 - (inset + seen - MARGIN) / 2, 0), behavior: "smooth" });
  }, [active, panelW]);
}

/** A building picked in Build, placed with the mouse (js/build.js place): its ghost follows the pointer — the house
 *  alone for a building with no card — and a press builds it there; Escape or a right click lets it go. */
function Placing({ p }) {
  const [at, setAt] = useState(null);
  useEffect(() => {
    const key = (e) => { if (e.key === "Escape") { e.preventDefault(); placing.value = null; } };
    window.addEventListener("keydown", key);
    return () => window.removeEventListener("keydown", key);
  }, []);
  const spot = at && { x: at.x - 120, y: at.y - 30 };     // the ghost's middle under the pointer
  const put = (e) => {
    e.stopPropagation();
    const f = free(DEFAULT_SIZE);
    const x = e.offsetX - 120, y = e.offsetY - 30;
    const hut = [Math.min(Math.max((x - MARGIN) / f.w, 0), 1), Math.min(Math.max((y - MARGIN) / f.h, 0), 1)];
    const { type } = p;
    placing.value = null;
    command("town.build", { type, hut }).then((id) => raised(id, type), () => {});
  };
  return html`<div class="gui-town__placing" role="application" aria-label=${say(`Place ${p.title}: press where it should stand, Escape to cancel`)}
      onPointerMove=${(e) => setAt({ x: e.offsetX, y: e.offsetY })}
      onClick=${put} onContextMenu=${(e) => { e.preventDefault(); e.stopPropagation(); placing.value = null; }}>
    ${spot && html`<${Ghost} g=${{ id: "", type: p.type, title: p.title, state: "planned" }} spot=${spot} biome=${activeBiome()} bare=${p.bare} />`}
    <p class="gui-town__placing-hint ok-font-status">${say(`Place ${p.title}: press where it should stand · Esc cancels`)}</p>
  </div>`;
}

export function Town({ buildings, roads }) {
  const ref = useRef(null);
  const panelW = panelShown() && !opened.value.full ? panelWidth.value : 0;
  useLayoutEffect(() => {
    const el = ref.current;
    const measure = () => {
      const r = { w: Math.max(el.clientWidth, MIN_ROOM.w), h: Math.max(el.clientHeight, MIN_ROOM.h), strip: STRIP };
      if (r.w !== room.value.w || r.h !== room.value.h || r.strip !== room.value.strip) room.value = r;
    };
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  // A hut stands where its full height (every part shown) would put it; the huts under one with parts
  // hidden, or folded, are lifted by what it lost.
  // A grown card is placed by its natural size: growing never moves a neighbour.
  const placed = (b) => (grownLast.has(b.id) && natural[b.id]) || sizes.value[b.id]
    || (constructing.value[b.id] !== undefined ? RAISING_SIZE : { w: 240, h: 64 });
  const fullSize = (b) => {
    const size = placed(b);
    return { ...size, h: size.h + lost(b.id, size.h, !!b.folded && b.id !== CORNER) };
  };
  const full = {};
  buildings.forEach((b, i) => {
    const size = fullSize(b);
    full[b.id] = { ...place(b, i, size), w: size.w, h: size.h, lost: size.h - placed(b).h };
  });
  const up = lifts(full);
  const standing = Object.fromEntries(buildings.map((b) => {
    const size = placed(b);
    return [b.id, { x: full[b.id].x, y: full[b.id].y - up[b.id], w: size.w, h: size.h }];
  }));
  const held = new Set([CORNER, "\u0000portrait"]);
  const down = settle({ ...standing, "\u0000portrait": CORNER_ROOM }, held);
  for (const b of buildings) up[b.id] -= down[b.id];   // `moved` keeps the spot unpushed, as it keeps it unlifted
  const spots = {}, rects = {}, ports = {};
  buildings.forEach((b) => {
    const size = sizes.value[b.id] || (constructing.value[b.id] !== undefined ? RAISING_SIZE : { w: 240, h: 64 });
    spots[b.id] = { x: full[b.id].x, y: full[b.id].y - up[b.id] };
    rects[b.id] = { x: spots[b.id].x, y: spots[b.id].y, w: size.w, h: size.h };
    // A road meets the plinth the building stands on in Camp (js/hut.js measure), the card that holds the name in Office
    ports[b.id] = size.ch ? { x: rects[b.id].x + (size.px || 0), y: rects[b.id].y + (size.top || 0), w: size.pw || size.w, h: size.ch }
      : rects[b.id];
  });

  /** Where a hut dropped at (x, y) would stand: its spot kept as fractions, and its ghost at the place it takes. */
  function landing(b, x, y) {
    const size = fullSize(b);
    const f = free(size);
    const fx = Math.min(Math.max((x - MARGIN) / f.w, 0), 1), fy = Math.min(Math.max((y + (up[b.id] || 0) - MARGIN) / f.h, 0), 1);
    const at = { x: MARGIN + fx * f.w, y: MARGIN + fy * f.h - (up[b.id] || 0) };   // the spot kept is the one it stands at unlifted
    return { fx, fy, ghost: footprint(b.id, { ...at, w: rects[b.id].w, h: rects[b.id].h }, rects) };
  }

  /** The ghost of a card stretched to w × h: the hut keeps its spot; the card under its sprite grows. */
  function stretched(b, w, h) {
    const r = rects[b.id], top = (sizes.value[b.id] || {}).top || 0;
    return footprint(b.id, { x: r.x, y: r.y, w, h: top + h }, rects);
  }

  function sized(b, w, h) {
    if (stretched(b, w, h).hits.length) return;            // over another hut: it keeps its size
    command("hut.size", { id: b.id, w, h }).catch(() => {});
  }

  function moved(b, x, y) {
    const { fx, fy, ghost } = landing(b, x, y);
    if (ghost.hits.length) return;                         // over another hut: it stays where it stood
    const size = fullSize(b);
    const f = free(size);
    dropped.value = { ...dropped.value, [b.id]: { x: MARGIN + fx * f.w, y: MARGIN + fy * f.h } };
    const forget = () => {
      const { [b.id]: _, ...rest } = dropped.value;
      dropped.value = rest;
    };
    command("hut.move", { id: b.id, x: fx, y: fy }).then(() => setTimeout(forget, 300), forget);
  }

  // A click on the bare town lets the selected building go, as in the TUI.
  const bare = (e) => { if (!e.target.closest(".gui-hut, .gui-road, .gui-loose")) closeBuilding(); };
  const shown = new Set(buildings.map((b) => b.id));
  const here = roads.filter((r) => shown.has(r.from) && shown.has(r.to));
  const paths = plannedPaths(rects, here, ports);
  const snap = snapshot.value;
  // With a building selected, Office dims every hut that is neither it nor at the other end of one of its roads.
  const active = opened.value.active;
  const near = new Set(active ? here.flatMap((r) => (r.from === active ? [r.to] : r.to === active ? [r.from] : [])) : []);
  const dim = (id) => !!active && shown.has(active) && id !== active && !near.has(id);
  useCamera(ref.current, rects, here, panelW);
  numbered = buildings.map((b) => b.id);
  // Huts pushed under the fold make the room taller, so the town scrolls to them rather than hiding them under the foot.
  const tall = Math.max(room.value.h, ...Object.values(rects).map((r) => r.y + r.h + MARGIN + room.value.strip));
  const fresh = new Set([...risen(), ...built.value]);   // raised by the onboarding or by Build: each rises into place once
  const going = constructing.value;          // raised by Build and not standing yet: scaffolding where it will stand
  const drag = dragging.value, stretch = resizing.value;
  const still = new Set([drag && drag.id, stretch && stretch.id].filter(Boolean));
  const r20 = (v) => Math.round((v || 0) / 20);
  const shape = JSON.stringify([room.value, panelW, buildings.map((b) => [b.id, b.size, b.folded, b.hut])]);
  const auto = steady(() => grow(buildings, spots, rects, still),
    JSON.stringify([shape, [...still], buildings.map((b) => [r20(spots[b.id].x), r20(spots[b.id].y),
      natural[b.id] ? [r20(natural[b.id].w), r20(natural[b.id].h)] : 0])]), shape);
  for (const b of buildings) {
    const m = sizes.value[b.id];
    if (!m) continue;
    if (!auto[b.id] && !grownLast.has(b.id)) natural[b.id] = m;
    // only wider, it draws its own height: a card that grew before its card was drawn in full learns it here
    // (taller only: a height that may also shrink can swing the growth to and fro)
    else if (auto[b.id] && !auto[b.id][1] && grownLast.has(b.id) && natural[b.id] && m.h > natural[b.id].h) {
      natural[b.id] = { ...natural[b.id], h: m.h, top: m.top };
    }
  }
  grownLast = new Set(Object.keys(auto));
  const dragged = drag && buildings.find((b) => b.id === drag.id && rects[b.id]);
  const grown = stretch && buildings.find((b) => b.id === stretch.id && rects[b.id]);
  const ghost = dragged ? landing(dragged, spots[dragged.id].x + drag.dx, spots[dragged.id].y + drag.dy).ghost
    : grown ? stretched(grown, stretch.w, stretch.h) : null;
  return html`<main ref=${ref} class="ok-ground gui-town" onClick=${bare} onContextMenu=${(e) => bareMenu(e, buildings, here)}>
    <div class="gui-town__room" style=${`width:${room.value.w + panelW}px;height:${tall}px`}>
      <${Roads} roads=${here} rects=${rects} ports=${ports}
        tints=${Object.assign({}, ...buildings.map((b) => (b.card && b.card.tints) || {}))} />
      ${onboardingPlan().filter((g) => !shown.has(g.id)).map((g) => html`<${Ghost} key=${`plan-${g.id}`} g=${g}
          spot=${place({ id: g.id, hut: g.hut }, 0, DEFAULT_SIZE)} biome=${activeBiome()} />`)}
      ${buildings.map((b, i) => going[b.id] !== undefined ? html`<${Ghost} key=${`up-${b.id}`}
          g=${{ id: b.id, type: b.type, title: b.title, state: "raising" }} spot=${spots[b.id]} biome=${activeBiome()} bare=${bareOf(b)} />`
        : html`<${Hut} key=${b.id} b=${b} number=${i + 1} spot=${spots[b.id]} dim=${dim(b.id)} auto=${auto[b.id] || null}
          fresh=${fresh.has(b.id)} onMoved=${moved} onSized=${sized} />`)}
      ${ghost && html`<${Footprint} g=${ghost} />`}
      <${Signs} paths=${paths} roads=${here} />
      <${LooseEnds} buildings=${buildings} rects=${rects} />
      <${Carts} paths=${paths} carts=${(snap && snap.carts) || []} travel=${(snap && snap.travel) || 0} />
      ${placing.value && html`<${Placing} p=${placing.value} />`}
    </div>
    ${!buildings.length && html`<p class="gui-empty ok-font-body ok-tone-muted">${say("No buildings in this orkspace yet.")}</p>`}
  </main>`;
}
