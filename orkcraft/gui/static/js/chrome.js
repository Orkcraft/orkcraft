// The Office chrome around the town: the HUD (title bar), the War Map (the orkspaces, a small
// block over the town's bottom-left corner, as in the TUI), the status bar and the toasts. Markup and classes are the design system's
// (design-system/components.md: Hud, WarMap, KeyFooter, Toast).
import { html, cls } from "./html.js";
import { town, online, toasts, command, dismiss } from "./link.js";
import { showBuilding } from "./windows.js";
import { openOrders } from "./orders.js";
import { newSession, HALL } from "./tent.js";
import { building } from "./build.js";

const LEVEL = { warn: "is-warn", over: "is-over" };
const MARK = { information: "✓", warning: "⚠", error: "✗" };
const SEVERITY = { information: "is-ok", warning: "is-warn", error: "is-error" };

function Resource({ word, value, level }) {
  return html`<span class=${cls("ok-res", { [LEVEL[level] || ""]: !!LEVEL[level] })}>
    <span class="ok-word">${word}</span>${value}</span>`;
}

export function Hud() {
  const t = town.value;
  const hud = t.hud;
  const words = t.resources;
  return html`<header class="ok-hud gui-hud">
    <span class="ok-hud__brand">Orkcraft</span>
    <span class="gui-hud__project">${t.project}${t.demo ? " · demo" : ""}</span>
    ${online.value
      ? html`<span class="ok-hud__ready">Ready</span>`
      : html`<span class="ok-hud__halt">Disconnected — reconnecting</span>`}
    ${hud.alerts > 0 && html`<button class="ok-hud__fire gui-link" onClick=${() => openOrders()}>
      ${hud.alerts} awaiting an answer</button>`}
    <span class="ok-hud__spacer"></span>
    ${hud.hour_plain && html`<span class=${cls("ok-res", { quiet: hud.quiet })}>${hud.hour_plain}</span>`}
    ${hud.quota && html`<${Resource} word=${words.quota} value=${hud.quota} level=${hud.quota_level} />`}
    ${hud.show_gold && html`<${Resource} word=${words.gold} value=${hud.gold} level=${hud.gold_level} />`}
    <${Resource} word=${words.lumber} value=${hud.lumber} level=${hud.lumber_level} />
    <${Resource} word=${words.supply} value=${`${hud.supply}/${hud.supply_max}`}
      level=${hud.supply >= hud.supply_max ? "over" : "ok"} />
  </header>`;
}

export function WarMap() {
  const t = town.value;
  return html`<nav class="ok-list gui-warmap" aria-label="Orkspaces">
    <div class="ok-list__head">War Map</div>
    <ul class="ok-list__items">
      ${t.orkspaces.map((o) => html`<li key=${o.id}
          class=${cls("ok-item", { "is-selected": o.id === t.active_orkspace, "is-alert": o.questions > 0 })}
          onClick=${() => o.id !== t.active_orkspace && command("orkspace.select", { id: o.id })}>
        ${o.hotkey && html`<span class="ok-kbd">${o.hotkey.toUpperCase()}</span>`}${o.name}
        <span class="meta">${o.questions > 0 ? html`<span class="ok-word">?</span>`
                                              : html`<span class="ok-word">${o.biome}</span>`}</span>
      </li>`)}
    </ul>
  </nav>`;
}

export function StatusBar() {
  const t = town.value;
  return html`<footer class="ok-keys gui-status">
    <button class="gui-status__item" onClick=${() => command("halt")}>Halt All</button>
    <button class="gui-status__item" onClick=${() => { building.value = true; }}>Build</button>
    <button class="gui-status__item" onClick=${() => openOrders()}>Answers${t.alerts.length ? ` (${t.alerts.length})` : ""}</button>
    <button class="gui-status__item" onClick=${() => newSession("claude")}>Add agent</button>
    <button class="gui-status__item" onClick=${() => showBuilding(HALL)}>Sessions${t.sessions.length ? ` (${t.sessions.filter((s) => s.running).length})` : ""}</button>
    <span class="gui-status__spacer"></span>
    <span class="gui-status__item" title=${t.repo}>${t.repo}</span>
  </footer>`;
}

export function Toasts() {
  return html`<div class="gui-toasts" role="status" aria-live="polite">
    ${toasts.value.map((x) => html`<div key=${x.id} class=${cls("ok-toast", { [SEVERITY[x.severity] || "is-ok"]: true })}
        onClick=${() => dismiss(x.id)}>
      <span class="ok-toast__mark">${MARK[x.severity] || "✓"}</span>
      <span>${x.title ? html`<b>${x.title}</b> — ` : ""}${x.message}</span>
    </div>`)}
  </div>`;
}
