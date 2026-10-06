// 🪔 Clan Fire: a review of a document by the clan, three ways (docs/design/building-views.md §3).
// Closed: only the review's state — its cycle, the tally and the spend while it runs, else how it ended,
// and what waits in line. Command: the members and their verdicts, the document and the last turns;
// Review, Add member, Answer. Full: the members, the review turn by turn and cycle by cycle, the document
// with its comments, the report and the past reviews, each a pane of its UI document
// (design/buildings/council.json). The worker does it (core/workers/council.py); the
// document opens in Lake, briefs and rules change through the keeper.
import { signal } from "@preact/signals";
import { useState } from "preact/hooks";
import { html, cls } from "../html.js";
import { act, say } from "../link.js";
import { Dialog } from "../dialog.js";
import { openInLake } from "../lake.js";
import { askKeeper } from "../keeper.js";

const dialogs = signal({});        // building id → "review" | "member" | "answer"
const past = signal({});           // building id → a past review shown in place of the current one
const side = signal({});           // building id → "document" | "report"

const VERDICT = { approve: "approves", changes: "asks for changes", veto: "vetoes", rework: "sends it back",
                  ask: "asks you", "": "" };
const TONE = { approve: "ok-tone-ok", changes: "ok-tone-wait", veto: "ok-tone-error", rework: "ok-tone-wait",
               ask: "ok-tone-fire", approved: "ok-tone-ok", asked: "ok-tone-fire", error: "ok-tone-error",
               running: "ok-tone-wait", budget: "ok-tone-wait" };

const SHOWN = 4;                  // members the Command Card lists (the rest: +N more)
const setIn = (sig, id, value) => { sig.value = { ...sig.value, [id]: value }; };
const firstLine = (text) => (text || "").split("\n").find((l) => l.trim()) || "";

function openDoc(id, r) {
  return openInLake(r.doc_path ? { path: r.doc_path, title: r.title, from: id } : { text: r.doc, title: r.title, from: id });
}

// -- dialogs ------------------------------------------------------------------------------------------

function ReviewDialog({ id, busy, onClose }) {
  const [what, setWhat] = useState("");
  return html`<${Dialog} title=${say("What should the clan review?")}
      text=${busy ? "A review is under way: this one waits in line." : "A path in the project, or the text itself."} onCancel=${onClose}
      actions=${html`<button class="ok-btn" onClick=${onClose}>Cancel</button>
        <button class="ok-btn primary" disabled=${!what.trim()} onClick=${() => act(id, "review", { text: what }).then(onClose, () => {})}>Review it</button>`}>
    <textarea class="ok-input gui-textarea" rows="6" value=${what} autofocus placeholder=${say("docs/plan.md — or paste the text")}
      onInput=${(e) => setWhat(e.target.value)}></textarea>
  </${Dialog}>`;
}

function MemberDialog({ id, onClose }) {
  const [role, setRole] = useState("");
  const [harness, setHarness] = useState("claude");
  const add = () => act(id, "add_member", { role, harness }).then(onClose, () => {});
  return html`<${Dialog} title=${say("Add a member of the clan")} text=${say("Its brief is a file: what it checks, what it knows, its red lines.")}
      onCancel=${onClose}
      actions=${html`<button class="ok-btn" onClick=${onClose}>Cancel</button>
        <button class="ok-btn primary" disabled=${!role.trim()} onClick=${add}>Add it</button>`}>
    <p class="ok-dialog__section">Role</p>
    <input class="ok-input" value=${role} autofocus placeholder=${say("Marketing")} onInput=${(e) => setRole(e.target.value)} />
    <p class="ok-dialog__section">Model</p>
    <input class="ok-input" value=${harness} placeholder=${say("claude · agy · codex · agy:gemini-3.1-pro-high")}
      onInput=${(e) => setHarness(e.target.value)} onKeyDown=${(e) => e.key === "Enter" && role.trim() && add()} />
  </${Dialog}>`;
}

function AnswerDialog({ id, question, onClose }) {
  const [answer, setAnswer] = useState("");
  return html`<${Dialog} title=${say("The steward asks")} onCancel=${onClose}
      actions=${html`<button class="ok-btn" onClick=${onClose}>Later</button>
        <button class="ok-btn primary" disabled=${!answer.trim()} onClick=${() => act(id, "answer", { text: answer }).then(onClose, () => {})}>Answer</button>`}>
    <pre class="gui-pre">${question}</pre>
    <textarea class="ok-input gui-textarea" rows="4" value=${answer} autofocus onInput=${(e) => setAnswer(e.target.value)}></textarea>
  </${Dialog}>`;
}

function Dialogs({ id, data }) {
  const d = dialogs.value[id];
  const close = () => setIn(dialogs, id, null);
  if (d === "review") return html`<${ReviewDialog} id=${id} busy=${data.busy} onClose=${close} />`;
  if (d === "member") return html`<${MemberDialog} id=${id} onClose=${close} />`;
  if (d === "answer" && data.current && data.current.question) return html`<${AnswerDialog} id=${id} question=${data.current.question} onClose=${close} />`;
  return null;
}

function Acts({ id, data }) {
  const asks = data.current && data.current.outcome === "asked";
  return html`${asks && html`<button class="ok-act" onClick=${() => setIn(dialogs, id, "answer")}><span class="ok-act__label">Answer</span></button>`}
    <button class="ok-act" onClick=${() => setIn(dialogs, id, "review")}><span class="ok-act__label">Review</span></button>
    <button class="ok-act" onClick=${() => setIn(dialogs, id, "member")}><span class="ok-act__label">Add member</span></button>`;
}

// -- closed ------------------------------------------------------------------------------------------

/** Closed: `cycle 2/3 · 3 ✓ 1 ✗ · $0.40` while it reviews, else how the last one ended; `N queued`. */
export function card(b) {
  const c = b.card;
  if (!c) return null;
  return html`<div>
    ${c.state === "none" ? html`<div class="ok-tone-muted">no review yet</div>`
      : c.state === "running" ? html`<div>cycle ${c.cycle}/${c.max} · ${c.ok} ✓ ${c.no} ✗ · ${c.spent}</div>`
      : html`<div class=${TONE[c.state] || ""}>${c.outcome}${c.route ? ` → ${c.route}` : ""}</div>`}
    ${c.queued > 0 && html`<div>${c.queued} queued</div>`}
  </div>`;
}

// -- command -----------------------------------------------------------------------------------------

function Member({ m }) {
  return html`<li><b>${m.role}</b>${m.tier && html` <span class="ok-tone-muted">${m.tier}</span>`}
    ${m.veto && html` <span class="ok-word">veto</span>`}
    <span class="ok-tone-muted"> · ${m.label}</span>
    ${m.verdict && html` · <span class=${TONE[m.verdict] || ""}>${VERDICT[m.verdict] || m.verdict}</span>`}</li>`;
}

/** Where a routed review went: `→ human`. */
const routed = (r) => (r && r.route ? ` → ${r.route}` : "");

/** Command: the members (role, tier, veto, verdict now), the document under review and the last turns. */
export function preview(id, data) {
  if (data.routes && data.routes.length && data.current) return html`<${Triage} id=${id} data=${data} />`;
  const r = data.current;
  const more = data.members.length - SHOWN;
  return html`<div class="gui-section">
    ${r && r.outcome === "asked" && html`<p class="ok-tone-fire gui-alert">The steward asks: ${firstLine(r.question).slice(0, 160)}</p>`}
    <div class="ok-row"><${Acts} id=${id} data=${data} /></div>
    <ul class="gui-rows">${data.members.slice(0, SHOWN).map((m) => html`<${Member} key=${m.role} m=${m} />`)}
      ${more > 0 && html`<li class="ok-tone-muted">+${more} more</li>`}
      ${!data.members.length && html`<li class="ok-tone-muted">No members yet — Add member</li>`}</ul>
    ${r ? html`<div class="gui-head">
        <span class="gui-head__what gui-link" title=${say("Open it in Lake")} onClick=${() => openDoc(id, r)}><b>${r.title}</b></span>
        <span class=${cls("gui-head__note", { [TONE[r.outcome] || ""]: true })}>cycle ${r.cycle}/${data.max_cycles} · ${r.outcome_word}${routed(r)} · ${r.spent}</span></div>
      <ul class="gui-rows">${r.turns.slice(-3).map((t, i) => html`<li key=${i}><b>${t.role}</b>
        <span class=${TONE[t.verdict] || "ok-tone-muted"}> ${VERDICT[t.verdict] ?? t.verdict}</span>
        <span class="ok-tone-muted"> · ${firstLine(t.text).slice(0, 100)}</span></li>`)}</ul>`
      : html`<p class="ok-tone-muted">No review yet — send a document down a road, or Review.</p>`}
    ${data.queued.length > 0 && html`<div class="ok-tone-muted">${data.queued.length} queued</div>`}
    <${Dialogs} id=${id} data=${data} />
  </div>`;
}

/** Command, for a clan that routes (triage): what came in, what each member found, and who takes it on. */
function Triage({ id, data }) {
  const r = data.current;
  const decided = r.turns.filter((t) => t.kind === "decide").slice(-1)[0];
  return html`<div class="gui-section">
    ${r.outcome === "asked" && html`<p class="ok-tone-fire gui-alert">The steward asks: ${firstLine(r.question).slice(0, 160)}</p>`}
    <div class="ok-row"><${Acts} id=${id} data=${data} /></div>
    <div class="gui-head"><span class="gui-head__what gui-link" title=${say("Open it in Lake")} onClick=${() => openDoc(id, r)}>
      <b>${r.title}</b></span></div>
    <ul class="gui-rows">${data.members.slice(0, SHOWN + 2).map((m) => html`<li key=${m.role}><b>${m.role}</b>
      <span class=${m.says ? TONE[m.verdict] || "" : "ok-tone-muted"}> · ${m.says || say("reading…")}</span></li>`)}</ul>
    ${decided ? html`<p><b>${say("Steward")}</b> <b class=${TONE[r.outcome] || ""}>${r.route ? `→ ${r.route}` : r.outcome_word}</b>${
        r.task ? html` · <b>${r.task}</b>` : ""}</p>
        <p>${r.when && html`<b>${r.when}</b> · `}<span class="ok-tone-muted">${firstLine(decided.text).slice(0, 140)}</span></p>`
      : html`<p class="ok-tone-muted">${say("The steward decides when every member has spoken.")}</p>`}
    ${data.queued.length > 0 && html`<div class="ok-tone-muted">${data.queued.length} queued</div>`}
    <${Dialogs} id=${id} data=${data} />
  </div>`;
}

// -- full --------------------------------------------------------------------------------------------

function Members({ id, data }) {
  const [ask, setAsk] = useState("");
  const brief = (path, who) => openInLake({ path, title: `Brief — ${who}`, from: id });
  return html`<section class="gui-section">
      <h3 class="ok-font-heading">The clan</h3>
      <ul class="gui-rows">
        <li><b>Steward</b> <span class="ok-tone-muted">· ${data.steward.label} · decides</span>
          <span class="gui-link" onClick=${() => brief(data.steward.brief, "Steward")}> · brief${data.steward.briefed ? "" : " (empty)"}</span></li>
        ${data.members.map((m) => html`<li key=${m.role}><b>${m.role}</b>${m.tier && html` <span class="ok-tone-muted">${m.tier}</span>`}
          ${m.veto && html` <span class="ok-word">veto</span>`}<span class="ok-tone-muted"> · ${m.label}</span>
          ${m.verdict && html` · <span class=${TONE[m.verdict] || ""}>${VERDICT[m.verdict]}</span>`}
          <span class="gui-link" onClick=${() => brief(m.brief, m.role)}> · brief${m.briefed ? "" : " (empty)"}</span></li>`)}
      </ul>
      <p class="ok-tone-muted">At most ${data.max_cycles} cycles and ${data.budget} a review.</p>
    </section>
    <section class="gui-section">
      <h3 class="ok-font-heading">Ask the keeper</h3>
      <textarea class="ok-input gui-textarea" rows="3" value=${ask} placeholder=${say("In plain words: a member's brief, who holds a veto, when the steward should ask you…")}
        onInput=${(e) => setAsk(e.target.value)}></textarea>
      <div class="ok-row"><button class="ok-btn" disabled=${!ask.trim()} onClick=${() => askKeeper(id, ask).then((r) => { if (r !== null) setAsk(""); })}>Ask</button></div>
    </section>`;
}

function Turns({ turns, open }) {
  return html`<ul class="gui-rows">${turns.map((t, i) => html`<li key=${i}>
    <details open=${open && i >= turns.length - 2}>
      <summary><b>${t.kind === "decide" ? say("Steward") : t.role}</b>
        <span class=${TONE[t.verdict] || "ok-tone-muted"}> ${t.kind === "answer" ? "answers" : VERDICT[t.verdict] ?? t.verdict}</span>
        <span class="ok-tone-muted">${t.note ? ` · ${t.note}` : ""}${t.cost ? ` · ${t.cost}` : ""}${t.at ? ` · ${t.at}` : ""}</span></summary>
      <div class="gui-prose" dangerouslySetInnerHTML=${{ __html: t.html }}></div>
    </details></li>`)}</ul>`;
}

function Discussion({ data, r }) {
  return html`<section class="gui-section">
    <h3 class="ok-font-heading">The review, turn by turn</h3>
    ${data.cycles.map((c) => html`<details key=${c.id}>
      <summary>Cycle ${c.cycle} <span class=${TONE[c.outcome] || "ok-tone-muted"}>· ${c.outcome_word}</span>
        <span class="ok-tone-muted"> · ${c.ok} ✓ ${c.no} ✗ · ${c.spent} · ${c.started}</span></summary>
      <${Turns} turns=${c.turns} open=${false} />
    </details>`)}
    <h3 class="ok-font-heading">Cycle ${r.cycle} <span class=${TONE[r.outcome] || "ok-tone-muted"}>· ${r.outcome_word}</span></h3>
    ${r.turns.length ? html`<${Turns} turns=${r.turns} open=${true} />` : html`<p class="ok-tone-muted">The clan reads it…</p>`}
    ${r.question && html`<p class="ok-tone-fire">The steward asks you.</p>`}
    ${r.error && html`<p class="ok-tone-error">${r.error}</p>`}
  </section>`;
}

function Paper({ id, r }) {
  const at = side.value[id] || "document";
  const comments = r.turns.filter((t) => t.kind !== "answer");
  return html`<div class="gui-split">
    <nav class="ok-tabs" role="tablist">
      <button class=${cls("ok-tab", { "is-active": at === "document" })} onClick=${() => setIn(side, id, "document")}>The document</button>
      <button class=${cls("ok-tab", { "is-active": at === "report" })} onClick=${() => setIn(side, id, "report")}>The report</button>
      <span class="gui-head__spacer"></span>
      <button class="ok-act" onClick=${() => (at === "report" ? openInLake({ text: r.report, title: `Report — ${r.title}`, from: id }) : openDoc(id, r))}>
        <span class="ok-act__label">Open in Lake</span></button>
    </nav>
    ${at === "report" ? html`<div class="gui-prose" dangerouslySetInnerHTML=${{ __html: r.report_html }}></div>`
      : html`<div class="gui-split is-row">
          <div class="gui-pane" style="flex: 3 1 0"><div>
            ${r.doc_path && html`<p class="ok-tone-muted">${r.doc_path}</p>`}
            <div class="gui-prose" dangerouslySetInnerHTML=${{ __html: r.doc_html }}></div></div></div>
          <div class="gui-pane" style="flex: 2 1 0"><div>
            <h3 class="ok-font-heading">Comments</h3>
            ${comments.length ? html`<ul class="gui-rows">${comments.map((t, i) => html`<li key=${i}>
                <b>${t.kind === "decide" ? say("Steward") : t.role}</b> <span class=${TONE[t.verdict] || ""}>${VERDICT[t.verdict] ?? t.verdict}</span>
                <div class="gui-prose" dangerouslySetInnerHTML=${{ __html: t.html }}></div></li>`)}</ul>`
              : html`<p class="ok-tone-muted">No comments yet.</p>`}</div></div>
        </div>`}
  </div>`;
}

function History({ id, data }) {
  if (!data.history.length && !data.queued.length) return null;
  const show = (h) => act(id, "show", { review: h.id }).then((r) => setIn(past, id, r), () => {});
  return html`${data.queued.length > 0 && html`<section class="gui-section"><h3 class="ok-font-heading">Waiting in line</h3>
      <ul class="gui-rows">${data.queued.map((t, i) => html`<li key=${i}>· ${t}</li>`)}</ul></section>`}
    ${data.history.length > 0 && html`<section class="gui-section"><h3 class="ok-font-heading">Past reviews</h3>
      <ul class="gui-rows">${data.history.map((h) => html`<li key=${h.id} class="gui-link" onClick=${() => show(h)}>
        ${h.title} <span class=${TONE[h.outcome] || "ok-tone-muted"}>· ${h.outcome_word}</span>
        <span class="ok-tone-muted"> · cycle ${h.cycle} · ${h.spent} · ${h.started}</span></li>`)}</ul></section>`}`;
}

/** The head: the review shown (current or past), Stop, the acts; the dialogs live here (the pane is always there). */
function Head({ id, data }) {
  const shown = past.value[id];
  const r = shown || data.current;
  return html`<div class="gui-head">
    ${r ? html`<span class="gui-head__what"><b>${r.title}</b>
        <span class=${TONE[r.outcome] || "ok-tone-muted"}> · cycle ${r.cycle}/${data.max_cycles} · ${r.outcome_word} · ${r.spent}</span></span>`
      : html`<span class="gui-head__what ok-tone-muted">No review yet — send a document down a road, or Review.</span>`}
    ${shown && html`<button class="ok-act" onClick=${() => setIn(past, id, null)}><span class="ok-act__label">Back to the current review</span></button>`}
    <span class="gui-head__spacer"></span>
    ${data.busy && html`<button class="ok-act" onClick=${() => act(id, "stop").catch(() => {})}><span class="ok-act__label">Stop</span></button>`}
    <${Acts} id=${id} data=${data} />
    <${Dialogs} id=${id} data=${data} />
  </div>`;
}

/** The full window by its UI document (design/buildings/council.json). A past review picked in the
 * history takes the current one's place in the review and the document. */
export function panes(id, data) {
  const shown = past.value[id];
  const r = shown || data.current;
  const none = html`<p class="ok-tone-muted">The review shows here turn by turn, each member's verdict and the steward's decision.</p>`;
  return {
    head: () => html`<${Head} id=${id} data=${data} />`,
    members: () => html`<div><${Members} id=${id} data=${data} /></div>`,
    history: () => (data.history.length || data.queued.length ? html`<div><${History} id=${id} data=${data} /></div>` : null),
    review: () => (r ? html`<${Discussion} data=${shown ? { cycles: [] } : data} r=${r} />` : none),
    document: () => (r ? html`<${Paper} id=${id} r=${r} />` : html`<p class="ok-tone-muted">The document under review shows here, with the clan's comments.</p>`),
  };
}
