// The Orkcraft GUI: the town over the core (gui/server.py), drawn with the design system's markup
// (design-system/components.md). Preact + signals, no build step. A calm town (docs/design/calm-town.md):
// the HUD, the map, the panel on the right, the War Map of orkspaces at the bottom left and the Warchief's line.
import { render } from "preact";
import { html } from "./js/html.js";
import { town, connect } from "./js/link.js";
import { Hud, Toasts } from "./js/chrome.js";
import { WarMap } from "./js/warmap.js";
import { wearGround } from "./js/terrain.js";
import { Town } from "./js/town.js";
import { Panel, panelShown, panelWidth, opened } from "./js/windows.js";
import { Jobs } from "./js/acts.js";
import { Orders } from "./js/orders.js";
import { BuildDialog, RoadDialog, RoadBar, DemolishAsked } from "./js/build.js";
import { HALL } from "./js/tent.js";
import { SettingsDialog } from "./js/settings.js";
import { Menu } from "./js/menu.js";
import { WarchiefLine } from "./js/warchief.js";

function App() {
  const t = town.value;
  if (!t) return html`<div class="gui-loading ok-font-body">Opening the town…</div>`;
  // One look, Office, on the Camp design system (index.html: data-theme camp, data-look office; office.css).
  const space = t.orkspaces.find((o) => o.id === t.active_orkspace);
  // The town's ground is the open orkspace's biome, its colour and its glyphs (docs/design/war-map.md §3).
  wearGround(space ? space.biome : "dirt");
  const ids = new Set(space ? space.buildings : t.buildings.map((b) => b.id));
  ids.delete(HALL);                                      // the Warchief's line is the hall's way in
  const buildings = t.buildings.filter((b) => ids.has(b.id));
  return html`<div class="gui">
    <${Hud} />
    <${Town} buildings=${buildings} roads=${t.roads} />
    <div class="gui-foot" style=${`margin-right:${panelShown() && !opened.value.full ? panelWidth.value : 0}px`}>
      <${WarMap} /><${WarchiefLine} /></div>
    <${Panel} />
    <${Toasts} />
    <${SettingsDialog} />
    <${Orders} />
    <${Jobs} />
    <${BuildDialog} />
    <${RoadDialog} />
    <${RoadBar} />
    <${DemolishAsked} />
    <${Menu} />
  </div>`;
}

connect();
render(html`<${App} />`, document.getElementById("app"));
