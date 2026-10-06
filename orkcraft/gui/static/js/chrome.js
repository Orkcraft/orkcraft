// The chrome around the town (docs/design/calm-town.md §1): the HUD (the project's name opens the town's
// settings, js/settings.js; Halt All; the orks' questions, Orders; the treasury) and the toasts. The
// orkspaces are the War Map (js/warmap.js). Markup and classes are the design system's (design-system/components.md: Hud, WarMap, Toast).
import { html, cls } from "./html.js";
import { town, online, toasts, command, dismiss, say } from "./link.js";
import { openOrders } from "./orders.js";
import { settingsOpen } from "./settings.js";

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
    <button class=${cls("gui-hud__orders gui-link", { "ok-hud__fire": hud.alerts > 0 })} title=${say("The orks' questions")}
      onClick=${() => openOrders()}>${say("Orders")}${hud.alerts > 0 ? ` (${hud.alerts})` : ""}</button>
    <span class="ok-hud__spacer"></span>
    ${hud.hour_plain && html`<span class=${cls("ok-res", { quiet: hud.quiet })}>${hud.hour_plain}</span>`}
    ${hud.quota && html`<${Resource} icon="quota" word=${words.quota} value=${hud.quota} level=${hud.quota_level} />`}
    ${hud.show_gold && html`<${Resource} icon="gold" word=${words.gold} value=${hud.gold} level=${hud.gold_level} />`}
    <${Resource} icon="lumber" word=${words.lumber} value=${hud.lumber} level=${hud.lumber_level} />
    <${Resource} icon="meat" word=${words.supply} value=${`${hud.agents_working}/${hud.agents}`}
      level=${hud.supply >= hud.supply_max ? "over" : "ok"} />
  </header>`;
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
