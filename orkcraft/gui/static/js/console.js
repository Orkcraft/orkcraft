// The console of a selected building, as the TUI's (screens/console.py), in the strip at the bottom
// right. Info holds what every building and ork shares: 👍 / 👎, the goal, pin, revert, recruit,
// redesign, demolish, an ork's orders and dismiss, why it is here, what it spent, its history, who it
// listens to (each road's handler, removing it). Beside it the garrison; an ork picked there turns it
// into the ork's Inventory (its models, the tools of its latest runs). The Command Card holds what
// only this building or ork does: its window, its question, its type's quick actions, deploy, halt,
// the steward's watch. The data is the host's (gui/info.py, gui/console.py), asked while selected;
// the dialogs that change a garrison and the model calls' jobs are js/acts.js.
import { signal } from "@preact/signals";
import { useEffect, useState } from "preact/hooks";
import { html, cls } from "./html.js";
import { town, command } from "./link.js";
import { opened, chosen, showBuilding, closeBuilding, selectOrk, Badge, Question, DemolishButton } from "./windows.js";
import { HALL, deploy, showSession } from "./tent.js";
import { openOrders } from "./orders.js";
import { laying, building as buildOpen } from "./build.js";
import { Dialog } from "./dialog.js";
import { RecruitDialog, OrdersDialog, ModelDialog, RedesignDialog, HandlerDialog } from "./acts.js";

const infos = signal({});          // "<building>" or "<building>|<ork ref>" → what `info` said
const asked = new Map();           // the same key → when it was asked last
const ASK_MS = 2000;               // while the town keeps changing, at most this often

function keyOf(id, ork) {
  return ork ? `${id}|${ork}` : id;
}

function ask(id, ork, force = false) {
  const key = keyOf(id, ork);
  const now = Date.now();
  if (!force && now - (asked.get(key) || 0) < ASK_MS) return;
  asked.set(key, now);
  command("info", ork ? { id, ork } : { id }).then((r) => { infos.value = { ...infos.value, [key]: r }; }, () => {});
}

/** What the host says of the selected building or ork, asked again as the town changes. */
function useInfo(id, ork) {
  const t = town.value;
  useEffect(() => { ask(id, ork); }, [id, ork, t]);
  return infos.value[keyOf(id, ork)];
}

function Act({ label, title, onClick }) {
  return html`<button class="ok-act" title=${title || label} onClick=${onClick}>
    <span class="ok-act__label">${label}</span></button>`;
}

// -- dialogs: 👎 for a building, a note for an ork's 👎, the chronicles --------------------------------

function DislikeDialog({ b, onClose, onDone }) {
  const [ctx, setCtx] = useState(null);
  const [note, setNote] = useState("");
  useEffect(() => { command("building.dislike_context", { id: b.id }).then(setCtx, () => setCtx({ last: "", cascade: [] })); }, [b.id]);
  const pick = (kind) => command("building.dislike", { id: b.id, kind, note }).then(() => { onClose(); onDone(); }, () => {});
  return html`<${Dialog} title=${`Bad result — ${b.title}`} text="What went wrong?" onCancel=${onClose} warn
      actions=${html`<button class="ok-btn" onClick=${onClose}>Cancel</button>
        <button class="ok-btn" onClick=${() => pick("inputs")}>The inputs were broken</button>
        <button class="ok-btn danger" onClick=${() => pick("logic")}>Its own logic was wrong</button>`}>
    ${ctx === null ? html`<p class="ok-tone-muted">Looking…</p>` : html`
      ${ctx.last ? html`<pre class="gui-pre gui-orders__context">${ctx.last}</pre>`
                 : html`<p class="ok-font-status ok-tone-muted">It has sent no result yet.</p>`}
      ${ctx.cascade.length > 0 && html`<p class="ok-font-status ok-tone-muted">Broken inputs: its suppliers pay —
        ${ctx.cascade.map(([title, share]) => `${title} −${share}`).join(", ")}.</p>`}`}
    <textarea class="ok-input gui-textarea" rows="3" placeholder="What was wrong (optional)"
      value=${note} onInput=${(e) => setNote(e.target.value)}></textarea>
  </${Dialog}>`;
}

function NoteDialog({ title, onClose, onSend }) {
  const [note, setNote] = useState("");
  return html`<${Dialog} title=${title} text="What went wrong?" onCancel=${onClose} warn
      actions=${html`<button class="ok-btn" onClick=${onClose}>Cancel</button>
        <button class="ok-btn danger" onClick=${() => onSend(note)}>Save the incident</button>`}>
    <textarea class="ok-input gui-textarea" rows="3" placeholder="optional"
      value=${note} onInput=${(e) => setNote(e.target.value)}></textarea>
  </${Dialog}>`;
}

function HistoryDialog({ b, ork, tool, onClose }) {
  const [h, setH] = useState(null);
  useEffect(() => {
    command("history", { id: b.id, ork: ork ? ork.ref : "", tool: tool || "" }).then(setH, () => setH({ events: [], runs: [] }));
  }, [b.id, ork && ork.ref, tool]);
  const reopen = (key) => command("sessions.resume", { key }).then((k) => { onClose(); showSession(k); }, () => {});
  const who = ork ? ork.name : b.title;
  return html`<${Dialog} title=${tool ? `${who} — runs with ${tool}` : `History — ${who}`} onCancel=${onClose}
      actions=${html`<button class="ok-btn primary" onClick=${onClose}>Close</button>`}>
    ${h === null ? html`<p class="ok-tone-muted">Looking…</p>` : html`<div class="gui-history">
      ${ork && html`<h3 class="ok-font-heading">Runs</h3>
        ${h.runs.length ? html`<ul class="gui-rows">${h.runs.map((r) => html`<li key=${r.key}>
            <span class="ok-font-status ok-tone-muted">${r.when} · ${r.harness}</span> ${r.title}
            <button class="ok-act" onClick=${() => reopen(r.key)}><span class="ok-act__label">Reopen</span></button></li>`)}</ul>`
          : html`<p class="ok-font-status ok-tone-muted">No runs yet.</p>`}`}
      ${!tool && html`<h3 class="ok-font-heading">Chronicles</h3>
        ${h.events.length ? html`<ul class="gui-rows">${h.events.map((e, n) => html`<li key=${n}>
            <span class="ok-font-status ok-tone-muted">${e.ts}</span> ${e.text}
            ${e.by && e.by !== "operator" && html`<span class="ok-font-status ok-tone-muted"> · ${e.by}</span>`}</li>`)}</ul>`
          : html`<p class="ok-font-status ok-tone-muted">Nothing recorded yet.</p>`}`}
    </div>`}
  </${Dialog}>`;
}

/** Pick the building a new road comes from (➕ Listen); the road itself is the Road dialog's. */
function ListenDialog({ b, onClose }) {
  const t = town.value;
  const space = t.orkspaces.find((o) => o.id === t.active_orkspace);
  const here = new Set(space ? space.buildings : t.buildings.map((x) => x.id));
  here.add(HALL);
  const sources = t.buildings.filter((x) => x.id !== b.id && here.has(x.id));
  const pick = (from) => { onClose(); laying.value = { from, to: b.id }; };
  return html`<${Dialog} title=${`Listen — ${b.title}`} text="Which building should it listen to?" onCancel=${onClose}
      actions=${html`<button class="ok-btn" onClick=${onClose}>Cancel</button>`}>
    <ul class="gui-catalog">${sources.map((x) => html`<li key=${x.id} class="gui-catalog__item" onClick=${() => pick(x.id)}>
      <b>${x.title}</b></li>`)}</ul>
  </${Dialog}>`;
}

// -- Info: what every building and ork shares --------------------------------------------------------

function BuildingInfo({ b, i, redo, open }) {
  const run = (name, args = {}) => command(name, { id: b.id, ...args }).then(redo, () => {});
  const w = i.week;
  return html`<section class="gui-info">
    <div class="gui-info__acts">
      <${Act} label="Good" title="Its last result becomes a reference" onClick=${() => run("building.like")} />
      <${Act} label="Bad" title="What went wrong?" onClick=${() => open("dislike")} />
      <${Act} label=${i.goal_title} title="What the retros improve it towards: Thrift, Balance, Quality"
        onClick=${() => run("building.goal")} />
      <${Act} label=${i.pinned ? "Unpin" : "Pin"} title="A pinned building keeps its place on the town"
        onClick=${() => run("building.pin")} />
      <${Act} label="Recruit" title="A new ork for its garrison" onClick=${() => open("recruit")} />
      <${Act} label="Redesign" title="Its steward redraws its window" onClick=${() => open("redesign")} />
      ${b.id !== HALL && html`<${Act} label="Revert" title="Back to its previous checkpoint"
        onClick=${() => run("building.revert")} />
      <${DemolishButton} b=${b} />`}
    </div>
    <p class="ok-font-body gui-info__about">${i.about_plain}</p>
    <p class="ok-font-status ok-tone-muted gui-info__line">
      ${i.spend_plain} · week: ${w.runs} runs (${w.ok} ok, ${w.failed} failed) · ${w.results} results ·
      good ${i.likes} · bad ${i.dislikes}
      <${Act} label="History" onClick=${() => open("history")} /></p>
    <div class="ok-font-status gui-info__line">
      <span class="ok-tone-muted">${i.listens.length ? "Listens:" : "Listens to nobody yet"}</span>
      <${Act} label="Listen" title="A road from another building into this one" onClick=${() => open("listen")} />
      ${i.listens.length > 0 && html`<ul class="gui-rows">${i.listens.map((l) => html`<li key=${l.key}>
        <b>${l.title}</b><span class="ok-tone-muted"> ${l.label} → </span>${l.handler || html`<span class="ok-tone-muted">plain</span>`}
        <${Act} label="Handler" title="Who takes what it brings" onClick=${() => open("handler", l)} />
        <${Act} label="Remove" title="Take this road up" onClick=${() => command("roads.remove", { key: l.key }).then(redo, () => {})} />
      </li>`)}</ul>`}
    </div>
  </section>`;
}

function OrkInfo({ b, o, i, redo, open }) {
  const run = (name, args = {}) => command(name, { id: b.id, ork: o.ref, ...args }).then(redo, () => {});
  return html`<section class="gui-info">
    <div class="gui-info__acts">
      ${i.garrison && html`<${Act} label="Good" title="Good work: noted on this ork" onClick=${() => run("ork.like")} />
        <${Act} label="Bad" title="What went wrong?" onClick=${() => open("ork-bad")} />`}
      ${i.garrison && html`<${Act} label="Orders" title="Its orders and trigger" onClick=${() => open("orders")} />`}
      ${i.garrison && !i.lead && html`<${Act} label="Dismiss" title="It leaves the garrison"
        onClick=${() => command("ork.dismiss", { id: b.id, ork: o.ref }).then(() => selectOrk(null), () => {})} />`}
      <${Act} label="History" onClick=${() => open("history")} />
    </div>
    <p class="ok-font-body gui-info__about">${i.about_plain}</p>
    <p class="ok-font-status ok-tone-muted gui-info__line">${[i.spend_plain, i.context && `${i.context} in context`,
      i.garrison && `good ${i.likes} · bad ${i.dislikes}`, i.deployed ? "deployed" : "not deployed"].filter(Boolean).join(" · ")}</p>
  </section>`;
}

// -- the garrison, and an ork's Inventory ------------------------------------------------------------

function GarrisonList({ b }) {
  return html`<section class="gui-console__list">
    <h3 class="ok-font-heading">Garrison</h3>
    ${b.garrison.length ? html`<ul class="gui-rows">${b.garrison.map((o, n) => html`<li key=${o.ref || o.name}
        class=${cls("gui-console__row", { "is-alert": o.status === "alert" })} onClick=${() => o.ref && selectOrk(o.ref)}>
      <span class="ok-tone-muted">${n + 1}</span> ${o.status === "alert" && html`<span class="ok-word">?</span> `}
      ${o.tier && html`<span class="ok-tone-muted">${o.tier} </span>`}<span class="ok-font-label">${o.name}</span>
      ${o.scheme && html` <span class="gui-scheme">${o.scheme}</span>`}
      <span class="ok-font-status ok-tone-muted"> · ${o.lead ? "steward" : o.kind} · ${o.status}</span></li>`)}</ul>`
      : html`<p class="ok-font-status ok-tone-muted">No orks yet.</p>`}
  </section>`;
}

function Inventory({ i, open }) {
  return html`<section class="gui-console__list">
    <h3 class="ok-font-heading">Inventory</h3>
    <div class="ok-font-status">${i.models.length ? i.models.map((m, n) => html`<span key=${n}>
        ${n > 0 && html`<span class="ok-tone-muted"> → </span>`}${m.tier_label && html`<span class="ok-tone-muted">${m.tier_label} </span>`}<b>${m.model}</b></span>`)
      : html`<span class="ok-tone-muted">no model</span>`}
      ${i.garrison && i.uses_model && i.kind !== "chain" && i.kind !== "script" && html`<button class="ok-act"
        title="Its harness and tier per step" onClick=${() => open("model")}><span class="ok-act__label">Change</span></button>`}</div>
    <h3 class="ok-font-heading gui-console__sub">Tools</h3>
    ${i.tools.length ? html`<ul class="gui-rows">${i.tools.map((u) => html`<li key=${u.tool} class="gui-console__row"
        title="Its runs with this tool" onClick=${() => open("history", u.tool)}>
      ${u.name} <span class="ok-tone-muted">×${u.count}</span></li>`)}</ul>`
      : html`<p class="ok-font-status ok-tone-muted">No tool calls yet.</p>`}
  </section>`;
}

// -- the Command Card: what only this building or ork does --------------------------------------------

function BuildingCommands({ b, i }) {
  const quick = (a) => (a.id === "hall.preset" ? (buildOpen.value = true)
                                               : command("building.quick", { id: b.id, action: a.id }).catch(() => {}));
  return html`<${Act} label="Open" title="Its whole window (or click its hut again)" onClick=${() => showBuilding(b.id)} />
    ${b.alert && html`<${Act} label="Answer" onClick=${() => openOrders(b.alert.id)} />`}
    ${(i ? i.quick : []).map((a) => html`<${Act} key=${a.id} label=${a.label} onClick=${() => quick(a)} />`)}`;
}

function OrkCommands({ b, o, i }) {
  const agent = o.kind === "agent" || o.kind === "hybrid";
  return html`${agent && html`<${Act} label=${o.session ? "Its session" : "Deploy"} onClick=${() => deploy(o.ref)} />`}
    ${o.session && html`<${Act} label="Halt" onClick=${() => command("ork.halt", { id: b.id, ork: o.ref }).catch(() => {})} />`}
    ${o.status === "alert" && b.alert && html`<${Act} label="Answer" onClick=${() => openOrders(b.alert.id)} />`}
    ${o.lead && html`<${Act} label="Watch now" title="Its steward looks at the building: free metrics, a model only on findings"
      onClick=${() => command("ork.watch", { id: b.id, ork: o.ref }).catch(() => {})} />
      <${Act} label="Report" title="The steward's last findings and proposals"
      onClick=${() => command("ork.report", { id: b.id }).catch(() => {})} />`}
    <${Act} label="Back" title="Back to the building (Esc)" onClick=${() => selectOrk(null)} />`;
}

function Console({ b, orkRef }) {
  const o = orkRef ? b.garrison.find((x) => x.ref === orkRef) : null;
  const ork = o ? o.ref : null;
  const i = useInfo(b.id, ork);
  const [dialog, setDialog] = useState(null);         // {kind, tool, road}
  useEffect(() => setDialog(null), [b.id, ork]);
  const redo = () => ask(b.id, ork, true);
  const open = (kind, x = "") => setDialog(typeof x === "string" ? { kind, tool: x } : { kind, road: x });
  const close = () => setDialog(null);
  return html`<section class=${cls("ok-win is-active gui-console", { "is-alert": !!b.alert })} aria-label=${b.title}>
    <div class="ok-win__frame">
      <div class="ok-win__bar">
        <span class="ok-win__title">${b.title}${o ? html`<span class="ok-tone-muted"> · ${o.name}</span>` : ""}</span>
        <${Badge} garrison=${b.garrison} alert=${b.alert} />
        <button class="gui-tab__close gui-win__close" title="Let go (Esc)" aria-label="Let go"
          onClick=${() => closeBuilding()}>×</button>
      </div>
      <div class="ok-win__body gui-console__body">
        <div class="gui-console__main">
          ${b.alert && !o && html`<${Question} alert=${b.alert} />`}
          ${!i ? html`<p class="ok-font-status ok-tone-muted">Looking…</p>`
            : o ? html`<${OrkInfo} b=${b} o=${o} i=${i} redo=${redo} open=${open} />`
                : html`<${BuildingInfo} b=${b} i=${i} redo=${redo} open=${open} />`}
          ${o ? i && html`<${Inventory} i=${i} open=${open} />` : html`<${GarrisonList} b=${b} />`}
        </div>
        <div class="gui-console__card" aria-label="Commands">
          ${o ? html`<${OrkCommands} b=${b} o=${o} i=${i} />` : html`<${BuildingCommands} b=${b} i=${i} />`}
        </div>
      </div>
    </div>
    ${dialog && dialog.kind === "dislike" && html`<${DislikeDialog} b=${b} onClose=${close} onDone=${redo} />`}
    ${dialog && dialog.kind === "ork-bad" && o && html`<${NoteDialog} title=${`Bad work — ${o.name}`} onClose=${close}
      onSend=${(note) => command("ork.dislike", { id: b.id, ork: o.ref, note }).then(() => { close(); redo(); }, () => {})} />`}
    ${dialog && dialog.kind === "history" && html`<${HistoryDialog} b=${b} ork=${o} tool=${dialog.tool} onClose=${close} />`}
    ${dialog && dialog.kind === "listen" && html`<${ListenDialog} b=${b} onClose=${close} />`}
    ${dialog && dialog.kind === "recruit" && i && html`<${RecruitDialog} b=${b} tiers=${i.tiers || []} onClose=${close} />`}
    ${dialog && dialog.kind === "redesign" && html`<${RedesignDialog} b=${b} onClose=${close} />`}
    ${dialog && dialog.kind === "handler" && html`<${HandlerDialog} road=${dialog.road} onClose=${close} onDone=${redo} />`}
    ${dialog && dialog.kind === "orders" && i && o && html`<${OrdersDialog} b=${b} i=${i} onClose=${close} onDone=${redo} />`}
    ${dialog && dialog.kind === "model" && i && o && html`<${ModelDialog} b=${b} i=${i} onClose=${close} onDone=${redo} />`}
  </section>`;
}

/** The selected building's console, beside the War Map in the strip over the town's bottom. */
export function Selected() {
  const c = chosen();
  return c && !c.full ? html`<${Console} b=${c.b} orkRef=${opened.value.ork} />` : null;
}
