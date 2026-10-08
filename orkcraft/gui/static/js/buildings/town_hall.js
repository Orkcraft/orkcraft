// 🏰 Town Hall, the town's way in (docs/design/building-views.md §3; the work is
// core/workers/town_hall.py, the data gui/views/town_hall.py):
//   closed  — Ask me anything, or what happens in the hall (Camp's hut; Office has the Warchief's line);
//   Work    — the tabs Chat (the Warchief's whole chat), Hall (its orks, the audit, the proposals), Sessions
//             (the War Tent, js/tent.js), Limits.
import { useEffect, useRef, useState } from "preact/hooks";
import { html, cls } from "../html.js";
import { act, command, town, say } from "../link.js";
import { openBuilding } from "../windows.js";
import { building as buildOpen } from "../build.js";
import { WarTent, hallTab, HALL } from "../tent.js";
import { fill } from "../warchief.js";

const sheet = new URL("./town_hall.css", import.meta.url).href;
if (typeof document !== "undefined" && !document.querySelector(`link[href="${sheet}"]`)) {
  const link = document.createElement("link");
  link.rel = "stylesheet";
  link.href = sheet;
  document.head.appendChild(link);
}

/** Change, on a plan: the person goes on talking, and the Warchief asks the Town Builder again. */
const changePlan = () => fill("Change the plan: ");

const keep = (e) => e.stopPropagation();          // a press on a control is not a press on the hut

/** A question for the Warchief (Camp's hut asks it); its answer comes in the town's line and the hall's Chat. */
function askWarchief(id, text) {
  return act(id, "ask", { text }).then(() => true, () => false);
}

function AskField({ id, autofocus }) {
  const [text, setText] = useState("");
  const send = () => {
    const t = text.trim();
    if (t) askWarchief(id, t).then((ok) => ok && setText(""));
  };
  return html`<input class="ok-input" placeholder=${say("Ask me anything")} value=${text} autofocus=${autofocus}
    onPointerDown=${keep} onInput=${(e) => setText(e.target.value)} onKeyDown=${(e) => e.key === "Enter" && send()} />`;
}

/** Builds `type`; `asked`, the request it answers, names it (≤ 4 words, gui/builder.py). */
function raise(type, asked = "") {
  return command("town.build", asked ? { type, prompt: asked } : { type }).then((id) => id && openBuilding(id), () => {});
}

// -- closed: the hut ---------------------------------------------------------------------------------

/** Closed: what happens in the hall — a town order waits, the Warchief is answering, the audit found
 *  something — its count the headline and each on a line; else the field to ask the Warchief. */
function HallCard({ b }) {
  const news = (b.card && b.card.news) || [];
  if (!news.length) return html`<div class="gui-hut__body-in"><div class="gui-form__row th-ask"><${AskField} id=${b.id} /></div></div>`;
  return html`<div class="gui-hut__body-in">
    <div class="gui-hut__big ok-tone-wait">⚠ ${news.length}<small>${say(news.length === 1 ? "thing for you" : "things for you")}</small></div>
    ${news.slice(0, 2).map((line, i) => html`<div key=${i} class="gui-hut__text">${say(line)}</div>`)}
  </div>`;
}

export function card(b) {
  return html`<${HallCard} b=${b} />`;
}

/** The hall's quick actions in its Info: Build opens the catalog, Audit runs it. */
export function quick(id, action) {
  if (action === "hall.build") buildOpen.value = true;
  else if (action === "hall.audit") act(id, "audit").catch(() => {});
  else return false;
  return true;
}

// -- the Warchief's chat ---------------------------------------------------------------------------

// -- the Warchief's cards: the work it gave a specialist (core/warchief.py) ----------------------------

const STEP = { working: "…", done: "✓", failed: "✗" };
const HAS = { road: "Road planner", recruit: "Recruiter", keeper: "keeper" };

function cardAct(c, choice) {
  return act(HALL, "card", { card: c.id, choice }).catch(() => {});
}

function Steps({ c }) {
  if (!c.steps || !c.steps.length) return null;
  return html`<ul class="gui-card-steps ok-font-status">${c.steps.map((s, i) => html`<li key=${i}
      class=${cls("", { "ok-tone-wait": s.state === "working", "ok-tone-error": s.state === "failed" })}>
    ${say(s.who)} ${s.state === "working" ? say("is on it") : s.state === "done" ? say("done") : say("could not")} ${STEP[s.state] || ""}</li>`)}</ul>`;
}

function PlanList({ plan }) {
  return html`<div class="gui-card-plan">
    ${plan.title && html`<b>${plan.title}</b>`}${plan.summary && html` <span class="ok-tone-muted">${plan.summary}</span>`}
    <ul class="gui-rows">${plan.buildings.map((x, i) => html`<li key=${i}>${say(x.title)}
      ${x.why && html`<span class="ok-font-status ok-tone-muted"> · ${x.why}</span>`}</li>`)}</ul>
    ${plan.roads.length > 0 && html`<ul class="gui-rows ok-font-status">${plan.roads.map((r, i) => html`<li key=${i}>
      ${say(r.from)} → ${say(r.to)} <span class="ok-tone-muted">· ${r.event}</span></li>`)}</ul>`}
  </div>`;
}

/** A card in the Warchief's chat: who has the work, what came of it, and what the person decides. */
export function Card({ c }) {
  const live = c.state === "ready" || c.state === "working" || c.state === "sent";
  const btn = (label, choice, primary = false) => html`<button class=${cls("ok-btn", { primary })}
      onClick=${() => cardAct(c, choice)}>${say(label)}</button>`;
  return html`<div class=${cls("gui-card-order", { [`is-${c.state}`]: true })}>
    <${Steps} c=${c} />
    ${c.kind === "build" && html`<p class="ok-font-body">${say(c.type_title)}${c.state === "done" ? html` <span class="ok-tone-muted">· ${say("built")}</span>` : ""}</p>`}
    ${c.plan && html`<${PlanList} plan=${c.plan} />`}
    ${HAS[c.kind] && html`<p class="ok-font-status">→ ${say(HAS[c.kind])}${c.building_title ? html` · <b>${say(c.building_title)}</b>` : ""}:
      ${c.order}${c.state === "sent" ? html`<br /><span class="ok-tone-muted">${say("Its offer opens when it is ready; nothing changes before you take it.")}</span>` : ""}</p>`}
    ${c.cost && html`<p class="ok-font-status ok-tone-muted">${c.cost}</p>`}
    ${(c.notes || []).map((n, i) => html`<p key=${i} class="ok-font-status ok-tone-wait">⚠ ${n}</p>`)}
    ${c.error && html`<p class="ok-font-status ok-tone-error">${say(c.error)}</p>`}
    ${c.state === "dropped" && html`<p class="ok-font-status ok-tone-muted">${say("Cancelled.")}</p>`}
    ${c.state === "undone" && html`<p class="ok-font-status ok-tone-muted">${say("Taken back.")}</p>`}
    <div class="gui-card-order__acts">
      ${c.state === "ready" && btn("Build", "build", true)}
      ${c.state === "ready" && c.kind === "plan" && html`<button class="ok-btn" onClick=${() => changePlan()}>${say("Change")}</button>`}
      ${live && btn("Cancel", "cancel")}
      ${c.state === "done" && btn("Undo", "undo")}
    </div>
  </div>`;
}

export function Message({ m, name }) {
  if (m.who === "you") {
    return html`<li class="ok-font-body"><span class="ok-font-label ok-tone-muted">You: </span>${m.text}</li>`;
  }
  return html`<li class=${cls("ok-font-body", { "ok-tone-error": m.error })}>
    <span class="ok-font-label">${say(name)}:</span>
    <div class="gui-prose" dangerouslySetInnerHTML=${{ __html: m.html }}></div>
    ${m.card && html`<${Card} c=${m.card} />`}
    ${m.suggest && html`<button class="ok-act" onClick=${() => raise(m.suggest, m.asked)}>
      <span class="ok-act__label">${say(`Build ${m.suggest_title}`)}</span></button>`}
  </li>`;
}

/** The composer under the chat: one line that grows while it is written, Send beside it; Enter sends,
 *  Shift+Enter breaks the line. */
function Composer({ id, name }) {
  const [text, setText] = useState("");
  const send = () => {
    const t = text.trim();
    if (t) askWarchief(id, t).then((ok) => ok && setText((now) => (now === text ? "" : now)));
  };
  const keys = (e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } };
  return html`<div class="th-compose">
    <textarea class=${cls("ok-input gui-textarea", { "has-text": !!text })} rows="1" value=${text} aria-label=${say(`Ask the ${name}`)}
      placeholder=${say("Ask me anything — Enter sends it, Shift+Enter a new line")}
      onInput=${(e) => setText(e.target.value)} onKeyDown=${keys}></textarea>
    <button class="ok-btn primary" disabled=${!text.trim()} onClick=${send}>Send</button>
  </div>`;
}

/** The Warchief's whole chat: the messages take the room and scroll, the newest at the bottom; the
 *  composer stays under them; New chat quiet on top. */
function Chat({ id, data }) {
  const box = useRef(null);
  useEffect(() => { if (box.current) box.current.scrollTop = box.current.scrollHeight; }, [data.chat.length, data.thinking]);
  const name = data.warchief;
  return html`<div class="th-chat">
    ${data.chat.length > 0 && html`<div class="th-chat__bar">
      <span class="ok-tone-muted">${say(`${data.chat.length} messages`)}</span>
      <button class="ok-act" onClick=${() => act(id, "forget").catch(() => {})}><span class="ok-act__label">New chat</span></button></div>`}
    <ul class="th-chat__list" ref=${box}>
      ${data.chat.map((m, i) => html`<${Message} key=${i} m=${m} name=${name} />`)}
      ${data.thinking && html`<li class="ok-font-status ok-tone-wait">${say(`${name} is answering…`)}</li>`}
      ${!data.chat.length && !data.thinking && html`<li class="th-chat__empty ok-tone-muted">${say(`Ask the ${name} what the town should do — he builds, plans roads and answers about the orks.`)}</li>`}
    </ul>
    <${Composer} id=${id} name=${name} />
  </div>`;
}

// -- Work: Chat, Hall, Sessions, Limits ------------------------------------------------------------------

/** Apply or say no to a retro's proposal; an unanswered one may be applied by the orks (its building's
 * autonomy, docs/design/retros-and-goals.md §3). */
function Answer({ onApply, onNo, no }) {
  const run = (f) => f().catch(() => {});
  return html`<span class="gui-answer"><button class="ok-act" title=${say("Apply it: a checkpoint, Revert takes it back")}
      onClick=${() => run(onApply)}><span class="ok-act__label">${say("Apply")}</span></button>
    <button class="ok-act" title=${say("Not this one: the orks will not apply it either")} onClick=${() => run(onNo)}>
      <span class="ok-act__label">${no}</span></button></span>`;
}

function Section({ title, children, extra }) {
  return html`<section class="gui-section">
    <div class="gui-head"><h3 class="ok-font-heading">${title}</h3><span class="gui-head__spacer"></span>${extra}</div>
    ${children}
  </section>`;
}

function Rows({ items, empty, row }) {
  return items.length ? html`<ul class="gui-rows">${items.map(row)}</ul>`
    : html`<p class="ok-font-status ok-tone-muted">${empty}</p>`;
}

const MARK = { approved: "✓", overridden: "?", rejected: "✗", cancelled: "·", pending: "…", applied: "✓", dismissed: "✗",
               answered: "↪", advised: "!", left: "·" };

/** A rare part of the hall: one line (its name, a count, a word on it) until opened. */
function Fold({ title, count, sum, children }) {
  return html`<details class="th-fold">
    <summary><span>${title}${count !== undefined ? html` <b>${count}</b>` : ""}</span>
      ${sum && html`<span class="th-fold__sum ok-font-status">${sum}</span>`}</summary>
    <div class="th-fold__body">${children}</div>
  </details>`;
}

/** The Hall tab, what needs the person first: a town order waiting, the proposals and the town retro's
 *  items with Apply beside each, the audit's findings with Audit now; the rest — its orks, the answered
 *  proposals, the Elders, the Council's Fast Path, the stewards' ratings — one line each until opened. */
function Hall({ id, h }) {
  const b = town.value.buildings.find((x) => x.id === id);
  const garrison = b ? b.garrison : [];
  const titles = Object.fromEntries(town.value.buildings.map((x) => [x.id, say(x.title)]));
  const pending = h.proposals.filter((p) => p.status === "pending");
  const answered = h.proposals.filter((p) => p.status !== "pending");
  const weekly = h.weekly ? h.weekly.rows : [];
  const where = (bid) => (bid && titles[bid]
    ? html`<button class="gui-link" onClick=${() => openBuilding(bid)}>${titles[bid]}</button>` : html`<b>${bid || ""}</b>`);
  const proposal = (p, i) => html`<li key=${p.id || i} class="th-item">
    <span class="th-item__what">${p.status === "pending" ? "" : `${MARK[p.status] || "·"} `}${where(p.building)} · ${p.action} ${p.target}
      <span class="ok-font-status ok-tone-muted"> — ${p.why} · ${p.ts}</span></span>
    ${p.status === "pending" && html`<${Answer} onApply=${() => act(id, "proposal", { id: p.id, choice: "apply" })}
      onNo=${() => act(id, "proposal", { id: p.id, choice: "dismiss" })} no=${say("Dismiss")} />`}</li>`;
  const orks = garrison.length + h.builders.length + h.agents.length;
  const ratings = h.board.length + h.incidents.length;
  return html`<div class="th-hall">
    ${h.order && html`<div class="th-strip">
      <span class="th-strip__what">${say("A town waits to be raised")}: “${h.order}”</span>
      <span class="ok-font-status ok-tone-muted">${say("The Town Builder plans it; you approve the plan before anything is raised.")}</span></div>`}
    <${Section} title=${say("Waiting for you")} extra=${html`<span class="ok-font-status ok-tone-muted">${pending.length + weekly.length}</span>`}>
      ${pending.length + weekly.length ? html`<ul class="gui-rows th-items">
          ${pending.map(proposal)}
          ${weekly.map((x) => html`<li key=${`w${x.n}`} class="th-item">
            <span class="th-item__what">${say("Town retro")} · ${x.building && titles[x.building] ? html`${where(x.building)}: ` : ""}${x.title}
              <span class="ok-font-status ok-tone-muted"> — ${x.why}</span></span>
            <${Answer} onApply=${() => act(id, "weekly", { n: x.n, choice: "apply" })}
              onNo=${() => act(id, "weekly", { n: x.n, choice: "decline" })} no=${say("Decline")} /></li>`)}</ul>`
        : html`<p class="ok-font-status ok-tone-muted">${say("Nothing to decide — the Building retro and the Town retro bring proposals here.")}</p>`}
    </${Section}>
    <${Section} title=${h.audit ? `${say("Last audit")} ${h.audit.ts.slice(0, 16).replace("T", " ")}` : say("Audit")}
        extra=${html`<button class="ok-act" onClick=${() => act(id, "audit").catch(() => {})}><span class="ok-act__label">Audit now</span></button>`}>
      <${Rows} items=${h.audit ? h.audit.findings : []} empty=${h.audit ? say("Nothing found.")
          : say("No audit yet: the Warder, the Pathfinder and the Treasurer look over the town in a moment, no model call.")}
        row=${(f, i) => html`<li key=${i} class=${cls("ok-font-body", { "ok-tone-error": f.severity === "high", "ok-tone-wait": f.severity === "warn" })}>
          ${f.severity === "high" ? "✗ " : f.severity === "warn" ? "⚠ " : "· "}${f.building && titles[f.building] ? html`${where(f.building)}: ` : ""}${f.text}</li>`} />
    </${Section}>
    <${Fold} title=${say("Orks of the hall")} count=${orks}
        sum=${h.audit ? say(`${h.agents.reduce((n, a) => n + (a.serious || 0), 0)} to look at`) : say("not audited yet")}>
      <ul class="gui-rows">
        ${garrison.map((o) => html`<li key=${o.ref || o.name}><b>${say(o.name)}</b>
          <span class="ok-font-status ok-tone-muted"> · ${o.lead ? say("steward") : o.tier || o.kind} · ${o.status}</span></li>`)}
        ${h.builders.map((x) => html`<li key=${x.name}><b>${say(x.name)}</b>
          <span class="ok-font-status ok-tone-muted"> · ${x.role}</span></li>`)}
        ${h.agents.map((a) => html`<li key=${a.id}><b>${say(a.name)}</b>
          <span class="ok-font-status ok-tone-muted"> · ${a.area} · </span>
          <span class=${cls("ok-font-status", { "ok-tone-wait": a.serious > 0 })}>${h.audit ? `${a.found} found${a.serious ? `, ${a.serious} to look at` : ""}` : "not audited yet"}</span></li>`)}
      </ul>
    </${Fold}>
    <${Fold} title=${say("Proposals answered")} count=${answered.length}
        sum=${`${say("Town retro")}: ${h.weekly ? `${h.weekly.ts.slice(0, 10)} · ${h.weekly.items} items, ${h.weekly.applied} applied` : say("not run yet — Sunday 05:00")}`}>
      <${Rows} items=${answered} empty=${say("None yet.")} row=${proposal} />
    </${Fold}>
    <${Fold} title=${say("The Elders")} count=${h.elders.length}>
      <${Rows} items=${h.elders} empty=${say("Nothing judged yet — they read the orks' questions in quiet hours.")}
        row=${(r, i) => html`<li key=${i} class="ok-font-body">${MARK[r.how]} ${r.ts} ${r.who && `${r.who} · `}${r.question}
          <span class="ok-font-status ok-tone-muted"> → ${r.how === "left" ? "left to you" : `${r.how} [${r.key}] ${r.option}`}${r.why ? ` — ${r.why}` : ""}</span></li>`} />
    </${Fold}>
    <${Fold} title=${say("The Council's Fast Path")} count=${h.reviews.length} sum=${h.fast_path.map((r) => r.name).join(" · ")}>
      <p class="ok-font-status ok-tone-muted">${h.fast_path.map((r) => `${r.name} (${r.duty})`).join(" · ")}</p>
      <${Rows} items=${h.reviews} empty=${say("No reviews yet.")}
        row=${(r, i) => html`<li key=${i} class="ok-font-body">${MARK[r.decision] || "·"} ${r.ts} ${r.kind} ${r.id}
          ${r.note && html`<span class="ok-font-status ok-tone-muted"> — ${r.note}</span>`}</li>`} />
    </${Fold}>
    <${Fold} title=${say("Good and bad of the stewards")} count=${ratings}>
      <${Rows} items=${[...h.board.map((x) => ({ ...x, row: "board" })), ...h.incidents.map((x) => ({ ...x, row: "incident" }))]}
        empty=${say("No ratings yet.")}
        row=${(x, i) => x.row === "board"
          ? html`<li key=${i} class="ok-font-body"><b>${titles[x.building] || x.building}</b>: good ${x.likes} bad ${x.dislikes} · penalty ${x.penalty}</li>`
          : html`<li key=${i} class="ok-font-body ok-tone-wait">${x.ts} ${titles[x.building] || x.building} · ${x.kind}${x.how ? ` (${x.how})` : ""} → ${x.blamed}${x.note ? ` — ${x.note}` : ""}</li>`} />
    </${Fold}>
  </div>`;
}

function Meter({ label, part, value, level }) {
  const width = part === null || part === undefined ? 0 : Math.max(0, Math.min(1, part)) * 100;
  return html`<div class=${cls("ok-meter", { "is-warn": level === "warn", "is-over": level === "over" })}>
    <span>${label}</span><span class="ok-meter__track"><span class="ok-meter__fill" style=${`width:${width}%`}></span></span>
    <span class="ok-meter__val">${value}</span></div>`;
}

/** The last 7 days' model calls by what they were for, each with its buildings inside
 *  (docs/design/simplify.md §2). */
function ByPurpose({ week }) {
  const money = (r) => `$${r.usd.toFixed(2)} · ${r.tokens} tokens · ${r.calls} ${r.calls === 1 ? "call" : "calls"}`;
  return html`<${Section} title=${say("By purpose, last 7 days")}>
    ${week.length ? week.map((g) => html`<${Fold} key=${g.purpose} title=${say(g.word)}
        sum=${money(g) + (g.unpriced ? ` · ${g.unpriced} unpriced` : "")}>
        <${Rows} items=${g.buildings} empty=""
          row=${(b, i) => html`<li key=${i} class="ok-font-body">${say(b.title)}
            <span class="ok-font-status ok-tone-muted"> — ${money(b)}</span></li>`} />
      </${Fold}>`)
      : html`<p class="ok-font-status ok-tone-muted">${say("No model calls recorded in the last 7 days.")}</p>`}
  </${Section}>`;
}

function Limits({ id, data }) {
  const s = data.spend;
  return html`<div>
    <${Section} title=${say("Spend")}>
      <${Meter} label=${say("This run")} part=${s.limit ? s.spent / s.limit : 0} value=${`$${s.spent.toFixed(2)} / $${s.limit}`} level=${s.level} />
    </${Section}>
    <${ByPurpose} week=${s.week || []} />
    <${Section} title=${say("Quotas")} extra=${html`<span class="ok-font-status ok-tone-muted">
        ${data.reading_limits ? say("reading…") : data.limits_at ? `${say("updated")} ${data.limits_at}` : ""}</span>
      <button class="ok-act" onClick=${() => act(id, "limits").catch(() => {})}><span class="ok-act__label">Read again</span></button>`}>
      ${data.limits.length ? data.limits.map((x, i) => x.remaining === null
          ? html`<p key=${i} class="ok-font-status ok-tone-muted">${x.provider}: ${x.error || "no data"}</p>`
          : html`<${Meter} key=${i} label=${`${x.provider} ${x.what}`} part=${x.remaining}
              level=${x.remaining <= 0.2 ? "over" : x.remaining <= 0.5 ? "warn" : "ok"}
              value=${`${Math.round(x.remaining * 100)}% left${x.reset ? ` · resets ${x.reset}` : ""}${x.note ? ` · ${x.note}` : ""}`} />`)
        : html`<p class="ok-font-status ok-tone-muted">${data.reading_limits ? say("Reading the quotas…") : say("No quotas reported.")}</p>`}
    </${Section}>
  </div>`;
}

function Tabs() {
  const tab = hallTab.value;
  const live = town.value.sessions.filter((s) => s.running).length;
  const pick = (name) => () => { hallTab.value = name; };
  return html`<div class="ok-tabs" role="tablist">
    <button class=${cls("ok-tab", { "is-active": tab === "chat" })} role="tab" onClick=${pick("chat")}>Chat</button>
    <button class=${cls("ok-tab", { "is-active": tab === "hall" })} role="tab" onClick=${pick("hall")}>Hall</button>
    <button class=${cls("ok-tab", { "is-active": tab === "sessions" })} role="tab" onClick=${pick("sessions")}>Sessions${live ? ` (${live})` : ""}</button>
    <button class=${cls("ok-tab", { "is-active": tab === "limits" })} role="tab" onClick=${pick("limits")}>Limits</button>
  </div>`;
}

/** Full: the tab strip and one pane per tab (design/buildings/town_hall.json); only the open tab's
 *  pane shows, the others are dynamic panes that hide themselves. */
export function panes(id, data) {
  const tab = hallTab.value;
  return {
    tabs: () => html`<${Tabs} />`,
    chat: () => (tab === "chat" ? html`<${Chat} id=${id} data=${data} />` : null),
    hall: () => (tab === "hall" ? html`<${Hall} id=${id} h=${data.hall} />` : null),
    sessions: () => (tab === "sessions" ? html`<${WarTent} />` : null),
    limits: () => (tab === "limits" ? html`<${Limits} id=${id} data=${data} />` : null),
  };
}
