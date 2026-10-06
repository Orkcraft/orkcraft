// A building as it stands on the town, closed (design-system/components.md: Hut;
// docs/design/building-views.md): its name above the card, inside only its type's live status (the
// type's `card(b)`, else its status lines), and the mouse on it — a press opens it, a drag moves
// it, the + handle pulls a road out of it. Every hut stands pinned: the pin at the right of its name
// unpins it, so a drag moves it, and five seconds without a move pin it again. Before the name a
// spinner while it works and, in Office, its type's icon; in Camp its type's header sprite stands
// between the name and the card. One look's huts differ only in what this draws (Office: an explorer card; Camp: the
// card under its header sprite), never in how the town places them.
import { signal } from "@preact/signals";
import { useLayoutEffect, useRef } from "preact/hooks";
import { html, cls } from "./html.js";
import { opened, openBuilding, Badge } from "./windows.js";
import { laying, demolishing } from "./build.js";
import { openMenu } from "./menu.js";
import { mention } from "./warchief.js";
import { typeModule } from "./types.js";
import { town, say } from "./link.js";
import { TypeIcon, headerSprite } from "./icons.js";

const DRAG_PX = 4;                         // a press that moves less is a click
export const CORNER = "town_hall";          // stands in the town's bottom-right corner, as in the TUI: never moved
const IDLE_MS = 5000;                      // an unpinned hut left alone this long is pinned again
export const sizes = signal({});           // building id → {w, h} of its card, as drawn
export const dragging = signal(null);      // {id, dx, dy}: the hut under the mouse, so its roads follow it
export const pulling = signal(null);       // {from, x, y}: a road being pulled out of a hut, to the pointer
export const unpinned = signal({});        // building id → true while a drag may move it
const idle = new Map();                    // building id → the timer that pins it again
const WARN_MS = 2000;                      // a drag on a pinned hut turns its pin red this long
const warned = signal({});                 // building id → true while its pin says it holds the hut
const warnings = new Map();                // building id → the timer that lets the pin go back

/** A drag on a pinned hut: its pin turns red for WARN_MS, so the person sees why it does not move. */
function warnPinned(id) {
  clearTimeout(warnings.get(id));
  warned.value = { ...warned.value, [id]: true };
  warnings.set(id, setTimeout(() => {
    warnings.delete(id);
    const { [id]: _, ...rest } = warned.value;
    warned.value = rest;
  }, WARN_MS));
}

function pinAgain(id) {
  clearTimeout(idle.get(id));
  idle.delete(id);
  const { [id]: _, ...rest } = unpinned.value;
  unpinned.value = rest;
}

/** Keeps a hut unpinned for another IDLE_MS. */
function stir(id) {
  clearTimeout(idle.get(id));
  idle.set(id, setTimeout(() => pinAgain(id), IDLE_MS));
}

function togglePin(e, id) {
  e.stopPropagation();
  if (unpinned.value[id]) { pinAgain(id); return; }
  unpinned.value = { ...unpinned.value, [id]: true };
  stir(id);
}

/** The pin by a hut's name: on, the hut keeps its place; off, a drag moves it. */
function PinButton({ b }) {
  const off = !!unpinned.value[b.id];
  const label = off ? say("Pin it in place") : say("Unpin to move it");
  return html`<button class=${cls("gui-hut__pin", { "is-off": off, "is-warn": !!warned.value[b.id] })} title=${label} aria-label=${label} aria-pressed=${off}
      onPointerDown=${(e) => e.stopPropagation()} onClick=${(e) => togglePin(e, b.id)}>
    <svg viewBox="0 0 16 16" width="12" height="12" aria-hidden="true">
      <path d="M6 1.5h4M7 1.5v4.5L4.5 9h7L9 6V1.5M8 9v5.5" />
      ${off && html`<path d="M2.5 2.5l11 11" />`}
    </svg></button>`;
}

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

/** The right click on a hut: its building's menu (docs/design/calm-town.md §3). */
function hutMenu(e, b) {
  const t = town.value;
  const space = t.orkspaces.find((o) => o.id === t.active_orkspace);
  const here = new Set(space ? space.buildings : t.buildings.map((x) => x.id));
  here.add(CORNER);
  const among = t.buildings.filter((x) => x.id !== b.id && here.has(x.id)).map((x) => x.id);
  const name = say(b.title);
  openMenu(e, [
    { label: "Open", hint: "click", run: () => openBuilding(b.id, "work") },
    { label: "Info", run: () => openBuilding(b.id, "info") },
    "-",
    { label: "Listen to…", hint: `/road @${name}`, run: () => { laying.value = { from: null, to: b.id, among }; } },
    { label: "Ask the Warchief about it", hint: `@${name}`, run: () => mention(b) },
    b.id !== CORNER && !b.pinned && { label: unpinned.value[b.id] ? "Pin it in place" : "Unpin to move it",
      run: () => togglePin({ stopPropagation() {} }, b.id) },
    b.id !== CORNER && "-",
    b.id !== CORNER && { label: "Demolish…", hint: `/demolish @${name}`, danger: true, run: () => { demolishing.value = b.id; } },
  ]);
}

/** The inside of the card (closed): the type's own `card(b)` (js/types.js), else its status lines. */
function Card({ b }) {
  const mod = b.page ? typeModule(b.type) : null;
  if (mod && mod.card) return html`<div class="gui-hut__body ok-font-status">${mod.card(b)}</div>`;
  return b.status_plain.length > 0 ? html`<ul class="ok-hut__lines">
    ${b.status_plain.map((line, i) => html`<li key=${i}>${line}</li>`)}</ul>` : null;
}

export function Hut({ b, spot, number, dim = false, onMoved }) {
  const ref = useRef(null);
  const drag = dragging.value && dragging.value.id === b.id ? dragging.value : null;
  // Its size as drawn, on every draw and whenever it changes between them (a type's stylesheet coming
  // late, a part of its card hidden): the town places the huts and the roads by it.
  const measure = () => {
    const el = ref.current;
    if (!el) return;
    const w = el.offsetWidth, h = el.offsetHeight;
    const card = el.querySelector(".ok-hut__card");          // where roads meet the hut in Camp: its card's frame
    const top = card ? card.offsetTop : 0, ch = card ? card.offsetHeight : h;
    const old = sizes.value[b.id];
    if (!old || old.w !== w || old.h !== h || old.top !== top || old.ch !== ch) {
      sizes.value = { ...sizes.value, [b.id]: { w, h, top, ch } };
    }
  };
  useLayoutEffect(measure);
  useLayoutEffect(() => {
    if (!ref.current || typeof ResizeObserver === "undefined") return undefined;
    const ro = new ResizeObserver(measure);
    ro.observe(ref.current);
    return () => ro.disconnect();
  }, [b.id]);
  const free = !!unpinned.value[b.id] && !b.pinned && b.id !== CORNER;   // pinned in the scroll, or the Hall: never moves
  const office = town.value.look === "office";
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
      if (!moved && !free) warnPinned(b.id);
      moved = true;
      if (!free) return;                   // a pinned hut keeps its place: a drag on it does nothing
      stir(b.id);
      dragging.value = { id: b.id, dx, dy };
    };
    const up = (ev) => {
      ev.currentTarget.removeEventListener("pointermove", move);
      ev.currentTarget.removeEventListener("pointerup", up);
      dragging.value = null;
      if (moved) { if (free) { stir(b.id); onMoved(b, spot.x + ev.clientX - start.x, spot.y + ev.clientY - start.y); } }
      else openBuilding(b.id);
    };
    e.currentTarget.addEventListener("pointermove", move);
    e.currentTarget.addEventListener("pointerup", up);
  }

  const x = spot.x + (drag ? drag.dx : 0), y = spot.y + (drag ? drag.dy : 0);
  // The name heads the card: in Camp a bevelled title bar with the garrison's badge under the header
  // sprite, as on a window; in Office a plain line, so a block on the map is one box and its roads
  // meet that box.
  const title = html`<span class="ok-hut__label gui-hut__title"><span class="no">${number}</span>
      ${busy && html`<span class="gui-hut__spin" role="img" title=${say("Working")} aria-label=${say("Working")}></span>`}
      ${office && html`<${TypeIcon} type=${b.type} />`}
      <span class="gui-hut__name">${say(b.title)}</span>
      ${!office && html`<${Badge} garrison=${b.garrison} alert=${b.alert} />`}
      ${b.alert && html`<span class="ok-word">?</span>`}${b.pinned && html`<span class=${cls("ok-word ok-tone-muted gui-hut__pinned", { "is-warn": !!warned.value[b.id] })}>pinned</span>`}
      ${!b.pinned && b.id !== CORNER && html`<${PinButton} b=${b} />`}</span>`;
  return html`<div ref=${ref} data-id=${b.id} style=${`left:${x}px;top:${y}px`}
      class=${cls("ok-hut m gui-hut", { "is-selected": opened.value.active === b.id, "is-busy": busy,
                                        "is-alert": !!b.alert, "is-hot": hot, "is-dragging": !!drag, "is-dim": dim,
                                        "is-free": free })}
      onPointerDown=${down} onContextMenu=${(e) => hutMenu(e, b)}>
    ${!office && html`<div class="ok-head"><img class="ok-sprite gui-hut__sprite" src=${headerSprite(b.type)} alt=""
      draggable="false" onError=${(e) => { e.currentTarget.hidden = true; }} /></div>`}
    <div class="ok-hut__card">
      ${title}
      <button class="gui-hut__road" title=${say("Pull a road to another building")} aria-label=${say("Pull a road")}
        onPointerDown=${(e) => pull(e, b)}>+</button>
      <span class="ok-hut__dot gui-hut__dot"></span>
      <${Card} b=${b} />
    </div>
  </div>`;
}

