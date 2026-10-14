// The living camp on the phone (docs/design/color-pass.md §6c; audience.md §2a): the orkspace's buildings where the
// person put them on the desktop (`spot`, fractions of the room), each its mark, the roads between them, and an ork
// walking by each building at work. The camp is laid out for a wide screen; on a tall one it is never squeezed: the
// art keeps its own size (1×, so a 2× or 3× screen scales it by whole numbers and it stays sharp) and a camp too
// big for the screen pans. The camera starts where the person is needed — the building with a ❓ or a 🔥 — and
// shows the whole camp, fitted, when nothing waits. A tap on a building opens its card as a sheet from the foot.
//
// ❓ and 🔥 are UI, not art: chips at least 24 px high on a building at least 44 px wide, whatever the art's scale.
// The orks walk at a low frame rate (TICK_MS), only while the page is shown and the person allows motion.

import { h } from "./util.js";
import { mark } from "./icons.js";

const CELL = { w: 96, h: 100 };          // a building's place: its mark (82×67 at 1×), its name, a road's gap
const ART = { w: 82, h: 67 };            // the header sprite at 1×
const PAD = 8;                            // between the camp's edge and the outermost buildings
const TICK_MS = 160;                      // the orks' frame: about six a second
const WALK = 36;                          // how far an ork walks to and fro beside its building, px
const FRAMES = 6;                         // walk-side.png: six frames of 32×48, its feet at the foot (camp/manifest.json)
const AT_WORK = new Set(["WORKING", "BUSY", "PENDING", "EDITING"]);
const TROUBLE = new Set(["ERROR", "NO WIKI"]);
const STILL = matchMedia("(prefers-reduced-motion: reduce)");
const SVG = "http://www.w3.org/2000/svg";

/** What a building signals on the camp: "asks" | "fire" | "work" | "". */
export function signalOf(b, asking) {
  if (b.alert || b.state === "ASKS" || asking.has(b.id)) return "asks";
  if (TROUBLE.has(b.state)) return "fire";
  if (AT_WORK.has(b.state)) return "work";
  return "";
}

/** Each building's cell: its spot snapped to the nearest free cell of a grid `cols`×`rows`, in the order given (a
 *  building with no spot takes the first free cell). Pure, so the tests can read it. */
export function place(buildings, cols, rows) {
  const taken = new Set();
  const out = new Map();
  const free = (c, r) => c >= 0 && r >= 0 && c < cols && r < rows && !taken.has(`${c},${r}`);
  const placed = [...buildings].sort((a, b) => Number(!a.spot) - Number(!b.spot));
  for (const b of placed) {
    const want = b.spot ? [Math.round(b.spot[0] * (cols - 1)), Math.round(b.spot[1] * (rows - 1))] : [0, 0];
    let best = null;
    for (let d = 0; d < cols + rows && !best; d += 1) {
      for (let dr = -d; dr <= d && !best; dr += 1) {
        for (let dc = -d; dc <= d && !best; dc += 1) {
          if (Math.max(Math.abs(dc), Math.abs(dr)) !== d) continue;
          if (free(want[0] + dc, want[1] + dr)) best = [want[0] + dc, want[1] + dr];
        }
      }
    }
    if (!best) continue;
    taken.add(`${best[0]},${best[1]}`);
    out.set(b.id, best);
  }
  return out;
}

/** How many cells across and down: as many as fit the screen, more (and the camp pans) when the buildings need
 *  them. The camp is never squeezed. */
export function gridFor(n, vw, vh) {
  const fitC = Math.max(1, Math.floor((vw - 2 * PAD) / CELL.w));
  const fitR = Math.max(1, Math.floor((vh - 2 * PAD) / CELL.h));
  if (n <= fitC * fitR) return { cols: fitC, rows: fitR, fits: true };
  const rows = fitR;
  return { cols: Math.ceil(n / rows) + 1, rows, fits: false };
}

function pos(el, x, y) {
  el.style.left = `${x}px`;
  el.style.top = `${y}px`;
  return el;
}

/** `ctx`: {open(b), name(b)}. Returns {el, render(town, buildings, asking)}. */
export function makeCamp(ctx) {
  const world = h("div", { class: "camp-world" });
  const view = h("div", { class: "camp-view", tabindex: "-1" }, world);
  const el = h("section", { class: "camp", "aria-label": "The camp" }, view);
  let walkers = [];
  let timer = 0;
  let focused = "";                       // what the camera last went to: it moves again only when that changes

  function tick() {
    for (const w of walkers) {
      w.t = (w.t + 1) % (WALK * 2);
      const x = w.t < WALK ? w.t : WALK * 2 - w.t;
      w.el.style.transform = `translate(${x}px, 0)${w.t < WALK ? "" : " scaleX(-1)"}`;
      w.el.style.backgroundPositionX = `${-(w.t % FRAMES) * 32}px`;
    }
  }
  // Runs only while there is someone to move, the page is shown and motion is allowed (the battery).
  function motion() {
    const run = walkers.length > 0 && document.visibilityState === "visible" && !STILL.matches;
    if (run && !timer) timer = setInterval(tick, TICK_MS);
    if (!run && timer) { clearInterval(timer); timer = 0; }
  }
  document.addEventListener("visibilitychange", motion);
  STILL.addEventListener?.("change", motion);

  function render(s, buildings, asking) {
    const camp = s.look !== "office";
    const vw = view.clientWidth || Math.min(window.innerWidth - 32, 640);
    const vh = Math.round(Math.min(Math.max(window.innerHeight * 0.42, 240), 420));
    view.style.height = `${vh}px`;
    const { cols, rows } = gridFor(buildings.length, vw, vh);
    const cells = place(buildings, cols, rows);
    const W = Math.max(vw, cols * CELL.w + 2 * PAD);
    const H = Math.max(vh, rows * CELL.h + 2 * PAD);
    // The cells spread over the room the camp has, so a camp that fits fills the screen.
    const stepX = (W - 2 * PAD) / cols;
    const stepY = (H - 2 * PAD) / rows;
    const at = (id) => {
      const c = cells.get(id);
      return c ? { x: Math.round(PAD + c[0] * stepX + (stepX - CELL.w) / 2), y: Math.round(PAD + c[1] * stepY + (stepY - CELL.h) / 2) } : null;
    };
    world.style.width = `${W}px`;
    world.style.height = `${H}px`;

    // The roads: which building feeds which, a line from mark to mark, solid while the one it starts from works.
    const svg = document.createElementNS(SVG, "svg");
    svg.setAttribute("class", "camp-roads");
    svg.setAttribute("width", String(W));
    svg.setAttribute("height", String(H));
    svg.setAttribute("aria-hidden", "true");
    const ids = new Set(buildings.map((b) => b.id));
    const byId = new Map(buildings.map((b) => [b.id, b]));
    for (const [from, to] of s.roads || []) {
      const a = at(from), b = at(to);
      if (!ids.has(from) || !ids.has(to) || !a || !b) continue;
      const line = document.createElementNS(SVG, "line");
      line.setAttribute("x1", String(a.x + CELL.w / 2));
      line.setAttribute("y1", String(a.y + ART.h / 2 + 8));
      line.setAttribute("x2", String(b.x + CELL.w / 2));
      line.setAttribute("y2", String(b.y + ART.h / 2 + 8));
      line.setAttribute("class", signalOf(byId.get(from), asking) === "work" ? "road busy" : "road");
      svg.append(line);
    }

    walkers = [];
    const huts = [];
    let target = null;
    for (const b of buildings) {
      const p = at(b.id);
      if (!p) continue;
      const sig = signalOf(b, asking);
      const qs = asking.get(b.id) || [];
      const chip = sig === "asks" ? h("span", { class: "camp-sig asks", "aria-hidden": "true" }, qs.length > 1 ? `❓${qs.length}` : "❓")
        : sig === "fire" ? h("span", { class: "camp-sig fire", "aria-hidden": "true" }, "🔥") : null;
      const said = sig === "asks" ? ", asks you" : sig === "fire" ? ", in trouble" : sig === "work" ? ", at work" : "";
      const hut = h("button", { class: `camp-hut${sig ? ` ${sig}` : ""}`, type: "button", "data-b": b.id,
        "aria-label": `${ctx.name(b)}${said}` },
        h("span", { class: "camp-art" }, mark(b.type, camp)), chip,
        h("span", { class: "camp-name" }, ctx.name(b)));
      pos(hut, p.x, p.y);                 // through the CSSOM: the page's CSP takes no style attribute
      hut.addEventListener("click", () => ctx.open(b));
      huts.push(hut);
      if (sig === "work" && camp) {
        const ork = pos(h("span", { class: "camp-ork", "aria-hidden": "true" }), p.x - 4, p.y + ART.h - 44);
        huts.push(ork);
        walkers.push({ el: ork, t: (p.x + p.y) % (WALK * 2) });
      }
      if ((sig === "asks" || sig === "fire") && (!target || (sig === "asks" && target.sig !== "asks"))) target = { id: b.id, sig, p };
    }
    world.replaceChildren(svg, ...huts);
    tick();
    motion();

    // The camera: on what waits (the first that asks, else the first in trouble), or the whole camp from its corner.
    const key = target ? `${target.sig}:${target.id}` : "all";
    if (key !== focused) {
      focused = key;
      const go = () => {
        if (target) view.scrollTo({ left: Math.max(0, target.p.x + CELL.w / 2 - vw / 2), top: Math.max(0, target.p.y + CELL.h / 2 - vh / 2) });
        else view.scrollTo({ left: 0, top: 0 });
      };
      requestAnimationFrame(go);
    }
    el.dataset.focus = target ? target.id : "";
  }

  return { el, render };
}
