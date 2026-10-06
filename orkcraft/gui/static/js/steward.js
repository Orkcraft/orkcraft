// The steward's window: the middle column of a selected building's console (js/console.js), once the
// garrison's list. Its head is the steward — name, status, model (a click: its models) — and its body
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
import { html, cls } from "./html.js";
import { command, say } from "./link.js";
import { selectOrk } from "./windows.js";
import { HALL } from "./tent.js";
import { pickedRoad } from "./build.js";
import { openInLake } from "./lake.js";

// Chains, a clock, broken chains: drawn, as the pin is (js/hut.js), since ⛓️‍💥 is missing from many fonts.
const CHAIN = html`<rect x="1" y="5" width="8" height="6" rx="3" /><rect x="7" y="5" width="8" height="6" rx="3" />`;
const CLOCK = html`<circle cx="8" cy="8" r="6" /><path d="M8 4.5V8l2.5 1.5" />`;
const BROKEN = html`<rect x="0.5" y="5" width="6.5" height="6" rx="3" /><rect x="9" y="5" width="6.5" height="6" rx="3" />
  <path d="M8 1.5v2M8 12.5v2M5.5 2.5l1 1.5M10.5 2.5l-1 1.5" />`;
const FREEDOMS = [["chains", CHAIN, "In chains", "Its steward only proposes; nothing changes without you"],
                  ["clock", CLOCK, "On the clock", "Its steward proposes; what you leave unanswered for a day it applies in quiet hours"],
                  ["free", BROKEN, "Unchained", "Its steward applies its changes in the next quiet hours"]];
const GOALS = [["thrift", "Thrift", "Fewer tokens, keeping what was liked"],
               ["balance", "Balance", "Cheaper where it is liked, better where it is not"],
               ["quality", "Quality", "Better results; it may spend more"]];

/** The window's title: the steward, its status, its model (a click: which model for what). */
export function StewardTitle({ i, open }) {
  const s = i && i.steward;
  if (!s) return say("Steward");
  return html`<span class="gui-steward__head">
    <button class="gui-link" title=${say("The steward itself: its runs, Deploy, Halt")} onClick=${() => selectOrk(s.ref)}>★ <b>${s.name}</b></button>
    <span class="ok-tone-muted"> · ${s.status}</span>
    ${s.model && html` <button class="gui-steward__model" title=${say("Which model it uses, step by step")}
        onClick=${() => open("ork-model", s.ref)}>${s.model}${s.models > 1 ? ` +${s.models - 1}` : ""} ▾</button>`}
  </span>`;
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
  return html`<${Steps} label=${say("Freedom")} title=${say(`How freely ${retro} applies its changes`)}>
    ${FREEDOMS.map(([v, icon, name, hint]) => html`<button key=${v} class=${cls("gui-steps__one is-icon", { "is-on": i.autonomy === v })}
        aria-pressed=${i.autonomy === v} title=${`${say(name)}: ${say(hint)}`} aria-label=${say(name)}
        onClick=${() => set(i.autonomy === v ? "" : v)}>
      <svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true">${icon}</svg></button>`)}
  </${Steps}>
  ${!i.autonomy && html`<div class="ok-tone-muted gui-steward__note" title=${say(`The town's autonomy (${i.town_autonomy}), until one is picked`)}>
    ${say("as the town")}</div>`}`;
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
  return html`<span class="gui-steward__who"><b>${h.name}</b>
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
      ${i.listens.map((l) => l.orc
        ? html`<li key=${l.key} class="gui-console__row gui-steward__road" title=${editTitle(l.orc)} onClick=${() => edit(b, l.orc, open)}>
            <span class="gui-steward__from">◂ ${say(l.title)} <span class="ok-tone-muted">${l.label}</span></span>
            <span class="gui-steward__to">→ <${Handler} h=${l.orc} /><${More} h=${l.orc} /></span></li>`
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
    <section class="gui-steward__settings"><${Goal} b=${b} i=${i} redo=${redo} /><${Freedom} b=${b} i=${i} redo=${redo} /></section>
    <${Commands} b=${b} i=${i} redo=${redo} open=${open} />
    <${Listens} b=${b} i=${i} open=${open} />
    <${OnItsOwn} b=${b} i=${i} open=${open} />
  </div>`;
}
