// Mission 1's quest log in the Warchief's line (docs/design/first-mission.md §3; gui/mission.py, core/mission.py):
// the quest under way, the Warchief's line for it, its goal, what it costs, and its one press, which raises the
// building on the plot lit for it. Skip the mission leaves the town as it stands. When the last quest is done,
// one line and Good.
import { html } from "./html.js";
import { command, say } from "./link.js";

const send = (name, args = {}) => command(name, args).catch(() => {});

export function QuestLog({ m, name }) {
  if (m.finished) {
    return html`<p class="ok-font-status"><b>${say(name)}:</b> ${say(m.says)}</p>
      <div class="gui-warchief__setup-foot"><span></span>
        <button class="ok-btn primary" onClick=${() => send("mission.seen")}>${say("Good")}</button></div>`;
  }
  return html`<span class="ok-font-label">${say(`Mission 1 · quest ${m.n} of ${m.of}`)}</span>
    <p class="ok-font-status"><b>${say(name)}:</b> ${say(m.says)}</p>
    <p class="ok-font-status">${say(m.goal)} <span class="ok-tone-muted">· ${say(m.cost)}</span></p>
    <div class="gui-warchief__setup-foot">
      <button class="gui-link ok-font-status" onClick=${() => send("mission.leave")}>${say("Skip the mission")}</button>
      ${m.press && html`<button class="ok-btn primary" onClick=${() => send("mission.raise")}>${say(m.press)}</button>`}
    </div>`;
}
