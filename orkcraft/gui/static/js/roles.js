// The roles' marks for Office (docs/design/portrait.md §1): one line icon per role, drawn on a 24-unit grid
// with a 1.5 stroke in the ink, no fill, so they sit with the Office look's hairlines. The role's two letters
// stay as its name for a screen reader and a tooltip. Someone else is a plain figure.
import { html } from "./html.js";

const C = (cx, cy, r) => `<circle cx="${cx}" cy="${cy}" r="${r}"/>`;
const P = (d) => `<path d="${d}"/>`;

export const ROLE_ICONS = {
  engineer: P("M8 7l-5 5 5 5M16 7l5 5-5 5M14 4l-4 16"),                                   // code brackets
  qa: C(10, 10, 6) + P("M14.5 14.5L20 20M7.5 10l2 2 3.5-3.5"),                            // a lens with a tick
  eng_manager: P("M10 3h4v4h-4zM3 17h4v4H3zM10 17h4v4h-4zM17 17h4v4h-4zM12 7v10M5 17v-5h14v5"),   // a team tree
  product_manager: P("M5 21V3M5 4h11l-2 4 2 4H5"),                                         // a flag on the road ahead
  designer: P("M12 3l6 6-3 9H9L6 9zM12 3v7M9 21h6") + C(12, 11.5, 1.5),                    // a pen nib
  game_designer: P("M7 8h10a5 5 0 0 1 5 5v1a3 3 0 0 1-5.4 1.8L15 14H9l-1.6 1.8A3 3 0 0 1 2 14v-1a5 5 0 0 1 5-5zM7 10.5v4M5 12.5h4M16 12h.01M18 14h.01"),
  aso_manager: P("M7 2h10v20H7zM11 19h2M12 14V7M9 10l3-3 3 3"),                            // a phone, rising
  marketing: P("M3 10v4h3l7 4V6l-7 4H3zM16 9a4 4 0 0 1 0 6M18.5 6.5a7.5 7.5 0 0 1 0 11"),  // a horn
  data_analyst: P("M4 20h16M7 16v-5M12 16V6M17 16V9"),                                     // bars
  founder: P("M12 2c3 2 5 6 5 10l-2 4H9l-2-4c0-4 2-8 5-10zM9 16l-3 3M15 16l3 3M12 18v4") + C(12, 9, 1.5),   // a rocket
  "": C(12, 8, 4) + P("M4 21a8 8 0 0 1 16 0"),                                             // someone else
};

/** A role's mark: its line icon, at `size` px. `mono` (its two letters) names it. */
export function RoleIcon({ role, mono, size = 24 }) {
  const body = ROLE_ICONS[role] || ROLE_ICONS[""];
  return html`<svg class="gui-role-icon" viewBox="0 0 24 24" width=${size} height=${size} role="img" aria-label=${mono}
    dangerouslySetInnerHTML=${{ __html: `<title>${mono}</title>${body}` }}></svg>`;
}
