// 🪔 Clan Fire: a review of a document by the clan, three ways (docs/design/building-views.md §3).
// Closed: the review's state — its cycle, the tally and the spend while it runs, else how it ended — what
// it reviews and the last turn. Open, made for the half panel: the review on one line with Review and
// Stop, the question waiting for you as a strip with Answer, the clan as a row of chips (each one's
// verdict now, a click opens its brief), then the review itself — turn by turn, the document, the
// report, as tabs taking the room — and the past reviews, the line and the steward's rules folded to
// one line at the bottom; each a pane of its UI document (design/buildings/council.json). The worker
// does it (core/workers/council.py); the document opens in Lake, briefs and rules change through the
// keeper.
import { signal } from "@preact/signals";
import { useState } from "preact/hooks";
import { html, cls } from "../html.js";
import { act, say } from "../link.js";
import { Dialog } from "../dialog.js";
import { openInLake } from "../lake.js";
import { askKeeper } from "../keeper.js";

const sheet = new URL("./council.css", import.meta.url).href;
if (!document.querySelector(`link[href="${sheet}"]`)) {
  const link = document.createElement("link");
  link.rel = "stylesheet";
  link.href = sheet;
  document.head.appendChild(link);
}

const dialogs = signal({});        // building id → "review" | "member" | "answer"
const past = signal({});           // building id → a past review shown in place of the current one
const side = signal({});           // building id → "review" | "document" | "report"

const MARK = { approve: "✓", changes: "⚠", veto: "✗", rework: "↩", ask: "?" };
const VERDICT = { approve: "approves", changes: "asks for changes", veto: "vetoes", rework: "sends it back",
                  ask: "asks you", "": "" };
const TONE = { approve: "ok-tone-ok", changes: "ok-tone-wait", veto: "ok-tone-error", rework: "ok-tone-wait",
               ask: "ok-tone-fire", approved: "ok-tone-ok", asked: "ok-tone-fire", error: "ok-tone-error",
               running: "ok-tone-wait", budget: "ok-tone-wait" };

const setIn = (sig, id, value) => { sig.value = { ...sig.value, [id]: value }; };

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

// -- closed ------------------------------------------------------------------------------------------

const BIG = { approved: "✓", rework: "↩", budget: "⚠", asked: "?", error: "✗", stopped: "■" };

/** Closed: the headline is the state — the cycle and the tally while it reviews (a triage: how many have
 *  spoken), else how it ended; under it what it reviews and the line; the foot the last turn and when. */
export function card(b) {
  const c = b.card;
  if (!c) return null;
  const last = c.last;
  return html`<div class="gui-hut__body-in">
    ${c.state === "none" ? html`<div class="gui-hut__big">${say("Ready")}<small>${say("a road or Review brings a document")}</small></div>`
      : c.state === "running" && c.triage ? html`<div class="gui-hut__big ok-tone-wait">${c.ok + c.no}/${c.of}<small>${say("have spoken · reading")}</small></div>`
      : c.state === "running" ? html`<div class="gui-hut__big">${c.cycle}/${c.max}<small>${say("cycle")} · <span class="ok-tone-ok">✓${c.ok}</span> <span class=${c.no ? "ok-tone-error" : ""}>✗${c.no}</span> · ${c.spent}</small></div>`
      : html`<div class=${`gui-hut__big ${TONE[c.state] || ""}`}>${BIG[c.state] || ""} ${say(c.outcome)}<small>${c.route ? `→ ${c.route}` : `${say("cycle")} ${c.cycle} · ${c.spent}`}</small></div>`}
    ${c.title && html`<div class="gui-hut__text" title=${c.title}>${c.title}</div>`}
    ${c.queued > 0 && html`<div class="gui-hut__text"><b>${c.queued}</b> ${say("waiting in line")}</div>`}
    ${last && html`<div class="gui-hut__foot"><span><b>${say(last.who)}</b>${" "}<span class=${TONE[last.verdict] || ""}>${last.kind === "answer" ? say("answers") : VERDICT[last.verdict] ?? last.verdict}</span></span>
      ${last.at && html`<span class="gui-hut__when">${last.at}</span>`}</div>`}
  </div>`;
}

// -- open ------------------------------------------------------------------------------------------

/** Where a routed review went: `→ human`. */
const routed = (r) => (r && r.route ? ` → ${r.route}` : "");


/** The clan as a row of chips: who, its verdict now; a click opens its brief in Lake. Add member at the end. */
function Clan({ id, data }) {
  const brief = (path, who) => openInLake({ path, title: `Brief — ${who}`, from: id });
  return html`<div class="council-clan" role="list" aria-label=${say("The clan")}>
    <button class="council-chip" role="listitem" onClick=${() => brief(data.steward.brief, "Steward")}
        title=${say(`${data.steward.label} · decides · open its brief${data.steward.briefed ? "" : " (empty)"}`)}>
      <b>${say("Steward")}</b><span class="ok-tone-muted">${say("decides")}</span></button>
    ${data.members.map((m) => html`<button key=${m.role} role="listitem" class=${`council-chip${TONE[m.verdict] ? ` is-${m.verdict}` : ""}`}
        onClick=${() => brief(m.brief, m.role)}
        title=${`${m.label}${m.tier ? ` · ${m.tier}` : ""}${m.veto ? " · veto" : ""} · ${say("open its brief")}${m.briefed ? "" : say(" (empty)")}${m.says ? `\n${m.says}` : ""}`}>
      <b>${m.role}</b>${m.veto && html`<span class="ok-word">veto</span>`}
      ${m.verdict ? html`<span class=${TONE[m.verdict] || ""}>${MARK[m.verdict] || ""} ${VERDICT[m.verdict]}</span>`
        : html`<span class="ok-tone-muted">${say("waits")}</span>`}</button>`)}
    <button class="council-chip council-clan__add" onClick=${() => setIn(dialogs, id, "member")}>+ ${say("Add member")}</button>
  </div>`;
}

/** The steward's rules, asked in plain words, and the review's limits: rare, so in the fold. */
function KeeperAsk({ id, data }) {
  const [ask, setAsk] = useState("");
  return html`<section class="gui-section">
    <h3 class="ok-font-heading">${say("Ask the keeper")}</h3>
    <p class="ok-tone-muted">At most ${data.max_cycles} cycles and ${data.budget} a review. Members: ${data.members.map((m) => `${m.role} (${m.label}${m.tier ? ` ${m.tier}` : ""})`).join(", ") || "none"}.</p>
    <textarea class="ok-input gui-textarea" rows="2" value=${ask} placeholder=${say("In plain words: a member's brief, who holds a veto, when the steward should ask you…")}
      onInput=${(e) => setAsk(e.target.value)}></textarea>
    <div class="ok-row"><button class="ok-btn" disabled=${!ask.trim()} onClick=${() => askKeeper(id, ask).then((r) => { if (r !== null) setAsk(""); })}>Ask</button></div>
  </section>`;
}

function Turns({ turns, open }) {
  return html`<ul class="gui-rows council-turn-list">${turns.map((t, i) => html`<li key=${i}>
    <details class="council-turn" open=${open && i >= turns.length - 2}>
      <summary><b>${t.kind === "decide" ? say("Steward") : t.role}</b>
        <span class=${TONE[t.verdict] || "ok-tone-muted"}> ${t.kind === "answer" ? "answers" : `${MARK[t.verdict] || ""} ${VERDICT[t.verdict] ?? t.verdict}`}</span>
        <span class="council-turn__note">${t.note ? ` · ${t.note}` : ""}</span>
        <span class="council-turn__when">${t.cost ? `${t.cost} · ` : ""}${t.at}</span></summary>
      <div class="gui-prose" dangerouslySetInnerHTML=${{ __html: t.html }}></div>
    </details></li>`)}</ul>`;
}

function Discussion({ data, r }) {
  return html`<section class="council-turns">
    ${data.cycles.map((c) => html`<details key=${c.id}>
      <summary>Cycle ${c.cycle} <span class=${TONE[c.outcome] || "ok-tone-muted"}>· ${c.outcome_word}</span>
        <span class="ok-tone-muted"> · ${c.ok} ✓ ${c.no} ✗ · ${c.spent} · ${c.started}</span></summary>
      <${Turns} turns=${c.turns} open=${false} />
    </details>`)}
    ${data.cycles.length > 0 && html`<h3 class="ok-detail__section">Cycle ${r.cycle} <span class=${TONE[r.outcome] || ""}>· ${r.outcome_word}</span></h3>`}
    ${r.turns.length ? html`<${Turns} turns=${r.turns} open=${true} />` : html`<p class="ok-tone-muted">The clan reads it…</p>`}
    ${r.question && html`<p class="ok-tone-fire">The steward asks you.</p>`}
    ${r.error && html`<p class="ok-tone-error">${r.error}</p>`}
  </section>`;
}

/** The review itself, taking the room: turn by turn, the document, the report — a tab each; Open in Lake. */
function Paper({ id, data, r, shown }) {
  const at = side.value[id] || "review";
  const tab = (key, label, n) => html`<button role="tab" aria-selected=${at === key} class=${cls("ok-tab", { "is-active": at === key })}
    onClick=${() => setIn(side, id, key)}>${label}${n ? html` <span class="ok-tone-muted">${n}</span>` : ""}</button>`;
  const lake = () => (at === "report" ? openInLake({ text: r.report, title: `Report — ${r.title}`, from: id }) : openDoc(id, r));
  return html`<div class="council-paper">
    <nav class="council-paper__tabs" role="tablist">
      ${tab("review", say("Turn by turn"), r.turns.length)}${tab("document", say("The document"))}${tab("report", say("The report"))}
      <span class="gui-head__spacer"></span>
      ${at !== "review" && html`<button class="ok-btn" onClick=${lake}>${say("Open in Lake")}</button>`}
    </nav>
    ${at === "report" ? html`<div class="gui-prose" dangerouslySetInnerHTML=${{ __html: r.report_html }}></div>`
      : at === "document" ? html`<div>${r.doc_path && html`<p class="ok-detail__meta council-paper__path" title=${r.doc_path}>${r.doc_path}</p>`}
          <div class="gui-prose" dangerouslySetInnerHTML=${{ __html: r.doc_html }}></div></div>`
      : html`<${Discussion} data=${shown ? { cycles: [] } : data} r=${r} />`}
  </div>`;
}

/** What waits in line, the past reviews (a click shows one) and the steward's rules: one line until opened. */
function History({ id, data }) {
  const show = (h) => act(id, "show", { review: h.id }).then((r) => setIn(past, id, r), () => {});
  const last = data.history[0];
  return html`<details class="council-fold">
    <summary><span>${say("Past reviews")} ${data.history.length}${data.queued.length ? ` · ${say("waiting")} ${data.queued.length}` : ""} · ${say("Rules")}</span>
      ${last && html`<span class="council-fold__sum ok-font-status">${say("last:")} ${last.title} · <span class=${TONE[last.outcome] || ""}>${last.outcome_word}</span></span>`}</summary>
    ${data.queued.length > 0 && html`<section class="gui-section"><h3 class="ok-font-heading">Waiting in line</h3>
      <ul class="gui-rows">${data.queued.map((t, i) => html`<li key=${i}>· ${t}</li>`)}</ul></section>`}
    <section class="gui-section"><h3 class="ok-font-heading">Past reviews</h3>
      ${data.history.length ? html`<ul class="gui-rows">${data.history.map((h) => html`<li key=${h.id}>
        <button class="council-past" onClick=${() => show(h)}><span class="council-past__title">${h.title}</span>
          <span class=${TONE[h.outcome] || "ok-tone-muted"}>${h.outcome_word}</span>
          <span class="ok-tone-muted">${say("cycle")} ${h.cycle} · ${h.spent} · ${h.started}</span></button></li>`)}</ul>`
        : html`<p class="ok-tone-muted">${say("None yet.")}</p>`}</section>
    <${KeeperAsk} id=${id} data=${data} />
  </details>`;
}

/** The head: the review shown (current or past) on one line, Stop, Review; the question waiting for you as a
 *  strip with Answer; the dialogs live here (the pane is always there). */
function Head({ id, data }) {
  const shown = past.value[id];
  const r = shown || data.current;
  const asks = !shown && data.current && data.current.outcome === "asked";
  return html`<div>
    <div class="council-head">
      ${shown && html`<button class="ok-btn" onClick=${() => setIn(past, id, null)}>← ${say("The current review")}</button>`}
      ${r ? html`<span class="council-head__title" title=${r.title}><b>${r.title}</b></span>
          <span>${say("cycle")} <b>${r.cycle}/${data.max_cycles}</b></span>
          <span class=${TONE[r.outcome] || ""}>${r.outcome === "running" ? "" : `${BIG[r.outcome] || ""} `}${r.outcome_word}${routed(r)}</span>
          <span><b class="ok-tone-ok">✓${r.ok}</b> <b class=${r.no ? "ok-tone-error" : ""}>✗${r.no}</b></span>
          <span><b>${r.spent}</b> ${say("of")} ${data.budget}</span>`
        : html`<span class="council-head__title">${say("No review yet — send a document down a road, or Review.")}</span>`}
      <span class="gui-head__spacer"></span>
      ${data.busy && html`<button class="ok-btn" onClick=${() => act(id, "stop").catch(() => {})}>Stop</button>`}
      <button class=${cls("ok-btn", { primary: !r })} onClick=${() => setIn(dialogs, id, "review")}>${say("Review…")}</button>
    </div>
    ${asks && html`<div class="council-ask">
      <span class="council-ask__who">? ${say("The steward asks")}</span>
      <span class="council-ask__what" title=${data.current.question}>${data.current.question}</span>
      <button class="ok-btn primary" onClick=${() => setIn(dialogs, id, "answer")}>Answer</button>
    </div>`}
    <${Dialogs} id=${id} data=${data} />
  </div>`;
}

/** The window by its UI document (design/buildings/council.json). A past review picked in the fold takes the
 * current one's place. `document` shows nothing of its own: the document is a tab of the review (an older
 * document that still has the pane loses nothing). */
export function panes(id, data) {
  const shown = past.value[id];
  const r = shown || data.current;
  return {
    head: () => html`<${Head} id=${id} data=${data} />`,
    members: () => html`<${Clan} id=${id} data=${data} />`,
    review: () => (r ? html`<${Paper} id=${id} data=${data} r=${r} shown=${!!shown} />`
      : html`<p class="ok-tone-muted">${say("Review… or a road brings a document: each member's verdict and the steward's decision show here, turn by turn.")}</p>`),
    document: () => null,
    history: () => html`<${History} id=${id} data=${data} />`,
  };
}
