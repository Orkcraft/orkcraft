// The steward's window: the middle column of a selected building's console (js/console.js), once the
// garrison's list. Its head is the steward — name, status, model (a click: which model for which of its
// tasks, realm/steward.py USES) — and its body
// what the steward keeps and does:
//
//   settings   two rows, each named: the goal its retros aim at (three steps), how freely it applies their changes
//              (Freedom: as the town, or its own three; the Town Hall's: the Town retro's), retros-and-goals.md §3
//   commands   one row: Watch, Report, Redesign, Revert while there is a checkpoint
//   listens    the roads into the building, one line each with its handler (an agent, a script, a chain)
//              and what it does now; a click edits the handler's prompt, opens its script in Lake, or
//              picks a plain road; › opens the ork itself; + Listen lays a new road
//
// As tall as Info: every line is one line, its whole text in its tooltip.
//   on its own the handlers no road feeds: on a schedule or when asked
//
// The data is the building's `info` (gui/info.py: steward, listens, others, goal, autonomy).
import { useState } from "preact/hooks";
import { html, cls } from "./html.js";
import { command, say } from "./link.js";
import { Dialog } from "./dialog.js";
import { selectOrk } from "./windows.js";
import { HALL } from "./tent.js";
import { pickedRoad } from "./build.js";
import { openInLake } from "./lake.js";

// Chains, a clock, broken chains: drawn, as the pin is (js/hut.js), since ⛓️‍💥 is missing from many fonts.
const CHAIN = html`<rect x="1" y="5" width="8" height="6" rx="3" /><rect x="7" y="5" width="8" height="6" rx="3" />`;
const CLOCK = html`<circle cx="8" cy="8" r="6" /><path d="M8 4.5V8l2.5 1.5" />`;
const BROKEN = html`<rect x="0.5" y="5" width="6.5" height="6" rx="3" /><rect x="9" y="5" width="6.5" height="6" rx="3" />
  <path d="M8 1.5v2M8 12.5v2M5.5 2.5l1 1.5M10.5 2.5l-1 1.5" />`;
const FREEDOMS = [["chains", CHAIN, "In chains", "Its questions and its changes wait for you"],
                  ["clock", CLOCK, "On the clock", "A question waits for you some minutes, a change the hours you are around — then the steward decides"],
                  ["free", BROKEN, "Unchained", "Its steward decides at once and applies its changes in the next quiet hours"]];
const GOALS = [["thrift", "Thrift", "Fewer tokens, keeping what was liked"],
               ["balance", "Balance", "Cheaper where it is liked, better where it is not"],
               ["quality", "Quality", "Better results; it may spend more"]];

/** The window's title: the steward, its status, its model (a click: which model for which task). */
export function StewardTitle({ i, open }) {
  const s = i && i.steward;
  if (!s) return say("Steward");
  return html`<span class="gui-steward__head">
    <button class="gui-link" title=${say("The steward itself: its runs, Deploy, Halt")} onClick=${() => selectOrk(s.ref)}>★ <b>${say(s.name)}</b></button>
    <span class="ok-tone-muted"> · ${s.status}</span>
    ${s.own && html` <button class="gui-steward__model" title=${say("Which model it runs each of its tasks on")}
        onClick=${() => open("steward-models")}>${s.model}${s.more > 0 ? ` +${s.more}` : ""} ▾</button>`}
  </span>`;
}

/** Which tier the steward runs each of its tasks on: every building's (watch, redesign, rules) and its
 * type's own; "" is the default — for its work (realm/steward.py WORK) the tier its goal names, else the
 * CLI's own model (or the type's setting). */
export function StewardModels({ b, i, onClose, onDone }) {
  const s = i.steward;
  const [picked, setPicked] = useState(Object.fromEntries(s.uses.map((u) => [u.id, u.tier])));
  const fallback = (u) => u.work ? say(`Default — ${i.goal_title}: ${u.by_goal || "the default model"}`)
                                  : say(`Default${s.default ? ` (${s.default})` : ""}`);
  const choices = (u) => (i.tiers || []).map(([v, label]) => [v, v ? label : fallback(u)]);
  const save = () => command("steward.models", { id: b.id, models: picked }).then(() => { onClose(); onDone(); }, () => {});
  return html`<${Dialog} title=${say(`${s.name}'s models — ${b.title}`)} text=${say("Which model the steward runs each of its tasks on.")}
      onCancel=${onClose}
      actions=${html`<button class="ok-btn" onClick=${onClose}>${say("Cancel")}</button>
        <button class="ok-btn primary" onClick=${save}>${say("Save")}</button>`}>
    <div class="gui-form">${s.uses.map((u) => html`<label key=${u.id} class="gui-field"><span class="ok-font-label">${say(u.label)}</span>
      <select class="ok-input" value=${picked[u.id]} onChange=${(e) => setPicked({ ...picked, [u.id]: e.target.value })}>
        ${choices(u).map(([v, label]) => html`<option key=${v} value=${v} selected=${v === picked[u.id]}>${label}</option>`)}
      </select></label>`)}</div>
  </${Dialog}>`;
}

/** One setting's row: its name, then its steps. */
function Steps({ label, title, children }) {
  return html`<span class="gui-steward__setting ok-font-label ok-tone-muted" title=${title}>${label}</span>
    <span class="gui-steps" role="group" aria-label=${label} title=${title}>${children}</span>`;
}

function Goal({ b, i, redo }) {
  const set = (value) => command("building.goal", { id: b.id, value }).then(redo, () => {});
  const hints = i.goal_hints || {};                // core/buildings.py goal_words: the retros, and the models
  const what = Object.keys(hints).length ? "Goal: what the retros improve it towards, and the models its work runs on"
                                         : "Goal: what the retros improve it towards";
  const tip = (v, name, hint) => `${say("Goal")}: ${say(name)} — ${say(hints[v] || hint)}`;
  return html`<${Steps} label=${say("Goal")} title=${say(what)}>
    ${GOALS.map(([v, name, hint]) => html`<button key=${v} class=${cls("gui-steps__one", { "is-on": i.goal === v })}
        aria-pressed=${i.goal === v} title=${tip(v, name, hint)} onClick=${() => i.goal !== v && set(v)}>${say(name)}</button>`)}
  </${Steps}>`;
}

/** How freely the steward applies its retro's changes: as the town's (lit when none is picked), or its own. */
function Freedom({ b, i, redo }) {
  const set = (value) => command("building.autonomy", { id: b.id, value }).then(redo, () => {});
  const retro = b.id === HALL ? "the Town retro (weekly)" : "its Building retro (daily)";
  return html`<${Steps} label=${say("Freedom")} title=${say(`Freedom: how freely its steward decides and ${retro} applies its changes`)}>
    <button class=${cls("gui-steps__one is-as-town", { "is-on": !i.autonomy })} aria-pressed=${!i.autonomy}
        title=${say(`As the town: its autonomy (${i.town_autonomy})`)} onClick=${() => i.autonomy && set("")}>${say("town")}</button>
    ${FREEDOMS.map(([v, icon, name, hint]) => html`<button key=${v} class=${cls("gui-steps__one is-icon", { "is-on": i.autonomy === v })}
        aria-pressed=${i.autonomy === v} title=${`${say("Freedom")}: ${say(name)} — ${say(hint)}`} aria-label=${say(name)}
        onClick=${() => set(i.autonomy === v ? "" : v)}>
      <svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true">${icon}</svg></button>`)}
  </${Steps}>`;
}

function Command({ label, title, onClick }) {
  return html`<button class="ok-act" title=${title || label} onClick=${onClick}><span class="ok-act__label">${label}</span></button>`;
}

/** The steward's commands in one row: Watch, Report, Redesign, Revert (while there is a checkpoint). */
function Commands({ b, i, redo, open }) {
  const s = i.steward;
  const revert = () => command("building.revert", { id: b.id }).then(redo, () => {});
  return html`<div class="gui-steward__commands">
    ${s && html`<${Command} label=${say("Watch")} title=${say("Watch now: its steward looks at the building, free metrics, a model only on findings")}
        onClick=${() => command("ork.watch", { id: b.id, ork: s.ref }).catch(() => {})} />
      <${Command} label=${say("Report")} title=${say("The steward's last findings and proposals")}
        onClick=${() => command("ork.report", { id: b.id }).catch(() => {})} />`}
    <${Command} label=${say("Redesign")} title=${say("Redesign window: its steward redraws its window")} onClick=${() => open("redesign")} />
    ${b.id !== HALL && i.can_revert && html`<${Command} label=${say("Revert")} title=${say("Back to its previous checkpoint")}
      onClick=${revert} />`}
  </div>`;
}

/** What a click on a handler does: an agent's prompt, a script in Lake, a chain's ork. */
function edit(b, h, open) {
  if (h.kind === "script" && h.script) return openInLake({ path: h.script, title: `${h.name} — ${b.title}`, from: b.id });
  if (h.kind === "agent" || h.kind === "hybrid") return open("ork-orders", h.ref);
  return selectOrk(h.ref);
}

function editTitle(h) {
  if (h.kind === "script" && h.script) return say("Its script, in Lake");
  if (h.kind === "agent" || h.kind === "hybrid") return say("Its prompt: standing orders and trigger");
  return say("The ork: its chain");
}

function handlerText(h) {
  return `${say(h.name)} · ${say(h.kind_label)}${h.tier ? ` · ${h.tier}` : ""} · ${h.status}`;
}

function Handler({ h }) {
  return html`<b>${say(h.name)}</b><span class="ok-tone-muted"> · ${say(h.kind_label)}${h.tier ? ` · ${h.tier}` : ""}</span><span
    class=${cls({ "ok-tone-wait": h.status === "busy", "ok-tone-fire": h.status === "alert" })}> · ${h.status}</span>`;
}

function More({ h }) {
  return html`<button class="gui-steward__more" title=${say("The ork itself: Deploy, Halt, its runs")} aria-label=${say("The ork itself")}
    onClick=${(e) => { e.stopPropagation(); selectOrk(h.ref); }}>›</button>`;
}

/** One road in, on one line: where from, what it carries, who takes it (its whole text in the tooltip). */
function Road({ b, l, open }) {
  const from = `◂ ${say(l.title)} · ${l.label}`;
  if (!l.by) {
    return html`<li class="gui-console__row gui-steward__road" title=${`${from} → ${say("plain")}: ${say("pick it to give it a handler or remove it")}`}
        onClick=${() => { pickedRoad.value = l.key; }}>
      <span class="gui-steward__line">◂ ${say(l.title)} <span class="ok-tone-muted">${l.label} → ${say("plain")}</span></span></li>`;
  }
  return html`<li class="gui-console__row gui-steward__road" title=${`${from} → ${handlerText(l.by)}. ${editTitle(l.by)}`}
      onClick=${() => edit(b, l.by, open)}>
    <span class="gui-steward__line">◂ ${say(l.title)} <span class="ok-tone-muted">${l.label}</span> → <${Handler} h=${l.by} /></span>
    <${More} h=${l.by} /></li>`;
}

function Listens({ b, i, open }) {
  return html`<details class="gui-steward__group" open>
    <summary class="ok-font-label">${say("Listens")} <span class="ok-tone-muted">${i.listens.length}</span>
      <button class="gui-steward__add" title=${say("A road from another building into this one")}
        onClick=${(e) => { e.preventDefault(); open("listen"); }}>+ ${say("Listen")}</button></summary>
    <ul class="gui-rows">
      ${i.listens.map((l) => html`<${Road} key=${l.key} b=${b} l=${l} open=${open} />`)}
      ${!i.listens.length && html`<li class="ok-font-status ok-tone-muted">${say("Listens to nobody yet")}</li>`}
    </ul>
  </details>`;
}

function OnItsOwn({ b, i, open }) {
  if (!i.others.length) return null;
  return html`<details class="gui-steward__group" open>
    <summary class="ok-font-label">${say("By schedule or by hand")} <span class="ok-tone-muted">${i.others.length}</span></summary>
    <ul class="gui-rows">${i.others.map((h) => html`<li key=${h.ref} class="gui-console__row gui-steward__own"
        title=${`${handlerText(h)} · ${h.trigger.replace("_", " ")}. ${editTitle(h)}`} onClick=${() => edit(b, h, open)}>
      <span class="gui-steward__line"><${Handler} h=${h} /><span class="ok-tone-muted"> · ${h.trigger.replace("_", " ")}</span></span>
      <${More} h=${h} /></li>`)}</ul>
  </details>`;
}

/** The body of the steward's window. */
export function StewardWindow({ b, i, redo, open }) {
  if (!i) return html`<p class="ok-font-status ok-tone-muted">${say("Looking…")}</p>`;
  return html`<div class="gui-steward">
    <div class="gui-steward__settings"><${Goal} b=${b} i=${i} redo=${redo} /><${Freedom} b=${b} i=${i} redo=${redo} /></div>
    <${Commands} b=${b} i=${i} redo=${redo} open=${open} />
    <${Listens} b=${b} i=${i} open=${open} />
    <${OnItsOwn} b=${b} i=${i} open=${open} />
  </div>`;
}
