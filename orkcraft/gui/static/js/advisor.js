// Office only: the Control panel (the Town Hall) is no hut on the town but an advisor pinned at the
// strip's bottom right — the ork mark (design-system/logo), gold under the mouse — with the hall's closed card over it at
// the left, as a speech bubble without a name (its `card(b)`, js/buildings/town_hall.js). A press on
// the advisor selects the hall, as a press on its hut does in Camp. While a building is selected its
// Command Card stands over the advisor (layout.css .gui-advisor).
import { html, cls } from "./html.js";
import { town, say } from "./link.js";
import { opened, openBuilding } from "./windows.js";
import { typeModule } from "./types.js";
import { HALL } from "./tent.js";

export function Advisor() {
  const t = town.value;
  const b = t.buildings.find((x) => x.id === HALL);
  if (!b) return null;
  const mod = b.page ? typeModule(b.type) : null;
  const active = opened.value.active;
  return html`<div class=${cls("gui-advisor", { "is-quiet": !!active && active !== HALL, "is-selected": active === HALL,
                                                 "is-alert": !!b.alert })}>
    ${mod && mod.card && html`<div class="gui-advisor__bubble ok-font-status" role="dialog" aria-label=${say(b.title)}>
      ${mod.card(b)}</div>`}
    <button class="gui-advisor__face" title=${say(b.title)} aria-label=${say(b.title)} onClick=${() => openBuilding(HALL)}>
      <img src="/ds/logo/ork-mark.svg" width="72" height="48" alt="" />
      ${b.alert && html`<span class="ok-word gui-advisor__ask">?</span>`}
    </button>
  </div>`;
}
