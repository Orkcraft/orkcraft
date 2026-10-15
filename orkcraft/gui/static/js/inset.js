// What covers the town from below: the top (in window pixels) of a panel that stays open over the Warchief's line —
// Mission 1's quest log, a building's setup (js/warchief.js) — or null. The camp keeps its work above it
// (js/camp/town.js), so no cart runs behind the panel.
import { signal } from "@preact/signals";

export const coverTop = signal(null);
