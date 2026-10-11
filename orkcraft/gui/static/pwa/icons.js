// A building's mark on the phone (gui/pwa.py): Camp draws the type's header sprite, as the desktop's town does
// (design/system/sprites/buildings, served as sprites/<type>.png); Office its line icon. PATHS is the desktop's
// (gui/static/js/icons.js), the same lines (tests/test_pwa.py keeps them so).

import { h } from "./util.js";

export const PATHS = {
  pit: "M2 9.5v4h12v-4M2 9.5h3.5l1 1.5h3l1-1.5H14M8 2v6M5.5 5.5 8 8l2.5-2.5",                      // inbox tray
  watchtower: "M8 9v5.5M5.5 14.5h5M5 4.5a4.2 4.2 0 0 0 0 6M11 4.5a4.2 4.2 0 0 1 0 6M3 2.5a7 7 0 0 0 0 10M13 2.5a7 7 0 0 1 0 10M8 7.8v.4", // broadcast
  signpost: "M8 1.5v13M3 3.5h8l2 2-2 2H3zM13 8.5H6l-2 2 2 2h7z",                                     // signpost
  mill: "M2.5 5.5h9l-2.5-2.5M13.5 10.5h-9L7 13",                                                     // transform arrows
  horn: "M4 11V7a4 4 0 0 1 8 0v4l1.5 1.5h-11zM6.5 14h3",                                               // bell
  fields: "M2 2.5h12v11H2zM6 2.5v11M10 2.5v11M3.5 5h1M7.5 5h1M7.5 7.5h1M11.5 5h1",                    // kanban
  barracks: "M6 7.5a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5zM1.5 14c0-2.5 2-4 4.5-4s4.5 1.5 4.5 4M11 2.8a2.3 2.3 0 0 1 0 4.4M12.5 10.3c1.3.6 2 1.9 2 3.7", // users
  council: "M2 3h12v8H7l-3 2.5V11H2zM5.5 7l1.8 1.8L10.5 5.5",                                       // review: message with a check
  war_drum: "M2 3.5h12v10H2zM2 6.5h12M5 1.8v3M11 1.8v3M5 9h1.5M9.5 9H11M5 11h1.5",                    // calendar
  forest: "M2 2v10.5h4M2 6h4M6 4.5h3l1 1h4v3H6zM6 11h3l1 1h4v2H6z",                                   // folder tree
  mine: "M2.5 7C5 3.5 11 3.5 13.5 7M8 4.6 3.5 14.5",                                                 // pickaxe
  gramophone: "M2.5 14.5h7M6 14.5v-4l2.5-2.5M8.5 8 13.5 2.5M8.5 8l6 .5M13.5 2.5c1.5 2 1.5 4.5 1 6",               // gramophone
  scrolls: "M1.5 3h4.5a2 2 0 0 1 2 2v9a1.5 1.5 0 0 0-1.5-1.5h-5zM14.5 3H10a2 2 0 0 0-2 2v9a1.5 1.5 0 0 1 1.5-1.5h5z", // open book
  lake: "M1.5 8s2.5-4.5 6.5-4.5S14.5 8 14.5 8s-2.5 4.5-6.5 4.5S1.5 8 1.5 8zM8 10a2 2 0 1 0 0-4 2 2 0 0 0 0 4z", // eye
  forge: "M4 5.5v8M4 5.5a1.8 1.8 0 1 0 0-3.6 1.8 1.8 0 0 0 0 3.6zM12 10.5a1.8 1.8 0 1 0 0 3.6 1.8 1.8 0 0 0 0-3.6zM12 10.5V6a2 2 0 0 0-2-2H7.5M9 2.5 7.5 4 9 5.5", // pull request
  loot: "M8 1.5 13.5 3.5v4c0 3.5-2.5 6-5.5 7-3-1-5.5-3.5-5.5-7v-4zM5.5 8l1.8 1.8L10.5 6.5",             // shield check
  crag: "M2 14h12M3.5 14V9M6.5 14V4.5M9.5 14V7M12.5 14V2.5",                                        // bar chart
  catapult: "M14.5 1.5 1.5 7l5 2.5 2.5 5zM14.5 1.5 6.5 9.5",                                        // send
  town_hall: "M2.5 4h7M12.5 4h1M2.5 12h1M6.5 12h7M9.5 2.5v3M5 10.5v3M2.5 8h4M9.5 8h4M6.5 6.5v3",      // sliders
  workshop: "M2 2.5h12v11H2zM4.5 6l2 2-2 2M8 10.5h3.5",                                              // terminal
  lab: "M9.8 4.2a.67.67 0 0 0 0 .93l1.07 1.07a.67.67 0 0 0 .93 0l2.51-2.51a4 4 0 0 1-5.29 5.29l-4.61 4.61a1.41 1.41 0 0 1-2-2l4.61-4.61a4 4 0 0 1 5.29-5.29l-2.51 2.51z",   // wrench: the Mechanic's (the gear is Settings')
  ux_lab: "M6 1.5h4M6.8 1.5v4.8L3 12.6a1.4 1.4 0 0 0 1.2 1.9h7.6a1.4 1.4 0 0 0 1.2-1.9L9.2 6.3V1.5M4.6 10h6.8",   // flask
  custom: "M8 1.5 14 4.5v7L8 14.5 2 11.5v-7zM2 4.5 8 7.5l6-3M8 7.5v7",                                // box
};
PATHS.loot_vault = PATHS.loot;

const SVG = "http://www.w3.org/2000/svg";
// The types with a sprite of their own (sprites/buildings/<type>); any other wears the custom one.
const SPRITES = new Set(["barracks", "catapult", "council", "crag", "custom", "fields", "forest", "forge", "gramophone",
  "horn", "lab", "lake", "loot", "mill", "mine", "pit", "scrolls", "signpost", "town_hall", "ux_lab", "war_drum",
  "watchtower", "workshop"]);

export function spriteName(type) {
  const name = type === "loot_vault" ? "loot" : type;
  return SPRITES.has(name) ? name : "custom";
}

/** The building's mark in the look: an <img> of its sprite in Camp, a line icon in Office. */
export function mark(type, camp) {
  if (camp) {
    const name = spriteName(type);
    return h("img", { class: "mark-sprite", src: `sprites/${name}.png`, srcset: `sprites/${name}.png 1x, sprites/${name}@2x.png 2x`,
      alt: "", draggable: "false" });
  }
  const svg = document.createElementNS(SVG, "svg");
  svg.setAttribute("viewBox", "0 0 16 16");
  svg.setAttribute("class", "mark-line");
  svg.setAttribute("aria-hidden", "true");
  const path = document.createElementNS(SVG, "path");
  path.setAttribute("d", PATHS[type] || PATHS.custom);
  svg.append(path);
  return svg;
}
