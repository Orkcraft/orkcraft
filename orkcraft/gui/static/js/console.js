// The console of a selected building, laid out as the TUI's (screens/console.py): to the right of the
// War Map, Info (UnitInfo), the garrison or a picked ork's Inventory (ClanRoster), the Command Card.
// Info as in the TUI: the name with Good / Bad / its goal / Demolish (an ork's: Good / Bad / Dismiss),
// why it is here, one line of what it spent and its runs with History, one line of who it listens to
// with Listen (a road there picks it: its handler, removing it). The Command Card: the type's own
// actions, Answer, Open, then the building's commands the TUI keeps on keys (Recruit, Pin, Revert,
// Redesign); for an ork Deploy, Orders & trigger, Halt, the steward's Watch now and Report. The data
// is the host's (gui/info.py, gui/console.py), asked while selected; the dialogs that change a
// garrison and the model calls' jobs are js/acts.js.
import { signal } from "@preact/signals";
import { useEffect, useState } from "preact/hooks";
import { html, cls } from "./html.js";
import { town, command, details, say } from "./link.js";
import { typeModule } from "./types.js";
import { opened, chosen, showBuilding, closeBuilding, selectOrk, DemolishButton } from "./windows.js";
import { HALL, deploy, showSession } from "./tent.js";
import { openOrders } from "./orders.js";
import { laying, pickedRoad, building as buildOpen } from "./build.js";
import { Dialog } from "./dialog.js";
import { RecruitDialog, OrdersDialog, ModelDialog, RedesignDialog } from "./acts.js";

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
  return html`<${Dialog} title=${say(`Bad result — ${b.title}`)} text=${say("What went wrong?")} onCancel=${onClose} warn
      actions=${html`<button class="ok-btn" onClick=${onClose}>${say("Cancel")}</button>
        <button class="ok-btn" onClick=${() => pick("inputs")}>${say("The inputs were broken")}</button>
        <button class="ok-btn danger" onClick=${() => pick("logic")}>${say("Its own logic was wrong")}</button>`}>
    ${ctx === null ? html`<p class="ok-tone-muted">${say("Looking…")}</p>` : html`
      ${ctx.last ? html`<pre class="gui-pre gui-orders__context">${ctx.last}</pre>`
                 : html`<p class="ok-font-status ok-tone-muted">${say("It has sent no result yet.")}</p>`}
      ${ctx.cascade.length > 0 && html`<p class="ok-font-status ok-tone-muted">Broken inputs: its suppliers pay —
        ${ctx.cascade.map(([title, share]) => `${title} −${share}`).join(", ")}.</p>`}`}
    <textarea class="ok-input gui-textarea" rows="3" placeholder=${say("What was wrong (optional)")}
      value=${note} onInput=${(e) => setNote(e.target.value)}></textarea>
  </${Dialog}>`;
}

function NoteDialog({ title, onClose, onSend }) {
  const [note, setNote] = useState("");
  return html`<${Dialog} title=${title} text=${say("What went wrong?")} onCancel=${onClose} warn
      actions=${html`<button class="ok-btn" onClick=${onClose}>${say("Cancel")}</button>
        <button class="ok-btn danger" onClick=${() => onSend(note)}>${say("Save the incident")}</button>`}>
    <textarea class="ok-input gui-textarea" rows="3" placeholder=${say("optional")}
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
      actions=${html`<button class="ok-btn primary" onClick=${onClose}>${say("Close")}</button>`}>
    ${h === null ? html`<p class="ok-tone-muted">${say("Looking…")}</p>` : html`<div class="gui-history">
      ${ork && html`<h3 class="ok-font-heading">${say("Runs")}</h3>
        ${h.runs.length ? html`<ul class="gui-rows">${h.runs.map((r) => html`<li key=${r.key}>
            <span class="ok-font-status ok-tone-muted">${r.when} · ${r.harness}</span> ${r.title}
            <button class="ok-act" onClick=${() => reopen(r.key)}><span class="ok-act__label">${say("Reopen")}</span></button></li>`)}</ul>`
          : html`<p class="ok-font-status ok-tone-muted">${say("No runs yet.")}</p>`}`}
      ${!tool && html`<h3 class="ok-font-heading">${say("Chronicles")}</h3>
        ${h.events.length ? html`<ul class="gui-rows">${h.events.map((e, n) => html`<li key=${n}>
            <span class="ok-font-status ok-tone-muted">${e.ts}</span> ${e.text}
            ${e.by && e.by !== "operator" && html`<span class="ok-font-status ok-tone-muted"> · ${e.by}</span>`}</li>`)}</ul>`
          : html`<p class="ok-font-status ok-tone-muted">${say("Nothing recorded yet.")}</p>`}`}
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
  return html`<${Dialog} title=${say(`Listen — ${b.title}`)} text=${say("Which building should it listen to?")} onCancel=${onClose}
      actions=${html`<button class="ok-btn" onClick=${onClose}>${say("Cancel")}</button>`}>
    <ul class="gui-catalog">${sources.map((x) => html`<li key=${x.id} class="gui-catalog__item" onClick=${() => pick(x.id)}>
      <b>${x.title}</b></li>`)}</ul>
  </${Dialog}>`;
}

// -- Info: what every building and ork shares --------------------------------------------------------

// The TUI's Info (screens/console.py UnitInfo): the name with its buttons on one row, why it is here
// (up to three lines), one quiet line of runs with History, one line of who it listens to with Listen.

function Row({ text, children, title }) {
  return html`<div class="gui-info__row"><span class="gui-info__text" title=${title || ""}>${text}</span>${children}</div>`;
}

function BuildingInfo({ b, i, redo, open }) {
  const run = (name, args = {}) => command(name, { id: b.id, ...args }).then(redo, () => {});
  const w = i.week;
  const runs = `${i.spend_plain} · week: ${w.runs} runs (${w.ok} ✓ ${w.failed} ✗) · ${w.results} results · good ${i.likes} bad ${i.dislikes}`;
  return html`<section class="gui-info">
    <${Row} text=${html`<b>${say(b.title)}</b>`}>
      <${Act} label=${say("Good")} title=${say("Its last result becomes a reference")} onClick=${() => run("building.like")} />
      <${Act} label=${say("Bad")} title=${say("What went wrong?")} onClick=${() => open("dislike")} />
      <${Act} label=${i.goal_title} title=${say("What the retros improve it towards: Thrift → Balance → Quality")}
        onClick=${() => run("building.goal")} />
      ${b.id !== HALL && html`<${DemolishButton} b=${b} />`}
    </${Row}>
    <p class="ok-font-body gui-info__about">${i.about_plain}</p>
    <${Row} text=${say(runs)} title=${runs}>
      <${Act} label=${say("History")} title=${say("Its chronicles")} onClick=${() => open("history")} />
    </${Row}>
    <${Row} text=${i.listens.length ? html`<span class="ok-tone-muted">${say("Listens:")} </span>${i.listens.map((l, n) => html`<span key=${l.key}>
        ${n > 0 && html`<span class="ok-tone-muted"> · </span>`}<button class="gui-link" title=${say("Pick this road: its handler, removing it")}
          onClick=${() => { pickedRoad.value = l.key; }}>◂ <b>${say(l.title)}</b></button>
        <span class="ok-tone-muted"> ${l.label} → </span>${l.handler || html`<span class="ok-tone-muted">${say("plain")}</span>`}</span>`)}`
      : html`<span class="ok-tone-muted">${say("Listens to nobody yet")}</span>`}>
      <${Act} label=${say("Listen")} title=${say("A road from another building into this one")} onClick=${() => open("listen")} />
    </${Row}>
  </section>`;
}

function OrkInfo({ b, o, i, redo, open }) {
  const run = (name, args = {}) => command(name, { id: b.id, ork: o.ref, ...args }).then(redo, () => {});
  const runs = [i.spend_plain, i.context && `${i.context} in context`, i.garrison && `good ${i.likes} bad ${i.dislikes}`,
                i.deployed ? "deployed" : "not deployed"].filter(Boolean).join(" · ");
  return html`<section class="gui-info">
    <${Row} text=${html`${o.tier && html`<span class="ok-tone-muted">${o.tier} </span>`}<b>${o.lead ? "★ " : ""}${o.name}</b>
        <span class="ok-tone-muted"> · ${say(b.title)}</span>`}>
      ${i.garrison && html`<${Act} label=${say("Good")} title=${say("Good work: noted on this ork")} onClick=${() => run("ork.like")} />
        <${Act} label=${say("Bad")} title=${say("What went wrong?")} onClick=${() => open("ork-bad")} />`}
      ${i.garrison && !i.lead && html`<${Act} label=${say("Dismiss")} title=${say("It leaves the garrison (a steward stays)")}
        onClick=${() => command("ork.dismiss", { id: b.id, ork: o.ref }).then(() => selectOrk(null), () => {})} />`}
    </${Row}>
    <p class="ok-font-body gui-info__about">${i.about_plain}</p>
    <${Row} text=${say(runs)} title=${runs}>
      <${Act} label=${say("History")} title=${say("Its runs and chronicles")} onClick=${() => open("history")} />
    </${Row}>
  </section>`;
}

// -- the garrison and an ork's Inventory: the TUI's middle column (ClanRoster) ---------------------------

function GarrisonList({ b }) {
  return html`${b.garrison.length ? html`<ul class="gui-rows">${b.garrison.map((o, n) => html`<li key=${o.ref || o.name}
        class=${cls("gui-console__row", { "is-alert": o.status === "alert" })} title=${o.role || o.name}
        onClick=${() => o.ref && selectOrk(o.ref)}>
      <span class="ok-tone-muted">[${n + 1}]</span> ${o.status === "alert" && html`<span class="ok-word">?</span> `}
      ${o.lead ? "★ " : ""}${o.tier && html`<span class="ok-tone-muted">${o.tier} </span>`}<b>${o.name}</b>
      ${o.scheme && html` <span class="gui-scheme">${o.scheme}</span>`}
      ${o.status !== "alert" && html` <span class="ok-tone-muted">${o.status}</span>`}</li>`)}</ul>`
    : html`<p class="ok-font-status ok-tone-muted">${say("No orks yet — Recruit")}</p>`}`;
}

function Inventory({ i, open }) {
  const change = i.garrison && i.uses_model && i.kind !== "chain" && i.kind !== "script";
  return html`<ul class="gui-rows">
    <li class=${cls("gui-console__row", { "is-static": !change })} title=${change ? "Its harness and tier per step" : ""}
        onClick=${() => change && open("model")}>
      ${i.models.length ? i.models.slice(0, 2).map((m, n) => html`<span key=${n}>${n > 0 && html`<span class="ok-tone-muted">→</span>`}
          ${m.tier_label && html`<span class="ok-tone-muted">${m.tier_label} </span>`}<b>${m.model}</b></span>`)
        : html`<span class="ok-tone-muted">${say("no model")}</span>`}
      ${i.models.length > 2 && html`<span class="ok-tone-muted">·${i.models.length}</span>`}
      ${change && html` <span class="ok-word">⇄</span>`}</li>
    <li class="ok-tone-muted gui-console__sep">${say("tools")}</li>
    ${i.tools.length ? i.tools.map((u) => html`<li key=${u.tool} class="gui-console__row" title=${say("Its runs with this tool")}
        onClick=${() => open("history", u.tool)}>${u.name} <span class="ok-tone-muted">×${u.count}</span></li>`)
      : html`<li class="ok-font-status ok-tone-muted">${say("no tool calls yet")}</li>`}
  </ul>`;
}

// -- the Command Card: the building's own actions first, then its commands (the TUI's keys) ------------

function BuildingCommands({ b, i, redo, open }) {
  const run = (name) => command(name, { id: b.id }).then(redo, () => {});
  const quick = (a) => (a.id === "hall.preset" ? (buildOpen.value = true)
                                               : command("building.quick", { id: b.id, action: a.id }).catch(() => {}));
  return html`${(i ? i.quick : []).map((a) => html`<${Act} key=${a.id} label=${a.label} onClick=${() => quick(a)} />`)}
    ${b.alert && html`<${Act} label=${say("Answer")} onClick=${() => openOrders(b.alert.id)} />`}
    <${Act} label=${say("Open")} title=${say("Its whole window (or click its hut again)")} onClick=${() => showBuilding(b.id)} />
    <hr class="gui-card__sep" />
    <${Act} label=${say("Recruit")} title=${say("A new ork for its garrison")} onClick=${() => open("recruit")} />
    ${i && html`<${Act} label=${say(i.pinned ? "Unpin" : "Pin")} title=${say("A pinned building keeps its place on the town")}
      onClick=${() => run("building.pin")} />`}
    ${b.id !== HALL && html`<${Act} label=${say("Revert")} title=${say("Back to its previous checkpoint")} onClick=${() => run("building.revert")} />`}
    <${Act} label=${say("Redesign window")} title=${say("Its steward redraws its window")} onClick=${() => open("redesign")} />`;
}

function OrkCommands({ b, o, open }) {
  const agent = o.kind === "agent" || o.kind === "hybrid";
  return html`${o.status === "alert" && b.alert && html`<${Act} label=${say("Resolve alert")} onClick=${() => openOrders(b.alert.id)} />`}
    ${agent && html`<${Act} label=${o.session ? "Open session" : "Deploy"} onClick=${() => deploy(o.ref)} />`}
    <${Act} label=${say("Standing orders & trigger")} title=${say("What it is told to do, and when it starts")} onClick=${() => open("orders")} />
    <${Act} label=${say("Halt")} onClick=${() => command("ork.halt", { id: b.id, ork: o.ref }).catch(() => {})} />
    ${o.lead && html`<${Act} label=${say("Watch now")} title=${say("Its steward looks at the building: free metrics, a model only on findings")}
      onClick=${() => command("ork.watch", { id: b.id, ork: o.ref }).catch(() => {})} />
      <${Act} label=${say("Report")} title=${say("The steward's last findings and proposals")}
      onClick=${() => command("ork.report", { id: b.id }).catch(() => {})} />`}
    <hr class="gui-card__sep" />
    <${Act} label=${say("Back")} title=${say("Back to the building (Esc)")} onClick=${() => selectOrk(null)} />`;
}

/** The command view: the top of the Command Card is the type's cut-down main screen, `preview(id, data)`
 * from its detail (js/types.js; docs/design/building-views.md); a type without one shows its buttons only. */
function Preview({ b }) {
  const mod = b.page ? typeModule(b.type) : null;
  const d = details.value[b.id];
  if (!mod || !mod.preview || !d || !d.data) return null;
  return html`<div class="gui-card__preview">${mod.preview(b.id, d.data)}</div>
    <hr class="gui-card__sep" />`;
}

function Window({ cls: c, title, label, onClose, children }) {
  return html`<section class=${`ok-win ${c}`} aria-label=${label || title}>
    <div class="ok-win__frame">
      <div class="ok-win__bar"><span class="ok-win__title">${title}</span>
        ${onClose && html`<button class="gui-tab__close gui-win__close" title=${say("Let go (Esc)")} aria-label=${say("Let go")}
          onClick=${onClose}>×</button>`}</div>
      <div class="ok-win__body gui-console__body">${children}</div>
    </div>
  </section>`;
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
  return html`<${Window} cls=${cls("is-active gui-console", { "is-alert": !!b.alert })} title=${say("Info")} label=${say(`Info — ${b.title}`)}
      onClose=${() => closeBuilding()}>
    ${!i ? html`<p class="ok-font-status ok-tone-muted">${say("Looking…")}</p>`
      : o ? html`<${OrkInfo} b=${b} o=${o} i=${i} redo=${redo} open=${open} />`
          : html`<${BuildingInfo} b=${b} i=${i} redo=${redo} open=${open} />`}
  </${Window}>
  <${Window} cls="gui-roster" title=${say(o ? "Inventory" : "Garrison")}>
    ${o ? i && html`<${Inventory} i=${i} open=${open} />` : html`<${GarrisonList} b=${b} />`}
  </${Window}>
  <${Window} cls="gui-card" title=${say("Commands")} label=${say("Command Card")}>
    ${!o && html`<${Preview} b=${b} />`}
    ${o ? html`<${OrkCommands} b=${b} o=${o} open=${open} />` : html`<${BuildingCommands} b=${b} i=${i} redo=${redo} open=${open} />`}
  </${Window}>
  ${dialog && dialog.kind === "dislike" && html`<${DislikeDialog} b=${b} onClose=${close} onDone=${redo} />`}
  ${dialog && dialog.kind === "ork-bad" && o && html`<${NoteDialog} title=${say(`Bad work — ${o.name}`)} onClose=${close}
    onSend=${(note) => command("ork.dislike", { id: b.id, ork: o.ref, note }).then(() => { close(); redo(); }, () => {})} />`}
  ${dialog && dialog.kind === "history" && html`<${HistoryDialog} b=${b} ork=${o} tool=${dialog.tool} onClose=${close} />`}
  ${dialog && dialog.kind === "listen" && html`<${ListenDialog} b=${b} onClose=${close} />`}
  ${dialog && dialog.kind === "recruit" && i && html`<${RecruitDialog} b=${b} tiers=${i.tiers || []} onClose=${close} />`}
  ${dialog && dialog.kind === "redesign" && html`<${RedesignDialog} b=${b} onClose=${close} />`}
  ${dialog && dialog.kind === "orders" && i && o && html`<${OrdersDialog} b=${b} i=${i} onClose=${close} onDone=${redo} />`}
  ${dialog && dialog.kind === "model" && i && o && html`<${ModelDialog} b=${b} i=${i} onClose=${close} onDone=${redo} />`}`;
}

/** The selected building's console, beside the War Map in the strip over the town's bottom. */
export function Selected() {
  const c = chosen();
  return c && !c.full ? html`<${Console} b=${c.b} orkRef=${opened.value.ork} />` : null;
}
