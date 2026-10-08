// The keeper of a building (docs/design/building-views.md §2): the person says in plain words what the
// building should do — its rules, its settings, a task on a selection in Lake — and the keeper writes it
// (core/keeper.py over the host's `keeper.ask`). Its proposal comes back as a job: the change line by line
// and what the keeper says, then Apply takes it (Revert takes it back) or Drop lets it go.
//
//   askKeeper(id, request, selection?)       ask from code (a type's own button, Lake's selection)
//   <${KeeperAsk} id=${id} />                 the request field a type puts in its Command Card or window
//   <${KeeperDialog} id=${id} onClose=… />    the same field in a dialog
import { useState } from "preact/hooks";
import { html } from "./html.js";
import { command, say } from "./link.js";
import { Dialog } from "./dialog.js";

/** Ask a building's keeper: `request` in plain words, `selection` what was selected in Lake (optional:
 *  `{text, path?, title?, lines?: [first, last]}` or the text). The job's id, or null when refused (toasted). */
export function askKeeper(buildingId, request, selection = null) {
  return command("keeper.ask", { id: buildingId, request, selection }).catch(() => null);
}

/** The request field: what the building should do, in plain words. */
export function KeeperAsk({ id, selection = null, placeholder = "e.g. send bugs to the Forge, the rest to Task Fields",
                            onAsked = () => {} }) {
  const [request, setRequest] = useState("");
  const send = () => request.trim() && askKeeper(id, request.trim(), selection).then((job) => {
    if (job) { setRequest(""); onAsked(job); }
  });
  return html`<div class="gui-form__row">
    <input class="ok-input" value=${request} placeholder=${say(placeholder)}
      onInput=${(e) => setRequest(e.target.value)} onKeyDown=${(e) => e.key === "Enter" && send()} />
    <button class="ok-btn" disabled=${!request.trim()} onClick=${send}>Ask the steward</button>
  </div>`;
}

/** The request field in a dialog (a type's "Ask the keeper" button, a selection in Lake). */
export function KeeperDialog({ id, title, selection = null, onClose, children = null }) {
  return html`<${Dialog} title=${say(title || "Ask the keeper")} onCancel=${onClose}
      text=${say(selection ? "What should its keeper do with the selection?" : "What should the building do? Its keeper writes it.")}
      actions=${html`<button class="ok-btn" onClick=${onClose}>Cancel</button>`}>
    ${children}
    ${selection && html`<${Selection} s=${selection} />`}
    <${KeeperAsk} id=${id} selection=${selection} onAsked=${onClose} />
  </${Dialog}>`;
}

function Selection({ s }) {
  const where = [s.path || s.title, s.lines && `lines ${s.lines[0]}–${s.lines[1]}`].filter(Boolean).join(" · ");
  return html`<div>
    ${where && html`<p class="ok-font-status ok-tone-muted">${where}</p>`}
    <pre class="gui-pre gui-orders__context">${s.text}</pre></div>`;
}

const MARK = { "+": "ok-tone-ok", "-": "ok-tone-error", " ": "ok-tone-muted" };

function Diff({ lines }) {
  return html`<pre class="gui-pre gui-orders__context">${lines.map(([op, text], k) =>
    html`<div key=${k} class=${MARK[op] || ""}>${op} ${text}</div>`)}</pre>`;
}

/** A keeper's job as a dialog (js/acts.js shows the oldest job): writing, its proposal, or why it could not. */
export function KeeperJob({ job }) {
  const v = job.view || {};
  const drop = () => command("job.drop", { job: job.id }).catch(() => {});
  const apply = () => command("job.accept", { job: job.id }).catch(() => {});
  const title = say(`Keeper — ${job.title}`);
  if (job.state === "running") {
    return html`<${Dialog} title=${title} text=${job.text} onCancel=${drop}
      actions=${html`<button class="ok-btn" onClick=${drop}>Cancel</button>`}>
      <p class="ok-font-status ok-tone-muted">This calls a model; it takes a moment.</p></${Dialog}>`;
  }
  if (job.state === "failed") {
    return html`<${Dialog} title=${title} text=${job.error} onCancel=${drop} warn
      actions=${html`<button class="ok-btn primary" onClick=${drop}>Close</button>`} />`;
  }
  const changes = (v.diff || []).some(([op]) => op !== " ");
  return html`<${Dialog} title=${title} onCancel=${drop}
      actions=${html`<button class="ok-btn" onClick=${drop}>${changes ? "Drop" : "Close"}</button>
        ${changes && html`<button class="ok-btn primary" onClick=${apply}>Apply</button>`}`}>
    <div class="gui-form">
      <p class="ok-font-status"><span class="ok-tone-muted">Asked:</span> ${v.request}</p>
      ${v.selection && html`<${Selection} s=${v.selection} />`}
      ${v.answer && html`<div class="gui-prose" dangerouslySetInnerHTML=${{ __html: v.answer }}></div>`}
      ${changes ? html`<h3 class="ok-font-heading">${say(`New ${v.kind}`)}</h3>
          ${v.why && html`<p class="ok-font-status">${v.why}</p>`}<${Diff} lines=${v.diff} />
          <p class="ok-font-status ok-tone-muted">Checked against the building's contract. Revert takes it back.</p>`
        : html`<p class="ok-font-status ok-tone-muted">Nothing to change.</p>`}
      <p class="ok-font-status ok-tone-muted">Attempts: ${v.attempts}${v.cost ? ` · cost ${v.cost}` : ""}</p>
    </div></${Dialog}>`;
}
