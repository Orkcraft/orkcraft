// The War Map (docs/design/war-map.md): the orkspaces as lands stacked in a framed landscape at the town's
// bottom left, each in its biome's colour, the open one tall with its status and its buildings as dots, the
// fog of war at the foot (Add orkspace +) and in a wedge at the right, each land a step shorter than the
// one above. Its title and the lands' names are in the pixel face. Every land is a real button cut to
// its shape by a clip path, so clicks follow the shape; ↑ / ↓ walk the lands, Enter opens, the right click
// renames, changes the biome or removes. When an ork asks in another orkspace the map calls: rings from the
// land's ■, the land flashes, an arrow at the frame's edge when it is out of sight (§2.5).
import { useEffect, useLayoutEffect, useRef, useState } from "preact/hooks";
import { html, cls } from "./html.js";
import { town, command, say } from "./link.js";
import { openMenu } from "./menu.js";
import { BIOMES, BIOME_ORDER } from "./icons.js";
import { useScrollCue } from "./scrollcue.js";

const N = 36, W = 52, T = 4;               // 36 rows × 52 columns of 4 px: 208 × 144, a minimap's landscape
const FOG_ROWS = 4, CLOSED_MIN = 7, OPEN_MIN = 12;   // a closed land at least 28 px: its name never touches a border
const FOG = "#221e16";
const CALL_EVERY_MS = 30_000;              // a land calls at most this often

// Straight borders, and each land a step shorter than the one above it: even stripes, a neat terrace.
const TAPER = 2, TAPER_MAX = 14;           // cells each land is shorter than the one above it, at most

function layout(lands, open) {
  const closedN = lands.length - 1, avail = N - FOG_ROWS;
  const closed = Math.max(CLOSED_MIN, Math.floor(avail / (closedN + 2.4)));
  let openH = Math.max(OPEN_MIN, avail - closedN * closed);
  const rows = closedN * closed + openH + FOG_ROWS;
  if (rows < N) openH += N - rows;
  const H = Math.max(N, rows);
  const tops = [0];
  for (const o of lands) tops.push(tops[tops.length - 1] + (o.id === open ? openH : closed));
  const border = tops.map((y, k) => (k === 0 ? null : Array(W).fill(y)));
  return { H, tops, border };
}

/** A union of the cells `inside` holds, row by row; a land's first row in a column leaves a 1 px seam. */
function cellsPath(inside, H, isTop) {
  let d = "";
  for (let y = 0; y < H; y++) {
    let x = 0;
    while (x < W) {
      if (!inside(x, y)) { x++; continue; }
      const top = isTop(x, y);
      let x1 = x;
      while (x1 < W && inside(x1, y) && isTop(x1, y) === top) x1++;
      const y0 = y * T + (top ? 1 : 0), h = T - (top ? 1 : 0);
      d += `M${x * T} ${y0}h${(x1 - x) * T}v${h}h${-(x1 - x) * T}z`;
      x = x1;
    }
  }
  return d;
}

const plural = (n, w) => `${n} ${w}${n === 1 ? "" : "s"}`;

/** What the open land says after its count: what waits on the person first, "all quiet" only when nothing does. */
function state(o) {
  const parts = [];
  if (o.questions) parts.push(plural(o.questions, "question"));
  if (o.paused) parts.push(`${o.paused} paused`);
  if (o.working) parts.push(`${o.working} at work`);
  return parts.length ? parts.join(" · ") : "all quiet";
}

/** A name typed in place: a new orkspace in the fog, or a land renamed. */
function NameField({ top, value = "", onDone, onName }) {
  const [name, setName] = useState(value);
  const ref = useRef(null);
  useEffect(() => { if (ref.current) { ref.current.focus(); ref.current.select(); } }, []);
  const done = () => { if (name.trim() && name.trim() !== value) onName(name.trim()); onDone(); };
  return html`<input ref=${ref} class="ok-input gui-map__field" style=${`top:${top}px`} value=${name}
    aria-label=${say("Orkspace name")} placeholder=${say("Orkspace name")}
    onInput=${(e) => setName(e.target.value)} onBlur=${onDone}
    onKeyDown=${(e) => { e.stopPropagation(); if (e.key === "Enter") done(); else if (e.key === "Escape") onDone(); }} />`;
}

/** The biome a new land takes unless another is picked: the first nobody has, else any but the last's
 *  (realm/biomes.py `for_new`). */
function suggested(lands) {
  const taken = lands.map((o) => o.biome);
  const free = BIOME_ORDER.find((b) => !taken.includes(b));
  if (free) return free;
  const others = BIOME_ORDER.filter((b) => b !== taken[taken.length - 1]);
  return others[taken.length % others.length];
}

/** A new land from the fog: its name, and its ground picked from a row of swatches (the biome it suggests
 *  lit). ← / → walk the swatches without leaving the name; Enter raises it, Esc lets it go. */
function NewLand({ lands, bottom, onDone }) {
  const [name, setName] = useState("");
  const [biome, setBiome] = useState(() => suggested(lands));
  const ref = useRef(null);
  useEffect(() => { if (ref.current) ref.current.focus(); }, []);
  const make = () => {
    if (name.trim()) command("orkspace.new", { name: name.trim(), biome }).catch(() => {});
    onDone();
  };
  const step = (d) => setBiome(BIOME_ORDER[(BIOME_ORDER.indexOf(biome) + d + BIOME_ORDER.length) % BIOME_ORDER.length]);
  return html`<div class="gui-map__new" style=${`bottom:${bottom}px`}
      onMouseDown=${(e) => { if (e.target !== ref.current) e.preventDefault(); }}>
    <input ref=${ref} class="ok-input gui-map__field" value=${name} aria-label=${say("Orkspace name")}
      placeholder=${say("Orkspace name")} onInput=${(e) => setName(e.target.value)} onBlur=${onDone}
      onKeyDown=${(e) => {
        e.stopPropagation();
        if (e.key === "Enter") make();
        else if (e.key === "Escape") onDone();
        else if (e.key === "ArrowLeft" && !name) { e.preventDefault(); step(-1); }
        else if (e.key === "ArrowRight" && !name) { e.preventDefault(); step(1); }
      }} />
    <div class="gui-map__biomes" role="radiogroup" aria-label=${say("Biome")}>
      ${BIOME_ORDER.map((b) => html`<button key=${b} role="radio" aria-checked=${b === biome} title=${say(`Biome: ${b}`)}
          class=${cls("gui-map__biome", { "is-on": b === biome })} style=${`--fill:${BIOMES[b].land};--ground:${BIOMES[b].ground}`}
          tabindex="-1" onClick=${() => { setBiome(b); if (ref.current) ref.current.focus(); }}></button>`)}
      <span class="gui-map__biome-name">${say(biome)}</span>
    </div>
  </div>`;
}

export function WarMap() {
  const t = town.value;
  const lands = t.orkspaces, open = t.active_orkspace;
  const view = useRef(null), land = useRef(null), frame = useRef(null);
  useScrollCue(view);
  const [naming, setNaming] = useState(null);          // "new" | an orkspace id being renamed
  const asked = useRef(null);                           // orkspace id → its questions at the last render
  const called = useRef({});                            // orkspace id → when it last called
  const { H, tops, border } = layout(lands, open);
  const coastAt = (y, i) => W - Math.min(TAPER * i, TAPER_MAX);   // each land a step shorter: terraces
  const n = lands.length;

  const select = (o) => { if (o.id !== open) command("orkspace.select", { id: o.id }).catch(() => {}); };
  const menuOf = (e, o) => openMenu(e, [
    { label: "Rename…", run: () => setNaming(o.id) },
    "-",
    ...BIOME_ORDER.map((b) => ({ label: `${b === o.biome ? "✓ " : ""}Biome: ${b}`,
      run: () => command("orkspace.biome", { id: o.id, biome: b }).catch(() => {}) })),
    "-",
    lands.length > 1 && { label: "Remove", danger: true, run: () => command("orkspace.remove", { id: o.id }).catch(() => {}) },
  ]);
  function key(e) {
    if (e.key !== "ArrowDown" && e.key !== "ArrowUp") return;
    const all = [...land.current.querySelectorAll(".gui-map__land")];
    const i = all.indexOf(document.activeElement);
    if (i < 0) return;
    e.preventDefault();
    const j = Math.max(0, Math.min(all.length - 1, i + (e.key === "ArrowDown" ? 1 : -1)));
    all[j].focus({ preventScroll: true });
    all[j].querySelector(".gui-map__name")?.scrollIntoView({ block: "nearest" });
  }

  // keep the open land in sight
  const k = Math.max(0, lands.findIndex((o) => o.id === open));
  useLayoutEffect(() => {
    const v = view.current;
    if (!v) return;
    const top = tops[k] * T, bottom = tops[k + 1] * T;
    if (top < v.scrollTop || bottom > v.scrollTop + v.clientHeight) v.scrollTop = Math.max(0, top - 24);
  }, [open, n]);

  // the call: a new question in an orkspace that is not open
  useEffect(() => {
    const before = asked.current;
    asked.current = Object.fromEntries(lands.map((o) => [o.id, o.questions]));
    if (!before || t.hud.quiet) return;
    const now = Date.now();
    for (const o of lands) {
      if (o.id === open || o.questions <= (before[o.id] ?? o.questions)) continue;
      if (now - (called.current[o.id] || 0) < CALL_EVERY_MS) continue;
      called.current[o.id] = now;
      call(o);
    }
  });
  function call(o) {
    const el = land.current && land.current.querySelector(`[data-id="${CSS.escape(o.id)}"]`);
    const ask = el && el.querySelector(".gui-map__ask");
    if (!ask) return;
    const L = land.current.getBoundingClientRect(), r = ask.getBoundingClientRect();
    const x = r.left - L.left + 4, y = r.top - L.top + 4;
    for (let i = 0; i < 3; i++) {
      const p = document.createElement("span");
      p.className = "gui-map__ping";
      p.style.cssText = `left:${x}px;top:${y}px;animation-delay:${i * 0.45}s`;
      land.current.append(p);
      setTimeout(() => p.remove(), 1000 + i * 450);
    }
    el.classList.add("is-hit");
    setTimeout(() => el.classList.remove("is-hit"), 1300);
    const v = view.current;
    if (v && (y < v.scrollTop || y > v.scrollTop + v.clientHeight) && frame.current) {
      const a = document.createElement("span");
      a.className = `gui-map__edge ${y < v.scrollTop ? "is-up" : "is-down"}`;
      a.textContent = `${y < v.scrollTop ? "▲" : "▼"} ${o.name}`;
      frame.current.append(a);
      setTimeout(() => a.remove(), 4000);
    }
  }

  const fogFrom = (x) => border[n][x];
  const fogMid = (tops[n] + (H - tops[n]) / 2) * T - 7;
  return html`<nav ref=${frame} class="gui-map" aria-label=${say("Orkspaces")} onKeyDown=${key}>
    <div class="gui-map__title">${say("War Map")}</div>
    <div class="gui-map__frame"><div ref=${view} class="gui-map__view gui-scrolls">
      <div ref=${land} class="gui-map__ground" style=${`height:${H * T}px;--fog:${FOG}`}>
        ${lands.map((o, i) => {
          const from = (x) => (i === 0 ? 0 : border[i][x]), to = (x) => border[i + 1][x];
          const inside = (x, y) => y >= from(x) && y < to(x) && x < coastAt(y, i);
          const path = cellsPath(inside, H, (x, y) => i > 0 && y === from(x));
          const y0 = tops[i] * T, y1 = tops[i + 1] * T, isOpen = o.id === open;
          const label = `${o.name}, ${plural(o.count, "building")}${o.questions ? `, ${plural(o.questions, "question")}` : ""}`;
          return html`<button key=${o.id} data-id=${o.id} class=${cls("gui-map__land", { "is-open": isOpen })}
              style=${`clip-path:path("${path}");--fill:${(BIOMES[o.biome] || BIOMES.dirt).land}`}
              aria-current=${isOpen ? "true" : "false"} aria-label=${say(label)} title=${say(`${o.name} · ${o.biome}`)}
              onClick=${() => select(o)} onContextMenu=${(e) => menuOf(e, o)}>
            ${isOpen && html`<span class="gui-map__bar" style=${`top:${y0 + 5}px;height:${y1 - y0 - 10}px`}></span>`}
            <span class="gui-map__name" style=${`top:${isOpen ? y0 + 6 : (y0 + y1) / 2 - 7}px`}>${say(o.name)}${o.questions
              ? html`<span class="gui-map__ask" aria-hidden="true"></span>` : null}</span>
            ${isOpen && html`<span class=${cls("gui-map__state", { "ok-tone-wait": !!o.paused && !o.questions })}
              style=${`top:${y0 + 21}px`}>${say(`${plural(o.count, "building")} · ${state(o)}`)}</span>`}
            ${isOpen && o.count > 0 && html`<span class="gui-map__dots" style=${`top:${y1 - 10}px`}
              title=${say(`${plural(o.count, "building")}${o.working ? ` · ${o.working} at work` : ""}`)}>
              ${Array.from({ length: Math.min(o.count, 16) }, (_, j) => html`<i key=${j} class=${j < o.working ? "is-busy" : ""}></i>`)}</span>`}
          </button>`;
        })}
        <button class="gui-map__land gui-map__fog" title=${say("A new orkspace from the fog of war")}
            style=${`clip-path:path("${cellsPath((x, y) => y >= fogFrom(x), H, (x, y) => y === fogFrom(x))}");--fill:${FOG}`}
            onClick=${() => setNaming("new")}>
          <span class="gui-map__name" style=${`top:${fogMid}px`}>${say("Add orkspace")} +</span>
        </button>
        ${naming === "new" && html`<${NewLand} lands=${lands} bottom=${2} onDone=${() => setNaming(null)} />`}
        ${naming && naming !== "new" && (() => {
          const i = lands.findIndex((o) => o.id === naming);
          if (i < 0) return null;
          return html`<${NameField} top=${tops[i] * T + 2} value=${lands[i].name} onDone=${() => setNaming(null)}
            onName=${(name) => command("orkspace.rename", { id: naming, name }).catch(() => {})} />`;
        })()}
      </div>
    </div></div>
  </nav>`;
}
