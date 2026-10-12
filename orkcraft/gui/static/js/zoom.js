// The map view (docs/design/map-view.md): the town from above, every building as its house, its plinth, its name and
// its mark, with no card. A view of the whole town, never a state of a building: the Town Scroll keeps nothing of it,
// this browser keeps it (as `orkcraft.grow`). `M` toggles it from anywhere but a field, a terminal or a dialog; a pinch
// on the town and the bare town's menu do too (js/town.js).
import { signal } from "@preact/signals";

const KEY = "orkcraft.map";

export const mapView = signal((() => { try { return localStorage.getItem(KEY) === "1"; } catch { return false; } })());

export function setMap(on) {
  if (mapView.value === !!on) return;
  mapView.value = !!on;
  try { localStorage.setItem(KEY, on ? "1" : "0"); } catch { /* the view holds for this page */ }
}

export const toggleMap = () => setMap(!mapView.value);

window.addEventListener("keydown", (e) => {
  if (e.ctrlKey || e.metaKey || e.altKey || e.key.toLowerCase() !== "m" || document.querySelector(".gui-modal, .gui-menu")) return;
  if (e.target.closest && e.target.closest("input, textarea, select, [contenteditable], .gui-term")) return;
  e.preventDefault();
  toggleMap();
});
