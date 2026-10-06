// ⚙️ The Mill (docs/design/building-views.md §3): closed, the last run's state and time; command, the
// steps as a chain (the failing one marked), the last runs, Edit steps (Run is its quick action); full,
// the steps, for a chosen run its input and what every step made of it, the runs with their costs and
// the queue. The milling is the worker's (core/workers/mill.py).
import { signal } from "@preact/signals";
import { useState } from "preact/hooks";
import { html, cls } from "../html.js";
import { act, say } from "../link.js";
import { Dialog } from "../dialog.js";
import { openInLake } from "../lake.js";

const chosen = signal({});          // building id → the run shown in full

const when = (at) => (at || "").slice(11, 16);
const day = (at) => (at || "").slice(5, 16).replace("T", " ");
const money = (usd) => (usd ? `$${usd < 0.01 ? usd.toFixed(4) : usd.toFixed(2)}` : "");

// -- closed --------------------------------------------------------------------------------------------------

export function card(b) {
  const c = b.card;
  if (!c) return null;
  if (c.state === "running") {
    return html`<span class="ok-tone-wait">running… ${when(c.at)}${c.queue ? ` · ${c.queue} waiting` : ""}</span>`;
  }
  if (c.state === "none") {
    return html`<span class="ok-tone-muted">no runs yet · ${c.steps} step${c.steps === 1 ? "" : "s"}</span>`;
  }
  return c.state === "ok"
    ? html`<span><span class="ok-tone-ok">last run ok</span> <span class="ok-tone-muted">${when(c.at)}</span></span>`
    : html`<span><span class="ok-tone-error">last run failed</span> <span class="ok-tone-muted">${when(c.at)}</span></span>`;
}

// -- the steps ----------------------------------------------------------------------------------------------

function Chain({ data }) {
  if (!data.steps.length) return html`<p class="ok-tone-muted">No steps yet — Edit steps.</p>`;
  return html`<div class="gui-counters ok-font-mono">${data.steps.map((s, n) => html`<span key=${n} class="gui-counter">
    ${n > 0 && html`<span class="ok-tone-muted">→ </span>`}<span class=${cls("ok-chip", { "ok-tone-error": data.failed === n + 1 })}
      title=${data.failed === n + 1 ? say("The last run failed here") : ""}>${s}</span></span>`)}</div>
  ${data.problems.map((p) => html`<p key=${p} class="ok-tone-error">${p}</p>`)}`;
}

function StepsDialog({ id, data, onClose }) {
  const [steps, setSteps] = useState(data.steps.join("\n"));
  const keep = () => act(id, "set_steps", { steps }).then(onClose, () => {});
  return html`<${Dialog} title="The Mill — steps, one per line" onCancel=${onClose}
      actions=${html`<button class="ok-btn" onClick=${onClose}>Cancel</button>
        <button class="ok-btn primary" onClick=${keep}>Keep them</button>`}>
    <textarea class="ok-input gui-textarea ok-font-mono" rows="8" value=${steps} autofocus
      onInput=${(e) => setSteps(e.target.value)}></textarea>
    <p class="ok-dialog__hint ok-font-status ok-tone-muted">${data.help}</p>
  </${Dialog}>`;
}

/** Run and Edit steps (`run` false: Run is left out). */
function Acts({ id, data, run = true }) {
  const [editing, setEditing] = useState(false);
  return html`<div class="gui-head">
    ${run && html`<button class="ok-act" disabled=${!data.has_input} title=${say(data.has_input ? "The steps again on the last input" : "Nothing has arrived yet")}
      onClick=${() => act(id, "run").catch(() => {})}><span class="ok-act__label">Run</span></button>`}
    <button class="ok-act" onClick=${() => setEditing(true)}><span class="ok-act__label">Edit steps</span></button>
    ${data.running && html`<span class="ok-tone-wait">running…${data.queue.length ? ` ${data.queue.length} waiting` : ""}</span>`}
    ${editing && html`<${StepsDialog} id=${id} data=${data} onClose=${() => setEditing(false)} />`}
  </div>`;
}

// -- the runs -----------------------------------------------------------------------------------------------

function RunRow({ r, onClick, selected = false, full = false }) {
  return html`<li class=${cls("ok-item", { "is-selected": selected })} onClick=${onClick}>
    <span class=${r.ok ? "ok-tone-ok" : "ok-tone-error"}>${r.ok ? "ok" : "failed"}</span>
    <span class="ok-tone-muted">${full ? day(r.started) : when(r.started)}</span>
    ${full && html`<span class="ok-tone-muted">${r.trigger}</span>`}
    <span class="gui-head__what">${r.result.replace(/\n/g, " ⏎ ").slice(0, 120)}</span>
    <span class="meta">${r.cost ? money(r.cost) : r.agent ? say("an agent") : ""}</span>
  </li>`;
}

// -- full ---------------------------------------------------------------------------------------------------

function RunsPane({ id, data }) {
  const sel = chosen.value[id] || (data.runs[0] && data.runs[0].id);
  if (!data.runs.length) return html`<p class="ok-tone-muted">No runs yet — a road brings the input.</p>`;
  return html`<div>
    <p class="ok-font-status ok-tone-muted">${data.runs.length} run${data.runs.length === 1 ? "" : "s"}${data.spent ? html` · agents spent <b>${money(data.spent)}</b>` : ""}</p>
    <ul class="ok-list__items gui-rows">${data.runs.map((r) => html`<${RunRow} key=${r.id} r=${r} full selected=${r.id === sel}
      onClick=${() => { chosen.value = { ...chosen.value, [id]: r.id }; }} />`)}</ul></div>`;
}

function Text({ text }) {
  return html`<pre class="ok-font-mono" style="white-space: pre-wrap; margin: 0">${text}</pre>`;
}

function RunPane({ id, data }) {
  const r = data.runs.find((x) => x.id === chosen.value[id]) || data.runs[0];
  if (!r) return html`<p class="ok-tone-muted">Pick a run.</p>`;
  const steps = r.steps || [];
  return html`<div class="ok-detail">
    <p class="ok-detail__meta">${day(r.started)} · ${r.trigger} · ${r.title}
      ${r.cost ? html` · <b>${money(r.cost)}</b>` : ""}${r.agent ? ` · an agent did ${r.agent} step${r.agent === 1 ? "" : "s"}` : ""}
      ${r.items ? ` · ${r.items} record${r.items === 1 ? "" : "s"} went out one by one` : ""}</p>
    <div class="ok-detail__actions">
      <button class="ok-act" onClick=${() => openInLake({ text: r.input, title: `${r.title} — input`, from: id })}>
        <span class="ok-act__label">Input in Lake</span></button>
      <button class="ok-act" onClick=${() => openInLake({ text: r.ok ? r.result : r.error, title: r.title, from: id })}>
        <span class="ok-act__label">Result in Lake</span></button></div>
    <p class="ok-detail__section">Input${r.cut ? " (cut to 256 KB)" : ""}</p>
    <${Text} text=${r.input} />
    ${steps.length ? steps.map((s, n) => html`<div key=${n}>
        <p class=${cls("ok-detail__section", { "ok-tone-error": !!s.error })}>${n + 1} · <span class="ok-font-mono">${s.step}</span></p>
        ${s.error ? html`<p class="ok-tone-error">${s.error}</p>` : html`<${Text} text=${s.out} />`}</div>`)
      : html`<p class="ok-detail__section">Output</p>
        ${r.ok ? html`<${Text} text=${r.result} />` : html`<p class="ok-tone-error">${r.error}</p>`}
        <p class="ok-tone-muted">This run was kept before the Mill kept every step.</p>`}
  </div>`;
}

function QueuePane({ data }) {
  return html`<div class="ok-font-status">
    ${data.current && html`<p><span class="ok-tone-wait">milling</span> ${data.current.title} <span class="ok-tone-muted">since ${when(data.current.started)}</span></p>`}
    ${data.queue.length > 0 && html`<p class="ok-tone-muted">${data.queue.length} waiting:</p>
      <ul class="gui-rows">${data.queue.slice(0, 10).map((q, n) => html`<li key=${n}>${q.title}
        <span class="ok-tone-muted">· ${q.trigger} · ${q.size} chars</span></li>`)}</ul>`}
  </div>`;
}

export function panes(id, data) {
  return {
    steps: () => html`<div><${Chain} data=${data} /><${Acts} id=${id} data=${data} /></div>`,
    runs: () => html`<${RunsPane} id=${id} data=${data} />`,
    run: () => html`<${RunPane} id=${id} data=${data} />`,
    queue: () => (data.running || data.queue.length ? html`<${QueuePane} data=${data} />` : null),   // only while it mills
  };
}
