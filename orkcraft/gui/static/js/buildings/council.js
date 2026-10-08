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
import { act, details, say } from "../link.js";
import { Dialog } from "../dialog.js";
import { openInLake } from "../lake.js";
import { askKeeper } from "../keeper.js";
import { usePeek, openBuilding } from "../windows.js";
import { Setup } from "./council_setup.js";

const sheet = new URL("./council.css", import.meta.url).href;
if (!document.querySelector(`link[href="${sheet}"]`)) {
  const link = document.createElement("link");
  link.rel = "stylesheet";
  link.href = sheet;
  document.head.appendChild(link);
}

const dialogs = signal({});        // building id → "review" (the rest happens in the panel)
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

function Dialogs({ id, data }) {
  const d = dialogs.value[id];
  const close = () => setIn(dialogs, id, null);
  if (d === "review") return html`<${ReviewDialog} id=${id} busy=${data.busy} onClose=${close} />`;
  return null;
}

/** Setting up, or changing, the clan and the exits: in the panel (docs/design/review-board.md §3). */
const setUp = (id, step = "purpose") => { openBuilding(id, "work"); act(id, "setup_open", { step }).catch(() => {}); };

// -- closed ------------------------------------------------------------------------------------------

const BIG = { approved: "✓", rework: "↩", budget: "⚠", asked: "?", error: "✗", stopped: "■" };

/** Closed: the headline is the state — the cycle and the tally while it reviews (a triage: how many have
 *  spoken), else how it ended; under it what it reviews and the line; the foot the last turn and when. */
export function card(b) {
  const c = b.card;
  if (!c) return null;
  const last = c.last;
  if (!c.set_up) {
    return html`<div class="gui-hut__body-in">
      <div class="gui-hut__big">${say("Not set up")}</div>
      <button class="ok-btn primary council-card__setup" onPointerDown=${(e) => e.stopPropagation()}
        onClick=${(e) => { e.stopPropagation(); setUp(b.id); }}>Set up the review</button>
      <div class="gui-hut__text ok-tone-muted">${say("Say what it reviews; the keeper picks the clan")}</div>
    </div>`;
  }
  return html`<div class="gui-hut__body-in">
    ${c.state === "none" ? html`<div class="gui-hut__big">${say("Ready")}<small>${say("a road or Review brings a document")}</small></div>`
      : c.state === "running" && c.triage ? html`<div class="gui-hut__big ok-tone-wait">${c.ok + c.no}/${c.of}<small>${say("have spoken · reading")}</small></div>`
      : c.state === "running" ? html`<div class="gui-hut__big">${c.cycle}/${c.max}<small>${c.phase === "deciding" ? say("deciding") : say("cycle")} · <span class="ok-tone-ok">✓${c.ok}</span> <span class=${c.no ? "ok-tone-error" : ""}>✗${c.no}</span> · ${c.spent}</small></div>`
      : c.exit ? html`<div class=${`gui-hut__big ${c.state === "rework" ? "ok-tone-wait" : "ok-tone-ok"}`}>${c.state === "rework" ? "↩" : "→"} ${c.exit}<small>${say("cycle")} ${c.cycle} · ${c.spent}</small></div>`
      : html`<div class=${`gui-hut__big ${TONE[c.state] || ""}`}>${BIG[c.state] || ""} ${say(c.outcome)}<small>${c.route ? `→ ${c.route}` : `${say("cycle")} ${c.cycle} · ${c.spent}`}</small></div>`}
    ${c.state === "none" && c.exits.length > 0 && html`<div class="gui-hut__text council-card__exits">${c.exits.map((x) => html`<span key=${x} class="council-sign">${x}</span>`)}</div>`}
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
    <button class="council-chip council-clan__add" onClick=${() => setUp(id, "clan")}>+ ${say("Add member")}</button>
    <button class="council-chip council-clan__add" onClick=${() => setUp(id, "exits")}>${say("Exits")} · ${data.exits.length}</button>
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
      <summary><b>${t.kind === "decide" && t.role !== "Operator" ? say("Steward") : say(t.role)}</b>
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

/** The review itself, taking the room: turn by turn, the document, the report — a tab each; Open in Lake. Wide
 *  (the whole town), the document stands beside the turns too. */
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
      : html`<div class="council-review"><${Discussion} data=${shown ? { cycles: [] } : data} r=${r} />
          <div class="council-review__doc" aria-hidden="true"><div class="gui-prose" dangerouslySetInnerHTML=${{ __html: r.doc_html }}></div></div></div>`}
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
          <span class=${TONE[r.outcome] || ""}>${r.outcome === "running" ? (data.phase === "deciding" ? say("the steward decides") : say("members read"))
            : r.exit ? `${r.outcome === "rework" ? "↩" : "→"} ${r.exit}` : `${BIG[r.outcome] || ""} ${r.outcome_word}${routed(r)}`}</span>
          <span><b class="ok-tone-ok">✓${r.ok}</b> <b class=${r.no ? "ok-tone-error" : ""}>✗${r.no}</b></span>
          <span><b>${r.spent}</b> ${say("of")} ${data.budget}</span>`
        : html`<span class="council-head__title">${say("No review yet")}</span>`}
      <span class="gui-head__spacer"></span>
      ${data.busy && html`<button class="ok-btn" onClick=${() => act(id, "stop").catch(() => {})}>Stop</button>`}
      ${!shown && r && WAYS_ON[r.outcome] && !data.busy && r.goes_on_at && html`<span class="ok-tone-muted council-head__at"
          title=${r.reopens ? say("in the session it stopped in: what was read is not read again") : ""}>${say("at")} ${r.goes_on_at}</span>`}
      ${!shown && r && WAYS_ON[r.outcome] && !data.busy && html`<button class="ok-btn primary" onClick=${() => act(id, "go_on").catch(() => {})}>${WAYS_ON[r.outcome]}</button>`}
      <button class=${cls("ok-btn", { primary: !r })} onClick=${() => setIn(dialogs, id, "review")}>${say("Review…")}</button>
    </div>
    ${data.queued.length > 0 && html`<div class="council-line">
      <span><b>${data.queued.length}</b> ${say("waiting in line")} · ${data.queued[0]}</span>
      ${!data.busy && !asks && html`<button class="ok-btn" onClick=${() => act(id, "review_next").catch(() => {})}>${say("Review now")}</button>`}
      <button class="ok-btn" onClick=${() => act(id, "drop", { index: 0 }).catch(() => {})}>${say("Drop")}</button>
    </div>`}
    ${!shown && data.answers.length > 0 && html`<${Decide} id=${id} data=${data} asks=${asks} />`}
    ${!shown && r && r.out && html`<${Sent} id=${id} r=${r} />`}
  </div>`;
}

const WAYS_ON = { budget: "Raise the budget and go on", error: "Try again", stopped: "Go on" };

/** The steward asks (the building burns), or a review stopped on the way: its exits as buttons, a comment as the
 *  verdict's words, or a reply in words for the steward to decide again (docs/design/review-board.md §5). */
function Decide({ id, data, asks }) {
  const [comment, setComment] = useState("");
  const [words, setWords] = useState(null);
  const q = data.current.question;
  const pick = (exit) => act(id, "decide", { exit, comment }).then(() => setComment(""), () => {});
  return html`<div class=${cls("council-ask", { "is-asking": asks })}>
    ${asks ? html`<span class="council-ask__who">? ${say("The steward asks you")}</span><p class="council-ask__what">${q}</p>`
      : html`<span class="council-ask__who ok-tone-muted">${say("Or decide yourself")}</span>`}
    <input class="ok-input" value=${comment} placeholder=${say("Your note — it goes on top of the verdict")}
      aria-label=${say("Your note")} onInput=${(e) => setComment(e.target.value)} />
    <div class="council-ask__exits">${data.answers.map((a) => html`<button key=${a.id} disabled=${!a.open}
      title=${a.open ? "" : say("No road takes this exit yet: pull one from this building")}
      class=${cls("ok-btn", { primary: a.open && a.id === (data.answers.find((x) => x.open) || {}).id })}
      onClick=${() => pick(a.id)}>${a.id === "back" ? "↩ " : ""}${a.words}${a.open ? "" : ` · ${say("not connected")}`}</button>`)}
      ${data.current.vetoed.length > 0 && html`<span class="ok-tone-error council-ask__veto">✗ ${say("vetoed by")} ${data.current.vetoed.join(", ")}</span>`}</div>
    ${asks && (words === null
      ? html`<button class="ok-btn council-ask__more" onClick=${() => setWords("")}>${say("Answer the steward in words instead")}</button>`
      : html`<div class="council-ask__words"><textarea class="ok-input gui-textarea" rows="2" value=${words} onInput=${(e) => setWords(e.target.value)}></textarea>
          <button class="ok-btn" disabled=${!words.trim()} onClick=${() => act(id, "answer", { text: words }).then(() => setWords(null), () => {})}>Send</button></div>`)}
  </div>`;
}

/** What went down the exit: the verdict, then the document. */
function Sent({ id, r }) {
  return html`<details class="council-sent">
    <summary><span class=${r.outcome === "rework" ? "ok-tone-wait" : "ok-tone-ok"}>${r.outcome === "rework" ? "↩" : "✓"}</span>
      <b>${say("Sent")} → ${r.exit}</b> <span class="ok-tone-muted">${say("the verdict, then the document")}</span></summary>
    <pre class="gui-pre council-sent__out">${r.out.length > 1600 ? `${r.out.slice(0, 1600)}
…` : r.out}</pre>
    <button class="ok-btn" onClick=${() => openInLake({ text: r.out, title: `Sent → ${r.exit} — ${r.title}`, from: id })}>${say("Open in Lake")}</button>
  </details>`;
}

/** The window by its UI document (design/buildings/council.json). A past review picked in the fold takes the
 * current one's place. `document` shows nothing of its own: the document is a tab of the review (an older
 * document that still has the pane loses nothing). */
export function panes(id, data) {
  const shown = past.value[id];
  const r = shown || data.current;
  if (!data.set_up || data.setup) {                  // the setup takes the window (in the panel, never a dialog)
    const brief = (role) => (data.members.find((m) => m.role === role) || {}).brief || "";
    return { head: () => null, members: () => null, document: () => null, history: () => null,
             review: () => html`<${Setup} id=${id} data=${data} briefOf=${brief} />` };
  }
  return {
    head: () => html`<${Head} id=${id} data=${data} />`,
    members: () => html`<${Clan} id=${id} data=${data} />`,
    review: () => (r ? html`<${Paper} id=${id} data=${data} r=${r} shown=${!!shown} />`
      : html`<p class="ok-tone-muted">${say("Nothing under review — Review a document, or a road brings one; each member's verdict shows here, turn by turn.")}</p>`),
    document: () => null,
    history: () => html`<${History} id=${id} data=${data} />`,
  };
}

/** Its quick actions, from its Info or its closed card: each opens its own small window. */
export function quick(id, action) {
  if (action === "team.add") { setUp(id, "clan"); return true; }
  if (action === "team.start") { setIn(dialogs, id, "review"); return true; }
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
