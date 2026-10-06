// The steward's window: the middle column of a selected building's console (js/console.js), once the
// garrison's list. Its head is the steward — name, status, model (a click: which model for which of its
// tasks, realm/steward.py USES) — and its body
// what the steward keeps and does:
//
//   settings   the goal its retros aim at (three steps), how freely it applies their changes (the Town
//              Hall's: the Town retro's), docs/design/retros-and-goals.md §3
//   commands   Watch now, Report, Redesign window, Revert while there is a checkpoint
//   listens    the roads into the building, each with its handler (an agent, a script, a chain) and what
//              it does now; a click edits the handler's prompt, opens its script in Lake, or picks a
//              plain road; › opens the ork itself; + Listen lays a new road
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
 * type's own; "" is the default (the CLI's own model, or the type's setting). */
export function StewardModels({ b, i, onClose, onDone }) {
  const s = i.steward;
  const [picked, setPicked] = useState(Object.fromEntries(s.uses.map((u) => [u.id, u.tier])));
  const choices = (i.tiers || []).map(([v, label]) => [v, v ? label : say(`Default${s.default ? ` (${s.default})` : ""}`)]);
  const save = () => command("steward.models", { id: b.id, models: picked }).then(() => { onClose(); onDone(); }, () => {});
  return html`<${Dialog} title=${say(`${s.name}'s models — ${b.title}`)} text=${say("Which model the steward runs each of its tasks on.")}
      onCancel=${onClose}
      actions=${html`<button class="ok-btn" onClick=${onClose}>${say("Cancel")}</button>
        <button class="ok-btn primary" onClick=${save}>${say("Save")}</button>`}>
    <div class="gui-form">${s.uses.map((u) => html`<label key=${u.id} class="gui-field"><span class="ok-font-label">${say(u.label)}</span>
      <select class="ok-input" value=${picked[u.id]} onChange=${(e) => setPicked({ ...picked, [u.id]: e.target.value })}>
        ${choices.map(([v, label]) => html`<option key=${v} value=${v} selected=${v === picked[u.id]}>${label}</option>`)}
      </select></label>`)}</div>
  </${Dialog}>`;
}

function Steps({ label, title, children }) {
  return html`<div class="gui-steward__row" title=${title}>
    <span class="gui-steward__label">${label}</span>
    <span class="gui-steps" role="group" aria-label=${label}>${children}</span></div>`;
}

function Goal({ b, i, redo }) {
  const set = (value) => command("building.goal", { id: b.id, value }).then(redo, () => {});
  return html`<${Steps} label=${say("Goal")} title=${say("What the retros improve it towards")}>
    ${GOALS.map(([v, name, hint]) => html`<button key=${v} class=${cls("gui-steps__one", { "is-on": i.goal === v })}
        aria-pressed=${i.goal === v} title=${say(hint)} onClick=${() => i.goal !== v && set(v)}>${say(name)}</button>`)}
  </${Steps}>`;
}

/** How freely the steward applies its retro's changes; the lit step again goes back to the town's. */
function Freedom({ b, i, redo }) {
  const set = (value) => command("building.autonomy", { id: b.id, value }).then(redo, () => {});
  const retro = b.id === HALL ? "the Town retro (weekly)" : "its Building retro (daily)";
  return html`<${Steps} label=${say("Freedom")} title=${say(`How freely its steward decides and ${retro} applies its changes`)}>
    ${FREEDOMS.map(([v, icon, name, hint]) => html`<button key=${v} class=${cls("gui-steps__one is-icon", { "is-on": i.autonomy === v })}
        aria-pressed=${i.autonomy === v} title=${`${say(name)}: ${say(hint)}`} aria-label=${say(name)}
        onClick=${() => set(i.autonomy === v ? "" : v)}>
      <svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true">${icon}</svg></button>`)}
  </${Steps}>
  ${!i.autonomy && html`<div class="ok-tone-muted gui-steward__note" title=${say(`The town's autonomy (${i.town_autonomy}), until one is picked`)}>
    ${say("as the town")}</div>`}`;
}

/** 🕰 How long its questions and its changes wait for you, on the clock; the lit one again goes back to the town's. */
function Waits({ b, i, redo }) {
  const w = i.waits;
  if (!w || !w.clock) return null;
  const set = (key, value) => command("building.waits", { id: b.id, question: w.question, rebuild: w.rebuild, [key]: value })
    .then(redo, () => {});
  const row = (key, label, title, choices, own, town, unit) => html`<${Steps} label=${say(label)} title=${say(title)}>
    ${choices.map((v) => html`<button key=${v} class=${cls("gui-steps__one", { "is-on": (own || town) === v, "is-town": !own && town === v })}
        aria-pressed=${own === v} title=${say(own ? "" : "as the town")} onClick=${() => set(key, own === v ? 0 : v)}>${v} ${say(unit)}</button>`)}
  </${Steps}>`;
  return html`${row("question", "Questions wait", "How long a question waits for you before the steward decides", w.questions,
                    w.question, w.town_question, "min")}
    ${row("rebuild", "Changes wait", "How many hours you are around (the camp open, not quiet hours) a change waits before it is applied in quiet hours",
          w.rebuilds, w.rebuild, w.town_rebuild, "h")}`;
}

function Command({ label, title, onClick }) {
  return html`<li class="gui-console__row" title=${title || label} onClick=${onClick}>${label}</li>`;
}

function Commands({ b, i, redo, open }) {
  const s = i.steward;
  const revert = () => command("building.revert", { id: b.id }).then(redo, () => {});
  return html`<ul class="gui-rows gui-steward__commands">
    ${s && html`<${Command} label=${say("Watch now")} title=${say("Its steward looks at the building: free metrics, a model only on findings")}
        onClick=${() => command("ork.watch", { id: b.id, ork: s.ref }).catch(() => {})} />
      <${Command} label=${say("Report")} title=${say("The steward's last findings and proposals")}
        onClick=${() => command("ork.report", { id: b.id }).catch(() => {})} />`}
    <${Command} label=${say("Redesign window")} title=${say("Its steward redraws its window")} onClick=${() => open("redesign")} />
    ${b.id !== HALL && i.can_revert && html`<${Command} label=${say("Revert")} title=${say("Back to its previous checkpoint")}
      onClick=${revert} />`}
  </ul>`;
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

function Handler({ h }) {
  return html`<span class="gui-steward__who"><b>${say(h.name)}</b>
    <span class="ok-tone-muted"> · ${say(h.kind_label)}${h.tier ? ` · ${h.tier}` : ""}</span>
    <span class=${cls("gui-steward__status", { "ok-tone-wait": h.status === "busy", "ok-tone-fire": h.status === "alert" })}> · ${h.status}</span></span>`;
}

function More({ h }) {
  return html`<button class="gui-steward__more" title=${say("The ork itself: Deploy, Halt, its runs")} aria-label=${say("The ork itself")}
    onClick=${(e) => { e.stopPropagation(); selectOrk(h.ref); }}>›</button>`;
}

function Listens({ b, i, open }) {
  return html`<details class="gui-steward__group" open>
    <summary class="ok-font-label">${say("Listens")} <span class="ok-tone-muted">${i.listens.length}</span></summary>
    <ul class="gui-rows">
      ${i.listens.map((l) => l.by
        ? html`<li key=${l.key} class="gui-console__row gui-steward__road" title=${editTitle(l.by)} onClick=${() => edit(b, l.by, open)}>
            <span class="gui-steward__from">◂ ${say(l.title)} <span class="ok-tone-muted">${l.label}</span></span>
            <span class="gui-steward__to">→ <${Handler} h=${l.by} /><${More} h=${l.by} /></span></li>`
        : html`<li key=${l.key} class="gui-console__row gui-steward__road" title=${say("A plain road: pick it to give it a handler or remove it")}
            onClick=${() => { pickedRoad.value = l.key; }}>
            <span class="gui-steward__from">◂ ${say(l.title)} <span class="ok-tone-muted">${l.label}</span></span>
            <span class="gui-steward__to ok-tone-muted">→ ${say("plain")}</span></li>`)}
      ${!i.listens.length && html`<li class="ok-font-status ok-tone-muted">${say("Listens to nobody yet")}</li>`}
      <li class="gui-console__row" title=${say("A road from another building into this one")} onClick=${() => open("listen")}>
        + ${say("Listen")}</li>
    </ul>
  </details>`;
}

function OnItsOwn({ b, i, open }) {
  if (!i.others.length) return null;
  return html`<details class="gui-steward__group" open>
    <summary class="ok-font-label">${say("By schedule or by hand")} <span class="ok-tone-muted">${i.others.length}</span></summary>
    <ul class="gui-rows">${i.others.map((h) => html`<li key=${h.ref} class="gui-console__row" title=${editTitle(h)}
        onClick=${() => edit(b, h, open)}><${Handler} h=${h} />
      <span class="ok-tone-muted"> · ${h.trigger.replace("_", " ")}</span><${More} h=${h} /></li>`)}</ul>
  </details>`;
}

/** The body of the steward's window. */
export function StewardWindow({ b, i, redo, open }) {
  if (!i) return html`<p class="ok-font-status ok-tone-muted">${say("Looking…")}</p>`;
  return html`<div class="gui-steward">
    <section class="gui-steward__settings"><${Goal} b=${b} i=${i} redo=${redo} /><${Freedom} b=${b} i=${i} redo=${redo} /><${Waits} b=${b} i=${i} redo=${redo} /></section>
    <${Commands} b=${b} i=${i} redo=${redo} open=${open} />
    <${Listens} b=${b} i=${i} open=${open} />
    <${OnItsOwn} b=${b} i=${i} open=${open} />
  </div>`;
}
