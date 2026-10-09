// The chrome around the town (docs/design/calm-town.md §1): the HUD (the portrait, js/portrait.js; the project's name opens the town's
// settings, js/settings.js; Halt All; the treasury; the orks' questions are the Warchief's line's, js/warchief.js) and the toasts. The
// orkspaces are the War Map (js/warmap.js). Markup and classes are the design system's (design-system/components.md: Hud, WarMap, Toast).
import { useEffect, useRef, useState } from "preact/hooks";
import { html, cls } from "./html.js";
import { town, online, toasts, command, dismiss, say } from "./link.js";
import { settingsOpen } from "./settings.js";
import { Portrait, Steps } from "./portrait.js";
import { Scheme } from "./icons.js";
import { opened, panelShown, panelWidth } from "./windows.js";
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

/** The hour in the middle of the HUD, as an old strategy game's day and night dial: a sun while the orks work, a
 *  moon in quiet hours (no fires, no sound, no push). A press opens its menu — will the town bother me now, and how
 *  does it look (as the TUI's was): quiet hours on or off, Do not disturb, the look (Camp, Office, or by the shift:
 *  Office in work hours). */
function Hour({ hud, p }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  useEffect(() => {
    if (!open) return undefined;
    const away = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    const key = (e) => { if (e.key === "Escape") setOpen(false); };
    document.addEventListener("pointerdown", away, true);
    window.addEventListener("keydown", key);
    return () => { document.removeEventListener("pointerdown", away, true); window.removeEventListener("keydown", key); };
  }, [open]);
  const night = !!hud.quiet;
  const said = night ? say(`Night: ${hud.hour_plain.replace(/^🌙\s*/, "")}`) : hud.quiet_hours ? say(`Day: orks work. Quiet hours ${hud.quiet_hours}`)
    : say("Day: orks work. No quiet hours");
  const set = (on) => { command("you.quiet", { on }).catch(() => {}); setOpen(false); };
  const d = (p && p.dnd) || {};
  // over the middle of the town: a building's window open on the right takes its part away
  const panel = panelShown() && !opened.value.full ? panelWidth.value : 0;
  return html`<span ref=${ref} class="gui-hour" style=${`--town-w:calc(100vw - ${panel}px)`}>
    <button class=${cls("gui-hour__dial", { "is-night": night })} title=${said} aria-label=${said} aria-expanded=${open}
        onClick=${() => setOpen(!open)}>
      <img class="ok-sprite" src=${`/ds/sprites/icons/${night ? "night" : "day"}.png`}
        srcset=${`/ds/sprites/icons/${night ? "night" : "day"}@2x.png 2x`} width="32" height="32" alt="" draggable="false" />
      <span class="gui-hour__glyph" aria-hidden="true">${night ? "☾" : "☀"}</span></button>
    ${open && html`<div class="gui-hour__menu" role="menu">
      <p class="ok-font-status">${said}</p>
      <p class="ok-font-status ok-tone-muted">${say("In quiet hours no building burns, nothing sounds and no phone is called.")}</p>
      ${hud.quiet_hours ? html`<button class="ok-btn" role="menuitem" onClick=${() => set(false)}>${say("Turn quiet hours off")}</button>`
        : html`<button class="ok-btn primary" role="menuitem" onClick=${() => set(true)}>${say("Turn quiet hours on, from 23:00")}</button>`}
      ${p && html`<${Steps} label="Do not disturb" value=${d.choice || "off"} onPick=${(v) => command("you.dnd", { dnd: v }).catch(() => {})}
          items=${[["off", "Off"], ["1h", "1 h"], ["morning", `Until ${d.morning || "09:00"}`], ["on", "On"]]} />
        <p class="ok-font-status ok-tone-muted">${say(d.on
          ? `${d.label}: sounds, pushes and the Warchief's news wait; only errors show. The orks keep working.`
          : "Do not disturb holds sounds, pushes and the Warchief's news; the orks keep working.")}</p>
        <${Steps} label="Look" value=${p.look_choice || p.look} onPick=${(v) => command("you.look", { look: v }).catch(() => {})}
          items=${[["shift", "By shift"], ["camp", "Camp"], ["office", "Office"]]} />
        <p class="ok-font-status ok-tone-muted">${say(`By shift: Office ${p.shift || "09:00–17:00"}, Camp the rest of the day.`)}</p>`}
    </div>`}
  </span>`;
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
      ? html`<button class="gui-hud__stop" title=${say("Stop every ork at work")} onClick=${() => command("halt")}>Stop all</button>`
      : html`<span class="ok-hud__halt">Disconnected — reconnecting</span>`}
    <span class="ok-hud__spacer"></span>
    <${Hour} hud=${hud} p=${t.portrait} />
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
