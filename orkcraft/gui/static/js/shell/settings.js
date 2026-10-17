// The gear's menu (docs/specs/33-v1-shell.md §4, §9; spec 34 §5–§6), in the shell's modal: Push after merging, Download
// today's logs, Pair a phone. The theme follows the system.
import { html } from "../html.js";
import { review, act } from "./store.js";
import { Modal, closeDialog, openDialog } from "./modals.js";

/** The analytics zip of the last `days` days (gui/server.py `/api/analytics`): the model calls, the event log, each idea's plan and logs. */
const logsHref = (days) => `/api/analytics?days=${days}&t=${encodeURIComponent(new URLSearchParams(location.search).get("t") || "")}`;

export function SettingsDialog() {
  const push = !!review.value?.push;
  return html`<${Modal} title="Settings" onClose=${closeDialog} foot=${html`<button type="button" class="ok-btn primary" onClick=${closeDialog}>Done</button>`}>
    <div class="shell-form">
      <label class="ok-check">
        <input type="checkbox" class="gui-onb__hide" checked=${push} onChange=${(e) => act("ideas.into", { push: e.target.checked })} />
        <i>${push ? "✓" : ""}</i><span>Push after merging (sends your code to origin)</span></label>
      <div class="shell-field"><span class="ok-font-label">Your phone</span>
        <span><button type="button" class="ok-btn" onClick=${() => openDialog("pair")}>Pair a phone</button></span></div>
      <div class="shell-gear__logs"><span class="ok-font-label">Download today's logs</span>
        <a class="ok-btn" href=${logsHref(1)} download>Today</a><a class="ok-btn" href=${logsHref(7)} download>The last 7 days</a></div>
      <p class="ok-font-status ok-tone-muted">What you did and what the orks did, on this machine only. Off by default. The colours follow your system's light or dark setting.</p>
    </div>
  <//>`;
}
