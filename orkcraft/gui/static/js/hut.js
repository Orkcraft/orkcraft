// A building as it stands on the town (design-system/components.md: Hut): its card, its live lines,
// its question, and the mouse on it — a press opens it, a drag moves it, the + handle pulls a road
// out of it. One look's huts differ only in what this draws (Office: an explorer card; Camp: the
// card under its header sprite), never in how the town places them.
import { signal } from "@preact/signals";
import { useLayoutEffect, useRef } from "preact/hooks";
import { html, cls } from "./html.js";
import { opened, openBuilding } from "./windows.js";
import { laying } from "./build.js";
import { say } from "./link.js";

const DRAG_PX = 4;                         // a press that moves less is a click
export const sizes = signal({});           // building id → {w, h} of its card, as drawn
export const dragging = signal(null);      // {id, dx, dy}: the hut under the mouse, so its roads follow it
export const pulling = signal(null);       // {from, x, y}: a road being pulled out of a hut, to the pointer

/** A road pulled out of a hut's handle: where the pointer lets go over another hut, it goes there. */
function pull(e, b) {
  if (e.button !== 0) return;
  e.stopPropagation();
  e.preventDefault();
  const room = e.currentTarget.closest(".gui-town__room");
  const at = (ev) => {
    const r = room.getBoundingClientRect();
    return { x: ev.clientX - r.left, y: ev.clientY - r.top };
  };
  const move = (ev) => { pulling.value = { from: b.id, ...at(ev) }; };
  const up = (ev) => {
    window.removeEventListener("pointermove", move);
    window.removeEventListener("pointerup", up);
    pulling.value = null;
    const hut = document.elementFromPoint(ev.clientX, ev.clientY)?.closest(".gui-hut");
    const to = hut && hut.dataset.id;
    if (to && to !== b.id) laying.value = { from: b.id, to };
  };
  window.addEventListener("pointermove", move);
  window.addEventListener("pointerup", up);
  move(e);
}

export function Hut({ b, spot, number, onMoved }) {
  const ref = useRef(null);
  const drag = dragging.value && dragging.value.id === b.id ? dragging.value : null;
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
      if (b.pinned) return;                // a pinned hut keeps its place: a drag on it does nothing
      dragging.value = { id: b.id, dx, dy };
    };
    const up = (ev) => {
      ev.currentTarget.removeEventListener("pointermove", move);
      ev.currentTarget.removeEventListener("pointerup", up);
      dragging.value = null;
      if (moved) { if (!b.pinned) onMoved(b, spot.x + ev.clientX - start.x, spot.y + ev.clientY - start.y); }
      else openBuilding(b.id);
    };
    e.currentTarget.addEventListener("pointermove", move);
    e.currentTarget.addEventListener("pointerup", up);
  }

  const x = spot.x + (drag ? drag.dx : 0), y = spot.y + (drag ? drag.dy : 0);
  return html`<div ref=${ref} data-id=${b.id} style=${`left:${x}px;top:${y}px`}
      class=${cls("ok-hut m gui-hut", { "is-selected": opened.value.active === b.id, "is-busy": busy,
                                        "is-alert": !!b.alert, "is-hot": hot, "is-dragging": !!drag })}
      onPointerDown=${down}>
    <div class="ok-head"></div>
    <div class="ok-hut__card">
      <button class="gui-hut__road" title=${say("Pull a road to another building")} aria-label=${say("Pull a road")}
        onPointerDown=${(e) => pull(e, b)}>+</button>
      <span class="ok-hut__label"><span class="no">${number}</span>${say(b.title)}
        ${b.alert && html` <span class="ok-word">?</span>`}${b.pinned && html` <span class="ok-word ok-tone-muted">pinned</span>`}<span class="ok-hut__dot"></span></span>
      ${b.status_plain.length > 0 && html`<ul class="ok-hut__lines">
        ${b.status_plain.map((line, i) => html`<li key=${i}>${line}</li>`)}</ul>`}
    </div>
  </div>`;
}

