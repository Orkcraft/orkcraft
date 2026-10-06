// The Orkcraft GUI, Office look: the town over the core (gui/server.py), drawn with the design
// system's markup (design-system/components.md). Preact + signals, no build step.
import { render } from "preact";
import { html } from "./js/html.js";
import { town, connect } from "./js/link.js";
import { Hud, WarMap, StatusBar, Toasts } from "./js/chrome.js";
import { Town } from "./js/town.js";
import { Opened } from "./js/windows.js";
import { LakeWindow } from "./js/lake.js";
import { Selected } from "./js/console.js";
import { Jobs } from "./js/acts.js";
import { Orders } from "./js/orders.js";
import { BuildDialog, RoadDialog, RoadBar } from "./js/build.js";

import { HALL } from "./js/tent.js";
import { SettingsDialog } from "./js/settings.js";
import { Advisor } from "./js/advisor.js";

function App() {
  const t = town.value;
  if (!t) return html`<div class="gui-loading ok-font-body">Opening the town…</div>`;
  document.documentElement.dataset.theme = t.look;      // office | camp (orkcraft gui --look; Shift by the hour)
  const space = t.orkspaces.find((o) => o.id === t.active_orkspace);
  const ids = new Set(space ? space.buildings : t.buildings.map((b) => b.id));
  const office = t.look === "office";
  if (office) ids.delete(HALL);                          // Office: the Control panel is the pinned advisor
  else ids.add(HALL);                                    // Camp: the Town Hall stands on every canvas
  const buildings = t.buildings.filter((b) => ids.has(b.id));
  return html`<div class="gui">
    <${Hud} />
    <${Town} buildings=${buildings} roads=${t.roads} />
    <div class="gui-strip"><${WarMap} /><${Selected} />${office && html`<${Advisor} />`}</div>
    <${Opened} />
    <${LakeWindow} />
    <${StatusBar} />
    <${Toasts} />
    <${SettingsDialog} />
    <${Orders} />
    <${Jobs} />
    <${BuildDialog} />
    <${RoadDialog} />
    <${RoadBar} />
  </div>`;
}

connect();
render(html`<${App} />`, document.getElementById("app"));
