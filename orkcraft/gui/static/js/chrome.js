// The chrome around the town (docs/design/calm-town.md §1): the HUD (the project's name opens the town's
// settings, js/settings.js; Halt All; the orks' questions, Orders; the treasury), the orkspaces at the
// town's bottom left (`+ Orkspace` alone while there is one, their list with + once there are more) and
// the toasts. Markup and classes are the design system's (design-system/components.md: Hud, WarMap, Toast).
import { useState } from "preact/hooks";
import { html, cls } from "./html.js";
import { town, online, toasts, command, dismiss, say } from "./link.js";
import { openOrders } from "./orders.js";
import { settingsOpen } from "./settings.js";

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
    <button class="gui-hud__project gui-hud__menu" title=${say("Settings: how freely the orks decide, how long they wait")}
      onClick=${() => { settingsOpen.value = true; }}>${t.project}${t.demo ? " · demo" : ""} ▾</button>
    ${online.value
      ? html`<button class="gui-hud__stop" title=${say("Stop every ork at work")} onClick=${() => command("halt")}>Halt All</button>`
      : html`<span class="ok-hud__halt">Disconnected — reconnecting</span>`}
    <button class=${cls("gui-hud__orders gui-link", { "ok-hud__fire": hud.alerts > 0 })} title=${say("The orks' questions")}
      onClick=${() => openOrders()}>${say("Orders")}${hud.alerts > 0 ? ` (${hud.alerts})` : ""}</button>
    <span class="ok-hud__spacer"></span>
    ${hud.hour_plain && html`<span class=${cls("ok-res", { quiet: hud.quiet })}>${hud.hour_plain}</span>`}
    ${hud.quota && html`<${Resource} word=${words.quota} value=${hud.quota} level=${hud.quota_level} />`}
    ${hud.show_gold && html`<${Resource} word=${words.gold} value=${hud.gold} level=${hud.gold_level} />`}
    <${Resource} word=${words.lumber} value=${hud.lumber} level=${hud.lumber_level} />
    <${Resource} word=${words.supply} value=${`${hud.agents_working}/${hud.agents}`}
      level=${hud.supply >= hud.supply_max ? "over" : "ok"} />
  </header>`;
}

/** A new orkspace: its name, then the town goes to it. */
function NewOrkspace({ onDone }) {
  const [name, setName] = useState("");
  const make = () => name.trim() && command("orkspace.new", { name: name.trim() }).then(onDone, () => {});
  return html`<span class="gui-orkspaces__new">
    <input class="ok-input" autofocus placeholder=${say("Orkspace name")} value=${name} aria-label=${say("Orkspace name")}
      onInput=${(e) => setName(e.target.value)}
      onKeyDown=${(e) => { if (e.key === "Enter") make(); else if (e.key === "Escape") onDone(); }} />
  </span>`;
}

/** The orkspaces, bottom left: `+ Orkspace` while there is one, their list with + once there are more. */
export function Orkspaces() {
  const t = town.value;
  const [adding, setAdding] = useState(false);
  const many = t.orkspaces.length > 1;
  const add = adding ? html`<${NewOrkspace} onDone=${() => setAdding(false)} />`
    : html`<button class="ok-btn gui-orkspaces__add" title=${say("A new orkspace: another town of this project")}
        aria-label=${say("New orkspace")} onClick=${() => setAdding(true)}>+${many ? "" : html` ${say("Orkspace")}`}</button>`;
  return html`<nav class="gui-orkspaces" aria-label=${say("Orkspaces")}>
    ${many && t.orkspaces.map((o) => html`<button key=${o.id}
        class=${cls("ok-btn gui-orkspaces__one", { "is-selected": o.id === t.active_orkspace, "is-alert": o.questions > 0 })}
        aria-pressed=${o.id === t.active_orkspace}
        onClick=${() => o.id !== t.active_orkspace && command("orkspace.select", { id: o.id })}>
      ${say(o.name)}${o.questions > 0 && html` <span class="ok-word">?</span>`}</button>`)}
    ${add}
  </nav>`;
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
