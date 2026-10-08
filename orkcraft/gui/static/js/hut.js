// A building as it stands on the town, closed (design-system/components.md: Hut;
// docs/design/building-views.md): its name above the card, inside only its type's live status (the
// type's `card(b)`, else its status lines), and the mouse on it — a press opens it, a drag moves
// it, the + handle pulls a road out of it. A hut moves freely until the person pins it: the pin at the
// right of its name pins it in place (in the Town Scroll, as from its Info) and unpins it. Before the name a
// spinner while it works and its type's icon; its type's header sprite stands over the card's left
// (office.css: two thirds of the sprite's size), and the garrison's lead is its ork's head alone.
// A hut may fold to its title bar (docs/design/folded-cards.md): a mark says what the card would have said
// first, and the card peeks out over the huts under it while it wants the person or a drag is held over it.
// A drag or a stretch by an edge or corner never moves the hut at once: a ghost outline follows the mouse, red
// where it would stand on another hut, and the hut goes there on the drop only if it is free (js/town.js
// Footprint). A card stretched larger shows more (docs/design/building-views.md §1a): its size is kept in the
// Town Scroll (`hut.size`).
import { signal } from "@preact/signals";
import { useLayoutEffect, useRef, useState } from "preact/hooks";
import { html, cls } from "./html.js";
import { opened, openBuilding } from "./windows.js";
import { laying, demolishing } from "./build.js";
import { reasons, busy as busyOf, fold } from "./fold.js";
import { openMenu } from "./menu.js";
import { mention } from "./warchief.js";
import { typeModule, runQuick } from "./types.js";
import { town, say, command } from "./link.js";
import { Outside } from "./visit.js";
import { TypeIcon, HutSprite, OrkHead, Scheme, activeBiome } from "./icons.js";

const DRAG_PX = 4;                         // a press that moves less is a click
export const CORNER = "town_hall";          // stands in the town's bottom-right corner, as in the TUI: never moved
export const sizes = signal({});           // building id → {w, h} of its card, as drawn
export const dragging = signal(null);      // {id, dx, dy}: the hut being dragged; its ghost stands this far from it
export const resizing = signal(null);      // {id, w, h}: the card being stretched; its ghost has this size
export const HUT_MIN = { w: 240, h: 60 }, HUT_MAX = { w: 960, h: 900 };   // as the host keeps them (gui/host.py)
// A yard is stretched in whole pickets in Camp (docs/design/yards.md §3b′): one bottom picket and its gap across,
// one side picket and its gap down, so no picket is cut at a corner. Office draws no fence: no step.
export const YARD_STEP = { w: 21, h: 27 };
const stepOf = (b) => (b.yard && document.documentElement.dataset.look !== "office" ? YARD_STEP : null);
const snap = (v, by) => (by ? Math.max(by, Math.round(v / by) * by) : v);

/** How much a card shows by its size (docs/design/building-views.md §1a): `s` as it comes, `m` stretched, `l` big. */
export function levelOf(b) {
  const [w, h] = (b && b.size) || [0, 0];
  return w >= 520 && h >= 400 ? "l" : w >= 360 && h >= 240 ? "m" : "s";
}
export const pulling = signal(null);       // {from, x, y, over}: a road being pulled out of a hut, to the pointer; `over` the hut under it
const WARN_MS = 2000;                      // a drag on a pinned hut turns its pin red this long
const warned = signal({});                 // building id → true while its pin says it holds the hut
const putAway = signal({});                // building id → the peek reasons the person put away (▸ on a peek)
const dragOver = signal(null);             // the folded hut a drag is held over: it peeks
// Caught first, let go after the drop reached the card, so the peek holds till the Pit took what fell on it.
for (const end of ["drop", "dragend"]) window.addEventListener(end, () => setTimeout(() => { dragOver.value = null; }), true);
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

function togglePin(e, id) {
  e.stopPropagation();
  command("building.pin", { id });
}

/** The pin by a hut's name: on, the hut keeps its place; off, a drag moves it. */
function PinButton({ b }) {
  const on = !!b.pinned;
  const label = on ? say("Unpin to move it") : say("Pin it in place");
  return html`<button class=${cls("gui-hut__pin", { "is-on": on, "is-warn": !!warned.value[b.id] })} title=${label} aria-label=${label} aria-pressed=${on}
      onPointerDown=${(e) => e.stopPropagation()} onClick=${(e) => togglePin(e, b.id)}>
    <svg viewBox="0 0 16 16" width="12" height="12" aria-hidden="true">
      <path d="M6 1.5h4M7 1.5v4.5L4.5 9h7L9 6V1.5M8 9v5.5" />
    </svg></button>`;
}

const peekReasons = (b) => { const away = putAway.value[b.id] || []; return reasons(b).filter((r) => !away.includes(r)); };

/** ▾ folds an open card, ▸ unfolds a folded one; on a peek ▸ puts it away while the same reasons stand. A
 *  chevron in a 24px box, so it is found and hit in either look. */
function FoldButton({ b, peek }) {
  const label = !b.folded ? say("Fold the card") : peek ? say("Put it away") : say("Unfold the card");
  const press = (e) => {
    e.stopPropagation();
    if (peek) putAway.value = { ...putAway.value, [b.id]: reasons(b) };
    else fold(b);
  };
  return html`<button class=${cls("gui-hut__fold", { "is-on": !!b.folded })} title=${label} aria-label=${label} aria-expanded=${!b.folded || peek}
      onPointerDown=${(e) => e.stopPropagation()} onClick=${press}>
    <svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true"><path d=${b.folded ? "M6 3.5 10.5 8 6 12.5" : "M3.5 6 8 10.5 12.5 6"} /></svg>
  </button>`;
}

/** A folded hut's mark: what its card would have said first — an error, a pause, else its type's own `mark(b)`. */
export function Mark({ b }) {
  const mod = b.page ? typeModule(b.type) : null;
  const own = mod && mod.mark ? mod.mark(b) : null;
  const m = b.state === "ERROR" ? { text: "error", tone: "error" } : b.paused ? { text: "paused", tone: "wait" } : own;
  return m && m.text ? html`<span class=${cls("gui-hut__mark", m.tone && `ok-tone-${m.tone}`)}>${say(String(m.text))}</span>` : null;
}

/** A road pulled out of a hut's handle: where the pointer lets go over another hut, it goes there. */
function pull(e, b) {
  pullRoad(e, b.id);
}

/** A road pulled out of building `from` (its handle, or a stub of a way out with no road: `event`, as
 *  `signpost.routed#urgent`). Let go over another hut: a stub's road is laid at once on its event (docs/design/
 *  review-board.md §2.1); any other asks what it carries. */
export function pullRoad(e, from, event = "") {
  const b = { id: from };
  if (e.button !== 0) return;
  e.stopPropagation();
  e.preventDefault();
  const room = e.currentTarget.closest(".gui-town__room");
  const at = (ev) => {
    const r = room.getBoundingClientRect();
    return { x: ev.clientX - r.left, y: ev.clientY - r.top };
  };
  const under = (ev) => {
    const to = document.elementFromPoint(ev.clientX, ev.clientY)?.closest(".gui-hut")?.dataset.id;
    return to && to !== b.id ? to : null;
  };
  const move = (ev) => { pulling.value = { from: b.id, ...at(ev), over: under(ev) }; };
  const up = (ev) => {
    window.removeEventListener("pointermove", move);
    window.removeEventListener("pointerup", up);
    pulling.value = null;
    const to = under(ev);
    if (to && event) command("roads.lay", { from: b.id, to, event, handler: null })
      .catch(() => { laying.value = { from: b.id, to }; });
    else if (to) laying.value = { from: b.id, to };
  };
  window.addEventListener("pointermove", move);
  window.addEventListener("pointerup", up);
  move(e);
}

/** The right click on a hut, or ⋯ in its panel's bar: its building's menu (docs/design/calm-town.md §3).
 *  Demolish lives here only, rare and confirmed, never a button in view. */
export function buildingMenu(e, b) {
  const t = town.value;
  const space = t.orkspaces.find((o) => o.id === t.active_orkspace);
  const here = new Set(space ? space.buildings : t.buildings.map((x) => x.id));
  here.add(CORNER);
  const among = t.buildings.filter((x) => x.id !== b.id && here.has(x.id)).map((x) => x.id);
  const name = say(b.title);
  const mod = b.page ? typeModule(b.type) : null;
  const own = mod && mod.infoActs ? mod.infoActs(b) : [];        // what only its type offers (Import calendar)
  openMenu(e, [
    { label: "Open", hint: "click", run: () => openBuilding(b.id, "work") },
    { label: "Info", run: () => openBuilding(b.id, "info") },
    ...own.map((a) => ({ label: a.label, run: a.run })),
    "-",
    { label: "Listen to…", hint: `/road @${name}`, run: () => { laying.value = { from: null, to: b.id, among }; } },
    { label: "Ask the Warchief about it", hint: `@${name}`, run: () => mention(b) },
    b.id !== CORNER && { label: b.pinned ? "Unpin to move it" : "Pin it in place",
      run: () => togglePin({ stopPropagation() {} }, b.id) },
    b.id !== CORNER && { label: b.folded ? "Unfold the card" : "Fold the card", hint: `/${b.folded ? "unfold" : "fold"} @${name}`,
      run: () => fold(b) },
    b.id !== CORNER && "-",
    b.id !== CORNER && { label: "Demolish…", hint: `/demolish @${name}`, danger: true, run: () => { demolishing.value = b.id; } },
  ]);
}

/** The garrison's lead as its head alone, no framed name (it is in the tooltip and the Info), then its harness scheme.
 *  A yard has no ork of its own (docs/design/yards.md §2): its head stands there only while one visits, with the word. */
function Keeper({ garrison, alert, yard, visit }) {
  if (!garrison.length || (yard && !visit)) return null;
  const lead = garrison.find((o) => o.lead) || garrison[0];
  const busy = garrison.some((o) => o.status === "busy");
  const more = garrison.length - 1;
  const doing = alert ? say("asks you") : busy ? say("at work") : say("idle");
  return html`<span class="gui-hut__keeper" title=${`${lead.name}${more > 0 ? ` +${more}` : ""}${visit ? ` · ${say("visiting")}` : ""} · ${doing}`}>
    <${OrkHead} o=${busy && lead.status !== "busy" ? { ...lead, status: "busy" } : lead} alert=${!!alert} />
    <${Scheme} scheme=${lead.scheme} />${visit && html`<span class="gui-hut__visit">visiting</span>`}</span>`;
}

// -- its orks, seen from outside (docs/design/yards.md §4) -----------------------------------------------------
// In Camp the head left the title bar: a building says what its orks do over its roof — Zz while they sleep, a
// wheel while they work. A yard shows nothing: no ork lives in it. Its ork comes out onto the plinth under the
// mouse, or by itself to ask (js/visit.js). Office keeps its words (office.css).

function Doing({ b, busy }) {
  if (b.yard || b.alert || !b.garrison.length) return null;
  return html`<i class=${cls("gui-hut__doing", busy ? "is-busy" : "is-idle")} aria-hidden="true"
    title=${say(busy ? "at work" : "idle")}></i>`;
}

/** A yard's name stands over its building, on the ground, with no plate (Camp). */
function YardName({ b, number }) {
  return html`<span class="gui-hut__yard-name" title=${number <= 9 ? say(`Press ${number} to open it`) : ""}>
    <span class="no">${number}</span><${TypeIcon} type=${b.type} /><span class="gui-hut__yard-title">${say(b.title)}</span></span>`;
}

// -- fire: a building whose ork waits for you burns (design-system README: States and motion) --------------
// Its card is ablaze from the first second (components.css); from FIRE_FROM s flames climb its roof, one more
// a minute until FIRE_FULL s covers it. Never in quiet hours, nor when the portrait's menu turned them off; under
// prefers-reduced-motion they stand still (components.css).
const FIRE_FROM = 60, FIRE_FULL = 300;
const FLAMES = [[50, 46], [24, 26], [76, 30], [38, 4], [62, 8]];        // where each flame stands: % of the roof
const now = signal(Date.now());
setInterval(() => { now.value = Date.now(); }, 10_000);
const firstSeen = new Map();               // alert id → when it began, as this page counts it

function Flames({ alert }) {
  const hud = (town.value && town.value.hud) || {};
  if (!alert || hud.fire === false || hud.quiet) return null;
  if (!firstSeen.has(alert.id)) firstSeen.set(alert.id, Date.now() - (alert.waited || 0) * 1000);
  const waited = (now.value - firstSeen.get(alert.id)) / 1000;
  if (waited < FIRE_FROM) return null;
  const n = Math.min(FLAMES.length, 1 + Math.floor(((waited - FIRE_FROM) / (FIRE_FULL - FIRE_FROM)) * (FLAMES.length - 1)));
  return html`${FLAMES.slice(0, n).map(([x, y], i) => html`<i key=${i} class="ok-flame is-sprite gui-hut__flame" aria-hidden="true"
    style=${`left:${x}%;bottom:${y}%;animation-delay:${-i * 0.15}s`}></i>`)}`;
}

/** Its quick actions on the card's bottom edge, out while the mouse is on the hut, it has the focus or it is
 *  selected: a press does that one thing — a small window of its own when it asks for words, else it is
 *  done — and never opens the building. */
export function QuickTray({ b }) {
  if (!b.quick || !b.quick.length) return null;
  const keep = (e) => e.stopPropagation();
  return html`<div class="gui-hut__quick" onPointerDown=${keep} role="group" aria-label=${say(`${b.title}: quick actions`)}>
    ${b.quick.map((a) => html`<button key=${a.id} class="ok-btn gui-hut__quick-one"
        onClick=${(e) => { keep(e); runQuick(b, a.id); }}>${say(a.label)}</button>`)}
  </div>`;
}

/** The inside of the card (closed): the type's own `card(b)` (js/types.js), else its status lines. */
export function Card({ b }) {
  const mod = b.page ? typeModule(b.type) : null;
  if (mod && mod.card) return html`<div class="gui-hut__body ok-font-status">${mod.card(b, levelOf(b))}</div>`;
  return b.status_plain.length > 0 ? html`<ul class="ok-hut__lines">
    ${b.status_plain.map((line, i) => html`<li key=${i}>${line}</li>`)}</ul>` : null;
}

/** The corner a card is stretched by (its edges pull roads, js/hut.js edgeAt): a ghost of the new size follows the
 *  mouse, red over another hut; a double click gives the card back its own size. */
function Grips({ b, onSized }) {
  const grab = (e, sides) => {
    if (e.button !== 0) return;
    e.stopPropagation();
    e.preventDefault();
    const card = e.currentTarget.closest(".ok-hut__card");
    const from = { x: e.clientX, y: e.clientY, w: card.offsetWidth, h: card.offsetHeight };
    const el = e.currentTarget;
    el.setPointerCapture(e.pointerId);
    let gone = false;
    const clamp = (v, lo, hi) => Math.round(Math.min(Math.max(v, lo), hi));
    const step = stepOf(b);
    const move = (ev) => {
      resizing.value = { id: b.id,
        w: sides.includes("e") ? snap(clamp(from.w + ev.clientX - from.x, HUT_MIN.w, HUT_MAX.w), step && step.w) : from.w,
        h: sides.includes("s") ? snap(clamp(from.h + ev.clientY - from.y, HUT_MIN.h, HUT_MAX.h), step && step.h) : from.h };
    };
    const key = (ev) => { if (ev.key === "Escape") { ev.stopImmediatePropagation(); gone = true; end(); } };
    const end = () => {
      el.removeEventListener("pointermove", move);
      el.removeEventListener("pointerup", up);
      window.removeEventListener("keydown", key, true);
      const r = resizing.value;
      resizing.value = null;
      return r;
    };
    const up = () => {
      const r = end();
      if (!gone && r && (r.w !== from.w || r.h !== from.h)) onSized(b, r.w, r.h);
    };
    el.addEventListener("pointermove", move);
    el.addEventListener("pointerup", up);
    window.addEventListener("keydown", key, true);
  };
  const back = (e) => { e.stopPropagation(); if (b.size) command("hut.size", { id: b.id, w: null }).catch(() => {}); };
  const label = say("Drag to resize · double-click: its own size");
  return html`${[["es", "is-se"]].map(([sides, c]) => html`<span key=${c}
      class=${cls("gui-hut__grip", c)} title=${label} aria-hidden="true"
      onPointerDown=${(e) => grab(e, sides)} onClick=${(e) => e.stopPropagation()} onDblClick=${back}></span>`)}`;
}

// The road handle comes where the mouse nears the card's edge — the yard's fence, the hut's frame — and a road is
// pulled out of it there; it leaves no gate behind, the road keeps its arrow. The corner it stays clear of resizes.
const EDGE_PX = 12, CORNER_PX = 20;

/** The point on the card's edge the mouse is near, in the card's own px, or null (inside, or at the resizing corner). */
function edgeAt(card, e) {
  const r = card.getBoundingClientRect(), k = r.width / card.offsetWidth || 1;
  const w = card.offsetWidth, h = card.offsetHeight, x = (e.clientX - r.left) / k, y = (e.clientY - r.top) / k;
  const d = { left: x, right: w - x, top: y, bottom: h - y };
  const side = Object.keys(d).reduce((a, k2) => (d[k2] < d[a] ? k2 : a), "left");
  if (d[side] > EDGE_PX || (w - x < CORNER_PX && h - y < CORNER_PX)) return null;
  const clamp = (v, hi) => Math.min(Math.max(v, 11), hi - 11);
  return side === "left" ? { x: 0, y: clamp(y, h) } : side === "right" ? { x: w, y: clamp(y, h) }
    : side === "top" ? { x: clamp(x, w), y: 0 } : { x: clamp(x, w), y: h };
}

export function Hut({ b, spot, number, dim = false, fresh = false, onMoved, onSized }) {
  const ref = useRef(null);
  const road = useRef(null);
  const [near, setNear] = useState(false);   // the mouse over it: its ork comes out (js/visit.js)
  // the handle follows the mouse along the edge without drawing the hut again
  const nearEdge = (e) => {
    const btn = road.current;
    if (!btn || e.pointerType !== "mouse" || btn.contains(e.target)) return;
    // never over a control, nor on the title bar: that moves the card (a yard's is its top fence)
    const at = e.target.closest("button, a, input, select, textarea, .gui-hut__title") ? null : edgeAt(e.currentTarget, e);
    btn.classList.toggle("is-at", !!at);
    if (at) { btn.style.left = `${at.x}px`; btn.style.top = `${at.y}px`; }
  };
  const awayEdge = () => { if (road.current) road.current.classList.remove("is-at"); };
  const drag = dragging.value && dragging.value.id === b.id ? dragging.value : null;
  // Its size as drawn, on every draw and whenever it changes between them (a type's stylesheet coming
  // late, a part of its card hidden): the town places the huts and the roads by it.
  const measure = () => {
    const el = ref.current;
    if (!el) return;
    const w = el.offsetWidth, h = el.offsetHeight;
    // Where roads meet the hut (docs/design/yards.md §3f): a yard's fence, a hut's plinth in Camp, the card's frame in
    // Office (no plinth drawn). A yard's top fence leaves a gap the width of its house.
    const card = el.querySelector(".ok-hut__card");
    let top = card ? card.offsetTop : 0, ch = card ? card.offsetHeight : h, px = 0, pw = w;
    const plinth = el.querySelector(".gui-hut__plinth");
    if (plinth && plinth.offsetWidth) {
      const hr = el.getBoundingClientRect(), pr = plinth.getBoundingClientRect(), k = hr.width / w || 1;
      const left = Math.round((pr.left - hr.left) / k), width = Math.round(pr.width / k);
      el.style.setProperty("--house-w", `${left + width}px`);
      if (!b.yard) {
        top = Math.round((pr.top - hr.top) / k); ch = Math.round(pr.height / k); px = left; pw = width;
      }
    }
    const old = sizes.value[b.id];
    if (!old || old.w !== w || old.h !== h || old.top !== top || old.ch !== ch || old.px !== px || old.pw !== pw) {
      sizes.value = { ...sizes.value, [b.id]: { w, h, top, ch, px, pw } };
    }
  };
  useLayoutEffect(measure);
  useLayoutEffect(() => {
    if (!ref.current || typeof ResizeObserver === "undefined") return undefined;
    const ro = new ResizeObserver(measure);
    ro.observe(ref.current);
    return () => ro.disconnect();
  }, [b.id]);
  const free = !b.pinned && b.id !== CORNER;   // pinned by the person, or the Hall: never moves
  const busy = busyOf(b);
  const hot = b.alert && b.alert.waited >= 30;
  const folded = !!b.folded && b.id !== CORNER;
  const peek = folded && (peekReasons(b).length > 0 || dragOver.value === b.id);
  // A drag held over a folded hut peeks it, so a drop target (the Pit) is never a title bar alone.
  const dragIn = folded ? () => { if (dragOver.value !== b.id) dragOver.value = b.id; } : undefined;
  const dragOut = folded ? (e) => { if (!e.currentTarget.contains(e.relatedTarget) && dragOver.value === b.id) dragOver.value = null; } : undefined;

  function down(e) {
    if (e.button !== 0) return;
    const start = { x: e.clientX, y: e.clientY };
    let moved = false, gone = false;
    const el = e.currentTarget;
    el.setPointerCapture(e.pointerId);
    const move = (ev) => {
      const dx = ev.clientX - start.x, dy = ev.clientY - start.y;
      if (gone || (!moved && Math.hypot(dx, dy) < DRAG_PX)) return;
      if (!moved && !free) warnPinned(b.id);
      moved = true;
      if (!free) return;                   // a pinned hut keeps its place: a drag on it does nothing
      dragging.value = { id: b.id, dx, dy };   // the hut stays; its ghost moves (js/town.js Footprint)
    };
    // Esc lets the ghost go: the hut was never moved
    const key = (ev) => { if (ev.key === "Escape" && moved) { ev.stopImmediatePropagation(); gone = true; dragging.value = null; } };
    const up = (ev) => {
      el.removeEventListener("pointermove", move);
      el.removeEventListener("pointerup", up);
      window.removeEventListener("keydown", key, true);
      dragging.value = null;
      if (gone) return;
      if (moved) { if (free) { onMoved(b, spot.x + ev.clientX - start.x, spot.y + ev.clientY - start.y); } }
      else openBuilding(b.id);
    };
    el.addEventListener("pointermove", move);
    el.addEventListener("pointerup", up);
    window.addEventListener("keydown", key, true);
  }

  const x = spot.x, y = spot.y;
  const level = levelOf(b);
  const sized = b.size && !folded;
  const step = stepOf(b);                  // a yard's size, as saved before, is drawn in whole pickets
  const w = sized ? snap(b.size[0], step && step.w) : 0, h = sized ? snap(b.size[1], step && step.h) : 0;
  // The name heads the card: in Camp a bevelled title bar with the garrison's badge under the header
  // sprite, as on a window; in Office a plain line, so a block on the map is one box and its roads
  // meet that box.
  const title = html`<span class="ok-hut__label gui-hut__title"><span class="no" title=${number <= 9 ? say(`Press ${number} to open it`) : ""}>${number}</span>
      ${busy && html`<span class="gui-hut__spin" role="img" title=${say("Working")} aria-label=${say("Working")}></span>`}
      <${TypeIcon} type=${b.type} />
      <span class="gui-hut__name">${say(b.title)}</span>
      <${Keeper} garrison=${b.garrison} alert=${b.alert} yard=${!!b.yard} visit=${b.visit || ""} />
      ${b.alert && html`<span class="ok-word gui-hut__ask">?</span>`}
      ${folded && html`<${Mark} b=${b} />`}
      ${b.id !== CORNER && html`<${PinButton} b=${b} />`}
      ${b.id !== CORNER && html`<${FoldButton} b=${b} peek=${peek} />`}</span>`;
  return html`<div ref=${ref} data-id=${b.id} style=${`left:${x}px;top:${y}px` + (sized ? `;width:${w}px` : "")}
      class=${cls("ok-hut m gui-hut", { "is-selected": opened.value.active === b.id, "is-busy": busy, "is-yard": !!b.yard,
                                        "is-alert": !!b.alert, "is-hot": hot, "is-paused": !!b.paused, "is-dragging": !!drag, "is-dim": dim,
                                        "is-free": free, "is-target": pulling.value?.over === b.id,
                                        "is-fresh": fresh, "is-folded": folded, "is-peek": peek,
                                        "is-sized": !!sized, [`is-size-${level}`]: !!sized,
                                        "is-resizing": resizing.value?.id === b.id })}
      onPointerDown=${down} onContextMenu=${(e) => buildingMenu(e, b)} onDragEnter=${dragIn} onDragLeave=${dragOut}
      onPointerEnter=${(e) => e.pointerType === "mouse" && setNear(true)} onPointerLeave=${() => setNear(false)}>
    <div class="ok-head"><span class="gui-hut__roof"><${HutSprite} className="gui-hut__sprite" type=${b.type} biome=${activeBiome()} goal=${b.goal}
      level=${b.level} onError=${(e) => { e.currentTarget.hidden = true; }} /><${Flames} alert=${b.alert} />
      <${Doing} b=${b} busy=${busy} />${b.yard && html`<${YardName} b=${b} number=${number} />`}
      <span class="gui-hut__plinth" aria-hidden="true"></span><${Outside} b=${b} near=${near} /></span></div>
    <div class="ok-hut__card" style=${sized ? `height:${h}px` : ""} onPointerMove=${nearEdge} onPointerLeave=${awayEdge}>
      ${title}
      <button ref=${road} class="gui-hut__road" title=${say("Pull a road to another building")} aria-label=${say("Pull a road")}
        onPointerDown=${(e) => pull(e, b)}><img class="ok-sprite" src="/ds/sprites/icons/road-handle.png"
        srcset="/ds/sprites/icons/road-handle@2x.png 2x" width="22" height="22" alt="" draggable="false" /></button>
      ${!folded ? html`<${Card} b=${b} /><${QuickTray} b=${b} />`
        : peek ? html`<div class="gui-hut__peek"><${Card} b=${b} /><${QuickTray} b=${b} /></div>`
        : html`<${QuickTray} b=${b} />`}
      ${!folded && onSized && html`<${Grips} b=${b} onSized=${onSized} />`}
    </div>
  </div>`;
}

