// Merged without your eyes (docs/specs/29c-after-the-merge.md §1): what reached `main` on green tests without a look,
// a line per task — its goal, the subject, the tests and the cost against the estimate, the commit. Revert asks once;
// Looked clears the line, Looked at all the group.
import { useState } from "preact/hooks";
import { html } from "../html.js";
import { toast } from "../link.js";
import { board, run } from "./store.js";

const usd = (n) => (n < 10 ? Number(n).toFixed(2).replace(/0$/, "") : String(Math.round(n)));

/** `tests · $cost (est. $a–b)`; a part the line lacks is left out. */
export function cost(m) {
  const est = Array.isArray(m.estimate) && m.estimate.length === 2 ? `est. $${usd(m.estimate[0])}–${usd(m.estimate[1])}` : "";
  const spent = m.cost != null ? `$${usd(m.cost)}${est ? ` (${est})` : ""}` : est ? `(${est})` : "";
  return [m.tests, spent].filter(Boolean).join(" · ");
}

function Line({ m }) {
  const [sure, setSure] = useState(false);
  const args = { idea: m.idea, task: m.task };
  const revert = async () => {
    setSure(false);
    const got = await run("ideas.revert", args);
    if (got && !got.error) toast(`Reverted “${m.subject}” on main.`);
  };
  return html`<li class="board-merged" data-task=${m.task} data-reverted=${String(!!m.reverted)}>
    <div class="board-merged__head"><b class="board-merged__goal">${m.goal || m.title}</b>
      ${m.commit && html`<code class="board-commit" title=${m.commit}>${m.commit.slice(0, 7)}</code>`}</div>
    <span class="board-merged__subject">${m.subject}</span>
    <span class="board-merged__meta ok-tone-muted">${cost(m)}</span>
    ${sure ? html`<div class="board-row board-merged__sure"><span>Revert “${m.subject}” on ${m.branch || "dev"}?</span>
        <button class="ok-btn danger" onClick=${revert}>Revert it</button><button class="ok-btn" onClick=${() => setSure(false)}>Keep it</button></div>`
      : html`<div class="board-row">
        ${m.reverted ? html`<span class="board-chip kit-well">reverted</span>`
          : html`<button class="ok-btn danger" onClick=${() => setSure(true)}>Revert</button>`}
        <button class="ok-btn" onClick=${() => run("ideas.seen", args)}>Looked</button></div>`}
  </li>`;
}

export function Merged() {
  const t = board.value.today, list = t.merged || [];
  if (!list.length) return "";
  const n = list.length + (t.merged_more || 0);
  return html`<div class="board-merged-group" aria-label="Merged without your eyes">
    <h3 class="board-sub kit-band">Merged without your eyes · ${n}
      <button class="ok-btn board-merged__all" onClick=${() => run("ideas.seen", {})}>Looked at all</button></h3>
    <ul class="board-list">${list.map((m) => html`<${Line} key=${m.idea + m.task} m=${m} />`)}</ul>
    ${t.merged_more ? html`<p class="ok-tone-muted">${t.merged_more} more not shown.</p>` : ""}
  </div>`;
}
