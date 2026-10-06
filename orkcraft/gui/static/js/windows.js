// A building, three ways, as in the TUI: its hut on the town (the minimal look: the lines its type
// keeps, gui/state.py), selected (one click: the console at the bottom right, js/console.js) and open (a click on the selected hut: its whole window over the town). Which one
// is shown is the page's own state. Esc steps back: open → selected → nothing.
import { signal, effect } from "@preact/signals";
import { html, cls } from "./html.js";
import { town, command, details, online, say } from "./link.js";
import { Layout } from "./layout.js";
import { HALL, deploy } from "./tent.js";
import { openOrders } from "./orders.js";
import { Demolish } from "./build.js";
import { useState } from "preact/hooks";
import { typeModule } from "./types.js";
import { OrkHead, headerSprite } from "./icons.js";

// A type's window is `buildings/<type>.js` (js/types.js): the host draws a type when
// `gui/views/<type>.py` exists (its detail carries data); a new type is new files, no list here.
const viewOf = (type) => typeModule(type);

// The selected building; `ork`: one of its orks picked in the console; `full`: open over the town.
export const opened = signal({ active: null, ork: null, full: false });

function select(id, full) {
  const o = opened.value;
  if (o.active !== id) command("building.open", { id }).catch(() => {});
  opened.value = { active: id, ork: o.active === id ? o.ork : null, full };
}

/** A click on a building's hut: the first selects it, a click on the selected one opens it. */
export function openBuilding(id) {
  const o = opened.value;
  select(id, o.active === id);
}

/** Open a building over the town straight away (the War Tent, a session to show). */
export function showBuilding(id) {
  select(id, true);
}

export function closeBuilding(id) {
  if (id === undefined || opened.value.active === id) opened.value = { active: null, ork: null, full: false };
}

/** An ork of the selected building picked in its garrison (null: back to the building). */
export function selectOrk(ref) {
  opened.value = { ...opened.value, ork: ref, full: false };
}

/** Esc: an open building goes back to selected, a picked ork back to its building, a selected one lets go. */
export function stepBack() {
  const o = opened.value;
  opened.value = o.full ? { ...o, full: false } : o.ork ? { ...o, ork: null } : { active: null, ork: null, full: false };
}

// Esc on the page, unless a dialog takes it or the keys go to a field or a terminal.
window.addEventListener("keydown", (e) => {
  if (e.key !== "Escape" || !opened.value.active || document.querySelector(".gui-modal")) return;
  if (e.target.closest && e.target.closest("input, textarea, select, [contenteditable], .gui-term")) return;
  stepBack();
});

// The host sends the selected building's own state, and again when its worker says it changed.
effect(() => {
  const id = opened.value.active;
  if (online.value) command("watch", { ids: id ? [id] : [] }).catch(() => {});
});

/** The garrison badge: the lead ork's name, how many more, the harness scheme, `?` while asking. */
export function Badge({ garrison, alert }) {
  if (!garrison.length) return null;
  const lead = garrison.find((o) => o.lead) || garrison[0];
  const more = garrison.length - 1;
  const busy = garrison.some((o) => o.status === "busy");
  return html`<span class=${cls("ok-badge", { "is-alert": !!alert })}>
    <${OrkHead} o=${busy && lead.status !== "busy" ? { ...lead, status: "busy" } : lead} alert=${!!alert} />
    ${lead.name}${more > 0 ? `+${more}` : ""}
    ${lead.scheme && html` <span class="gui-scheme">${lead.scheme}</span>`}
    ${alert ? html` <span class="ok-word">?</span>` : busy ? html` <span class="ok-word">busy</span>` : ""}
  </span>`;
}

function Roads({ b, t }) {
  const titles = Object.fromEntries(t.buildings.map((x) => [x.id, say(x.title)]));
  const incoming = t.roads.filter((r) => r.to === b.id);
  const outgoing = t.roads.filter((r) => r.from === b.id);
  if (!incoming.length && !outgoing.length) return null;
  const row = (r, other) => html`<li key=${r.id}>
    <span class="ok-font-label">${titles[other] || other}</span>
    <span class="ok-font-status ok-tone-muted"> · ${r.label}${r.handler ? ` · ${r.handler}` : ""}</span></li>`;
  return html`<section class="gui-section">
    ${incoming.length > 0 && html`<h3 class="ok-font-heading">${say("Roads in")}</h3>
      <ul class="gui-rows">${incoming.map((r) => row(r, r.from))}</ul>`}
    ${outgoing.length > 0 && html`<h3 class="ok-font-heading">${say("Roads out")}</h3>
      <ul class="gui-rows">${outgoing.map((r) => row(r, r.to))}</ul>`}
  </section>`;
}

function Garrison({ garrison, b }) {
  if (!garrison.length) return null;
  return html`<section class="gui-section">
    <h3 class="ok-font-heading">${say("Garrison")}</h3>
    <ul class="gui-rows">${garrison.map((o) => html`<li key=${o.name}>
      <${OrkHead} o=${o} /> <span class="ok-font-label">${o.name}</span>
      ${o.scheme && html` <span class="gui-scheme">${o.scheme}</span>`}
      <span class="ok-font-status ok-tone-muted"> · ${o.lead ? "steward" : o.tier || o.kind} · ${o.status}</span>
      ${(o.kind === "agent" || o.kind === "hybrid") && html` <button class="ok-act" onClick=${() => deploy(o.ref)}>
        <span class="ok-act__label">${o.session ? "Its session" : "Deploy"}</span></button>`}
      ${o.role && html`<div class="ok-font-status ok-tone-muted">${o.role}</div>`}
    </li>`)}</ul>
  </section>`;
}

function About({ b, t }) {
  return html`<details key=${b.id} class="gui-about">
    <summary class="ok-font-heading">${say("About this building")}</summary>
    <${Garrison} garrison=${b.garrison} b=${b} />
    <${Roads} b=${b} t=${t} />
  </details>`;
}

/** The window's last row: About this building (a view's), Demolish at the bottom right. */
function Foot({ b, children }) {
  return html`<div class="gui-win__foot">
    ${children || html`<span class="gui-head__spacer"></span>`}
    ${b.id !== HALL && html`<${DemolishButton} b=${b} />`}
  </div>`;
}

export function Question({ alert }) {
  return html`<p class="ok-font-body ok-tone-fire gui-alert">${alert.title}
    <button class="ok-act" onClick=${() => openOrders(alert.id)}><span class="ok-act__label">Answer</span></button></p>`;
}

function Body({ b, t }) {
  const d = details.value[b.id];
  const view = d && d.data && viewOf(d.type);
  if (view) {
    return html`<div class="ok-win__body gui-win__body is-view">
      ${b.alert && html`<${Question} alert=${b.alert} />`}
      <${Layout} doc=${d.ui} panes=${view.panes(b.id, d.data)} />
      <${Foot} b=${b}><${About} b=${b} t=${t} /></${Foot}>
    </div>`;
  }
  return html`<div class="ok-win__body gui-win__body">
    ${b.alert && html`<${Question} alert=${b.alert} />`}
    ${b.status_plain.length > 0 && html`<section class="gui-section">
      ${b.status_plain.map((line, i) => html`<div key=${i} class="ok-font-status">${line}</div>`)}</section>`}
    ${!b.has_worker && html`<p class="ok-font-status ok-tone-muted">
      This building's own view is not in the window yet; it works in the TUI meanwhile.</p>`}
    <${Garrison} garrison=${b.garrison} b=${b} />
    <${Roads} b=${b} t=${t} />
    <${Foot} b=${b} />
  </div>`;
}

export function DemolishButton({ b }) {
  const [asking, setAsking] = useState(false);
  return html`<button class="ok-act gui-win__demolish" onClick=${() => setAsking(true)}>
    <span class="ok-act__label">Demolish</span></button>
    ${asking && html`<${Demolish} b=${b} onClose=${() => setAsking(false)} />`}`;
}

/** Open: the building's whole window over the town. */
function Full({ b, t }) {
  const hot = b.alert && b.alert.waited >= 30;
  return html`<section class=${cls("ok-win is-active gui-win gui-full", { "is-alert": !!b.alert, "is-hot": hot })}>
    <div class="ok-head is-banner"><img class="ok-sprite gui-win__banner" src=${headerSprite(b.type)} alt=""
      onError=${(e) => { e.currentTarget.hidden = true; }} /></div>
    <div class="ok-win__frame">
      <div class="ok-win__bar" onDblClick=${stepBack}>
        <span class="ok-win__no">${t.buildings.indexOf(b) + 1}</span>
        <span class="ok-win__title">${say(b.title)}</span>
        <${Badge} garrison=${b.garrison} alert=${b.alert} />
        <button class="gui-tab__close gui-win__close" title=${say("Back to the town (Esc)")} aria-label=${say("Back to the town")}
          onClick=${stepBack}>×</button>
      </div>
      <${Body} b=${b} t=${t} />
    </div>
  </section>`;
}

export function chosen() {
  const o = opened.value;
  const b = o.active && town.value.buildings.find((x) => x.id === o.active);
  return b ? { b, full: o.full } : null;   // nothing selected, or it was demolished
}

/** The open building, over the whole town. */
export function Opened() {
  const c = chosen();
  return c && c.full ? html`<${Full} b=${c.b} t=${town.value} />` : null;
}
