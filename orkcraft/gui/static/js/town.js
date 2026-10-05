// The town: every building of the orkspace as a hut card where the person put it, and the roads
// between them. Office draws huts as explorer cards and roads as 2px lines with dot gates
// (design-system/components.md: Hut, Road). Positions are the person's: dragging a hut saves its
// spot as fractions of the room (`hut` in the Town Scroll, the same the TUI reads).
import { signal } from "@preact/signals";
import { useLayoutEffect, useRef, useState } from "preact/hooks";
import { html, cls } from "./html.js";
import { command } from "./link.js";
import { opened, openBuilding } from "./windows.js";

const DRAG_PX = 4;                         // a press that moves less is a click
const sizes = signal({});                  // building id → {w, h} of its card, as drawn
const room = signal({ w: 1, h: 1 });
const dropped = signal({});                // building id → {x, y}: where a hut was dropped, till the town says so

// The room never gets smaller than four huts across and three down: a narrower town scrolls, so
// huts placed as fractions never pile up when a window opens beside it.
const MIN_ROOM = { w: 1080, h: 600 };
const COLS = 4, ROWS = 3;
const MARGIN = 24;                          // between the room's edge and the outermost huts

/** The room a hut's spot is a fraction of: the canvas less the hut and the margins. */
function free(size) {
  return { w: Math.max(room.value.w - size.w - 2 * MARGIN, 1), h: Math.max(room.value.h - size.h - 2 * MARGIN, 1) };
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

/** Where the segment from a's centre to b's centre leaves rectangle a. */
function edge(a, b) {
  const cx = a.x + a.w / 2, cy = a.y + a.h / 2;
  const dx = b.x + b.w / 2 - cx, dy = b.y + b.h / 2 - cy;
  if (!dx && !dy) return { x: cx, y: cy };
  const s = 1 / Math.max(Math.abs(dx) / (a.w / 2 || 1), Math.abs(dy) / (a.h / 2 || 1));
  return { x: cx + dx * s, y: cy + dy * s };
}

function Roads({ roads, rects }) {
  const r = room.value;
  return html`<svg class="gui-roads" width=${r.w} height=${r.h} aria-hidden="true">
    ${roads.map((road) => {
      const a = rects[road.from], b = rects[road.to];
      if (!a || !b) return null;
      const p = edge(a, b), q = edge(b, a);
      const sel = opened.value.active === road.from || opened.value.active === road.to;
      return html`<g key=${road.id} class=${cls("gui-road", { "is-selected": sel })}>
        <line x1=${p.x} y1=${p.y} x2=${q.x} y2=${q.y} />
        <circle cx=${p.x} cy=${p.y} r="3" /><circle cx=${q.x} cy=${q.y} r="4" class="gui-road__in" />
        ${sel && html`<text x=${(p.x + q.x) / 2} y=${(p.y + q.y) / 2 - 6} class="ok-font-status">${road.label}</text>`}
      </g>`;
    })}
  </svg>`;
}

function Hut({ b, spot, number, onMoved }) {
  const ref = useRef(null);
  const [drag, setDrag] = useState(null);   // {dx, dy} while dragging
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    const w = el.offsetWidth, h = el.offsetHeight;
    const old = sizes.value[b.id];
    if (!old || old.w !== w || old.h !== h) sizes.value = { ...sizes.value, [b.id]: { w, h } };
  });
  const busy = b.garrison.some((o) => o.status === "busy") || b.state === "WORKING";
  const hot = b.alert && b.alert.waited >= 30;

  function down(e) {
    if (e.button !== 0) return;
    const start = { x: e.clientX, y: e.clientY };
    let moved = false;
    e.currentTarget.setPointerCapture(e.pointerId);
    const move = (ev) => {
      const dx = ev.clientX - start.x, dy = ev.clientY - start.y;
      if (!moved && Math.hypot(dx, dy) < DRAG_PX) return;
      moved = true;
      setDrag({ dx, dy });
    };
    const up = (ev) => {
      ev.currentTarget.removeEventListener("pointermove", move);
      ev.currentTarget.removeEventListener("pointerup", up);
      setDrag(null);
      if (moved) onMoved(b, spot.x + ev.clientX - start.x, spot.y + ev.clientY - start.y);
      else openBuilding(b.id);
    };
    e.currentTarget.addEventListener("pointermove", move);
    e.currentTarget.addEventListener("pointerup", up);
  }

  const x = spot.x + (drag ? drag.dx : 0), y = spot.y + (drag ? drag.dy : 0);
  return html`<div ref=${ref} style=${`left:${x}px;top:${y}px`}
      class=${cls("ok-hut m gui-hut", { "is-selected": opened.value.active === b.id, "is-busy": busy,
                                        "is-alert": !!b.alert, "is-hot": hot, "is-dragging": !!drag })}
      onPointerDown=${down}>
    <div class="ok-head"></div>
    <div class="ok-hut__card">
      <span class="ok-hut__label"><span class="no">${number}</span>${b.title}
        ${b.alert && html` <span class="ok-word">?</span>`}<span class="ok-hut__dot"></span></span>
      ${b.status_plain.length > 0 && html`<ul class="ok-hut__lines">
        ${b.status_plain.map((line, i) => html`<li key=${i}>${line}</li>`)}</ul>`}
    </div>
  </div>`;
}

export function Town({ buildings, roads }) {
  const ref = useRef(null);
  useLayoutEffect(() => {
    const el = ref.current;
    const measure = () => {
      const r = { w: Math.max(el.clientWidth, MIN_ROOM.w), h: Math.max(el.clientHeight, MIN_ROOM.h) };
      if (r.w !== room.value.w || r.h !== room.value.h) room.value = r;
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
    rects[b.id] = { ...spots[b.id], ...size };
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

  const shown = new Set(buildings.map((b) => b.id));
  return html`<main ref=${ref} class="ok-ground gui-town">
    <div class="gui-town__room" style=${`width:${room.value.w}px;height:${room.value.h}px`}>
      <${Roads} roads=${roads.filter((r) => shown.has(r.from) && shown.has(r.to))} rects=${rects} />
      ${buildings.map((b, i) => html`<${Hut} key=${b.id} b=${b} number=${i + 1} spot=${spots[b.id]} onMoved=${moved} />`)}
    </div>
    ${!buildings.length && html`<p class="gui-empty ok-font-body ok-tone-muted">No buildings in this orkspace yet.</p>`}
  </main>`;
}
