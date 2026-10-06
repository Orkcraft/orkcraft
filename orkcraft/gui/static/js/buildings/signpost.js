// 🚏 Signpost (docs/design/building-views.md §3): closed, a counter per road out in its road's colour
// (the town paints the start of each road the same: `card.tints`); command, the rules one per line, the
// last carts (the unmatched marked), Test and a request to the keeper; full, no editor — the keeper
// writes the rules from plain words — a test of the rules on an example and the carts filtered by route.
// The routing is the worker's (core/workers/signpost.py).
import { signal } from "@preact/signals";
import { useState } from "preact/hooks";
import { html, cls } from "../html.js";
import { act, say } from "../link.js";
import { askKeeper } from "../keeper.js";
import { openInLake } from "../lake.js";

const filter = signal({});          // building id → the route the history shows ("*" every one, "" no rule)
const chosen = signal({});          // building id → the index of the cart shown

const MARKS = new Set(["blue", "green", "purple", "yellow", "red"]);
const mark = (c) => (MARKS.has(c) ? `color: var(--mark-${c})` : "");
const when = (at) => (at || "").slice(11, 16);

function Swatch({ color }) {
  return html`<span aria-hidden="true" style=${mark(color)}>■</span>`;
}

function Route({ data, route }) {
  const c = data.colors[route];
  if (!route) return html`<span class="ok-tone-wait">no rule</span>`;
  return html`<span style=${mark(c)}>${route}</span>`;
}

// -- closed ----------------------------------------------------------------------------------------------

export function card(b) {
  const c = b.card;
  if (!c) return null;
  if (!c.roads.length) {
    return html`<span class="ok-tone-muted">${c.rules ? `${c.rules} rule${c.rules === 1 ? "" : "s"} · no roads out` : "no rules yet"}</span>`;
  }
  return html`<div class="gui-counters">${c.roads.map((r) => html`<span key=${r.key} class="gui-counter" title=${r.label}>
    <${Swatch} color=${r.color} /> <span class=${r.unmatched ? "ok-tone-wait" : "ok-tone-muted"}>${say(r.label)}</span>${" "}<b>${r.count}</b></span>`)}</div>`;
}

// -- the dialogs: Test and the keeper ----------------------------------------------------------------------

function TestBox({ id, data }) {
  const [text, setText] = useState("");
  const [got, setGot] = useState(null);
  const test = () => act(id, "test", { text }).then(setGot, () => {});
  return html`<div class="gui-signpost__test">
    <textarea class="ok-input gui-textarea" rows="3" placeholder=${say("Paste a text: where would it go?")} value=${text}
      onInput=${(e) => { setText(e.target.value); setGot(null); }}></textarea>
    <div class="gui-head">
      <button class="ok-act" disabled=${!text.trim()} onClick=${test}><span class="ok-act__label">Test</span></button>
      ${got && (got.route
        ? html`<span>→ <b><${Route} data=${data} route=${got.route} /></b>
            <span class="ok-tone-muted"> by rule ${got.index + 1}: </span><code class="ok-font-mono">${got.rule}</code></span>`
        : html`<span class="ok-tone-wait">No rule matches — it would go out as “no rule”.</span>`)}
    </div>
  </div>`;
}

function KeeperBox({ id, onDone }) {
  const [request, setRequest] = useState("");
  const ask = () => askKeeper(id, request).then((r) => { if (r !== null) { setRequest(""); onDone && onDone(); } });
  return html`<div>
    <textarea class="ok-input gui-textarea" rows="3" value=${request}
      placeholder=${say("Say in plain words where things should go: “bug reports to bugs, links to reading, the rest to inbox”")}
      onInput=${(e) => setRequest(e.target.value)}></textarea>
    <div class="gui-head"><button class="ok-act" disabled=${!request.trim()} onClick=${ask}>
      <span class="ok-act__label">Ask the keeper</span></button>
      <span class="ok-tone-muted">The keeper writes the rules; you see them here and test them.</span></div>
  </div>`;
}

// -- command -----------------------------------------------------------------------------------------------

function Rules({ data, max = 0 }) {
  const rules = max ? data.rules.slice(0, max) : data.rules;
  if (!data.rules.length) return html`<p class="ok-tone-muted">No rules yet — ask the keeper for them.</p>`;
  return html`<ol class="gui-rows ok-font-mono">
    ${rules.map((r, n) => html`<li key=${n}><span class="ok-tone-muted">${n + 1}</span> ${r}</li>`)}
    ${max > 0 && data.rules.length > max && html`<li class="ok-tone-muted">${data.rules.length - max} more</li>`}
  </ol>
  ${data.problems.map((p) => html`<p key=${p} class="ok-tone-error">${p}</p>`)}`;
}

function Carts({ id, data, rows, onPick, sel = -1 }) {
  if (!rows.length) return html`<p class="ok-tone-muted">No carts yet.</p>`;
  return html`<ul class="ok-list__items gui-rows">${rows.map(({ h, n }) => html`<li key=${n}
      class=${cls("ok-item", { "is-selected": n === sel })} onClick=${() => onPick(n)}>
    <span class="ok-tone-muted">${when(h.at)}</span> → <${Route} data=${data} route=${h.route} />
    <span class="gui-head__what">${h.title}</span><span class="meta">${h.source_title}</span></li>`)}</ul>`;
}

// -- full ------------------------------------------------------------------------------------------------------

function RulesPane({ id, data }) {
  return html`<div>
    <${Rules} data=${data} />
    <${KeeperBox} id=${id} />
  </div>`;
}

function HistoryPane({ id, data }) {
  const f = filter.value[id] ?? "*";
  const rows = data.history.map((h, n) => ({ h, n })).filter(({ h }) => f === "*" || h.route === f);
  const pick = (v) => { filter.value = { ...filter.value, [id]: v }; };
  const count = (r) => data.counts[r] || 0;
  return html`<div>
    <div class="gui-head">
      <button class=${cls("ok-chip", { "is-on": f === "*" })} onClick=${() => pick("*")}>every route</button>
      ${data.routes.map((r) => html`<button key=${r} class=${cls("ok-chip", { "is-on": f === r })} onClick=${() => pick(r)}>
        <${Swatch} color=${data.colors[r]} /> ${r} ${count(r)}</button>`)}
      <button class=${cls("ok-chip", { "is-on": f === "" })} onClick=${() => pick("")}>no rule ${count("")}</button>
    </div>
    <${Carts} id=${id} data=${data} rows=${rows} sel=${chosen.value[id] ?? -1}
      onPick=${(n) => { chosen.value = { ...chosen.value, [id]: n }; }} />
  </div>`;
}

function CartPane({ id, data }) {
  const h = data.history[chosen.value[id] ?? 0];
  if (!h) return html`<p class="ok-tone-muted">Pick a cart.</p>`;
  return html`<div class="ok-detail">
    <p class="ok-detail__meta">${h.at.replace("T", " ")} · from <b>${h.source_title || h.source}</b> · ${h.event}</p>
    <p>→ <${Route} data=${data} route=${h.route} /> <span class="ok-tone-muted">${h.title}</span></p>
    <div class="ok-detail__actions"><button class="ok-act" onClick=${() => openInLake({ text: h.value, title: h.title, from: id })}>
      <span class="ok-act__label">Open in Lake</span></button></div>
    <pre class="ok-font-mono" style="white-space: pre-wrap; margin: 0">${h.value.slice(0, 3000)}</pre>
  </div>`;
}

export function panes(id, data) {
  return {
    rules: () => html`<${RulesPane} id=${id} data=${data} />`,
    test: () => html`<${TestBox} id=${id} data=${data} />`,
    history: () => html`<${HistoryPane} id=${id} data=${data} />`,
    cart: () => html`<${CartPane} id=${id} data=${data} />`,
  };
}
