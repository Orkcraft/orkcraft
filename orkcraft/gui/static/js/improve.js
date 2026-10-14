// Improve's days, over the Warchief's line (js/warchief.js): first the logs since the last update (since this machine
// started on the code it runs now, core/running.py), then each day with logs, for the Mechanic and the Farseer to
// read (gui/day_review.py, docs/design/improve-buildings.md §13) — again when it was read — and the latest 👎 alone.
// A day read has its changes: each one tried in the Test bench that tests its building, and measured there
// (gui/day_try.py); a pull request goes from that bench when its numbers are better, or, for a code change, as a fix
// the Mechanic writes in a copy of Orkline's source (Write the fix: js/fixes.js, gui/fixes.py).
import { useState } from "preact/hooks";
import { html } from "./html.js";
import { command, say } from "./link.js";

export const SINCE_UPDATE = "since-update";

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
  const up = (im && im.update) || {};
  return html`<p class="ok-font-status ok-tone-muted">${say("Which logs should the Mechanic and the Farseer read? They look at its costliest calls, failures, reworks and 👎, and the Warchief offers each change to apply or skip.")}</p>
    ${running && html`<p class="ok-font-status ok-tone-wait">${say(`Reading ${running.includes("_") ? "the logs since the last update" : dayWord(running)}…`)}</p>`}
    ${up.at && html`<span class="gui-warchief__day is-update">
      <button class="ok-btn" disabled=${!!running} onClick=${() => onPick(SINCE_UPDATE)}>${say("Since the last update")}</button>
      <span class="ok-font-status ok-tone-muted">${say(up.read ? `${up.read} · press again for the logs up to now` : `from ${up.at.replace("T", " ")}, up to now`)}</span>
      ${up.changes > 0 && html`<${Changes} day=${up.key} />`}
    </span>`}
    ${days.map((d) => html`<span key=${d.day} class="gui-warchief__day">
      <button class="ok-btn" disabled=${!!running} onClick=${() => onPick(d.day)}>${say(dayWord(d.day))}</button>
      <span class="ok-font-status ok-tone-muted">${say(d.read || "not read yet")}</span>
      ${d.read && html`<button class="gui-link ok-font-status" disabled=${!!running} onClick=${() => onPick(d.day, true)}>${say("Read again")}</button>`}
      ${d.changes > 0 && html`<${Changes} day=${d.day} />`}
    </span>`)}
    <span><button class="gui-link ok-font-status" onClick=${() => onPick("")}>${say("Only the latest 👎")}</button></span>`;
}

/** A read day's changes, asked for when opened: each with Try in the Test bench, or why it cannot be. */
function Changes({ day }) {
  const [rows, setRows] = useState(null);
  const [said, setSaid] = useState("");
  const load = () => command("improve.findings", { day }).then((r) => setRows(r.findings), () => setRows([]));
  if (rows === null) return html`<button class="gui-link ok-font-status" onClick=${load}>${say("Changes")}</button>`;
  const write = (n) => command("fixes.finding", { day, n }).then((r) => { setSaid(say(r.said)); }, () => {});
  const attempt = (n) => command("improve.try", { day, n }).then((r) => { setSaid(say(r.error || r.said)); load(); }, () => {});
  return html`<ul class="gui-improve__changes">
    ${rows.map((f) => html`<li key=${f.n} class="ok-font-status">
      <b>${say(f.title)}</b> · ${say(f.who)}: ${say(f.what)} <span class="ok-tone-muted">${say(`Change (${f.kind}): ${f.change}`)}</span>
      ${f.can ? html` <span class="ok-tone-muted">${say(f.can)}</span>`
        : html` <button class="ok-btn" onClick=${() => attempt(f.n)}>${say(f.tried ? "Try again" : `Try in ${f.bench}`)}</button>`}
      ${f.kind === "code" && html` <button class="ok-btn" onClick=${() => write(f.n)}>${say("Write the fix")}</button>`}
    </li>`)}
    ${said && html`<li class="ok-font-status ok-tone-wait">${said}</li>`}
  </ul>`;
}
