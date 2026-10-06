// 🛠 Workshop: a script that runs on every cart (core/workers/workshop.py runs it). Its runs, the chosen
// one's input, output and result, and Test's log — in a dialog when Test is pressed from the Command
// Card, and in the full window. The script is edited in Lake; its keeper rewrites the script and the
// schedule from plain words (core/keeper.py, docs/design/building-views.md §2).
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
  return html`<li class=${cls("ws-run", { "is-selected": selected, "is-static": !onPick })} onClick=${onPick}>
    <span class=${`ws-run__mark ${tone(r)}`}>${r.mark}</span>
    <span class="ok-tone-muted">${r.time}</span>
    <span class="ws-run__code">exit ${r.code}</span>
    ${test ? html`<span>${r.event}</span>` : r.sent && html`<span>→ ${SENT[r.sent] || r.sent}</span>`}
    ${r.keeper && html`<span class="ok-tone-wait">keeper</span>`}
    <span class="ws-run__what">${firstLine(r.result || r.err)}</span>
  </li>`;
}

function TestLog({ data }) {
  if (!data.tests.length) return html`<p class="ok-tone-muted">${say("Test runs the blueprint's mock carts in the sandbox.")}</p>`;
  const ok = data.tests.filter((r) => r.ok).length;
  return html`<div>
    <p class=${cls("ok-font-status", { "ok-tone-ok": ok === data.tests.length, "ok-tone-error": ok < data.tests.length })}>
      ${ok}/${data.tests.length} mock carts passed · ${String(data.tested_at).slice(11, 19)}</p>
    ${data.tests.map((r, i) => html`<div key=${i}>
      <p class="ws-section"><span class=${tone(r)}>${r.mark}</span> ${r.event} · exit ${r.code} · ${r.ms} ms</p>
      <pre class="ws-pre ok-font-mono ok-tone-muted">in  ${r.input || "—"}</pre>
      <${Result} r=${r} />
    </div>`)}
  </div>`;
}

/** The request to its keeper: the script or the schedule, in plain words. */
function Ask({ id, data, onDone }) {
  const [request, setRequest] = useState("");
  const keeper = data.keeper_name || say("the keeper");
  const send = () => request.trim() && askKeeper(id, request.trim()).then((r) => {
    if (r !== null) { setRequest(""); onDone && onDone(); }
  });
  return html`<div class="ws-ask">
    <textarea class="ok-input gui-textarea" rows="2" value=${request}
      placeholder=${say("In plain words: what the script should do, when it should run on its own…")}
      onInput=${(e) => setRequest(e.target.value)}></textarea>
    <div class="gui-head">
      <button class="ok-act" disabled=${!request.trim()} onClick=${send}><span class="ok-act__label">Ask ${keeper}</span></button>
      <span class="ok-tone-muted">${keeper} writes the script and the schedule; you see the change before it is kept.</span>
    </div>
  </div>`;
}

/** Closed: the last run (✓ / ✗ / → keeper) and its schedule (docs/design/building-views.md). */
export function card(b) {
  const c = b.card;
  if (!c) return null;
  const last = c.running ? html`<span class="ok-tone-wait">${say("running…")}</span>`
    : c.mark ? html`<span><b class=${tone({ outcome: c.outcome })}>${c.mark}</b> <span class="ok-tone-muted">${c.at}</span></span>`
      : html`<span class="ok-tone-muted">${say("waiting for a cart")}</span>`;
  return html`<div class="ws-card">${last}
    <span class="ok-tone-muted">${c.schedule ? `${say("schedule")} ${c.schedule}` : say("no schedule")}</span></div>`;
}

function Head({ id, data }) {
  return html`<div class="gui-head">
    <span class="gui-head__what"><span class="ws-link" title=${say("Edit the script in Lake")}
      onClick=${() => editScript(id, data)}>${data.script}</span>
      <span class="ok-tone-muted"> · ${data.runtime} · layout ${data.layout}${data.schedule ? ` · schedule ${data.schedule}` : ""}
      ${data.keeper ? " · the keeper takes exit 3" : ""}</span>
      ${data.running && html`<span class="ok-tone-wait"> · running…</span>`}</span>
    <span class="gui-head__spacer"></span>
    <button class="ok-act" disabled=${!data.has_cart || data.running} onClick=${() => act(id, "workshop.run").catch(() => {})}>
      <span class="ok-act__label">Run</span></button>
    <button class="ok-act" onClick=${() => act(id, "workshop.test").catch(() => {})}><span class="ok-act__label">Test</span></button>
    <button class="ok-act" onClick=${() => editScript(id, data)}><span class="ok-act__label">Edit the script in Lake</span></button>
  </div>`;
}

function Runs({ id, data }) {
  const at = chosen.value[id] || (data.runs[0] && data.runs[0].at);
  if (!data.runs.length) return html`<p class="ok-tone-muted">${say("No runs yet — a road brings a cart.")}</p>`;
  return html`<ul class="ws-runs">${data.runs.map((r) => html`<${RunRow} key=${r.at} r=${r} selected=${r.at === at}
    onPick=${() => { chosen.value = { ...chosen.value, [id]: r.at }; }} />`)}</ul>`;
}

function Run({ id, data }) {
  const at = chosen.value[id];
  const r = data.runs.find((x) => x.at === at) || data.runs[0];
  if (!r) return html`<p class="ok-tone-muted">${say("Pick a run.")}</p>`;
  return html`<div>
    <p class="ok-font-status"><span class=${tone(r)}>${r.mark}</span> ${r.event} from ${r.source || "—"} · exit ${r.code} · ${r.ms} ms
      ${r.sent && html` · → ${SENT[r.sent] || r.sent}`}</p>
    <p class="ws-section">Input</p><pre class="ws-pre ok-font-mono">${r.input || "—"}</pre>
    <p class="ws-section">Output</p><pre class=${cls("ws-pre ok-font-mono", { "ok-tone-error": !!r.err })}>${[r.result, r.err].filter(Boolean).join("\n") || "—"}</pre>
    ${r.shape && r.shape.kind !== "log" && html`<p class="ws-section">Result</p><${Result} r=${r} />`}
  </div>`;
}

/** Full: the runs, the chosen one's input, output and result, and Test's log. */
export function panes(id, data) {
  return {
    head: () => html`<div><${Head} id=${id} data=${data} /><${Ask} id=${id} data=${data} /></div>`,
    runs: () => html`<${Runs} id=${id} data=${data} />`,
    run: () => html`<${Run} id=${id} data=${data} />`,
    tests: () => html`<${TestLog} data=${data} />`,
  };
}
