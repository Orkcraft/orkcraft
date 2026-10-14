// 🏕 The Agent pool: the orks and their tasks (docs/design/building-views.md §3). It has no Work window
// (docs/design/lighter-buildings.md §2): its card does its everyday job. Small, how many orks work of how many, the
// queue, the tally and the spend, the steward first when it asks; medium, a lane per role with its sessions as chips;
// large, under the lanes, a New task written in place and the open tasks as one flow of cards (the one that asks
// first), the finished ones folded to a line — a task opens over the flow (← back) with its answer written there.
// Each ork's session, its terminal and its history are its console (js/orkconsole.js); its rules, folder, kinds of
// work and settings are its Info (`settings`). The worker does it all (core/workers/barracks.py); documents open in
// the Inspector, the rules change through the keeper.
import { signal, effect } from "@preact/signals";
import { useState } from "preact/hooks";
import { html, cls } from "../html.js";
import { act, town, details, say } from "../link.js";
import { Dialog } from "../dialog.js";
import { openInLake } from "../lake.js";
import { askKeeper } from "../keeper.js";
import { usePeek, showOnCard } from "../windows.js";
import { OrkHead, TierMark } from "../icons.js";
import { showConsole, shownCart } from "../slots.js";

const sheet = new URL("./barracks.css", import.meta.url).href;
if (!document.querySelector(`link[href="${sheet}"]`)) {
  const link = document.createElement("link");
  link.rel = "stylesheet";
  link.href = sheet;
  document.head.appendChild(link);
}

export const work = false;         // no Work window: the card and the console do it (lighter-buildings.md §2)

const chosen = signal({});         // building id → the task open on its large card
const dialogs = signal({});        // building id → {kind: "task" | "answer" | "rule", …}


const setIn = (sig, id, value) => { sig.value = { ...sig.value, [id]: value }; };
const openDialog = (id, d) => setIn(dialogs, id, d);
const closeDialog = (id) => setIn(dialogs, id, null);

// -- dialogs ------------------------------------------------------------------------------------------

/** New task, at the top of its large card: one line written in place, no window and no title (its first words are
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
const LANE_STATE = { working: "busy", resting: "idle", asks: "alert" };

/** A press on a role's name or on one of its sessions (ork-console.md §14): it opens that session's console (js/slots.js,
 *  the key core/slots.py gives a pool's ork) — folded for one at work or asking, unfolded for a resting one, whose
 *  console is its history and its terminal. The role opens its first session, the asking one first. The rest of the
 *  lane is the hut's, to select or drag it. */
function openSession(e, id, s) {
  keep(e);
  showConsole(`${id}/${s.name.toLowerCase()}`, s.state === "resting" || s.state === "stopped");
}

// A console's cart link (ork-console.md §21): the task open on its pool's large card.
effect(() => {
  const want = shownCart.value;
  const b = want && (town.peek()?.buildings || []).find((x) => x.id === want.building);
  if (!b || b.type !== "barracks") return;
  shownCart.value = null;
  setIn(chosen, b.id, want.id);
  showOnCard(b.id);
});

/** Its roles, a lane each (docs/design/pool-roles.md): an ork is a role — "Grunt · tests" — and the orks hired as it
 *  are its sessions, a chip each in the one status (❓ asks, 💭 at work, Zz resting; Office says the word), the asking
 *  one first. Then its tier when its sessions share one, how many are at work, and how many tasks of it wait. */
function Lanes({ id, lanes, more }) {
  return html`<ul class="pool-lanes">${lanes.map((l) => html`<li key=${l.role} class=${cls("pool-lane", `is-${l.state}`)}
      title=${`${say(l.name)} · ${say(l.word)} · ${l.at_work} ${say("at work")}${l.queue ? ` · ${l.queue} ${say("waiting")}` : ""}`}>
    <span class="pool-lane__head"><${OrkHead} o=${{ name: l.ork, status: LANE_STATE[l.state] }} alert=${l.state === "asks"} /><span
      class="pool-lane__state">${say(l.word)}</span></span>
    <button type="button" class="pool-lane__name" onPointerDown=${keep} onClick=${(e) => openSession(e, id, l.sessions[0])}>${say(l.name)}</button>
    <span class="pool-lane__how">${l.tier && html`<${TierMark} tier=${l.tier} />`}</span>
    <span class="pool-lane__chips">${l.sessions.map((s) => html`<button key=${s.name} type="button"
        class=${cls("pool-chip", `is-${s.state}`)} data-ork=${s.name} title=${`${say(s.line)} · ${s.harness}`} aria-label=${say(s.line)}
        onPointerDown=${keep} onClick=${(e) => openSession(e, id, s)}>
      <span class="pool-chip__mark">${s.mark}</span><span class="pool-chip__word">${say(s.word)}</span></button>`)}${l.more > 0
      && html`<span class="pool-chip is-more ok-tone-muted">+${l.more}</span>`}</span>
    <span class=${cls("pool-lane__queue", { "ok-tone-muted": !l.at_work && !l.queue })}>${l.at_work || l.queue
      ? `${l.at_work} ${say("at work")} · ${l.queue} ${say("waiting")}` : "—"}</span>
  </li>`)}${more > 0 && html`<li class="pool-lane is-more ok-tone-muted">+${more}</li>`}</ul>`;
}

export function card(b, level = "s") {
  const c = b.card;
  if (!c) return null;
  if (level === "l") return html`<div class="gui-hut__body-in">${c.paused
      ? html`<div class="gui-hut__text ok-tone-wait">⚠ ${say("Paused")} · <button class="gui-link" onPointerDown=${keep}
          onClick=${(e) => { keep(e); act(b.id, "pause").catch(() => {}); }}>${say("Resume")}</button></div>`
      : html`<div class="gui-hut__text"><b>${c.active}</b> ${say(`of ${c.max} orks at work`)} · ${say("queue")} <b>${c.queue}</b>
          · <span class=${c.done ? "ok-tone-ok" : ""}>✓${c.done}</span> <span class=${c.failed ? "ok-tone-error" : ""}>✗${c.failed}</span> · <b>${c.spent}</b></div>`}
    ${(c.lanes || []).length > 0 && html`<${Lanes} id=${b.id} lanes=${c.lanes} more=${c.more || 0} />`}
    <${Large} id=${b.id} />
  </div>`;
  const working = c.working || [];
  const lanes = c.lanes || [];
  return html`<div class="gui-hut__body-in">
    ${c.paused
      ? html`<div class="gui-hut__big ok-tone-wait">⚠ ${say("Paused")}<small>${c.queue ? `${c.queue} waiting` : say("nothing waits")}</small></div>`
      : html`<div class="gui-hut__big">${c.active}<small>${say(`of ${c.max} orks at work`)}</small></div>`}
    <div class="gui-hut__text">${say("queue")} <b>${c.queue}</b> · <span class=${c.done ? "ok-tone-ok" : ""}>✓${c.done}</span>
      <span class=${c.failed ? "ok-tone-error" : ""} title=${c.failed ? say("Failed tasks: open the building to see why") : ""}>✗${c.failed}</span>
      · <b>${c.spent}</b></div>
    ${c.asks && html`<div class="gui-hut__text ok-tone-fire">? ${c.asks} ${say("asks")}</div>`}
    ${lanes.length > 0 && html`<${Lanes} id=${b.id} lanes=${lanes} more=${c.more || 0} />`}
    ${c.paused
      ? html`<div class="gui-hut__foot"><span>${say("Stopped: no task starts")}</span>
          <button class="ok-act gui-hut__act" onPointerDown=${keep}
            onClick=${(e) => { keep(e); act(b.id, "pause").catch(() => {}); }}><span class="ok-act__label">Resume</span></button></div>`
      : lanes.length > 0 ? null
      : working.length > 0
        ? html`<div class="gui-hut__foot"><span>⚒ <b>${working[0].ork}</b> · ${working[0].want ? `${say(working[0].want)}: ` : ""}${working[0].task}</span>
            ${working.length > 1 && html`<span class="gui-hut__when">+${working.length - 1}</span>`}</div>`
        : c.last && html`<div class="gui-hut__foot"><span><span class=${c.last.ok ? "ok-tone-ok" : "ok-tone-error"}>${c.last.ok ? "✓" : "✗"}</span> ${c.last.title}</span></div>`}
  </div>`;
}

/** Folded (docs/design/folded-cards.md): failed tasks first, else the orks at work, else the queue. */
export function mark(b) {
  const c = b.card;
  if (!c) return null;
  if (c.failed) return { text: `✗${c.failed}`, tone: "error" };
  if (c.active) return { text: `${c.active}/${c.max} at work` };
  return c.queue ? { text: `${c.queue} queued` } : null;
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

/** Its kind of work and where it was decided: `Reply · from External listeners` (docs/design/barracks-flows.md §9). */
function Want({ t }) {
  return html`${say(t.want)}${t.want_note ? ` · ${say(t.want_note)}` : ""}`;
}

/** Why a task waits, until when, and the way past it (ork-console.md §19): the line, and its button. An answer's
 *  way past is the answer card above it, so it gets none here. */
function WaitLine({ id, w }) {
  if (!w) return null;
  const skip = w.skip;
  const go = () => (skip.act === "open" ? setIn(chosen, id, skip.args.task) : act(id, skip.act, skip.args).catch(() => {}));
  return html`<p class="ok-detail__meta">⏳ ${w.line}
    ${skip && skip.label !== "Answer" && html` <button class="ok-btn" onClick=${go}>${skip.act === "open" ? `${skip.label} →` : say(skip.label)}</button>`}</p>`;
}

/** A task as a card: who and how it is on top, its title, its branch and cost under it. */
function TaskCard({ id, t, n }) {
  const working = t.status === "working" || t.status === "planned";
  return html`<button class=${cls("pool-card", { "is-asks": t.asks })} onClick=${() => setIn(chosen, id, t.id)}
      title=${t.title}>
    <span class=${`pool-card__state ${STATE_TONE[t.status] || ""}`}>
      ${t.ork ? html`<${Head} ork=${t.ork} asks=${t.asks} working=${working} /><span class="pool-card__who">${t.ork}</span> · ` : ""}
      ${t.status === "done" ? "✓ " : t.status === "failed" ? "✗ " : ""}${say(WORD[t.status] || t.status)}${n ? ` #${n}` : ""}
</span>
    <span class="pool-card__title">${t.title}</span>
    ${t.wait && html`<span class="pool-card__want ok-tone-muted">⏳ ${t.wait.line}</span>`}
    ${t.want && html`<span class="pool-card__want ok-tone-muted"><${Want} t=${t} /></span>`}
    ${(t.overlaps.length > 0 || t.against.length > 0) && html`<span class="pool-card__warn ok-tone-wait">
      ${t.held ? `⏸ ${say("waits for")} “${t.overlaps[0] ? t.overlaps[0].title : ""}”`
        : t.overlaps.length ? `⚠ ${say("overlaps")} “${t.overlaps[0].title}”${t.overlaps.length > 1 ? ` +${t.overlaps.length - 1}` : ""}`
        : `⚠ ${say("goes against a design brief")}`}</span>`}
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
  const send = (said = answer) => act(id, "answer", { task: t.id, text: said }).then((rule) => {
    setAnswer("");
    if (rule) openDialog(id, { kind: "rule", rule });
  }, () => {});
  // The ork's questions, each with its answers as buttons (ork-console.md §20): one question answers at a press,
  // several fill the field a line each.
  const qs = t.questions || [];
  const pick = (q, o) => (qs.length === 1 ? send(o) : setAnswer((a) => `${a ? `${a}\n` : ""}${q.text} → ${o}`));
  return html`<div class="pool-task__answer">
    <b class="ok-tone-fire">${t.ork || data.keeper} ${say("asks")}</b>
    ${qs.length ? qs.map((q, i) => html`<div key=${i} class="pool-task__question"><pre class="gui-pre">${q.text}</pre>
      ${q.options.length > 0 && html`<div class="ok-row">${q.options.map((o) => html`<button key=${o} class="ok-btn" onClick=${() => pick(q, o)}>${o}</button>`)}</div>`}</div>`)
      : html`<pre class="gui-pre">${t.question}</pre>`}
    <textarea class="ok-input gui-textarea" rows="2" value=${answer} aria-label=${say("Your answer")} placeholder=${say("Your answer")}
      onInput=${(e) => setAnswer(e.target.value)}
      onKeyDown=${(e) => { if (e.key === "Enter" && (e.ctrlKey || e.metaKey) && answer.trim()) { e.preventDefault(); send(); } }}></textarea>
    <div class="ok-row"><button class="ok-btn primary" disabled=${!answer.trim()} onClick=${() => send()}>Answer</button></div>
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
      ${t.want && html` · <${Want} t=${t} />`}
      ${[t.ork, t.branch, t.parts ? say(`planned in ${t.parts} parts`) : "", t.part ? say(`part ${t.part}`) : "",
         t.reworks ? `${t.reworks} rework${t.reworks > 1 ? "s" : ""}` : "", t.warm ? say("resumed its session") : "",
         t.scope === "local" ? say("local, no pull request") : "", t.wait_for ? `${say("waits for")} ${t.wait_for}` : ""]
        .filter(Boolean).map((x) => ` · ${x}`)}</p>
    <${WaitLine} id=${id} w=${t.wait} />
    ${t.asks && html`<${AnswerHere} key=${t.id} id=${id} data=${data} t=${t} />`}
    <div class="ok-detail__actions">
      ${t.branch && html`<button class="ok-btn" onClick=${diff}>Diff in Inspector</button>`}
      <button class="ok-btn" onClick=${() => openInLake({ text: t.brief, title: `Brief — ${t.title}`, from: id })}>Brief in Inspector</button>
      ${t.report && html`<button class="ok-btn" onClick=${() => openInLake({ text: t.report, title: `Report — ${t.title}`, from: id })}>Report in Inspector</button>`}
      ${t.pr && html`<a class="ok-btn" href=${t.pr} target="_blank" rel="noreferrer">${say("Open PR")} ↗</a>`}
      ${t.design && html`<button class="ok-btn" onClick=${() => openInLake({ path: t.design, from: id })}>Design brief in Inspector</button>`}
    </div>
    ${t.code_card && html`<p class="ok-tone-wait">${say("It reads like a code task: a card waits for you on the Task board —")} “${t.code_card}”</p>`}
    <${Overlaps} id=${id} t=${t} />
    <${Text} label="Brief" text=${t.brief} />
    <${Text} label="Review notes" text=${t.notes} />
    <${Text} label="Error" text=${t.error} />
    ${t.qa.length > 0 && html`<p class="ok-detail__section">Questions</p>
      <ul class="gui-rows">${t.qa.map((x, i) => html`<li key=${i}><b>${x.q}</b><br />→ ${x.a} <span class="ok-tone-muted">· ${x.who}</span></li>`)}</ul>`}
    ${t.files.length > 0 && html`<p class="ok-detail__section">Files · ${t.files.length}</p>
      <ul class="gui-rows">${t.files.map((f) => html`<li key=${f} class="gui-link" onClick=${() => openInLake({ path: f, from: id })}>${f}</li>`)}</ul>`}
    ${(t.assumptions || []).length > 0 && html`<p class="ok-detail__section">${say("Assumptions")} · ${t.assumptions.length}</p>
      <ul class="gui-rows">${t.assumptions.map((a, i) => html`<li key=${i}>${a}</li>`)}</ul>`}
    <${Text} label="Report" text=${t.report} />
    ${t.decided && html`<p class="ok-detail__meta">The foreman: ${t.decided}</p>`}
  </div>`;
}

/** Other tasks on its area, the design briefs it goes against or met (docs/design/barracks-designs.md). */
function Overlaps({ id, t }) {
  const brief = (path) => html`<span class="gui-link" onClick=${() => openInLake({ path, from: id })}>${path}</span>`;
  return html`
    ${t.overlaps.length > 0 && html`<p class="ok-detail__section">Overlaps · ${t.overlaps.length}</p>
      <ul class="gui-rows">${t.overlaps.map((o) => html`<li key=${o.key}><b>${o.title}</b>
        <span class="ok-tone-muted"> · ${o.paths.join(", ")} · ${say(o.status === "work" ? "being built" : "waits to be merged")}</span>
        ${o.pr && html` · <a class="gui-link" href=${o.pr} target="_blank" rel="noreferrer">PR ↗</a>`}
        ${o.brief && html` · ${brief(o.brief)}`}
        ${o.conflicts.length > 0 && html`<br /><span class="ok-tone-error">${say("Merged together they conflict in")} ${o.conflicts.join(", ")}</span>`}</li>`)}</ul>`}
    ${t.against.length > 0 && html`<p class="ok-detail__section">Goes against a design brief</p>
      <ul class="gui-rows">${t.against.map((c) => html`<li key=${c.with}>${brief(c.with)}<span class="ok-tone-muted"> · ${c.why}</span></li>`)}</ul>`}
    ${t.designs.length > 0 && html`<p class="ok-detail__section">Design briefs it met</p>
      <ul class="gui-rows">${t.designs.map((d) => html`<li key=${d.path}>${brief(d.path)}
        <span class=${d.state === "not confirmed" ? "ok-tone-wait" : "ok-tone-muted"}> · ${say(d.state)}</span></li>`)}</ul>`}`;
}

/** The repository's areas in work: every open task's files, this pool's and the others'. */
function Areas({ id, areas }) {
  if (!areas.length) return html`<p class="ok-tone-muted">${say("No areas in work: no open task claims files.")}</p>`;
  return html`<ul class="gui-rows">${areas.map((a) => html`<li key=${a.building + a.task}><b>${a.title}</b>
    <span class="ok-tone-muted"> · ${a.paths.join(", ")}${a.guessed ? ` (${say("a guess")})` : ""} · ${say(a.status === "work" ? "being built" : "waits to be merged")}
      ${a.mine ? "" : ` · ${a.building}`}</span>
    ${a.brief && html` · <span class="gui-link" onClick=${() => openInLake({ path: a.brief, from: id })}>${a.brief}</span>`}</li>`)}</ul>`;
}

function Tasks({ id, data }) {
  const t = data.tasks.find((x) => x.id === chosen.value[id]);
  return t ? html`<${TaskDetail} key=${t.id} id=${id} data=${data} t=${t} />` : html`<${Flow} id=${id} data=${data} />`;
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

/** The kinds of work it takes and its table source → kind of work (docs/design/barracks-flows.md §5, §9): a cart
 *  whose building named no kind takes its source's; a kind it does not take goes back as not mine. */
function Kinds({ id, kinds }) {
  const takes = (k, on) => act(id, "wants", { wants: kinds.all.map((x) => x.id).filter((x) => (x === k ? on : kinds.wants.includes(x))) }).catch(() => {});
  return html`<section class="gui-section pool-kinds"><h3 class="ok-font-heading">${say("Kinds of work")}</h3>
    <p class="ok-tone-muted">${say("What it takes. A reply is drafted by one light ork that only reads, and goes to the Review gate; another kind goes back as not mine.")}</p>
    <div class="ok-row">${kinds.all.map((k) => html`<label key=${k.id} class="pool-kinds__take">
      <input type="checkbox" checked=${kinds.wants.includes(k.id)} onChange=${(e) => takes(k.id, e.target.checked)} />${say(k.label)}</label>`)}</div>
    ${kinds.table.length > 0 && html`<p class="ok-tone-muted">${say("When the building it came from names no kind:")}</p>
      <ul class="gui-rows">${kinds.table.map((r) => html`<li key=${r.source} class="pool-kinds__row">
        <span>${say(r.title)}</span> →
        <select class="ok-input" value=${r.own ? r.want : ""} aria-label=${`${say("Kind of work")}: ${say(r.title)}`}
          onChange=${(e) => act(id, "want_by_source", { source: r.source, want: e.target.value }).catch(() => {})}>
          <option value="">${r.want && !r.own ? `${say(kinds.all.find((k) => k.id === r.want)?.label || r.want)} (${say("default")})` : say("The sort decides")}</option>
          ${kinds.all.map((k) => html`<option key=${k.id} value=${k.id}>${say(k.label)}</option>`)}
        </select></li>`)}</ul>`}
  </section>`;
}

/** The folder of code its orks work in (`repo`): the town's own, or a project of yours somewhere else — the system's
 *  folder dialog, a path pasted, or one of the recent folders. Taken for the next ork it hires. */
function Folder({ id, data }) {
  const [typed, setTyped] = useState("");
  const [waiting, setWaiting] = useState(false);
  const [hint, setHint] = useState("");
  const set = (path) => act(id, "repo", { path }).then(() => { setTyped(""); setHint(""); }, () => {});
  const choose = () => {
    setWaiting(true); setHint("");
    act(id, "pick", { start: data.repo }).then((token) => {
      const poll = () => act(id, "picked", { token }).then((r) => {
        if (r.state === "open") { setTimeout(poll, 400); return; }
        setWaiting(false);
        if (r.state === "done") set(r.path);
        else if (r.state === "error") setHint(say("No folder dialog here: paste the folder's path."));
      }, () => setWaiting(false));
      poll();
    }, () => setWaiting(false));
  };
  const others = (data.recent || []).filter((f) => f !== data.repo).slice(0, 4);
  return html`<section class="gui-section pool-folder"><h3 class="ok-font-heading">${say("Folder")}</h3>
    <p class="ok-font-status"><code>${data.repo}</code>${!data.repo_own && html`<span class="ok-tone-muted"> · ${data.repo_project
      ? `${say("the orkspace's project")}: ${data.repo_project}` : say("the town's own")}</span>`}</p>
    <p class="ok-font-status ok-tone-muted">${say("Where its orks work: their branches, worktrees, tests and pull requests. A folder with no git gets one when the first ork starts. The next ork it hires takes it.")}</p>
    <div class="gui-form__row">
      <button class="ok-btn" disabled=${waiting} onClick=${choose}>${say(waiting ? "Choosing…" : "Choose…")}</button>
      <input class="ok-input" value=${typed} placeholder=${say("or paste a folder's path")} aria-label=${say("Folder path")}
        onInput=${(e) => setTyped(e.target.value)} onKeyDown=${(e) => e.key === "Enter" && typed.trim() && set(typed.trim())} />
      ${data.repo_own && html`<button class="ok-btn" onClick=${() => set("")}>${say(data.repo_project ? "The orkspace's project" : "The town's own")}</button>`}
    </div>
    ${hint && html`<p class="ok-font-status ok-tone-wait">${hint}</p>`}
    ${others.length > 0 && html`<p class="ok-font-status">${say("Recent")}: ${others.map((f, i) => html`${i ? " · " : ""}<button key=${f}
        class="gui-link" onClick=${() => set(f)}>${f}</button>`)}</p>`}
  </section>`;
}

/** Rules, settings and the foreman's decisions: one line until opened — they are read rarely. */
function Rules({ id, data }) {
  const settings = [["Tests", data.test_cmd || "none — the review reads the diff only"], ["Steward", `${data.steward} · spent ${data.steward_cost}`],
    ["Providers", data.providers.join(", ")], ["Orks at most", data.max], ["Budget", data.budget || "none of its own"],
    ["Reworks at most", data.max_reworks], ["Worktrees", say(data.worktrees ? "one per ork" : "off: they work in the project")]];
  return html`<details class="pool-rules">
    <summary><span>${say("Rules")} ${data.rules.length} · ${say("Settings")} · ${say("Areas in work")} ${data.areas.length} · ${say("Decisions")} ${data.decisions.length}</span>
      <span class="pool-rules__sum ok-font-status">${say("Tests")}: ${data.test_cmd || say("none")} · ${say("reworks")} ≤ ${data.max_reworks}${data.budget ? ` · ${data.budget}` : ""}</span></summary>
    <section class="gui-section"><h3 class="ok-font-heading">Rules</h3>
      <p class="ok-tone-muted">${data.keeper}, the steward, answers the orks' questions from them and reviews every task.</p>
      ${data.rules.length ? html`<ul class="gui-rows">${data.rules.map((r, i) => html`<li key=${i}>${r.replace(/^-\s*/, "")}</li>`)}</ul>`
        : html`<p class="ok-tone-muted">None yet — answers you give can become rules.</p>`}</section>
    <${KeeperAsk} id=${id} keeper=${data.keeper} />
    <${Folder} id=${id} data=${data} />
    <section class="gui-section"><h3 class="ok-font-heading">Settings</h3>
      <ul class="gui-rows">${settings.map(([k, v]) => html`<li key=${k}><span class="ok-tone-muted">${say(k)}</span> · ${v}</li>`)}</ul></section>
    <${Kinds} id=${id} kinds=${data.kinds} />
    <section class="gui-section"><h3 class="ok-font-heading">Areas in work</h3>
      <p class="ok-tone-muted">${say("The files open tasks change, until their pull requests are merged. A new task on an area being built waits for it.")}</p>
      <${Areas} id=${id} areas=${data.areas} /></section>
    <section class="gui-section"><h3 class="ok-font-heading">Decisions</h3>
      ${data.decisions.length ? html`<ul class="gui-rows">${data.decisions.map((d, i) => html`<li key=${i}>
        <span class="ok-tone-muted">${d.at}</span> <span class="ok-tone-wait">${d.action}</span>${d.ork ? ` ${d.ork}` : ""}
        <span class="ok-tone-muted"> · ${d.why}</span></li>`)}</ul>`
        : html`<p class="ok-tone-muted">None yet — a road brings tasks here.</p>`}</section>
  </details>`;
}

/** Its large card's everyday job (lighter-buildings.md §2): New task written in place, the open tasks as one flow
 *  with why each waits, a task opened over the flow with its answer written there. A press inside is the card's, never
 *  the hut's (no drag, no select). */
function Large({ id }) {
  usePeek(id);
  const d = details.value[id];
  const data = d && d.data;
  if (!data || !data.tasks) return html`<p class="ok-tone-muted">${say("Opening…")}</p>`;
  return html`<div class="pool-large" onPointerDown=${keep} onClick=${keep} onDblClick=${keep}>
    <${NewTask} id=${id} />
    <${Tasks} id=${id} data=${data} />
  </div>`;
}

/** Its settings, in its Info (lighter-buildings.md §2): the rules, the folder, the kinds of work, the settings, the
 *  areas in work and the foreman's decisions, as they were in its Work. */
export function settings(id, data) {
  if (!data || !data.rules) return null;
  return html`<${Rules} id=${id} data=${data} />`;
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
