// The steward's window: the middle column of a selected building's console (js/console.js), once the
// garrison's list. Its head is the steward — name, status, model (a click: which model for which of its
// tasks, realm/steward.py USES) — and its body
// what the steward keeps and does:
//
//   tier       how heavy a mind the steward is: Novice, Seasoned, Veteran (realm/steward_models.py level_of), and
//              the AI tool it runs on — its own, not its building's goal (docs/design/warchief-line-and-cards.md §7)
//   commands   one row: Watch, Report, Redesign, Revert while there is a checkpoint
//   script     a script-first building's line: no model, its ork wakes on an error or a 👎 (or what thinks)
//   listens    the roads into the building, one line each with its handler (an agent, a script, a chain)
//              and what it does now; a click edits the handler's prompt, opens its script in Lake, or
//              picks a plain road; › opens the ork itself; + Listen lays a new road
//
// As tall as Info: every line is one line, its whole text in its tooltip.
//   on its own the handlers no road feeds: on a schedule or when asked
//   rules      its road rules (docs/design/steward-listens.md): what the steward itself does with a road's carts,
//              one line each with its roads, its last run and its spend; a click opens the rule
//
// The building's own settings — its goal and its Freedom — are `BuildingSettings`, drawn in the building's part
// of Info: what the building is for, apart from who works it.
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
import { TierMark } from "./icons.js";

// Chains, a clock, broken chains: drawn, as the pin is (js/hut.js), since ⛓️‍💥 is missing from many fonts.
const CHAIN = html`<rect x="1" y="5" width="8" height="6" rx="3" /><rect x="7" y="5" width="8" height="6" rx="3" />`;
const CLOCK = html`<circle cx="8" cy="8" r="6" /><path d="M8 4.5V8l2.5 1.5" />`;
const BROKEN = html`<rect x="0.5" y="5" width="6.5" height="6" rx="3" /><rect x="9" y="5" width="6.5" height="6" rx="3" />
  <path d="M8 1.5v2M8 12.5v2M5.5 2.5l1 1.5M10.5 2.5l-1 1.5" />`;
const FREEDOMS = [["chains", CHAIN, "In chains", "Its questions and its changes wait for you"],
                  ["clock", CLOCK, "On the clock", "A question waits for you some minutes, a change the hours you are around — then the steward decides"],
                  ["free", BROKEN, "Unchained", "Its steward decides at once and applies its changes in the next quiet hours"]];
const RANKS = [["laborer", "Novice", "A light model: quick and cheap, for plain work"],
               ["warrior", "Seasoned", "A middle model: most work"],
               ["elder", "Veteran", "A heavy model: the hardest work; it costs the most"]];
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
 * type's own; "" is the default — for its work (realm/steward.py WORK) the one its own tier names for the task,
 * else the CLI's own model (or the type's setting). */
export function StewardModels({ b, i, onClose, onDone }) {
  const s = i.steward;
  const [picked, setPicked] = useState(Object.fromEntries(s.uses.map((u) => [u.id, u.tier])));
  const fallback = (u) => u.work ? say(`Default — ${s.rank_title}: ${u.by_level || "the default model"}`)
                                  : say(`Default${s.default ? ` (${s.default})` : ""}`);
  const choices = (u) => (i.tiers || []).map(([v, label]) => [v, v ? label : fallback(u)]);
  const save = () => command("steward.models", { id: b.id, models: picked }).then(() => { onClose(); onDone(); }, () => {});
  return html`<${Dialog} title=${say(`${s.name}'s models — ${b.title}`)} text=${say("Which model the steward runs each of its tasks on.")}
      onCancel=${onClose}
      actions=${html`<button class="ok-btn" onClick=${onClose}>${say("Cancel")}</button>
        <button class="ok-btn primary" onClick=${save}>${say("Save")}</button>`}>
    <div class="gui-form">${s.uses.map((u) => html`<label key=${u.id} class="gui-field"><span class="ok-font-label">${say(u.label)}${
        u.spend ? html`<span class="ok-tone-muted"> · ${u.spend}</span>` : ""}</span>
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
  const hints = i.goal_hints || {};                // core/buildings.py goal_words: the retros, and an Agent pool's orks
  const what = "Goal: what the retros improve it towards (its steward's tier is its own)";
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

/** The steward's own tier, three chevron steps, and the AI tool it runs on (its ork's model dialog). */
function Rank({ b, i, redo, open }) {
  const s = i.steward;
  const set = (value) => command("building.steward_level", { id: b.id, value }).then(redo, () => {});
  const lead = (b.garrison || []).find((o) => o.lead);
  return html`<${Steps} label=${say("Tier")} title=${say("Tier: how heavy a model its steward thinks with. The goal never moves it; a tight quota makes it light for a while")}>
    ${RANKS.map(([v, name, hint]) => html`<button key=${v} class=${cls("gui-steps__one is-rank", { "is-on": s.rank === v })}
        aria-pressed=${s.rank === v} title=${`${say(name)} — ${say(hint)}`} onClick=${() => s.rank !== v && set(v)}>
<${TierMark} tier=${v} /></button>`)}
  </${Steps}>
  ${lead && lead.scheme && html`<${Steps} label=${say("AI tool")} title=${say("The AI tool its steward runs on (from its next run)")}>
    <button class="gui-steps__one gui-steward__tool" title=${say("Change its AI tool and model")}
      onClick=${() => open("ork-model", lead.ref)}>${lead.scheme} ▾</button>
  </${Steps}>`}`;
}

/** The building's own settings, in its part of Info: the goal its retros aim at (three steps), how freely its
 * retro's changes apply (Freedom: as the town, or its own three; the Town Hall's: the Town retro's),
 * retros-and-goals.md §3. */
export function BuildingSettings({ b, i, redo }) {
  return html`<div class="gui-steward__settings gui-building-part"><${Goal} b=${b} i=${i} redo=${redo} /><${Freedom} b=${b} i=${i} redo=${redo} /></div>`;
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
  return selectOrk(h.ref);                         // a chain's ork, or a road rule's panel
}

function editTitle(h) {
  if (h.kind === "script" && h.script) return say("Its script, in Lake");
  if (h.kind === "agent" || h.kind === "hybrid") return say("Its prompt: standing orders and trigger");
  if (h.kind === "steward") return say("The rule: its words, its roads, its runs");
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

/** Whether its work is code (docs/design/script-first.md): no model, its ork wakes on an error or a 👎; or what
 * in it thinks on its carts. Nothing for a type that thinks by its nature. */
function ScriptFirst({ i }) {
  const c = i.script_first;
  if (!c) return null;
  if (!c.on) {
    const parts = c.thinking.join(", ");
    return html`<p class="gui-steward__script-first ok-font-status ok-tone-muted"
        title=${say("It calls a model on its carts. Without these parts it would be script-first: no model, its ork woken only on an error or a 👎")}>
      ${say("Thinks on its carts")}: ${parts}</p>`;
  }
  return html`<p class="gui-steward__script-first is-on ok-font-status ok-tone-ok"
      title=${say("Its work is code. Its ork calls no model on carts or schedules: it wakes once when the building fails or gets a 👎, and its keeper proposes a fix")}>
    ${say("Script-first")} · ${say("no model")} · ${say("its ork wakes on an error or a 👎")}${c.woke && html`<span class="ok-tone-muted"> · ${say(c.woke)}</span>`}</p>`;
}

/** Its road rules: what the steward does with a road's carts itself, on its own tool and listen tier. */
function Rules({ i }) {
  if (!i.rules || !i.rules.length) return null;
  return html`<details class="gui-steward__group" open>
    <summary class="ok-font-label">${say("Road rules")} <span class="ok-tone-muted">${i.rules.length}</span></summary>
    <ul class="gui-rows">${i.rules.map((r) => {
      const line = `📜 ${say(r.name)} · ${r.roads.map(say).join(", ") || say("no road yet")} → ${say("here")}`;
      const more = [r.last, say(r.spend)].filter(Boolean).join(" · ");
      return html`<li key=${r.ref} class="gui-console__row gui-steward__rule" title=${`${line} · ${more}. ${say("The rule: its words, its roads, its runs")}`}
          onClick=${() => selectOrk(r.ref)}>
        <span class="gui-steward__line">${line} <span class="ok-tone-muted">· ${more}</span></span></li>`;
    })}</ul>
  </details>`;
}

/** The body of the steward's window. */
export function StewardWindow({ b, i, redo, open }) {
  if (!i) return html`<p class="ok-font-status ok-tone-muted">${say("Looking…")}</p>`;
  return html`<div class="gui-steward">
    ${i.steward && i.steward.own && html`<div class="gui-steward__settings"><${Rank} b=${b} i=${i} redo=${redo} open=${open} /></div>`}
    <${Commands} b=${b} i=${i} redo=${redo} open=${open} />
    <${ScriptFirst} i=${i} />
    <${Listens} b=${b} i=${i} open=${open} />
    <${Rules} i=${i} />
    <${OnItsOwn} b=${b} i=${i} open=${open} />
  </div>`;
}
