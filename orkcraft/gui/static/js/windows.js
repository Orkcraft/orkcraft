// The town's panel on the right (docs/design/calm-town.md §2): a click on a hut opens its building there,
// over the right half of the town, and the map keeps the rest. Its tabs: the building's Work (its view,
// `buildings/<type>.js` `panes`) and Info (js/console.js: about, garrison, steward, roads), then the
// documents opened from it (Lake, js/lake.js). An ork picked in the garrison opens in the same panel with
// ← back. ⤢ takes the whole town; Esc steps back: whole → half, an ork → its building, then closed. Closed
// with documents open, the panel waits as a handle at the right edge. A setup in steps (js/setup.js) has its
// ← Back in the bar's top right corner, past its first step; done, the panel opens the building's Info.
import { signal, effect } from "@preact/signals";
import { html, cls } from "./html.js";
import { town, command, details, online, say } from "./link.js";
import { Layout } from "./layout.js";
import { HALL } from "./tent.js";
import { openOrders } from "./orders.js";
import { useEffect, useLayoutEffect, useRef } from "preact/hooks";
import { typeModule } from "./types.js";
import { lake, tabs as docTabs, DocTab, DocBody } from "./lake.js";
import { InfoTab, OrkView, RuleView } from "./console.js";
import { setupBack } from "./setup.js";
import { buildingMenu } from "./hut.js";

// A type's window is `buildings/<type>.js` (js/types.js): the host draws a type when
// `gui/views/<type>.py` exists (its detail carries data); a new type is new files, no list here.
const viewOf = (type) => typeModule(type);

export const panelWidth = signal(0);       // how wide the panel stands over the town (js/town.js scrolls by it)

// The open building; `ork`: one of its orks picked in its garrison; `tab`: work | info; `full`: the whole town.
export const opened = signal({ active: null, ork: null, tab: "work", full: false });
// The selected building (docs/design/select-a-building.md §1): a click selects — its ork comes out, the Warchief's
// line is its card — and opens nothing; a second click, a double click or Open on its card opens it. An open
// building is selected too.
export const selected = signal(null);

/** A click on a building (or its number): selected; the selected one again, opened. */
export function pickBuilding(id) {
  if (selected.value === id) openBuilding(id);
  else selected.value = id;
}

/** Nothing selected (a click on the bare town, Escape with no window up). */
export function letGo() {
  selected.value = null;
}

function select(id, tab) {
  selected.value = id;
  const o = opened.value;
  if (o.active !== id) command("building.open", { id }).catch(() => {});
  opened.value = { active: id, ork: o.active === id ? o.ork : null, tab: tab || (o.active === id ? o.tab : "work"),
                   full: o.active === id && o.full };
  lake.value = { ...lake.value, front: false };
}

/** A click on a building's hut: it opens in the panel (its Work tab, or the tab it had). */
/** A building's number as its card shows it: its place among the open orkspace's buildings, the hall left out
 * (app.js, js/town.js `numbered`), not among the whole town's. */
function numberOf(b) {
  const t = town.value;
  const space = t.orkspaces.find((o) => o.id === t.active_orkspace);
  const ids = new Set(space ? space.buildings : t.buildings.map((x) => x.id));
  ids.delete(HALL);
  return t.buildings.filter((x) => ids.has(x.id)).indexOf(b) + 1 || "";
}

export function openBuilding(id, tab) {
  select(id, tab);
}

/** Open a building in the panel straight away (the War Tent, a session to show). */
export function showBuilding(id) {
  select(id);
}

export function closeBuilding(id) {
  if (id === undefined || opened.value.active === id) opened.value = { active: null, ork: null, tab: "work", full: false };
}

/** ✕: the panel closes, its documents wait at the handle. */
/** A setup in steps is done (a source added, a board saved): the building's Info, not its last step. */
export function setupDone(id) {
  if (opened.value.active === id) opened.value = { ...opened.value, tab: "info", ork: null };
}

function closePanel() {
  closeBuilding();
  lake.value = { ...lake.value, shown: false, front: false };
}

/** An ork of the open building picked in its garrison (null: back to the building). */
export function selectOrk(ref) {
  opened.value = { ...opened.value, ork: ref, tab: "info" };
  lake.value = { ...lake.value, front: false };
}

function pickTab(tab) {
  opened.value = { ...opened.value, tab, ork: null };
  lake.value = { ...lake.value, front: false };
}

function pickDoc(id) {
  lake.value = { ...lake.value, shown: true, front: true, active: id };
}

const toggleFull = () => { opened.value = { ...opened.value, full: !opened.value.full }; };

/** Is the panel up: a building open, or documents shown. */
export function panelShown() {
  return !!chosen() || (lake.value.shown && docTabs().length > 0);
}

/** Esc: the whole town goes back to half, a picked ork back to its building, else the panel closes. */
function stepBack() {
  const o = opened.value;
  if (o.full) opened.value = { ...o, full: false };
  else if (o.ork) opened.value = { ...o, ork: null };
  else closePanel();
}

// Esc on the page, unless a dialog takes it or the keys go to a field or a terminal: the window steps back; with
// none up, the selected building is let go.
window.addEventListener("keydown", (e) => {
  if (e.key !== "Escape" || document.querySelector(".gui-modal, .gui-menu")) return;
  if (e.target.closest && e.target.closest("input, textarea, select, [contenteditable], .gui-term")) return;
  if (panelShown()) stepBack();
  else if (selected.value) letGo();
});

// The host sends the open building's own state, and the Town Hall's (the Warchief's line shows his chat),
// and again when its worker says it changed.
// A small window of a closed building (a quick action's, js/types.js overlay) wants its state too, while it stands.
const peeking = signal({});                 // building id → how many small windows want its state

/** A small window over a closed building: its state comes while the window stands. */
export function usePeek(id) {
  useEffect(() => {
    peeking.value = { ...peeking.value, [id]: (peeking.value[id] || 0) + 1 };
    return () => {
      const n = (peeking.value[id] || 1) - 1;
      const { [id]: _, ...rest } = peeking.value;
      peeking.value = n > 0 ? { ...rest, [id]: n } : rest;
    };
  }, [id]);
}

effect(() => {
  const id = opened.value.active, peeked = Object.keys(peeking.value);
  if (online.value) command("watch", { ids: [...new Set([HALL, ...(id ? [id] : []), ...peeked])] }).catch(() => {});
});

function Question({ alert }) {
  return html`<p class="ok-font-body ok-tone-fire gui-alert">${alert.title}
    <button class="ok-act" onClick=${() => openOrders(alert.id)}><span class="ok-act__label">Answer</span></button></p>`;
}

/** ⋯ in the bar: the building's menu, the same as a right click on its hut — Demolish is there, rare and
 *  confirmed, never a button in view. Opened under the button, from the mouse or the keys. */
function More({ b }) {
  const open = (e) => {
    const r = e.currentTarget.getBoundingClientRect();
    buildingMenu({ preventDefault() {}, stopPropagation() { e.stopPropagation(); }, clientX: r.left, clientY: r.bottom }, b);
  };
  return html`<button class="gui-tab__close gui-panel__more" title=${say("More: pin, fold, demolish…")}
    aria-label=${say("More")} aria-haspopup="menu" onClick=${open}>⋯</button>`;
}

/** Work: the building's own view by its UI document; a type without one shows its status lines. */
function Work({ b }) {
  const d = details.value[b.id];
  const view = d && d.data && viewOf(d.type);
  if (view) {
    return html`<div class="ok-win__body gui-win__body is-view"><${Layout} doc=${d.ui} panes=${view.panes(b.id, d.data)} /></div>`;
  }
  return html`<div class="ok-win__body gui-win__body">
    ${b.status_plain.length > 0 ? html`<section class="gui-section">
      ${b.status_plain.map((line, i) => html`<div key=${i} class="ok-font-status">${line}</div>`)}</section>`
      : html`<p class="ok-font-status ok-tone-muted">${d ? say("Nothing to show yet.") : say("Opening…")}</p>`}
  </div>`;
}

/** Does the building have a view of its own (a Work tab)? Unknown while its detail comes: yes. */
function hasWork(b) {
  const d = details.value[b.id];
  return !d || !!(d.data && b.page) || b.status_plain.length > 0;
}

export function chosen() {
  const o = opened.value;
  const b = o.active && town.value.buildings.find((x) => x.id === o.active);
  return b ? { b, full: o.full } : null;   // nothing open, or it was demolished
}

/** The panel's width, kept in `panelWidth` while it stands. */
function useMeasure(shown) {
  const ref = useRef(null);
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) { panelWidth.value = 0; return undefined; }
    const set = () => { panelWidth.value = el.offsetWidth; };
    set();
    const ro = new ResizeObserver(set);
    ro.observe(el);
    return () => { ro.disconnect(); panelWidth.value = 0; };
  }, [shown]);
  return ref;
}

/** The panel: the open building's tabs and the documents' tabs; a handle while it is closed with documents. */
export function Panel() {
  const measured = useMeasure(panelShown());
  const c = chosen();
  const docs = docTabs();
  const l = lake.value;
  const o = opened.value;
  if (!c && !(l.shown && docs.length)) {
    return docs.length ? html`<button class="ok-btn gui-panel__handle" title=${say("Show the documents")}
      onClick=${() => { lake.value = { ...l, shown: true, front: true }; }}>${say("Lake")} · ${docs.length}</button>` : null;
  }
  const b = c && c.b;
  const front = !b || (l.front && l.shown && docs.length > 0);
  const work = b && hasWork(b);
  const tab = b && (o.tab === "work" && !work ? "info" : o.tab);
  const hot = b && b.alert && b.alert.waited >= 30;
  const activeDoc = docs.find((t) => t.id === l.active) || docs[docs.length - 1];
  return html`<section ref=${measured} class=${cls("ok-win is-active gui-win gui-panel", { "is-full": o.full, "is-alert": !!(b && b.alert), "is-hot": !!hot })}
      aria-label=${b ? say(b.title) : say("Lake")}>
    <div class="ok-win__frame">
      <div class="ok-win__bar" onDblClick=${toggleFull}>
        ${b && html`<span class="ok-win__no">${numberOf(b)}</span>`}
        <span class="ok-win__title">${b ? say(b.title) : say("Lake")}</span>
        <div class="ok-tabs gui-panel__tabs" role="tablist" onDblClick=${(e) => e.stopPropagation()}>
          ${b && work && html`<button class=${cls("ok-tab", { "is-active": !front && tab === "work" })} role="tab"
              aria-selected=${!front && tab === "work"} onClick=${() => pickTab("work")}>${say("Work")}</button>`}
          ${b && html`<button class=${cls("ok-tab", { "is-active": !front && tab === "info" })} role="tab"
              aria-selected=${!front && tab === "info"} onClick=${() => pickTab("info")}>${say("Info")}</button>`}
          ${l.shown && docs.map((t) => html`<${DocTab} key=${t.id} t=${t} active=${front && activeDoc && t.id === activeDoc.id}
              onPick=${() => pickDoc(t.id)} />`)}
        </div>
        <span class="gui-head__spacer"></span>
        ${b && !front && setupBack.value[b.id] && html`<button class="ok-btn gui-panel__back" title=${say("One step back")}
          onClick=${setupBack.value[b.id]}>← ${say("Back")}</button>`}
        ${b && html`<${More} b=${b} />`}
        <button class="gui-tab__close gui-panel__full" title=${o.full ? say("Half the town") : say("The whole town")}
          aria-label=${o.full ? say("Half") : say("Full")} onClick=${toggleFull}>${o.full ? "⤡" : "⤢"}</button>
        <button class="gui-tab__close gui-win__close" title=${say("Close (Esc)")} aria-label=${say("Close")}
          onClick=${closePanel}>×</button>
      </div>
      ${b && b.alert && html`<${Question} alert=${b.alert} />`}
      ${front ? html`<${DocBody} />`
        : tab === "work" ? html`<${Work} b=${b} />`
        : o.ork && b.garrison.some((x) => x.ref === o.ork) ? html`<${OrkView} b=${b} orkRef=${o.ork} />`
        : o.ork && (b.rules || []).some((x) => x.ref === o.ork) ? html`<${RuleView} b=${b} ruleRef=${o.ork} />`
        : html`<${InfoTab} b=${b} />`}
    </div>
  </section>`;
}
