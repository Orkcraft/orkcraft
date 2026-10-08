// The portrait (docs/design/portrait.md): the person in the HUD's left corner, as a hero's in Warcraft III.
// Camp draws the mascot's head at its stage (docs/design/growth.md §7), Office the role's two letters. Its
// marks: the stage, 🌙 while Do not disturb holds, a dot while an ork asks (the dot opens Answers). A click
// opens its menu: You (the head, the stage, Next, the deeds), the look, Do not disturb, Town settings…. The look and Do not disturb are the person's, per machine (gui/you.py).
import { signal } from "@preact/signals";
import { useEffect, useRef } from "preact/hooks";
import { html, cls } from "./html.js";
import { command, say, town } from "./link.js";
import { MascotHead, BIOMES } from "./icons.js";
import { terrainUrl } from "./terrain.js";
import { openOrders } from "./orders.js";
import { settingsOpen } from "./settings.js";

export const portraitOpen = signal(false);

const ROMAN = ["", "I", "II", "III", "IV"];

function ground(home) {
  const b = BIOMES[home] || BIOMES.dirt;
  const url = terrainUrl(home);
  return `--ground:${b.ground};--land:${b.land};--glyphs:${url ? `url("${url}")` : "none"}`;
}

/** The head: the mascot in Camp, the monogram in Office. */
function Face({ y, p, size }) {
  if (p.look === "office") return html`<span class=${cls("gui-portrait__mono", { "is-big": size > 2 })}>${p.mono}</span>`;
  return html`<span class="gui-portrait__ground" style=${ground(y.home)}><${MascotHead} sprite=${y.sprite} stage=${y.stage} size=${size} /></span>`;
}

function Steps({ label, items, value, onPick }) {
  return html`<div class="gui-portrait__row"><span class="ok-font-label">${say(label)}</span>
    <span class="gui-steps" role="group" aria-label=${say(label)}>
      ${items.map(([v, text]) => html`<button key=${v} class=${cls("gui-steps__one", { "is-on": value === v })}
          aria-pressed=${value === v} onClick=${() => onPick(v)}>${say(text)}</button>`)}
    </span></div>`;
}

function Menu({ y, p }) {
  const ref = useRef(null);
  useEffect(() => {
    const away = (e) => { if (ref.current && !ref.current.contains(e.target) && !e.target.closest(".gui-portrait")) portraitOpen.value = false; };
    const esc = (e) => { if (e.key === "Escape") portraitOpen.value = false; };
    document.addEventListener("pointerdown", away);
    document.addEventListener("keydown", esc);
    return () => { document.removeEventListener("pointerdown", away); document.removeEventListener("keydown", esc); };
  }, []);
  const d = p.dnd || {};
  const set = (args) => command(args.look ? "you.look" : "you.dnd", args).catch(() => {});
  return html`<section ref=${ref} class="gui-portrait__menu" role="dialog" aria-label=${say("You")}>
    <div class="gui-you">
      <${Face} y=${y} p=${p} size=${4} />
      <div class="gui-you__who">
        <span class="gui-you__name">${p.look === "office" ? y.role : y.name}</span>
        ${p.look === "office"
          ? html`<span class="ok-font-status ok-tone-muted">${say("Your stage and deeds keep counting; Camp shows them.")}</span>`
          : html`<span class="ok-font-status ok-tone-muted">${say(`${y.role} · stage ${y.stage} of 4`)}</span>
            ${y.next && html`<span class="ok-font-status">${say(`Next: ${y.next}`)}</span>`}
            <span class="gui-you__deeds" aria-label=${say("Deeds")}>
              ${y.deeds.map((x) => html`<span key=${x.id} class=${cls("gui-you__deed", { "is-ahead": !x.done })}
                  title=${say(x.done ? `${x.title} · ${x.done}` : `${x.title}: ${x.hint}`)} aria-label=${say(x.title)}>${x.icon}</span>`)}
            </span>`}
      </div>
    </div>
    <${Steps} label="Look" value=${p.look} onPick=${(v) => set({ look: v })}
      items=${[["camp", "Camp"], ["office", "Office"]]} />
    <${Steps} label="Do not disturb" value=${d.choice || "off"} onPick=${(v) => set({ dnd: v })}
      items=${[["off", "Off"], ["1h", "1 h"], ["morning", `Until ${d.morning || "09:00"}`], ["on", "On"]]} />
    <p class="ok-font-status ok-tone-muted">${say(d.on
      ? `${d.label}: sounds, pushes and the Warchief's news wait; only errors show. The orks keep working.`
      : "Do not disturb holds sounds, pushes and the Warchief's news; the orks keep working.")}</p>
    <div class="gui-portrait__links">
      <button class="gui-link" onClick=${() => { portraitOpen.value = false; settingsOpen.value = true; }}>${say("Town settings…")}</button>
    </div>
  </section>`;
}

export function Portrait() {
  const t = town.value;
  const y = t.growth && t.growth.you;
  const p = t.portrait;
  if (!y || !p) return null;
  const d = p.dnd || {};
  const asks = t.hud.alerts > 0;
  const who = p.look === "office" ? y.role : `${y.name}, stage ${y.stage}`;
  return html`<span class="gui-portrait-slot">
    <button class=${cls("gui-portrait", { "is-office": p.look === "office", "is-open": portraitOpen.value })}
        aria-expanded=${portraitOpen.value} aria-label=${say(`You: ${who}${d.on ? ` · Do not disturb, ${d.label}` : ""}`)}
        title=${say(`You: ${who}`)} onClick=${() => { portraitOpen.value = !portraitOpen.value; }}>
      <${Face} y=${y} p=${p} size=${2} />
      ${p.look !== "office" && html`<span class="gui-portrait__stage" aria-hidden="true">${ROMAN[y.stage] || ""}</span>`}
      ${d.on && html`<span class="gui-portrait__dnd" aria-hidden="true">🌙</span>`}
    </button>
    ${asks && html`<button class="gui-portrait__asks" title=${say("An ork asks: Answers")} aria-label=${say("Answers")}
        onClick=${() => openOrders()}></button>`}
    ${portraitOpen.value && html`<${Menu} y=${y} p=${p} />`}
  </span>`;
}
