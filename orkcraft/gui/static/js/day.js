// The person's day, in the sun dial's menu (js/chrome.js `Hour`): the working hours and leaving the camp
// (docs/design/audience.md §2a). In the working hours an ork's question raises no toast and no push: it waits in
// Answers, and the orks assume and mark what is safe to guess (gui/you.py). "I'm off" asks the town what the orks
// will do until evening, which cart first, and the cap; while away the menu says how much of the window went and
// offers Back (gui/away.py). The computer is kept awake only while carts work and it is on power.
import { useState } from "preact/hooks";
import { html } from "./html.js";
import { command, say } from "./link.js";
import { Steps } from "./portrait.js";

/** The working hours: off, or a start and an end (half-hour steps). */
export function WorkHours({ p }) {
  const w = (p && p.work) || {};
  const [start, setStart] = useState(w.start || "10:00");
  const [end, setEnd] = useState(w.end || "19:00");
  const save = (a, b) => command("you.work", { start: a, end: b }).catch(() => {});
  return html`<div class="gui-day">
    <${Steps} label="Working hours" value=${!!w.set}
      onPick=${(v) => (v ? save(start, end) : command("you.work", { on: false }).catch(() => {}))}
      items=${[[true, "On"], [false, "Off"]]} />
    ${w.set && html`<span class="gui-day__hours">
      <input class="ok-input" type="time" step="1800" value=${start} aria-label=${say("Working hours start")}
        onChange=${(e) => { setStart(e.target.value); save(e.target.value, end); }} />
      <span aria-hidden="true">–</span>
      <input class="ok-input" type="time" step="1800" value=${end} aria-label=${say("Working hours end")}
        onChange=${(e) => { setEnd(e.target.value); save(start, e.target.value); }} />
    </span>`}
    <p class="ok-font-status ok-tone-muted">${say(w.on
      ? `At work until ${w.end}: an ork's question raises no toast and no push; it waits in Answers${w.held ? ` (${w.held} so far)` : ""}. The orks assume and mark what is safe to guess.`
      : "In your working hours an ork's question raises no toast and no push; it waits in Answers, and the orks assume and mark what is safe to guess.")}</p>
  </div>`;
}

/** "I'm off": the Workchief's line about the day away, the cart to take first, Go. While away: the window spent, Back. */
export function Leave({ p, onDone }) {
  const away = p && p.away;
  const [plan, setPlan] = useState(null);
  const [first, setFirst] = useState("");
  if (away) {
    const spent = away.metered ? `${away.spent} % of ${away.cap} % of the window spent` : "no window measured";
    return html`<div class="gui-day gui-day__away">
      <p class="ok-font-status">${say(`Away since ${away.since}, until ${away.until}: ${spent}${away.capped ? ", the cap reached: the Agent pool waits for you" : ""}.`)}</p>
      <p class="ok-font-status ok-tone-muted">${say(away.lid)}</p>
      <button class="ok-btn primary" onClick=${() => { command("away.back").catch(() => {}); onDone(); }}>${say("I'm back")}</button>
    </div>`;
  }
  if (!plan) {
    const ask = () => command("away.plan").then((r) => { setPlan(r); setFirst((r.carts[0] || {}).task || ""); }, () => {});
    return html`<button class="ok-btn" onClick=${ask}>${say("I'm off…")}</button>`;
  }
  const go = () => { command("away.leave", { first }).catch(() => {}); setPlan(null); onDone(); };
  return html`<div class="gui-day gui-day__plan" role="group" aria-label=${say("Leaving the camp")}>
    <p class="ok-font-status">${say(`Workchief: ${plan.line}`)}</p>
    ${plan.carts.length > 1 && html`<ul class="gui-day__carts">
      ${plan.carts.slice(0, 6).map((c) => html`<li key=${c.task}><label>
        <input type="radio" name="gui-day-first" checked=${first === c.task} onChange=${() => setFirst(c.task)} />
        ${" "}${say(c.title)}</label></li>`)}
    </ul>`}
    <p class="ok-font-status ok-tone-muted">${say(plan.keep_awake ? plan.lid
      : "Keeping the computer awake is off in Town settings: while it sleeps the orks stop.")}${plan.keep_awake && plan.on_power === false ? say(" It is on battery now, so it is not kept awake.") : ""}</p>
    <span class="gui-day__acts">
      <button class="ok-btn primary" onClick=${go}>${say(plan.carts.length > 1 ? "Take this first, I'm off" : "I'm off")}</button>
      <button class="ok-btn" onClick=${() => setPlan(null)}>${say("Not now")}</button>
    </span>
  </div>`;
}
