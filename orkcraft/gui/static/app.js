// The Orkline GUI: the town over the core (gui/server.py), drawn with the design system's markup
// (design-system/components.md). Preact + signals, no build step. A calm town (docs/design/calm-town.md):
// the HUD, the map, the panel on the right, the War Map of orkspaces at the bottom left and the Warchief's line.
import { render } from "preact";
import { html } from "./js/html.js";
import { town, connect, openLink, copyText } from "./js/link.js";
import { Hud, Toasts } from "./js/chrome.js";
import { WarMap } from "./js/warmap.js";
import { wearGround } from "./js/terrain.js";
import { Town } from "./js/town.js";
import { CampTown } from "./js/camp/town.js";
import { Panel, panelShown, panelWidth, opened, inside } from "./js/windows.js";
import { Inside } from "./js/inside.js";
import { Jobs } from "./js/acts.js";
import { Orders } from "./js/orders.js";
import { VisitDialogs } from "./js/visit.js";
import { RoadDialog, RoadBar, DemolishAsked, CopyAsked } from "./js/build.js";
import { ProjectAsked } from "./js/project.js";
import { HistoryAsked } from "./js/history.js";
import { HALL } from "./js/tent.js";
import { SettingsDialog, UsageAsk } from "./js/settings.js";
import { GoogleWizard } from "./js/accounts.js";
import { UpdateAsk } from "./js/update.js";
import { Onboarding } from "./js/onboarding.js";
import { Menu } from "./js/menu.js";
import { WarchiefLine } from "./js/warchief.js";
import { OrkConsole } from "./js/slots.js";
import { Overlays } from "./js/types.js";
import { Pocket, narrow } from "./js/pocket.js";
import { CoverSheet } from "./js/sheet.js";
import { Portrait } from "./js/portrait.js";
import { watchErrors } from "./js/crashes.js";
import { CommentLayer, FixesDialog } from "./js/fixes.js";
import { LastLook } from "./js/lastlook.js";

function App() {
  const t = town.value;
  if (!t) return html`<div class="gui-loading ok-font-body">Opening the town…</div>`;
  // Two looks, the person's (docs/design/portrait.md §3): Camp on the camp theme, Office, calm, on the office
  // theme (town.css draws both, office.css only Office). Camp's town is v3's rows and loop (js/camp/), Office's its
  // cards (js/town.js): one town, two drawings. The words are the same in both.
  const look = t.look === "office" ? "office" : "camp";
  const root = document.documentElement;
  if (root.dataset.look !== look) { root.dataset.look = look; root.dataset.theme = look; }
  const space = t.orkspaces.find((o) => o.id === t.active_orkspace);
  // The town's ground is the open orkspace's biome, its colour and its glyphs (docs/design/war-map.md §3).
  wearGround(space ? space.biome : "dirt", look);
  const ids = new Set(space ? space.buildings : t.buildings.map((b) => b.id));
  ids.delete(HALL);                                      // the Warchief's line is the hall's way in
  const buildings = t.buildings.filter((b) => ids.has(b.id));
  return html`<div class="gui">
    <${Hud} />
    ${narrow.value ? html`<${Pocket} buildings=${buildings} />`
      : look === "camp" && inside.value ? html`<${Inside} />`
      : look === "camp" ? html`<${CampTown} buildings=${buildings} roads=${t.roads} />`
      : html`<${Town} buildings=${buildings} roads=${t.roads} />`}
    <div class="gui-foot" style=${`margin-right:${panelShown() && !opened.value.full ? panelWidth.value : 0}px`}>
      ${!narrow.value && html`<${WarMap} />`}<${WarchiefLine} /><${OrkConsole} /></div>
    ${!narrow.value && html`<${Portrait} corner=${true} />`}
    <${Panel} />
    <${Toasts} />
    ${narrow.value && html`<${CoverSheet} buildings=${buildings} />`}
    <${SettingsDialog} />
    <${GoogleWizard} />
    <${UsageAsk} />
    <${UpdateAsk} />
    <${Orders} />
    <${VisitDialogs} />
    <${Jobs} />
    <${Overlays} />
    <${RoadDialog} />
    <${RoadBar} />
    <${DemolishAsked} />
    <${CopyAsked} />
    <${ProjectAsked} />
    <${HistoryAsked} />
    <${Menu} />
    <${Onboarding} />
    ${!t.onboarding && html`<${LastLook} />`}
    <${FixesDialog} />
    <${CommentLayer} />
  </div>`;
}

// A link to another site opens in the browser, never in the town's own window: a page's Markdown or an ork's text may
// carry one without target=_blank, and the app's window would leave the town for it.
document.addEventListener("click", (e) => {
  const a = e.target instanceof Element && e.target.closest("a[href]");
  if (!a || e.defaultPrevented || !/^https?:/i.test(a.href) || new URL(a.href).origin === location.origin) return;
  e.preventDefault();
  openLink(a.href);
});

watchErrors();
connect();
render(html`<${App} />`, document.getElementById("app"));

// Copy in a window whose shell has no Edit menu (a webview): Ctrl/⌘ + C puts the selected text on the clipboard itself.
window.addEventListener("keydown", (e) => {
  if (!(e.ctrlKey || e.metaKey) || e.shiftKey || e.altKey || (e.key !== "c" && e.key !== "C")) return;
  const on = document.activeElement;
  if (on && (on.tagName === "INPUT" || on.tagName === "TEXTAREA" || on.closest?.(".xterm"))) return;   // its own copy
  const text = window.getSelection ? window.getSelection().toString() : "";
  if (text) copyText(text);
});
