// The town: every building of the orkspace as a hut card where the person put it, and the roads
// between them. Office draws huts as explorer cards and roads as 2px lines with dot gates
// (design-system/components.md: Hut, Road). Positions are the person's: dragging a hut saves its
// spot as fractions of the room (`hut` in the Town Scroll, the same the TUI reads).
import { signal } from "@preact/signals";
import { useLayoutEffect, useRef } from "preact/hooks";
import { html, cls } from "./html.js";
import { command, say, town as snapshot } from "./link.js";
import { opened, closeBuilding } from "./windows.js";
import { plan } from "./roads.js";
import { pickedRoad } from "./build.js";
import { Hut, sizes, dragging, pulling, CORNER } from "./hut.js";
import { RoadTiles } from "./roadtiles.js";

const room = signal({ w: 1, h: 1, strip: 0 });
const dropped = signal({});                // building id → {x, y}: where a hut was dropped, till the town says so

// The room never gets smaller than four huts across and three down: a narrower town scrolls, so
// huts placed as fractions never pile up when a window opens beside it.
const MIN_ROOM = { w: 1080, h: 600 };
const COLS = 4, ROWS = 3;
const MARGIN = 24;                          // between the room's edge and the outermost huts
const STRIP = 0.21, STRIP_MIN = 126;         // the War Map's share of the window (layout.css .gui-strip): no hut under it

/** The room a hut's spot is a fraction of: the canvas less the hut, the margins and the strip. */
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
  if (b.id === CORNER) {                       // the Hall: the bottom-right corner, where Office's advisor stands —
    const r = room.value;                       // under the strip, which covers it while a building is selected
    return { x: Math.max(r.w - size.w - MARGIN, 0), y: Math.max(r.h - size.h - MARGIN, 0) };
  }
  if (dropped.value[b.id]) return dropped.value[b.id];
  const [fx, fy] = b.hut || defaultSpot(i);
  return { x: MARGIN + fx * f.w, y: MARGIN + fy * f.h };
}

// Planning every road is a few A* runs: keep the last plan while nothing it reads changed.
let planned = { key: "", paths: [] };

function plannedPaths(rects, roads, ports = rects) {
  const r = room.value;
  const key = JSON.stringify([rects, ports, roads.map((x) => [x.id, x.from, x.to]), r.w, r.h]);
  if (key !== planned.key) planned = { key, paths: plan(rects, roads, r.w, r.h, ports) };
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

function Carts({ paths, carts, travel, camp }) {
  const byRoad = Object.fromEntries(paths.map((p) => [p.id, p]));
  const trip = travel > 0 ? travel : SHORT_TRIP_S;
  return html`<div class="gui-carts" aria-hidden="true">
    ${carts.filter((c) => byRoad[c.road] && c.age < trip + 1).map((c) => {
      const p = byRoad[c.road];
      const d = "M" + p.points.map((q) => q.join(" ")).join(" L");
      const back = c.status === "filtered";
      return html`<div key=${c.id} class=${cls("gui-cart", { "is-back": back, "is-held": c.status === "held" || c.status === "error" })}
          style=${`offset-path: path("${d}"); animation-duration: ${back ? SHORT_TRIP_S : trip}s; animation-delay: ${delayOf(c)}`}>
        ${camp ? html`<img class="gui-cart__sprite" src="/ds/sprites/carts/minecart@2x.png" width="20" height="18" alt="" />`
               : html`<i class="gui-cart__dot"></i>`}
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

function Roads({ roads, rects, ports, tints = {} }) {
  const r = room.value;
  const byId = Object.fromEntries(roads.map((x) => [x.id, x]));
  const active = opened.value.active;
  return html`<svg class="gui-roads" width=${r.w} height=${r.h} aria-hidden="true">
    ${plannedPaths(rects, roads, ports).map((p) => {
      const road = byId[p.id];
      const sel = active === road.from || active === road.to;
      const mid = along(p.points, 0.5);
      const pts = p.points.map((q) => q.join(",")).join(" ");
      return html`<g key=${p.id} class=${cls("gui-road", { "is-selected": sel || pickedRoad.value === p.id, "is-return": road.returns })}>
        <polyline points=${pts} />
        ${MARKS.has(tints[p.id]) && html`<polyline points=${start(p.points)} style=${`stroke: var(--mark-${tints[p.id]}); stroke-width: 4`} />`}
        <polyline points=${pts} class="gui-road__hit" onClick=${() => { pickedRoad.value = p.id; }} />
        <circle cx=${p.exit[0]} cy=${p.exit[1]} r="3" /><circle cx=${p.entry[0]} cy=${p.entry[1]} r="4" class="gui-road__in" />
        ${sel && !road.sign && html`<text x=${mid[0] + 6} y=${mid[1] - 6} class="ok-font-status">${road.label}</text>`}
      </g>`;
    })}
    ${pulling.value && rects[pulling.value.from] && html`<line class="gui-road__pull"
      x1=${rects[pulling.value.from].x + rects[pulling.value.from].w} y1=${rects[pulling.value.from].y + rects[pulling.value.from].h / 2}
      x2=${pulling.value.x} y2=${pulling.value.y} />`}
  </svg>`;
}

export function Town({ buildings, roads }) {
  const ref = useRef(null);
  useLayoutEffect(() => {
    const el = ref.current;
    const measure = () => {
      const r = { w: Math.max(el.clientWidth, MIN_ROOM.w), h: Math.max(el.clientHeight, MIN_ROOM.h),
                  strip: Math.max(Math.round(window.innerHeight * STRIP), STRIP_MIN) };
      if (r.w !== room.value.w || r.h !== room.value.h || r.strip !== room.value.strip) room.value = r;
    };
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const spots = {}, rects = {}, ports = {};
  const camp = !!snapshot.value && snapshot.value.look === "camp";
  buildings.forEach((b, i) => {
    const size = sizes.value[b.id] || { w: 240, h: 64 };
    spots[b.id] = place(b, i, size);
    const d = dragging.value && dragging.value.id === b.id ? dragging.value : { dx: 0, dy: 0 };
    rects[b.id] = { x: spots[b.id].x + d.dx, y: spots[b.id].y + d.dy, w: size.w, h: size.h };
    // Camp: a road meets the card's frame under the sprite, not the sprite (Office's hut is its card)
    ports[b.id] = camp && size.ch ? { x: rects[b.id].x, y: rects[b.id].y + (size.top || 0), w: size.w, h: size.ch }
                                  : rects[b.id];
  });

  function moved(b, x, y) {
    const size = sizes.value[b.id] || { w: 240, h: 64 };
    const f = free(size);
    const fx = Math.min(Math.max((x - MARGIN) / f.w, 0), 1), fy = Math.min(Math.max((y - MARGIN) / f.h, 0), 1);
    dropped.value = { ...dropped.value, [b.id]: { x: MARGIN + fx * f.w, y: MARGIN + fy * f.h } };
    const forget = () => {
      const { [b.id]: _, ...rest } = dropped.value;
      dropped.value = rest;
    };
    command("hut.move", { id: b.id, x: fx, y: fy }).then(() => setTimeout(forget, 300), forget);
  }

  // A click on the bare town lets the selected building go, as in the TUI.
  const bare = (e) => { if (!e.target.closest(".gui-hut, .gui-road")) closeBuilding(); };
  const shown = new Set(buildings.map((b) => b.id));
  const here = roads.filter((r) => shown.has(r.from) && shown.has(r.to));
  const gatesOn = camp ? ports : rects;               // Office: the hut is its card
  const paths = plannedPaths(rects, here, gatesOn);
  const snap = snapshot.value;
  return html`<main ref=${ref} class="ok-ground gui-town" onClick=${bare}>
    <div class="gui-town__room" style=${`width:${room.value.w}px;height:${room.value.h}px`}>
      ${camp && html`<${RoadTiles} paths=${paths} roads=${here} />`}
      <${Roads} roads=${here} rects=${rects} ports=${gatesOn}
        tints=${Object.assign({}, ...buildings.map((b) => (b.card && b.card.tints) || {}))} />
      ${buildings.map((b, i) => html`<${Hut} key=${b.id} b=${b} number=${i + 1} spot=${spots[b.id]} onMoved=${moved} />`)}
      <${Signs} paths=${paths} roads=${here} />
      <${Carts} paths=${paths} carts=${(snap && snap.carts) || []} travel=${(snap && snap.travel) || 0}
        camp=${!!snap && snap.look === "camp"} />
    </div>
    ${!buildings.length && html`<p class="gui-empty ok-font-body ok-tone-muted">${say("No buildings in this orkspace yet.")}</p>`}
  </main>`;
}
