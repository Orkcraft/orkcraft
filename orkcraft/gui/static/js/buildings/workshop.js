// 🛠 Workshop: a script that runs on every cart (core/workers/workshop.py runs it). Closed: how the last
// run went, what it said and when, the schedule. Open, made for the half panel: the script on one line with
// Run, Test and Edit; the ask to its keeper as one line that grows; the last run (or the one picked) takes
// the room — its result first, then its input and output; the runs as rows under it; Test's log folded
// to one line. The script is edited in Lake; its keeper rewrites the script and the schedule from plain
// words (core/keeper.py, docs/design/building-views.md §2).
import { signal } from "@preact/signals";
import { useState } from "preact/hooks";
import { html, cls } from "../html.js";
import { act, say } from "../link.js";
import { openInLake } from "../lake.js";
import { askKeeper } from "../keeper.js";

const sheet = new URL("./workshop.css", import.meta.url).href;
if (!document.querySelector(`link[href="${sheet}"]`)) {
  const link = document.createElement("link");
  link.rel = "stylesheet";
  link.href = sheet;
  document.head.appendChild(link);
}

const chosen = signal({});         // building id → the run picked in the full window (its `at`)
const SENT = { "workshop.done": "done", "workshop.alert": "alert", "workshop.failed": "failed" };

const tone = (r) => (r.outcome === "failed" ? "ok-tone-error" : r.outcome === "done" ? "ok-tone-ok" : "ok-tone-wait");
const firstLine = (t) => (t || "").split("\n").find((x) => x.trim()) || "";

function editScript(id, data) {
  openInLake({ path: data.script, title: data.script.split("/").pop(), from: id });
}

/** A run's result as the building's layout says: a table, a card, else its output as a log. */
function Result({ r, cut = false }) {
  const s = r.shape || { kind: "log" };
  if (s.kind === "table") {
    const rows = cut ? s.rows.slice(0, 3) : s.rows;
    const cols = cut ? s.columns.slice(0, 4) : s.columns;
    return html`<table class="ws-table ok-font-status"><thead><tr>${cols.map((c) => html`<th key=${c}>${c}</th>`)}</tr></thead>
      <tbody>${rows.map((row, i) => html`<tr key=${i}>${cols.map((_, j) => html`<td key=${j}>${row[j]}</td>`)}</tr>`)}</tbody></table>
      ${cut && s.rows.length > 3 && html`<span class="ok-tone-muted ok-font-status">+${s.rows.length - 3} rows</span>`}`;
  }
  if (s.kind === "card") {
    const fields = cut ? s.fields.slice(0, 4) : s.fields;
    return html`<dl class="ws-fields">${fields.map(([k, v]) => html`<dt key=${`k${k}`}>${k}</dt><dd key=${`v${k}`}><b>${v}</b></dd>`)}</dl>`;
  }
  const out = (r.result || "") + (r.err ? `${r.result ? "\n" : ""}${r.err}` : "");
  return html`<pre class=${cls("ws-pre ok-font-mono", { "ws-cut": cut, "ok-tone-error": !r.ok })}>${out || "—"}</pre>`;
}

function RunRow({ r, selected, onPick, test = false }) {
  return html`<li class=${cls("ws-run", { "is-selected": selected, "is-static": !onPick })} onClick=${onPick}
      tabIndex=${onPick ? "0" : undefined} onKeyDown=${(e) => onPick && e.key === "Enter" && onPick()}>
    <span class=${`ws-run__mark ${tone(r)}`}>${say(r.mark)}</span>
    <span class="ok-tone-muted">${r.time}</span>
    <span class="ws-run__code">exit ${r.code}</span>
    ${test ? html`<span>${r.event}</span>` : r.sent && html`<span>→ ${SENT[r.sent] || r.sent}</span>`}
    ${r.keeper && html`<span class="ok-tone-wait">steward</span>`}
    <span class="ws-run__what">${firstLine(r.result || r.err)}</span>
  </li>`;
}

/** Test's log: one line — how many mock carts passed — until opened. */
function TestLog({ id, data }) {
  if (!data.tests.length) {
    return html`<p class="ws-none">${say("Test runs the blueprint's mock carts in the sandbox.")}${" "}<button class="ws-quiet" onClick=${() => act(id, "workshop.test").catch(() => {})}>${say("Test now")}</button></p>`;
  }
  const ok = data.tests.filter((r) => r.ok).length;
  const all = ok === data.tests.length;
  return html`<details class="ws-fold">
    <summary><span>${say("Test")}</span>
      <span class=${all ? "ok-tone-ok" : "ok-tone-error"}>${all ? "✓" : "✗"} ${ok}/${data.tests.length} ${say("mock carts passed")}</span>
      <span class="ws-fold__sum">${String(data.tested_at).slice(11, 19)}</span></summary>
    ${data.tests.map((r, i) => html`<div key=${i}>
      <p class="ws-section"><span class=${tone(r)}>${say(r.mark)}</span> ${r.event} · exit ${r.code} · ${r.ms} ms</p>
      <pre class="ws-pre ok-font-mono ok-tone-muted">in  ${r.input || "—"}</pre>
      <${Result} r=${r} />
    </div>`)}
  </details>`;
}

/** The request to its keeper: the script or the schedule, in plain words. */
function Ask({ id, data, onDone }) {
  const [request, setRequest] = useState("");
  const keeper = data.keeper_name || say("the keeper");
  const send = () => request.trim() && askKeeper(id, request.trim()).then((r) => {
    if (r !== null) { setRequest(""); onDone && onDone(); }
  });
  const keys = (e) => { if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) { e.preventDefault(); send(); } };
  return html`<div class="ws-ask">
    <textarea class=${cls("ok-input gui-textarea", { "has-text": !!request })} rows="1" value=${request} aria-label=${say(`Ask ${keeper}`)}
      placeholder=${say("In plain words: what the script should do, when it runs on its own")}
      title=${say(`${keeper} writes the script and the schedule; you see the change before it is kept.`)}
      onInput=${(e) => setRequest(e.target.value)} onKeyDown=${keys}></textarea>
    <button class="ok-btn" disabled=${!request.trim()} onClick=${send}>${say(`Ask ${keeper}`)}</button>
  </div>`;
}

const BIG = { done: ["✓", "Ran", "ok-tone-ok"], alert: ["!", "Alert", "ok-tone-wait"], escalated: ["→", "To the keeper", "ok-tone-wait"],
              failed: ["✗", "Failed", "ok-tone-error"] };

/** Closed: the headline is how the last run went (`✓ Ran`, `✗ Failed`), running meanwhile; under it the schedule;
 *  the foot what the last run said and when (docs/design/building-views.md). */
export function card(b) {
  const c = b.card;
  if (!c) return null;
  const [mark, word, tn] = BIG[c.outcome] || ["✗", "Failed", "ok-tone-error"];
  return html`<div class="gui-hut__body-in">
    ${c.running ? html`<div class="gui-hut__big ok-tone-wait">… ${say("Running")}<small>${say("on the last cart")}</small></div>`
      : c.mark ? html`<div class=${`gui-hut__big ${tn}`}>${mark} ${say(word)}<small>${c.runs} ${say(c.runs === 1 ? "run" : "runs")}</small></div>`
      : html`<div class="gui-hut__big">${say("Waits")}<small>${say("a road brings a cart to run on")}</small></div>`}
    <div class="gui-hut__text">${c.schedule ? html`${say("runs")} <b>${c.schedule}</b> ${say("and on each cart")}` : say("runs on each cart a road brings")}</div>
    ${c.mark && html`<div class="gui-hut__foot"><span class="ws-card__said">${c.said || say("(no output)")}</span>
      <span class="gui-hut__when">${c.at}</span></div>`}
  </div>`;
}

function Head({ id, data }) {
  const name = data.script.split("/").pop();
  return html`<div>
    <div class="ws-head">
      <button class="ws-script" title=${`${data.script} — ${say("edit the script in Lake")}`} onClick=${() => editScript(id, data)}>${name}</button>
      <span>${data.runtime}</span>
      <span>${data.schedule ? html`${say("runs")} <b>${data.schedule}</b>` : say("on each cart")}</span>
      <span>${say("shows a")} <b>${data.layout}</b></span>
      ${data.keeper && html`<span title=${say("exit 3 hands the cart to the keeper")}>${say("exit 3 → keeper")}</span>`}
      ${data.running && html`<span class="ok-tone-wait">${say("running…")}</span>`}
      <span class="gui-head__spacer"></span>
      <button class="ok-btn" onClick=${() => editScript(id, data)}>${say("Edit in Lake")}</button>
      <button class="ok-btn" onClick=${() => act(id, "workshop.test").catch(() => {})}>Test</button>
      <button class="ok-btn primary" disabled=${!data.has_cart || data.running} title=${data.has_cart ? say("Run it again on the last cart") : say("No cart yet")}
        onClick=${() => act(id, "workshop.run").catch(() => {})}>Run</button>
    </div>
    <${Ask} id=${id} data=${data} />
  </div>`;
}

function Runs({ id, data }) {
  const at = chosen.value[id] || (data.runs[0] && data.runs[0].at);
  if (!data.runs.length) return null;
  return html`<ul class="ws-runs" aria-label=${say("Runs")}>${data.runs.map((r) => html`<${RunRow} key=${r.at} r=${r} selected=${r.at === at}
    onPick=${() => { chosen.value = { ...chosen.value, [id]: r.at }; }} />`)}</ul>`;
}

function Run({ id, data }) {
  const at = chosen.value[id];
  const r = data.runs.find((x) => x.at === at) || data.runs[0];
  if (!r) return html`<p class="ok-tone-muted">${say("No runs yet — a road brings a cart, or Test runs the mock ones.")}</p>`;
  const latest = r === data.runs[0];
  const shaped = r.shape && r.shape.kind !== "log";
  return html`<div class="ws-run-open">
    <p class="ws-run-open__head ok-font-status"><b class=${tone(r)}>${say(r.mark)}</b>
      <span>${latest ? say("Last run") : say("Run")} · ${r.time}</span>
      <span class="ok-tone-muted">${r.event} ${say("from")} ${r.source || "—"} · exit ${r.code} · ${r.ms} ms${r.sent ? ` · → ${SENT[r.sent] || r.sent}` : ""}</span>
      <span class="gui-head__spacer"></span>
      ${!latest && html`<button class="ws-quiet" onClick=${() => { chosen.value = { ...chosen.value, [id]: null }; }}>${say("Back to the last run")}</button>`}</p>
    ${shaped && html`<div class="ws-result"><${Result} r=${r} /></div>`}
    <div class="ws-io">
      <div><p class="ws-section">Input</p><pre class="ws-pre ok-font-mono">${r.input || "—"}</pre></div>
      <div><p class="ws-section">Output</p><pre class=${cls("ws-pre ok-font-mono", { "ok-tone-error": !!r.err })}>${[r.result, r.err].filter(Boolean).join("\n") || "—"}</pre></div>
    </div>
  </div>`;
}

/** The window by its UI document (design/buildings/workshop.json): the last run (or the one picked) takes the
 *  room, the runs as rows under it, Test's log folded. */
export function panes(id, data) {
  return {
    head: () => html`<${Head} id=${id} data=${data} />`,
    runs: () => (data.runs.length ? html`<${Runs} id=${id} data=${data} />` : null),
    run: () => html`<${Run} id=${id} data=${data} />`,
    tests: () => html`<${TestLog} id=${id} data=${data} />`,
  };
}
