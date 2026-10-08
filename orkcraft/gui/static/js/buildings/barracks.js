// 🏕 Barracks: the orks and their tasks (docs/design/building-views.md §3). Closed: how many orks work of
// how many, the queue, the tally and the spend, the steward first when it asks. Open, made for the half
// panel: the counters on one line, the question waiting for you with Answer, a New task written in place,
// the open tasks as one flow of cards (the one that asks first), the finished ones folded to a line; a
// card opens its task over the flow (← back), a tab per ork with its terminal under it, the rules and
// settings folded to a line — each a pane of its UI document (design/buildings/barracks.json). The worker
// does it all (core/workers/barracks.py); documents open in Lake, the rules change through the keeper.
import { signal } from "@preact/signals";
import { useState } from "preact/hooks";
import { html, cls } from "../html.js";
import { act, town, details, say } from "../link.js";
import { Dialog } from "../dialog.js";
import { Terminal } from "../terminal.js";
import { openInLake } from "../lake.js";
import { askKeeper } from "../keeper.js";
import { usePeek } from "../windows.js";
import { OrkHead } from "../icons.js";

const sheet = new URL("./barracks.css", import.meta.url).href;
if (!document.querySelector(`link[href="${sheet}"]`)) {
  const link = document.createElement("link");
  link.rel = "stylesheet";
  link.href = sheet;
  document.head.appendChild(link);
}

const tabs = signal({});           // building id → "ork:<name>": the ork whose terminal shows
const chosen = signal({});         // building id → the task shown beside the lanes
const dialogs = signal({});        // building id → {kind: "task" | "answer" | "rule", …}
const folded = signal({});         // building id → true: the orks' terminal folded to its tabs


const setIn = (sig, id, value) => { sig.value = { ...sig.value, [id]: value }; };
const openDialog = (id, d) => setIn(dialogs, id, d);
const closeDialog = (id) => setIn(dialogs, id, null);

function sessionOf(key) {
  return (town.value.sessions || []).find((s) => s.key === key) || null;
}

// -- dialogs ------------------------------------------------------------------------------------------

/** New task, at the top of its Work: one line written in place, no window and no title (its first words are
 *  one); it grows while it is written. */
function NewTask({ id }) {
  const [brief, setBrief] = useState("");
  const send = () => {                     // cleared once sent, unless the next one is already being written
    const sent = brief;
    if (sent.trim()) act(id, "task", { brief: sent }).then(() => setBrief((now) => (now === sent ? "" : now)), () => {});
  };
  const keys = (e) => { if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) { e.preventDefault(); send(); } };
  return html`<div class="gui-newtask">
    <textarea class=${cls("ok-input gui-textarea", { "has-text": !!brief })} rows="1" value=${brief} aria-label=${say("New task")}
      placeholder=${say("New task — what, where, what done looks like (Ctrl+Enter sends it)")}
      onInput=${(e) => setBrief(e.target.value)} onKeyDown=${keys}></textarea>
    <button class="ok-btn primary" disabled=${!brief.trim()} onClick=${send}>Send</button>
  </div>`;
}

function TaskDialog({ id, onClose }) {
  const [brief, setBrief] = useState("");
  const send = () => act(id, "task", { brief }).then(onClose, () => {});
  return html`<${Dialog} title=${say("New task for the barracks")} text=${say("Its first words become its title; the foreman gives it to an ork.")}
      onCancel=${onClose}
      actions=${html`<button class="ok-btn" onClick=${onClose}>Cancel</button>
        <button class="ok-btn primary" disabled=${!brief.trim()} onClick=${send}>Send</button>`}>
    <textarea class="ok-input gui-textarea" rows="5" value=${brief} autofocus aria-label=${say("New task")}
      placeholder=${say("What to do, where, what done looks like (Ctrl+Enter sends it)")} onInput=${(e) => setBrief(e.target.value)}
      onKeyDown=${(e) => { if (e.key === "Enter" && (e.ctrlKey || e.metaKey) && brief.trim()) { e.preventDefault(); send(); } }}></textarea>
  </${Dialog}>`;
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
  if (!data.asked) return null;
  if (d.kind === "rule") return html`<${RuleDialog} id=${id} data=${data} rule=${d.rule} onClose=${close} />`;
  const task = data.asked.find((t) => t.id === d.task) || data.asked[0];
  return task ? html`<${AnswerDialog} key=${task.id} id=${id} data=${data} task=${task} onClose=${close} />` : null;
}

// -- closed ------------------------------------------------------------------------------------------

const keep = (e) => e.stopPropagation();          // a press on the card's control is not a press on the hut

/** Closed: the headline is how many orks work of how many; under it the queue, the tally and the spend, the
 *  steward first when it asks; the foot who works on what. Paused, the headline says so with what waits and
 *  Resume in the foot: a stopped queue is the one thing to fix here. */
export function card(b) {
  const c = b.card;
  if (!c) return null;
  const working = c.working || [];
  return html`<div class="gui-hut__body-in">
    ${c.paused
      ? html`<div class="gui-hut__big ok-tone-wait">⚠ ${say("Paused")}<small>${c.queue ? `${c.queue} waiting` : say("nothing waits")}</small></div>`
      : html`<div class="gui-hut__big">${c.active}<small>${say(`of ${c.max} orks at work`)}</small></div>`}
    <div class="gui-hut__text">${say("queue")} <b>${c.queue}</b> · <span class=${c.done ? "ok-tone-ok" : ""}>✓${c.done}</span>
      <span class=${c.failed ? "ok-tone-error" : ""} title=${c.failed ? say("Failed tasks: open the building to see why") : ""}>✗${c.failed}</span>
      · <b>${c.spent}</b></div>
    ${c.asks && html`<div class="gui-hut__text ok-tone-fire">? ${c.asks} ${say("asks")}</div>`}
    ${c.paused
      ? html`<div class="gui-hut__foot"><span>${say("Stopped: no task starts")}</span>
          <button class="ok-act gui-hut__act" onPointerDown=${keep}
            onClick=${(e) => { keep(e); act(b.id, "pause").catch(() => {}); }}><span class="ok-act__label">Resume</span></button></div>`
      : working.length > 0
        ? html`<div class="gui-hut__foot"><span>⚒ <b>${working[0].ork}</b> · ${working[0].task}</span>
            ${working.length > 1 && html`<span class="gui-hut__when">+${working.length - 1}</span>`}</div>`
        : c.last && html`<div class="gui-hut__foot"><span><span class=${c.last.ok ? "ok-tone-ok" : "ok-tone-error"}>${c.last.ok ? "✓" : "✗"}</span> ${c.last.title}</span></div>`}
  </div>`;
}

// -- open --------------------------------------------------------------------------------------------

const ORDER = { asked: 0, reviewing: 1, working: 2, planned: 2, planning: 3, queued: 3, blocked: 3 };
const WORD = { asked: "asks you", reviewing: "in review", working: "working", planned: "working", planning: "planning",
               queued: "queue", blocked: "queue", done: "done", failed: "failed" };
const STATE_TONE = { asked: "ok-tone-fire", reviewing: "ok-tone-wait", working: "ok-tone-accent", planned: "ok-tone-accent",
                     done: "ok-tone-ok", failed: "ok-tone-error" };

/** An ork's head as its state says: at work it sweats, asking it burns, else it rests. */
function Head({ ork, asks, working }) {
  return html`<${OrkHead} o=${{ name: ork, status: working ? "busy" : "idle" }} alert=${!!asks} />`;
}

/** A task as a card: who and how it is on top, its title, its branch and cost under it. */
function TaskCard({ id, t, n }) {
  const working = t.status === "working" || t.status === "planned";
  return html`<button class=${cls("pool-card", { "is-asks": t.asks })} onClick=${() => setIn(chosen, id, t.id)}
      title=${t.title}>
    <span class=${`pool-card__state ${STATE_TONE[t.status] || ""}`}>
      ${t.ork ? html`<${Head} ork=${t.ork} asks=${t.asks} working=${working} /><span class="pool-card__who">${t.ork}</span> · ` : ""}
      ${t.status === "done" ? "✓ " : t.status === "failed" ? "✗ " : ""}${say(WORD[t.status] || t.status)}${n ? ` #${n}` : ""}
      ${!t.ork && t.wait_for ? ` · ${say("waits for")} ${t.wait_for}` : ""}</span>
    <span class="pool-card__title">${t.title}</span>
    ${!!(t.branch || t.cost || t.pr || t.reworks > 0 || t.parts || t.part) && html`<span class="pool-card__foot">
      ${t.branch && html`<span class="pool-card__branch">${t.branch}</span>`}
      ${t.parts ? html`<span>${say(`${t.parts} parts`)}</span>` : t.part ? html`<span>${say(`part ${t.part}`)}</span>` : ""}
      ${t.reworks > 0 && html`<span>${t.reworks} rework${t.reworks > 1 ? "s" : ""}</span>`}
      ${t.pr && html`<span class="ok-pr" data-state=${(t.pr_state || "open").toLowerCase()}>PR</span>`}
      ${t.cost && html`<span class="pool-card__cost">${t.cost}</span>`}</span>`}
  </button>`;
}

/** The open tasks as one flow, the one that asks first, then review, work, the queue; the finished folded. */
function Flow({ id, data }) {
  const open = data.tasks.filter((t) => t.lane !== "done" && t.lane !== "failed")
    .map((t, i) => ({ t, i })).sort((a, b) => (ORDER[a.t.status] ?? 3) - (ORDER[b.t.status] ?? 3) || a.i - b.i).map((x) => x.t);
  const done = data.tasks.filter((t) => t.lane === "done");
  const failed = data.tasks.filter((t) => t.lane === "failed");
  const finished = data.tasks.filter((t) => t.lane === "done" || t.lane === "failed");
  let q = 0;
  return html`<div>
    ${open.length ? html`<div class="pool-flow">
        ${open.map((t) => html`<${TaskCard} key=${t.id} id=${id} t=${t} n=${t.lane === "queue" && !t.ork ? ++q : 0} />`)}</div>`
      : html`<p class="pool-empty">${say("No open tasks — write one above, or a road brings them here.")}</p>`}
    ${finished.length > 0 && html`<details class="pool-fold">
      <summary><span class="ok-tone-ok">✓ ${done.length} ${say("done")}</span><span class=${failed.length ? "ok-tone-error" : ""}>✗ ${failed.length} ${say("failed")}</span>
        <span class="pool-fold__last">${say("last:")} ${finished[0].title}</span></summary>
      <div class="pool-flow">${finished.map((t) => html`<${TaskCard} key=${t.id} id=${id} t=${t} n=${0} />`)}</div>
    </details>`}
  </div>`;
}

function Text({ label, text }) {
  if (!text) return null;
  return html`<p class="ok-detail__section">${label}</p><pre class="gui-pre">${text}</pre>`;
}

/** The answer to a task's question, written where the question is (a draft to publish keeps its dialog). */
function AnswerHere({ id, data, t }) {
  const [answer, setAnswer] = useState("");
  if (t.draft) {
    return html`<div class="pool-task__answer"><span class="ok-tone-fire">${t.ork} ${say(`wants to publish to ${t.target || "a service"}`)}</span>
      <div class="ok-row"><button class="ok-btn primary" onClick=${() => openDialog(id, { kind: "answer", task: t.id })}>${say("Look at the draft")}</button></div></div>`;
  }
  const send = () => act(id, "answer", { task: t.id, text: answer }).then((rule) => {
    setAnswer("");
    if (rule) openDialog(id, { kind: "rule", rule });
  }, () => {});
  return html`<div class="pool-task__answer">
    <b class="ok-tone-fire">${data.keeper} ${say("asks")}</b>
    <pre class="gui-pre">${t.question}</pre>
    <textarea class="ok-input gui-textarea" rows="2" value=${answer} aria-label=${say("Your answer")} placeholder=${say("Your answer")}
      onInput=${(e) => setAnswer(e.target.value)}
      onKeyDown=${(e) => { if (e.key === "Enter" && (e.ctrlKey || e.metaKey) && answer.trim()) { e.preventDefault(); send(); } }}></textarea>
    <div class="ok-row"><button class="ok-btn primary" disabled=${!answer.trim()} onClick=${send}>Answer</button></div>
  </div>`;
}

/** A task open over the flow: ← back, its state, the question with the answer in place, its brief, diff, notes. */
function TaskDetail({ id, data, t }) {
  const diff = () => act(id, "diff", { task: t.id }).then((d) => openInLake({ text: d.text, title: d.title, from: id }), () => {});
  const back = () => setIn(chosen, id, null);
  return html`<div class="pool-task" onKeyDown=${(e) => { if (e.key === "Escape") { e.stopPropagation(); back(); } }}>
    <button class="ok-btn pool-task__back" onClick=${back}>← ${say("All tasks")} · ${data.tasks.length}</button>
    <div class="pool-task__head"><h3 class="ok-detail__head pool-task__title">${t.title}</h3>
      ${t.cost && html`<span class="ok-tone-muted">${t.cost}</span>`}</div>
    <p class="ok-detail__meta"><span class=${STATE_TONE[t.status] || ""}>● ${say(WORD[t.status] || t.status)}</span>
      ${[t.ork, t.branch, t.parts ? say(`planned in ${t.parts} parts`) : "", t.part ? say(`part ${t.part}`) : "",
         t.reworks ? `${t.reworks} rework${t.reworks > 1 ? "s" : ""}` : "", t.warm ? say("resumed its session") : "",
         t.scope === "local" ? say("local, no pull request") : "", t.wait_for ? `${say("waits for")} ${t.wait_for}` : ""]
        .filter(Boolean).map((x) => ` · ${x}`)}</p>
    ${t.asks && html`<${AnswerHere} key=${t.id} id=${id} data=${data} t=${t} />`}
    <div class="ok-detail__actions">
      ${t.branch && html`<button class="ok-btn" onClick=${diff}>Diff in Lake</button>`}
      <button class="ok-btn" onClick=${() => openInLake({ text: t.brief, title: `Brief — ${t.title}`, from: id })}>Brief in Lake</button>
      ${t.report && html`<button class="ok-btn" onClick=${() => openInLake({ text: t.report, title: `Report — ${t.title}`, from: id })}>Report in Lake</button>`}
      ${t.pr && html`<a class="ok-btn" href=${t.pr} target="_blank" rel="noreferrer">${say("Open PR")} ↗</a>`}
    </div>
    <${Text} label="Brief" text=${t.brief} />
    <${Text} label="Review notes" text=${t.notes} />
    <${Text} label="Error" text=${t.error} />
    ${t.qa.length > 0 && html`<p class="ok-detail__section">Questions</p>
      <ul class="gui-rows">${t.qa.map((x, i) => html`<li key=${i}><b>${x.q}</b><br />→ ${x.a} <span class="ok-tone-muted">· ${x.who}</span></li>`)}</ul>`}
    ${t.files.length > 0 && html`<p class="ok-detail__section">Files · ${t.files.length}</p>
      <ul class="gui-rows">${t.files.map((f) => html`<li key=${f} class="gui-link" onClick=${() => openInLake({ path: f, from: id })}>${f}</li>`)}</ul>`}
    <${Text} label="Report" text=${t.report} />
    ${t.decided && html`<p class="ok-detail__meta">The foreman: ${t.decided}</p>`}
  </div>`;
}

function Tasks({ id, data }) {
  const t = data.tasks.find((x) => x.id === chosen.value[id]);
  return t ? html`<${TaskDetail} key=${t.id} id=${id} data=${data} t=${t} />` : html`<${Flow} id=${id} data=${data} />`;
}

function OrkTab({ id, o }) {
  const s = sessionOf(o.terminal);
  const open = () => act(id, "terminal", { ork: o.name }).catch(() => {});
  if (s) return html`<${Terminal} key=${s.key} sessionKey=${s.key} />`;
  return html`<div class="gui-section">
    <p class="ok-tone-muted">${o.status === "working" ? say("It is working now: its terminal opens when it is free.") : say("No terminal open.")}
      ${o.status !== "working" && html` <button class="ok-btn" onClick=${open}
        title=${say("Its last session, on its worktree")}>${o.session ? say("Resume its session") : say("Open its terminal")}</button>`}</p>
    ${o.recent.length > 0 && html`<h3 class="ok-font-heading">${say("Its recent work")}</h3>
      <ul class="gui-rows">${o.recent.map((r, i) => html`<li key=${i}>${r}</li>`)}</ul>`}
  </div>`;
}

/** The orks' pane: a tab per ork (its head says how it is), the chosen one's terminal under them; ▾ folds it
 *  to the tabs, and it folds by itself while a task is open. */
function Orks({ id, data }) {
  if (!data.orks.length) return html`<p class="ok-tone-muted">${say("No orks yet — the steward hires them for the tasks.")}</p>`;
  const tab = tabs.value[id] || "";
  const ork = data.orks.find((o) => `ork:${o.name}` === tab)
    || data.orks.find((o) => o.asks) || data.orks.find((o) => o.status === "working") || data.orks[0];
  const fold = folded.value[id] ?? !!chosen.value[id];
  const pick = (o) => { setIn(tabs, id, `ork:${o.name}`); setIn(folded, id, false); };
  return html`<div class=${cls("pool-orks", { "is-folded": fold })}>
    <nav class="pool-orks__bar" role="tablist" aria-label=${say("Orks")}>
      ${data.orks.map((o) => html`<button key=${o.name} role="tab" aria-selected=${o === ork && !fold}
          class=${cls("ok-tab", { "is-active": o === ork && !fold })} onClick=${() => pick(o)}
          title=${o.asks ? say("asks you") : o.status === "working" ? say("at work") : say("resting")}>
        <${Head} ork=${o.name} asks=${o.asks} working=${o.status === "working"} />${o.name}</button>`)}
      <span class="pool-orks__about ok-font-status">${ork.label}${ork.tier ? ` · ${ork.tier}` : ""} · ✓${ork.done} ✗${ork.failed} · ${ork.cost}${ork.tokens ? ` · ${Math.round(ork.tokens / 1000)}k` : ""}</span>
      <button class="ok-btn" aria-label=${fold ? say("Show the terminal") : say("Fold the terminal")} title=${fold ? say("Show the terminal") : say("Fold the terminal")}
        onClick=${() => setIn(folded, id, !fold)}>${fold ? "▴" : "▾"}</button>
    </nav>
    ${!fold && html`<${OrkTab} key=${ork.name} id=${id} o=${ork} />`}
  </div>`;
}

function KeeperAsk({ id, keeper }) {
  const [ask, setAsk] = useState("");
  const send = () => askKeeper(id, ask).then((r) => { if (r !== null) setAsk(""); });
  return html`<div class="gui-section">
    <h3 class="ok-font-heading">Ask ${keeper} to change them</h3>
    <textarea class="ok-input gui-textarea" rows="2" value=${ask} placeholder=${say("In plain words: what the orks should always or never do, how the review should go…")}
      onInput=${(e) => setAsk(e.target.value)}></textarea>
    <div class="ok-row"><button class="ok-btn" disabled=${!ask.trim()} onClick=${send}>Ask ${keeper}</button></div>
  </div>`;
}

/** Rules, settings and the foreman's decisions: one line until opened — they are read rarely. */
function Rules({ id, data }) {
  const settings = [["Tests", data.test_cmd || "none — the review reads the diff only"], ["Steward", `${data.steward} · spent ${data.steward_cost}`],
    ["Providers", data.providers.join(", ")], ["Orks at most", data.max], ["Budget", data.budget || "none of its own"],
    ["Reworks at most", data.max_reworks], ["Worktrees", say(data.worktrees ? "one per ork" : "off: they work in the project")]];
  return html`<details class="pool-rules">
    <summary><span>${say("Rules")} ${data.rules.length} · ${say("Settings")} · ${say("Decisions")} ${data.decisions.length}</span>
      <span class="pool-rules__sum ok-font-status">${say("Tests")}: ${data.test_cmd || say("none")} · ${say("reworks")} ≤ ${data.max_reworks}${data.budget ? ` · ${data.budget}` : ""}</span></summary>
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
  </details>`;
}

/** The head: the counters on one line, Pause; the question waiting for you, with Answer; the dialogs live here. */
function PoolHead({ id, data }) {
  const queue = data.tasks.filter((t) => t.lane === "queue").length;
  const working = data.orks.filter((o) => o.status === "working").length;
  const done = data.tasks.filter((t) => t.status === "done").length, failed = data.tasks.filter((t) => t.status === "failed").length;
  const spent = parseFloat(String(data.spent).replace("$", "")) || 0, budget = parseFloat(String(data.budget).replace("$", "")) || 0;
  const ask = data.asked[0];
  return html`<div>
    <div class="pool-head">
      ${data.paused && html`<span class="ok-tone-wait">⚠ ${say("paused")}</span>`}
      <span><b>${working}/${data.max}</b> ${say("at work")}</span>
      <span><b>${queue}</b> ${say("queued")}</span>
      <span class="pool-head__spend"><b>${data.spent}</b>${data.budget ? html` ${say("of")} ${data.budget}
        <span class="pool-meter" aria-hidden="true"><i style=${`width:${Math.min(100, budget ? (spent / budget) * 100 : 0)}%`}></i></span>` : ""}</span>
      <span><b class=${done ? "ok-tone-ok" : ""}>✓${done}</b> <b class=${failed ? "ok-tone-error" : ""}>✗${failed}</b></span>
      <span class="pool-head__spacer"></span>
      <button class="ok-btn" onClick=${() => act(id, "pause").catch(() => {})}>${data.paused ? "Resume" : "Pause"}</button>
    </div>
    ${ask && html`<div class="pool-ask">
      <span class="pool-ask__who">? ${data.keeper} ${say("asks")}${data.asked.length > 1 ? ` · ${data.asked.length}` : ""}</span>
      <span class="pool-ask__what" title=${ask.question}>${ask.title}: ${ask.question}</span>
      <button class="ok-btn primary" onClick=${() => setIn(chosen, id, ask.id)}>Answer</button>
    </div>`}
  </div>`;
}

/** The window by its UI document (design/buildings/barracks.json). `task` shows nothing of its own: a task
 *  opens over the flow, in `lanes` (an older document that still has the pane loses nothing). */
export function panes(id, data) {
  return {
    head: () => html`<div class="gui-split"><${PoolHead} id=${id} data=${data} /><${NewTask} id=${id} /></div>`,
    lanes: () => html`<${Tasks} id=${id} data=${data} />`,
    task: () => null,
    orks: () => html`<${Orks} id=${id} data=${data} />`,
    rules: () => html`<${Rules} id=${id} data=${data} />`,
  };
}

/** Its quick actions, from its Info or its closed card: New task and Answer open their own small window,
 *  Pause / resume is done at once. */
export function quick(id, action) {
  if (action === "pool.task") { openDialog(id, { kind: "task" }); return true; }
  if (action === "pool.answer") { openDialog(id, { kind: "answer" }); return true; }
  if (action === "pool.pause") { act(id, "pause").catch(() => {}); return true; }
  return false;
}

/** Its dialogs, over the town, whether the building is open or not (js/types.js). */
function Peeked({ id }) {
  usePeek(id);
  return html`<${Dialogs} id=${id} data=${(details.value[id] || {}).data || {}} />`;
}

export function overlay() {
  return html`${Object.keys(dialogs.value).filter((id) => dialogs.value[id]).map((id) => html`<${Peeked} key=${id} id=${id} />`)}`;
}
