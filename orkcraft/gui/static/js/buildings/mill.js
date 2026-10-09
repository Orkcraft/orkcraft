// ⚙️ The Mill (docs/design/building-views.md §3). Closed: how the last run went (✓ Ran, ✗ Failed at step
// k, Milling…) with its first line and time. Open, made for the half panel: the steps as a chain (the
// failing one marked) with Run and Edit steps beside it, the runs as one-line rows, newest first; a run
// opens over the rows (← back) with its input and what every step made of it; the queue shows only while
// it mills. The milling is the worker's (core/workers/mill.py).
import { signal } from "@preact/signals";
import { useState } from "preact/hooks";
import { html, cls } from "../html.js";
import { act, say } from "../link.js";
import { Dialog } from "../dialog.js";
import { openInLake } from "../lake.js";

const sheet = new URL("./mill.css", import.meta.url).href;
if (!document.querySelector(`link[href="${sheet}"]`)) {
  const link = document.createElement("link");
  link.rel = "stylesheet";
  link.href = sheet;
  document.head.appendChild(link);
}

const chosen = signal({});          // building id → the run open over the rows

const when = (at) => (at || "").slice(11, 16);
const day = (at) => (at || "").slice(5, 16).replace("T", " ");
const money = (usd) => (usd ? `$${usd < 0.01 ? usd.toFixed(4) : usd.toFixed(2)}` : "");
const plural = (n, word) => `${n} ${word}${n === 1 ? "" : "s"}`;
/** A time as a card says it: today's as 09:21, an older one as 10-06. */
function stamp(at) {
  if (!at) return "";
  const d = new Date();
  const today = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
  return at.slice(0, 10) === today ? at.slice(11, 16) : at.slice(5, 10);
}

// -- closed --------------------------------------------------------------------------------------------------

/** Closed: the headline says how the last run went; under it the steps and runs; the foot its first line
 *  (the error, failed) and when. */
/** No view of its own: in Camp it stands with no card, its house and its name alone (js/hut.js bareOf). */
export const bare = true;

export function card(b) {
  const c = b.card;
  if (!c) return null;
  const counts = html`<div class="gui-hut__text ok-tone-muted"><b>${c.steps ?? 0}</b> ${say(c.steps === 1 ? "step" : "steps")} · <b>${c.runs ?? 0}</b> ${say(c.runs === 1 ? "run" : "runs")}</div>`;
  if (c.state === "running") {
    return html`<div class="gui-hut__body-in">
      <div class="gui-hut__big ok-tone-wait">${say("Milling…")}<small>${c.queue ? `${c.queue} ${say("waiting")}` : say("since")} ${!c.queue ? when(c.at) : ""}</small></div>
      ${counts}
      ${c.title && html`<div class="gui-hut__foot"><span>${c.title}</span><span class="gui-hut__when">${stamp(c.at)}</span></div>`}
    </div>`;
  }
  if (c.state === "none") {
    return html`<div class="gui-hut__body-in">
      <div class="gui-hut__big">${say("Ready")}<small>${say("no runs yet")}</small></div>
      ${counts}
      <div class="gui-hut__text ok-tone-muted">${say(c.steps ? "It runs when a road brings a cart" : "Open it and set its steps")}</div>
    </div>`;
  }
  const ok = c.state === "ok";
  return html`<div class="gui-hut__body-in">
    ${ok ? html`<div class="gui-hut__big ok-tone-ok">✓ ${say("Ran")}<small>${say("the last run")}</small></div>`
      : html`<div class="gui-hut__big ok-tone-error">✗ ${say("Failed")}<small>${c.failed ? say(`at step ${c.failed} of ${c.steps}`) : say("the last run")}</small></div>`}
    ${counts}
    <div class="gui-hut__foot"><span class=${ok ? "" : "ok-tone-error"}>${c.line || say(ok ? "nothing came out" : "no error kept")}</span>
      <span class="gui-hut__when">${stamp(c.at)}</span></div>
  </div>`;
}

/** Folded: the last run's state in a word, as its card's headline says it. */
export function mark(b) {
  const c = b.card;
  if (!c) return null;
  if (c.state === "running") return { text: "milling", tone: "wait" };
  if (c.state === "failed") return { text: "failed", tone: "error" };
  if (c.state === "none") return { text: c.steps ? "no runs yet" : "no steps yet" };
  return { text: plural(c.runs ?? 0, "run") };
}

// -- open: the steps, Run, Edit steps ------------------------------------------------------------------------

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

/** The steps as a chain, the one the last run failed at marked; Run and Edit steps beside it. */
function Steps({ id, data }) {
  const [editing, setEditing] = useState(false);
  return html`<div class="gui-mill__head">
    <div class="gui-mill__chain">
      ${data.steps.length ? data.steps.map((s, n) => html`<span key=${n} class="gui-mill__link">
          ${n > 0 && html`<span class="gui-mill__arrow" aria-hidden="true">→</span>`}
          <span class=${cls("gui-mill__step", { "is-failed": data.failed === n + 1 })} title=${data.failed === n + 1 ? say(`The last run failed here: ${s}`) : s}>
            ${data.failed === n + 1 ? "✗ " : ""}${s}</span></span>`)
        : html`<span class="ok-tone-muted">${say("No steps yet — Edit steps says what to do with what arrives.")}</span>`}
    </div>
    <div class="gui-mill__acts">
      ${data.running && html`<span class="ok-tone-wait">${say("milling…")}${data.queue.length ? ` ${data.queue.length} ${say("waiting")}` : ""}</span>`}
      <button class="ok-btn primary" disabled=${!data.has_input} title=${say(data.has_input ? "The steps again on the last input" : "Nothing has arrived yet")}
        onClick=${() => act(id, "run").catch(() => {})}>Run</button>
      <button class="ok-btn" onClick=${() => setEditing(true)}>${say("Edit steps")}</button>
    </div>
    ${data.problems.map((p) => html`<p key=${p} class="gui-mill__problem ok-tone-error">✗ ${p}</p>`)}
    ${editing && html`<${StepsDialog} id=${id} data=${data} onClose=${() => setEditing(false)} />`}
  </div>`;
}

// -- the runs, and a run over them -------------------------------------------------------------------------

function RunRow({ r, onClick }) {
  return html`<li><button class="gui-mill__row" onClick=${onClick} title=${r.result}>
    <span class=${r.ok ? "ok-tone-ok" : "ok-tone-error"}>${r.ok ? "✓" : "✗"}</span>
    <span class="gui-mill__at">${day(r.started)}</span>
    <span class="gui-mill__trigger">${r.trigger}</span>
    <span class=${cls("gui-mill__what", { "ok-tone-error": !r.ok })}>${r.result.replace(/\s*\n\s*/g, " ⏎ ")}</span>
    <span class="gui-mill__cost">${r.cost ? money(r.cost) : r.agent ? say("an agent") : ""}</span>
  </button></li>`;
}

function Runs({ id, data }) {
  if (!data.runs.length) return html`<p class="ok-tone-muted">${say("No runs yet — a road brings the input, or Run takes the last one again.")}</p>`;
  const done = data.runs.filter((r) => r.ok).length;
  return html`<div class="gui-mill__runs">
    <p class="gui-mill__sum"><b>${data.runs.length}</b> ${say(data.runs.length === 1 ? "run" : "runs")} ·
      <span class="ok-tone-ok">✓ ${done}</span> <span class=${data.runs.length - done ? "ok-tone-error" : ""}>✗ ${data.runs.length - done}</span>
      ${data.spent ? html` · ${say("agents spent")} <b>${money(data.spent)}</b>` : ""}</p>
    <ul class="gui-mill__rows">${data.runs.map((r) => html`<${RunRow} key=${r.id} r=${r}
      onClick=${() => { chosen.value = { ...chosen.value, [id]: r.id }; }} />`)}</ul>
  </div>`;
}

function Text({ text }) {
  return html`<pre class="gui-pre gui-mill__out">${text}</pre>`;
}

/** A run open over the rows: ← back, how it went, its input, then what every step made of it. */
function Run({ id, data, r }) {
  const back = () => { chosen.value = { ...chosen.value, [id]: null }; };
  const steps = r.steps || [];
  return html`<div class="gui-mill__run" onKeyDown=${(e) => { if (e.key === "Escape") { e.stopPropagation(); back(); } }}>
    <button class="ok-btn gui-mill__back" onClick=${back}>← ${say("All runs")} · ${data.runs.length}</button>
    <p class="gui-mill__state"><b class=${r.ok ? "ok-tone-ok" : "ok-tone-error"}>${r.ok ? `✓ ${say("Ran")}` : `✗ ${say("Failed")}${r.failed ? ` ${say(`at step ${r.failed}`)}` : ""}`}</b>
      <span class="gui-mill__title">${r.title}</span></p>
    <p class="ok-detail__meta">${day(r.started)} · ${r.trigger}
      ${r.cost ? html` · <b>${money(r.cost)}</b>` : ""}${r.agent ? ` · ${say(`an agent did ${plural(r.agent, "step")}`)}` : ""}
      ${r.items ? ` · ${say(`${plural(r.items, "record")} went out one by one`)}` : ""}</p>
    <div class="ok-detail__actions">
      <button class="ok-btn" onClick=${() => openInLake({ text: r.input, title: `${r.title} — input`, from: id })}>${say("Input in the Inspector")}</button>
      <button class="ok-btn" onClick=${() => openInLake({ text: r.ok ? r.result : r.error, title: r.title, from: id })}>${say("Result in the Inspector")}</button></div>
    <p class="ok-detail__section">${say("Input")}${r.cut ? ` ${say("(cut to 256 KB)")}` : ""}</p>
    <${Text} text=${r.input} />
    ${steps.length ? steps.map((s, n) => html`<div key=${n} class=${cls("gui-mill__trace", { "is-failed": !!s.error })}>
        <p class="ok-detail__section">${s.error ? "✗ " : ""}${n + 1} · <span class="ok-font-mono">${s.step}</span></p>
        ${s.error ? html`<p class="ok-tone-error">${s.error}</p>` : html`<${Text} text=${s.out} />`}</div>`)
      : html`<p class="ok-detail__section">${say("Output")}</p>
        ${r.ok ? html`<${Text} text=${r.result} />` : html`<p class="ok-tone-error">${r.error}</p>`}
        <p class="ok-tone-muted">${say("This run was kept before the Mill kept every step.")}</p>`}
  </div>`;
}

function RunsPane({ id, data }) {
  const r = data.runs.find((x) => x.id === chosen.value[id]);
  return r ? html`<${Run} key=${r.id} id=${id} data=${data} r=${r} />` : html`<${Runs} id=${id} data=${data} />`;
}

function QueuePane({ data }) {
  return html`<div class="gui-mill__queue">
    ${data.current && html`<p><span class="ok-tone-wait">${say("milling")}</span> ${data.current.title} <span class="ok-tone-muted">${say("since")} ${when(data.current.started)}</span></p>`}
    ${data.queue.length > 0 && html`<p class="ok-tone-muted">${data.queue.length} ${say("waiting")}:</p>
      <ul class="gui-rows">${data.queue.slice(0, 10).map((q, n) => html`<li key=${n}>${q.title}
        <span class="ok-tone-muted">· ${q.trigger} · ${q.size} ${say("chars")}</span></li>`)}</ul>`}
  </div>`;
}

/** The window by its UI document (design/buildings/mill.json): a run opens over the rows, in `runs`; `run`
 *  shows nothing of its own (an older document that still has the pane loses nothing). */
export function panes(id, data) {
  return {
    steps: () => html`<${Steps} id=${id} data=${data} />`,
    runs: () => html`<${RunsPane} id=${id} data=${data} />`,
    run: () => null,
    queue: () => (data.running || data.queue.length ? html`<${QueuePane} data=${data} />` : null),   // only while it mills
  };
}
