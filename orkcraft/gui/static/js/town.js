// The town: every building of the orkspace as a hut card where the person put it, and the roads
// between them. Office draws huts as explorer cards and roads as 2px lines with dot gates
// (design-system/components.md: Hut, Road). Positions are the person's: dragging a hut saves its
// spot as fractions of the room (`hut` in the Town Scroll, the same the TUI reads).
import { signal } from "@preact/signals";
import { useLayoutEffect, useRef } from "preact/hooks";
import { html, cls } from "./html.js";
import { command, say } from "./link.js";
import { opened, closeBuilding } from "./windows.js";
import { plan } from "./roads.js";
import { pickedRoad } from "./build.js";
import { Hut, sizes, dragging, pulling } from "./hut.js";

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
  if (dropped.value[b.id]) return dropped.value[b.id];
  const [fx, fy] = b.hut || defaultSpot(i);
  const f = free(size);
  return { x: MARGIN + fx * f.w, y: MARGIN + fy * f.h };
}

// Planning every road is a few A* runs: keep the last plan while nothing it reads changed.
let planned = { key: "", paths: [] };

function plannedPaths(rects, roads) {
  const r = room.value;
  const key = JSON.stringify([rects, roads.map((x) => [x.id, x.from, x.to]), r.w, r.h]);
  if (key !== planned.key) planned = { key, paths: plan(rects, roads, r.w, r.h) };
  return planned.paths;
}

function Roads({ roads, rects }) {
  const r = room.value;
  const byId = Object.fromEntries(roads.map((x) => [x.id, x]));
  const active = opened.value.active;
  return html`<svg class="gui-roads" width=${r.w} height=${r.h} aria-hidden="true">
    ${plannedPaths(rects, roads).map((p) => {
      const road = byId[p.id];
      const sel = active === road.from || active === road.to;
      const mid = p.points[Math.floor(p.points.length / 2)];
      const pts = p.points.map((q) => q.join(",")).join(" ");
      return html`<g key=${p.id} class=${cls("gui-road", { "is-selected": sel || pickedRoad.value === p.id })}>
        <polyline points=${pts} />
        <polyline points=${pts} class="gui-road__hit" onClick=${() => { pickedRoad.value = p.id; }} />
        <circle cx=${p.exit[0]} cy=${p.exit[1]} r="3" /><circle cx=${p.entry[0]} cy=${p.entry[1]} r="4" class="gui-road__in" />
        ${sel && html`<text x=${mid[0] + 6} y=${mid[1] - 6} class="ok-font-status">${road.label}</text>`}
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

  const spots = {}, rects = {};
  buildings.forEach((b, i) => {
    const size = sizes.value[b.id] || { w: 240, h: 64 };
    spots[b.id] = place(b, i, size);
    const d = dragging.value && dragging.value.id === b.id ? dragging.value : { dx: 0, dy: 0 };
    rects[b.id] = { x: spots[b.id].x + d.dx, y: spots[b.id].y + d.dy, ...size };
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
  return html`<main ref=${ref} class="ok-ground gui-town" onClick=${bare}>
    <div class="gui-town__room" style=${`width:${room.value.w}px;height:${room.value.h}px`}>
      <${Roads} roads=${roads.filter((r) => shown.has(r.from) && shown.has(r.to))} rects=${rects} />
      ${buildings.map((b, i) => html`<${Hut} key=${b.id} b=${b} number=${i + 1} spot=${spots[b.id]} onMoved=${moved} />`)}
    </div>
    ${!buildings.length && html`<p class="gui-empty ok-font-body ok-tone-muted">${say("No buildings in this orkspace yet.")}</p>`}
  </main>`;
}
