// ⛏️ The Mine (docs/design/mine.md §9). Closed: the question in work and its round, or the last report; the
// sources each tool found in its own mark and colour, what is confirmed and disputed, the cost. Open, made for
// the half panel: a question with what it may cost before it starts; the research in work (the plan, a column
// per tool, the findings marked ✓ ⚠ ①) and the disputes waiting on you with their answers; the reports, one
// line each, a report opening over them (← back); the repeats the Calendar shows. The worker does the research
// (core/workers/mine.py).
import { signal } from "@preact/signals";
import { useState } from "preact/hooks";
import { html, cls } from "../html.js";
import { act, details, say } from "../link.js";
import { Dialog } from "../dialog.js";
import { openInLake } from "../lake.js";
import { usePeek } from "../windows.js";

const sheet = new URL("./mine.css", import.meta.url).href;
if (!document.querySelector(`link[href="${sheet}"]`)) {
  const link = document.createElement("link");
  link.rel = "stylesheet";
  link.href = sheet;
  document.head.appendChild(link);
}

const chosen = signal({});          // building id → the report open over the rows (its data)
const asking = signal({});          // building id → true: New research is open over the town

const money = (usd) => `$${(usd || 0).toFixed(2)}`;
const day = (at) => (at || "").slice(5, 16).replace("T", " ");
const MARK = { confirmed: "✓", decided: "✓", disputed: "⚠", single: "①" };
const TONE = { confirmed: "ok-tone-ok", decided: "ok-tone-ok", disputed: "ok-tone-fire", single: "ok-tone-muted" };
const WORD = { confirmed: "Confirmed", decided: "Confirmed by you", disputed: "Disputed", single: "One source" };
const STATUS = { queued: "Waiting its turn", planning: "Planning", searching: "Searching", checking: "Checking",
  round: "Searching again", waiting: "Waits on you", done: "Done", failed: "Failed", stopped: "Stopped" };

function Tools({ tools }) {
  return html`<span class="gui-mine__tools">${tools.map((t) => html`<span key=${t.id} class=${`ok-h-${t.id}`} title=${t.title}>
    ${t.mark} ${t.sources ?? ""}</span>`)}</span>`;
}

function Counts({ c }) {
  if (!c) return null;
  return html`<span class="gui-mine__counts"><span class="ok-tone-ok">✓ ${c.confirmed}</span>
    <span class=${c.disputed ? "ok-tone-fire" : "ok-tone-muted"}>⚠ ${c.disputed}</span>
    <span class="ok-tone-muted">① ${c.single}</span></span>`;
}

// -- closed --------------------------------------------------------------------------------------------------

export function card(b) {
  const c = b.card;
  if (!c) return null;
  if (c.state === "none") {
    return html`<div class="gui-hut__body-in">
      <div class="gui-hut__big">${say("Ready")}<small>${say("no research yet")}</small></div>
      <div class="gui-hut__text ok-tone-muted">${c.tools.length
        ? html`${say("Searches with")} <${Tools} tools=${c.tools} />`
        : say("No AI tool that can search the web is on")}</div>
    </div>`;
  }
  const running = c.state === "running";
  return html`<div class="gui-hut__body-in">
    ${running ? html`<div class="gui-hut__big ok-tone-wait">${say(STATUS[c.status] || "Researching")}<small>${c.round
        ? say(`round ${c.round} of ${c.rounds}`) : ""}${c.queue ? ` · ${c.queue} ${say("waiting")}` : ""}</small></div>`
      : c.waiting ? html`<div class="gui-hut__big ok-tone-fire">? ${say("Disputed")}<small>${say("waits on you")}</small></div>`
        : html`<div class=${cls("gui-hut__big", c.state === "failed" ? "ok-tone-error" : "ok-tone-ok")}>${say(STATUS[c.state] || "Done")}<small>${say("the last report")}</small></div>`}
    <div class="gui-hut__text gui-mine__line"><${Tools} tools=${c.tools} /> <${Counts} c=${c.counts} /> <b>${money(c.cost)}</b></div>
    <div class="gui-hut__foot"><span>${c.question}</span><span class="gui-hut__when">${day(c.at).slice(6)}</span></div>
  </div>`;
}

// -- asking --------------------------------------------------------------------------------------------------

function AskForm({ id, data, onDone }) {
  const [question, setQuestion] = useState("");
  const [must, setMust] = useState("");
  const [skip, setSkip] = useState("");
  const [limit, setLimit] = useState(String(data.limit ?? 3));
  const [busy, setBusy] = useState(false);
  const [low, high] = data.estimate || [0, 0];
  const left = Math.max((data.month_limit || 0) - (data.month_spent || 0), 0);
  const start = () => {
    setBusy(true);
    act(id, "ask", { question, must, skip, limit }).then(() => { setQuestion(""); setMust(""); setSkip(""); onDone && onDone(); },
      () => {}).finally(() => setBusy(false));
  };
  const tools = data.tools || [];
  return html`<div class="gui-mine__ask" onKeyDown=${(e) => { if (e.key === "Enter" && (e.ctrlKey || e.metaKey) && question.trim()) start(); }}>
    <textarea class="ok-input gui-textarea" rows="2" placeholder=${say("What do you want researched?")} value=${question}
      onInput=${(e) => setQuestion(e.target.value)} aria-label=${say("Question")}></textarea>
    <details class="gui-mine__more"><summary>${say("Must cover · leave out")}</summary>
      <textarea class="ok-input gui-textarea" rows="2" placeholder=${say("Must cover: one sub-question per line")} value=${must}
        onInput=${(e) => setMust(e.target.value)}></textarea>
      <textarea class="ok-input gui-textarea" rows="2" placeholder=${say("Leave out: sites or topics, one per line")} value=${skip}
        onInput=${(e) => setSkip(e.target.value)}></textarea>
    </details>
    <div class="gui-mine__go">
      <span class="ok-tone-muted">${tools.length < 2
        ? html`<span class="ok-tone-fire">${say(tools.length ? "One tool searches: nothing can be confirmed" : "No AI tool that can search the web is on")}</span>`
        : html`<${Tools} tools=${tools} /> · ${say(`about ${money(low)}–${money(high)}`)} · ${say(`${money(left)} left this month`)}`}</span>
      <label class="gui-mine__limit">${say("Limit")} $<input class="ok-input" type="number" min="0.1" step="0.5" value=${limit}
        onInput=${(e) => setLimit(e.target.value)} aria-label=${say("Limit in dollars")} /></label>
      <button class="ok-btn primary" disabled=${busy || !question.trim()} onClick=${start}>${say(`Start research · up to $${Number(limit || 0).toFixed(2)}`)}</button>
    </div>
  </div>`;
}

// -- the research in work ------------------------------------------------------------------------------------

function Group({ g }) {
  return html`<li class=${cls("gui-mine__finding", `is-${g.state}`)}>
    <span class=${TONE[g.state]} title=${say(WORD[g.state] || "")}>${MARK[g.state] || "·"}</span>
    <span class="gui-mine__claim">${g.claim}</span>
    <span class="gui-mine__srcs">${g.sources.slice(0, 4).map((s) => html`<a key=${s.url} href=${s.url} target="_blank" rel="noopener noreferrer" title=${s.title}>${s.site}</a>`)}</span>
    <span class="gui-mine__minds ok-tone-muted">${g.decided === "accept" ? say("you") : g.minds.join(", ")}</span>
  </li>`;
}

function Dispute({ id, r, pair }) {
  const [a, b] = pair;
  const answer = (ans) => act(id, "decide", { id: r.id, a: a.id, b: b.id, answer: ans }).catch(() => {});
  return html`<div class="gui-mine__dispute">
    <p class="ok-tone-fire"><b>⚠ ${say("Disputed")}</b></p>
    <ul class="gui-mine__findings"><${Group} g=${a} /></ul>
    <p class="ok-tone-muted gui-mine__against">${say("against")}</p>
    <ul class="gui-mine__findings"><${Group} g=${b} /></ul>
    <div class="ok-detail__actions">
      <button class="ok-btn" onClick=${() => answer("more")}>${say("Search more")}</button>
      <button class="ok-btn" onClick=${() => answer("a")}>${say("Accept the first")}</button>
      <button class="ok-btn" onClick=${() => answer("b")}>${say("Accept the second")}</button>
      <button class="ok-btn" onClick=${() => answer("keep")}>${say("Keep it disputed")}</button>
    </div>
  </div>`;
}

function Research({ id, r }) {
  const groups = r.groups || [];
  return html`<div class="gui-mine__current">
    <p class="gui-mine__state"><b class=${r.status === "waiting" ? "ok-tone-fire" : "ok-tone-wait"}>${say(STATUS[r.status] || r.status)}</b>
      <span>${r.question}</span></p>
    <p class="ok-detail__meta">${r.round ? say(`round ${r.round}`) : ""} · <b>${money(r.cost)}</b> ${say(`of ${money(r.limit)}`)} · <${Counts} c=${r.counts} /></p>
    ${r.plan.length > 0 && html`<ol class="gui-mine__plan">${r.plan.map((s, n) => html`<li key=${n}>${s.q}
      <span class="ok-tone-muted gui-mine__marks">${groups.filter((g) => g.sub === n + 1).map((g) => MARK[g.state] || "").join(" ")}</span></li>`)}</ol>`}
    <div class="gui-mine__cols">${r.tools.map((t) => html`<div key=${t.id} class="gui-mine__col">
      <b class=${`ok-h-${t.id}`}>${t.mark} ${t.title}</b>
      <span>${t.sources} ${say("sources")} · ${t.findings} ${say("findings")}</span>
      <span class="ok-tone-muted">${t.mind}${t.cost ? ` · ${money(t.cost)}` : ""}</span>
      ${t.error && html`<span class="ok-tone-error" title=${t.error}>✗ ${t.error.slice(0, 60)}</span>`}
    </div>`)}</div>
    ${r.disputes.map((pair) => html`<${Dispute} key=${`${pair[0].id}-${pair[1].id}`} id=${id} r=${r} pair=${pair} />`)}
    ${groups.length > 0 && html`<ul class="gui-mine__findings">${groups.filter((g) => g.state !== "disputed")
      .map((g) => html`<${Group} key=${g.id} g=${g} />`)}</ul>`}
  </div>`;
}

// -- the reports and one over them ---------------------------------------------------------------------------

function Report({ id, r, count }) {
  const back = () => { chosen.value = { ...chosen.value, [id]: null }; };
  return html`<div class="gui-mine__report" onKeyDown=${(e) => { if (e.key === "Escape") { e.stopPropagation(); back(); } }}>
    <button class="ok-btn" onClick=${back}>← ${say("All reports")} · ${count}</button>
    <p class="gui-mine__state"><b class=${r.status === "failed" ? "ok-tone-error" : "ok-tone-ok"}>${say(STATUS[r.status] || r.status)}</b>
      <span>${r.question}</span></p>
    <p class="ok-detail__meta">${day(r.created)} · ${r.trigger} · <b>${money(r.cost)}</b> · <${Counts} c=${r.counts} />
      ${r.wiki_note ? html` · ${say("in the Wiki")}` : ""}</p>
    ${r.stopped && html`<p class="ok-tone-wait">${r.stopped}</p>`}
    ${r.error && html`<p class="ok-tone-error">${r.error}</p>`}
    <div class="ok-detail__actions">
      ${r.path && html`<button class="ok-btn" onClick=${() => openInLake({ path: r.path, title: r.question, from: id })}>${say("Report in the Inspector")}</button>`}
      <button class="ok-btn" onClick=${() => act(id, "again", { id: r.id }).catch(() => {})}>${say("Research again")}</button>
    </div>
    ${r.groups && html`<ul class="gui-mine__findings">${r.groups.map((g) => html`<${Group} key=${g.id} g=${g} />`)}</ul>`}
  </div>`;
}

function Repeats({ id, data }) {
  const [question, setQuestion] = useState("");
  const [every, setEvery] = useState("weekly mon 09:00");
  if (!data.calendar && !data.repeats.length) {
    return html`<p class="ok-tone-muted">${say("A repeat shows on the Calendar — build a Calendar to repeat a research.")}</p>`;
  }
  return html`<details class="gui-mine__repeats"><summary>${say("Repeats")} · ${data.repeats.length}</summary>
    <ul class="gui-rows">${data.repeats.map((r) => html`<li key=${r.question}><span>${r.question}</span>
      <span class="ok-tone-muted"> · ${r.every}</span>
      <button class="ok-btn" onClick=${() => act(id, "repeat", { question: r.question, every: "" }).catch(() => {})}>${say("Stop")}</button></li>`)}</ul>
    ${data.calendar && html`<div class="gui-mine__go">
      <input class="ok-input" placeholder=${say("Question to repeat")} value=${question} onInput=${(e) => setQuestion(e.target.value)} />
      <input class="ok-input gui-mine__every" value=${every} onInput=${(e) => setEvery(e.target.value)} aria-label=${say("Every")} />
      <button class="ok-btn" disabled=${!question.trim()} onClick=${() => act(id, "repeat", { question, every }).then(() => setQuestion(""), () => {})}>${say("Repeat")}</button>
    </div>`}
  </details>`;
}

function Reports({ id, data }) {
  const open = chosen.value[id];
  if (open) return html`<${Report} id=${id} r=${open} count=${data.reports.length} />`;
  const pick = (r) => act(id, "open", { id: r.id }).then((full) => { chosen.value = { ...chosen.value, [id]: full }; }, () => {});
  return html`<div class="gui-mine__reports">
    ${data.reports.length ? html`<ul class="gui-mine__rows">${data.reports.map((r) => html`<li key=${r.id}>
      <button class="gui-mine__row" onClick=${() => pick(r)}>
        <span class=${r.status === "failed" ? "ok-tone-error" : r.status === "waiting" ? "ok-tone-fire" : "ok-tone-ok"}>${r.status === "failed" ? "✗" : r.status === "waiting" ? "?" : "✓"}</span>
        <span class="gui-mine__at">${day(r.created)}</span>
        <span class="gui-mine__what">${r.question}</span>
        <${Counts} c=${r.counts} />
        <span class="gui-mine__cost">${money(r.cost)}</span>
      </button></li>`)}</ul>`
      : html`<p class="ok-tone-muted">${say("No reports yet — ask a question above, or a road brings one.")}</p>`}
    <${Repeats} id=${id} data=${data} />
  </div>`;
}

/** The window by its UI document (design/buildings/mine.json). */
export function panes(id, data) {
  return {
    ask: () => html`<${AskForm} id=${id} data=${data} />`,
    current: () => (data.current ? html`<${Research} id=${id} r=${data.current} />` : null),
    reports: () => html`<${Reports} id=${id} data=${data} />`,
  };
}

/** New research from its Info or its closed card: the question in its own small window. */
export function quick(id, action) {
  if (action === "mine.new") { asking.value = { ...asking.value, [id]: true }; return true; }
  return false;
}

function Asking({ id }) {
  usePeek(id);
  const close = () => { asking.value = { ...asking.value, [id]: false }; };
  const data = (details.value[id] || {}).data;
  return html`<${Dialog} title=${say("New research")} onCancel=${close} wide=${true}
      actions=${html`<button class="ok-btn" onClick=${close}>Cancel</button>`}>
    ${data ? html`<${AskForm} id=${id} data=${data} onDone=${close} />` : html`<p class="ok-tone-muted">${say("Loading…")}</p>`}
  </${Dialog}>`;
}

export function overlay() {
  return html`${Object.keys(asking.value).filter((id) => asking.value[id]).map((id) => html`<${Asking} key=${id} id=${id} />`)}`;
}
