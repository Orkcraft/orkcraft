// A newer Orkcraft (gui/updates.py, core/updates.py, docs/updates.md): asked once per version, loudly
// for a critical one; one click installs it with the tool that installed this copy, and the window
// opens again on it. "Later" hides an ordinary update until the next version, a critical one until the
// window opens again (and under the default policy it installs by itself then).
import { signal } from "@preact/signals";
import { html } from "./html.js";
import { command, say, town } from "./link.js";
import { Dialog } from "./dialog.js";
import { settingsOpen } from "./settings.js";

const HIDDEN_KEY = "orkcraft.update.later";
const hidden = signal(readHidden());          // the version "Later" was said to

function readHidden() {
  try { return localStorage.getItem(HIDDEN_KEY) || ""; } catch { return ""; }
}

function later(u) {
  hidden.value = u.version;
  if (u.critical) return;                    // a critical one is asked again when the window opens
  try { localStorage.setItem(HIDDEN_KEY, u.version); } catch { /* the page keeps it for now */ }
}

export const install = () => command("update.install").catch(() => {});

export function UpdateAsk() {
  const t = town.value;
  const u = t && t.update;
  if (!u || settingsOpen.value) return null;
  const busy = u.state === "installing" || u.state === "installed";
  if (!busy && u.state !== "failed" && hidden.value === u.version) return null;
  const notes = u.critical ? u.critical_notes : u.notes;
  const title = u.critical ? say(`Critical update: Orkcraft ${u.version}`) : say(`Orkcraft ${u.version} is out`);
  const close = () => later(u);
  return html`<${Dialog} title=${title} warn=${u.critical} onCancel=${busy ? () => {} : close}
      meta=${say(`You have ${u.current}.`)}
      actions=${busy
        ? html`<button class="ok-btn" disabled>${u.state === "installed" ? "Restarting…" : "Installing…"}</button>`
        : html`<button class="ok-btn" onClick=${close}>Later</button>
          ${u.can && html`<button class="ok-btn primary" onClick=${install}>
            ${u.state === "failed" ? "Try again" : "Update and restart"}</button>`}`}>
    ${notes.length > 0 && html`<ul class="gui-rows">${notes.map((n, k) => html`<li key=${k} class="ok-font-body">${n}</li>`)}</ul>`}
    ${u.critical && !busy && html`<p class="ok-font-status">
      It fixes something that can lose work or let harm in: install it now.</p>`}
    <p class="ok-font-status ok-tone-muted">${u.can
      ? html`Orkcraft restarts when it is in: what runs now stops. It installs with <code>${u.how}</code>`
      : html`It cannot install itself here: ${u.how}`}</p>
    ${u.state === "failed" && html`<p class="ok-font-status ok-tone-error">It did not install. Orkcraft keeps running ${u.current}.</p>
      <pre class="gui-pre gui-orders__context">${u.error}</pre>`}
  </${Dialog}>`;
}
