// A building's window laid out from its UI document (design/ui.py, schemas/building-ui.v1.json):
// groups split in rows or columns by share, each pane wearing its font and tone roles as the classes
// /roles.css defines. The page draws a group as written; what fills a pane is the building's own.
import { html, cls } from "./html.js";

function flex(size) {
  return size === "auto" ? "flex: none" : `flex: ${Number(size) || 1} 1 0`;
}

function Pane({ pane, fill }) {
  const body = fill ? fill(pane) : null;
  if (body === null || body === undefined || pane.hidden) return null;   // a dynamic pane shows itself
  const roles = cls("gui-pane", {
    [`ok-font-${pane.font}`]: !!pane.font,
    [`ok-tone-${String(pane.tone || "").replace(/[._]/g, "-")}`]: !!pane.tone,
    "is-auto": pane.size === "auto",
  });
  return html`<section class=${roles} style=${flex(pane.size)} data-pane=${pane.id}>
    ${pane.title && html`<h3 class="gui-pane__title ok-font-heading">${pane.title}</h3>`}
    ${body}
  </section>`;
}

function Group({ split, items, size, panes }) {
  return html`<div class=${cls("gui-split", { "is-row": split === "row" })} style=${size === undefined ? "" : flex(size)}>
    ${items.map((item, i) => "split" in item
      ? html`<${Group} key=${i} split=${item.split} items=${item.panes || []} size=${item.size} panes=${panes} />`
      : html`<${Pane} key=${item.id} pane=${item} fill=${panes[item.id]} />`)}
  </div>`;
}

/** `panes`: pane id → (pane) => content, or null while the pane has nothing to show. */
export function Layout({ doc, panes }) {
  return html`<${Group} split=${doc.split || "column"} items=${doc.panes || []} panes=${panes} />`;
}
