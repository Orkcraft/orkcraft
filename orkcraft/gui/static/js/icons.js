// Office: a building type's icon at the start of its name — line pictograms in the manner of the
// usual UI sets (Lucide, VS Code's codicons), drawn here on a 16px grid in the text's colour. Camp
// shows the type's header sprite instead (js/hut.js). A type without one of its own gets the box.
import { html } from "./html.js";
import { town, say } from "./link.js";

const PATHS = {
  pit: "M2 9.5v4h12v-4M2 9.5h3.5l1 1.5h3l1-1.5H14M8 2v6M5.5 5.5 8 8l2.5-2.5",                      // inbox tray
  watchtower: "M8 9v5.5M5.5 14.5h5M5 4.5a4.2 4.2 0 0 0 0 6M11 4.5a4.2 4.2 0 0 1 0 6M3 2.5a7 7 0 0 0 0 10M13 2.5a7 7 0 0 1 0 10M8 7.8v.4", // broadcast
  signpost: "M8 1.5v13M3 3.5h8l2 2-2 2H3zM13 8.5H6l-2 2 2 2h7z",                                     // signpost
  mill: "M2.5 5.5h9l-2.5-2.5M13.5 10.5h-9L7 13",                                                     // transform arrows
  horn: "M4 11V7a4 4 0 0 1 8 0v4l1.5 1.5h-11zM6.5 14h3",                                               // bell
  fields: "M2 2.5h12v11H2zM6 2.5v11M10 2.5v11M3.5 5h1M7.5 5h1M7.5 7.5h1M11.5 5h1",                    // kanban
  barracks: "M6 7.5a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5zM1.5 14c0-2.5 2-4 4.5-4s4.5 1.5 4.5 4M11 2.8a2.3 2.3 0 0 1 0 4.4M12.5 10.3c1.3.6 2 1.9 2 3.7", // users
  council: "M2 3h12v8H7l-3 2.5V11H2zM5.5 7l1.8 1.8L10.5 5.5",                                       // review: message with a check
  war_drum: "M2 3.5h12v10H2zM2 6.5h12M5 1.8v3M11 1.8v3M5 9h1.5M9.5 9H11M5 11h1.5",                    // calendar
  forest: "M2 2v10.5h4M2 6h4M6 4.5h3l1 1h4v3H6zM6 11h3l1 1h4v2H6z",                                   // folder tree
  mine: "M2.5 7C5 3.5 11 3.5 13.5 7M8 4.6 3.5 14.5",                                                 // pickaxe
  gramophone: "M2.5 14.5h7M6 14.5v-4l2.5-2.5M8.5 8 13.5 2.5M8.5 8l6 .5M13.5 2.5c1.5 2 1.5 4.5 1 6",               // gramophone
  scrolls: "M1.5 3h4.5a2 2 0 0 1 2 2v9a1.5 1.5 0 0 0-1.5-1.5h-5zM14.5 3H10a2 2 0 0 0-2 2v9a1.5 1.5 0 0 1 1.5-1.5h5z", // open book
  lake: "M1.5 8s2.5-4.5 6.5-4.5S14.5 8 14.5 8s-2.5 4.5-6.5 4.5S1.5 8 1.5 8zM8 10a2 2 0 1 0 0-4 2 2 0 0 0 0 4z", // eye
  forge: "M4 5.5v8M4 5.5a1.8 1.8 0 1 0 0-3.6 1.8 1.8 0 0 0 0 3.6zM12 10.5a1.8 1.8 0 1 0 0 3.6 1.8 1.8 0 0 0 0-3.6zM12 10.5V6a2 2 0 0 0-2-2H7.5M9 2.5 7.5 4 9 5.5", // pull request
  loot: "M8 1.5 13.5 3.5v4c0 3.5-2.5 6-5.5 7-3-1-5.5-3.5-5.5-7v-4zM5.5 8l1.8 1.8L10.5 6.5",             // shield check
  crag: "M2 14h12M3.5 14V9M6.5 14V4.5M9.5 14V7M12.5 14V2.5",                                        // bar chart
  catapult: "M14.5 1.5 1.5 7l5 2.5 2.5 5zM14.5 1.5 6.5 9.5",                                        // send
  town_hall: "M2.5 4h7M12.5 4h1M2.5 12h1M6.5 12h7M9.5 2.5v3M5 10.5v3M2.5 8h4M9.5 8h4M6.5 6.5v3",      // sliders
  workshop: "M2 2.5h12v11H2zM4.5 6l2 2-2 2M8 10.5h3.5",                                              // terminal
  lab: "M6 1.5h4M6.8 1.5v4.8L3 12.6a1.4 1.4 0 0 0 1.2 1.9h7.6a1.4 1.4 0 0 0 1.2-1.9L9.2 6.3V1.5M4.6 10h6.8",   // flask
  custom: "M8 1.5 14 4.5v7L8 14.5 2 11.5v-7zM2 4.5 8 7.5l6-3M8 7.5v7",                                // box
};
PATHS.loot_vault = PATHS.loot;

export function TypeIcon({ type }) {
  return html`<svg class="gui-type-icon" viewBox="0 0 16 16" width="14" height="14" aria-hidden="true">
    <path d=${PATHS[type] || PATHS.custom} /></svg>`;
}

// The biomes an orkspace stands on (docs/design/war-map.md §3, realm/biomes.py): the town's ground, the
// land's fill on the War Map. Dark and low in saturation, so cards, gold and fire read on all; lava is
// basalt, never red (red is the fire's). Every ground stays darker than a card (`--panel`), so a card reads
// as a plane on it (about 1.2:1 at least), never as a hole in it.
export const BIOMES = {
  dirt: { ground: "#141210", land: "#3a3326" },
  forest: { ground: "#101a0b", land: "#22341a" },
  ice: { ground: "#070d14", land: "#1c2c3c" },
  dust: { ground: "#1a1712", land: "#5a462a" },   // a step greyer than the fence's wood, so the two part
  void: { ground: "#0e0c14", land: "#2c263c" },
  lava: { ground: "#170f0d", land: "#342c2a" },   // basalt night, a breath of ember in it; the huts ash-grey on it
  meadow: { ground: "#0d1a16", land: "#24443a" },   // the knights' open field: cool spring green, not forest's
};
export const BIOME_ORDER = Object.keys(BIOMES);
const DRAWN_FOR = new Set(["ice", "dust", "void", "lava", "meadow"]);   // header-<biome>.png (tools/growth_sprites.py)
// Headers kept as they were painted (tools/painted.py): drawn smoothly, not as pixels, their @2x on a retina screen.
const PAINTED = new Set(["town_hall", "watchtower", "fields", "war_drum", "barracks", "council", "scrolls", "mine",
  "gramophone", "forge", "loot", "catapult", "lab", "workshop", "pit", "signpost", "mill", "crag", "horn"]);

function spriteName(type) {
  return type === "loot_vault" ? "loot" : PATHS[type] ? type : "custom";
}

/** The type's header sprite (design-system/sprites/buildings/<type>/header.png), drawn for the biome its
 *  orkspace stands on; dirt and forest wear the flat one. */
export function headerSprite(type, biome = "") {
  const name = spriteName(type);
  return `/ds/sprites/buildings/${name}/${DRAWN_FOR.has(biome) ? `header-${biome}` : "header"}.png`;
}

// Where the goal flag stands on each roof (docs/design/growth.md §5): [x, y, height] in units of 2 screen px over
// the header: the pole's foot at (x, y), the sprite `height` tall. The top of each sprite's middle third
// (tools/painted.py's headers are measured on their 1x).
const FLAG_AT = {
  barracks: [19, 2, 34], catapult: [12, 8, 32], council: [28, 1, 33], crag: [17, 0, 38], custom: [17, 1, 26],
  fields: [16, 0, 33], forest: [17, 0, 27], forge: [24, 0, 40], gramophone: [18, 0, 37], horn: [16, 13, 32],
  lab: [23, 9, 43], lake: [17, 0, 33], loot: [17, 14, 37], mill: [11, 4, 38], mine: [17, 0, 32], pit: [12, 0, 27],
  scrolls: [15, 0, 34], signpost: [9, 0, 38], town_hall: [23, 0, 38], war_drum: [9, 3, 40], watchtower: [10, 0, 44],
  workshop: [25, 1, 32],
};

const FOOTING_ROWS = { 1: 2, 2: 4, 3: 6 };     // the footing's height in its pixels (2 screen px each), by level

/** A building's header sprite in its biome, its renown told twice and its goal once (docs/design/growth.md §5):
 *  from I a flag on the roof (ivory, taller at II, gold at III) and stones under it, a course more at each
 *  level; beside it an annex by its goal, a lean-to over logs for thrift, a crystal for quality, none for
 *  balance. */
export function HutSprite({ type, biome, goal, level, className = "", onError }) {
  const at = FLAG_AT[spriteName(type)];
  const n = Math.min(Math.max(level || 0, 0), 3);
  const annex = goal === "thrift" || goal === "quality" ? goal : "";
  const src = headerSprite(type, biome);
  const painted = PAINTED.has(spriteName(type));
  return html`<span class=${`gui-sprite ${className}`} data-goal=${goal || "balance"} data-level=${n}>
    <span class="gui-sprite__hut">
      <span class="gui-sprite__walls">
        <img class=${`ok-sprite${painted ? " is-painted" : ""}`} src=${src} alt="" draggable="false" onError=${onError}
          srcset=${painted ? `${src} 1x, ${src.replace(/\.png$/, "@2x.png")} 2x` : null} />
        ${n > 0 && at && html`<img class=${`ok-sprite gui-sprite__flag${biome === "ice" ? " is-on-snow" : ""}`}
          src=${`/ds/sprites/flags/level-${n}.png`} alt="" draggable="false"
          style=${`left:${at[0] * 2}px;bottom:${(at[2] - at[1]) * 2}px`} />`}
      </span>
      ${n > 0 && html`<span class="gui-sprite__footing"
        style=${`height:${FOOTING_ROWS[n] * 2}px;background-image:url(/ds/sprites/flags/footing-${n}.png)`}></span>`}
    </span>
    ${annex && html`<img class="ok-sprite gui-sprite__annex" src=${`/ds/sprites/flags/annex-${annex}.png`}
      alt="" draggable="false" />`}
  </span>`;
}

// Camp: an ork of a garrison as its head in its state (design-system/sprites/orks/, the ork mark's
// head); a chain or script as its signpost. Office hides both (`.ok-sprite`) and keeps the words.
// A state's sprite is wider than the bare head: its glyph (Zz, a gear, `!`, a snowflake, a page) stands
// beside it, 40 × 16 against the head's 24 × 16 (tools/logo.py).
const ORK_STATE = { busy: "ork-busy", alert: "ork-waiting", idle: "ork-idle", frozen: "ork-frozen", draft: "ork-draft" };
const ORK_STATE_WORD = { busy: "busy", alert: "waiting", idle: "resting", frozen: "frozen", draft: "draft" };

/** The Warchief: the ork's head under its gold crown (docs/design/growth.md §8); waiting, the crown burns. */
export function WarchiefHead({ state = "" }) {
  const name = state ? `warchief-${state}` : "warchief";
  return html`<img class="ok-sprite gui-warchief__crowned" src=${`/ds/sprites/orks/${name}.png`}
    srcset=${`/ds/sprites/orks/${name}@2x.png 2x`} width=${state ? 40 : 24} height="20" alt="" />`;
}

// A steward's hat by the work of its building (tools/hat_sprites.py): its face on the Warchief's line, and the ork
// that comes out of its building wears it (js/visit.js). A type with none (a custom one) keeps the bare head.
export const HATS = {
  scrolls: "scribe", mill: "scribe", gramophone: "scribe", lake: "scribe",
  watchtower: "lookout", horn: "lookout", crag: "lookout",
  forge: "smith", workshop: "smith", catapult: "smith",
  fields: "clerk", war_drum: "clerk", loot: "clerk", signpost: "clerk", forest: "clerk", pit: "clerk",
  barracks: "captain", council: "captain",
  mine: "miner",
};

/** A building's steward, its head under its role's hat (the bare head for a type with none). */
export function StewardHead({ type }) {
  const hat = HATS[type];
  const name = hat ? `steward-${hat}` : "ork";
  return html`<img class="ok-sprite gui-warchief__crowned" src=${`/ds/sprites/orks/${name}.png`}
    srcset=${`/ds/sprites/orks/${name}@2x.png 2x`} width="24" height=${hat ? 20 : 16} alt="" draggable="false" />`;
}

/** The operator's mascot (docs/design/growth.md §7): its role's head at its stage. */
export function MascotHead({ sprite, stage, size = 4 }) {  // size: screen px a pixel of its 12 × 11 grid
  return html`<img class="ok-sprite gui-mascot" src=${`/ds/sprites/mascots/${sprite}-${stage}@2x.png`}
    width=${12 * size} height=${11 * size} alt="" />`;
}

/** The biome of the open orkspace: the ground its huts stand on. */
export function activeBiome() {
  const t = town.value;
  const o = t && t.orkspaces.find((x) => x.id === t.active_orkspace);
  return o && BIOMES[o.biome] ? o.biome : "dirt";
}

// An AI tool's mark (realm/harnesses.py): a simple sign of its own in the tool's colours, no one's logo —
// Claude an orange starburst, Antigravity an arch in Google's four colours, Codex a green tile with `>_`,
// Hermes a purple winged staff, pi a rose tile with π, Cursor a grey cube. Camp draws the pixel sprite
// (design-system/sprites/icons/harness-<id>.png, tools/icon_sprites.py), Office the same sign as a small
// SVG; a look shows one of the two (layout.css, office.css). A tool without one shows its text mark.
const TOOL_SVG = {
  claude: [["path", { d: "M8 1.2v13.6M1.2 8h13.6M3.2 3.2l9.6 9.6M12.8 3.2l-9.6 9.6", stroke: "#d97757", "stroke-width": 2.1, "stroke-linecap": "round" }],
           ["circle", { cx: 8, cy: 8, r: 2.4, fill: "#d97757" }]],
  agy: [["path", { d: "M3.2 15V8", stroke: "#4285f4" }], ["path", { d: "M3.2 8.1A4.8 4.8 0 0 1 8 3.2", stroke: "#ea4335" }],
        ["path", { d: "M8 3.2a4.8 4.8 0 0 1 4.8 4.9", stroke: "#fbbc05" }], ["path", { d: "M12.8 8v7", stroke: "#34a853" }]]
    .map(([t, a]) => [t, { ...a, "stroke-width": 2.6, fill: "none" }]),
  codex: [["rect", { x: 1, y: 1, width: 14, height: 14, rx: 3, fill: "#10a37f" }],
          ["path", { d: "M4.3 4.8 7.5 8l-3.2 3.2M8.6 11.4h3.4", stroke: "#fff", "stroke-width": 1.7, "stroke-linecap": "round", "stroke-linejoin": "round", fill: "none" }]],
  hermes: [["path", { d: "M8 1.5v13", stroke: "#a855f7", "stroke-width": 1.8 }],
           ["path", { d: "M7 4.6C5.4 2.6 3.3 2.2 1 2.9c1 1.8 3.3 2.7 6 2.6zM9 4.6c1.6-2 3.7-2.4 6-1.7-1 1.8-3.3 2.7-6 2.6z", fill: "#c39bfb" }],
           ["path", { d: "M10.6 6.6c0 1.6-5.2 1.4-5.2 3s5.2 1.4 5.2 3M5.4 6.6c0 1.6 5.2 1.4 5.2 3s-5.2 1.4-5.2 3", stroke: "#a855f7", "stroke-width": 1.3, fill: "none" }]],
  pi: [["rect", { x: 1, y: 1, width: 14, height: 14, rx: 3, fill: "#e5395b" }],
       ["path", { d: "M3.8 5.2h8.4M6.2 5.2v4.4c0 1-.3 1.8-1 2.3M9.8 5.2v5.2c0 .8.4 1.2 1.3 1.2", stroke: "#fff", "stroke-width": 1.8, "stroke-linecap": "round", fill: "none" }]],
  cursor: [["path", { d: "M8 1.2 14.4 4.9 8 8.6 1.6 4.9z", fill: "#e3e8ef" }], ["path", { d: "M1.6 4.9 8 8.6v6.2l-6.4-3.7z", fill: "#9aa5b4" }],
           ["path", { d: "M14.4 4.9 8 8.6v6.2l6.4-3.7z", fill: "#4a525e" }],
           ["path", { d: "M8 1.2l6.4 3.7v6.2L8 14.8l-6.4-3.7V4.9z", stroke: "#4a525e", "stroke-width": .8, "stroke-linejoin": "round", fill: "none" }]],
};
const TOOL_OF_MARK = { "✻": "claude", "✦": "agy", "⌬": "codex", "☤": "hermes", "π": "pi", "◆": "cursor" };

/** An AI tool's mark by its id (`claude`) or its text mark (`✻`): the sprite in Camp, the SVG in Office. */
export function ToolMark({ id = "", mark = "" }) {
  const tool = TOOL_SVG[id] ? id : TOOL_OF_MARK[mark];
  if (!tool) return mark ? html`<span class="gui-toolmark__text" aria-hidden="true">${mark}</span>` : null;
  return html`<span class="gui-toolmark" aria-hidden="true"><img class="ok-sprite" data-kind="harness"
      src=${`/ds/sprites/icons/harness-${tool}.png`} srcset=${`/ds/sprites/icons/harness-${tool}@2x.png 2x`}
      width="16" height="16" alt="" />
    <svg class="gui-toolmark__svg" viewBox="0 0 16 16" width="14" height="14">
      ${TOOL_SVG[tool].map(([tag, attrs]) => html`<${tag} ...${attrs} />`)}</svg></span>`;
}

// Camp: a harness scheme (`✦→✻`, `P→✻·4`: realm/looks.py) as marks, one a harness (`ToolMark`), the steps
// joined by a pixel arrow; a pipeline's P has its sprite too. Office shows the tools' SVGs and the P and the
// arrow as text: each sprite carries its glyph beside it (layout.css, office.css).
const HARNESS_SPRITE = { "P": "pipeline", "→": "arrow" };

/** The harness scheme: the tools' marks, the P and the arrow pixel in Camp and text in Office. */
export function Scheme({ scheme }) {
  if (!scheme) return null;
  const parts = [...scheme.matchAll(/·\d+|./gu)].map((m) => m[0]);
  return html`<span class="gui-scheme" title=${scheme}>${parts.map((c, i) => {
    if (TOOL_OF_MARK[c]) return html`<span key=${i} class="gui-scheme__mark"><${ToolMark} mark=${c} /></span>`;
    const name = HARNESS_SPRITE[c];
    if (!name) return html`<span key=${i} class="gui-scheme__text">${c}</span>`;
    return html`<span key=${i} class="gui-scheme__mark"><img class="ok-sprite" data-kind="harness"
      src=${`/ds/sprites/icons/harness-${name}.png`} srcset=${`/ds/sprites/icons/harness-${name}@2x.png 2x`}
      width=${name === "arrow" ? 10 : 16} height="16" alt="" /><span class="gui-scheme__glyph">${c}</span></span>`;
  })}</span>`;
}

/** A tier as a person reads it (realm/tiers.py; docs/design/warchief-line-and-cards.md §6): its chevrons and its
 *  word — Novice, Seasoned, Veteran — never the code's `laborer`, `warrior`, `elder`. Office: the word alone. */
const RANKS = { laborer: [1, "Novice"], warrior: [2, "Seasoned"], elder: [3, "Veteran"] };
export function TierMark({ tier }) {
  const r = RANKS[tier];
  if (!r) return null;
  return html`<span class="gui-tier" title=${r[1]}><img class="ok-sprite gui-tier__mark" src=${`/ds/sprites/icons/rank-${r[0]}.png`}
    srcset=${`/ds/sprites/icons/rank-${r[0]}@2x.png 2x`} width="12" height="12" alt="" draggable="false" />${r[1]}</span>`;
}

export function OrkHead({ o, alert }) {
  if (o.kind === "chain" || o.kind === "script") {
    return html`<img class="ok-sprite" data-kind="chain" src="/ds/sprites/icons/chain.png" width="16" height="16" alt="" />`;
  }
  const status = alert ? "alert" : o.status;
  const state = ORK_STATE[status] || "ork";
  return html`<img class="ok-sprite" data-kind="ork" src=${`/ds/sprites/orks/${state}.png`}
    srcset=${`/ds/sprites/orks/${state}@2x.png 2x`} width=${state === "ork" ? 24 : 40} height="16"
    alt="" title=${say(ORK_STATE_WORD[status] || "")} />`;
}
