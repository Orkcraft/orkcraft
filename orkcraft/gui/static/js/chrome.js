// The Office chrome around the town: the HUD (title bar: the project's name opens the town's settings,
// js/settings.js; Halt All), the War Map (the orkspaces, a small block over the town's bottom-left
// corner, as in the TUI), the status bar (Answers, the project's folder; Build and the sessions are the
// Town Hall's) and the toasts. Markup and classes are the design system's
// (design-system/components.md: Hud, WarMap, KeyFooter, Toast).
import { html, cls } from "./html.js";
import { town, online, toasts, command, dismiss, say } from "./link.js";
import { openOrders } from "./orders.js";
import { settingsOpen } from "./settings.js";
import { OrkHead } from "./icons.js";

const LEVEL = { warn: "is-warn", over: "is-over" };
const MARK = { information: "✓", warning: "⚠", error: "✗" };
const SEVERITY = { information: "is-ok", warning: "is-warn", error: "is-error" };

// Camp shows each resource's sprite before its word and value (design-system/sprites/icons/res-*.png);
// Office hides the sprite (`.ok-res img`).
function Resource({ icon, word, value, level }) {
  return html`<span class=${cls("ok-res", { [LEVEL[level] || ""]: !!LEVEL[level] })}>
    <img src=${`/ds/sprites/icons/res-${icon}.png`} srcset=${`/ds/sprites/icons/res-${icon}@2x.png 2x`} alt="" />
    <span class="ok-word">${word}</span>${value}</span>`;
}

export function Hud() {
  const t = town.value;
  const hud = t.hud;
  const words = t.resources;
  return html`<header class="ok-hud gui-hud">
    <img class="ok-sprite gui-hud__mark" src="/ds/logo/ork-mark-camp.svg" width="24" height="16" alt="" />
    <span class="ok-hud__brand">Orkcraft</span>
    <button class="gui-hud__project gui-hud__menu" title=${say("Settings: how freely the orks decide, how long they wait")}
      onClick=${() => { settingsOpen.value = true; }}>${t.project}${t.demo ? " · demo" : ""} ▾</button>
    ${online.value
      ? html`<button class="gui-hud__stop" title=${say("Stop every ork at work")} onClick=${() => command("halt")}>Halt All</button>`
      : html`<span class="ok-hud__halt">Disconnected — reconnecting</span>`}
    ${hud.alerts > 0 && html`<button class="ok-hud__fire gui-link" onClick=${() => openOrders()}>
      ${hud.alerts} awaiting an answer</button>`}
    <span class="ok-hud__spacer"></span>
    ${hud.hour_plain && html`<span class=${cls("ok-res", { quiet: hud.quiet })}>${hud.hour_plain}</span>`}
    ${hud.quota && html`<${Resource} icon="quota" word=${words.quota} value=${hud.quota} level=${hud.quota_level} />`}
    ${hud.show_gold && html`<${Resource} icon="gold" word=${words.gold} value=${hud.gold} level=${hud.gold_level} />`}
    <${Resource} icon="lumber" word=${words.lumber} value=${hud.lumber} level=${hud.lumber_level} />
    <${Resource} icon="meat" word=${words.supply} value=${`${hud.agents_working}/${hud.agents}`}
      level=${hud.supply >= hud.supply_max ? "over" : "ok"} />
  </header>`;
}

export function WarMap() {
  const t = town.value;
  return html`<nav class="ok-list gui-warmap" aria-label=${say("Orkspaces")}>
    <div class="ok-list__head">${say("War Map")}</div>
    <ul class="ok-list__items">
      ${t.orkspaces.map((o) => html`<li key=${o.id}
          class=${cls("ok-item", { "is-selected": o.id === t.active_orkspace, "is-alert": o.questions > 0 })}
          onClick=${() => o.id !== t.active_orkspace && command("orkspace.select", { id: o.id })}>
        ${o.hotkey && html`<span class="ok-kbd">${o.hotkey.toUpperCase()}</span>`}${say(o.name)}
        <span class="meta">${o.questions > 0 ? html`<${OrkHead} o=${{ status: "alert" }} /><span class="ok-word">?</span>`
                                              : html`<span class="ok-word">${o.biome}</span>`}</span>
      </li>`)}
    </ul>
  </nav>`;
}

export function StatusBar() {
  const t = town.value;
  return html`<footer class="ok-keys gui-status">
    <button class="gui-status__item" onClick=${() => openOrders()}>Answers${t.alerts.length ? ` (${t.alerts.length})` : ""}</button>
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
