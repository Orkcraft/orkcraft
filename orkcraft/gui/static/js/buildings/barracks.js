// 🏕 Barracks: the orks and their tasks, three ways (docs/design/building-views.md §3). Closed: how many
// work, the queue, the tally and the spend, the steward first when it asks. Command: the orks (a click
// opens the ork's terminal), the queue's top, a New task written in place, Pause / Answer. Full: the tasks in lanes by
// state with the chosen one beside them, a tab per ork with its terminal, the rules and settings, each a
// pane of its UI document (design/buildings/barracks.json). The worker does it all (core/workers/barracks.py); documents open in Lake, the rules change through the
// keeper.
import { signal } from "@preact/signals";
import { useState } from "preact/hooks";
import { html, cls } from "../html.js";
import { act, town, say } from "../link.js";
import { Dialog } from "../dialog.js";
import { Terminal } from "../terminal.js";
import { openInLake } from "../lake.js";
import { askKeeper } from "../keeper.js";
import { showBuilding } from "../windows.js";

const tabs = signal({});           // building id → "ork:<name>": the ork whose terminal shows
const chosen = signal({});         // building id → the task shown beside the lanes
const dialogs = signal({});        // building id → {kind: "task" | "answer" | "rule", …}

const STATE = { queued: "queued", working: "working", reviewing: "in review", asked: "asks you", done: "done", failed: "failed" };
const TONE = { asked: "ok-tone-fire", failed: "ok-tone-error", done: "ok-tone-ok", reviewing: "ok-tone-wait", working: "ok-tone-wait" };

const setIn = (sig, id, value) => { sig.value = { ...sig.value, [id]: value }; };
const openDialog = (id, d) => setIn(dialogs, id, d);
const closeDialog = (id) => setIn(dialogs, id, null);

function sessionOf(key) {
  return (town.value.sessions || []).find((s) => s.key === key) || null;
}

/** An ork's tab in the orks' pane, over the whole town; its terminal opens when it is free (its session resumed). */
export function openOrk(id, ork) {
  setIn(tabs, id, `ork:${ork.name}`);
  showBuilding(id);
  const s = sessionOf(ork.terminal);
  if (ork.status !== "working" && !(s && s.running)) act(id, "terminal", { ork: ork.name }).catch(() => {});
}

// -- dialogs ------------------------------------------------------------------------------------------

function TaskDialog({ id, onClose }) {
  const [brief, setBrief] = useState("");
  const send = () => act(id, "task", { brief }).then(onClose, () => {});
  return html`<${Dialog} title=${say("New task for the barracks")} text=${say("The foreman gives it to an ork: a free one, the one that did its earlier part, or a new one. Its first words become its title.")}
      onCancel=${onClose}
      actions=${html`<button class="ok-btn" onClick=${onClose}>Cancel</button>
        <button class="ok-btn primary" disabled=${!brief.trim()} onClick=${send}>Send it</button>`}>
    <textarea class="ok-input gui-textarea" rows="8" value=${brief} autofocus placeholder=${say("What to do, where, what done looks like")}
      onInput=${(e) => setBrief(e.target.value)}></textarea>
  </${Dialog}>`;
}

/** New task, at the top of its Work: the brief written in place, no window and no title (its first words are one). */
function NewTask({ id }) {
  const [brief, setBrief] = useState("");
  const send = () => {                     // cleared once sent, unless the next one is already being written
    const sent = brief;
    if (sent.trim()) act(id, "task", { brief: sent }).then(() => setBrief((now) => (now === sent ? "" : now)), () => {});
  };
  const keys = (e) => { if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) { e.preventDefault(); send(); } };
  return html`<div class="gui-newtask">
    <textarea class="ok-input gui-textarea" rows="3" value=${brief}
      placeholder=${say("New task: what to do, where, what done looks like (Ctrl+Enter sends it)")}
      onInput=${(e) => setBrief(e.target.value)} onKeyDown=${keys}></textarea>
    <div class="ok-row"><button class="ok-btn primary" disabled=${!brief.trim()} onClick=${send}>Send it</button></div>
  </div>`;
}

function AnswerDialog({ id, data, task, onClose }) {
  const [answer, setAnswer] = useState("");
  const send = (text) => act(id, "answer", { task: task.id, text }).then((rule) => {
    if (rule) openDialog(id, { kind: "rule", rule }); else onClose();
  }, () => {});
  if (task.draft) {
    return html`<${Dialog} title=${`${task.ork} wants to publish to ${task.target || "a service"}`} onCancel=${onClose}
        actions=${html`<button class="ok-btn" onClick=${onClose}>Later</button>
          <button class="ok-btn" disabled=${!answer.trim()} onClick=${() => send(answer)}>Send back</button>
          <button class="ok-btn primary" onClick=${() => send("")}>Publish as is</button>`}>
      <p class="ok-dialog__text">${task.title}</p>
      <pre class="gui-pre">${task.draft_text}</pre>
      <p class="ok-dialog__section">Or what to change</p>
      <textarea class="ok-input gui-textarea" rows="3" value=${answer} onInput=${(e) => setAnswer(e.target.value)}></textarea>
    </${Dialog}>`;
  }
  return html`<${Dialog} title=${`${data.keeper} asks — ${task.title}`} onCancel=${onClose}
      actions=${html`<button class="ok-btn" onClick=${onClose}>Later</button>
        <button class="ok-btn primary" disabled=${!answer.trim()} onClick=${() => send(answer)}>Answer</button>`}>
    <pre class="gui-pre">${task.question}</pre>
    <textarea class="ok-input gui-textarea" rows="4" value=${answer} autofocus onInput=${(e) => setAnswer(e.target.value)}></textarea>
  </${Dialog}>`;
}

function RuleDialog({ id, data, rule, onClose }) {
  return html`<${Dialog} title=${say(`Add to ${data.keeper}'s rules?`)} text=${say("Kept as a rule, every ork gets it; else it was only this once.")}
      onCancel=${onClose}
      actions=${html`<button class="ok-btn" onClick=${onClose}>Only this once</button>
        <button class="ok-btn primary" onClick=${() => act(id, "add_rule", { rule }).then(onClose, () => {})}>Keep it as a rule</button>`}>
    <pre class="gui-pre">${rule}</pre>
  </${Dialog}>`;
}

function Dialogs({ id, data }) {
  const d = dialogs.value[id];
  if (!d) return null;
  const close = () => closeDialog(id);
  if (d.kind === "task") return html`<${TaskDialog} id=${id} onClose=${close} />`;
  if (d.kind === "rule") return html`<${RuleDialog} id=${id} data=${data} rule=${d.rule} onClose=${close} />`;
  const task = data.asked.find((t) => t.id === d.task) || data.asked[0];
  return task ? html`<${AnswerDialog} key=${task.id} id=${id} data=${data} task=${task} onClose=${close} />` : null;
}

function Acts({ id, data, inline }) {
  return html`${!inline && html`<button class="ok-act" onClick=${() => openDialog(id, { kind: "task" })}><span class="ok-act__label">New task</span></button>`}
    <button class="ok-act" onClick=${() => act(id, "pause").catch(() => {})}>
      <span class="ok-act__label">${data.paused ? "Resume" : "Pause"}</span></button>
    ${data.asked.length > 0 && html`<button class="ok-act" onClick=${() => openDialog(id, { kind: "answer" })}>
      <span class="ok-act__label">Answer</span></button>`}`;
}

// -- closed ------------------------------------------------------------------------------------------

/** Closed: `active 2/4 · queue 3` and `✓5 ✗1 · $1.20`, with `<keeper> asks` first when it asks. */
export function card(b) {
  const c = b.card;
  if (!c) return null;
  return html`<div>
    ${c.asks && html`<div class="ok-tone-fire">${c.asks} asks</div>`}
    ${(c.working || []).map((w) => html`<div key=${w.ork} class="ok-tone-accent gui-hut__line">⚒ <b>${w.ork}</b> · ${w.task}</div>`)}
    <div>active ${c.active}/${c.max} · queue ${c.queue}${c.paused ? html` · <span class="ok-tone-wait">⚠ paused</span>` : ""}</div>
    <div>✓${c.done} ✗${c.failed} · ${c.spent}</div>
  </div>`;
}

// -- command -----------------------------------------------------------------------------------------

// -- full --------------------------------------------------------------------------------------------

function TaskCard({ id, t, isChosen }) {
  return html`<div class=${cls("ok-card", { "is-selected": isChosen, "is-done": t.status === "done" })}
      onClick=${() => setIn(chosen, id, t.id)}>
    <div class="ok-card__title">${t.status === "done" && html`<span class="ok-card__check">✓</span>`}<span>${t.title}</span>
      ${t.asks && html`<span class="ok-word ok-tone-fire"> asks</span>`}</div>
    <div class="ok-card__meta ok-tone-muted">
      ${[t.parts ? say(`planned in ${t.parts} parts`) : "", t.part ? say(`part ${t.part}`) : "",
         t.ork || (t.wait_for && `waits for ${t.wait_for}`), t.tier, t.branch,
         t.reworks ? `${t.reworks} rework${t.reworks > 1 ? "s" : ""}` : "", t.cost].filter(Boolean).join(" · ")}
      ${t.pr && html` <span class="ok-pr" data-state=${(t.pr_state || "open").toLowerCase()}>PR</span>`}</div>
  </div>`;
}

function Lanes({ id, data }) {
  return html`<div class="ok-board" style=${`--lanes:${data.lanes.length}`}>
    ${data.lanes.map((ln) => {
      const rows = data.tasks.filter((t) => t.lane === ln.id);
      return html`<section key=${ln.id} class="ok-lane">
        <header class="ok-lane__head">${ln.label}<span class="ok-lane__count">${rows.length}</span></header>
        ${rows.map((t) => html`<${TaskCard} key=${t.id} id=${id} t=${t} isChosen=${t.id === chosen.value[id]} />`)}
      </section>`;
    })}
  </div>`;
}

function Text({ label, text }) {
  if (!text) return null;
  return html`<p class="ok-detail__section">${label}</p><pre class="gui-pre">${text}</pre>`;
}

function TaskDetail({ id, data }) {
  const t = data.tasks.find((x) => x.id === chosen.value[id]);
  if (!t) return html`<div class="ok-detail ok-tone-muted">Pick a task in the lanes: its brief, its diff, the review's notes and the questions.</div>`;
  const diff = () => act(id, "diff", { task: t.id }).then((d) => openInLake({ text: d.text, title: d.title, from: id }), () => {});
  return html`<div class="ok-detail">
    <div class="ok-detail__head"><span>${t.title}</span>${t.pr && html`<span class="ok-pr" data-state=${(t.pr_state || "open").toLowerCase()}>PR</span>`}</div>
    <p class="ok-detail__meta"><span class=${TONE[t.status] || ""}>${STATE[t.status] || t.status}</span>
      ${[t.ork, t.branch, t.reworks ? `${t.reworks} rework${t.reworks > 1 ? "s" : ""}` : "", t.cost, t.warm ? "resumed its session" : "",
         t.scope === "local" ? "local, no pull request" : ""].filter(Boolean).map((x) => ` · ${x}`)}</p>
    ${t.pr && html`<p class="ok-detail__pr"><a href=${t.pr} target="_blank" rel="noreferrer">${t.pr}</a>${t.pr_state && ` · ${t.pr_state.toLowerCase()}`}</p>`}
    <div class="ok-detail__actions">
      ${t.asks && html`<button class="ok-btn primary" onClick=${() => openDialog(id, { kind: "answer", task: t.id })}>Answer</button>`}
      ${t.branch && html`<button class="ok-btn" onClick=${diff}>Diff in Lake</button>`}
      <button class="ok-btn" onClick=${() => openInLake({ text: t.brief, title: `Brief — ${t.title}`, from: id })}>Brief in Lake</button>
      ${t.report && html`<button class="ok-btn" onClick=${() => openInLake({ text: t.report, title: `Report — ${t.title}`, from: id })}>Report in Lake</button>`}
    </div>
    ${t.question && html`<p class="ok-detail__section ok-tone-fire">Waits for you</p><pre class="gui-pre">${t.question}</pre>`}
    <${Text} label="Brief" text=${t.brief} />
    <${Text} label="Review notes" text=${t.notes} />
    <${Text} label="Error" text=${t.error} />
    ${t.qa.length > 0 && html`<p class="ok-detail__section">Questions</p>
      <ul class="gui-rows">${t.qa.map((x, i) => html`<li key=${i}><b>${x.q}</b><br />→ ${x.a} <span class="ok-tone-muted">· ${x.who}</span></li>`)}</ul>`}
    ${t.files.length > 0 && html`<p class="ok-detail__section">Files</p>
      <ul class="gui-rows">${t.files.map((f) => html`<li key=${f} class="gui-link" onClick=${() => openInLake({ path: f, from: id })}>${f}</li>`)}</ul>`}
    <${Text} label="Report" text=${t.report} />
    ${t.decided && html`<p class="ok-detail__meta">The foreman: ${t.decided}</p>`}
  </div>`;
}

function OrkTab({ id, data, o }) {
  const s = sessionOf(o.terminal);
  const open = () => act(id, "terminal", { ork: o.name }).catch(() => {});
  return html`<div class="gui-split">
    <div class="gui-head">
      <span class="gui-head__what"><b>${o.name}</b>${` · ${o.label}${o.tier ? ` · ${o.tier}` : ""} · `}
        ${o.task ? html`<span class=${TONE[o.task.status] || ""}>${STATE[o.task.status]}: ${o.task.title}</span>` : "idle"}
        <span class="ok-tone-muted"> · ✓${o.done} ✗${o.failed} · ${o.cost}${o.tokens ? ` · ${Math.round(o.tokens / 1000)}k tokens` : ""}</span></span>
      <span class="gui-head__spacer"></span>
      ${!(s && s.running) && html`<button class="ok-act" disabled=${o.status === "working"} onClick=${open}
        title=${say(o.status === "working" ? "It is working: its terminal opens when it is free" : "Its last session, on its worktree")}>
        <span class="ok-act__label">${o.session ? "Resume its session" : "Open its terminal"}</span></button>`}
    </div>
    <div class="gui-head__note">${o.worktree || say("works in the project itself")}${o.branch ? ` · ${o.branch}` : ""}</div>
    ${s ? html`<${Terminal} key=${s.key} sessionKey=${s.key} />`
      : html`<div class="gui-section">
          <p class="ok-tone-muted">${o.status === "working" ? "It is working now: its terminal opens when it is free." : "No terminal open."}</p>
          ${o.recent.length > 0 && html`<h3 class="ok-font-heading">Its recent work</h3>
            <ul class="gui-rows">${o.recent.map((r, i) => html`<li key=${i}>${r}</li>`)}</ul>`}
        </div>`}
  </div>`;
}

function KeeperAsk({ id, keeper }) {
  const [ask, setAsk] = useState("");
  const send = () => askKeeper(id, ask).then((r) => { if (r !== null) setAsk(""); });
  return html`<div class="gui-section">
    <h3 class="ok-font-heading">Ask ${keeper} to change them</h3>
    <textarea class="ok-input gui-textarea" rows="3" value=${ask} placeholder=${say("In plain words: what the orks should always or never do, how the review should go…")}
      onInput=${(e) => setAsk(e.target.value)}></textarea>
    <div class="ok-row"><button class="ok-btn" disabled=${!ask.trim()} onClick=${send}>Ask ${keeper}</button></div>
  </div>`;
}

function Rules({ id, data }) {
  const settings = [["Tests", data.test_cmd || "none — the review reads the diff only"], ["Steward", `${data.steward} · spent ${data.steward_cost}`],
    ["Providers", data.providers.join(", ")], ["Orks at most", data.max], ["Budget", data.budget || "none of its own"],
    ["Reworks at most", data.max_reworks], ["Worktrees", say(data.worktrees ? "one per ork" : "off: they work in the project")]];
  return html`<div>
    <section class="gui-section"><h3 class="ok-font-heading">Rules</h3>
      <p class="ok-tone-muted">${data.keeper}, the steward, answers the orks' questions from them and reviews every task.</p>
      ${data.rules.length ? html`<ul class="gui-rows">${data.rules.map((r, i) => html`<li key=${i}>${r.replace(/^-\s*/, "")}</li>`)}</ul>`
        : html`<p class="ok-tone-muted">None yet — answers you give can become rules.</p>`}</section>
    <${KeeperAsk} id=${id} keeper=${data.keeper} />
    <section class="gui-section"><h3 class="ok-font-heading">Settings</h3>
      <ul class="gui-rows">${settings.map(([k, v]) => html`<li key=${k}><span class="ok-tone-muted">${say(k)}</span> · ${v}</li>`)}</ul></section>
    <section class="gui-section"><h3 class="ok-font-heading">Decisions</h3>
      ${data.decisions.length ? html`<ul class="gui-rows">${data.decisions.map((d, i) => html`<li key=${i}>
        <span class="ok-tone-muted">${d.at}</span> <span class="ok-tone-wait">${d.action}</span>${d.ork ? ` ${d.ork}` : ""}
        <span class="ok-tone-muted"> · ${d.why}</span></li>`)}</ul>`
        : html`<p class="ok-tone-muted">None yet — a road brings tasks here.</p>`}</section>
  </div>`;
}

/** The head: the counters, the acts, the steward when it asks; the dialogs live here (the pane is always there). */
function Head({ id, data }) {
  const queue = data.tasks.filter((t) => t.lane === "queue").length;
  return html`<div class="gui-head">
    <span class="gui-head__what">${data.paused && html`<span class="ok-tone-wait">⚠ paused · </span>`}
      ${data.orks.length}/${data.max} orks · ${queue} queued · ${data.spent}${data.budget ? ` of ${data.budget}` : ""}</span>
    ${data.asked.length > 0 && html`<span class="ok-tone-fire">${data.keeper} asks (${data.asked.length})</span>`}
    <span class="gui-head__spacer"></span>
    <${Acts} id=${id} data=${data} />
    <${Dialogs} id=${id} data=${data} />
  </div>`;
}

/** The orks' pane: a tab per ork, the chosen one's terminal under it (the one that asks comes first). */
function Orks({ id, data }) {
  if (!data.orks.length) return html`<p class="ok-tone-muted">No orks yet — the steward hires them for the tasks.</p>`;
  const tab = tabs.value[id] || "";
  const ork = data.orks.find((o) => `ork:${o.name}` === tab)
    || data.orks.find((o) => o.asks) || data.orks.find((o) => o.status === "working") || data.orks[0];
  return html`<div class="gui-split">
    <nav class="ok-tabs" role="tablist">
      ${data.orks.map((o) => html`<button key=${o.name} class=${cls("ok-tab", { "is-active": o === ork })}
          onClick=${() => setIn(tabs, id, `ork:${o.name}`)}>${o.name}${o.asks ? " ?" : o.status === "working" ? " ·" : ""}</button>`)}
    </nav>
    <${OrkTab} key=${ork.name} id=${id} data=${data} o=${ork} />
  </div>`;
}

/** The full window by its UI document (design/buildings/barracks.json). */
export function panes(id, data) {
  return {
    head: () => html`<div class="gui-split"><${Head} id=${id} data=${data} /><${NewTask} id=${id} /></div>`,
    lanes: () => html`<${Lanes} id=${id} data=${data} />`,
    task: () => html`<${TaskDetail} id=${id} data=${data} />`,
    orks: () => html`<${Orks} id=${id} data=${data} />`,
    rules: () => html`<${Rules} id=${id} data=${data} />`,
  };
}
