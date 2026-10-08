// The chrome around the town (docs/design/calm-town.md §1): the HUD (the portrait, js/portrait.js; the project's name opens the town's
// settings, js/settings.js; Halt All; the orks' questions, Orders; the treasury) and the toasts. The
// orkspaces are the War Map (js/warmap.js). Markup and classes are the design system's (design-system/components.md: Hud, WarMap, Toast).
import { useState } from "preact/hooks";
import { html, cls } from "./html.js";
import { town, online, toasts, command, dismiss, say } from "./link.js";
import { openOrders } from "./orders.js";
import { settingsOpen } from "./settings.js";
import { Portrait } from "./portrait.js";
import { Scheme } from "./icons.js";
import { narrow } from "./pocket.js";

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
    ${narrow.value && html`<${Portrait} />`}
    <span class="ok-hud__brand">Orkcraft</span>
    <button class="gui-hud__project gui-hud__menu" title=${say("Town settings: how freely the orks decide, how long they wait")}
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
    ${toasts.value.map((x) => x.tool ? html`<${ToolToast} key=${x.id} x=${x} />`
      : html`<div key=${x.id} class=${cls("ok-toast", { [SEVERITY[x.severity] || "is-ok"]: true })}
        onClick=${() => dismiss(x.id)}>
      <span class="ok-toast__mark">${MARK[x.severity] || "✓"}</span>
      <span>${x.title ? html`<b>${x.title}</b> — ` : ""}${x.message}</span>
    </div>`)}
  </div>`;
}

// An AI tool that failed (gui/failures.py): what happened in one line, then Switch to another tool that is
// installed (a menu when there are several), Retry, and Details — the tool's own words, to read or copy. Each
// tool wears its harness mark (js/icons.js Scheme: the pixel sprite in Camp, the glyph in Office).
function ToolToast({ x }) {
  const t = x.tool;
  const [open, setOpen] = useState("");          // "" | "details" | "switch"
  const close = () => dismiss(x.id);
  const toggle = (what) => setOpen(open === what ? "" : what);
  const switchTo = (to) => { close(); command("tool_error.switch", { to, retry: t.retry || "" }).catch(() => {}); };
  const retry = () => { close(); command("tool_error.retry", { retry: t.retry }).catch(() => {}); };
  const copy = () => navigator.clipboard?.writeText(t.detail || "").catch(() => {});
  const others = t.switch || [];
  return html`<div class="ok-toast is-error gui-toolerr" role="alert">
    <span class="ok-toast__mark">✗</span>
    <div class="gui-toolerr__body">
      <div class="gui-toolerr__head">
        <b class="gui-toolerr__title"><${Scheme} scheme=${t.mark} />${x.title}</b>
        <button class="gui-toolerr__close" title="Close" aria-label="Close" onClick=${close}>×</button>
      </div>
      <span>${say(x.message)}</span>
      ${t.action && html`<span class="gui-toolerr__note">${say(t.action)}</span>`}
      ${!others.length && t.hint && html`<span class="gui-toolerr__note">${say(t.hint)}</span>`}
      <div class="gui-toolerr__acts">
        ${others.length === 1 && html`<button class="ok-btn primary" onClick=${() => switchTo(others[0].id)}><${Scheme} scheme=${others[0].mark} />Switch to ${others[0].title}</button>`}
        ${others.length > 1 && html`<button class="ok-btn primary" aria-expanded=${open === "switch"}
          onClick=${() => toggle("switch")}>Switch to… ▾</button>`}
        ${t.retry && html`<button class="ok-btn" onClick=${retry}>Retry</button>`}
        <button class="ok-btn" aria-expanded=${open === "details"} onClick=${() => toggle("details")}>Details</button>
      </div>
      ${open === "switch" && html`<div class="gui-toolerr__menu" role="menu">
        ${others.map((o) => html`<button key=${o.id} class="ok-btn" role="menuitem" onClick=${() => switchTo(o.id)}><${Scheme} scheme=${o.mark} />${o.title}</button>`)}
      </div>`}
      ${open === "details" && html`<div class="gui-toolerr__details">
        <pre>${t.detail}</pre>
        <button class="ok-btn" onClick=${copy}>Copy</button>
      </div>`}
    </div>
  </div>`;
}
