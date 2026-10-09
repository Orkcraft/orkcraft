// A building's Info in the town's panel (js/windows.js, docs/design/calm-town.md §2), in the order it is
// needed: its name with 👍 / 👎, why it is here and its runs with History; its own quick actions; its
// goal and Freedom; its garrison (Deploy, Its session); its steward (its tier and AI tool, Watch, Report, Redesign, the roads it
// listens to with their handlers, js/steward.js); its roads out; Demolish at the bottom. An ork picked in the
// garrison shows here with ← back: its Info, its models and tools, its commands (Deploy, Standing orders,
// Halt). The data is the host's (gui/info.py, gui/console.py), asked while open; the dialogs that change
// a garrison and the model calls' jobs are js/acts.js.
import { signal } from "@preact/signals";
import { useEffect, useState } from "preact/hooks";
import { html, cls } from "./html.js";
import { town, command, say } from "./link.js";
import { runQuick, typeModule } from "./types.js";
import { infoPage } from "./infopage.js";
import { selectOrk } from "./windows.js";
import { HALL, deploy, showSession } from "./tent.js";
import { openOrders } from "./orders.js";
import { laying } from "./build.js";
import { Dialog } from "./dialog.js";
import { OrdersDialog, ModelDialog, RedesignDialog, Field, Select } from "./acts.js";
import { StewardTitle, StewardWindow, StewardModels, BuildingSettings } from "./steward.js";
import { OrkHead, HutSprite, activeBiome, Scheme, TierMark } from "./icons.js";

const infos = signal({});          // "<building>" or "<building>|<ork ref>" → what `info` said
const asked = new Map();           // the same key → when it was asked last
const ASK_MS = 2000;               // while the town keeps changing, at most this often
const ROMAN = ["", "I", "II", "III"];

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

/** 👍 or 👎 with how many it got: a like or a dislike, the same in Office and in Camp. */
function Thumb({ up, count, title, onClick }) {
  const label = say(up ? "Good" : "Bad");
  return html`<button class=${cls("ok-act gui-thumb", { "is-down": !up })} title=${title} aria-label=${label} onClick=${onClick}>
    <span aria-hidden="true">${up ? "👍" : "👎"}</span><span class="gui-thumb__n">${count}</span></button>`;
}

function Act({ label, title, onClick }) {
  return html`<button class="ok-act" title=${title || label} onClick=${onClick}>
    <span class="ok-act__label">${label}</span></button>`;
}

// -- dialogs: 👎 for a building, a note for an ork's 👎, the chronicles --------------------------------

export function DislikeDialog({ b, onClose, onDone }) {
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

export function NoteDialog({ title, onClose, onSend }) {
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

/** ➕ Listen: the road dialog in words, the steward picks the source among the buildings here (build.js). */
function ListenDialog({ b, onClose }) {
  useEffect(() => {
    const t = town.value;
    const space = t.orkspaces.find((o) => o.id === t.active_orkspace);
    const here = new Set(space ? space.buildings : t.buildings.map((x) => x.id));
    here.add(HALL);
    laying.value = { from: null, to: b.id, among: t.buildings.filter((x) => x.id !== b.id && here.has(x.id)).map((x) => x.id) };
    onClose();
  }, []);
  return null;
}

// -- Info: what every building and ork shares --------------------------------------------------------

// The TUI's Info (screens/console.py UnitInfo): the name with its buttons on one row, why it is here
// (up to three lines), one quiet line of runs with History.

function Row({ text, children, title }) {
  return html`<div class="gui-info__row"><span class="gui-info__text" title=${title || ""}>${text}</span>${children}</div>`;
}

function BuildingInfo({ b, i, redo, open }) {
  const run = (name, args = {}) => command(name, { id: b.id, ...args }).then(redo, () => {});
  const w = i.week;
  const runs = `${i.spend_plain} · week: ${w.runs} runs (${w.ok} ✓ ${w.failed} ✗) · ${w.results} results`;
  const renown = `Renown: ${i.level ? ROMAN[i.level] : "none yet"}`;
  return html`<section class="gui-info">
    <div class="gui-info__head">
      <${HutSprite} type=${b.type} biome=${activeBiome()} goal=${i.goal} level=${i.level || 0} />
      <div class="gui-info__renown">
        <span class="ok-font-body">${i.level_mark ? html`<b>${i.level_mark}</b> · ${say(i.goal_title)}` : say(`${renown} · ${i.goal_title}`)}</span>
        ${i.next && html`<span class="ok-font-status ok-tone-muted">${say(i.next)}</span>`}
      </div>
    </div>
    <${Row} text=${html`<b>${say(b.title)}</b>`}>
      <${Thumb} up count=${i.likes} title=${say("Good: its last result becomes a reference")} onClick=${() => run("building.like")} />
      <${Thumb} count=${i.dislikes} title=${say("Bad: what went wrong?")} onClick=${() => open("dislike")} />
    </${Row}>
    <p class="ok-font-body gui-info__about">${i.about_plain}</p>
    <${Row} text=${say(runs)} title=${runs}>
      <${Act} label=${say("History")} title=${say("Its chronicles")} onClick=${() => open("history")} />
    </${Row}>
  </section>`;
}

function OrkInfo({ b, o, i, redo, open }) {
  const run = (name, args = {}) => command(name, { id: b.id, ork: o.ref, ...args }).then(redo, () => {});
  const runs = [i.spend_plain, i.context && `${i.context} in context`,
                i.deployed ? "deployed" : "not deployed"].filter(Boolean).join(" · ");
  return html`<section class="gui-info">
    <${Row} text=${html`${o.tier && html`<span class="ok-tone-muted"><${TierMark} tier=${o.tier} /> </span>`}<b>${o.lead ? "★ " : ""}${o.name}</b>
        <span class="ok-tone-muted"> · ${say(b.title)}</span>`}>
      ${i.garrison && html`<${Thumb} up count=${i.likes} title=${say("Good work: noted on this ork")} onClick=${() => run("ork.like")} />
        <${Thumb} count=${i.dislikes} title=${say("Bad work: what went wrong?")} onClick=${() => open("ork-bad")} />`}
      ${i.garrison && !i.lead && html`<${Act} label=${say("Dismiss")} title=${say("It leaves the garrison (a steward stays)")}
        onClick=${() => command("ork.dismiss", { id: b.id, ork: o.ref }).then(() => selectOrk(null), () => {})} />`}
    </${Row}>
    <p class="ok-font-body gui-info__about">${i.about_plain}</p>
    <${Row} text=${say(runs)} title=${runs}>
      <${Act} label=${say("History")} title=${say("Its runs and chronicles")} onClick=${() => open("history")} />
    </${Row}>
  </section>`;
}

// -- a picked ork's Inventory: the TUI's middle column (ClanRoster) -------------------------------------

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

// -- the garrison and the roads out -------------------------------------------------------------------

function Roads({ b, t }) {
  const titles = Object.fromEntries(t.buildings.map((x) => [x.id, say(x.title)]));
  const incoming = t.roads.filter((r) => r.to === b.id);
  const outgoing = t.roads.filter((r) => r.from === b.id);
  if (!incoming.length && !outgoing.length) return null;
  const row = (r, other) => html`<li key=${r.id}>
    <span class="ok-font-label">${titles[other] || other}</span>
    <span class="ok-font-status ok-tone-muted"> · ${r.label}${r.handler ? ` · ${r.handler}` : ""}</span></li>`;
  return html`<section class="gui-section">
    ${incoming.length > 0 && html`<h3 class="ok-font-heading">${say("Roads in")}</h3>
      <ul class="gui-rows">${incoming.map((r) => row(r, r.from))}</ul>`}
    ${outgoing.length > 0 && html`<h3 class="ok-font-heading">${say("Roads out")}</h3>
      <ul class="gui-rows">${outgoing.map((r) => row(r, r.to))}</ul>`}
  </section>`;
}

function Garrison({ garrison, b }) {
  if (!garrison.length) return null;
  return html`<section class="gui-section">
    <h3 class="ok-font-heading">${say("Garrison")}</h3>
    <ul class="gui-rows">${garrison.map((o) => html`<li key=${o.name}>
      <${OrkHead} o=${o} /> <button class="gui-link ok-font-label" title=${say("The ork itself: its runs, Deploy, Halt")} onClick=${() => selectOrk(o.ref)}>${o.name}</button>
      ${o.scheme && html` <${Scheme} scheme=${o.scheme} />`}
      <span class="ok-font-status ok-tone-muted"> · ${o.lead ? "steward" : o.tier ? html`<${TierMark} tier=${o.tier} />` : o.kind} · ${o.status}</span>
      ${(o.kind === "agent" || o.kind === "hybrid") && html` <button class="ok-act" onClick=${() => deploy(o.ref)}>
        <span class="ok-act__label">${o.session ? "Its session" : "Deploy"}</span></button>`}
      ${o.role && html`<div class="ok-font-status ok-tone-muted">${o.role}</div>`}
    </li>`)}</ul>
  </section>`;
}

// -- the building's own quick actions (the TUI's keys of its type) --------------------------------------

function Quick({ b, i }) {
  const mod = b.page ? typeModule(b.type) : null;
  const own = mod && mod.infoActs ? mod.infoActs(b) : [];  // what only its Info offers (a setup: Import calendar)
  if (!i || (!i.quick.length && !own.length)) return null; // a type may do its quick actions itself (js/types.js)
  return html`<div class="gui-info__acts">${i.quick.map((a) => html`<${Act} key=${a.id} label=${a.label} onClick=${() => runQuick(b, a.id)} />`)}
    ${own.map((a) => html`<${Act} key=${a.id} label=${say(a.label)} title=${say(a.title || a.label)} onClick=${a.run} />`)}</div>`;
}

function OrkCommands({ b, o, open }) {
  const agent = o.kind === "agent" || o.kind === "hybrid";
  return html`<div class="gui-info__acts">
    ${o.kind === "agent" && !o.lead && html`<${Act} label=${say("Hand to the steward")}
      title=${say("Its orders become a road rule of the steward: its own tools go, its roads stay")} onClick=${() => open("hand")} />`}
    ${o.status === "alert" && b.alert && html`<${Act} label=${say("Resolve alert")} onClick=${() => openOrders(b.alert.id)} />`}
    ${agent && html`<${Act} label=${o.session ? "Open session" : "Deploy"} onClick=${() => deploy(o.ref)} />`}
    <${Act} label=${say("Standing orders & trigger")} title=${say("What it is told to do, and when it starts")} onClick=${() => open("orders")} />
    <${Act} label=${say("Halt")} onClick=${() => command("ork.halt", { id: b.id, ork: o.ref }).catch(() => {})} />
    ${o.lead && html`<${Act} label=${say("Watch now")} title=${say("Its steward looks at the building: free metrics, a model only on findings")}
      onClick=${() => command("ork.watch", { id: b.id, ork: o.ref }).catch(() => {})} />
      <${Act} label=${say("Report")} title=${say("The steward's last findings and proposals")}
      onClick=${() => command("ork.report", { id: b.id }).catch(() => {})} />`}
  </div>`;
}

/** The prompt (standing orders and trigger) or the models of any ork of the building, picked from the
 * steward's part: its own info is asked first. */
function OrkDialog({ b, ref, which, onClose }) {
  const [i, setI] = useState(null);
  useEffect(() => { command("info", { id: b.id, ork: ref }).then(setI, onClose); }, [b.id, ref]);
  if (!i) return null;
  const done = () => ask(b.id, null, true);
  return which === "model" ? html`<${ModelDialog} b=${b} i=${i} onClose=${onClose} onDone=${done} />`
    : html`<${OrdersDialog} b=${b} i=${i} onClose=${onClose} onDone=${done} />`;
}

/** *Hand to the steward*: what changes (tools, tier, the spend per run), then the change; Revert takes it back. */
function HandDialog({ b, o, onClose }) {
  const [v, setV] = useState(null);
  useEffect(() => { command("ork.hand", { id: b.id, ork: o.ref, preview: true }).then(setV, onClose); }, [o.ref]);
  if (!v) return null;
  const hand = () => command("ork.hand", { id: b.id, ork: o.ref }).then((ref) => { onClose(); selectOrk(ref); }, () => {});
  return html`<${Dialog} title=${say(`Hand to the steward — ${v.name}`)}
      text=${say("Its orders become a road rule: the steward carries them out on its own tool and tier. Its roads stay; Revert takes it back.")}
      onCancel=${onClose}
      actions=${html`<button class="ok-btn" onClick=${onClose}>${say("Cancel")}</button>
        <button class="ok-btn primary" onClick=${hand}>${say("Hand it over")}</button>`}>
    <ul class="gui-rows gui-hand">
      <li><span class="ok-font-label">${say("Tools")}</span> ${say(v.tools_now)} → <b>${say(v.tools_then)}</b></li>
      <li><span class="ok-font-label">${say("Tier")}</span> ${say(v.tier_now)} → <b>${say(v.tier_then)}</b></li>
      <li><span class="ok-font-label">${say("Spend per run")}</span> ${v.per_run_now
        ? html`${v.per_run_now} → <b>${v.per_run_then || say("not known")}</b> <span class="ok-tone-muted">(${say("an estimate from")} ${v.runs} ${say("runs")})</span>`
        : say("no runs yet to tell")}</li>
      <li><span class="ok-font-label">${say("Roads")}</span> ${v.roads.map(say).join(", ") || say("none")}</li>
      <li class="ok-font-status">${say("Rule")}: ${v.orders}</li>
    </ul>
  </${Dialog}>`;
}

/** A road rule's words, edited: what the steward does with the carts of its roads, and its own tier when it
 *  needs a heavier (or lighter) model than the steward's listen (docs/design/steward-listens.md §7). */
function RuleDialog({ b, i, onClose, onDone }) {
  const [words, setWords] = useState(i.orders || "");
  const [tier, setTier] = useState(i.own_tier || "");
  const tiers = (i.tiers || []).map(([v, label]) => [v, v ? label : say("Follow the steward")]);
  const save = () => command("ork.orders", { id: b.id, ork: i.ref, orders: words, tier })
    .then(() => { onClose(); onDone(); }, () => {});
  return html`<${Dialog} title=${say(`Road rule — ${i.name}`)} text=${say("What the steward does with every cart of its roads, in your words.")}
      onCancel=${onClose}
      actions=${html`<button class="ok-btn" onClick=${onClose}>${say("Cancel")}</button>
        <button class="ok-btn primary" onClick=${save} disabled=${!words.trim()}>${say("Save")}</button>`}>
    <div class="gui-form">
      <textarea class="ok-input gui-textarea" rows="4" value=${words} onInput=${(e) => setWords(e.target.value)}></textarea>
      ${tiers.length > 0 && html`<${Field} label=${say("Model tier")}><${Select} value=${tier} options=${tiers} onChange=${setTier} /></${Field}>`}
    </div>
  </${Dialog}>`;
}

/** A road rule of the steward's, picked under it: its words, its roads, its runs and spend; ← back. */
export function RuleView({ b, ruleRef }) {
  const i = useInfo(b.id, ruleRef);
  const [dialog, setDialog] = useState(null);
  const redo = () => ask(b.id, ruleRef, true);
  useEffect(redo, [ruleRef]);                     // what it said as an agent (just handed over) is not a rule's
  const remove = () => command("ork.dismiss", { id: b.id, ork: ruleRef }).then(() => selectOrk(null), () => {});
  return html`<div class="ok-win__body gui-win__body gui-info-tab">
    <button class="gui-link gui-info__back" onClick=${() => selectOrk(null)}>← ${say(b.title)}</button>
    ${!i || !i.rule ? html`<p class="ok-font-status ok-tone-muted">${say("Looking…")}</p>` : html`
      <section class="gui-info gui-rule">
        <${Row} text=${html`📜 <b>${say(i.name)}</b><span class="ok-tone-muted"> · ${say("Road rule")} · ${say(b.title)}</span>`}>
          <${Act} label=${say("Edit")} title=${say("Its words: what the steward does with its carts")} onClick=${() => setDialog("words")} />
          <${Act} label=${say("Remove")} title=${say("The rule goes; its roads stay, plain")} onClick=${remove} />
        </${Row}>
        <p class="ok-font-body gui-info__about gui-rule__words">${i.orders}</p>
        <ul class="gui-rows ok-font-status">
          <li>${say("Roads")}: ${i.roads.map(say).join(", ") || say("none yet")}</li>
          <li class="ok-tone-muted">${say("Carried out by the steward on its own tool")}${i.tier ? ` · ${say(i.tier)}` : ""}${i.own_tier ? ` · ${say("the rule's own tier")}` : ""}</li>
          <li>${say(i.spend)}${i.last ? ` · ${say("last")}: ${i.last}` : ""}${i.last_error ? ` — ${i.last_error}` : ""}</li></ul>
      </section>
      <section class="gui-section"><h3 class="ok-font-heading">${say("Runs")}</h3>
        ${i.recent.length ? html`<ul class="gui-rows">${i.recent.map((r, k) => html`<li key=${k} class="ok-font-status">
            <span class="ok-tone-muted">${r.ts}${typeof r.cost === "number" ? ` · $${r.cost.toFixed(3)}` : ""}</span> ${r.output}</li>`)}</ul>`
          : html`<p class="ok-font-status ok-tone-muted">${say("No runs yet: it runs when a cart comes")}</p>`}
      </section>
      ${dialog === "words" && html`<${RuleDialog} b=${b} i=${i} onClose=${() => setDialog(null)} onDone=${redo} />`}`}
  </div>`;
}

/** The dialogs a part of Info opens, by `dialog.kind`. */
function Dialogs({ b, o, i, dialog, close, redo }) {
  if (!dialog) return null;
  const k = dialog.kind;
  return html`
    ${k === "dislike" && html`<${DislikeDialog} b=${b} onClose=${close} onDone=${redo} />`}
    ${k === "ork-bad" && o && html`<${NoteDialog} title=${say(`Bad work — ${o.name}`)} onClose=${close}
      onSend=${(note) => command("ork.dislike", { id: b.id, ork: o.ref, note }).then(() => { close(); redo(); }, () => {})} />`}
    ${k === "history" && html`<${HistoryDialog} b=${b} ork=${o} tool=${dialog.tool} onClose=${close} />`}
    ${k === "hand" && o && html`<${HandDialog} b=${b} o=${o} onClose=${close} />`}
    ${k === "listen" && html`<${ListenDialog} b=${b} onClose=${close} />`}
    ${k === "redesign" && html`<${RedesignDialog} b=${b} onClose=${close} />`}
    ${k === "steward-models" && i && i.steward && html`<${StewardModels} b=${b} i=${i} onClose=${close} onDone=${redo} />`}
    ${(k === "ork-orders" || k === "ork-model") && html`<${OrkDialog} key=${dialog.tool}
      b=${b} ref=${dialog.tool} which=${k === "ork-model" ? "model" : "orders"} onClose=${close} />`}
    ${k === "orders" && i && o && html`<${OrdersDialog} b=${b} i=${i} onClose=${close} onDone=${redo} />`}
    ${k === "model" && i && o && html`<${ModelDialog} b=${b} i=${i} onClose=${close} onDone=${redo} />`}`;
}

function useDialog(key) {
  const [dialog, setDialog] = useState(null);         // {kind, tool, road}
  useEffect(() => setDialog(null), [key]);
  const open = (kind, x = "") => setDialog(typeof x === "string" ? { kind, tool: x } : { kind, road: x });
  return [dialog, open, () => setDialog(null)];
}

/** Info: the building, its quick actions, its garrison, its steward, its roads out, Demolish — or a page
 *  of its type's own over it while one is open (js/infopage.js: a setup in steps). */
export function InfoTab({ b }) {
  const page = infoPage(b.id);
  const mod = page && b.page ? typeModule(b.type) : null;
  if (mod && mod.infoPage) {
    return html`<div class="ok-win__body gui-win__body gui-info-tab">${mod.infoPage(b, page)}</div>`;
  }
  return html`<${UsualInfo} b=${b} />`;
}

function UsualInfo({ b }) {
  const i = useInfo(b.id, null);
  const [dialog, open, close] = useDialog(b.id);
  const redo = () => ask(b.id, null, true);
  const t = town.value;
  return html`<div class="ok-win__body gui-win__body gui-info-tab">
    ${!i ? html`<p class="ok-font-status ok-tone-muted">${say("Looking…")}</p>` : html`
      <${BuildingInfo} b=${b} i=${i} redo=${redo} open=${open} />
      <${BuildingSettings} b=${b} i=${i} redo=${redo} />
      <${Quick} b=${b} i=${i} />
      <${Garrison} garrison=${b.garrison} b=${b} />
      <section class="gui-section gui-steward-part">
        <h3 class="ok-font-heading"><${StewardTitle} i=${i} open=${open} /></h3>
        <${StewardWindow} b=${b} i=${i} redo=${redo} open=${open} />
      </section>
      <${Roads} b=${b} t=${t} />
`}
    <${Dialogs} b=${b} o=${null} i=${i} dialog=${dialog} close=${close} redo=${redo} />
  </div>`;
}

/** An ork of the building, picked in its garrison or the steward's part: ← back to the building. */
export function OrkView({ b, orkRef }) {
  const o = b.garrison.find((x) => x.ref === orkRef);
  const i = useInfo(b.id, o.ref);
  const [dialog, open, close] = useDialog(o.ref);
  const redo = () => ask(b.id, o.ref, true);
  return html`<div class="ok-win__body gui-win__body gui-info-tab">
    <button class="gui-link gui-info__back" onClick=${() => selectOrk(null)}>← ${say(b.title)}</button>
    ${!i ? html`<p class="ok-font-status ok-tone-muted">${say("Looking…")}</p>` : html`
      <${OrkInfo} b=${b} o=${o} i=${i} redo=${redo} open=${open} />
      <${OrkCommands} b=${b} o=${o} open=${open} />
      <section class="gui-section"><h3 class="ok-font-heading">${say("Inventory")}</h3>
        <${Inventory} i=${i} open=${open} /></section>`}
    <${Dialogs} b=${b} o=${o} i=${i} dialog=${dialog} close=${close} redo=${redo} />
  </div>`;
}
