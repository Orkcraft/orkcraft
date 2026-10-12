// Improve's days, over the Warchief's line (js/warchief.js): each day with logs, for the Mechanic and the Farseer to
// read (gui/day_review.py, docs/design/improve-buildings.md §13) — again when it was read — and the latest 👎 alone.
import { html } from "./html.js";
import { say } from "./link.js";

const iso = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;

function dayWord(day) {
  const now = new Date();
  if (day === iso(now)) return "Today";
  now.setDate(now.getDate() - 1);
  return day === iso(now) ? "Yesterday" : day;
}

/** Improve's days: each day with logs, read by the Mechanic and the Farseer (again when it was read); the latest 👎. */
export function ImprovePick({ im, onPick }) {
  const days = (im && im.days) || [];
  const running = im && im.running;
  return html`<p class="ok-font-status ok-tone-muted">${say("Which day should the Mechanic and the Farseer read? They look at its costliest calls, failures, reworks and 👎, and the Warchief offers each change to apply or skip.")}</p>
    ${running && html`<p class="ok-font-status ok-tone-wait">${say(`Reading ${dayWord(running)}…`)}</p>`}
    ${days.map((d) => html`<span key=${d.day} class="gui-warchief__day">
      <button class="ok-btn" disabled=${!!running} onClick=${() => onPick(d.day)}>${say(dayWord(d.day))}</button>
      <span class="ok-font-status ok-tone-muted">${say(d.read || "not read yet")}</span>
      ${d.read && html`<button class="gui-link ok-font-status" disabled=${!!running} onClick=${() => onPick(d.day, true)}>${say("Read again")}</button>`}
    </span>`)}
    <span><button class="gui-link ok-font-status" onClick=${() => onPick("")}>${say("Only the latest 👎")}</button></span>`;
}
