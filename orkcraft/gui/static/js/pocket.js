// The town in a narrow window (a phone, docs/design/mobile.md §1: a glance, a tap, back in the pocket): no map,
// no roads — the buildings as a list of their cards, closed to one line each, what wants the person first.
// A tap opens a card in place (its live status and its quick actions); Open takes the whole building. A swipe
// to the left lays the card's quick actions over its line. The chips at the top jump to what asks and what
// works; the quiet buildings fold under one line until the person opens them.
import { signal } from "@preact/signals";
import { useRef } from "preact/hooks";
import { html, cls } from "./html.js";
import { openBuilding } from "./windows.js";
import { busy as busyOf } from "./fold.js";
import { Card, Mark, QuickTray } from "./hut.js";
import { runQuick } from "./types.js";
import { TypeIcon, OrkHead } from "./icons.js";
import { say } from "./link.js";

const WIDTH = "(max-width: 640px)";
const query = typeof matchMedia === "function" ? matchMedia(WIDTH) : null;
export const narrow = signal(!!(query && query.matches));
if (query) query.addEventListener("change", (e) => { narrow.value = e.matches; });

const SWIPE_PX = 56;                        // a swipe to the left this long lays out the actions
const STEER_PX = 8;                         // a move shorter than this is still a tap or a scroll
const QUIET_KEY = "orkcraft.pocket.quiet";  // this viewer's choice: the quiet buildings shown or folded
const OPENS_KEY = "orkcraft.pocket.opens";  // building id → how often this viewer opened it here
// The buildings a phone opens most stand first whatever this viewer did: the day's meetings and the task boards.
const FIRST = { war_drum: 10, fields: 10 };
const USUAL = 5;                            // at most this many in "Usually open"

const unfolded = signal(null);              // the one building whose card is open in the list
const swiped = signal(null);                // the one building whose actions lie over its line
const sliding = signal(null);               // {id, dx} while a finger drags a line sideways
const quietShown = signal(readQuiet());
const opens = signal(readOpens());

function readOpens() {
  try { return JSON.parse(localStorage.getItem(OPENS_KEY) || "{}") || {}; } catch { return {}; }
}

/** One more opening of `id` on this device: the list learns what this viewer reaches for. */
function counted(id) {
  opens.value = { ...opens.value, [id]: (opens.value[id] || 0) + 1 };
  try { localStorage.setItem(OPENS_KEY, JSON.stringify(opens.value)); } catch { /* kept for the page */ }
}

/** How likely this viewer opens `b`: its type's standing (a calendar, a task board), then how often it was opened here. */
const likely = (b) => (FIRST[b.type] || 0) + (opens.value[b.id] || 0);

function readQuiet() {
  try { return localStorage.getItem(QUIET_KEY) === "1"; } catch { return false; }
}

function showQuiet(on) {
  quietShown.value = on;
  try { localStorage.setItem(QUIET_KEY, on ? "1" : "0"); } catch { /* a private window keeps it for the page */ }
}

/** What a building's line says closed: its own mark (what its folded card says first), else its first status line. */
function Gist({ b }) {
  const mark = Mark({ b });
  if (mark) return mark;
  const line = (b.status_plain || [])[0];
  return line ? html`<span class="ok-tone-muted">${say(line)}</span>` : null;
}

/** A finger on a line: sideways past SWIPE_PX to the left lays out its actions, to the right puts them away;
 *  a tap opens or closes its card. Up and down is the list's own scroll. */
function useSwipe(b, toggle) {
  const t = useRef({ start: null, steering: null }).current;   // kept across the redraws a drag causes
  const down = (e) => {
    if (e.pointerType === "mouse" && e.button !== 0) return;
    t.start = { x: e.clientX, y: e.clientY, id: e.pointerId };
    t.steering = null;
  };
  const move = (e) => {
    if (!t.start || e.pointerId !== t.start.id) return;
    const dx = e.clientX - t.start.x, dy = e.clientY - t.start.y;
    if (t.steering === null && Math.hypot(dx, dy) >= STEER_PX) {
      t.steering = Math.abs(dx) > Math.abs(dy) ? "side" : "scroll";
      if (t.steering === "side") e.currentTarget.setPointerCapture(e.pointerId);
    }
    if (t.steering === "side") sliding.value = { id: b.id, dx: Math.max(Math.min(dx, 0), -120) };
  };
  const up = (e) => {
    if (!t.start || e.pointerId !== t.start.id) return;
    if (t.steering === "side") { if (e.clientX - t.start.x <= -SWIPE_PX) swiped.value = b.id; }
    else if (t.steering === null) toggle();
    sliding.value = null;
    t.start = null;
  };
  const cancel = () => { sliding.value = null; t.start = null; };
  return { onPointerDown: down, onPointerMove: move, onPointerUp: up, onPointerCancel: cancel };
}

/** The actions a swipe lays over a line: the card's quick actions, Open, and ✕ to put them away. */
function Actions({ b }) {
  const done = () => { swiped.value = null; };
  return html`<div class="gui-pocket__swiped" role="group" aria-label=${say(`${b.title}: quick actions`)}>
    ${(b.quick || []).map((a) => html`<button key=${a.id} class="ok-btn" onClick=${() => { done(); runQuick(b, a.id); }}>${say(a.label)}</button>`)}
    <button class="ok-btn primary" onClick=${() => { done(); counted(b.id); openBuilding(b.id); }}>${say("Open")}</button>
    <button class="ok-btn gui-pocket__away" title=${say("Put the actions away")} aria-label=${say("Put the actions away")}
      onClick=${done}>✕</button>
  </div>`;
}

function Row({ b, number }) {
  const open = unfolded.value === b.id;
  const lead = b.garrison.find((o) => o.lead) || b.garrison[0];
  const busy = busyOf(b);
  const toggle = () => { swiped.value = null; if (!open) counted(b.id); unfolded.value = open ? null : b.id; };
  const finger = useSwipe(b, toggle);
  const dx = sliding.value && sliding.value.id === b.id ? sliding.value.dx : 0;
  const keys = (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); toggle(); } };
  return html`<li id=${`pocket-${b.id}`} class=${cls("gui-pocket__row ok-hut", { "is-open": open, "is-alert": !!b.alert, "is-busy": busy })}>
    ${swiped.value === b.id ? html`<${Actions} b=${b} />`
      : html`<div class="gui-pocket__head" role="button" tabindex="0" aria-expanded=${open} onKeyDown=${keys} ...${finger}
          style=${dx ? `transform:translateX(${dx}px)` : ""}>
        <span class="gui-pocket__no">${number}</span>
        <${TypeIcon} type=${b.type} />
        <span class="gui-pocket__name">${say(b.title)}</span>
        <span class="gui-pocket__gist">${b.alert ? html`<span class="ok-tone-wait">❓ ${say("asks you")}</span>` : html`<${Gist} b=${b} />`}</span>
        ${lead && (b.alert || busy) && html`<${OrkHead} o=${lead} alert=${!!b.alert} />`}
        <span class="gui-pocket__chev" aria-hidden="true">${open ? "▾" : "▸"}</span>
      </div>`}
    ${open && html`<div class="gui-pocket__body">
      <${Card} b=${b} />
      <div class="gui-pocket__acts">
        <${QuickTray} b=${b} />
        <button class="ok-btn primary" onClick=${() => { counted(b.id); openBuilding(b.id); }}>${say("Open")}</button>
      </div>
    </div>`}
  </li>`;
}

/** Jump to a group's first building: its card opens and the list scrolls to it. */
function jump(list) {
  if (!list.length) return;
  const id = list[0].b.id;
  swiped.value = null;
  unfolded.value = id;
  requestAnimationFrame(() => {
    const el = document.getElementById(`pocket-${id}`);
    if (el) el.scrollIntoView({ block: "start", behavior: "smooth" });
  });
}

export function Pocket({ buildings }) {
  const numbered = buildings.map((b, i) => ({ b, n: i + 1 }));
  const asks = numbered.filter((x) => x.b.alert);
  const working = numbered.filter((x) => !x.b.alert && busyOf(x.b));
  // The quiet ones by how likely this viewer opens them: the likeliest stand out as "Usually open", the rest fold.
  const quiet = numbered.filter((x) => !x.b.alert && !busyOf(x.b))
    .sort((x, y) => likely(y.b) - likely(x.b) || x.n - y.n);
  const usual = quiet.filter((x) => likely(x.b) > 0).slice(0, USUAL);
  const rest = quiet.slice(usual.length);
  const rows = (list) => html`<ul class="gui-pocket__list">${list.map((x) => html`<${Row} key=${x.b.id} b=${x.b} number=${x.n} />`)}</ul>`;
  const head = (label, list, tone) => html`<h2 class="ok-list__head gui-pocket__group-head">
    <button class="gui-pocket__jump" onClick=${() => jump(list)} title=${say("Open the first one")}>
      ${say(label)} <span class=${tone}>${list.length}</span></button></h2>`;
  return html`<main class="ok-ground gui-town gui-pocket">
    <nav class="gui-pocket__chips" aria-label=${say("Jump to")}>
      <button class=${cls("ok-btn gui-pocket__chip", { "is-hot": asks.length > 0 })} disabled=${!asks.length}
        onClick=${() => jump(asks)}>❓ ${say("Asks you")} ${asks.length}</button>
      <button class="ok-btn gui-pocket__chip" disabled=${!working.length} onClick=${() => jump(working)}>⚙ ${say("At work")} ${working.length}</button>
    </nav>
    ${asks.length > 0 && html`<section class="gui-pocket__group">${head("Asks you", asks, "ok-tone-wait")}${rows(asks)}</section>`}
    ${working.length > 0 && html`<section class="gui-pocket__group">${head("At work", working, "ok-tone-muted")}${rows(working)}</section>`}
    ${usual.length > 0 && html`<section class="gui-pocket__group">${head("Usually open", usual, "ok-tone-muted")}${rows(usual)}</section>`}
    ${!asks.length && !working.length && !usual.length && buildings.length > 0
      && html`<p class="ok-font-body ok-tone-muted gui-pocket__calm">${say("Nothing asks you and no ork is at work.")}</p>`}
    ${rest.length > 0 && html`<section class="gui-pocket__group">
      <h2 class="ok-list__head gui-pocket__group-head">
        <button class="gui-pocket__jump" aria-expanded=${quietShown.value} onClick=${() => showQuiet(!quietShown.value)}>
          ${quietShown.value ? "▾" : "▸"} ${say(usual.length ? "Other buildings" : "Buildings")} <span class="ok-tone-muted">${rest.length}</span></button></h2>
      ${quietShown.value && rows(rest)}
    </section>`}
    ${!buildings.length && html`<p class="gui-empty ok-font-body ok-tone-muted">${say("No buildings in this orkspace yet.")}</p>`}
  </main>`;
}
