// ⚗️ The UX bench (docs/design/improve-buildings.md §6): the look of one type of building. Closed: whose look it
// works on. Open: its settings — which building, picked from the groups and icons Build shows (a look is a type's,
// never one building's on the map), and the AI tool that paints — over the gallery of that building's pictures:
// its Build icon and its Office icon, its house on each ground it is drawn for, its ork. Painting them again from
// your words, and its window and cards, come next (stage 6). It lays no road (realm/catalog.py `roads`).
import { html, cls } from "../html.js";
import { act, say } from "../link.js";
import { GROUPS, INTENTS } from "../build.js";
import { TypeIcon, HutSprite, StewardHead } from "../icons.js";

const sheet = new URL("./ux_lab.css", import.meta.url).href;
if (!document.querySelector(`link[href="${sheet}"]`)) {
  const link = document.createElement("link");
  link.rel = "stylesheet";
  link.href = sheet;
  document.head.appendChild(link);
}

const OWN = "ux_lab";
const GROUND = { dirt: "Dirt and forest", ice: "Ice", dust: "Dust", void: "Void", lava: "Lava", meadow: "Meadow" };

export function card(b) {
  const c = b.card;
  if (!c) return null;
  if (!c.target) {
    return html`<div class="gui-hut__body-in">
      <div class="gui-hut__big">${say("No building yet")}</div>
      <div class="gui-hut__text ok-tone-muted">${say("Open it and pick the building whose look to work on")}</div>
    </div>`;
  }
  return html`<div class="gui-hut__body-in">
    <div class="gui-hut__big">${say(c.title)}</div>
    <div class="gui-hut__foot"><span>${say(`${c.pictures} pictures`)}</span></div>
  </div>`;
}

/** Which building: Build's own groups and icons, the one picked framed. */
function Pick({ id, target }) {
  const tiles = INTENTS.filter((x) => x.type !== OWN);
  return html`<div class="ux-pick" role="group" aria-label=${say("Which building")}>
    ${GROUPS.map((g) => ({ ...g, tiles: tiles.filter((x) => x.group === g.id) })).filter((g) => g.tiles.length).map((g) => html`
      <div key=${g.id} class="gui-build__group" role="group" aria-label=${say(g.word)}>
        <span class="gui-build__group-word">${say(g.word)}</span>
        <div class="gui-build__group-tiles">${g.tiles.map((x) => html`
          <button key=${x.id} class=${cls("gui-catalog__item gui-build__tile", { "is-picked": x.type === target })}
              aria-pressed=${x.type === target} title=${say(x.word)} onClick=${() => act(id, "pick", { type: x.type })}>
            <img class="ok-sprite" src=${`/ds/sprites/intents/${x.id}.png`} srcset=${`/ds/sprites/intents/${x.id}@2x.png 2x`}
              width="32" height="32" alt="" draggable="false" />
            <span class="gui-build__word">${say(x.word)}</span></button>`)}</div></div>`)}
  </div>`;
}

/** One picture of the gallery: small, with a line saying what it is. */
function Picture({ label, children }) {
  return html`<figure class="ux-picture"><div class="ux-picture__frame">${children}</div>
    <figcaption class="ok-font-status ok-tone-muted">${say(label)}</figcaption></figure>`;
}

function Gallery({ data }) {
  const t = data.target;
  const tile = INTENTS.find((x) => x.type === t);
  return html`<div class="ux-gallery">
    <section class="ux-gallery__group"><h3 class="ok-list__head">${say("Icon")}</h3><div class="ux-gallery__row">
      ${tile && html`<${Picture} label="In Build"><img class="ok-sprite" src=${`/ds/sprites/intents/${tile.id}.png`}
        srcset=${`/ds/sprites/intents/${tile.id}@2x.png 2x`} width="48" height="48" alt="" draggable="false" /></${Picture}>`}
      <${Picture} label="In Office"><span class="ux-picture__office"><${TypeIcon} type=${t} /></span></${Picture}>
    </div></section>
    <section class="ux-gallery__group"><h3 class="ok-list__head">${say("Sprite")}</h3><div class="ux-gallery__row">
      ${data.biomes.length ? data.biomes.map((g) => html`<${Picture} key=${g} label=${GROUND[g] || g}>
          <${HutSprite} type=${t} biome=${g === "dirt" ? "" : g} /></${Picture}>`)
        : html`<p class="ok-font-status ok-tone-muted">${say("It has no house of its own yet: it wears the plain one.")}</p>`}
      <${Picture} label="Its ork"><span class="ux-picture__ork"><${StewardHead} type=${t} /></span></${Picture}>
    </div></section>
    <p class="ok-font-status ok-tone-muted">${say("Next: press a picture to paint it again from your words, and its window and cards.")}</p>
  </div>`;
}

function Window({ id, data }) {
  return html`<div class="ux-window">
    <section class="ux-settings">
      <p class="ok-list__head">${say("Which building")}</p>
      <${Pick} id=${id} target=${data.target} />
      <label class="ux-tool"><span class="ok-font-status">${say("Paints with")}</span>
        <select class="ok-input" value=${data.image_tool} onChange=${(e) => act(id, "tool", { tool: e.target.value })}>
          ${data.tools.map((x) => html`<option key=${x.id} value=${x.id}>${x.title}${x.on ? "" : ` (${say("off")})`}</option>`)}
        </select></label>
    </section>
    ${data.target ? html`<${Gallery} data=${data} />`
      : html`<p class="ok-font-status ok-tone-muted">${say("Pick a building above: its pictures show here.")}</p>`}
  </div>`;
}

/** The window: one pane, its settings over the gallery. */
export function panes(id, data) {
  return { main: () => html`<${Window} id=${id} data=${data} />` };
}
