// The Orkcraft GUI, Office look: the town over the core (gui/server.py), drawn with the design
// system's markup (design-system/components.md). Preact + signals, no build step.
import { render } from "preact";
import { html } from "./js/html.js";
import { town, connect } from "./js/link.js";
import { Hud, WarMap, BuildingList, StatusBar, Toasts } from "./js/chrome.js";
import { Town } from "./js/town.js";
import { Windows, opened } from "./js/windows.js";

const HALL = "town_hall";

function App() {
  const t = town.value;
  if (!t) return html`<div class="gui-loading ok-font-body">Opening the town…</div>`;
  document.documentElement.dataset.theme = "office";     // Camp comes later (docs/design/gui-migration.md)
  const space = t.orkspaces.find((o) => o.id === t.active_orkspace);
  const ids = new Set(space ? space.buildings : t.buildings.map((b) => b.id));
  ids.add(HALL);                                         // the Town Hall stands on every canvas
  const buildings = t.buildings.filter((b) => ids.has(b.id));
  return html`<div class=${opened.value.ids.length ? "gui gui--open" : "gui"}>
    <${Hud} />
    <aside class="gui-side"><${WarMap} /><${BuildingList} buildings=${buildings} /></aside>
    <${Town} buildings=${buildings} roads=${t.roads} />
    <${Windows} />
    <${StatusBar} />
    <${Toasts} />
  </div>`;
}

connect();
render(html`<${App} />`, document.getElementById("app"));
