// Signals as UI drawn by the product (design-system-v3.md §5): ❓ ! ⏳ win by value, never in the art.
import { html, cls } from "../html.js";

const HOURGLASS = html`<svg viewBox="0 0 10 12" width="14" height="17" aria-hidden="true"><path d="M1 0h8v2.5L6 6l3 3.5V12H1V9.5L4 6 1 2.5z" fill="currentColor"/></svg>`;

/** ❓ ! ⏳ as UI over a building's door: 28 px on a dark plate with an outline and a keyline (§5). */
export function Badge({ kind, x, y, title = "", onClick = null }) {
  return html`<span class=${cls("gui-camp__badge", `is-${kind}`, { "is-button": !!onClick })} style=${`left:${x}px;top:${y}px`}
      title=${title} role=${onClick ? "button" : "img"} aria-label=${title}
      onClick=${onClick ? (e) => { e.stopPropagation(); onClick(); } : undefined}>${kind === "held" ? HOURGLASS : kind === "ask" ? "?" : "!"}</span>`;
}

