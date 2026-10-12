// The town's zoom (docs/design/map-view.md): three levels, as a strategy game's camera pulled back. `a` the map (every
// building its house and its name; over it only a question or what broke), `b` the overview (a card in its yard at its
// smallest; the default), `c` close (a card at its medium size, a bare building in a small yard of its own). A
// building keeps its width at every level and only its height and its place down the town change, so nothing moves
// sideways. A view of the whole town, never a state of a building: this browser keeps it, the Town Scroll nothing.
// A pinch on the town (js/town.js), ⌘+ / ⌘− (Ctrl on other systems), ⌘0 back to the overview; `M` the map and back.
import { signal, computed } from "@preact/signals";

const KEY = "orkcraft.zoom";
export const LEVELS = ["a", "b", "c"];
const DEFAULT = "b";

function stored() {
  try {
    const v = localStorage.getItem(KEY);
    if (LEVELS.includes(v)) return v;
    return localStorage.getItem("orkcraft.map") === "1" ? "a" : DEFAULT;      // the map view of before
  } catch { return DEFAULT; }
}

export const zoomLevel = signal(stored());
export const mapView = computed(() => zoomLevel.value === "a");
export const zooming = signal(false);       // a level just changed: huts glide to their new places (layout.css)
let back = zoomLevel.value === "a" ? DEFAULT : zoomLevel.value;              // where `M` returns from the map
let settle = null;

export function setZoom(level) {
  if (!LEVELS.includes(level) || level === zoomLevel.value) return;
  if (level !== "a") back = level;
  zoomLevel.value = level;
  zooming.value = true;
  clearTimeout(settle);
  settle = setTimeout(() => { zooming.value = false; }, 320);
  try { localStorage.setItem(KEY, level); } catch { /* the level holds for this page */ }
}

/** One level closer (+1) or further (−1); none past the ends. */
export function zoomBy(step) {
  const i = LEVELS.indexOf(zoomLevel.value) + step;
  if (i >= 0 && i < LEVELS.length) setZoom(LEVELS[i]);
}

export const setMap = (on) => setZoom(on ? "a" : back);
export const toggleMap = () => setMap(!mapView.value);

window.addEventListener("keydown", (e) => {
  if (document.querySelector(".gui-modal, .gui-menu")) return;
  if (e.target.closest && e.target.closest("input, textarea, select, [contenteditable], .gui-term")) return;
  if ((e.metaKey || e.ctrlKey) && !e.altKey) {
    // ⌘+ / ⌘− zoom the town, not the page; ⌘0 the overview
    const step = e.key === "+" || e.key === "=" ? 1 : e.key === "-" || e.key === "_" ? -1 : 0;
    if (step) { e.preventDefault(); zoomBy(step); }
    else if (e.key === "0") { e.preventDefault(); setZoom(DEFAULT); }
    return;
  }
  if (e.altKey || e.key.toLowerCase() !== "m") return;
  e.preventDefault();
  toggleMap();
});
