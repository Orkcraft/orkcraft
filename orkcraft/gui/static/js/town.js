// The town: every building of the orkspace as a hut card where the person put it, and the roads
// between them. Office draws huts as explorer cards and roads as a block diagram: 2px lines with an
// exit dot and an arrowhead, dashed when plain, moss green when a handler works on them, labelled,
// rounded at the bends and broken where another road crosses over (design-system/components.md: Hut,
// Road). Positions are the person's: dragging a hut saves its spot as fractions of the room (`hut`
// in the Town Scroll, the same the TUI reads).
import { signal } from "@preact/signals";
import { useEffect, useLayoutEffect, useRef } from "preact/hooks";
import { html, cls } from "./html.js";
import { command, say, town as snapshot } from "./link.js";
import { opened, closeBuilding, panelShown, panelWidth } from "./windows.js";
import { plan } from "./roads.js";
import { pickedRoad, building as buildOpen } from "./build.js";
import { openMenu } from "./menu.js";
import { settingsOpen } from "./settings.js";
import { Hut, sizes, dragging, pulling, CORNER } from "./hut.js";
import { lost } from "./parts.js";

const room = signal({ w: 1, h: 1, strip: 0 });
const dropped = signal({});                // building id → {x, y}: where a hut was dropped, till the town says so

// The room never gets smaller than four huts across and three down: a narrower town scrolls, so
// huts placed as fractions never pile up when a window opens beside it.
const MIN_ROOM = { w: 1080, h: 600 };
const COLS = 4, ROWS = 3;
const MARGIN = 24;                          // between the room's edge and the outermost huts
const STRIP = 64;                          // the town's foot (the orkspaces, the Warchief's line, layout.css .gui-foot): no hut under it
const DEFAULT_SIZE = { w: 240, h: 64 };     // a hut not drawn yet

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

/** Where a road's label goes: the middle of its longest straight run, above it or beside it. */
function labelSpot(points) {
  let best = 0, len = -1;
  for (let i = 1; i < points.length; i++) {
    const l = Math.abs(points[i][0] - points[i - 1][0]) + Math.abs(points[i][1] - points[i - 1][1]);
    if (l > len) { len = l; best = i; }
  }
  const [a, b] = [points[best - 1] || points[0], points[best] || points[0]];
  const x = (a[0] + b[0]) / 2, y = (a[1] + b[1]) / 2;
  return a[1] === b[1] ? { x, y: y - 6, anchor: "middle" } : { x: x + 6, y: y + 4, anchor: "start" };
}

// The arrowheads Office puts at a road's entry, one per colour a road can wear (layout.css picks one).
const HEADS = [["gui-road-head", "--road"], ["gui-road-head-live", "--road-live"], ["gui-road-head-selected", "--road-selected"]];

function Roads({ roads, rects, ports, tints = {} }) {
  const r = room.value;
  const byId = Object.fromEntries(roads.map((x) => [x.id, x]));
  const active = opened.value.active;
  return html`<svg class=${cls("gui-roads", { "has-focus": !!active && !!rects[active] })} width=${r.w} height=${r.h} aria-hidden="true">
    <defs>${HEADS.map(([id, token]) => html`<marker id=${id} viewBox="0 0 10 10" refX="10" refY="5" markerWidth="10"
      markerHeight="10" markerUnits="userSpaceOnUse" orient="auto"><path d="M 0 0 L 10 5 L 0 10 Z" style=${`fill: var(${token})`} /></marker>`)}</defs>
    ${plannedPaths(rects, roads, ports).map((p) => {
      const road = byId[p.id];
      const out = active === road.from, into = active === road.to;
      const d = pathOf(p.points, BEND_PX);
      const spot = labelSpot(p.points);
      return html`<g key=${p.id} class=${cls("gui-road", { "is-selected": out || into || pickedRoad.value === p.id,
                                                         "is-out": out, "is-in": into && !out, "is-live": !!road.handler,
                                                         "is-return": road.returns })}>
        <path d=${d} class="gui-road__halo" />
        <path d=${d} class="gui-road__line" />
        ${MARKS.has(tints[p.id]) && html`<polyline points=${start(p.points)} class="gui-road__tint" style=${`stroke: var(--mark-${tints[p.id]}); stroke-width: 4`} />`}
        <path d=${d} class="gui-road__hit" onClick=${() => { pickedRoad.value = p.id; }} />
        <circle cx=${p.exit[0]} cy=${p.exit[1]} r="3" class="gui-road__out" /><circle cx=${p.entry[0]} cy=${p.entry[1]} r="4" class="gui-road__in" />
        ${!road.sign && html`<text x=${spot.x} y=${spot.y} text-anchor=${spot.anchor} class="gui-road__label ok-font-status">${road.label}</text>`}
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

/** The right click on the bare town: Build here, the town's settings. */
function bareMenu(e) {
  if (e.target.closest(".gui-hut, .gui-road")) return;
  const r = e.currentTarget.querySelector(".gui-town__room").getBoundingClientRect();
  const hut = spotAt(e.clientX - r.left, e.clientY - r.top);
  openMenu(e, [
    { label: "Build here…", hint: "/build", run: () => { buildOpen.value = { hut }; } },
    { label: "Settings", run: () => { settingsOpen.value = true; } },
  ]);
}

/** The panel covers the town's right part: the room grows by as much, so the open building and the
 *  buildings its roads reach can be scrolled into the part left, and they are. */
function useCamera(el, rects, here, panelW) {
  const active = opened.value.active;
  useEffect(() => {
    if (!el || !active || !rects[active] || !panelW) return;
    const near = here.flatMap((r) => (r.from === active ? [r.to] : r.to === active ? [r.from] : [])).filter((id) => rects[id]);
    const boxes = [active, ...near].map((id) => rects[id]);
    const left = Math.min(...boxes.map((x) => x.x)), right = Math.max(...boxes.map((x) => x.x + x.w));
    const seen = el.clientWidth - panelW;
    const a = rects[active];
    // all of them when they fit, else the building itself, in the middle of the part left
    const [from, to] = right - left <= seen - 2 * MARGIN ? [left, right] : [a.x, a.x + a.w];
    if (from >= el.scrollLeft + MARGIN && to <= el.scrollLeft + seen - MARGIN) return;
    el.scrollTo({ left: Math.max((from + to) / 2 - seen / 2, 0), behavior: "smooth" });
  }, [active, panelW]);
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
  // hidden are lifted by what it lost.
  const fullSize = (b) => {
    const size = sizes.value[b.id] || { w: 240, h: 64 };
    return { ...size, h: size.h + lost(b.id, size.h) };
  };
  const full = {};
  buildings.forEach((b, i) => {
    const size = fullSize(b);
    full[b.id] = { ...place(b, i, size), w: size.w, h: size.h, lost: size.h - (sizes.value[b.id] || size).h };
  });
  const up = lifts(full);
  const spots = {}, rects = {}, ports = {};
  buildings.forEach((b) => {
    const size = sizes.value[b.id] || { w: 240, h: 64 };
    spots[b.id] = { x: full[b.id].x, y: full[b.id].y - up[b.id] };
    const d = dragging.value && dragging.value.id === b.id ? dragging.value : { dx: 0, dy: 0 };
    rects[b.id] = { x: spots[b.id].x + d.dx, y: spots[b.id].y + d.dy, w: size.w, h: size.h };
    // A road meets the card's frame: in Camp under the sprite, in Office the card that holds the name
    ports[b.id] = size.ch ? { x: rects[b.id].x, y: rects[b.id].y + (size.top || 0), w: size.w, h: size.ch } : rects[b.id];
  });

  function moved(b, x, y) {
    y += up[b.id] || 0;                     // the spot kept is the one it stands at unlifted
    const size = fullSize(b);
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
  const paths = plannedPaths(rects, here, ports);
  const snap = snapshot.value;
  // With a building selected, Office dims every hut that is neither it nor at the other end of one of its roads.
  const active = opened.value.active;
  const near = new Set(active ? here.flatMap((r) => (r.from === active ? [r.to] : r.to === active ? [r.from] : [])) : []);
  const dim = (id) => !!active && shown.has(active) && id !== active && !near.has(id);
  useCamera(ref.current, rects, here, panelW);
  return html`<main ref=${ref} class="ok-ground gui-town" onClick=${bare} onContextMenu=${bareMenu}>
    <div class="gui-town__room" style=${`width:${room.value.w + panelW}px;height:${room.value.h}px`}>
      <${Roads} roads=${here} rects=${rects} ports=${ports}
        tints=${Object.assign({}, ...buildings.map((b) => (b.card && b.card.tints) || {}))} />
      ${buildings.map((b, i) => html`<${Hut} key=${b.id} b=${b} number=${i + 1} spot=${spots[b.id]} dim=${dim(b.id)} onMoved=${moved} />`)}
      <${Signs} paths=${paths} roads=${here} />
      <${Carts} paths=${paths} carts=${(snap && snap.carts) || []} travel=${(snap && snap.travel) || 0} />
    </div>
    ${!buildings.length && html`<p class="gui-empty ok-font-body ok-tone-muted">${say("No buildings in this orkspace yet.")}</p>`}
  </main>`;
}
