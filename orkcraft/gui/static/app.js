// The Orkcraft GUI, Office look: the town over the core (gui/server.py), drawn with the design
// system's markup (design-system/components.md). Preact + signals, no build step.
import { render } from "preact";
import { html } from "./js/html.js";
import { town, connect } from "./js/link.js";
import { Hud, WarMap, BuildingList, StatusBar, Toasts } from "./js/chrome.js";
import { Town } from "./js/town.js";
import { Windows, opened } from "./js/windows.js";
import { Orders } from "./js/orders.js";
import { BuildDialog, RoadDialog, RoadBar } from "./js/build.js";

import { HALL } from "./js/tent.js";

function App() {
  const t = town.value;
  if (!t) return html`<div class="gui-loading ok-font-body">Opening the town…</div>`;
  document.documentElement.dataset.theme = t.look;      // office | camp (orkcraft gui --look; Shift by the hour)
  const space = t.orkspaces.find((o) => o.id === t.active_orkspace);
  const ids = new Set(space ? space.buildings : t.buildings.map((b) => b.id));
  ids.add(HALL);                                         // the Town Hall stands on every canvas
  const buildings = t.buildings.filter((b) => ids.has(b.id));
  const standing = new Set(t.buildings.map((b) => b.id));       // a demolished building's tab is gone
  const open = opened.value.ids.some((id) => standing.has(id));
  return html`<div class=${open ? "gui gui--open" : "gui"}>
    <${Hud} />
    <aside class="gui-side"><${WarMap} /><${BuildingList} buildings=${buildings} /></aside>
    <${Town} buildings=${buildings} roads=${t.roads} />
    <${Windows} />
    <${StatusBar} />
    <${Toasts} />
    <${Orders} />
    <${BuildDialog} />
    <${RoadDialog} />
    <${RoadBar} />
  </div>`;
}

connect();
render(html`<${App} />`, document.getElementById("app"));
