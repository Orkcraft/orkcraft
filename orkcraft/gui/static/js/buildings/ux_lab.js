// ⚗️ The UX bench (docs/design/improve-buildings.md §6): the look of one type of building. Closed: whose look it
// works on. Open: its settings — which building, picked from the groups and icons Build shows (a look is a type's,
// never one building's on the map), and the AI tool that paints — over the gallery of that building's pictures:
// its Build icon and its Office icon, its house on each ground it is drawn for, its ork. Painting them again from
// your words, and its window and cards, come next (stage 6). It lays no road (realm/catalog.py `roads`).
import { useEffect, useRef, useState } from "preact/hooks";
import { html, cls } from "../html.js";
import { act, say } from "../link.js";
import { GROUPS, INTENTS } from "../build.js";
import { TypeIcon, HATS } from "../icons.js";
import { Dialog } from "../dialog.js";

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

/** One picture of the gallery: small, with a line saying what it is; a press opens it to change (when it can be). */
function Picture({ label, onOpen, children }) {
  const inner = html`<div class="ux-picture__frame">${children}</div>
    <figcaption class="ok-font-status ok-tone-muted">${say(label)}</figcaption>`;
  return onOpen ? html`<button class="ux-picture is-open" onClick=${onOpen} title=${say(`Change: ${label}`)}>${inner}</button>`
    : html`<figure class="ux-picture">${inner}</figure>`;
}

const v = (data, path) => (data.own[path] ? `?v=${data.own[path]}` : "");
const img = (data, path, cls_ = "ok-sprite") => html`<img class=${cls_} src=${`/ds/${path}${v(data, path)}`} alt="" draggable="false" />`;

function Gallery({ id, data }) {
  const [open, setOpen] = useState(null);           // {path, label} | {window: true}
  const t = data.target;
  const tile = INTENTS.find((x) => x.type === t);
  const houses = data.biomes.map((g) => ({ g, path: `sprites/buildings/${data.sprite}/header${g === "dirt" ? "" : `-${g}`}.png` }));
  const ork = HATS[t] ? `sprites/orks/steward-${HATS[t]}.png` : "sprites/orks/ork.png";
  return html`<div class="ux-gallery">
    <section class="ux-gallery__group"><h3 class="ok-list__head">${say("Icon")}</h3><div class="ux-gallery__row">
      ${tile && html`<${Picture} key=${`i${v(data, `sprites/intents/${tile.id}.png`)}`} label="In Build"
        onOpen=${() => setOpen({ path: `sprites/intents/${tile.id}.png`, label: "Its icon in Build" })}>
        ${img(data, `sprites/intents/${tile.id}.png`, "ok-sprite ux-picture__icon")}</${Picture}>`}
      <${Picture} label="In Office"><span class="ux-picture__office"><${TypeIcon} type=${t} /></span></${Picture}>
    </div></section>
    <section class="ux-gallery__group"><h3 class="ok-list__head">${say("Sprite")}</h3><div class="ux-gallery__row">
      ${houses.length ? houses.map((h) => html`<${Picture} key=${h.g + v(data, h.path)} label=${GROUND[h.g] || h.g}
          onOpen=${() => setOpen({ path: h.path, label: `Its house on ${GROUND[h.g] || h.g}` })}>${img(data, h.path, "ok-sprite ux-picture__house")}</${Picture}>`)
        : html`<p class="ok-font-status ok-tone-muted">${say("It has no house of its own yet: it wears the plain one.")}</p>`}
      <${Picture} key=${`o${v(data, ork)}`} label="Its ork" onOpen=${() => setOpen({ path: ork, label: "Its ork" })}>
        <span class="ux-picture__ork">${img(data, ork)}</span></${Picture}>
    </div></section>
    ${data.window && html`<section class="ux-gallery__group"><h3 class="ok-list__head">${say("Window")}</h3><div class="ux-gallery__row">
      <${Picture} label=${data.window.panes.length > 1 ? "Its Work window" : "Its Work window (one pane)"}
        onOpen=${data.window.panes.length > 1 ? () => setOpen({ window: true }) : null}>
        <${Wire} doc=${(data.window.draft && data.window.draft.doc) || data.window.doc} small=${true} /></${Picture}>
    </div></section>`}
    ${open && !open.window && html`<${PaintDialog} id=${id} data=${data} path=${open.path} label=${open.label} onClose=${() => setOpen(null)} />`}
    ${open && open.window && html`<${LayoutDialog} id=${id} data=${data} onClose=${() => setOpen(null)} />`}
  </div>`;
}

/** A picture large on the left (drag on it to mark a region), what to change on the right; Reset at the top brings
 *  the shipped one back, Apply at the bottom keeps it on this machine. */
function PaintDialog({ id, data, path, label, onClose }) {
  const [d, setD] = useState({ src: "", shipped: false, painting: false, error: "" });
  const [words, setWords] = useState("");
  const [region, setRegion] = useState(null);
  const box = useRef(null);
  const look = () => act(id, "draft", { path }).then(setD, () => {});
  useEffect(() => { look(); }, [path]);
  useEffect(() => {
    if (!d.painting) return undefined;
    const t = setInterval(look, 1500);
    return () => clearInterval(t);
  }, [d.painting]);
  const left = d.src || `/ds/${path}${v(data, path)}`;
  const down = (e) => {
    const r = box.current.getBoundingClientRect();
    const at = (ev) => ({ x: Math.min(Math.max((ev.clientX - r.left) / r.width, 0), 1), y: Math.min(Math.max((ev.clientY - r.top) / r.height, 0), 1) });
    const start = at(e);
    const move = (ev) => { const p = at(ev); setRegion({ x: Math.min(start.x, p.x), y: Math.min(start.y, p.y), w: Math.abs(p.x - start.x), h: Math.abs(p.y - start.y) }); };
    const up = () => { window.removeEventListener("pointermove", move); window.removeEventListener("pointerup", up); };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
  };
  const paint = () => act(id, "paint", { path, words, region: region && region.w > 0.01 ? region : null })
    .then(() => setD({ ...d, painting: true, error: "" }), () => {});
  const changed = !!d.src || d.shipped;
  return html`<${Dialog} title=${say(label)} wide=${true} onCancel=${() => { onClose(); }}
      actions=${html`<button class="ok-btn" onClick=${onClose}>${say("Close")}</button>
        <button class="ok-btn primary" disabled=${!changed || d.painting} onClick=${() => act(id, "apply", { path }).then(onClose, () => {})}>${say("Apply")}</button>`}>
    <div class="ux-edit">
      <div class="ux-edit__left">
        <div class="ux-edit__bar"><span class="ok-font-status ok-tone-muted">${say(d.shipped ? "As shipped" : d.src ? "The new one" : "As it is")}</span>
          <button class="ok-btn" disabled=${d.painting} onClick=${() => act(id, "reset", { path }).then(() => { setRegion(null); look(); }, () => {})}>${say("Reset")}</button></div>
        <div ref=${box} class="ux-edit__picture" onPointerDown=${down}>
          <img src=${left} alt="" draggable="false" />
          ${region && region.w > 0.01 && html`<div class="ux-edit__region" style=${`left:${region.x * 100}%;top:${region.y * 100}%;width:${region.w * 100}%;height:${region.h * 100}%`}></div>`}
        </div>
        <p class="ok-font-status ok-tone-muted">${say("Drag on it to mark a region: then only that part is painted again.")}</p>
      </div>
      <div class="ux-edit__right">
        <label class="gui-field"><span class="ok-font-label">${say(region && region.w > 0.01 ? "What to change in the region" : "What to change")}</span>
          <textarea class="ok-input gui-textarea" rows="5" maxlength="2000" value=${words} placeholder=${say("e.g. make it cuter: rounder roof, a small banner")}
            onInput=${(e) => setWords(e.target.value)}></textarea></label>
        <p class="ok-font-status ok-tone-muted">${say(`It goes with the style's own prompt to ${data.image_tool}; one picture each time.`)}</p>
        <span><button class="ok-btn primary" disabled=${words.trim().length < 3 || d.painting} onClick=${paint}>${say(d.painting ? "Painting…" : "Paint it")}</button>
          ${region && region.w > 0.01 && html`<button class="gui-link" onClick=${() => setRegion(null)}>${say("Whole picture")}</button>`}</span>
        ${d.error && html`<p class="ok-font-status ok-tone-error" role="alert">✗ ${say(d.error)}</p>`}
      </div>
    </div>
  </${Dialog}>`;
}

/** A window's UI document as boxes: its groups split as written, each pane its id and component. */
function Wire({ doc, small = false }) {
  const node = (n, i) => n.split
    ? html`<div key=${i} class=${cls("ux-wire__group", { "is-row": n.split === "row" })} style=${`flex:${n.size === "auto" ? "0 0 auto" : n.size || 1}`}>
        ${(n.panes || []).map(node)}</div>`
    : html`<div key=${n.id} class=${cls("ux-wire__pane", { "is-hidden": n.hidden })} style=${`flex:${n.size === "auto" ? "0 0 auto" : n.size || 1}`}>
        ${!small && html`<b>${n.title || n.id}</b> <span class="ok-tone-muted">${n.component}${n.font ? ` · ${n.font}` : ""}${n.tone ? ` · ${n.tone}` : ""}</span>`}</div>`;
  return doc ? html`<div class=${cls("ux-wire", { "is-small": small, "is-row": doc.split === "row" })}>${(doc.panes || []).map(node)}</div>` : null;
}

/** Its Work window as boxes on the left, what to change on the right: its steward lays it out again from the
 *  design system's roles; Apply gives it to every building of the type (undo takes it back). */
function LayoutDialog({ id, data, onClose }) {
  const [words, setWords] = useState("");
  const w = data.window;
  const draft = w.draft || {};
  return html`<${Dialog} title=${say("Its Work window")} wide=${true} onCancel=${onClose}
      actions=${html`<button class="ok-btn" onClick=${onClose}>${say("Close")}</button>
        <button class="ok-btn primary" disabled=${!draft.doc || draft.busy} onClick=${() => act(id, "layout_apply").then(onClose, () => {})}>${say("Apply")}</button>`}>
    <div class="ux-edit">
      <div class="ux-edit__left">
        <div class="ux-edit__bar"><span class="ok-font-status ok-tone-muted">${say(draft.doc ? "The new layout" : "As it is")}</span>
          <button class="ok-btn" disabled=${draft.busy} onClick=${() => act(id, "layout_reset")}>${say("Reset")}</button></div>
        <${Wire} doc=${draft.doc || w.doc} />
        ${draft.why && html`<p class="ok-font-status ok-tone-muted">${draft.why}</p>`}
      </div>
      <div class="ux-edit__right">
        <label class="gui-field"><span class="ok-font-label">${say("What to change in the window")}</span>
          <textarea class="ok-input gui-textarea" rows="5" maxlength="1000" value=${words} placeholder=${say("e.g. the tree narrower, the page larger")}
            onInput=${(e) => setWords(e.target.value)}></textarea></label>
        <p class="ok-font-status ok-tone-muted">${say(`Its panes: ${w.panes.join(", ")}. Laid out in the design system's roles only, checked before it shows.`)}</p>
        <span><button class="ok-btn primary" disabled=${words.trim().length < 3 || draft.busy || !w.standing}
          onClick=${() => act(id, "layout", { words })}>${say(draft.busy ? "Laying it out…" : "Lay it out")}</button></span>
        ${!w.standing && html`<p class="ok-font-status ok-tone-wait">${say("Build one of them first: its window is laid out on it.")}</p>`}
        ${draft.error && html`<p class="ok-font-status ok-tone-error" role="alert">✗ ${say(draft.error)}</p>`}
      </div>
    </div>
  </${Dialog}>`;
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
    ${data.target ? html`<${Gallery} id=${id} data=${data} />`
      : html`<p class="ok-font-status ok-tone-muted">${say("Pick a building above: its pictures show here.")}</p>`}
  </div>`;
}

/** The window: one pane, its settings over the gallery. */
export function panes(id, data) {
  return { main: () => html`<${Window} id=${id} data=${data} />` };
}
