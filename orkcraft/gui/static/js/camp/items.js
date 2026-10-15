// The items the person places in Camp (docs/design/v3-prompts.md §14, realm/items.py, gui/growth.py): the inventory
// panel lists what they may place (the starter set of g2 decor, and what they earned, each saying what for); an item
// dragged onto the camp snaps to the grid of js/camp/grass.js, which shows while dragging where it fits — on grass
// only. A placed one is dragged again to move it, or back onto the panel (or its right click) to put it back. Items
// stand under every signal, cart and flag, in their own calm colours; Office draws none (only Camp draws this). Nothing
// nags: no count, no badge, no "items to place". When a building (or a row moving) takes a placed item's cell, the
// item goes back to the inventory quietly, and one line waits in the panel ("The Anvil went back to your items when
// the Test bench was built"), said once it is opened.
import { signal } from "@preact/signals";
import { useEffect, useRef } from "preact/hooks";
import { html, cls } from "../html.js";
import { command, say } from "../link.js";
import { openMenu } from "../menu.js";
import { boxAt, blockers, cellAt, fits, grid, takenBy } from "./grass.js";

export const inventoryOpen = signal(false);
const drag = signal(null);        // {item, size, sprite, placed?, gx, gy, ok, over: "world" | "panel" | ""}
let here = { L: null, placed: [], rows: {} };   // the town as last drawn: the layout, what stands, the items by id

const DS = "/ds/";
const rowsById = (inv) => Object.fromEntries((inv || []).map((r) => [r.id, r]));

function boxesBut(skip) {
  return here.placed.filter((p) => p.id !== skip && here.rows[p.item])
    .map((p) => boxAt(here.L, here.rows[p.item].size, p.x, p.y));
}

/** Where the pointer is over the world, at an item's feet: its cell and whether it fits there. */
function track(e) {
  const d = drag.value;
  if (!d || !here.L) return;
  const world = document.querySelector(".gui-camp__world");
  const panel = document.querySelector(".gui-items");
  const over = panel && panel.contains(document.elementFromPoint(e.clientX, e.clientY)) ? "panel" : "world";
  const r = world ? world.getBoundingClientRect() : { left: 0, top: 0 };
  const { gx, gy } = cellAt(here.L, e.clientX - r.left, e.clientY - r.top);
  const ok = over === "world" && fits(here.L, boxAt(here.L, d.size, gx, gy), d.walls, d.others);
  if (gx !== d.gx || gy !== d.gy || ok !== d.ok || over !== d.over) drag.value = { ...d, gx, gy, ok, over };
}

function start(e, d) {
  if (e.button !== 0 || !here.L) return;
  e.preventDefault();
  e.stopPropagation();
  drag.value = { ...d, gx: null, gy: null, ok: false, over: "", walls: blockers(here.L), others: boxesBut(d.placed) };
  const move = (ev) => track(ev);
  const up = (ev) => {
    window.removeEventListener("pointermove", move);
    window.removeEventListener("pointerup", up);
    track(ev);
    const end = drag.value;
    drag.value = null;
    if (!end) return;
    if (end.over === "panel" && end.placed) command("items.remove", { id: end.placed }).catch(() => {});
    else if (end.ok && end.placed) command("items.move", { id: end.placed, x: end.gx, y: end.gy }).catch(() => {});
    else if (end.ok) command("items.place", { item: end.item, x: end.gx, y: end.gy }).catch(() => {});
  };
  window.addEventListener("pointermove", move);
  window.addEventListener("pointerup", up);
  track(e);
}

/** The grid while dragging: the cells where the dragged item fits, faint over the grass. One canvas, drawn once a drag. */
function Fit({ L }) {
  const ref = useRef(null);
  const d = drag.value;
  const key = d ? `${d.item}/${d.placed || ""}` : "";
  useEffect(() => {
    const cv = ref.current;
    if (!cv || !d) return;
    const g = grid(L), ctx = cv.getContext("2d");
    ctx.clearRect(0, 0, cv.width, cv.height);
    ctx.fillStyle = "rgba(255, 255, 255, 0.14)";
    ctx.strokeStyle = "rgba(255, 255, 255, 0.28)";
    const x0 = Math.floor(-g.x / g.c), x1 = Math.ceil((L.w - g.x) / g.c), y0 = Math.floor(-g.y / g.c), y1 = Math.ceil((L.h - g.y) / g.c);
    for (let gy = y0; gy < y1; gy++) {
      for (let gx = x0; gx < x1; gx++) {
        if (!fits(L, boxAt(L, d.size, gx, gy), d.walls, d.others)) continue;
        const x = g.x + gx * g.c, y = g.y + gy * g.c;
        ctx.fillRect(x + 1, y + 1, g.c - 2, g.c - 2);
        ctx.strokeRect(x + 1.5, y + 1.5, g.c - 3, g.c - 3);
      }
    }
  }, [key, L]);
  if (!d) return null;
  return html`<canvas ref=${ref} class="gui-items__grid" width=${L.w} height=${L.h} style=${`width:${L.w}px;height:${L.h}px`}></canvas>`;
}

const sentBack = new Set();        // asked to go back once; the next snapshot no longer has them
let known = null;                  // the buildings drawn last time: a new one is what moved the camp

/** The placed items on the open orkspace's grass, and the dragged one where it would land. In the world's frame.
 *  One whose cell a building took goes back to the inventory, not drawn against it. */
export function Placed({ L, items, buildings }) {
  const rows = rowsById(items && items.inventory);
  const all = (items && items.placed) || [];
  const walls = blockers(L);
  const taken = all.filter((p) => rows[p.item] && takenBy(L, boxAt(L, rows[p.item].size, p.x, p.y), walls) !== null);
  const ids = (buildings || []).map((b) => b.id);
  const fresh = known ? (buildings || []).find((b) => !known.includes(b.id)) : null;
  useEffect(() => {
    known = ids;
    for (const p of taken) {
      if (sentBack.has(p.id)) continue;
      sentBack.add(p.id);
      const by = takenBy(L, boxAt(L, rows[p.item].size, p.x, p.y), walls);
      // the building that stands there now, else the one just built that moved the row (the home, a path)
      const b = (by && (buildings || []).find((x) => x.id === by)) || fresh;
      command("items.back", { id: p.id, because: b ? b.title : "" }).catch(() => {});
    }
  });
  const placed = all.filter((p) => !taken.includes(p));
  here = { L, placed, rows };
  const d = drag.value;
  const putBack = (p) => (e) => openMenu(e, [{ label: "Put back in the inventory", run: () => command("items.remove", { id: p.id }).catch(() => {}) }]);
  return html`<div class="gui-camp__layer is-items">
    <${Fit} L=${L} />
    ${placed.map((p) => {
      const r = rows[p.item];
      if (!r) return null;
      const b = boxAt(L, r.size, p.x, p.y);
      return html`<img key=${p.id} class=${cls("gui-camp__px gui-items__placed", { "is-lifted": d && d.placed === p.id })}
        src=${DS + r.sprite} alt=${say(r.name)} title=${say(`${r.name} · ${r.why}`)} draggable="false" data-item=${p.item}
        style=${`left:${b.x}px;top:${b.y}px;width:${b.w}px;height:${b.h}px`}
        onPointerDown=${(e) => start(e, { item: p.item, size: r.size, sprite: r.sprite, placed: p.id })}
        onClick=${(e) => e.stopPropagation()} onContextMenu=${putBack(p)} />`;
    })}
    ${d && d.over === "world" && d.gx !== null && (() => {
      const b = boxAt(L, d.size, d.gx, d.gy);
      return html`<img class=${cls("gui-camp__px gui-items__ghost", { "is-ok": d.ok })} src=${DS + d.sprite} alt="" draggable="false"
        style=${`left:${b.x}px;top:${b.y}px;width:${b.w}px;height:${b.h}px`} />`;
    })()}
  </div>`;
}

/** The inventory: a quiet button in Camp's corner, and its panel. Each row says what the item is and why it is
 *  here; an earned one placed already says so. */
export function Inventory({ items }) {
  const rows = (items && items.inventory) || [];
  const notes = (items && items.notes) || [];
  const open = inventoryOpen.value;
  useEffect(() => {                          // a note is said once the panel is open; closing it marks them seen
    if (!open || !notes.length) return undefined;
    return () => command("items.seen").catch(() => {});
  }, [open, notes.length]);
  return html`<div class="gui-items-slot" onPointerDown=${(e) => e.stopPropagation()} onClick=${(e) => e.stopPropagation()}>
    <button class=${cls("gui-items__toggle ok-btn", { "is-on": open })} aria-expanded=${open}
        title=${say("Items: things you earned and the starter set, to place on the camp's grass")}
        onClick=${() => { inventoryOpen.value = !open; }}>${say("Items")}</button>
    ${open && html`<section class=${cls("gui-items", { "is-target": drag.value && drag.value.placed && drag.value.over === "panel" })}
        role="region" aria-label=${say("Items")}>
      ${notes.map((n, k) => html`<p key=${k} class="ok-font-body gui-items__note"><span class="gui-items__who">${say("Workchief")}:</span> ${say(n)}</p>`)}
      <p class="ok-font-status ok-tone-muted gui-items__hint">${say("Drag one onto the camp's grass: the grid shows where it fits. Drag a placed one back here to put it away.")}</p>
      <ul class="gui-items__list">${rows.map((r) => {
        const out = r.left === 0;
        return html`<li key=${r.id} class=${cls("gui-items__row", { "is-out": out })} data-item=${r.id}
            title=${say(out ? `${r.name}: it stands in the camp` : `${r.name}: drag it onto the camp`)}
            onPointerDown=${out ? null : (e) => start(e, { item: r.id, size: r.size, sprite: r.sprite })}>
          <span class="gui-items__pic"><img src=${DS + r.sprite} alt="" draggable="false" /></span>
          <span class="gui-items__words"><span class="gui-items__name">${say(r.name)}</span>
            <span class="ok-font-status ok-tone-muted">${say(out ? `${r.why} · in the camp` : r.why)}</span></span>
        </li>`;
      })}</ul>
    </section>`}
  </div>`;
}
