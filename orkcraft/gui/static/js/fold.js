// Folded cards (docs/design/folded-cards.md): what folds a hut and what makes a folded one peek, one by one
// (js/hut.js) or many at once — Fold the quiet ones and Unfold all on the bare town (js/town.js), `/fold` and
// `/unfold` in the Warchief's line (js/warchief.js).
import { command } from "./link.js";
import { opened } from "./windows.js";
import { keepTall } from "./parts.js";

export const CORNER = "town_hall";          // the Hall never folds: it is the way to the Warchief

/** Why a folded hut peeks (§2): an ork of it asks, its worker failed, it is paused. */
export function reasons(b) {
  return [b.alert && `alert:${b.alert.id}`, b.state === "ERROR" && "error", b.paused && "paused"].filter(Boolean);
}

export const busy = (b) => b.garrison.some((o) => o.status === "busy") || b.state === "WORKING";

/** A hut Fold the quiet ones folds: open, not the Hall, nothing on it wants the person, not at work, not open. */
export const quiet = (b) => b.id !== CORNER && !b.folded && !reasons(b).length && !busy(b) && opened.value.active !== b.id;

/** Folds or unfolds one hut: `value` sets it, else it toggles. */
export function fold(b, value) {
  const want = value === undefined ? !b.folded : value;
  if (want && !b.folded) keepTall(b.id);   // its full height, so the huts under it rise by what it gives up
  return command("building.fold", value === undefined ? { id: b.id } : { id: b.id, value }).catch(() => {});
}

/** Fold the quiet ones among `list`; how many it folds. */
export function foldQuiet(list) {
  const ids = list.filter(quiet).map((b) => b.id);
  ids.forEach(keepTall);
  if (ids.length) command("town.fold", { ids, value: true }).catch(() => {});
  return ids.length;
}

/** Unfold every folded hut among `list`; how many it opens. */
export function unfoldAll(list) {
  const ids = list.filter((b) => b.folded).map((b) => b.id);
  if (ids.length) command("town.fold", { ids, value: false }).catch(() => {});
  return ids.length;
}
