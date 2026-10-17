// The top bar on every pane (docs/specs/33-v1-shell.md §6): Orkline · what is left of each AI tool (the smaller of its
// window and its week; a hover or focus shows each window and when it resets) · today's Spend · Stop all · the gear.
// Roles only: warning at 20 % or less left, danger at 5 % or less (docs/design-system.md).
import { useState } from "preact/hooks";
import { html, cls } from "../html.js";
import { town, command, say } from "../link.js";
import { review, act } from "./store.js";

const MARKS = { claude: "✱", agy: "∩", codex: "◇", hermes: "☿", pi: "π", cursor: "▷" };
export const WARN = 0.2, DANGER = 0.05;

const pct = (left) => `${Math.round(left * 100)} %`;
export const levelOf = (left) => (left <= DANGER ? "danger" : left <= WARN ? "warn" : "ok");

/** "resets at 18:00", or with the day when it is not today. */
export function resetWords(iso, now = new Date()) {
  const d = new Date(iso);
  if (!iso || Number.isNaN(d.getTime())) return "";
  const hm = d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", hour12: false });
  return d.toDateString() === now.toDateString() ? `resets at ${hm}` : `resets ${d.toLocaleDateString([], { weekday: "short" })} ${hm}`;
}

function Limit({ l }) {
  const level = levelOf(l.left);
  return html`<span class=${cls("shell-limit", `is-${level}`)} tabindex="0" data-provider=${l.provider}
      aria-label=${`${l.name}: ${pct(l.left)} left`}>
    <span aria-hidden="true">${MARKS[l.provider] || l.name[0]}</span> <b>${pct(l.left)}</b>${level !== "ok" && html`<span aria-hidden="true"> ⚠</span>`}
    <span class="shell-pop" role="tooltip"><b>${l.name}</b>
      ${l.rows.map((r) => html`<span key=${r.window} class="shell-pop__row"><span>${r.window}</span><b>${pct(r.left)}</b>
        <span class="ok-tone-muted">${resetWords(r.reset)}</span></span>`)}</span>
  </span>`;
}

export function Limits() {
  const limits = town.value?.limits || [];
  return html`<span class="shell-limits" aria-label="What is left of your AI tools">${limits.map((l) => html`<${Limit} key=${l.provider} l=${l} />`)}</span>`;
}

/** The analytics zip of the last `days` days (gui/server.py `/api/analytics`): the model calls, the event log, each idea's plan and logs. */
const logsHref = (days) => `/api/analytics?days=${days}&t=${encodeURIComponent(new URLSearchParams(location.search).get("t") || "")}`;

function Gear() {
  const [open, setOpen] = useState(false);
  const push = !!review.value?.push;
  return html`<span class="shell-gear">
    <button class="ok-btn" aria-label="Settings" aria-haspopup="true" aria-expanded=${open} onClick=${() => setOpen(!open)}>⚙</button>
    ${open && html`<div class="shell-gear__pop ok-win" role="group" aria-label="Settings" onKeyDown=${(e) => e.key === "Escape" && setOpen(false)}>
      <label class="ok-check">
        <input type="checkbox" class="gui-onb__hide" checked=${push} onChange=${(e) => act("ideas.into", { push: e.target.checked })} />
        <i>${push ? "✓" : ""}</i><span>Push after merging (sends your code to origin)</span></label>
      <div class="shell-gear__logs"><span class="ok-font-label">Download today's logs</span>
        <a class="ok-btn" href=${logsHref(1)} download>Today</a><a class="ok-btn" href=${logsHref(7)} download>The last 7 days</a></div>
      <p class="ok-font-status ok-tone-muted">What you did and what the orks did, on this machine only. Off by default. The colours follow your system's light or dark setting.</p>
    </div>`}
  </span>`;
}

export function TopBar() {
  const hud = town.value?.hud || {};
  const spend = hud.show_gold ? hud.gold : hud.lumber;
  return html`<header class="shell-top">
    <span class="shell-top__brand">Orkline</span>
    <${Limits} />
    <span class="shell-top__spacer"></span>
    <span class="shell-top__spend" title="What was spent today"><span class="ok-tone-muted">Spend</span> <b>${spend ?? "—"}</b></span>
    <button class="ok-btn danger" title=${say("Stop every ork, script and browser at once")}
      onClick=${() => command("halt").catch(() => {})}>Stop all</button>
    <${Gear} />
  </header>`;
}
