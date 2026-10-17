// Agents, in the lower part of the centre as VS Code's terminal (docs/specs/33-v1-shell.md §6–§7): a block per role,
// its name and state. The Taskmaster says what it waits on or reads; the Grunts are a chip per live task. A chip opens
// its task in the preview. Done today folds below. No Add agent and no Edit in v1.
import { html, cls } from "../html.js";
import { say } from "../link.js";
import { agents, agentsLayout, setLayout, showIdea, showTask } from "./store.js";

const GRUNT = { running: ["working", "↻"], testing: ["testing", ""], review: ["at Review", ""], ready: ["queued", ""],
  held: ["held", "⏳"], failed: ["needs you", "⚠"] };

export function gruntWords(c) {
  const [word, mark] = GRUNT[c.state] || [c.state, ""];
  if (c.state === "held") return `${c.note || "held"}`;
  if (c.state === "ready" && c.note) return "stopped";
  return mark ? `${word} ${mark}` : word;
}

function Taskmaster({ role }) {
  const c = role.chips || [];
  const say_ = (c0) => `${c0.state === "talking" ? "talking about" : c0.state} “${c0.title}”`;
  const lead = c.find((x) => x.state !== "waiting");
  return html`<div class="shell-role" data-role="taskmaster">
    <h3 class="shell-role__name">${say(role.name)}</h3>
    ${role.state === "waiting" && role.waits_on
      ? html`<button class="shell-chip is-wait" onClick=${() => showIdea(role.waits_on.idea)}>${role.waits_on.text}</button>`
      : lead ? html`<button class="shell-chip is-live" onClick=${() => showIdea(lead.idea)}><span class="shell-spin" aria-hidden="true">↻</span> ${say_(lead)}</button>`
        : html`<span class="ok-tone-muted">nothing to do</span>`}
    ${c.filter((x) => x !== lead && x.state !== "waiting").map((x) => html`<button key=${x.idea} class="shell-chip" onClick=${() => showIdea(x.idea)}>${say_(x)}</button>`)}
  </div>`;
}

function Grunts({ role, done }) {
  const chips = role.chips || [];
  return html`<div class="shell-role" data-role="grunt">
    <h3 class="shell-role__name">${say(role.name)}</h3>
    ${chips.length ? html`<ul class="shell-chips">${chips.map((c) => html`<li key=${c.idea + c.task}><button
        class=${cls("shell-chip", `is-${c.state}`)} data-state=${c.state} onClick=${() => showTask(c.idea, c.task)}>
        <span class="shell-chip__state">${gruntWords(c)}</span><b>${c.title}</b><small class="ok-tone-muted">${c.idea_title}</small></button></li>`)}</ul>`
      : html`<span class="ok-tone-muted">No task runs now.</span>`}
    ${done.length > 0 && html`<details class="shell-done"><summary>Done today (${done.length})</summary>
      <ul class="shell-chips">${done.map((d) => html`<li key=${d.idea + d.task}><button class="shell-chip is-done"
        onClick=${() => showTask(d.idea, d.task)}>${d.title}</button></li>`)}</ul></details>`}
  </div>`;
}

export function AgentsPane() {
  const a = agents.value;
  const hidden = agentsLayout.value.hidden;
  const grunts = a?.roles.find((r) => r.role === "grunt");
  const live = (grunts?.chips || []).filter((c) => c.state === "running" || c.state === "testing").length;
  return html`<section class=${cls("shell-agents", { "is-hidden": hidden })} aria-label="Agents">
    <header class="shell-pane__head"><h2>Agents ${live > 0 && html`<span class="shell-count">${live}</span>`}</h2>
      <button class="ok-btn" aria-expanded=${!hidden} aria-label=${hidden ? "Show Agents (Ctrl+J)" : "Hide Agents (Ctrl+J)"}
        title="Ctrl+J" onClick=${() => setLayout({ hidden: !hidden })}>${hidden ? "▴ show" : "▾ hide"}</button></header>
    ${!hidden && html`<div class="shell-agents__body">
      ${a ? html`${a.roles.map((r) => r.role === "taskmaster" ? html`<${Taskmaster} key=${r.role} role=${r} />`
        : html`<${Grunts} key=${r.role} role=${r} done=${a.done_today || []} />`)}` : html`<p class="ok-tone-muted">Opening…</p>`}
    </div>`}
  </section>`;
}
