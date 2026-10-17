// An opened idea (29a §7), as the v1 shell's preview shows it (docs/specs/33-v1-shell.md §6): its sections as blocks (each
// its own colour role and icon, the thesis bold, the text folded), the question box, the talk, and the actions by state —
// Take it to work · Start · task states with Stop · Start again. `PlanView` is the same idea's plan, scrolled to a to-do.
import { useState } from "preact/hooks";
import { html, cls } from "../html.js";
import { say } from "../link.js";
import { stateWords } from "./store.js";
import { act as run, showTask, showIdea, closePreview } from "../shell/store.js";

// Section → [colour role, line icon, kit icon]. The role is a design-system token in board.css (`[data-sec]`); the line
// icon (16px) is Office's, the kit's pixel icon (tools/ui_kit.py) Camp's.
const SECTIONS = {
  Gist: ["info", "M3 2.5h7l3 3v8H3zM5.5 8h5M5.5 10.5h5", "gist"],
  Why: ["accent", "M8 1.5a4.5 4.5 0 0 0-2 8.5v1.5h4V10A4.5 4.5 0 0 0 8 1.5zM6.5 14h3", "why"],
  In: ["ok", "M3 8.5l3.2 3.2L13 4.8", "in"],
  Out: ["muted", "M4 4l8 8M12 4l-8 8", "out"],
  Risks: ["fire", "M8 2 14.5 13.5h-13zM8 6.5v3.5M8 11.8v.4", "risk"],
  "Open questions": ["wait", "M6 6a2 2 0 1 1 2.8 1.8c-.5.3-.8.7-.8 1.2M8 11.8v.4", "ask"],
  Estimate: ["accent", "M8 14a6 6 0 1 0 0-12 6 6 0 0 0 0 12zM8 4.5V8l2.5 1.5", "estimate"],
  Stages: ["info", "M2 4h4v3H2zM10 9h4v3h-4zM6 5.5h2.5V10.5H10", "stages"],
  Decisions: ["ok", "M3 2v12M3 3h9l-2 2.5L12 8H3", "decide"],
};
const KIT_ICONS = "/ds/sprites/v4/ui/icons/";

const usd = (n) => (n < 10 ? n.toFixed(2).replace(/0$/, "") : String(Math.round(n)));
export const price = (e) => (e ? `~$${usd(e.usd_low)}–${usd(e.usd_high)}` : "");

function Block({ s, onAsk, asked }) {
  const [role, d, icon] = SECTIONS[s.name] || ["muted", "M3 8h10", "gist"];
  const [editing, setEditing] = useState(null);
  const save = async () => { await run("ideas.edit", { slug: opened.value, section: s.name, text: editing }); setEditing(null); };
  return html`<details class=${cls("board-sec kit-well", { "is-asked": asked })} data-sec=${role} data-name=${s.name} open=${s.name === "Gist"}>
    <summary><svg class="board-sec__icon" viewBox="0 0 16 16" width="16" height="16" aria-hidden="true"><path d=${d} /></svg>
      <span class="board-sec__mark" aria-hidden="true"><img alt="" width="24" height="24" src=${`${KIT_ICONS}${icon}.png`}
        srcset=${`${KIT_ICONS}${icon}.png 1x, ${KIT_ICONS}${icon}@2x.png 2x`} /></span>
      <span class="board-sec__name">${s.name}</span>
      <b class="board-sec__thesis">${s.thesis}</b></summary>
    ${editing === null ? html`<div class="board-sec__body"><p class="board-sec__text">${s.text}</p>
        <div class="board-row"><button class="ok-btn" onClick=${() => onAsk(s.name)}>Ask about ${s.name}</button>
          <button class="ok-btn" onClick=${() => setEditing(s.text)}>Edit</button></div></div>`
      : html`<div class="board-sec__body"><textarea class="ok-input" rows="6" value=${editing} aria-label=${`Text of ${s.name}`}
          onInput=${(e) => setEditing(e.target.value)}></textarea>
        <div class="board-row"><button class="ok-btn primary" onClick=${save}>Keep it</button>
          <button class="ok-btn" onClick=${() => setEditing(null)}>Cancel</button></div></div>`}
  </details>`;
}

function Say({ p, section, setSection }) {
  const [text, setText] = useState("");
  const send = async () => {
    const t = text.trim();
    if (!t) return;
    setText("");
    await run("ideas.say", { slug: p.slug, text: t, ...(section ? { section } : {}) });
  };
  return html`<div class="board-say">
    ${section && html`<span class="board-chip">About ${section} <button class="board-link" aria-label="Ask about the whole idea"
      onClick=${() => setSection("")}>×</button></span>`}
    <textarea class="ok-input" rows="2" value=${text} aria-label=${say("Ask or answer the Taskmaster")}
      placeholder=${section ? `About ${section}…` : say("Ask or answer the Taskmaster…")} onInput=${(e) => setText(e.target.value)}
      onKeyDown=${(e) => { if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) { e.preventDefault(); send(); } }}></textarea>
    <div class="board-row"><button class="ok-btn" disabled=${!text.trim() || p.busy} onClick=${send}>Ask</button>
      ${p.busy && html`<span class="ok-tone-wait">${say("The Taskmaster is answering…")}</span>`}</div>
  </div>`;
}

function Talk({ turns }) {
  if (!turns.length) return "";
  return html`<ol class="board-talk" aria-label="The talk">${turns.slice(-8).map((t, n) => html`<li key=${n} data-who=${t.who}>
    <span class="board-talk__who">${t.who === "you" ? "You" : say("The Taskmaster")}${t.section ? ` · ${t.section}` : ""}</span>
    <span>${t.text}</span></li>`)}</ol>`;
}

const TASK_WORDS = { waiting: "waiting", ready: "ready", running: "running", testing: "testing", review: "at Review", merged: "merged",
  failed: "failed", held: "held" };

function Tasks({ plan, working }) {
  return html`<ul class="board-tasks">${plan.tasks.map((k) => html`<li key=${k.id} data-state=${k.state}>
    <span class="board-task__state" data-state=${k.state}>${TASK_WORDS[k.state] || k.state}</span>
    <button class="board-link board-task__title" onClick=${() => showTask(plan.idea, k.id)}><b>${k.title}</b></button>
    <span class="board-chip kit-well">${k.tier}</span>
    ${k.after?.length ? html`<span class="ok-tone-muted">after ${k.after.join(", ")}</span>` : ""}
    ${k.commit && html`<code class="board-commit" title=${k.branch}>${k.commit.slice(0, 8)}</code>`}
    ${k.state === "held" && k.note && html`<span class="ok-tone-wait">${k.note}</span>`}
    ${k.error && html`<span class="ok-tone-error">${k.error}</span>`}
    ${working && k.cost != null && html`<span class="ok-tone-muted">$${usd(k.cost)}</span>`}
  </li>`)}</ul>`;
}

/** "tasks k2 and k3 wait for it": the tasks a to-do holds back. */
export function unblocks(todo) {
  const ids = todo.for || [];
  if (!ids.length) return "";
  const list = ids.length === 1 ? ids[0] : `${ids.slice(0, -1).join(", ")} and ${ids[ids.length - 1]}`;
  return `${ids.length === 1 ? "task" : "tasks"} ${list} ${ids.length === 1 ? "waits" : "wait"} for it`;
}

function Plan({ plan, todo = "" }) {
  const e = plan.estimate;
  return html`<div class="board-plan kit-well"><h3 class="board-sub kit-legend">The plan ${e ? html`<span class="ok-tone-muted">${e.tasks} tasks · ${price(e)}</span>` : ""}</h3>
    <${Tasks} plan=${plan} />
    ${plan.todos?.length ? html`<h3 class="board-sub kit-legend">To-dos before it starts</h3><ul class="board-tasks">${plan.todos.map((t) =>
      html`<li key=${t.id} data-todo=${t.id} class=${cls("board-plan__todo", { "is-target": t.id === todo })}
        ref=${(el) => { if (el && t.id === todo) el.scrollIntoView({ block: "center" }); }}>
        <b>${t.title}</b><span class="board-chip kit-well">${t.kind}</span><span class="ok-tone-muted">${t.why}</span>
        ${t.id === todo && unblocks(t) && html`<span class="board-plan__line">${unblocks(t)}</span>`}</li>`)}</ul>` : ""}
  </div>`;
}

function Actions({ p }) {
  const s = p.state, plan = p.plan, slug = p.slug;
  const e = plan?.estimate;
  if (s === "reading" || s === "planning") return html`<p class="ok-tone-wait" role="status">${say(`The Taskmaster is ${s === "reading" ? "reading" : "planning"}…`)}</p>`;
  if (s === "raw") return html`<p class="ok-tone-muted">${say("New: the Taskmaster reads it at the next round.")}</p>`;
  return html`<div class="board-actions">
    ${(s === "ready" || s === "asks") && html`<button class="ok-btn primary" onClick=${() => run("ideas.plan", { slug })}>Take it to work</button>`}
    ${plan && html`<${Plan} plan=${plan} />`}
    ${s === "plan" && e && html`<button class="ok-btn primary" onClick=${() => run("ideas.start", { slug })}>Start · ${e.tasks} tasks · ${price(e)}</button>`}
    ${s === "working" && html`<button class="ok-btn danger" onClick=${() => run("ideas.stop", { slug })}>Stop</button>`}
    ${s === "failed" && html`<p class="ok-tone-error" role="alert">${plan?.tasks.find((k) => k.error)?.error || "It stopped and needs you."}</p>
      <button class="ok-btn primary" onClick=${() => run("ideas.start", { slug })}>Start again</button>`}
  </div>`;
}

/** The idea's plan with the to-do it was opened from highlighted and said what it unblocks; Start stays here. */
export function PlanView({ p, todo }) {
  const plan = p.plan, e = plan?.estimate;
  if (!plan) return html`<p class="ok-tone-muted">This idea has no plan yet.</p>`;
  return html`<div class="board-actions">
    <${Plan} plan=${plan} todo=${todo} />
    ${p.state === "plan" && e && html`<button class="ok-btn primary" onClick=${() => run("ideas.start", { slug: p.slug })}>Start · ${e.tasks} tasks · ${price(e)}</button>`}
    <button class="board-link" onClick=${() => showIdea(p.slug)}>Open the spec</button>
  </div>`;
}

export function IdeaView({ p }) {
  const [section, setSection] = useState("");
  const [sure, setSure] = useState(false);
  const drop = async () => { await run("ideas.drop", { slug: p.slug }); closePreview(); };
  return html`<div class="board-ideaview">
    <div class="board-bar">
      <span class="board-state" data-state=${p.state}>${stateWords({ state: p.state, progress: planProgress(p.plan) })}</span>
      ${p.size && html`<span class="board-size kit-well">${p.size}</span>`}</div>
    <${Actions} p=${p} />
    <div class="board-secs">${p.sections.map((s) => html`<${Block} key=${s.name} s=${s} asked=${section === s.name} onAsk=${setSection} />`)}</div>
    <${Say} p=${p} section=${section} setSection=${setSection} />
    <${Talk} turns=${p.talk || []} />
    <div class="board-row">${sure ? html`<span>Drop this idea and its page?</span>
        <button class="ok-btn danger" onClick=${drop}>Delete it</button><button class="ok-btn" onClick=${() => setSure(false)}>Keep it</button>`
      : html`<button class="ok-btn danger" onClick=${() => setSure(true)}>Delete idea</button>`}</div>
  </div>`;
}

export function planProgress(plan) {
  return plan ? { done: plan.tasks.filter((k) => k.state === "merged").length, total: plan.tasks.length } : { done: 0, total: 0 };
}
