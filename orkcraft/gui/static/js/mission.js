// Mission 1's quest log in the Warchief's line (docs/design/first-mission.md §3; gui/mission.py, core/mission.py):
// the quest under way, the Warchief's line for it, its goal, what it costs, and its one press, which sets up the
// building on the plot lit for it; on quest 3, once the drill waits at the Review gate, it lifts the barrier (the
// person's pass), and the line after it says the drill rolled on (the finale, drawn in Camp: js/camp/carts.js). Before quest 4 it asks once for the hooks, showing what is written into which
// file and how to take it back. Skip the mission leaves the town as it stands. When the last quest is done, one line
// and Good.
import { html } from "./html.js";
import { command, say } from "./link.js";

const send = (name, args = {}) => command(name, args).catch(() => {});

function Hooks({ h }) {
  return html`<p class="ok-font-status"><b>${say(h.says)}</b></p>
    <ul class="ok-font-status gui-mission__hooks">
      ${h.files.map((f) => html`<li key=${f.file}><code>${f.file}</code> (${f.tool})
        <ul>${f.lines.map((ln) => html`<li key=${ln}>${say(ln)}</li>`)}</ul></li>`)}
    </ul>
    <p class="ok-font-status ok-tone-muted">${say(h.fail_open)} ${say(`To take them back: ${h.take_back}.`)}</p>
    <div class="gui-warchief__setup-foot">
      <button class="ok-btn" onClick=${() => send("mission.hooks", { yes: false })}>${say("Not now")}</button>
      <button class="ok-btn primary" onClick=${() => send("mission.hooks", { yes: true })}>${say("Write them")}</button>
    </div>`;
}

export function QuestLog({ m, name }) {
  if (m.finished) {
    return html`<p class="ok-font-status"><b>${say(name)}:</b> ${say(m.says)}</p>
      <div class="gui-warchief__setup-foot"><span></span>
        <button class="ok-btn primary" onClick=${() => send("mission.seen")}>${say("Good")}</button></div>`;
  }
  return html`<span class="ok-font-label">${say(`Mission 1 · quest ${m.n} of ${m.of}`)}</span>
    ${m.finale && html`<p class="ok-font-status ok-tone-muted" role="status">${say(m.finale.says)}</p>`}
    <p class="ok-font-status"><b>${say(name)}:</b> ${say(m.says)}</p>
    <p class="ok-font-status">${say(m.goal)}${m.cost && html` <span class="ok-tone-muted">· ${say(m.cost)}</span>`}</p>
    ${m.hooks && html`<${Hooks} h=${m.hooks} />`}
    ${m.needs && html`<p class="ok-font-status ok-tone-wait" role="status">${say(m.needs)}</p>`}
    <div class="gui-warchief__setup-foot">
      <button class="gui-link ok-font-status" onClick=${() => send("mission.leave")}>${say("Skip the mission")}</button>
      ${m.press && html`<button class="ok-btn primary" onClick=${() => send("mission.raise")}>${say(m.press)}</button>`}
    </div>`;
}
