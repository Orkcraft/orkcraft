// 🚏 Signpost (docs/design/building-views.md §3). Closed: how many carts it routed, a counter per road
// out in its road's colour (the town paints the start of each road the same: `card.tints`) and the last
// cart. Open, made for the half panel: the rules one per line (first match wins) with a change asked of
// the steward in plain words folded under them, one line to test where a text would go, and the carts
// that came by as one-line rows filtered by route; a cart opens over the rows (← back). The routing is
// the worker's (core/workers/signpost.py).
import { signal } from "@preact/signals";
import { useState } from "preact/hooks";
import { html, cls } from "../html.js";
import { act, say } from "../link.js";
import { askKeeper } from "../keeper.js";
import { openInLake } from "../lake.js";

const sheet = new URL("./signpost.css", import.meta.url).href;
if (!document.querySelector(`link[href="${sheet}"]`)) {
  const link = document.createElement("link");
  link.rel = "stylesheet";
  link.href = sheet;
  document.head.appendChild(link);
}

const filter = signal({});          // building id → the route the history shows ("*" every one, "" no rule)
const chosen = signal({});          // building id → the index of the cart open over the rows

const MARKS = new Set(["blue", "green", "purple", "yellow", "red"]);
const mark = (c) => (MARKS.has(c) ? `color: var(--mark-${c})` : "");
const when = (at) => (at || "").slice(11, 16);
/** A time as a card says it: today's as 09:21, an older one as 10-06. */
function stamp(at) {
  if (!at) return "";
  const d = new Date();
  const today = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
  return at.slice(0, 10) === today ? at.slice(11, 16) : at.slice(5, 10);
}

function Swatch({ color }) {
  return html`<span class="gui-sign__swatch" aria-hidden="true" style=${mark(color)}>■</span>`;
}

function Route({ data, route }) {
  if (!route) return html`<span class="ok-tone-wait">⚠ ${say("no rule")}</span>`;
  return html`<span style=${mark(data.colors[route])}>${route}</span>`;
}

// -- closed ----------------------------------------------------------------------------------------------

/** Closed: the headline is how many carts it routed; under it a counter per road out in its colour; the
 *  foot the last cart and where it went. With no road out, the headline says so and what to do. */
export function card(b) {
  const c = b.card;
  if (!c) return null;
  const last = c.last && html`<div class="gui-hut__foot"><span>→ ${c.last.route
      ? html`<b>${c.last.route}</b>` : html`<span class="ok-tone-wait">${say("no rule")}</span>`} · ${c.last.title}</span>
    <span class="gui-hut__when">${stamp(c.last.at)}</span></div>`;
  if (!c.roads.length) {
    return html`<div class="gui-hut__body-in">
      ${c.rules
        ? html`<div class="gui-hut__big">${c.rules}<small>${say(`rule${c.rules === 1 ? "" : "s"}, no road out`)}</small></div>
          <div class="gui-hut__text ok-tone-muted">${say("Lay a road from it: each rule sends its carts down one")}</div>`
        : html`<div class="gui-hut__big">${say("No rules")}<small>${say("yet")}</small></div>
          <div class="gui-hut__text ok-tone-muted">${say("Open it and ask its steward for them")}</div>`}
      ${last}
    </div>`;
  }
  const unmatched = c.roads.filter((r) => r.unmatched).reduce((n, r) => n + r.count, 0);
  return html`<div class="gui-hut__body-in">
    <div class="gui-hut__big">${c.total ?? 0}<small>${say("carts routed")}${unmatched ? html` · <span class="ok-tone-wait">⚠ ${unmatched} ${say("no rule")}</span>` : ""}</small></div>
    <div class="gui-hut__text gui-sign__roads" title=${c.roads.map((r) => `${say(r.label)} ${r.count}`).join(" · ")}>
      ${c.roads.map((r) => html`<span key=${r.key} class="gui-sign__road">
        <${Swatch} color=${r.color} /> <span class=${r.unmatched ? "ok-tone-wait" : "ok-tone-muted"}>${say(r.label)}</span> <b>${r.count}</b></span>`)}</div>
    ${last}
  </div>`;
}

// -- open: the rules, the test, the carts ------------------------------------------------------------------

/** The change asked of the steward: folded to one line under the rules — the rules change rarely. */
function KeeperAsk({ id }) {
  const [request, setRequest] = useState("");
  const ask = () => askKeeper(id, request).then((r) => { if (r !== null) setRequest(""); });
  return html`<details class="gui-sign__fold">
    <summary>${say("Change the rules — ask the steward in plain words")}</summary>
    <div class="gui-sign__line">
      <textarea class=${cls("ok-input gui-textarea", { "has-text": !!request })} rows="1" value=${request}
        aria-label=${say("What should go where")}
        placeholder=${say("“bug reports to bugs, links to reading, the rest to inbox”")}
        onInput=${(e) => setRequest(e.target.value)}
        onKeyDown=${(e) => { if (e.key === "Enter" && (e.ctrlKey || e.metaKey) && request.trim()) { e.preventDefault(); ask(); } }}></textarea>
      <button class="ok-btn" disabled=${!request.trim()} onClick=${ask}>${say("Ask the steward")}</button>
    </div>
  </details>`;
}

function RulesPane({ id, data }) {
  return html`<div class="gui-sign__rules">
    ${data.rules.length
      ? html`<ol class="gui-sign__list">${data.rules.map((r, n) => html`<li key=${n} title=${r}>
          <span class="gui-sign__n">${n + 1}</span><code>${r}</code></li>`)}</ol>`
      : html`<p class="ok-tone-muted">${say("No rules yet — ask the steward for them below.")}</p>`}
    ${data.problems.map((p) => html`<p key=${p} class="ok-tone-error">✗ ${p}</p>`)}
    <${KeeperAsk} id=${id} />
  </div>`;
}

/** One line: a text pasted, Test, and where it would go beside it. */
function TestBox({ id, data }) {
  const [text, setText] = useState("");
  const [got, setGot] = useState(null);
  const test = () => act(id, "test", { text }).then(setGot, () => {});
  return html`<div class="gui-sign__test">
    <div class="gui-sign__line">
      <textarea class=${cls("ok-input gui-textarea", { "has-text": !!text })} rows="1" value=${text}
        aria-label=${say("A text to test")} placeholder=${say("Test the rules: paste a text — where would it go?")}
        onInput=${(e) => { setText(e.target.value); setGot(null); }}
        onKeyDown=${(e) => { if (e.key === "Enter" && (e.ctrlKey || e.metaKey) && text.trim()) { e.preventDefault(); test(); } }}></textarea>
      <button class="ok-btn" disabled=${!text.trim()} onClick=${test}>Test</button>
    </div>
    ${got && (got.route
      ? html`<p class="gui-sign__got">→ <b><${Route} data=${data} route=${got.route} /></b>
          <span class="ok-tone-muted"> ${say(`by rule ${got.index + 1}`)}: </span><code>${got.rule}</code></p>`
      : html`<p class="gui-sign__got ok-tone-wait">⚠ ${say("No rule matches — it would go out as “no rule”.")}</p>`)}
  </div>`;
}

function Carts({ id, data }) {
  const f = filter.value[id] ?? "*";
  const rows = data.history.map((h, n) => ({ h, n })).filter(({ h }) => f === "*" || h.route === f);
  const pick = (v) => { filter.value = { ...filter.value, [id]: v }; };
  const count = (r) => data.counts[r] || 0;
  const all = Object.values(data.counts).reduce((a, b) => a + b, 0);
  return html`<div class="gui-sign__carts">
    <div class="gui-sign__chips" role="group" aria-label=${say("Show the carts of")}>
      <button class=${cls("ok-chip", { "is-on": f === "*" })} aria-pressed=${f === "*"} onClick=${() => pick("*")}>${say("all")} ${all}</button>
      ${data.routes.map((r) => html`<button key=${r} class=${cls("ok-chip", { "is-on": f === r })} aria-pressed=${f === r} onClick=${() => pick(r)}>
        <${Swatch} color=${data.colors[r]} /> ${r} ${count(r)}</button>`)}
      ${count("") > 0 && html`<button class=${cls("ok-chip", { "is-on": f === "" })} aria-pressed=${f === ""} onClick=${() => pick("")}>⚠ ${say("no rule")} ${count("")}</button>`}
    </div>
    ${rows.length ? html`<ul class="gui-sign__rows">${rows.map(({ h, n }) => html`<li key=${n}>
        <button class="gui-sign__row" onClick=${() => { chosen.value = { ...chosen.value, [id]: n }; }} title=${h.title}>
          <span class="gui-sign__at">${when(h.at)}</span>
          <span class="gui-sign__route">→ <${Route} data=${data} route=${h.route} /></span>
          <span class="gui-sign__what">${h.title}</span>
          <span class="gui-sign__from">${h.source_title}</span></button></li>`)}</ul>`
      : html`<p class="ok-tone-muted">${data.history.length ? say("None on this route yet.") : say("No carts yet — a road brings them here.")}</p>`}
  </div>`;
}

/** A cart open over the rows: ← back, where it came from and went, what it carried. */
function Cart({ id, data, h }) {
  const back = () => { chosen.value = { ...chosen.value, [id]: null }; };
  return html`<div class="gui-sign__cart" onKeyDown=${(e) => { if (e.key === "Escape") { e.stopPropagation(); back(); } }}>
    <button class="ok-btn gui-sign__back" onClick=${back}>← ${say("All carts")} · ${data.history.length}</button>
    <p class="gui-sign__got">→ <b><${Route} data=${data} route=${h.route} /></b> <span>${h.title}</span></p>
    <p class="ok-detail__meta">${h.at.replace("T", " ")} · ${say("from")} <b>${h.source_title || h.source}</b> · ${h.event}</p>
    <div class="ok-detail__actions"><button class="ok-btn" onClick=${() => openInLake({ text: h.value, title: h.title, from: id })}>
      ${say("Open in the Inspector")}</button></div>
    <pre class="gui-pre">${h.value.slice(0, 3000)}</pre>
  </div>`;
}

function HistoryPane({ id, data }) {
  const n = chosen.value[id];
  const h = n === null || n === undefined ? null : data.history[n];
  return h ? html`<${Cart} key=${n} id=${id} data=${data} h=${h} />` : html`<${Carts} id=${id} data=${data} />`;
}

/** The window by its UI document (design/buildings/signpost.json): a cart opens over the rows, in
 *  `history`; `cart` shows nothing of its own (an older document that still has the pane loses nothing). */
export function panes(id, data) {
  return {
    rules: () => html`<${RulesPane} id=${id} data=${data} />`,
    test: () => html`<${TestBox} id=${id} data=${data} />`,
    history: () => html`<${HistoryPane} id=${id} data=${data} />`,
    cart: () => null,
  };
}
