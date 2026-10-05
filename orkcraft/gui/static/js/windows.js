// Opened buildings: Office shows them as an editor group, one tab per building
// (design-system/components.md: Window, Tabs). Which are open is the page's own state.
import { signal } from "@preact/signals";
import { html, cls } from "./html.js";
import { town, command } from "./link.js";

export const opened = signal({ ids: [], active: null, max: false });

export function openBuilding(id) {
  const o = opened.value;
  opened.value = { ...o, ids: o.ids.includes(id) ? o.ids : [...o.ids, id], active: id };
  command("building.open", { id }).catch(() => {});
}

export function closeBuilding(id) {
  const o = opened.value;
  const ids = o.ids.filter((x) => x !== id);
  const active = o.active === id ? ids[ids.length - 1] || null : o.active;
  opened.value = { ...o, ids, active, max: ids.length ? o.max : false };
}

function toggleMax() {
  opened.value = { ...opened.value, max: !opened.value.max };
}

/** The garrison badge: the lead ork's name, how many more, the harness scheme, `?` while asking. */
function Badge({ garrison, alert }) {
  if (!garrison.length) return null;
  const lead = garrison.find((o) => o.lead) || garrison[0];
  const more = garrison.length - 1;
  const busy = garrison.some((o) => o.status === "busy");
  return html`<span class=${cls("ok-badge", { "is-alert": !!alert })}>
    ${lead.name}${more > 0 ? `+${more}` : ""}
    ${lead.scheme && html` <span class="gui-scheme">${lead.scheme}</span>`}
    ${alert ? html` <span class="ok-word">?</span>` : busy ? html` <span class="ok-word">busy</span>` : ""}
  </span>`;
}

function Roads({ b, t }) {
  const titles = Object.fromEntries(t.buildings.map((x) => [x.id, x.title]));
  const incoming = t.roads.filter((r) => r.to === b.id);
  const outgoing = t.roads.filter((r) => r.from === b.id);
  if (!incoming.length && !outgoing.length) return null;
  const row = (r, other) => html`<li key=${r.id}>
    <span class="ok-font-label">${titles[other] || other}</span>
    <span class="ok-font-status ok-tone-muted"> · ${r.label}${r.handler ? ` · ${r.handler}` : ""}</span></li>`;
  return html`<section class="gui-section">
    ${incoming.length > 0 && html`<h3 class="ok-font-heading">Roads in</h3>
      <ul class="gui-rows">${incoming.map((r) => row(r, r.from))}</ul>`}
    ${outgoing.length > 0 && html`<h3 class="ok-font-heading">Roads out</h3>
      <ul class="gui-rows">${outgoing.map((r) => row(r, r.to))}</ul>`}
  </section>`;
}

function Garrison({ garrison }) {
  if (!garrison.length) return null;
  return html`<section class="gui-section">
    <h3 class="ok-font-heading">Garrison</h3>
    <ul class="gui-rows">${garrison.map((o) => html`<li key=${o.name}>
      <span class="ok-font-label">${o.name}</span>
      ${o.scheme && html` <span class="gui-scheme">${o.scheme}</span>`}
      <span class="ok-font-status ok-tone-muted"> · ${o.lead ? "steward" : o.tier || o.kind} · ${o.status}</span>
      ${o.role && html`<div class="ok-font-status ok-tone-muted">${o.role}</div>`}
    </li>`)}</ul>
  </section>`;
}

function Body({ b, t }) {
  return html`<div class="ok-win__body gui-win__body">
    ${b.alert && html`<p class="ok-font-body ok-tone-fire">${b.alert.title}</p>`}
    ${b.status_plain.length > 0 && html`<section class="gui-section">
      ${b.status_plain.map((line, i) => html`<div key=${i} class="ok-font-status">${line}</div>`)}</section>`}
    ${!b.has_worker && html`<p class="ok-font-status ok-tone-muted">
      This building's own view is not in the window yet; it works in the TUI meanwhile.</p>`}
    <${Garrison} garrison=${b.garrison} />
    <${Roads} b=${b} t=${t} />
  </div>`;
}

export function Windows() {
  const t = town.value;
  const o = opened.value;
  const byId = Object.fromEntries(t.buildings.map((b) => [b.id, b]));
  const ids = o.ids.filter((id) => byId[id]);
  if (!ids.length) return null;
  const b = byId[o.active] || byId[ids[0]];
  const hot = b.alert && b.alert.waited >= 30;
  return html`<section class=${cls("gui-group", { "is-max": o.max })}>
    <div class="ok-tabs gui-tabs">
      ${ids.map((id) => html`<span key=${id} class=${cls("ok-tab", { "is-active": id === b.id })}
          onClick=${() => { opened.value = { ...o, active: id }; }}>
        ${byId[id].title}${byId[id].alert ? html` <span class="ok-word">?</span>` : ""}
        <button class="gui-tab__close" title="Close" aria-label="Close"
          onClick=${(e) => { e.stopPropagation(); closeBuilding(id); }}>×</button>
      </span>`)}
    </div>
    <div class=${cls("ok-win is-active gui-win", { "is-alert": !!b.alert, "is-hot": hot })}>
      <div class="ok-head is-banner"></div>
      <div class="ok-win__frame">
        <div class="ok-win__bar" onDblClick=${toggleMax}>
          <span class="ok-win__title">${b.title}</span>
          <${Badge} garrison=${b.garrison} alert=${b.alert} />
        </div>
        <${Body} b=${b} t=${t} />
      </div>
    </div>
  </section>`;
}
