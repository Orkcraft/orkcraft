// The portrait (docs/design/portrait.md): the person in the HUD's left corner, as a hero's in Warcraft III.
// Camp draws the mascot's head at its stage (docs/design/growth.md §7), Office the role's two letters. Its
// marks: the stage and a dot while an ork asks (the dot opens Answers). Beside the big one stand two quick
// toggles: the horn (Do not disturb on / off, never shown on the head) and the look (Camp / Office). A click
// opens its menu: You (the head, the stage, Next, the deeds), then what is Camp's own — Fire on the roofs, the
// cards' background — Phone (Pair a phone: its QR code right in the menu; Settings → Phones keeps the list and
// Forget) and Town settings… (models, AI tools, how the town works). The sun's menu (js/chrome.js `Hour`) keeps
// the longer choices: Do not disturb for 1 h or Until, the look By shift. Below 640 px, with no corner, the
// menu is a sheet at the window's foot. These are the person's, per machine (gui/you.py).
import { signal } from "@preact/signals";
import { useEffect, useRef } from "preact/hooks";
import { html, cls } from "./html.js";
import { command, say, town } from "./link.js";
import { MascotHead, BIOMES } from "./icons.js";
import { terrainUrl } from "./terrain.js";
import { openOrders } from "./orders.js";
import { settingsOpen } from "./settings.js";
import { RoleIcon } from "./roles.js";
import { PairHere } from "./phones.js";

export const portraitOpen = signal(false);

// The cards' background in Camp, this browser's alone (docs/design/yards.md §3e, §7): "yard" (the default), each card's
// inside a step lighter than the town's ground, in its biome's hue; or "ground", the cards drawn on the ground itself.
// A card that asks keeps the fire's ground. "panel" and "shade" are gone: a browser that kept one draws a yard.
const CARDS_KEY = "orkcraft.cards";
const CARDS = ["yard", "ground"];
const readCards = () => { try { const v = localStorage.getItem(CARDS_KEY); return CARDS.includes(v) ? v : "yard"; } catch { return "yard"; } };
const cardGround = signal(readCards());
document.documentElement.dataset.cards = cardGround.value;
function setCards(v) {
  cardGround.value = v;
  document.documentElement.dataset.cards = v;
  try { localStorage.setItem(CARDS_KEY, v); } catch { /* private window: this session only */ }
}

const ROMAN = ["", "I", "II", "III", "IV"];

function ground(home) {
  const b = BIOMES[home] || BIOMES.dirt;
  const url = terrainUrl(home);
  return `--ground:${b.ground};--land:${b.land};--glyphs:${url ? `url("${url}")` : "none"}`;
}

/** The head: the mascot in Camp, the monogram in Office. */
function Face({ y, p, size }) {
  if (p.look === "office") return html`<span class=${cls("gui-portrait__mono", { "is-big": size > 3 })} title=${p.mono}>
    <${RoleIcon} role=${p.role || ""} mono=${p.mono} size=${size > 3 ? 28 : size > 2 ? 20 : 14} /></span>`;
  return html`<span class="gui-portrait__ground" style=${ground(y.home)}><${MascotHead} sprite=${y.sprite} stage=${y.stage} size=${size} /></span>`;
}

export function Steps({ label, items, value, onPick }) {
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
  const set = (args) => command("you.fire", args).catch(() => {});
  const office = p.look === "office";
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
    ${!office && html`<${Steps} label="Fire on the roofs" value=${p.fire !== false} onPick=${(v) => set({ fire: v })}
      items=${[[true, "On"], [false, "Off"]]} />
    <p class="ok-font-status ok-tone-muted">${say("A building whose ork has waited a minute for you burns: flames climb its roof, more each minute. Never in quiet hours.")}</p>`}
    <p class="ok-font-status ok-tone-muted">${say("Do not disturb for an hour or until morning, and the look by the shift, are under the sun in the middle of the top bar.")}</p>
    ${!office && html`<${Steps} label="Card background" value=${cardGround.value} onPick=${setCards}
      items=${[["yard", "Yard"], ["ground", "Ground"]]} />
    <p class="ok-font-status ok-tone-muted">${say("Yard: inside its fence each card is a step lighter than the town's ground. Ground: the cards are drawn on the ground itself. This browser only.")}</p>`}
    <${PairHere} />
    <div class="gui-portrait__links">
      <button class="gui-link" onClick=${() => { portraitOpen.value = false; settingsOpen.value = true; }}>${say("Town settings…")}</button>
    </div>
  </section>`;
}

/** Do not disturb's mark: a speaking horn while the town may call, the horn struck through while it holds —
 *  Camp's pixel sprite (design-system/sprites/icons/notify-*.png, tools/icon_sprites.py), Office's line icon. */
function Horn({ on }) {
  const name = on ? "notify-off" : "notify-on";
  return html`<img class="ok-sprite gui-portrait__horn" src=${`/ds/sprites/icons/${name}.png`}
      srcset=${`/ds/sprites/icons/${name}@2x.png 2x`} width="16" height="16" alt="" />
    <svg viewBox="0 0 16 16" width="12" height="12" aria-hidden="true">
      <path d="M2.5 6h2.2l6.8-3.5v11L4.7 10H2.5zM5 10l1 3.8h1.8L7.2 10.6" />${on && html`<path d="M1.5 1.5l13 13" />`}</svg>`;
}

/** The corner's quick buttons beside the big portrait: Do not disturb on or off (the sun's menu keeps 1 h and
 *  Until), and the look, Camp or Office (the sun's menu keeps By shift). A phone is paired in the menu. */
function Toggles({ p }) {
  const d = p.dnd || {};
  const office = p.look === "office";
  return html`<span class="gui-portrait__toggles">
    <button class=${cls("gui-portrait__toggle", { "is-on": d.on })} aria-pressed=${!!d.on}
        title=${say(d.on ? `Do not disturb: ${d.label} — a click turns it off` : "Do not disturb: off — a click turns it on")}
        aria-label=${say("Do not disturb")} onClick=${() => command("you.dnd", { dnd: d.on ? "off" : "on" }).catch(() => {})}>
      <${Horn} on=${!!d.on} />
    </button>
    <button class=${cls("gui-portrait__toggle", { "is-on": office })} aria-pressed=${office}
        title=${say(office ? "Office look — a click switches to Camp" : "Camp look — a click switches to Office")}
        aria-label=${say("Office look")} onClick=${() => command("you.look", { look: office ? "camp" : "office" }).catch(() => {})}>
      <svg viewBox="0 0 16 16" width="11" height="11" aria-hidden="true"><rect x="2.5" y="5.5" width="11" height="8" /><path d="M6 5.5V3.5h4v2" /></svg>
    </button>
  </span>`;
}

/** `corner`: the big portrait over the town's top-left corner, framed, its quick toggles beside it (a wide
 *  window); else the small one in the HUD (a narrow window, where the list of buildings needs the room). */
export function Portrait({ corner = false }) {
  const t = town.value;
  const y = t.growth && t.growth.you;
  const p = t.portrait;
  if (!y || !p) return null;
  const d = p.dnd || {};
  const asks = t.hud.alerts > 0;
  const who = p.look === "office" ? y.role : `${y.name}, stage ${y.stage}`;
  return html`<span class=${cls("gui-portrait-slot", { "is-corner": corner })}>
    <button class=${cls("gui-portrait", { "is-office": p.look === "office", "is-open": portraitOpen.value, "is-big": corner })}
        aria-expanded=${portraitOpen.value} aria-label=${say(`You: ${who}${d.on ? ` · Do not disturb, ${d.label}` : ""}`)}
        title=${say(`You: ${who}`)} onClick=${() => { portraitOpen.value = !portraitOpen.value; }}>
      <${Face} y=${y} p=${p} size=${corner ? 3 : 2} />
      ${p.look !== "office" && html`<span class="gui-portrait__stage" aria-hidden="true">${ROMAN[y.stage] || ""}</span>`}
    </button>
    ${asks && html`<button class="gui-portrait__asks" title=${say("An ork asks: Answers")} aria-label=${say("Answers")}
        onClick=${() => openOrders()}></button>`}
    ${corner && html`<${Toggles} p=${p} />`}
    ${portraitOpen.value && html`<${Menu} y=${y} p=${p} />`}
  </span>`;
}
