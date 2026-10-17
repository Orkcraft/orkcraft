// Agents, in the lower part of the centre as VS Code's terminal (docs/specs/33-v1-shell.md §6–§7, spec 34 §3): a block per
// role — its name, model and state, its chips, Edit — with + Add agent at the top; under them the Task types, each with
// the agent that does it (and New agent… to make one from there). A chip opens its task in the preview.
import { html, cls } from "../html.js";
import { say } from "../link.js";
import { agents, agentsLayout, roles, setLayout, showIdea, showGoal, showTask, act } from "./store.js";
import { openDialog } from "./modals.js";

const GRUNT = { running: ["working", "↻"], testing: ["testing", ""], review: ["at Review", ""], ready: ["queued", ""],
  held: ["held", "⏳"], failed: ["needs you", "⚠"] };

export function gruntWords(c) {
  const [word, mark] = GRUNT[c.state] || [c.state, ""];
  if (c.state === "held") return `${c.note || "held"}`;
  if (c.state === "ready" && c.note) return "stopped";
  return mark ? `${word} ${mark}` : word;
}

const usd = (n) => (n ? `$${n < 10 ? n.toFixed(2) : Math.round(n)} today` : "");
const modelWords = (r, models) => (models || []).find((m) => m.id === r.model)?.label || r.model || "the task's own tier";

function Head({ role, models }) {
  return html`<div class="shell-role__head">
    <h3 class="shell-role__name">${say(role.name)}</h3>
    <button class="board-link" aria-label=${`Edit ${say(role.name)}`} onClick=${() => openDialog("agent", { slug: role.role })}>Edit</button>
    <span class="ok-font-status ok-tone-muted shell-role__facts">${modelWords(role, models)}${role.role === "taskmaster" ? "" : ` · up to ${role.max_parallel}`}${role.spend_today ? ` · ${usd(role.spend_today)}` : ""}</span>
  </div>`;
}

function Taskmaster({ role, models }) {
  const c = role.chips || [];
  const say_ = (c0) => `${c0.state === "talking" ? "talking about" : c0.state} “${c0.title}”`;
  const open = (c0) => (c0.goal ? showGoal(c0.goal) : showIdea(c0.idea));
  const lead = c.find((x) => x.state !== "waiting");
  return html`<div class="shell-role" data-role="taskmaster">
    <${Head} role=${role} models=${models} />
    ${role.state === "waiting" && role.waits_on
      ? html`<button class="shell-chip is-wait" onClick=${() => showIdea(role.waits_on.idea)}>${role.waits_on.text}</button>`
      : lead ? html`<button class="shell-chip is-live" onClick=${() => open(lead)}><span class="shell-spin" aria-hidden="true">↻</span> ${say_(lead)}</button>`
        : html`<span class="ok-tone-muted">nothing to do</span>`}
    ${c.filter((x) => x !== lead && x.state !== "waiting").map((x) => html`<button key=${x.goal || x.idea} class="shell-chip" onClick=${() => open(x)}>${say_(x)}</button>`)}
  </div>`;
}

function Worker({ role, done, models }) {
  const chips = role.chips || [];
  const mine = done.filter((d) => (d.role || "grunt") === role.role);
  return html`<div class="shell-role" data-role=${role.role === "grunt" ? "grunt" : "agent"} data-slug=${role.role}>
    <${Head} role=${role} models=${models} />
    ${role.kinds?.length > 0 && html`<span class="ok-font-status ok-tone-muted">Does: ${role.kinds.join(", ")}</span>`}
    ${chips.length ? html`<ul class="shell-chips">${chips.map((c) => html`<li key=${c.idea + c.task}><button
        class=${cls("shell-chip", `is-${c.state}`)} data-state=${c.state} onClick=${() => showTask(c.idea, c.task)}>
        <span class="shell-chip__state">${gruntWords(c)}</span><b>${c.title}</b><small class="ok-tone-muted">${c.idea_title}</small></button></li>`)}</ul>`
      : html`<span class="ok-tone-muted">No task runs now.</span>`}
    ${mine.length > 0 && html`<details class="shell-done"><summary>Done today (${mine.length})</summary>
      <ul class="shell-chips">${mine.map((d) => html`<li key=${d.idea + d.task}><button class="shell-chip is-done"
        onClick=${() => showTask(d.idea, d.task)}>${d.title}</button></li>`)}</ul></details>`}
  </div>`;
}

const NEW = "__new__";

/** Which agent does each type of task: a select of the agents, or New agent… (opens Add agent and gives it the type). */
function Kinds() {
  const data = roles.value;
  if (!data) return null;
  const doers = data.roles.filter((r) => r.slug !== "taskmaster");
  const change = (kind, value) => {
    if (value === NEW) openDialog("agent", { assign: kind.kind });
    else act("ideas.kind_set", { kind: kind.kind, role: value });
  };
  return html`<div class="shell-role shell-kinds" data-role="kinds"><h3 class="shell-role__name">Task types</h3>
    <ul class="shell-kinds__list">${data.kinds.map((k) => html`<li key=${k.kind} data-kind=${k.kind}>
      <label><span class="shell-kinds__name">${k.label}</span>
        <select class="ok-input" aria-label=${`Agent for ${k.label}`} value=${k.role} onChange=${(e) => change(k, e.target.value)}>
          ${doers.map((r) => html`<option key=${r.slug} value=${r.slug}>${r.name}</option>`)}
          <option value=${NEW}>New agent…</option></select></label></li>`)}</ul>
  </div>`;
}

export function AgentsPane() {
  const a = agents.value;
  const hidden = agentsLayout.value.hidden;
  const live = (a?.roles || []).filter((r) => r.role !== "taskmaster").flatMap((r) => r.chips || [])
    .filter((c) => c.state === "running" || c.state === "testing").length;
  const models = roles.value?.models;
  return html`<section class=${cls("shell-agents", { "is-hidden": hidden })} aria-label="Agents">
    <header class="shell-pane__head"><h2>Agents ${live > 0 && html`<span class="shell-count">${live}</span>`}</h2>
      ${!hidden && html`<button class="ok-btn primary" onClick=${() => openDialog("agent")}>+ Add agent</button>`}
      <button class="ok-btn" aria-expanded=${!hidden} aria-label=${hidden ? "Show Agents (Ctrl+J)" : "Hide Agents (Ctrl+J)"}
        title="Ctrl+J" onClick=${() => setLayout({ hidden: !hidden })}>${hidden ? "▴ show" : "▾ hide"}</button></header>
    ${!hidden && html`<div class="shell-agents__body">
      ${a ? html`${a.roles.map((r) => r.role === "taskmaster" ? html`<${Taskmaster} key=${r.role} role=${r} models=${models} />`
        : html`<${Worker} key=${r.role} role=${r} done=${a.done_today || []} models=${models} />`)}<${Kinds} />` : html`<p class="ok-tone-muted">Opening…</p>`}
    </div>`}
  </section>`;
}
