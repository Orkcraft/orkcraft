// The living camp on the phone, in v3 (docs/design/design-system-v3.md §3–§4, mobile.md §12): the desktop's own layout
// (camp/layout.js, the same module) — the buildings on rows, a line of track under each, the loop, the lookout in the
// wall at the way in and the catapult at the buffer stop — drawn from the v3 sprites at a whole number of device pixels
// an art pixel. A finger pans; two fingers pinch to the next zoom step (never between steps); the camera starts on what
// waits (the first building that asks, else the first in trouble), else on the work. A first tap on a building is the
// desktop's hover and click at once: its scroll over it, its status and quick actions; a second tap opens its card as a
// sheet. A tap on its steward opens the steward's console, on a cart the task's history — sheets from the foot.
//
// ❓, 🔥 and ⏳ are UI chips (24 px at least); the page's CSP takes no style attribute, so every place is set through the
// CSSOM. Carts roll by CSS alone, paused while the page is hidden.

import { h } from "./util.js";
import { lay, stepsFor, phoneStep, lengthOf } from "./camp/layout.js";

const V3 = "v3/";
const AT_WORK = new Set(["WORKING", "BUSY", "PENDING", "EDITING"]);
const TROUBLE = new Set(["ERROR", "NO WIKI"]);
const PINCH = 1.3;                        // two fingers this much apart (or together) step the zoom once
const DRAG_PX = 8;                        // a move shorter than this is still a tap

/** What a building signals on the camp: "asks" | "fire" | "work" | "". */
export function signalOf(b, asking) {
  if (b.alert || b.state === "ASKS" || asking.has(b.id)) return "asks";
  if (TROUBLE.has(b.state) || b.signal === "error") return "fire";
  if (AT_WORK.has(b.state)) return "work";
  return "";
}

let kit = null;                           // the v3 manifest: file → [w, h] of a frame, art px
let hds = {};                             // an ork's file → its high-density cuts, step → file (tools/camp_hd.py)
const sizeOf = (file) => (kit && kit[file]) || null;
/** An ork's file at zoom S: on a dense screen its cut at one image px per device px (`S × dpr / 2` its step). */
function orkFile(file, S) {
  const d = window.devicePixelRatio || 1, k = (S * d) / 2;
  const hd = d >= 2 && hds[file] && Object.entries(hds[file]).find(([step]) => Math.abs(Number(step) - k) < 1e-6);
  return hd ? { url: V3 + hd[1], hd: true } : { url: V3 + file, hd: false };
}
function loadKit(done) {
  if (kit) return done();
  fetch(`${V3}manifest.json`).then((r) => (r.ok ? r.json() : { sprites: [] })).catch(() => ({ sprites: [] })).then((m) => {
    kit = Object.fromEntries((m.sprites || []).map((s) => [s.file, s.frame || s.size]));
    hds = Object.fromEntries((m.sprites || []).filter((s) => s.hd).map((s) => [s.file, s.hd]));
    done();
  });
}

function put(el, x, y, w, hh) {
  el.style.left = `${Math.round(x)}px`;
  el.style.top = `${Math.round(y)}px`;
  if (w !== undefined) el.style.width = `${Math.round(w)}px`;
  if (hh !== undefined) el.style.height = `${Math.round(hh)}px`;
  return el;
}
function sprite(file, x, y, k, cls = "camp-px") {
  const s = sizeOf(file);
  if (!s) return null;
  const img = h("img", { class: cls, src: V3 + file, alt: "", draggable: "false" });
  return put(img, x, y, s[0] * k, s[1] * k);
}
function tiled(file, x, y, w, hh, k, repeat = "repeat") {
  const s = sizeOf(file);
  if (!s) return null;
  const d = put(h("div", { class: "camp-px" }), x, y, w, hh);
  d.style.backgroundImage = `url(${V3}${file})`;
  d.style.backgroundSize = `${s[0] * k}px ${s[1] * k}px`;
  d.style.backgroundRepeat = repeat;
  return d;
}
const roleOf = (name) => `orks/roles/${String(name || "").toLowerCase().replace(/[^a-z]/g, "")}.png`;

/** `ctx`: {open(b), name(b), quick(b), ork(b), cart(c)}. Returns {el, render(town, buildings, asking)}. */
export function makeCamp(ctx) {
  const world = h("div", { class: "camp-world" });
  const view = h("div", { class: "camp-view", tabindex: "-1" }, world);
  const scroll = h("div", { class: "camp-scrolls" });
  const el = h("section", { class: "camp", "aria-label": "The camp" }, view, scroll);
  const dpr = window.devicePixelRatio || 1, steps = stepsFor(dpr);
  let step = phoneStep(steps), pan = { x: 0, y: 0 }, focused = "", selected = "", last = null, L = null;

  // a finger pans; two pinch to the next step; a tap stays a tap
  const pointers = new Map();
  let start = null, pinch0 = 0, moved = false;
  view.addEventListener("pointerdown", (e) => {
    pointers.set(e.pointerId, { x: e.clientX, y: e.clientY });
    if (pointers.size === 1) { start = { x: e.clientX, y: e.clientY, pan: { ...pan } }; moved = false; }
    if (pointers.size === 2) { const [a, b] = [...pointers.values()]; pinch0 = Math.hypot(a.x - b.x, a.y - b.y); moved = true; }
  });
  view.addEventListener("pointermove", (e) => {
    if (!pointers.has(e.pointerId)) return;
    pointers.set(e.pointerId, { x: e.clientX, y: e.clientY });
    if (pointers.size === 1 && start) {
      const dx = e.clientX - start.x, dy = e.clientY - start.y;
      if (!moved && Math.hypot(dx, dy) < DRAG_PX) return;
      moved = true;
      pan = { x: start.pan.x + dx, y: start.pan.y + dy };
      place();
    }
  });
  const up = (e) => {
    if (pointers.size === 2 && pinch0) {
      const [a, b] = [...pointers.values()], d = Math.hypot(a.x - b.x, a.y - b.y);
      const next = d > pinch0 * PINCH ? step + 1 : d < pinch0 / PINCH ? step - 1 : step;
      pinch0 = 0;
      if (next !== step && next >= 0 && next < steps.length) { step = next; pan = { x: 0, y: 0 }; draw(); }
    }
    pointers.delete(e.pointerId);
    if (!pointers.size) setTimeout(() => { moved = false; }, 0);
  };
  view.addEventListener("pointerup", up);
  view.addEventListener("pointercancel", up);
  view.addEventListener("wheel", (e) => {          // a trackpad or a mouse: the same steps
    e.preventDefault();
    const next = step + (e.deltaY < 0 ? 1 : -1);
    if (next >= 0 && next < steps.length) { step = next; pan = { x: 0, y: 0 }; draw(); }
  }, { passive: false });
  document.addEventListener("visibilitychange", () => el.classList.toggle("is-hidden", document.visibilityState !== "visible"));

  let centre = { x: 0, y: 0 };
  function place() {
    const vw = view.clientWidth, vh = view.clientHeight;
    world.style.transform = `translate(${Math.round(vw / 2 - centre.x + pan.x)}px, ${Math.round(vh / 2 - centre.y + pan.y)}px)`;
  }

  function tapBuilding(b) {
    if (moved) return;
    if (selected === b.id) { selected = ""; ctx.open(b); draw(); return; }
    selected = b.id;
    draw();
  }

  function draw() {
    if (!last) return;
    const [s, buildings, asking] = last;
    const st = steps[step], B = st.b, S = st.s;
    const roads = (s.roads || []).map(([from, to]) => ({ id: `${from}>${to}`, from, to }));
    const ids = new Set(buildings.map((b) => b.id));
    const here = roads.filter((r) => ids.has(r.from) && ids.has(r.to));
    const rows = buildings.map((b) => ({ ...b, hut: b.spot }));
    L = lay(rows, here, st, sizeOf, (b) => signalOf(b, asking) === "asks");
    world.style.width = `${L.w}px`;
    world.style.height = `${L.h}px`;
    el.dataset.step = `${B}/${S}`;
    const out = [];
    // the ground: paths, track, the palisade
    for (const p of L.paths) out.push(tiled("ground/earth.png", p.x, p.y, p.w, p.h, B) || put(h("div", { class: "camp-earth" }), p.x, p.y, p.w, p.h));
    for (const t of L.tiles) {
      const img = sprite(`track/${t.name}.png`, t.x, t.y, S);
      if (img) { img.style.width = img.style.height = `${L.T}px`; if (t.rot) img.style.transform = `rotate(${t.rot}deg)`; out.push(img); }
    }
    const wall = L.wall, ph = (sizeOf("edge/palisade-h.png") || [80, 48])[1] * B;
    for (const [x0, x1] of [[wall.left, wall.gap[0]], [wall.gap[1], wall.x]]) {
      if (x1 > x0) out.push(tiled("edge/palisade-h.png", x0, wall.y - ph, x1 - x0, ph, B, "repeat-x") || put(h("div", { class: "camp-logs" }), x0, wall.y - ph, x1 - x0, ph));
    }
    const pv = sizeOf("edge/palisade-v.png");
    if (pv) out.push(tiled("edge/palisade-v.png", wall.x - (pv[0] * B) / 2, wall.y, pv[0] * B, wall.bottom - wall.y, B, "repeat-y"));
    // the buildings: a button each, its sprite at a whole number of device px, its name, its signal
    let target = null, working = null;
    for (const b of buildings) {
      const p = L.buildings[b.id];
      if (!p) continue;
      const sig = signalOf(b, asking), qs = asking.get(b.id) || [];
      const said = sig === "asks" ? ", asks you" : sig === "fire" ? ", in trouble" : sig === "work" ? ", at work" : "";
      const art = p.file ? sprite(p.file, 0, 0, B, "camp-px camp-sprite") : put(h("span", { class: "camp-block" }), 0, 0, p.w, p.h);
      const chip = sig === "asks" ? h("span", { class: "camp-sig asks", "aria-hidden": "true" }, qs.length > 1 ? `❓${qs.length}` : "❓")
        : sig === "fire" ? h("span", { class: "camp-sig fire", "aria-hidden": "true" }, "!") : null;
      const name = h("span", { class: `camp-name${p.wall || p.row === 0 ? " is-top" : " is-under"}` }, ctx.name(b));
      const hut = put(h("button", { class: `camp-hut${sig ? ` ${sig}` : ""}${selected === b.id ? " is-selected" : ""}`, type: "button",
        "data-b": b.id, "aria-label": `${ctx.name(b)}${said}` }, art, chip, name), p.x, p.y, p.w, p.h);
      hut.style.zIndex = String(10 + Math.round(p.feet / 8));
      hut.addEventListener("click", () => tapBuilding(b));
      out.push(hut);
      if ((sig === "asks" || sig === "fire") && (!target || (sig === "asks" && target.sig !== "asks"))) target = { id: b.id, sig, p };
      if (sig === "work" && !working) working = p;
      // its steward: at the stop waiting, at the door asking; inside (a bubble over the roof) while at work
      if (!p.wall && b.ork_name) {
        if (sig === "work") {
          const bubble = h("button", { class: "camp-bubble", type: "button", "aria-label": `${b.ork_name}: at work` }, "…");
          bubble.addEventListener("click", (e) => { e.stopPropagation(); ctx.ork(b); });
          out.push(put(bubble, p.cx, p.y + 6 * B));
        } else {
          const file = sig === "asks" && sizeOf("orks/states/asks.png") ? "orks/states/asks.png" : sizeOf(roleOf(b.ork_name)) ? roleOf(b.ork_name) : null;
          const sz = file && sizeOf(file);
          if (sz) {
            const fx = sig === "asks" ? p.door.x + 14 * B : p.cx + p.w * (p.spur ? 0.36 : 0) + (p.spur ? 0 : 16 * B + 14 * S);
            const fy = sig === "asks" ? p.feet + 2 * B : p.stop.y - L.T / 2 - 2 * S;
            const ork = h("button", { class: "camp-ork", type: "button", "aria-label": `${b.ork_name}: its console` });
            put(ork, fx - (sz[0] * S) / 2, fy - sz[1] * S, sz[0] * S, sz[1] * S);
            const f = orkFile(file, S);
            ork.style.backgroundImage = `url(${f.url})`;
            if (f.hd) ork.classList.add("is-hd");
            ork.style.backgroundSize = `${sz[0] * S}px ${sz[1] * S}px`;
            ork.style.zIndex = String(11 + Math.round(fy / 8));
            ork.addEventListener("click", (e) => { e.stopPropagation(); if (!moved) ctx.ork(b); });
            out.push(ork);
          }
        }
      }
    }
    // the Task board's siding: its To Do lane as carts, five and "+N"
    for (const sd of L.sidings) {
      const b = buildings.find((x) => x.id === sd.id), n = (b && b.todo) || 0, cs = sizeOf("carts/doc.png") || [40, 48];
      for (let k = 0; k < Math.min(n, 5); k++) out.push(sprite("carts/doc.png", sd.stand.x + k * sd.stand.dx * 0.66 - (cs[0] * B) / 2, sd.stand.y - cs[1] * B, B));
      if (n > 5) out.push(put(h("span", { class: "camp-chip" }, `+${n - 5}`), sd.stand.x + 5 * sd.stand.dx * 0.66, sd.stand.y - 20 * B));
    }
    out.push(...carts(s, B));
    world.replaceChildren(...out.filter(Boolean));
    const sel = selected && buildings.find((b) => b.id === selected);
    scroll.replaceChildren(...(sel ? [scrollOf(sel)] : []));
    // the camera: on what waits, else on a building at work, else on the work's start (the top row's first); it moves
    // again only when that changes
    const first = Object.values(L.buildings).filter((p) => p.row === 0).sort((a, c) => a.x - c.x)[0];
    const on = target ? target.p : working || first;
    const key = `${target ? `${target.sig}:${target.id}` : on ? `at:${on.id}` : "work"}@${step}`;
    if (key !== focused) {
      focused = key;
      pan = { x: 0, y: 0 };
      centre = on ? { x: on.cx, y: on.y + on.h / 2 } : { x: L.work.x + L.work.w / 2, y: L.work.y + L.work.h / 2 };
    }
    place();
    el.dataset.focus = target ? target.id : "";
  }

  // the scroll of a building tapped once, over the camp's top edge (a phone has no room over a roof): its name, its
  // status in a line or two, its quick actions, and Open
  function scrollOf(b) {
    const status = (b.status && b.status.length ? b.status : [signalOf(b, last[2]) === "asks" ? "Asks you" : "Quiet"]).slice(0, 2);
    const open = h("button", { class: "ok-btn primary", type: "button" }, "Open");
    open.addEventListener("click", (e) => { e.stopPropagation(); selected = ""; ctx.open(b); draw(); });
    const sc = h("div", { class: "camp-scroll", "data-b": b.id }, h("b", {}, ctx.name(b)),
      ...status.map((x) => h("p", {}, x)), h("div", { class: "row" }, ...ctx.quick(b), open));
    sc.addEventListener("click", (e) => e.stopPropagation());
    sc.addEventListener("pointerdown", (e) => e.stopPropagation());
    return sc;
  }

  // the carts: a rolling one along its route (CSS offset-path, from the moment it set off), a stopped one at its stop
  function carts(s, B) {
    const out = [], standing = new Map();
    for (const c of s.carts || []) {
      if (!L.buildings[c.from] || !L.buildings[c.to]) continue;
      if (c.stands) { (standing.get(c.to) || standing.set(c.to, []).get(c.to)).push(c); continue; }
      if (c.state === "back") continue;
      const pts = L.route(c.from, c.to);
      if (!pts || pts.length < 2) continue;
      const dur = Math.max(s.travel || 0, Math.min(Math.max(lengthOf(pts) / (140 * B), 2), 9));
      if (c.age > dur + 0.5) continue;
      const feet = L.T * 0.3, d = `M ${pts.map(([x, y]) => `${Math.round(x)} ${Math.round(y + feet)}`).join(" L ")}`;
      const cart = h("button", { class: "camp-cart is-rolling", type: "button", "data-c": c.id, "aria-label": `${c.title}: its history` },
        binOf(c, B));
      cart.style.offsetPath = `path("${d}")`;
      cart.style.animationDuration = `${dur}s`;
      cart.style.animationDelay = `${-c.age}s`;
      cart.addEventListener("click", (e) => { e.stopPropagation(); ctx.cart(c); });
      out.push(cart);
    }
    for (const [id, list] of standing) {
      const p = L.buildings[id], c = list[list.length - 1];
      const x = p.type === "loot" && p.spur ? p.cx : p.stop.x, y = p.type === "loot" && p.spur ? p.y + p.h * 0.69 : p.stop.y + L.T * 0.3;
      const cart = put(h("button", { class: `camp-cart is-${c.state}`, type: "button", "data-c": c.id, "aria-label": `${c.title}: its history` },
        binOf(c, B), c.state === "ask" ? h("span", { class: "camp-chip" }, [c.ref, c.title].filter(Boolean).join(" · ").slice(0, 26)) : null,
        list.length > 3 ? h("span", { class: "camp-chip" }, `×${list.length}`) : null), x, y);
      cart.addEventListener("click", (e) => { e.stopPropagation(); ctx.cart(c); });
      out.push(cart);
    }
    return out;
  }
  function binOf(c, B) {
    const load = ["code", "asset", "message", "doc", "bundle"].includes(c.load) ? c.load : "asset";
    const sz = sizeOf(`carts/${load}.png`) || [40, 48];
    return sprite(`carts/${load}.png`, -(sz[0] * B) / 2, -sz[1] * B, B);
  }

  function render(s, buildings, asking) {
    const vh = Math.round(Math.min(Math.max(window.innerHeight * 0.5, 280), 520));
    view.style.height = `${vh}px`;
    last = [s, buildings, asking];
    if (selected && !buildings.some((b) => b.id === selected)) selected = "";
    loadKit(draw);
  }

  return { el, render };
}
