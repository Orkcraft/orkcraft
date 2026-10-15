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
import { lay, stepsFor, DEFAULT_STEP, SIDING_SHOWN, PATH_W } from "./layout.js";
import { V3, kit, loadKit, sizeOf } from "./sprites.js";
import { CampCarts, Finale, Switches, arriving } from "./carts.js";
import { hovered, StewardOut } from "./steward.js";
import { Stewards } from "./orks.js";
import { Badge } from "./signals.js";
import { typeModule } from "../types.js";
import { showConsole } from "../orkconsole.js";
import { Waybill, waybillOf } from "./waybill.js";
import { StewardConsole, stewardOf, openStewardConsole } from "./stewardconsole.js";
import { portraitOpen } from "../portrait.js";
import { coverTop } from "../inset.js";
import { settingsOpen } from "../settings.js";
import { openMenu } from "../menu.js";
import { Placed, Inventory } from "./items.js";

/** The ork a click on a building's steward means: the one stopped or asking, else at work, else its first; its
 *  console's key (core/slots.py rows: a roster ork's ref, a pool's `<building>/<name>`); null with none to show. */
function orkKey(b) {
  if (b.signal && b.signal.key) return b.signal.key;
  const g = b.garrison || [];
  // an ork asking or at work has a session to show; an Agent pool's keeps its runs (core/workers/barracks_console.py)
  const o = g.find((x) => x.status === "asking") || g.find((x) => x.status === "busy") || (b.type === "barracks" ? g[0] : null);
  return o ? o.ref || `${b.id}/${String(o.name).toLowerCase()}` : null;
}
/** The town's average wood per accepted result: this week's, else last week's; null when none was recorded. */
const averagePerResult = (s) => (!s ? null : s.tokens !== null && s.tokens !== undefined ? s.tokens
  : s.before && s.before.tokens !== null && s.before.tokens !== undefined ? s.before.tokens : null);
// its terminal at the town's foot; a building with no ork of its own: its steward's console (js/camp/stewardconsole.js)
const onOrk = (b) => { const key = orkKey(b); if (key) { stewardOf.value = null; showConsole(key, true); } else openStewardConsole(b.id); };
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

/** The dirt paths from the doors to the stops, and from a service down to its readers (§4c): earth with the grass's
 *  rim down both sides (and along the top and the foot of a run across). All the rims first, then all the earth over
 *  them, so where two runs join no rim cuts the join. */
function Paths({ L }) {
  const B = L.step.b;
  const rw = sizeOf("ground/rim-w.png"), re = sizeOf("ground/rim-e.png"), rn = sizeOf("ground/rim-n.png"), rs = sizeOf("ground/rim-s.png");
  const across = (p) => p.service && p.w > p.h;
  const rims = L.paths.map((p) => html`${rw && tiled("ground/rim-w.png", p.x - (rw[0] - 2) * B, p.y, rw[0] * B, p.h, B, "repeat-y")}
    ${re && tiled("ground/rim-e.png", p.x + p.w - 2 * B, p.y, re[0] * B, p.h, B, "repeat-y")}
    ${across(p) && rn && tiled("ground/rim-n.png", p.x, p.y - (rn[1] - 2) * B, p.w, rn[1] * B, B, "repeat-x")}
    ${across(p) && rs && tiled("ground/rim-s.png", p.x, p.y + p.h - 2 * B, p.w, rs[1] * B, B, "repeat-x")}`);
  const earth = L.paths.map((p) => tiled("ground/earth.png", p.x, p.y, p.w, p.h, B)
    || html`<div class="gui-camp__earth" style=${`left:${p.x}px;top:${p.y}px;width:${p.w}px;height:${p.h}px`}></div>`);
  return html`<div class="gui-camp__layer is-paths">${rims}${earth}</div>`;
}

function Track({ L }) {
  const T = L.T;
  return html`<div class="gui-camp__layer is-track">${L.tiles.map((t) => sizeOf(`track/${t.name}.png`)
    ? img(`track/${t.name}.png`, t.x, t.y, T, T, t.rot ? `transform:rotate(${t.rot}deg)` : "")
    : html`<div class=${cls("gui-camp__rails", { "is-v": t.name === "straight-v" })} style=${`left:${t.x}px;top:${t.y}px;width:${T}px;height:${T}px`}></div>`)}
    ${(L.crossings || []).map((c) => (sizeOf("track/crossing.png") ? img("track/crossing.png", c.x, c.y, c.w, c.h)
      : html`<div class="gui-camp__crossing" style=${`left:${c.x}px;top:${c.y}px;width:${c.w}px;height:${c.h}px`}></div>`))}</div>`;
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

/** Where a building's name stands, clear of its door and its steward: on the facade's top in the upper row (and the
 *  wall's two), under its foot left of its path in a lower row. In the building's own box. */
function nameAt(p, B) {
  if (p.wall || p.back || p.row === 0) return { cl: "is-top", style: `left:${p.w / 2}px;top:${Math.round(p.h * 0.14)}px` };
  return { cl: "is-under", style: `left:${p.cx - p.x - (PATH_W / 2 + 4) * B}px;top:${p.h + 6 * B}px` };
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
    <span class=${cls("gui-camp__name is-name", nameAt(p, B).cl)} style=${nameAt(p, B).style}>${say(b.title)}</span>
  </div>`;
  const sig = (signal || b.alert) && html`<${Badge} kind=${b.alert ? "ask" : signal} x=${p.cx} y=${p.y + 4 * B}
    title=${b.alert ? say(`${b.title} asks: ${b.alert.title}`) : say(`${b.title}: ${broken || (b.signal && b.signal.line) || ""}`)}
    onClick=${b.alert ? () => openOrders(b.alert.id) : null} />`;
  return raising ? html`<div class="gui-town__raising" aria-label=${say(`${b.title}: being built`)}>${el}</div>` : html`${el}${sig}`;
}

/** Growth on a building (growth.md §5, v3-prompts §13.4): its level I–III as a stone footing by the door and a banner
 *  on its roof, the banner gaining a crest at III (no gold: yellow is the question's); a goal's annex against its east
 *  wall (the Thrift lean-to, the Quality crystal). Nothing before its first level but the annex. */
function Growth({ L, buildings }) {
  const B = L.step.b, out = [];
  for (const b of buildings) {
    const p = L.buildings[b.id], g = p && p.growth;
    if (!g || p.wall) continue;
    const put = (file, x, feet, left = false, label = "", under = false) => {
      const s = sizeOf(file);
      if (!s) return;
      const w = s[0] * B, h = s[1] * B;
      out.push(html`<img class="gui-camp__px gui-camp__growth" src=${V3 + file} alt=${label} title=${label} draggable="false"
        data-id=${b.id} style=${`left:${left ? x : x - w / 2}px;top:${feet - h}px;width:${w}px;height:${h}px;z-index:${(under ? 9 : 11) + Math.round(p.feet / 8)}`} />`);
    };
    const level = ["", "I", "II", "III"][g.level];
    if (g.level) {
      put(`growth/footing-${g.level}.png`, p.x + 2 * B, p.feet + 3 * B, true, say(`Renown ${level}`), true);   // under its name
      put(`growth/banner-${g.level}.png`, p.x + p.w * 0.78, p.y + p.h * 0.32, false, say(`Renown ${level}`));
    }
    if (g.annex) put(g.annex, p.x + p.w + 1 * B, p.feet, true, say(b.goal === "thrift" ? "Goal: Thrift" : "Goal: Quality"));
  }
  return html`<div class="gui-camp__layer is-growth">${out}</div>`;
}

/** The person's home beside the Review gate (design-system-v3.md §4.13, v3-prompts §13): their kin's house, its name
 *  on it as a building's and its path down to the line (laid with the others, layout.js); a click
 *  opens what is the person's own — since your last look, their profile and deeds, the town's settings. */
function Home({ L, you }) {
  const h = L.home;
  if (!h) return null;
  const open = (e) => {
    e.stopPropagation();
    if (panned) return;
    openMenu(e, [
      { label: "Since your last look", run: () => command("look.show").catch(() => {}) },
      { label: "You: profile and deeds", run: () => { portraitOpen.value = true; } },
      { label: "Town settings…", run: () => { settingsOpen.value = true; } },
    ]);
  };
  return html`<div class="gui-camp__home" data-kin=${you.kin} style=${`left:${h.x}px;top:${h.y}px;width:${h.w}px;height:${h.h}px;z-index:${10 + Math.round(h.feet / 8)}`}
      role="button" tabindex="0" aria-label=${say("Your home")} title=${say(`Your home · ${you.name}`)}
      onClick=${open} onContextMenu=${open} onKeyDown=${(e) => { if (e.key === "Enter") open(e); }}>
    ${img(h.file, 0, 0, h.w, h.h, "", "gui-camp__px gui-camp__sprite")}
    <span class="gui-camp__name is-name is-top" style=${`left:${h.w / 2}px;top:${Math.round(h.h * 0.14)}px`}>${say("Home")}</span>
  </div>`;
}

/** The Task board's siding: the carts waiting to go (its To Do lane: the orks' backlog, not the person's own
 *  to-dos), at most five and "+N" for the rest. */
function Siding({ L, buildings }) {
  const B = L.step.b;
  return html`${L.sidings.map((s) => {
    const b = buildings.find((x) => x.id === s.id), c = b && b.card;
    const lanes = (c && c.lanes) || [], lane = lanes.find((l) => l.id === "todo") || lanes[0];
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

/** The rows a new building may join, as bands over the camp: each row standing, and a bottom row below a camp of
 *  one row. A row's band runs from over its buildings to its line. World px. */
export function rowBands(L) {
  const B = L.step.b, T = L.T, n = Math.max(L.lines.length, 2), out = [];
  for (let r = 0; r < n; r++) {
    const top = r === 0 ? L.wall.y - 24 * B : L.lines[r - 1] + T;
    const bottom = r < L.lines.length ? L.lines[r] + T : top + 200 * B;
    out.push({ r, n, x: L.cols.left, y: top, w: L.work.w, h: bottom - top,
               word: r === 0 ? "Top row" : r === n - 1 ? "Bottom row" : `Row ${r + 1}` });
  }
  return out;
}

/** Build's second half in Camp: the building joins the row the person presses, in its next free slot — the row's end
 *  (decisions §14: Camp's rows follow the Office positions, so it takes a spot at that row's right in Office). No
 *  free placement in Camp; Escape or a right click lets it go. */
function Placing({ p, L }) {
  useEffect(() => {
    const key = (e) => { if (e.key === "Escape") { e.preventDefault(); placing.value = null; } };
    window.addEventListener("keydown", key);
    return () => window.removeEventListener("keydown", key);
  }, []);
  const put = (e, band) => {
    e.stopPropagation();
    const { type } = p;
    placing.value = null;
    command("town.build", { type, hut: [0.999, (band.r + 0.5) / band.n] }).then((id) => raised(id, type), () => {});
  };
  const cancel = (e) => { e.preventDefault(); e.stopPropagation(); placing.value = null; };
  return html`<div class="gui-camp__placing" role="group" aria-label=${say(`Build ${p.title}: pick its row`)}
      onClick=${(e) => e.stopPropagation()} onContextMenu=${cancel}>
    ${rowBands(L).map((band) => html`<button key=${band.r} type="button" class="gui-camp__band"
        style=${`left:${band.x}px;top:${band.y}px;width:${band.w}px;height:${band.h}px`}
        aria-label=${say(`Build ${p.title} at the end of the ${band.word.toLowerCase()}`)} onClick=${(e) => put(e, band)}>
      <span class="gui-camp__chip">${say(band.word)}</span></button>`)}
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
  const you = snapshot.value && snapshot.value.growth && snapshot.value.growth.you;
  const home = you && you.kin ? `homes/${you.kin}.png` : "";
  const key = JSON.stringify([!!k, step, home, buildings.map((b) => [b.id, b.type, b.hut, b.goal, b.level, b.type === "loot" && !!b.alert]), here.map((r) => [r.from, r.to])]);
  if (k && key !== laid.key) laid = { key, L: lay(buildings, here, step, sizeOf, (b) => !!b.alert, home) };
  const L = k ? laid.L : null;
  const panelW = panelShown() && !opened.value.full ? panelWidth.value : 0;

  // the default view: the work in the middle of the part of the window the panel and the quest log leave (js/inset.js:
  // the camp's bottom inset is the quest log's height); then the drag's offset. Mission 1 (js/mission.js): the view
  // follows the drill at the Review gate's barrier, then from the gate to where it leaves (the finale, js/camp/carts.js)
  const m = snapshot.value && snapshot.value.mission, finale = m && m.finale;
  const fg = L && finale && L.buildings[finale.gate], fo = fg && (L.buildings[finale.out] ? L.buildings[finale.out].stop : L.buffer);
  const lift = L && !fg && m && m.quest === "gate" && m.press && L.buildings[m.built];
  const focus = fg ? { x: (fg.cx + fo.x) / 2, y: (fg.y + fo.y) / 2 } : lift ? { x: lift.cx, y: lift.y + lift.h / 2 } : null;
  const seen = Math.max(view.w - panelW, 320);
  const box = ref.current && coverTop.value !== null ? ref.current.getBoundingClientRect() : null;
  const tall = Math.max(view.h - (box ? Math.max(0, box.bottom - coverTop.value) : 0), 240);
  const ox = !L ? 0 : Math.round(seen / 2 - (focus ? focus.x : L.work.x + L.work.w / 2) + pan.value.x);
  // covered, a camp taller than what is left shows its last line (where the carts run) above the panel, the wall's top cut
  const low = !L || focus || !box || L.work.h <= tall ? null : L.work.y + L.work.h - tall + 8;
  const oy = !L ? 0 : Math.round((low !== null ? -low : tall / 2 - (focus ? focus.y : L.work.y + L.work.h / 2)) + pan.value.y);

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
  const bare = (e) => {
    if (!panned && !e.target.closest(".gui-camp__building, .gui-camp__card, .gui-camp__home")) { closeBuilding(); letGo(); }
  };
  const going = constructing.value;
  const carts = (snapshot.value && snapshot.value.carts) || [], travel = (snapshot.value && snapshot.value.travel) || 0;
  // the steward out of its door: the selected building's (its scroll grown), else the one under the mouse
  const outId = L && [selected.value, hovered.value].find((id) => id && L.buildings[id] && going[id] === undefined && buildings.some((b) => b.id === id));
  const outB = outId && buildings.find((b) => b.id === outId);
  const grown = grownCard.value && buildings.find((b) => b.id === grownCard.value);
  return html`<main ref=${ref} class=${cls("gui-town gui-camp", { "is-panning": panned, "is-overview": zoomLevel.value === "a" })} data-step=${L ? `${step.b}/${step.s}` : ""}
      onPointerDown=${down} onWheel=${wheel} onClick=${bare} onContextMenu=${(e) => { if (!e.target.closest(".gui-camp__building")) bareMenu(e, buildings, here, null); }}>
    ${L && html`<div class=${cls("gui-camp__world", { "is-following": !!focus })} style=${`width:${L.w}px;height:${L.h}px;transform:translate(${ox}px,${oy}px)`}>
      <${Decals} L=${L} />
      <${Paths} L=${L} />
      <${Track} L=${L} />
      <${Switches} L=${L} />
      <${Palisade} L=${L} />
      <${Placed} L=${L} items=${you && snapshot.value.growth.items} buildings=${buildings} />
      <div class="gui-camp__layer is-buildings">
        ${buildings.map((b, i) => L.buildings[b.id] && html`<${Building} key=${b.id} b=${b} at=${{ L, p: L.buildings[b.id] }} number=${i + 1}
          raising=${going[b.id] !== undefined} />`)}
        ${you && html`<${Home} L=${L} you=${you} />`}
      </div>
      <${Growth} L=${L} buildings=${buildings} />
      <${Siding} L=${L} buildings=${buildings} />
      <${CampCarts} L=${L} roads=${here} carts=${carts} travel=${travel} avg=${averagePerResult(snapshot.value && snapshot.value.score)} />
      <${Stewards} L=${L} buildings=${buildings} roads=${here} out=${outId} soon=${arriving(L, here, carts, travel)}
        onOrk=${onOrk} onBubble=${onBubble} />
      ${finale && html`<div class="gui-camp__layer is-carts"><${Finale} key=${finale.id} L=${L} f=${finale} /></div>`}
      ${outB && html`<${StewardOut} b=${outB} p=${L.buildings[outB.id]} L=${L} grown=${selected.value === outB.id} onOrk=${onOrk} onBubble=${onBubble}
        seen=${{ left: -ox, top: -oy + 8, right: -ox + seen }} />`}
      ${placing.value && html`<${Placing} p=${placing.value} L=${L} />`}
      ${grown && L.buildings[grown.id] && html`<${GrownCard} b=${grown} p=${L.buildings[grown.id]} L=${L} />`}
    </div>`}
    <${Waybill} />
    <${StewardConsole} />
    ${L && you && html`<${Inventory} items=${snapshot.value.growth.items} />`}
    ${placing.value && html`<p class="gui-town__placing-hint ok-font-status">${say(`Build ${placing.value.title}: press a row · it takes the row's next place on the line · Esc cancels`)}</p>`}
    ${!buildings.length && html`<p class="gui-empty ok-font-body ok-tone-muted">${say("No buildings in this orkspace yet.")}</p>`}
  </main>`;
}
