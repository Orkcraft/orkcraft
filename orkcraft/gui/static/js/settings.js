// The town's settings, opened from the project's name in the HUD (js/chrome.js): how freely the orks
// decide — the level every building follows until it has its own (its steward's window, js/steward.js)
// — and, on the clock, how long a question and a change wait for you. The host's town.settings
// (gui/town_settings.py), as the TUI's F10 → Ork autonomy. Only the town's rules: you (your mascot, the
// look, Do not disturb) are the portrait's menu in the HUD (js/portrait.js, docs/design/portrait.md); here
// the town's rules, whether flames climb the roof of a building that waits for you, and whether
// anonymous usage stats are shared (core/usage.py), which a small dialog of its own asks once; last,
// which updates install by themselves (gui/updates.py; js/update.js offers the rest); and the phones
// paired with this machine (js/phones.js). Accounts: a personal Google account for Gmail, the calendar and
// Drive (js/accounts.js). The 🌙 Night round sits with the town's rules: on or off, Look now.
import { signal } from "@preact/signals";
import { useEffect, useState } from "preact/hooks";
import { html, cls } from "./html.js";
import { command, say, town } from "./link.js";
import { Dialog } from "./dialog.js";
import { PhonesField } from "./phones.js";
import { AccountsField } from "./accounts.js";

export const settingsOpen = signal(false);

function Steps({ label, items, value, onPick }) {
  return html`<div class="gui-field"><span class="ok-font-label">${label}</span>
    <span class="gui-steps" role="group" aria-label=${label}>
      ${items.map(([v, text, title]) => html`<button key=${v} class=${cls("gui-steps__one", { "is-on": value === v })}
          aria-pressed=${value === v} title=${title || ""} onClick=${() => onPick(v)}>${text}</button>`)}
    </span></div>`;
}

export const USAGE_WHAT = "Which features are used, as counts — never your code, prompts, paths or project names. "
  + "The list of every event is in docs/usage-stats.md.";

const UPDATE_WHAT = {
  auto: "Every update installs when the town opens.",
  critical: "A critical update (a fix for something that loses work or lets harm in) installs when the town opens; the others are offered.",
  ask: "Nothing installs by itself: every update is offered, a critical one loudly.",
};

function UpdatesField({ s }) {
  const [u, setU] = useState(null);
  const t = town.value;
  const policy = (u && u.policy) || s.updates;
  const check = () => command("update.check").then(setU, () => {});
  const pick = (v) => command("update.policy", { policy: v }).then((r) => setU(r || { policy: v }), () => {});
  return html`<${Steps} label=${say("Updates that install by themselves")} value=${policy}
      items=${[["auto", say("All")], ["critical", say("Critical")], ["ask", say("None")]]} onPick=${pick} />
    <p class="ok-font-status ok-tone-muted">${say(UPDATE_WHAT[policy] || "")}
      ${" "}${say(`This is Orkcraft ${s.version}.`)}${t && t.update ? say(` ${t.update.version} is out.`) : ""}</p>
    <span><button class="ok-btn" onClick=${check}>Check for updates</button></span>`;
}

function UsageField({ s, onPick }) {
  return html`<${Steps} label=${say("Share anonymous usage stats")} value=${s.usage === true}
      items=${[[true, say("On")], [false, say("Off")]]} onPick=${onPick} />
    <p class="ok-font-status ok-tone-muted">${say(s.usage_blocked ? `Off here: ${s.usage_blocked}.` : USAGE_WHAT)}</p>`;
}

/** Asked once, when the operator has not said yes or no: the town opens, then this. While the onboarding
 *  sets up the town, its one card asks it instead (js/onboarding.js). */
export function UsageAsk() {
  const [done, setDone] = useState(false);
  const t = town.value;
  if (done || !t || !t.usage_ask || t.onboarding || settingsOpen.value) return null;
  const answer = (v) => { setDone(true); command("usage.share", { share: v }).catch(() => {}); };
  return html`<${Dialog} title=${say("Help improve Orkcraft?")} onCancel=${() => setDone(true)}
      text=${say(USAGE_WHAT + " You can change this in Settings.")}
      actions=${html`<button class="ok-btn" onClick=${() => answer(false)}>${say("No, thanks")}</button>
        <button class="ok-btn primary" onClick=${() => answer(true)}>${say("Share")}</button>`} />`;
}

/** The 🌙 Night round (docs/design/night-round.md): on or off, what its last night found, and Look now. */
function RoundField({ s, set, setS }) {
  const r = s.round;
  if (!r || r.demo) return null;
  const now = () => command("round.now").then(setS, () => {});
  return html`<${Steps} label=${say("Night round: the orks look over the boards")} value=${r.on}
      items=${[[true, say("On")], [false, say("Off")]]} onPick=${(v) => set({ round: v })} />
    <p class="ok-font-status ok-tone-muted">${say(`At ${r.at}, the to-dos and tasks that lie get a 🌙 when a commit or a wiki page is about them, and the day's code gives at most 3 cleanup ideas as notes in Ideas. It never sends work to the orks. Free when nothing changed.`)}</p>
    <p class="ok-font-status">${say(`Last night: ${r.said}`)}</p>
    <span><button class="ok-btn" onClick=${now}>${say("Look now")}</button></span>
    ${s.round_said && html`<p class="ok-font-status ok-tone-ok">${say(s.round_said)}</p>`}`;
}

/** The AI tools: which are on, and the main one decisions and `main` steps run on. */
function ToolsField({ s, set }) {
  if (!s.tools) return null;
  const on = s.tools.filter((x) => x.on);
  const now = (s.tools.find((x) => x.id === s.main_now) || {}).title || s.main_now;
  return html`<div class="gui-field"><span class="ok-font-label">${say("AI tools")}</span>
      <span class="gui-steps" role="group" aria-label=${say("AI tools")}>
        ${s.tools.map((x) => html`<button key=${x.id} class=${cls("gui-steps__one", { "is-on": x.on })} aria-pressed=${x.on}
            onClick=${() => set({ tools: { [x.id]: !x.on } })}>${x.mark} ${x.title}</button>`)}
      </span></div>
    <${Steps} label=${say("Main tool")} value=${s.main_tool}
      items=${[["", say("First one on")], ...on.map((x) => [x.id, `${x.mark} ${x.title}`])]}
      onPick=${(v) => set({ main_tool: v })} />
    <p class="ok-font-status ok-tone-muted">${say(`Decisions run on ${now}: the Warchief, the planners, the Council's fast path, the stewards, and every ork step set to the main tool. An ork or a steward that names its own tool keeps it.`)}</p>
    <${TierModelsField} s=${s} set=${set} />`;
}

const OTHER = "\u0000other";

/** One tier of one tool: Latest of its family by default, the tool's other families and listed models, or
 *  one typed; Reset to latest. Its price when the price tables know it. */
function TierModel({ tool, row, set }) {
  const [typing, setTyping] = useState(false);
  const [typed, setTyped] = useState(row.chosen);
  const save = (model) => { setTyping(false); set({ tier_model: { tool: tool.id, tier: row.tier, model } }); };
  const pick = (v) => (v === OTHER ? setTyping(true) : save(v));
  return html`<div class="gui-field"><span class="ok-font-label">${tool.mark} ${tool.title} · ${say(row.label)}</span>
      <span>
        <select class="ok-input" value=${typing ? OTHER : row.chosen} aria-label=${say(`${tool.title}: the ${row.label} model`)}
            onChange=${(e) => pick(e.target.value)}>
          ${row.options.map(([v, text]) => html`<option key=${v} value=${v}>${say(text)}</option>`)}
          <option value=${OTHER}>${say("Another model…")}</option>
        </select>
        ${typing && html` <input class="ok-input" autofocus value=${typed} placeholder=${say("the model's name, as the tool spells it")}
            aria-label=${say(`${tool.title}: the ${row.label} model's name`)}
            onInput=${(e) => setTyped(e.target.value)} onKeyDown=${(e) => e.key === "Enter" && typed.trim() && save(typed.trim())} />
          <button class="ok-btn" disabled=${!typed.trim()} onClick=${() => save(typed.trim())}>${say("Use it")}</button>`}
        ${row.chosen && html` <button class="ok-btn" onClick=${() => save("")}>${say("Reset to latest")}</button>`}
      </span></div>
    <p class="ok-font-status ok-tone-muted">${say(`Runs on ${row.now}`)}${row.price ? ` · ${row.price}` : ""}</p>`;
}

/** The model each tier runs on, per tool that is on. */
function TierModelsField({ s, set }) {
  if (!s.tier_models || !s.tier_models.length) return null;
  return html`<p class="ok-font-status ok-tone-muted">${say("Each tool runs a tier on the latest model of its family, read from the tool once a day. A model chosen here wins over it; a model named in a building or a task wins over this.")}</p>
    ${s.tier_models.map((tool) => tool.tiers.map((row) => html`<${TierModel} key=${`${tool.id}-${row.tier}-${row.chosen}`}
        tool=${tool} row=${row} set=${set} />`))}`;
}

export function SettingsDialog() {
  const [s, setS] = useState(null);
  useEffect(() => { if (settingsOpen.value) command("town.settings").then(setS, () => setS(null)); }, [settingsOpen.value]);
  if (!settingsOpen.value || !s) return null;
  const close = () => { settingsOpen.value = false; };
  const set = (args) => command("town.settings.set", args).then(setS, () => {});
  const level = s.levels.find((x) => x.id === s.autonomy) || s.levels[0];
  const t = town.value;
  return html`<${Dialog} title=${say("Town settings")} onCancel=${close}
      actions=${html`<button class="ok-btn primary" onClick=${close}>${say("Close")}</button>`}>
    <div class="gui-form gui-settings">
      <span class="gui-you__camp">${say(`Town: ${t.project}`)}</span>
      <${Steps} label=${say("Autonomy: how freely the orks decide")} value=${s.autonomy}
        items=${s.levels.map((x) => [x.id, `${x.icon} ${say(x.title)}`, say(x.questions)])} onPick=${(v) => set({ autonomy: v })} />
      <p class="ok-font-status ok-tone-muted">${say(level.questions)} ${say(level.improves)}</p>
      <p class="ok-font-status ok-tone-muted">${say("A building follows this until its steward's window gives it its own.")}</p>
      ${s.autonomy === "clock" && html`
        <${Steps} label=${say("A question waits for you")} value=${s.wait}
          items=${s.waits.map((v) => [v, `${v} min`])} onPick=${(v) => set({ wait: v })} />
        <${Steps} label=${say("A change waits the hours you are around")} value=${s.rebuild}
          items=${s.rebuilds.map((v) => [v, `${v} h`])} onPick=${(v) => set({ rebuild: v })} />`}
      <${Steps} label=${say("Fire on the roofs")} value=${s.fire !== false}
        items=${[[true, say("On")], [false, say("Off")]]} onPick=${(v) => set({ fire: v })} />
      <p class="ok-font-status ok-tone-muted">${say("A building whose ork has waited a minute for you burns: flames climb its roof, more each minute. Never in quiet hours.")}</p>
      <${RoundField} s=${s} set=${set} setS=${setS} />
      <${ToolsField} s=${s} set=${set} />
      <${UsageField} s=${s} onPick=${(v) => command("usage.share", { share: v }).then(setS, () => {})} />
      ${!s.updates_blocked && html`<${UpdatesField} s=${s} />`}
      <${AccountsField} />
      <${PhonesField} />
    </div>
  </${Dialog}>`;
}
