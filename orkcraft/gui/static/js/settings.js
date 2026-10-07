// The town's settings, opened from the project's name in the HUD (js/chrome.js): how freely the orks
// decide — the level every building follows until it has its own (its steward's window, js/steward.js)
// — and, on the clock, how long a question and a change wait for you. The host's town.settings
// (gui/town_settings.py), as the TUI's F10 → Ork autonomy. Its head is you: your mascot at its stage, what
// the next stage asks and your deeds, the ones ahead grey with a hint (docs/design/growth.md §7); below
// it, the camp's rules.
import { signal } from "@preact/signals";
import { useEffect, useState } from "preact/hooks";
import { html, cls } from "./html.js";
import { command, say, town } from "./link.js";
import { MascotHead, BIOMES } from "./icons.js";
import { terrainUrl } from "./terrain.js";
import { Dialog } from "./dialog.js";

export const settingsOpen = signal(false);

/** You: the mascot (per machine, every camp's), its name and stage, the next stage, the deeds. */
function You({ y }) {
  return html`<section class="gui-you">
    <span class="gui-you__home" title=${say(`Home: ${y.home}`)}
        style=${`--ground:${(BIOMES[y.home] || BIOMES.dirt).ground};--land:${(BIOMES[y.home] || BIOMES.dirt).land};--glyphs:${terrainUrl(y.home) ? `url("${terrainUrl(y.home)}")` : "none"}`}>
      <${MascotHead} kin=${y.kin} stage=${y.stage} size=${4} />
    </span>
    <div class="gui-you__who">
      <span class="gui-you__name">${y.name}</span>
      <span class="ok-font-status ok-tone-muted">${say(`${y.role} · stage ${y.stage} of 4`)}</span>
      ${y.next && html`<span class="ok-font-status">${say(`Next: ${y.next}`)}</span>`}
      <span class="gui-you__deeds" aria-label=${say("Deeds")}>
        ${y.deeds.map((d) => html`<span key=${d.id} class=${cls("gui-you__deed", { "is-ahead": !d.done })}
            title=${say(d.done ? `${d.title} · ${d.done}` : `${d.title}: ${d.hint}`)} aria-label=${say(d.title)}>${d.icon}</span>`)}
      </span>
    </div>
  </section>`;
}

function Steps({ label, items, value, onPick }) {
  return html`<div class="gui-field"><span class="ok-font-label">${label}</span>
    <span class="gui-steps" role="group" aria-label=${label}>
      ${items.map(([v, text, title]) => html`<button key=${v} class=${cls("gui-steps__one", { "is-on": value === v })}
          aria-pressed=${value === v} title=${title || ""} onClick=${() => onPick(v)}>${text}</button>`)}
    </span></div>`;
}

export function SettingsDialog() {
  const [s, setS] = useState(null);
  useEffect(() => { if (settingsOpen.value) command("town.settings").then(setS, () => setS(null)); }, [settingsOpen.value]);
  if (!settingsOpen.value || !s) return null;
  const close = () => { settingsOpen.value = false; };
  const set = (args) => command("town.settings.set", args).then(setS, () => {});
  const level = s.levels.find((x) => x.id === s.autonomy) || s.levels[0];
  const t = town.value;
  const you = t && t.growth && t.growth.you;
  return html`<${Dialog} title=${say("Settings")} onCancel=${close}
      actions=${html`<button class="ok-btn primary" onClick=${close}>${say("Close")}</button>`}>
    ${you && html`<${You} y=${you} />`}
    <div class="gui-form gui-settings">
      <span class="gui-you__camp">${say(`Town: ${t.project}`)}</span>
      <${Steps} label=${say("Autonomy: how freely the orks decide")} value=${s.autonomy}
        items=${s.levels.map((x) => [x.id, `${x.icon} ${say(x.title)}`, say(x.questions)])} onPick=${(v) => set({ autonomy: v })} />
      <p class="ok-font-status ok-tone-muted">${say(level.questions)} ${say(level.improves)}</p>
      <p class="ok-font-status ok-tone-muted">${say("A building follows this until its steward's window gives it its own.")}</p>
      ${s.autonomy === "clock" && html`
        <${Steps} label=${say("A question waits for you")} value=${s.wait}
          items=${s.waits.map((v) => [v, `${v} min`])} onPick=${(v) => set({ wait: v })} />
        <${Steps} label=${say("A change waits the hours you are around")} value=${s.rebuild}
          items=${s.rebuilds.map((v) => [v, `${v} h`])} onPick=${(v) => set({ rebuild: v })} />`}
    </div>
  </${Dialog}>`;
}
