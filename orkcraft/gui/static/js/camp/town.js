// Camp's town in v3 (docs/design/design-system-v3.md): the buildings on their rows, a line of track under each, the
// loop, the low palisade with the lookout at the way in and the catapult at the buffer stop, drawn from the v3 sprites
// at their own art pixel times their layer's zoom (js/camp/layout.js lays it out). The wheel steps the zoom
// (×1 · ×1.5 · ×2 on density 2), a drag pans, the default view is centred on the work. Office draws the same town as
// cards (js/town.js): one town, two drawings, the same words.
import { signal } from "@preact/signals";
import { useLayoutEffect, useRef, useState, useEffect } from "preact/hooks";
import { html, cls } from "../html.js";
import { command, say, town as snapshot } from "../link.js";
import { closeBuilding, letGo, panelShown, panelWidth, opened, selected, pickBuilding, grownCard } from "../windows.js";
import { buildingMenu, brokenOf, Card } from "../hut.js";
import { busy as busyOf } from "../fold.js";
import { openOrders } from "../orders.js";
import { placing, constructing, raised } from "../build.js";
import { zoomLevel, zoomBy, LEVELS } from "../zoom.js";
import { bareMenu, setNumbered } from "../town.js";
import { lay, stepsFor, DEFAULT_STEP, SIDING_SHOWN } from "./layout.js";
import { V3, kit, loadKit, sizeOf } from "./sprites.js";
import { CampCarts, arriving } from "./carts.js";
import { hovered, StewardOut } from "./steward.js";
import { Stewards } from "./orks.js";
import { Badge } from "./signals.js";
import { typeModule } from "../types.js";
import { showConsole } from "../orkconsole.js";
import { Waybill, waybillOf } from "./waybill.js";

/** The ork a click on a building's steward means: the one stopped or asking, else at work, else its first; its
 *  console's key (core/slots.py rows: a roster ork's ref, a pool's `<building>/<name>`). */
function orkKey(b) {
  if (b.signal && b.signal.key) return b.signal.key;
  const g = b.garrison || [];
  const o = g.find((x) => x.status === "asking") || g.find((x) => x.status === "busy") || g[0];
  if (o) return o.ref || `${b.id}/${String(o.name).toLowerCase()}`;
  return `${b.id}/${String(b.ork_name || "steward").toLowerCase()}`;
}
const onOrk = (b) => showConsole(orkKey(b), true);          // its terminal, at the town's foot
const onBubble = (b) => { waybillOf.value = { building: b.id }; };   // the task's history

const pan = signal({ x: 0, y: 0 });        // the drag's offset from the default view, CSS px
let panned = false;                        // the last press dragged the town: its click selects nothing
const DRAG_PX = 5;

/** The zoom step the town's level asks for: the map the overview, the default, close up the last. */
function stepOf(steps) {
  const i = LEVELS.indexOf(zoomLevel.value);
  return steps[i <= 0 ? 0 : i === 1 ? Math.min(DEFAULT_STEP, steps.length - 1) : steps.length - 1];
}

const img = (file, x, y, w, h, extra = "", cl = "gui-camp__px") =>
  html`<img class=${cl} src=${V3 + file} alt="" draggable="false" style=${`left:${x}px;top:${y}px;width:${w}px;height:${h}px;${extra}`} />`;

/** A sprite repeated over a box (the earth, a palisade's run), at its art size times `k`. */
function tiled(file, x, y, w, h, k, repeat = "repeat") {
  const s = sizeOf(file);
  if (!s) return null;
  return html`<div class="gui-camp__px" style=${`left:${x}px;top:${y}px;width:${w}px;height:${h}px;`
    + `background:url(${V3 + file}) 0 0 / ${s[0] * k}px ${s[1] * k}px ${repeat}`}></div>`;
}

/** The ground: grass is the token itself; tufts and flowers scattered (a fixed seed: every shot the same). */
function Decals({ L }) {
  const B = L.step.b, out = [];
  let t = 7;
  const r = () => ((t = (t * 1103515245 + 12345) % 2147483648) / 2147483648);
  for (let k = 0; k < Math.round((L.w * L.h) / (70000 * B * B)); k++) {
    const n = r() < 0.6 ? "ground/tufts.png" : "ground/flowers.png", s = sizeOf(n);
    if (s) out.push(img(n, Math.round(r() * L.w), Math.round(r() * L.h), s[0] * B, s[1] * B));
  }
  for (const d of L.decor) {
    const f = `decor/${d.name}.png`, s = sizeOf(f);
    if (s) out.push(img(f, d.x - (s[0] * B) / 2, d.y - s[1] * B, s[0] * B, s[1] * B));
  }
  return html`<div class="gui-camp__layer is-ground">${out}</div>`;
}

/** The dirt paths from the doors to the stops: earth with the grass's rim down both sides. */
function Paths({ L }) {
  const B = L.step.b;
  return html`<div class="gui-camp__layer is-paths">${L.paths.map((p) => {
    const rw = sizeOf("ground/rim-w.png"), re = sizeOf("ground/rim-e.png");
    return html`${tiled("ground/earth.png", p.x, p.y, p.w, p.h, B) || html`<div class="gui-camp__earth" style=${`left:${p.x}px;top:${p.y}px;width:${p.w}px;height:${p.h}px`}></div>`}
      ${rw && tiled("ground/rim-w.png", p.x - (rw[0] - 2) * B, p.y, rw[0] * B, p.h, B, "repeat-y")}
      ${re && tiled("ground/rim-e.png", p.x + p.w - 2 * B, p.y, re[0] * B, p.h, B, "repeat-y")}`;
  })}</div>`;
}

function Track({ L }) {
  const T = L.T;
  return html`<div class="gui-camp__layer is-track">${L.tiles.map((t) => sizeOf(`track/${t.name}.png`)
    ? img(`track/${t.name}.png`, t.x, t.y, T, T, t.rot ? `transform:rotate(${t.rot}deg)` : "")
    : html`<div class=${cls("gui-camp__rails", { "is-v": t.name === "straight-v" })} style=${`left:${t.x}px;top:${t.y}px;width:${T}px;height:${T}px`}></div>`)}</div>`;
}

/** The low palisade of rounded logs: along the back (open where the track comes in under the lookout), down the right
 *  edge to below the last line (§4.6). */
function Palisade({ L }) {
  const B = L.step.b, w = L.wall, out = [];
  const h = (sizeOf("edge/palisade-h.png") || [80, 48])[1] * B;
  const run = (x0, x1) => {
    if (x1 <= x0) return;
    out.push(tiled("edge/palisade-h.png", x0, w.y - h, x1 - x0, h, B, "repeat-x")
      || html`<div class="gui-camp__logs" style=${`left:${x0}px;top:${w.y - 32 * B}px;width:${x1 - x0}px;height:${32 * B}px`}></div>`);
    for (const [n, x] of [["edge/palisade-end-w.png", x0], ["edge/palisade-end-e.png", x1]]) {
      const s = sizeOf(n);
      if (s) out.push(img(n, n.endsWith("-w.png") ? x - (s[0] * B) / 2 : x - (s[0] * B) / 2, w.y - s[1] * B, s[0] * B, s[1] * B));
    }
  };
  run(w.left, w.gap[0]);
  run(w.gap[1], w.x);
  const v = sizeOf("edge/palisade-v.png"), post = sizeOf("edge/palisade-post.png");
  if (v) {
    const vw = v[0] * B, vh = v[1] * B, step = (v[1] - 10) * B;
    for (let y = w.y - 7 * B; y < w.bottom - 12 * B; y += step) {
      out.push(img("edge/palisade-v.png", w.x - vw / 2, y, vw, Math.min(vh, w.bottom - y), "object-fit:cover;object-position:top"));
    }
    if (post) out.push(img("edge/palisade-post.png", w.x - (post[0] * B) / 2, w.bottom - post[1] * B, post[0] * B, post[1] * B));
  }
  return html`<div class="gui-camp__layer is-wall">${out}</div>`;
}

/** One building: its v3 sprite (a block in v3's colours until its sheet is cut), its name under its foot. */
function Building({ b, at, number, raising }) {
  const L = at.L, p = at.p, B = L.step.b;
  const broken = brokenOf(b), busy = busyOf(b);
  const click = (e) => {
    e.stopPropagation();
    if (panned) return;
    if (b.alert) openOrders(b.alert.id);       // a question: a press opens it at once
    else pickBuilding(b.id);                    // selected; the selected one again: entered
  };
  const body = p.file ? img(p.file, 0, 0, p.w, p.h, "", "gui-camp__px gui-camp__sprite")
    : html`<div class="gui-camp__block" style=${`width:${p.w}px;height:${p.h}px`}><span class="gui-camp__block-door"></span></div>`;
  const signal = broken ? "fire" : b.signal ? (b.signal.kind === "held" ? "held" : "fire") : "";
  const el = html`<div class=${cls("gui-camp__building", { "is-selected": selected.value === b.id, "is-busy": busy, "is-alert": !!b.alert,
                                                            "is-broken": !!broken, "is-paused": !!b.paused, "is-raising": raising })}
      data-id=${b.id} data-type=${b.type} style=${`left:${p.x}px;top:${p.y}px;width:${p.w}px;height:${p.h}px;z-index:${10 + Math.round(p.feet / 8)}`}
      role="button" tabindex="0" aria-label=${say(b.title)} title=${number <= 9 ? say(`${b.title} · press ${number} to select it`) : say(b.title)}
      onClick=${click} onContextMenu=${(e) => buildingMenu(e, b)}
      onPointerEnter=${(e) => { if (e.pointerType === "mouse" && !raising) hovered.value = b.id; }}
      onPointerLeave=${() => { if (hovered.value === b.id) hovered.value = null; }}
      onKeyDown=${(e) => { if (e.key === "Enter") click(e); }}>
    ${body}
    <span class="gui-camp__name is-name" style=${`left:${p.w / 2}px;top:${p.wall === "in" ? p.h - 40 * B : p.h - (p.spur ? 64 : 4) * B}px`}>${say(b.title)}</span>
  </div>`;
  const sig = (signal || b.alert) && html`<${Badge} kind=${b.alert ? "ask" : signal} x=${p.cx} y=${p.y + 4 * B}
    title=${b.alert ? say(`${b.title} asks: ${b.alert.title}`) : say(`${b.title}: ${broken || (b.signal && b.signal.line) || ""}`)}
    onClick=${b.alert ? () => openOrders(b.alert.id) : null} />`;
  return raising ? html`<div class="gui-town__raising" aria-label=${say(`${b.title}: being built`)}>${el}</div>` : html`${el}${sig}`;
}

/** The Task board's siding: the carts waiting to go (its to-do lane), at most five and "+N" for the rest. */
function Siding({ L, buildings }) {
  const B = L.step.b;
  return html`${L.sidings.map((s) => {
    const b = buildings.find((x) => x.id === s.id), c = b && b.card;
    const lane = c && (c.lanes || []).find((l) => l.id === c.todo_lane);
    const n = lane ? lane.count : 0, shown = Math.min(n, SIDING_SHOWN), cart = sizeOf("carts/doc.png") || [40, 48];
    return html`<div key=${s.id} class="gui-camp__siding" data-id=${s.id}>
      ${Array.from({ length: shown }, (_, k) => img("carts/doc.png", s.stand.x + k * s.stand.dx * 0.66 - (cart[0] * B) / 2,
        s.stand.y - cart[1] * B, cart[0] * B, cart[1] * B))}
      ${n > shown && html`<span class="gui-camp__chip" style=${`left:${s.stand.x + shown * s.stand.dx * 0.66}px;top:${s.stand.y - 20 * B}px`}>+${n - shown}</span>`}
    </div>`;
  })}`;
}

/** A building's card at its large size, beside it: the second click enters a type with no Work window (A5's large
 *  card, lighter-buildings.md §2) until its inside is drawn (I2). */
function GrownCard({ b, p, L }) {
  const x = Math.min(p.x + p.w + 16, L.w - 480), y = Math.max(p.y, 8);
  return html`<div class="ok-hut gui-camp__card l" data-id=${b.id} style=${`left:${x}px;top:${y}px`}
      onClick=${(e) => e.stopPropagation()} onContextMenu=${(e) => buildingMenu(e, b)}>
    <div class="ok-hut__card"><span class="ok-hut__label gui-hut__title"><span class="gui-hut__name">${say(b.title)}</span></span>
      <${Card} b=${b} level="l" /></div>
  </div>`;
}

/** Build's second half in Camp: the building takes its place in the rows, so a press anywhere on the camp builds it. */
function Placing({ p }) {
  useEffect(() => {
    const key = (e) => { if (e.key === "Escape") { e.preventDefault(); placing.value = null; } };
    window.addEventListener("keydown", key);
    return () => window.removeEventListener("keydown", key);
  }, []);
  const put = (e) => {
    e.stopPropagation();
    const { type } = p;
    placing.value = null;
    command("town.build", { type, hut: [0.5, 0.5] }).then((id) => raised(id, type), () => {});
  };
  return html`<div class="gui-town__placing gui-camp__placing" role="application"
      aria-label=${say(`Place ${p.title}: press on the camp to build it, Escape to cancel`)}
      onClick=${put} onContextMenu=${(e) => { e.preventDefault(); e.stopPropagation(); placing.value = null; }}>
    <p class="gui-town__placing-hint ok-font-status">${say(`Build ${p.title}: press on the camp · it takes its place on the line · Esc cancels`)}</p>
  </div>`;
}

let laid = { key: "", L: null };

export function CampTown({ buildings, roads }) {
  loadKit();
  const ref = useRef(null);
  const [view, setView] = useState({ w: 1440, h: 860 });
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return undefined;
    const measure = () => setView((v) => (v.w === el.clientWidth && v.h === el.clientHeight ? v : { w: el.clientWidth, h: el.clientHeight }));
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  const k = kit.value;
  const steps = stepsFor(window.devicePixelRatio || 1), step = stepOf(steps);
  const shown = new Set(buildings.map((b) => b.id));
  const here = roads.filter((r) => shown.has(r.from) && shown.has(r.to));
  setNumbered(buildings.map((b) => b.id));
  for (const b of buildings) typeModule(b.type, b.page);   // each type's page code (its large card, its small windows)
  const key = JSON.stringify([!!k, step, buildings.map((b) => [b.id, b.type, b.hut, b.type === "loot" && !!b.alert]), here.map((r) => [r.from, r.to])]);
  if (k && key !== laid.key) laid = { key, L: lay(buildings, here, step, sizeOf, (b) => !!b.alert) };
  const L = k ? laid.L : null;
  const panelW = panelShown() && !opened.value.full ? panelWidth.value : 0;

  // the default view: the work in the middle of the part of the window the panel leaves; then the drag's offset
  const seen = Math.max(view.w - panelW, 320);
  const ox = L ? Math.round(seen / 2 - (L.work.x + L.work.w / 2) + pan.value.x) : 0;
  const oy = L ? Math.round(view.h / 2 - (L.work.y + L.work.h / 2) + pan.value.y) : 0;

  const down = (e) => {
    if (e.button !== 0 || placing.value) return;
    const start = { x: e.clientX, y: e.clientY, pan: pan.value };
    panned = false;
    const move = (ev) => {
      const dx = ev.clientX - start.x, dy = ev.clientY - start.y;
      if (!panned && Math.hypot(dx, dy) < DRAG_PX) return;
      panned = true;
      pan.value = { x: start.pan.x + dx, y: start.pan.y + dy };
    };
    const up = () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
      setTimeout(() => { panned = false; }, 0);
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
  };
  // the wheel (and a pinch, which a trackpad sends as the wheel with Ctrl) steps the zoom, one step a gesture
  const wheel = (e) => {
    e.preventDefault();
    const now = Date.now();
    if (now - (wheel.at || 0) < 250) return;
    wheel.at = now;
    const before = zoomLevel.value;
    zoomBy(e.deltaY < 0 ? 1 : -1);
    if (zoomLevel.value !== before) pan.value = { x: 0, y: 0 };
  };
  const bare = (e) => { if (!panned && !e.target.closest(".gui-camp__building, .gui-camp__card")) { closeBuilding(); letGo(); } };
  const going = constructing.value;
  const carts = (snapshot.value && snapshot.value.carts) || [], travel = (snapshot.value && snapshot.value.travel) || 0;
  // the steward out of its door: the selected building's (its scroll grown), else the one under the mouse
  const outId = L && [selected.value, hovered.value].find((id) => id && L.buildings[id] && going[id] === undefined && buildings.some((b) => b.id === id));
  const outB = outId && buildings.find((b) => b.id === outId);
  const grown = grownCard.value && buildings.find((b) => b.id === grownCard.value);
  return html`<main ref=${ref} class=${cls("gui-town gui-camp", { "is-panning": panned })} data-step=${L ? `${step.b}/${step.s}` : ""}
      onPointerDown=${down} onWheel=${wheel} onClick=${bare} onContextMenu=${(e) => { if (!e.target.closest(".gui-camp__building")) bareMenu(e, buildings, here, null); }}>
    ${L && html`<div class="gui-camp__world" style=${`width:${L.w}px;height:${L.h}px;transform:translate(${ox}px,${oy}px)`}>
      <${Decals} L=${L} />
      <${Paths} L=${L} />
      <${Track} L=${L} />
      <${Palisade} L=${L} />
      <div class="gui-camp__layer is-buildings">
        ${buildings.map((b, i) => L.buildings[b.id] && html`<${Building} key=${b.id} b=${b} at=${{ L, p: L.buildings[b.id] }} number=${i + 1}
          raising=${going[b.id] !== undefined} />`)}
      </div>
      <${Siding} L=${L} buildings=${buildings} />
      <${CampCarts} L=${L} roads=${here} carts=${carts} travel=${travel} />
      <${Stewards} L=${L} buildings=${buildings} roads=${here} out=${outId} soon=${arriving(L, here, carts, travel)}
        onOrk=${onOrk} onBubble=${onBubble} />
      ${outB && html`<${StewardOut} b=${outB} p=${L.buildings[outB.id]} L=${L} grown=${selected.value === outB.id} onOrk=${onOrk} onBubble=${onBubble}
        seen=${{ left: -ox, top: -oy + 8, right: -ox + seen }} />`}
      ${grown && L.buildings[grown.id] && html`<${GrownCard} b=${grown} p=${L.buildings[grown.id]} L=${L} />`}
    </div>`}
    <${Waybill} />
    ${placing.value && html`<${Placing} p=${placing.value} />`}
    ${!buildings.length && html`<p class="gui-empty ok-font-body ok-tone-muted">${say("No buildings in this orkspace yet.")}</p>`}
  </main>`;
}
