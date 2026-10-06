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

/** Change, on a plan: the person goes on talking, and the Warchief asks the Town Builder again. */
const changePlan = () => fill("Change the plan: ");

const keep = (e) => e.stopPropagation();          // a press on a control is not a press on the hut

/** A question for the Warchief (Camp's hut asks it); its answer comes in the town's line and the hall's Chat. */
export function askWarchief(id, text) {
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

function HallCard({ b }) {
  const news = (b.card && b.card.news) || [];
  return html`<div class="gui-form">
    ${news.length > 0 && html`<ul class="ok-hut__lines">${news.map((line, i) => html`<li key=${i}>${say(line)}</li>`)}</ul>`}
    ${!news.length && html`<div class="gui-form__row"><${AskField} id=${b.id} /></div>`}
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

function Chat({ id, data, height }) {
  const box = useRef(null);
  useEffect(() => { if (box.current) box.current.scrollTop = box.current.scrollHeight; }, [data.chat.length, data.thinking]);
  const name = data.warchief;
  return html`<div class="gui-form" style="max-height:none;overflow:visible">
    <div class="gui-head"><b>${say(`Ask the ${name}`)}</b><span class="gui-head__spacer"></span>
      ${data.chat.length > 0 && html`<button class="ok-act" onClick=${() => act(id, "forget").catch(() => {})}>
        <span class="ok-act__label">New chat</span></button>`}</div>
    ${(data.chat.length > 0 || data.thinking) && html`<ul class="gui-rows" ref=${box} style=${`max-height:${height};overflow:auto`}>
      ${data.chat.map((m, i) => html`<${Message} key=${i} m=${m} name=${name} />`)}
      ${data.thinking && html`<li class="ok-font-status ok-tone-wait">${say(`${name} is answering…`)}</li>`}
    </ul>`}
    <${AskField} id=${id} />
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

function Hall({ id, h }) {
  const b = town.value.buildings.find((x) => x.id === id);
  const garrison = b ? b.garrison : [];
  const titles = Object.fromEntries(town.value.buildings.map((x) => [x.id, say(x.title)]));
  return html`<div>
    ${h.order && html`<${Section} title=${say("A town waits to be raised")}>
      <p class="ok-font-body">“${h.order}”</p>
      <p class="ok-font-status ok-tone-muted">${say("The Town Builder plans it (in the TUI: F10); you approve the plan before anything is raised.")}</p>
    </${Section}>`}
    <${Section} title=${say("Orks of the hall")}>
      <ul class="gui-rows">
        ${garrison.map((o) => html`<li key=${o.ref || o.name}><b>${say(o.name)}</b>
          <span class="ok-font-status ok-tone-muted"> · ${o.lead ? say("steward") : o.tier || o.kind} · ${o.status}</span></li>`)}
        ${h.builders.map((x) => html`<li key=${x.name}><b>${say(x.name)}</b>
          <span class="ok-font-status ok-tone-muted"> · ${x.role}</span></li>`)}
        ${h.agents.map((a) => html`<li key=${a.id}><b>${say(a.name)}</b>
          <span class="ok-font-status ok-tone-muted"> · ${a.area} · </span>
          <span class=${cls("ok-font-status", { "ok-tone-wait": a.serious > 0 })}>${h.audit ? `${a.found} found${a.serious ? `, ${a.serious} to look at` : ""}` : "not audited yet"}</span></li>`)}
      </ul>
    </${Section}>
    <${Section} title=${h.audit ? `${say("Last audit")} ${h.audit.ts.slice(0, 16).replace("T", " ")}` : say("Audit")}
        extra=${html`<button class="ok-act" onClick=${() => act(id, "audit").catch(() => {})}><span class="ok-act__label">Audit now</span></button>`}>
      <${Rows} items=${h.audit ? h.audit.findings : []} empty=${h.audit ? say("Nothing found.")
          : say("No audit yet: the Warder, the Pathfinder and the Treasurer look over the town in a moment, no model call.")}
        row=${(f, i) => html`<li key=${i} class=${cls("ok-font-body", { "ok-tone-error": f.severity === "high", "ok-tone-wait": f.severity === "warn" })}>
          ${f.building && titles[f.building] ? html`<button class="gui-link" onClick=${() => openBuilding(f.building)}>${titles[f.building]}</button>: ` : ""}${f.text}</li>`} />
    </${Section}>
    <${Section} title=${say("Proposals")} extra=${html`<span class="ok-font-status ok-tone-muted">${h.pending} pending</span>`}>
      <${Rows} items=${h.proposals} empty=${say("No proposals yet — the Building retro makes them.")}
        row=${(p, i) => html`<li key=${i} class="ok-font-body">${MARK[p.status] || "·"} ${p.ts} <b>${titles[p.building] || p.building}</b>
          · ${p.action} ${p.target}<span class="ok-font-status ok-tone-muted"> — ${p.why}</span>
          ${p.status === "pending" && html` <${Answer} onApply=${() => act(id, "proposal", { id: p.id, choice: "apply" })}
            onNo=${() => act(id, "proposal", { id: p.id, choice: "dismiss" })} no=${say("Dismiss")} />`}</li>`} />
      <p class="ok-font-status ok-tone-muted">${say("Town retro")}: ${h.weekly
        ? `${h.weekly.ts.slice(0, 10)} · ${h.weekly.items} items, ${h.weekly.applied} applied${h.weekly.waiting ? `, ${h.weekly.waiting} waiting` : ""}`
        : say("not run yet — Sunday 05:00")}</p>
      ${h.weekly && h.weekly.rows.length > 0 && html`<ul class="gui-rows">${h.weekly.rows.map((x) => html`<li key=${x.n} class="ok-font-body">
        · ${x.building && titles[x.building] ? html`<b>${titles[x.building]}</b>: ` : ""}${x.title}
        <span class="ok-font-status ok-tone-muted"> — ${x.why}</span>
        <${Answer} onApply=${() => act(id, "weekly", { n: x.n, choice: "apply" })}
          onNo=${() => act(id, "weekly", { n: x.n, choice: "decline" })} no=${say("Decline")} /></li>`)}</ul>`}
    </${Section}>
    <${Section} title=${say("The Elders")}>
      <${Rows} items=${h.elders} empty=${say("Nothing judged yet — they read the orks' questions in quiet hours.")}
        row=${(r, i) => html`<li key=${i} class="ok-font-body">${MARK[r.how]} ${r.ts} ${r.who && `${r.who} · `}${r.question}
          <span class="ok-font-status ok-tone-muted"> → ${r.how === "left" ? "left to you" : `${r.how} [${r.key}] ${r.option}`}${r.why ? ` — ${r.why}` : ""}</span></li>`} />
    </${Section}>
    <${Section} title=${say("The Council's Fast Path")}>
      <p class="ok-font-status ok-tone-muted">${h.fast_path.map((r) => `${r.name} (${r.duty})`).join(" · ")}</p>
      <${Rows} items=${h.reviews} empty=${say("No reviews yet.")}
        row=${(r, i) => html`<li key=${i} class="ok-font-body">${MARK[r.decision] || "·"} ${r.ts} ${r.kind} ${r.id}
          ${r.note && html`<span class="ok-font-status ok-tone-muted"> — ${r.note}</span>`}</li>`} />
    </${Section}>
    <${Section} title=${say("Good and bad of the stewards")}>
      <${Rows} items=${[...h.board.map((x) => ({ ...x, row: "board" })), ...h.incidents.map((x) => ({ ...x, row: "incident" }))]}
        empty=${say("No ratings yet.")}
        row=${(x, i) => x.row === "board"
          ? html`<li key=${i} class="ok-font-body"><b>${titles[x.building] || x.building}</b>: good ${x.likes} bad ${x.dislikes} · penalty ${x.penalty}</li>`
          : html`<li key=${i} class="ok-font-body ok-tone-wait">${x.ts} ${titles[x.building] || x.building} · ${x.kind}${x.how ? ` (${x.how})` : ""} → ${x.blamed}${x.note ? ` — ${x.note}` : ""}</li>`} />
    </${Section}>
  </div>`;
}

function Meter({ label, part, value, level }) {
  const width = part === null || part === undefined ? 0 : Math.max(0, Math.min(1, part)) * 100;
  return html`<div class=${cls("ok-meter", { "is-warn": level === "warn", "is-over": level === "over" })}>
    <span>${label}</span><span class="ok-meter__track"><span class="ok-meter__fill" style=${`width:${width}%`}></span></span>
    <span class="ok-meter__val">${value}</span></div>`;
}

function Limits({ id, data }) {
  const s = data.spend;
  return html`<div>
    <${Section} title=${say("Spend")}>
      <${Meter} label=${say("This run")} part=${s.limit ? s.spent / s.limit : 0} value=${`$${s.spent.toFixed(2)} / $${s.limit}`} level=${s.level} />
    </${Section}>
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
    chat: () => (tab === "chat" ? html`<${Chat} id=${id} data=${data} height="none" />` : null),
    hall: () => (tab === "hall" ? html`<${Hall} id=${id} h=${data.hall} />` : null),
    sessions: () => (tab === "sessions" ? html`<${WarTent} />` : null),
    limits: () => (tab === "limits" ? html`<${Limits} id=${id} data=${data} />` : null),
  };
}
